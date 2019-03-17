import datacube
from datacube.storage.masking import make_mask

from pywps import LiteralOutput
from processes.geometrydrill import GeometryDrill
import altair
import xarray
import io

from processes.geometrydrill import _uploadToS3


# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(datas, **kwargs):
    dc = datacube.Datacube()
    wofs_product = dc.index.products.get_by_name("wofs_albers")

    wofs_mask_flags = [
        {
            "flags": {
                'dry': True
            },
        },
        {
            "flags": {
                "terrain_or_low_angle": False,
                "high_slope": False,
                "cloud_shadow": False,
                "cloud": False,
                "sea": False
            }
        },
    ]
    data = xarray.Dataset()
    for k, d in datas.items():
        if len(d.variables) > 0 and k != 'wofs_albers':
            if len(data.variables) > 0:
                data += d
            else:
                data = d
    print(data)
    mask_data = datas['wofs_albers'].astype('uint8')
    mask_data.attrs["flags_definition"] = wofs_product.measurements['water']['flags_definition']
    for m in wofs_mask_flags:
        mask = make_mask(mask_data, **m['flags'])
        data = data.where(mask['water'])

    pixels = (data != -1).sum(dim=['x', 'y'])

    fc_tester = data.drop(['UE'])

    #following robbi's advice, cast the dataset to a dataarray
    maxFC = fc_tester.to_array(dim='variable', name='maxFC')

    #turn FC array into integer only as nanargmax doesn't seem to handle floats the way we want it to
    FC_int = maxFC.astype('int8')

    #use numpy.nanargmax to get the index of the maximum value along the variable dimension
    #BSPVNPV=np.nanargmax(FC_int, axis=0)
    BSPVNPV = FC_int.argmax(dim='variable')

    FC_mask=xarray.ufuncs.isfinite(maxFC).all(dim='variable')

    # #re-mask with nans to remove no-data
    BSPVNPV=BSPVNPV.where(FC_mask)

    FC_dominant = xarray.Dataset({
        'BS': (BSPVNPV==0).where(FC_mask),
        'PV': (BSPVNPV==1).where(FC_mask),
        'NPV': (BSPVNPV==2).where(FC_mask),
    })

    FC_count = FC_dominant.sum(dim=['x','y'])

    #Fractional cover pixel count method
    #Get number of FC pixels, divide by total number of pixels per polygon

    Bare_soil_percent=(FC_count.BS/pixels)['BS']

    Photosynthetic_veg_percent=(FC_count.PV/pixels)['PV']

    NonPhotosynthetic_veg_percent=(FC_count.NPV/pixels)['NPV']

    # print(Bare_soil_percent, Photosynthetic_veg_percent, NonPhotosynthetic_veg_percent) 

    pixels['BS'] = Bare_soil_percent
    pixels['PV'] = Photosynthetic_veg_percent
    pixels['NPV'] = NonPhotosynthetic_veg_percent

    pixels = pixels.drop('UE')

    df = pixels.to_dataframe()
    df.reset_index(inplace=True)
    df = df.melt('time', var_name='Cover Type', value_name='Area')
    print ("pixels", df)

    chart = altair.Chart(df,
                         width=1000,
                         height=300,
                         title='Percentage of Area - Fractional Cover') \
                  .mark_area() \
                  .encode(
                    x='time:T',
                    y=altair.Y('Area:Q', stack='normalize'),
                    color=altair.Color('Cover Type:N',
                                       scale=altair.Scale(domain=['PV', 'NPV', 'BS'],
                                       range=['green', '#dac586', '#8B0000']))
                    )
                    # tooltip=[altair.Tooltip(
                    #             field='time',
                    #             format='%d %B, %Y',
                    #             title='Date',
                    #             type='temporal'),
                    #          'Area:Q',
                    #          'Cover Type:N'])

    html_io = io.StringIO()
    chart.save(html_io, format='html')
    html_bytes = io.BytesIO(html_io.getvalue().encode())
    html_url = _uploadToS3(str(kwargs['process_id']) + '/chart.html', html_bytes, 'text/html')
    print(html_url)
    # # data = data.dropna('time', how='all')
    # data = data.mean(dim=('x','y'))
    # data = data.to_dataframe().to_csv(header=['Bare Soil',
    #                                           'Photosynthetic Vegetation',
    #                                           'Non-Photosynthetic Vegetation',
    #                                           'Unmixing Error'],
    #                                   date_format="%Y-%m-%d");
    outputs = {
        'url': {
            'data': html_url
        }
    }
    return outputs


tableStyle = {
    "columns": {
        "Bare Soil": {
            "units": "%",
            "chartLineColor": "#8B0000",
            "active": True
        },
        "Photosynthetic Vegetation": {
            "units": "%",
            "chartLineColor": "green",
            "active": True
        },
        "Non-Photosynthetic Vegetation": {
            "units": "%",
            "chartLineColor": "#dac586",
            "active": True
        },
        "Unmixing Error": {
            "units": "%",
            "chartLineColor": "#6699CC",
            "active": False
        }
    }
}

class FcDrill(GeometryDrill):
    def __init__(self):
        super(FcDrill, self).__init__(
            handler          = _processData,
            identifier       = 'FractionalCoverDrill',
            version          = '0.2',
            title            = 'Fractional Cover',
            abstract         = 'Performs Fractional Cover Polygon Drill',
            store_supported  = True,
            status_supported = True,
            geometry_type    = "polygon",
            products         = [
                {
                    "name": "ls8_fc_albers"
                },
                {
                    "name": "ls7_fc_albers"
                },
                {
                    "name": "ls5_fc_albers"
                },
                {
                    "name": "wofs_albers",
                    "additional_query": {
                        "output_crs": 'EPSG:3577',
                        "resolution": (-25, 25)
                    }
                }
            ],
            output_name      = "FC",
            custom_outputs=[LiteralOutput("url", "Fractional Cover Asset Drill")])
        

