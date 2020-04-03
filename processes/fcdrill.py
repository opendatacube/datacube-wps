from timeit import default_timer as timer
import multiprocessing
import datacube
from datacube.storage.masking import make_mask
from functools import partial

from pywps import LiteralOutput, ComplexOutput
from pywps.app.exceptions import ProcessError

import altair
import xarray
import io
import numpy as np
import json

from processes.geometrydrill import _uploadToS3, DatetimeEncoder, FORMATS, log_call, GeometryDrill


# Data is a list of Datasets (returned from dc.load and masked if polygons)
@log_call
def _processData(datas, style, **kwargs):
    start_time = timer()
    dc = datacube.Datacube()
    wofs_product = dc.index.products.get_by_name("wofs_albers")

    wofs_mask_flags = [
        dict(dry=True),
        dict(terrain_or_low_angle=False, high_slope=False, cloud_shadow=False, cloud=False, sea=False)
    ]

    data = xarray.Dataset()
    for k, d in datas.items():
        if len(d.variables) > 0 and k != 'wofs_albers':
            if len(data.variables) > 0:
                data = xarray.concat([data, d], dim='time')
            else:
                data = d
    if not data or not datas['wofs_albers']:
        raise ProcessError('query returned no data')

    total = data.count(dim=['x', 'y'])
    total_valid = (data != -1).sum(dim=['x', 'y'])

    mask_data = datas['wofs_albers'].astype('uint8')
    mask_data.attrs["flags_definition"] = wofs_product.measurements['water']['flags_definition']
    for m in wofs_mask_flags:
        mask = make_mask(mask_data, **m)
        data = data.where(mask['water'])

    print('masking took', timer() - start_time)
    print('data', data)

    total_invalid = (np.isnan(data)).sum(dim=['x', 'y'])
    not_pixels = total_valid - (total - total_invalid)

    fc_tester = data.drop(['UE'])

    # following robbi's advice, cast the dataset to a dataarray
    maxFC = fc_tester.to_array(dim='variable', name='maxFC')

    # turn FC array into integer only as nanargmax doesn't seem to handle floats the way we want it to
    FC_int = maxFC.astype('int16')
    print('FC_int', FC_int)

    # use numpy.nanargmax to get the index of the maximum value along the variable dimension
    # BSPVNPV=np.nanargmax(FC_int, axis=0)
    BSPVNPV = FC_int.argmax(dim='variable')

    FC_mask = xarray.ufuncs.isfinite(maxFC).all(dim='variable')

    # #re-mask with nans to remove no-data
    BSPVNPV = BSPVNPV.where(FC_mask)

    FC_dominant = xarray.Dataset({
        'BS': (BSPVNPV == 0).where(FC_mask),
        'PV': (BSPVNPV == 1).where(FC_mask),
        'NPV': (BSPVNPV == 2).where(FC_mask)
    })

    FC_count = FC_dominant.sum(dim=['x', 'y'])

    # Fractional cover pixel count method
    # Get number of FC pixels, divide by total number of pixels per polygon

    Bare_soil_percent = (FC_count.BS / total_valid)['BS']

    Photosynthetic_veg_percent = (FC_count.PV / total_valid)['PV']

    NonPhotosynthetic_veg_percent = (FC_count.NPV / total_valid)['NPV']

    Unobservable = (not_pixels / total_valid)['BS']

    # print(Bare_soil_percent, Photosynthetic_veg_percent, NonPhotosynthetic_veg_percent)
    new_ds = xarray.Dataset({
        'BS': Bare_soil_percent * 100,
        'PV': Photosynthetic_veg_percent * 100,
        'NPV': NonPhotosynthetic_veg_percent * 100,
        'Unobservable': Unobservable * 100
    })

    print('calling dask with', multiprocessing.cpu_count())
    dask_time = timer()
    new_ds = new_ds.compute(scheduler='processes')
    print(new_ds)
    print('dask took exactly', timer() - dask_time)

    df = new_ds.to_dataframe()
    df.reset_index(inplace=True)
    melted = df.melt('time', var_name='Cover Type', value_name='Area')
    melted = melted.dropna()
    print(melted)

    chart = altair.Chart(melted,
                         width=1000,
                         height=300,
                         title='Percentage of Area - Fractional Cover')
    chart = chart.mark_area()
    chart = chart.encode(x='time:T',
                         y=altair.Y('Area:Q', stack='normalize'),
                         color=altair.Color('Cover Type:N',
                                            scale=altair.Scale(domain=['PV', 'NPV', 'BS', 'Unobservable'],
                                                               range=['green', '#dac586', '#8B0000', 'grey'])),
                         tooltip=[altair.Tooltip(field='time', format='%d %B, %Y', title='Date', type='temporal'),
                                  'Area:Q',
                                  'Cover Type:N'])

    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    html_url = _uploadToS3(str(kwargs['process_id']) + '/chart.html', html_bytes, 'text/html')
    print(html_url)
    # data = data.dropna('time', how='all')
    csv = new_ds.to_dataframe().to_csv(header=['Bare Soil',
                                               'Photosynthetic Vegetation',
                                               'Non-Photosynthetic Vegetation',
                                               'Unobservable'],
                                       date_format="%Y-%m-%d")

    output_dict = {
        "data": csv,
        "isEnabled": True,
        "type": "csv",
        "name": "FC",
        "tableStyle": style
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    output_str = output_json

    outputs = {
        'url': {'data': html_url},
        'timeseries': {'data': output_str}
    }

    print('in processData: ', timer() - start_time)
    return outputs


def wofls_fuser(dest, src):
    where_nodata = (src & 1) == 0
    np.copyto(dest, src, where=where_nodata)
    return dest


class FCDrill(GeometryDrill):
    def __init__(self, about, style):
        super().__init__(handler=partial(_processData, style=style),
                         products=[
                             {"name": "ls8_fc_albers"},
                             {"name": "ls7_fc_albers"},
                             {"name": "ls5_fc_albers"},
                             {"name": "wofs_albers", "additional_query": {"fuse_func": wofls_fuser}}
                         ],
                         custom_outputs=[
                             LiteralOutput("url", "Fractional Cover Asset Drill"),
                             ComplexOutput('timeseries',
                                           'Timeseries Drill',
                                           supported_formats=[FORMATS['output_json']])
                         ],
                         **about)
