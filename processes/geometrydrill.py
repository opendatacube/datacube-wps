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
        data = dc.load(product=product, group_by='solar_day', **query, **extra_query)
        return data

# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(data, **kwargs):
    data = data.mean(dim=('x','y'))
    return data

class GeometryDrill(Process):

    def __init__(self, handler, identifier, title, abstract='', profile=[], metadata=[],
                 version='None', store_supported=False, status_supported=False,
                 products=[], output_name=None, geometry_type="polygon", table_style=None):

        assert len(products) > 0
        assert geometry_type in [ "polygon", "point" ]
        assert table_style is not None
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#' + geometry_type)
                                                 ]),
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

        self.products = products
        self.custom_handler = handler
        self.table_style = table_style
        self.output_name = output_name if output_name is not None else "default"

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
                # Must assume the crs according to spec
                # http://geojson.org/geojson-spec.html#coordinate-reference-system-objects
                crs = 'urn:ogc:def:crs:OGC:1.3:CRS84'
            # Can do custom loading of data here
            for p in self.products:
              product = p['name']
              query = p.get('additional_query', {})
              d = _getData(geometry,
                           product,
                           crs,
                           time,
                           query)
              if (len(d) > 0):
                data.append(d)

        if len(data) == 0:
            csv = ""
        else:
            masked = []
            for d in data:
              print(data)
              mask = geometry_mask([f['geometry'] for f in features], crs, d.geobox, invert=True)
              d_masked = d.where(mask)
              masked.append(d_masked)
            csv = self.custom_handler(masked)

        output_dict = {
            "data": csv,
            "isEnabled": True,
            "type": "csv",
            "name": self.output_name,
            "tableStyle": self.table_style
        }

        output_json = json.dumps(output_dict, cls=DatetimeEncoder)

        output_str = output_json

        response.outputs['timeseries'].output_format = _json_format
        response.outputs['timeseries'].data = output_str

        return response

