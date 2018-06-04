import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS
from osgeo import ogr
import json

import datacube
from datacube.utils import geometry

import rasterio.features

import csv
import io
import boto3
import xarray

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
                     schema='https://tools.ietf.org/html/rfc7159')

def geometry_mask(geoms, src_crs, geobox, all_touched=False, invert=False):
    gs = [geometry.Geometry(geom, crs=datacube.utils.geometry.CRS(src_crs)).to_crs(geobox.crs) for geom in geoms]
    return rasterio.features.geometry_mask(gs,
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)

def _getData(shape, product, crs, time=None):
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
        data = dc.load(product=product, group_by='solar_day', **query)
        return data

# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(data, **kwargs):
    data = data.mean(dim=('x','y'))
    return data
    

class PolygonDrill(Process):
    def __init__(self):
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#polygon')
                                                 ]),
                  LiteralInput('product',
                               'Datacube product to drill',
                               data_type='string'),
                  LiteralInput('start',
                               'Start Date',
                               data_type='date'),
                  LiteralInput('end',
                               'End date',
                               data_type='date')]
        outputs = [ComplexOutput('timeseries',
                                 'Timeseries Drill',
                                 supported_formats=[
                                                        _json_format
                                                   ])]

        super(PolygonDrill, self).__init__(
            self._handler,
            identifier       = 'polygondrill',
            version          = '0.1',
            title            = 'Polygon Drill',
            abstract         = 'Performs Polygon Drill',
            inputs           = inputs,
            outputs          = outputs,
            store_supported  = True,
            status_supported = True)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())
        product      = request.inputs['product'][0].data

        time = (request.inputs['start'][0].data,
                request.inputs['end'][0].data)
        crs = None

        if hasattr(request_json, 'crs'):
            crs = request_json['crs']['properties']['name']

        features = request_json['features']
        if len(features) < 1:
            # Can't drill if there is no geometry
            raise pywps.InvalidParameterException()

        data = []
        for feature in features:
            geometry = feature['geometry']

            if crs is None and hasattr(feature, 'crs'):
                crs = feature['crs']['properties']['name']
            elif crs is None and not hasattr(feature, 'crs'):
                # Terria doesn't provide the CRS for the polygon
                # Must assume the crs even though geoJSON doesn't actually allow
                # assumption
                crs = 'EPSG:4326'
            # Can do custom loading of data here
            d = _getData(geometry,
                         product,
                         crs,
                         time)

            data.append(d)

        if len(data) == 0:
            csv = ""
        else:
            crs_attr = data[0].attrs['crs']
            data = xarray.merge(data)
            data.attrs['crs'] = crs_attr
            mask = geometry_mask([f['geometry'] for f in features], crs, data.geobox, invert=True)
            data = data.where(mask)
            csv = _processData(data).to_dataframe().to_csv(date_format="%Y-%m-%d");


        output_dict = {
            "data": csv,
            "isEnabled": True,
            "type": "csv",
            "name": "PolygonDrill",
        }

        output_json = json.dumps(output_dict, cls=DatetimeEncoder)

        output_str = output_json

        response.outputs['timeseries'].output_format = _json_format
        response.outputs['timeseries'].data = output_str

        return response

