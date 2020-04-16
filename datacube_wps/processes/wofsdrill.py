import json

import numpy as np
import datacube
import altair
from xarray import Dataset

from pywps import LiteralOutput, ComplexInput, ComplexOutput
import pywps.configuration as config

from . import PixelDrill, DatetimeEncoder, FORMATS, log_call
from . import upload_chart_svg_to_S3, upload_chart_html_to_S3



@log_call
def _processData(data, **kwargs):
    rules = [
        {
            'op': any,
            'flags': ['terrain_or_low_angle', 'cloud_shadow', 'cloud', 'high_slope', 'noncontiguous'],
            'value': 'not observable'
        },
        {
            'op': all,
            'flags': ['dry', 'sea'],
            'value': 'not observable'
        },
        {
            'op': any,
            'flags': ['dry'],
            'value': 'dry'
        },
        {
            'op': any,
            'flags': ['wet', 'sea'],
            'value': 'wet'
        }
    ]

    water = data.data_vars['water']

    def get_flags(val):
        flag_dict = datacube.storage.masking.mask_to_dict(water.attrs['flags_definition'], val)
        flags = list(filter(flag_dict.get, flag_dict))
        # apply rules in sequence
        ret_val = 'not observable'
        for rule in rules:
            if rule['op']([r in flags for r in rule['flags']]):
                ret_val = rule['value']
                break
        return ret_val
    gf = np.vectorize(get_flags)

    data = Dataset()
    data['observation'] = water
    data['observation'].values = gf(data['observation'].values)
    print(data)

    pt_lat = data['observation'].coords['latitude'][0].values
    pt_lon = data['observation'].coords['longitude'][0].values

    df = data.to_dataframe()
    df.reset_index(inplace=True)

    width = config.get_config_value('wofs', 'width')
    height = config.get_config_value('wofs', 'height')
    width = int(width) if width != '' else 1000
    height = int(height) if height != '' else 300

    yscale = altair.Scale(domain=['wet', 'dry', 'not observable'])
    ascale = altair.Scale(domain=['wet', 'dry', 'not observable'],
                          range=['blue', 'red', 'grey'])
    chart = altair.Chart(df,
                         width=width,
                         height=height,
                         autosize='fit',
                         background='white',
                         title=f"Water Observations for {pt_lat:.6f},{pt_lon:.6f}")
    chart = chart.mark_tick(thickness=3)
    chart = chart.encode(x=altair.X('time:T'),
                         y=altair.Y('observation:nominal', scale=yscale),
                         color=altair.Color('observation:nominal', scale=ascale),
                         tooltip=['observation:nominal',
                                  altair.Tooltip(field='time',
                                                 format='%d %B, %Y',
                                                 title='Date',
                                                 type='temporal')])

    assert 'process_id' in kwargs

    html_url = upload_chart_html_to_S3(chart, str(kwargs['process_id']))
    img_url = upload_chart_svg_to_S3(chart, str(kwargs['process_id']))

    csv = data.squeeze(dim=('latitude', 'longitude'), drop=True).to_dataframe().to_csv(header=['Observation'],
                                                                                       date_format="%Y-%m-%d")

    # not sure why style was never applied
    output_dict = {
        "data": csv,
        "isEnabled": False,
        "type": "csv",
        # "tableStyle": style['table'],
        "name": "WOfS"
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    outputs = {
        'image': {'data': img_url},
        'url': {'data': html_url},
        'timeseries': {'data': output_json}
    }

    return outputs


class WOfSDrill(PixelDrill):
    def input_formats(self):
        return [ComplexInput('geometry', 'Location (Lon, Lat)', supported_formats=[FORMATS['point']])]

    def output_formats(self):
        return [LiteralOutput("image", "WOfS Pixel Drill Preview"),
                LiteralOutput("url", "WOfS Pixel Drill Graph"),
                ComplexOutput('timeseries', 'Timeseries Drill', supported_formats=[FORMATS['output_json']])]

    def process_data(self, data):
        return _processData(data, process_id=self.uuid)
