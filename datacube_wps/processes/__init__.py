from functools import wraps
from timeit import default_timer
import json
import io
import os

from pywps import Process, ComplexInput, ComplexOutput, Format
from pywps.app.exceptions import ProcessError
import pywps.configuration as config

import datacube
from datacube.utils.geometry import Geometry, CRS
from datacube.api.core import output_geobox, query_group_by

from datacube.drivers import new_datasource
from datacube.storage import BandInfo
from datacube.utils.rio import configure_s3_access

import rasterio.features

import xarray
import numpy as np
import pandas
import altair
from dask.distributed import Client

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


def upload_chart_html_to_S3(chart : altair.Chart, process_id : str):
    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    return _uploadToS3(process_id + '/chart.html', html_bytes, 'text/html')


def upload_chart_svg_to_S3(chart : altair.Chart, process_id : str):
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


def chart_dimensions(style):
    if 'chart' in style and 'width' in style['chart']:
        width = style['chart']['width']
    else:
        width = 1000
    if 'height' in style and 'height' in style['chart']:
        height = style['chart']['height']
    else:
        height = 300

    return (width, height)


def _guard_rail(input, box):
    measurement_dicts = input.output_measurements(box.product_definitions)

    byte_count = 1
    for x in box.shape:
        byte_count *= x
    byte_count *= sum(np.dtype(m.dtype).itemsize for m in measurement_dicts.values())

    print('byte count for query: ', byte_count)
    if byte_count > MAX_BYTES_IN_GB * GB:
        raise ProcessError(("requested area requires {}GB data to load - "
                            "maximum is {}GB").format(int(byte_count / GB), MAX_BYTES_IN_GB))

    try:
        grouped = box.box
    except AttributeError:
        # datacube 1.7 compatibility
        grouped = box.pile

    print('grouped shape', grouped.shape)
    assert len(grouped.shape) == 1

    if grouped.shape[0] == 0:
        raise ProcessError('no data returned for query')

    bytes_per_obs = byte_count / grouped.shape[0]
    if bytes_per_obs > MAX_BYTES_PER_OBS_IN_GB * GB:
        raise ProcessError(("requested time slices each requires {}GB data to load - "
                            "maximum is {}GB").format(int(bytes_per_obs / GB), MAX_BYTES_PER_OBS_IN_GB))


def _datetimeExtractor(data):
    return parse(json.loads(data)["properties"]["timestamp"]["date-time"])

def _parse_geom(request_json):
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

def _get_feature(request):
    stream = request.inputs['geometry'][0].stream
    request_json = json.loads(stream.readline())

    return _parse_geom(request_json)


def _get_time(request):
    if 'start' not in request.inputs or 'end' not in request.inputs:
        return None

    def _datetimeExtractor(data):
        return parse(json.loads(data)["properties"]["timestamp"]["date-time"])

    return (_datetimeExtractor(request.inputs['start'][0].data),
            _datetimeExtractor(request.inputs['end'][0].data))


def _get_parameters(request):
    if 'parameters' not in request.inputs:
        return {}

    stream = request.inputs['parameters'][0].stream
    params = json.loads(stream.readline())

    return params


