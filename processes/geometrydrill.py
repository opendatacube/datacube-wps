import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS
from pywps.app.exceptions import ProcessError
from osgeo import ogr
import json

from timeit import default_timer as timer

import datacube
from datacube.utils import geometry
from datacube.api.core import output_geobox, query_group_by, apply_aliases

import rasterio.features

import csv
import io
import xarray
import numpy

import boto3
import botocore
from botocore.client import Config
import pywps.configuration as config

from dateutil.parser import parse
from concurrent.futures import ProcessPoolExecutor

def _uploadToS3(filename, data, mimetype):
    session = boto3.Session()
    bucket = config.get_config_value('s3', 'bucket')
    s3 = session.client('s3')
    s3.upload_fileobj(
        data,
        bucket,
        filename,
        ExtraArgs={
            'ACL':'public-read',
            'ContentType': mimetype
        }
    )
    # Create unsigned s3 client for determining public s3 url
    s3 = session.client('s3', config=Config(signature_version=botocore.UNSIGNED))
    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        ExpiresIn=0,
        Params={
            'Bucket': bucket,
            'Key': filename
        }
    )
    return url

# From https://stackoverflow.com/a/16353080
class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)

# Defines the format for the returned object
# in this case a JSON object containing a CSV
_json_format = Format('application/vnd.terriajs.catalog-member+json',
                     schema='https://tools.ietf.org/html/rfc7159',
                     encoding="utf-8")

def geometry_mask(geoms, src_crs, geobox, all_touched=False, invert=False):
    gs = [geometry.Geometry(geom, crs=datacube.utils.geometry.CRS(src_crs)).to_crs(geobox.crs) for geom in geoms]
    return rasterio.features.geometry_mask(gs,
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)

# Default function for querying and loading data for WPS processes
# Uses dc.load and groups by solar day
def _getData(shape, product, crs, time=None, extra_query={}):
    with datacube.Datacube() as dc:
        dc_crs = datacube.utils.geometry.CRS(crs)
        g = geometry.Geometry(shape, crs=dc_crs)
        query = {
            'geopolygon': g
        }
        if time is not None:
            first, second = time;
            time = (first.strftime("%Y-%m-%d"), second.strftime("%Y-%m-%d"))
            query['time'] = time
        final_query = {**query, **extra_query}
        print("loading data!", final_query)

        datasets = dc.find_datasets(product=product, **{k: v
                                                        for k, v in final_query.items()
                                                        if k not in ['dask_chunks',
                                                                     'fuse_func',
                                                                     'resampling',
                                                                     'skip_broken_datasets']})
        if len(datasets) == 0:
            raise ProcessError("query returned no data")

        datacube_product = datasets[0].type

        geobox = output_geobox(grid_spec=datacube_product.grid_spec, **final_query)
        grouped = dc.group_datasets(datasets, query_group_by(group_by='solar_day', **final_query))

        measurement_dicts = datacube_product.lookup_measurements(final_query.get('measurements'))

        byte_count = 1
        for x in geobox.shape:
            byte_count *= x
        for x in grouped.shape:
            byte_count *= x
        byte_count *= sum(numpy.dtype(m.dtype).itemsize for m in measurement_dicts.values())

        print('byte count for query: ', byte_count)
        if byte_count > 2.0e9:
            raise ProcessError("requested area requires {}GB data to load - maximum is 2GB".format(int(byte_count / 1e9)))

        result = dc.load_data(grouped, geobox, measurement_dicts,
                              resampling=final_query.get('resampling'),
                              fuse_func=final_query.get('fuse_func'),
                              dask_chunks=final_query.get('dask_chunks', {'time': 1}),
                              skip_broken_datasets=final_query.get('skip_broken_datasets', False))

        data = apply_aliases(result, datacube_product, final_query.get('measurements'))
        print("data load done", product, data)
        return data

# Default function for processing loaded data
# Datas is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(datas, **kwargs):

    output_json = json.dumps({"hello": "world"}, cls=DatetimeEncoder)

    output_str = output_json

    response.outputs['timeseries'].output_format = str(_json_format)
    response.outputs['timeseries'].data = output_str

    return response


# Product output JSON
def _createOutputJson(data, **kwargs):
  pass

