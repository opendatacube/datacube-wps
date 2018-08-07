import pywps
from osgeo import ogr
import json

import datacube
from datacube.utils import geometry
from datacube.storage.masking import make_mask

import rasterio.features

import csv
import io
import boto3
import xarray
from processes.geometrydrill import GeometryDrill


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

    data = datas[0]
    mask_data = datas[1].astype('uint8')
    mask_data.attrs["flags_definition"] = wofs_product.measurements['water']['flags_definition']
    for m in wofs_mask_flags:
        mask = make_mask(mask_data, **m['flags'])
        data = data.where(mask['water'])

    data = data.dropna('time', how='all')
    data = data.mean(dim=('x','y'))
    data = data.to_dataframe().to_csv(header=['Bare Soil',
                                              'Photosynthetic Vegetation',
                                              'Non-Photosynthetic Vegetation',
                                              'Unmixing Error'],
                                      date_format="%Y-%m-%d");
    return data


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
            version          = '0.1',
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
                    "name": "wofs_albers",
                    "additional_query": {
                        "output_crs": 'EPSG:3577',
                        "resolution": (-25, 25)
                    }
                }
            ],
            table_style      = tableStyle,
            output_name      = "FC")
        

