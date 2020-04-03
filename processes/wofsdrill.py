import pywps
import json
import numpy as np
import io
from xarray import DataArray, Dataset
from functools import partial

import datacube
import altair

from processes.geometrydrill import GeometryDrill, _uploadToS3, DatetimeEncoder, _json_format
from pywps import LiteralOutput, ComplexInput, Format, ComplexOutput
import pywps.configuration as config

from datacube.api.query import query_group_by
from datacube.drivers import new_datasource
from datacube.storage import BandInfo
from datacube.utils import geometry
from dea.io.pdrill import PixelDrill

from processes.utils import log_call
from timeit import default_timer


@log_call
def _getData(shape, product, crs, time=None, extra_query={}):
    with datacube.Datacube() as dc:
        dc_crs = datacube.utils.geometry.CRS(crs)
        query = {'geopolygon': geometry.Geometry(shape, crs=dc_crs)}
        if time is not None:
            first, second = time
            time = (first.strftime("%Y-%m-%d"), second.strftime("%Y-%m-%d"))
            query['time'] = time
        final_query = {**query, **extra_query}
        print("query to datacube:", final_query)

        dask_data = dc.load(product=product, group_by='time', dask_chunks={'time': 1}, **final_query)
        start_time = default_timer()
        data = dask_data.compute(scheduler='threads', num_workers=16)
        print('dask took', default_timer() - start_time, 'seconds')
        dc_product = dc.index.products.get_by_name(product)

        lonlat = geometry.Geometry(shape, crs='EPSG:4326').coords[0]
        measurement = dc_product.measurements['water'].copy()

        array = DataArray(
            data['water'].data,
            dims=('time', 'longitude', 'latitude'),
            coords={'time': data.time, 'longitude': np.full(1, lonlat[0]), 'latitude': np.full(1, lonlat[1])},
            attrs={'flags_definition': measurement['flags_definition']})

        return array


@log_call
def _processData(datas, **kwargs):
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

    water = datas['wofs_albers']

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
    print(data)
    data['observation'].values = gf(data['observation'].values)

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

    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    html_url = _uploadToS3(str(kwargs['process_id']) + '/chart.html', html_bytes, 'text/html')

    img_io = io.StringIO()
    chart.save(img_io, format='svg')
    img_bytes = io.BytesIO(img_io.getvalue().encode())
    img_url = _uploadToS3(str(kwargs['process_id']) + '/chart.svg', img_bytes, 'image/svg+xml')

    csv = data.squeeze(dim=('latitude', 'longitude'), drop=True).to_dataframe().to_csv(header=['Observation'],
                                                                                       date_format="%Y-%m-%d")

    # not sure why style was never applied
    output_dict = {
        "data": csv,
        "isEnabled": False,
        "type": "csv",
        # "tableStyle": style,
        "name": "WOfS"
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    outputs = {
        'image': {'data': img_url},
        'url': {'data': html_url},
        'timeseries': {'data': output_json}
    }

    return outputs


_point_format = Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#point')


class WOfSDrill(GeometryDrill):
    def __init__(self, about, style):
        super().__init__(handler=partial(_processData, style=style),
                         products=[{"name": "wofs_albers"}],
                         custom_inputs=[
                             ComplexInput('geometry',
                                          'Location (Lon,Lat)',
                                          supported_formats=[_point_format])
                         ],
                         custom_outputs=[
                             LiteralOutput("image", "WOfS Pixel Drill Preview"),
                             LiteralOutput("url", "WOfS Pixel Drill Graph"),
                             ComplexOutput('timeseries',
                                           'Timeseries Drill',
                                           supported_formats=[_json_format])
                         ],
                         custom_data_loader=_getData,
                         mask=False,
                         **about)
