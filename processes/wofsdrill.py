import pywps
import json
import numpy as np
import io
from xarray import DataArray, Dataset

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
        final_query = {**query, **extra_query}
        print("finding data!", final_query)
        ds = dc.find_datasets(product=product, group_by="solar_day", **final_query)
        dss = dc.group_datasets(ds, query_group_by(group_by="solar_day"))

        product = dc.index.products.get_by_name(product)

        lonlat = geometry.Geometry(shape, crs='EPSG:4326').coords[0]
        measurement = product.measurements['water'].copy()
        driller = PixelDrill(16)
        datasources = []
        for ds in dss.values:
            for d in ds:
                datasources.append(new_datasource(BandInfo(d, measurement['name'])))
        datasources = sorted(datasources, key=lambda x: x._band_info.center_time)
        times = [x._band_info.center_time for x in datasources]
        files = [s.filename for s in datasources]

        results = [[driller.read(urls=files, lonlat=lonlat)]]
        array = DataArray(
            results,
            dims=('longitude', 'latitude', 'time'),
            coords={'longitude': np.full(1, lonlat[0]), 'latitude': np.full(1, lonlat[1]), 'time': times})

        return array


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

    with datacube.Datacube() as dc:
        product = dc.index.products.get_by_name('wofs_albers')

    def get_flags(val):
        flag_dict = datacube.storage.masking.mask_to_dict(product.measurements['water'].flags_definition, val)
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
    data['observation'] = datas['wofs_albers']
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
    ascale = altair.Scale(
        domain=['wet','dry','not observable'],
        range=['blue', 'red', 'grey'])
    chart = altair.Chart(
                    df,
                    width=width,
                    height=height,
                    autosize='fit',
                    background='white',
                    title=f"Water Observations for {pt_lat:.6f},{pt_lon:.6f}") \
                .mark_tick(thickness=3) \
                .encode(
                    x=altair.X('time:T'),
                    y=altair.Y('observation:nominal', scale=yscale),
                    color=altair.Color('observation:nominal', scale=ascale),
                    tooltip=['observation:nominal',
                             altair.Tooltip(
                                field='time',
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

    output_dict = {
        "data": csv,
        "isEnabled": False,
        "type": "csv",
        "name": "WOfS"
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    outputs = {
        'image': {
            'data': img_url
        },
        'url': {
            'data': html_url
        },
        'timeseries': {
            'data': output_json
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
            version          = '0.3',
            title            = 'Water Observations from Space Pixel Drill',
            abstract         = """
Water Observations from Space Pixel Drill

Water Observations from Space (WOfS) provides surface water observations derived from satellite imagery for all of Australia. The current product (Version 2.1.5) includes observations taken from 1986 to the present, from the Landsat 5, 7 and 8 satellites. WOfS covers all of mainland Australia and Tasmania but excludes off-shore Territories.

The WOfS product allows users to get a better understanding of where water is normally present in a landscape, where water is seldom observed, and where inundation has occurred occasionally.

This Pixel Drill will output the water observations for a point through time as graph.

For service status information, see https://status.dea.ga.gov.au""",
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
            custom_inputs=[
                ComplexInput('geometry',
                             'Location (Lon,Lat)',
                             supported_formats=[
                                                  Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#point')
                                               ])
            ],
            custom_outputs=[
                LiteralOutput("image", "WOfS Pixel Drill Preview"),
                LiteralOutput("url", "WOfS Pixel Drill Graph"),
                ComplexOutput('timeseries',
                              'Timeseries Drill',
                              supported_formats=[
                                _json_format
                              ])
            ],
            custom_data_loader=_getData,
            mask=False)
        

