import pywps
from pywps import Process, ComplexInput, ComplexOutput, Format, FORMATS

import json

from shapely.geometry import shape

import datacube

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
            store_supported  = False,
            status_supported = False)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())

        features_json = request_json['features']
        if len(features_json) > 1:
            raise pywps.InvalidParameterException()

        geometry_json = features_json[0]['geometry']
        s = shape(geometry_json)

        d = _getData(s)

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
    dc = datacube.Datacube()
    if (shape.type == 'Point'):
        data = dc.load(product='LS8_OLI_WATER', latitude=(shape.y, shape.y), longitude=(shape.x, shape.x))

    return data


