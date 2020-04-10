from functools import wraps
from timeit import default_timer
import json
import io

from pywps import Process, ComplexInput, ComplexOutput, Format
from pywps.app.exceptions import ProcessError
import pywps.configuration as config

import datacube
from datacube.utils.geometry import Geometry, CRS
from datacube.api.core import output_geobox, query_group_by, apply_aliases

import rasterio.features

import xarray
import numpy as np

import boto3
import botocore
from botocore.client import Config

from dateutil.parser import parse


FORMATS = {
    # Defines the format for the returned object
    # in this case a JSON object containing a CSV
    'output_json': Format('application/vnd.terriajs.catalog-member+json',
                          schema='https://tools.ietf.org/html/rfc7159',
                          encoding="utf-8"),
    'point': Format('application/vnd.geo+json',
                    schema='http://geojson.org/geojson-spec.html#point'),
    'polygon': Format('application/vnd.geo+json',
                      schema='http://geojson.org/geojson-spec.html#polygon'),
    'datetime': Format('application/vnd.geo+json',
                       schema='http://www.w3.org/TR/xmlschema-2/#dateTime')
}

GB = 1.e9
MAX_BYTES_IN_GB = 20.0
MAX_BYTES_PER_OBS_IN_GB = 2.0


def log_call(func):
    @wraps(func)
    def log_wrapper(*args, **kwargs):
        name = func.__name__
        for index, arg in enumerate(args):
            try:
                arg_name = func.__code__.co_varnames[index]
            except (AttributeError, KeyError, IndexError):
                arg_name = f'arg #{index}'
            print(f'{name} {arg_name}: {arg}')
        for key, value in kwargs.items():
            print(f'{name} {key}: {value}')

        start = default_timer()
        result = func(*args, **kwargs)
        end = default_timer()
        print('{} returned {}'.format(name, result))
        print('{} took {:.3f}s'.format(name, end - start))
        return result

    return log_wrapper


@log_call
def _uploadToS3(filename, data, mimetype):
    session = boto3.Session()
    bucket = config.get_config_value('s3', 'bucket')
    s3 = session.client('s3')
    s3.upload_fileobj(data,
                      bucket,
                      filename,
                      ExtraArgs={'ACL': 'public-read', 'ContentType': mimetype})

    # Create unsigned s3 client for determining public s3 url
    s3 = session.client('s3', config=Config(signature_version=botocore.UNSIGNED))
    return s3.generate_presigned_url(ClientMethod='get_object',
                                     ExpiresIn=0,
                                     Params={'Bucket': bucket, 'Key': filename})


@log_call
def upload_chart_html_to_S3(chart, process_id):
    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    return _uploadToS3(process_id + '/chart.html', html_bytes, 'text/html')


@log_call
def upload_chart_svg_to_S3(chart, process_id):
    img_io = io.StringIO()
    chart.save(img_io, format='svg')
    img_bytes = io.BytesIO(img_io.getvalue().encode())
    return _uploadToS3(process_id + '/chart.svg', img_bytes, 'image/svg+xml')


# From https://stackoverflow.com/a/16353080
class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)


def geometry_mask(geom, geobox, all_touched=False, invert=False):
    return rasterio.features.geometry_mask([geom.to_crs(geobox.crs)],
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)


def wofls_fuser(dest, src):
    where_nodata = (src & 1) == 0
    np.copyto(dest, src, where=where_nodata)
    return dest


# Default function for querying and loading data for WPS processes
# Uses dc.load and groups by solar day
@log_call
def _getData(product, query):
    with datacube.Datacube() as dc:
        print("loading data!", query)

        datasets = dc.find_datasets(product=product, **{k: v
                                                        for k, v in query.items()
                                                        if k not in ['dask_chunks',
                                                                     'fuse_func',
                                                                     'resampling',
                                                                     'skip_broken_datasets']})
        if len(datasets) == 0:
            return xarray.Dataset()

        datacube_product = datasets[0].type

        geobox = output_geobox(grid_spec=datacube_product.grid_spec, **query)
        grouped = dc.group_datasets(datasets, query_group_by(group_by='solar_day', **query))

        measurement_dicts = datacube_product.lookup_measurements(query.get('measurements'))

        byte_count = 1
        for x in geobox.shape:
            byte_count *= x
        for x in grouped.shape:
            byte_count *= x
        byte_count *= sum(np.dtype(m.dtype).itemsize for m in measurement_dicts.values())

        print('byte count for query: ', byte_count)
        if byte_count > MAX_BYTES_IN_GB * GB:
            raise ProcessError(("requested area requires {}GB data to load - "
                                "maximum is {}GB").format(int(byte_count / GB), MAX_BYTES_IN_GB))

        print('grouped shape', grouped.shape)
        assert len(grouped.shape) == 1
        bytes_per_obs = byte_count / grouped.shape[0]
        if bytes_per_obs > MAX_BYTES_PER_OBS_IN_GB * GB:
            raise ProcessError(("requested time slices each requires {}GB data to load - "
                                "maximum is {}GB").format(int(bytes_per_obs / GB), MAX_BYTES_PER_OBS_IN_GB))

        result = dc.load_data(grouped, geobox, measurement_dicts,
                              resampling=query.get('resampling'),
                              fuse_func=query.get('fuse_func'),
                              dask_chunks=query.get('dask_chunks', {'time': 1}),
                              skip_broken_datasets=query.get('skip_broken_datasets', False))

        data = apply_aliases(result, datacube_product, query.get('measurements'))
        print("data load done", product, data)
        return data

