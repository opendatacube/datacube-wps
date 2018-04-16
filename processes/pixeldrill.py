import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS

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

def result_to_csv(results):
    with io.StringIO('') as csv_string:
        writer = csv.writer(csv_string, lineterminator='\n')

        writer.writerow(['date', 'water'])
        writer.writerows(results)

        return csv_string.getvalue()


def geometry_mask(geoms, geobox, all_touched=False, invert=False):
    """
    Create a mask from shapes.

    By default, mask is intended for use as a
    numpy mask, where pixels that overlap shapes are False.
    :param list[Geometry] geoms: geometries to be rasterized
    :param datacube.utils.GeoBox geobox:
    :param bool all_touched: If True, all pixels touched by geometries will be burned in. If
                             false, only pixels whose center is within the polygon or that
                             are selected by Bresenham's line algorithm will be burned in.
    :param bool invert: If True, mask will be True for pixels that overlap shapes.
    """
    return rasterio.features.geometry_mask([geom.to_crs(geobox.crs) for geom in geoms],
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)

_csv_format = Format('application/vnd.terriajs.catalog-member+json',
                     schema='https://tools.ietf.org/html/rfc7159')

class PixelDrill(Process):
    def __init__(self):
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#point')
                                                 ]),
                  LiteralInput('product',
                               'Datacube product to drill',
                               data_type='string')]
        outputs = [ComplexOutput('timeseries',
                                 'Timeseries Drill',
                                 supported_formats=[
                                                        _csv_format
                                                   ])]

        super(PixelDrill, self).__init__(
            self._handler,
            identifier       = 'pixeldrill',
            version          = '0.1',
            title            = 'Pixel Drill',
            abstract         = 'Performs Pixel Drill',
            inputs           = inputs,
            outputs          = outputs,
            store_supported  = True,
            status_supported = True)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())
        product      = request.inputs['product'][0].data

        features_json = request_json['features']
        if len(features_json) > 1:
            raise pywps.InvalidParameterException()

        geometry_json = features_json[0]['geometry']

        # test for CRS in geoJSON
        # Terria may not set this, so we will assume EPSG:4326
        # if nothing present even though geoJSON spec disallows assumption
        crs = 'EPSG:4326'

        if hasattr(request_json, 'crs'):
            crs = request_json['crs']['properties']['name']

        d = _getData(geometry_json, product, crs)

        if len(d.variables) == 0:
            output = []
        else:
            # massage dataset
            squeezed = d.squeeze()
            squeezed = squeezed.drop('x')
            squeezed = squeezed.drop('y')

            ar = squeezed.to_array()

            output = list(zip(ar.coords['time'].values, ar.values[0]))

        csv = result_to_csv(output)

        output_dict = {
            "data": csv,
            "isEnabled": True,
            "type": "csv",
            "name": "WOfS",
        }

        output_json = json.dumps(output_dict, cls=DatetimeEncoder)

        output_str = output_json

        response.outputs['timeseries'].output_format = _csv_format
        response.outputs['timeseries'].data = output_str

        return response


def _getData(shape, product, crs):
    dc = datacube.Datacube()
    dc_crs = datacube.utils.geometry.CRS(crs)
    g = geometry.Geometry(shape, crs=dc_crs)
    query = {
        'geopolygon': g
    }
    data = dc.load(product=product, **query)

    # # mask if polygon
    # mask = geometry_mask([g], data.geobox, invert=True)
    # masked = data.where(mask)

    return data

