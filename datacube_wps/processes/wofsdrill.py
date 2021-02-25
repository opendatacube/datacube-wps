import numpy as np
import datacube
import altair

from pywps import LiteralOutput, ComplexInput, ComplexOutput

from . import PixelDrill, FORMATS, log_call, chart_dimensions


class WOfSDrill(PixelDrill):
    def input_formats(self):
        return [ComplexInput('geometry', 'Location (Lon, Lat)', supported_formats=[FORMATS['point']])]

    def output_formats(self):
        return [LiteralOutput("image", "WOfS Pixel Drill Preview"),
                LiteralOutput("url", "WOfS Pixel Drill Graph"),
                ComplexOutput('timeseries', 'Timeseries Drill', supported_formats=[FORMATS['output_json']])]

    @log_call
    def process_data(self, data, parameters):
        # TODO raise ProcessError('query returned no data') when appropriate

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

        # TODO: investigate why PixelDrill is changing datatype
        water = data.data_vars['water']
        data['observation'] = water.astype('int16')
        data = data.drop_vars(['water'])

        def get_flags(val):
            flag_dict = datacube.utils.masking.mask_to_dict(water.attrs['flags_definition'], val)
            flags = list(filter(flag_dict.get, flag_dict))
            # apply rules in sequence
            ret_val = 'not observable'
            for rule in rules:
                if rule['op']([r in flags for r in rule['flags']]):
                    ret_val = rule['value']
                    break
            return ret_val
        gf = np.vectorize(get_flags)

        data['observation'].values = gf(data['observation'].values)

        df = data.to_dataframe()
        df.reset_index(inplace=True)
        return df

    @log_call
    def render_chart(self, df):
        width, height = chart_dimensions(self.style)

        pt_lat = df['latitude'].iat[0]
        pt_lon = df['longitude'].iat[0]

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
        return chart

    @log_call
    def render_outputs(self, df, chart):
        return super().render_outputs(df, chart,
                                      is_enabled=False, name="WOfS", header=['Observation'])