# Default function for processing loaded data
# Datas is a list of Datasets (returned from dc.load and masked if polygons)
@log_call
def _processData(datas, **kwargs):
    raise ProcessError('no _processData specified')


# Pulls datetime output of JSON start / end date inputs
def _datetimeExtractor(data):
    return parse(json.loads(data)["properties"]["timestamp"]["date-time"])


def _get_feature(request):
    stream = request.inputs['geometry'][0].stream
    request_json = json.loads(stream.readline())

    features = request_json['features']
    if len(features) < 1:
        # can't drill if there is no geometry
        raise ProcessError("no features specified")

    if len(features) > 1:
        # do we need multipolygon support here?
        raise ProcessError("multiple features specified")

    feature = features[0]

    if hasattr(request_json, 'crs'):
        crs = CRS(request_json['crs']['properties']['name'])
    elif hasattr(feature, 'crs'):
        crs = CRS(feature['crs']['properties']['name'])
    else:
        # http://geojson.org/geojson-spec.html#coordinate-reference-system-objects
        crs = CRS('urn:ogc:def:crs:OGC:1.3:CRS84')

    return Geometry(feature['geometry'], crs)


def _get_time(request):
    if 'start' not in request.inputs or 'end' not in request.inputs:
        return None

    def _datetimeExtractor(data):
        return parse(json.loads(data)["properties"]["timestamp"]["date-time"])

    return (_datetimeExtractor(request.inputs['start'][0].data),
            _datetimeExtractor(request.inputs['end'][0].data))


# GeometryDrill is the base class providing Datacube WPS functionality.
# It is a pywps Process class that has been extended to provide additional
# functionality specific to Datacube.
# In order to create a custom drill, GeometryDrill can be subclassed or
# passed arguments on construction to modify it's behavior.
# :param handler: Function to process loaded data. The function should accept a list of xarrays as loaded by datacube
# :param identifier: String that identifies this process (PyWPS)
# :param title: Human readable String for the name of this process (PyWPS)
# :param abstract: Human readable String for defining any information about this process (PyWPS)
# :param version: String containing a version identifier for this process (PyWPS)
# :param store_supported: Bool, If true PyWPS will allow storing local files as outputs (PyWPS)
# :param status_supported:
#      Bool, If true PyWPS will allow storing a status file for tracking the process execution (PyWPS)
# :param products: List of Strings, Contains the datacube product names of products to be loaded by this process
# :param geometry_type: currently "polygon" or "point"
# :param custom_inputs: Optional List of PyWPS Input types, otherwise will default to, geometry, start and end dates
# :param custom_outputs:
#      Optional List of PyWPS Output types, otherwise will default to a JSON object containing a timeseries
# :param custom_data_loader: Optional Function for loading data
# :param mask: Bool, if True, data will be masked to the geometry input
class GeometryDrill(Process):

    def __init__(self, handler, identifier, title, abstract='',
                 version='None', store_supported=False, status_supported=False,
                 products=None, geometry_type="polygon", custom_inputs=None,
                 custom_outputs=None, custom_data_loader=None,
                 mask=True):

        assert products is not None
        assert geometry_type in ["polygon", "point"]

        if custom_inputs is None:
            inputs = [ComplexInput('geometry', 'Geometry', supported_formats=[FORMATS[geometry_type]]),
                      ComplexInput('start', 'Start Date', supported_formats=[FORMATS['datetime']]),
                      ComplexInput('end', 'End date', supported_formats=[FORMATS['datetime']])]
        else:
            inputs = custom_inputs

        if custom_outputs is None:
            outputs = [ComplexOutput('timeseries', 'Timeseries Drill',
                                     supported_formats=[FORMATS['output_json']], as_reference=False)]
        else:
            outputs = custom_outputs

        self.products = products
        self.custom_handler = handler
        self.geometry_type = geometry_type
        self.custom_outputs = custom_outputs
        self.data_loader = _getData if custom_data_loader is None else custom_data_loader
        self.do_mask = mask

        super().__init__(handler=self._handler,
                         identifier=identifier,
                         version=version,
                         title=title,
                         abstract=abstract,
                         inputs=inputs,
                         outputs=outputs,
                         store_supported=store_supported,
                         status_supported=status_supported)

    def _handler(self, request, response):
        time = _get_time(request)
        feature = _get_feature(request)

        start_time = default_timer()
        data = dict()
        for p in self.products:
            product = p['name']
            query = {'geopolygon': feature}
            if time is not None:
                query.update({'time': time})
            if 'additional_query' in p:
                query.update(p['additional_query'])
            data[product] = self.data_loader(product, query)

        masked = dict()
        if self.geometry_type == 'point' or not self.do_mask:
            masked = data
        elif len(data) != 0:
            masked = dict()
            for k, d in data.items():
                if len(d.variables) > 0:
                    mask = geometry_mask(feature, d.geobox, invert=True)
                    for band in d.data_vars:
                        try:
                            d[band] = d[band].where(mask, other=d[band].attrs['nodata'])
                        except AttributeError:
                            d[band] = d[band].where(mask)
                masked[k] = d

        print('time elasped in load: {}'.format(default_timer() - start_time))

        outputs = self.custom_handler(masked, process_id=self.uuid)

        print('time elasped in process: {}'.format(default_timer() - start_time))

        for ident, output_value in outputs.items():
            if "data" in output_value:
                response.outputs[ident].data = output_value['data']
            if "output_format" in output_value:
                response.outputs[ident].output_format = output_value['output_format']
            if "url" in output_value:
                response.outputs[ident].url = output_value['url']
        return response
