import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS
from osgeo import ogr
import json

import datacube
from datacube.utils import geometry

import rasterio.features

import csv
import io

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

def geometry_mask(geom, geobox, all_touched=False, invert=False):
    return rasterio.features.geometry_mask(geom.to_crs(geobox.crs),
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)

def _getData(shape, product, crs, time=None):
    dc = datacube.Datacube()
    dc_crs = datacube.utils.geometry.CRS(crs)
    g = geometry.Geometry(shape, crs=dc_crs)
    query = {
        'geopolygon': g
    }
    if time is not None:
        first, second = time;
        time = (first.strftime("%Y-%m-%d"), second.strftime("%Y-%m-%d"))
        query['time'] = time

    data = dc.load(product=product, **query)

    if (g.type == 'Polygon'):
        mask = geometry_mask(g, data.geobox, invert=True)
        data = data.where(mask)

    return data

# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(data, **kwargs):
    return data

class PolygonDrill(Process):
    def __init__(self):
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#point')
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

        features = request_json['features']
        if len(features) < 1:
            # Can't drill if there is no geometry
            raise pywps.InvalidParameterException()

        data = []
        for feature in features:
            geometry = feature['geometry']
            # test for CRS in geoJSON
            # Terria may not set this, so we will assume EPSG:4326
            # if nothing present even though geoJSON spec disallows assumption
            crs = 'EPSG:4326' 

            if hasattr(request_json, 'crs'):
                crs = request_json['crs']['properties']['name']

            d = _getData(geometry,
                         product,
                         crs,
                         (request.inputs['start'][0].data,
                          request.inputs['end'][0].data))
            data.append(d)

        if len(data) == 0:
            csv = ""
        else:
            # Perform operations on data here, return a CSV string
            csv = _processData(data).to_pandas().to_csv();

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

