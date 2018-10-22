import pywps
import json
import numpy as np
import io

import datacube
import altair

from processes.geometrydrill import GeometryDrill, _uploadToS3
from pywps import LiteralOutput

from datacube.storage.storage import measurement_paths
from dea.io.pdrill import PixelDrill
from dea.aws.rioworkerpool import RioWorkerPool

nthreads = 32

# Data is a list of Datasets (returned from dc.load and masked if polygons)
# Must handle empty data case too
def _processData(datas, **kwargs):
    flag_lut = {'dry': 'dry', 'sea': 'wet', 'wet': 'wet', 'cloud': 'not observable', 'high_slope': 'not observable', 'cloud_shadow': 'not observable', 'noncontiguous': 'not observable', 'terrain_or_low_angle': 'not observable', 'nodata': 'not observable'}
    def get_flags(val):
        flag_dict = datacube.storage.masking.mask_to_dict(data['water'].flags_definition, val)
        flags = filter(flag_dict.get, flag_dict)
        flags_converted = [flag_lut[f] for f in flags]
        return flags_converted[0] if 'not observable' not in flags_converted else 'not observable'
    gf = np.vectorize(get_flags)

    data = datas[0]
    data['flags'] = data['water'].copy(deep=True)
    data['flags'].values = gf(data['flags'].values)

    df = data.to_dataframe()
    df.reset_index(inplace=True)

    yscale = altair.Scale(domain=['wet', 'dry', 'not observable'])
    ascale = altair.Scale(
        domain=['wet','dry','not observable'],
        range=['blue', 'red', 'grey'])
    chart = altair.Chart(df).mark_tick(thickness=3).encode(
        x=altair.X('time:T'),
        y=altair.Y('flags:nominal', scale=yscale),
        color=altair.Color('flags:nominal', scale=ascale), tooltip='flags:nominal')

    assert 'process_id' in kwargs

    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    html_url = _uploadToS3(str(kwargs['process_id']) + '/chart.html', html_bytes, 'text/html')

    img_io = io.StringIO()
    chart.save(img_io, format='svg')
    img_bytes = io.BytesIO(img_io.getvalue().encode())
    img_url = _uploadToS3(str(kwargs['process_id']) + '/chart.svg', img_bytes, 'image/svg+xml')

    outputs = {
        'image': {
            'data': img_url
        },
        'url': {
            'data': html_url
        }
    }

    return outputs


tableStyle = {
    "columns": {
        "Wet": {
            "units": "#",
            "chartLineColor": "#4F81BD",
            "active": True
        },
        "Dry": {
            "units": "#",
            "chartLineColor": "#D99694",
            "active": True
        },
        "Not Observable": {
            "units": "#",
            "chartLineColor": "#707070",
            "active": True
        }
    }
}

class WofsDrill(GeometryDrill):
    def __init__(self):
        super(WofsDrill, self).__init__(
            handler          = _processData,
            identifier       = 'WOfSDrill',
            version          = '0.2',
            title            = 'WOfS',
            abstract         = 'Performs WOfS Pixel Drill',
            store_supported  = True,
            status_supported = True,
            geometry_type    = "point",
            products         = [{
                "name": "wofs_albers",
                "additional_query": {
                    "output_crs": 'EPSG:3577',
                    "resolution": (-25, 25)
                }
            }],
            output_name      = "WOfS",
            custom_outputs=[
                LiteralOutput("image", "Pixel Drill Graph"),
                LiteralOutput("url", "Pixel Drill Chart")
            ])
        