# Pulls datetime output of JSON start / end date inputs
def _datetimeExtractor(data):
  return parse(json.loads(data)["properties"]["timestamp"]["date-time"])

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
# :param status_supported: Bool, If true PyWPS will allow storing a status file for tracking the process execution (PyWPS)
# :param products: List of Strings, Contains the datacube product names of products to be loaded by this process
# :param geometry_type: currently "polygon" or "point"
# :param custom_inputs: Optional List of PyWPS Input types, otherwise will default to, geometry, start and end dates
# :param custom_outputs: Optional List of PyWPS Output types, otherwise will default to a JSON object containing a timeseries
# :param custom_data_loader: Optional Function for loading data
# :param mask: Bool, if True, data will be masked to the geometry input
class GeometryDrill(Process):

    def __init__(self, handler, identifier, title, abstract='',
                 version='None', store_supported=False, status_supported=False,
                 products=[], geometry_type="polygon", custom_inputs=None,
                 custom_outputs=None, custom_data_loader=None,
                 mask=True):

        assert len(products) > 0
        assert geometry_type in [ "polygon", "point" ]
        if custom_inputs is None:
          inputs = [ComplexInput('geometry',
                                 'Geometry',
                                 supported_formats=[
                                                      Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#' + geometry_type)
                                                   ]),
                    ComplexInput('start',
                                 'Start Date',
                                 supported_formats=[
                                                      Format('application/vnd.geo+json', schema='http://www.w3.org/TR/xmlschema-2/#dateTime')
                                                   ]),
                    ComplexInput('end',
                                 'End date',
                                 supported_formats=[
                                                      Format('application/vnd.geo+json', schema='http://www.w3.org/TR/xmlschema-2/#dateTime')
                                                   ])]
        else:
          inputs = custom_inputs
        if custom_outputs is None:
          outputs = [ComplexOutput('timeseries',
                                   'Timeseries Drill',
                                   supported_formats=[
                                                          _json_format
                                                     ],
                                   as_reference=False)]
        else:
          outputs = custom_outputs

        self.products = products
        self.custom_handler = handler
        self.geometry_type = geometry_type
        self.custom_outputs = custom_outputs
        self.data_loader = _getData if custom_data_loader is None else custom_data_loader
        self.do_mask = mask

        super(GeometryDrill, self).__init__(
            handler          = self._handler,
            identifier       = identifier,
            version          = version,
            title            = title,
            abstract         = abstract,
            inputs           = inputs,
            outputs          = outputs,
            store_supported  = store_supported,
            status_supported = status_supported)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())
        if not 'start' in request.inputs or not 'end' in request.inputs:
          time = None
        else:
          time = (_datetimeExtractor(request.inputs['start'][0].data),
                  _datetimeExtractor(request.inputs['end'][0].data))
        crs = None
        if hasattr(request_json, 'crs'):
            crs = request_json['crs']['properties']['name']

        features = request_json['features']
        if len(features) < 1:
            # Can't drill if there is no geometry
            raise pywps.InvalidParameterException()

        start_time = timer()
        data = dict()
        for feature in features:
            geometry = feature['geometry']

            if crs is None and hasattr(feature, 'crs'):
                crs = feature['crs']['properties']['name']
            elif crs is None and not hasattr(feature, 'crs'):
                # Terria doesn't provide the CRS for the polygon
                # Must assume the crs according to spec
                # http://geojson.org/geojson-spec.html#coordinate-reference-system-objects
                crs = 'urn:ogc:def:crs:OGC:1.3:CRS84'
            # Can do custom loading of data here
            with ProcessPoolExecutor(max_workers=4) as executor:
              for p in self.products:
                product = p['name']
                query = p.get('additional_query', {})
                future = executor.submit(
                  self.data_loader,
                  geometry,
                  product,
                  crs,
                  time,
                  query)
                data[product] = future
              for k, v in data.items():
                d = v.result()
                data[k] = d

        masked = dict()
        if self.geometry_type == 'point' or not self.do_mask:
          masked = data
        elif len(data) != 0:
            masked = dict()
            for k, d in data.items():
              if len(d.variables) > 0:
                mask = geometry_mask([f['geometry'] for f in features], crs, d.geobox, invert=True)
                for band in d.data_vars:
                  try:
                      d[band] = d[band].where(mask, other=d[band].attrs['nodata'])
                  except AttributeError:
                      d[band] = d[band].where(mask)
              masked[k] = d

        print('time elasped in load: {}'.format(timer() - start_time))

        outputs = self.custom_handler(masked, process_id=self.uuid)

        print('time elasped in process: {}'.format(timer() - start_time))

        for ident, output_value in outputs.items():
          if "data" in output_value:
            response.outputs[ident].data = output_value['data']
          if "output_format" in output_value:
            response.outputs[ident].output_format = output_value['output_format']
          if "url" in output_value:
            response.outputs[ident].url = output_value['url']
        return response

