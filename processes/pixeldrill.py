import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS

import json

import datacube
from datacube.utils import geometry

# From https://stackoverflow.com/a/16353080
class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)


class PixelDrill(Process):
    def __init__(self):
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/gml+xml')
                                                 ]),
                  LiteralInput('product',
                               'Datacube Product to Drill',
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

    g = geometry.Geometry(shape, crs=datacube.utils.geometry.CRS(crs))
    query = {
        'geopolygon': g
    }
    data = dc.load(product=product, **query)
    return data

