import pywps
import json
import numpy as np
import io
from xarray import DataArray, Dataset

import datacube
import altair

from processes.geometrydrill import GeometryDrill, _uploadToS3
from pywps import LiteralOutput

from datacube.storage.storage import measurement_paths
from datacube.api.query import query_group_by
from datacube.drivers import new_datasource
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
        print("finding data!", query)
        ds = dc.find_datasets(product=product, group_by="solar_day", **query, **extra_query)
        dss = dc.group_datasets(ds, query_group_by(group_by="solar_day"))

        product = dc.index.products.get_by_name(product)

        lonlat = geometry.Geometry(shape, crs='EPSG:4326').coords[0]
        measurement = product.measurements['water'].copy()
        driller = PixelDrill(16)
        datasources = []
        for ds in dss.values:
            for d in ds:
                datasources.append(new_datasource(d, measurement['name']))
        datasources = sorted(datasources, key=lambda x: x._dataset.center_time)
        times = [x._dataset.center_time for x in datasources]
        files = [s.filename for s in datasources]

        results = [[driller.read(urls=files, lonlat=lonlat)]]
        array = DataArray(
            results,
            dims=('longitude', 'latitude', 'time'),
            coords={'longitude': np.full(1, lonlat[0]), 'latitude': np.full(1, lonlat[1]), 'time': times})

        return array


def _processData(datas, **kwargs):

    flag_lut = {'dry': 'dry', 'sea': 'wet', 'wet': 'wet', 'cloud': 'not observable', 'high_slope': 'not observable', 'cloud_shadow': 'not observable', 'noncontiguous': 'not observable', 'terrain_or_low_angle': 'not observable', 'nodata': 'not observable'}
    with datacube.Datacube() as dc:
        product = dc.index.products.get_by_name('wofs_albers')
    def get_flags(val):
        flag_dict = datacube.storage.masking.mask_to_dict(product.measurements['water'].flags_definition, val)
        flags = filter(flag_dict.get, flag_dict)
        flags_converted = [flag_lut[f] for f in flags]
        return flags_converted[0] if 'not observable' not in flags_converted else 'not observable'
    gf = np.vectorize(get_flags)
    
    data = Dataset()
    data['flags'] = datas[0]
    print(data)
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
            ],
            custom_data_loader=_getData,
            mask=False)
        

