import pywps
from pywps import Process, ComplexInput, ComplexOutput, Format, FORMATS

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
                                                 ])]
        outputs = [ComplexOutput('timeseries',
                                 'Timeseries Drill',
                                 supported_formats=[
                                                    Format('application/json')
                                                ])]

        super(PixelDrill, self).__init__(
            self._handler,
            identifier       = 'pixeldrill',
            version          = '0.1',
            title            = 'WOfS Pixel Drill',
            abstract         = 'Does WOfS Pixel Drill',
            inputs           = inputs,
            outputs          = outputs,
            store_supported  = True,
            status_supported = True)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())

        features_json = request_json['features']
        if len(features_json) > 1:
            raise pywps.InvalidParameterException()

        geometry_json = features_json[0]['geometry']

        d = _getData(geometry_json)

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


def _getData(shape):
    product_name = 'LS8_OLI_WATER'
    crs          = 'EPSG:4326'

    dc = datacube.Datacube()

    g = geometry.Geometry(shape, crs=datacube.utils.geometry.CRS('EPSG:4326'))
    query = {
        'geopolygon': g
    }
    data = dc.load(product=product_name, **query)
    return data


