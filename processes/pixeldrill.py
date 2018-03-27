import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS

import json

import datacube
from datacube.utils import geometry

import rasterio.features

# From https://stackoverflow.com/a/16353080
class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)

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


class PixelDrill(Process):
    def __init__(self):
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/gml+xml')
                                                 ]),
                  LiteralInput('product',
                               'Datacube product to drill',
                               data_type='string')]
        outputs = [ComplexOutput('timeseries',
                                 'Timeseries Drill',
                                 supported_formats=[
                                                    Format('application/json')
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

            output = list(zip(ar.values[0], ar.coords['time'].values))

        output_json = json.dumps(output, cls=DatetimeEncoder)

        response.outputs['timeseries'].output_format = Format('application/json', '.json', None)
        response.outputs['timeseries'].data = output_json
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