def _render_outputs(uuid, style, df: pandas.DataFrame, chart: altair.Chart,
                    is_enabled=True, name="Timeseries", header=True):
    html_url = upload_chart_html_to_S3(chart, str(uuid))
    img_url = upload_chart_svg_to_S3(chart, str(uuid))

    try:
        csv_df = df.drop(columns=['latitude', 'longitude'])
    except KeyError:
        csv_df = df

    csv_df.set_index('time', inplace=True)
    csv = csv_df.to_csv(header=header, date_format="%Y-%m-%d")

    if 'table' in style:
        table_style = {'tableStyle': style['table']}
    else:
        table_style = {}

    output_dict = {
        "data": csv,
        "isEnabled": is_enabled,
        "type": "csv",
        "name": name,
        **table_style
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    outputs = {
        'image': {'data': img_url},
        'url': {'data': html_url},
        'timeseries': {'data': output_json}
    }

    return outputs


def _populate_response(response, outputs):
    for ident, output_value in outputs.items():
        if ident in response.outputs:
            if "data" in output_value:
                response.outputs[ident].data = output_value['data']
            if "output_format" in output_value:
                response.outputs[ident].output_format = output_value['output_format']
            if "url" in output_value:
                response.outputs[ident].url = output_value['url']


def num_workers():
    return int(os.getenv('DATACUBE_WPS_NUM_WORKERS', '4'))


class PixelDrill(Process):
    def __init__(self, about, input, style):
        if 'geometry_type' in about:
            assert about['geometry_type'] == 'point'

        super().__init__(handler=self.request_handler,
                         inputs=self.input_formats(),
                         outputs=self.output_formats(),
                         **{key: value for key, value in about.items() if key not in ['geometry_type']})

        self.about = about
        self.input = input
        self.style = style

    def input_formats(self):
        return [ComplexInput('geometry', 'Location (Lon, Lat)', supported_formats=[FORMATS['point']]),
                ComplexInput('start', 'Start Date', supported_formats=[FORMATS['datetime']]),
                ComplexInput('end', 'End date', supported_formats=[FORMATS['datetime']])]

    def output_formats(self):
        return [ComplexOutput('timeseries', 'Timeseries Drill',
                              supported_formats=[FORMATS['output_json']])]

    def request_handler(self, request, response):
        time = _get_time(request)
        feature = _get_feature(request)
        parameters = _get_parameters(request)

        result = self.query_handler(time, feature, parameters=parameters)

        outputs = self.render_outputs(result['data'], result['chart'])
        _populate_response(response, outputs)
        return response

    @log_call
    def query_handler(self, time, feature, parameters=None):
        if parameters is None:
            parameters = {}

        with Client(n_workers=1, processes=False, threads_per_worker=num_workers()) as client:
            configure_s3_access(aws_unsigned=True,
                                region_name=os.getenv('AWS_DEFAULT_REGION', 'auto'),
                                client=client)

            with datacube.Datacube() as dc:
                data = self.input_data(dc, time, feature)

        df = self.process_data(data, parameters)
        chart = self.render_chart(df)

        return {'data': df, 'chart': chart}

    @log_call
    def input_data(self, dc, time, feature):
        if time is None:
            bag = self.input.query(dc, geopolygon=feature)
        else:
            bag = self.input.query(dc, time=time, geopolygon=feature)

        lonlat = feature.coords[0]

        measurements = self.input.output_measurements(bag.product_definitions)
        box = self.input.group(bag)

        data = self.input.fetch(box, dask_chunks={'time': 1})
        data = data.compute()

        coords = {'longitude': np.array([lonlat[0]]),
                  'latitude': np.array([lonlat[1]]),
                  'time': data.time.data}

        result = xarray.Dataset()
        for measurement_name, measurement in measurements.items():
            result[measurement_name] = xarray.DataArray(data[measurement_name],
                                                        dims=('time', 'longitude', 'latitude'),
                                                        coords=coords,
                                                        attrs={key: value
                                                               for key, value in measurement.items()
                                                               if key in ['flags_definition']})
        return result

    def process_data(self, data: xarray.Dataset, parameters: dict) -> pandas.DataFrame:
        raise NotImplementedError

    def render_chart(self, df: pandas.DataFrame) -> altair.Chart:
        raise NotImplementedError

    def render_outputs(self, df: pandas.DataFrame, chart: altair.Chart,
                       is_enabled=True, name="Timeseries", header=True):
        return _render_outputs(self.uuid, self.style, df, chart,
                               is_enabled=is_enabled, name=name, header=header)


class PolygonDrill(Process):
    def __init__(self, about, input, style):
        if 'geometry_type' in about:
            assert about['geometry_type'] == 'polygon'

        super().__init__(handler=self.request_handler,
                         inputs=self.input_formats(),
                         outputs=self.output_formats(),
                         **{key: value for key, value in about.items() if key not in ['geometry_type']})

        self.about = about
        self.input = input
        self.style = style

    def input_formats(self):
        return [ComplexInput('geometry', 'Geometry', supported_formats=[FORMATS['polygon']]),
                ComplexInput('start', 'Start Date', supported_formats=[FORMATS['datetime']]),
                ComplexInput('end', 'End date', supported_formats=[FORMATS['datetime']])]

    def output_formats(self):
        return [ComplexOutput('timeseries', 'Timeseries Drill',
                              supported_formats=[FORMATS['output_json']], as_reference=False)]

    def request_handler(self, request, response):
        time = _get_time(request)
        feature = _get_feature(request)
        parameters = _get_parameters(request)

        result = self.query_handler(time, feature, parameters=parameters)

        outputs = self.render_outputs(result['data'], result['chart'])
        _populate_response(response, outputs)
        return response

    @log_call
    def query_handler(self, time, feature, parameters=None):
        if parameters is None:
            parameters = {}

        with Client(n_workers=num_workers(), processes=True, threads_per_worker=1) as client:
            configure_s3_access(aws_unsigned=True,
                                region_name=os.getenv('AWS_DEFAULT_REGION', 'auto'),
                                client=client)

            with datacube.Datacube() as dc:
                data = self.input_data(dc, time, feature)

        df = self.process_data(data, parameters)
        chart = self.render_chart(df)

        return {'data': df, 'chart': chart}

    def input_data(self, dc, time, feature):
        if time is None:
            bag = self.input.query(dc, geopolygon=feature)
        else:
            bag = self.input.query(dc, time=time, geopolygon=feature)

        box = self.input.group(bag)
        _guard_rail(self.input, box)
        mask = geometry_mask(feature, box.geobox, invert=True)

        # TODO customize the number of processes
        data = self.input.fetch(box, dask_chunks={'time': 1})

        # mask out data outside requested polygon
        for band_name, band_array in data.data_vars.items():
            if 'nodata' in band_array.attrs:
                data[band_name] = band_array.where(mask, other=band_array.attrs['nodata'])
            else:
                data[band_name] = band_array.where(mask)

        return data

    def process_data(self, data: xarray.Dataset, parameters: dict) -> pandas.DataFrame:
        raise NotImplementedError

    def render_chart(self, df: pandas.DataFrame) -> altair.Chart:
        raise NotImplementedError

    def render_outputs(self, df: pandas.DataFrame, chart: altair.Chart,
                       is_enabled=True, name="Timeseries", header=True):
        return _render_outputs(self.uuid, self.style, df, chart,
                               is_enabled=is_enabled, name=name, header=header)
