import pywps
from osgeo import ogr
import json

import datacube
from datacube.utils import geometry

import rasterio.features

import csv
import io
import boto3
import xarray
from processes.geometrydrill import GeometryDrill


# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(datas, **kwargs):
    data = datas[0]
    wet = data.where( data == 128 or data == 132 ).count(['x', 'y']).rename(name_dict={'water': 'wet'})
    dry = data.where( data == 0 or data == 4 ).count(['x', 'y']).rename(name_dict={'water': 'dry'})
    notobservable = data.where( data != 0 or data != 4 or data != 128 or data != 132).count(['x', 'y']).rename(name_dict={ "water": 'notobservable'})

    final = xarray.merge([wet, dry, notobservable])
    final = final.to_dataframe().to_csv(header=['Wet', 'Dry', 'Not Observable'],
                                        date_format="%Y-%m-%d");
    return final


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
            version          = '0.1',
            title            = 'WOfS',
            abstract         = 'Performs WOfS Polygon Drill',
            store_supported  = True,
            status_supported = True,
            geometry_type    = "polygon",
            products         = [{
                "name": "wofs_albers",
                "additional_query": {
                    "output_crs": 'EPSG:3577',
                    "resolution": (-25, 25)
                }
            }],
            output_name      = "WOfS",
            table_style      = tableStyle)
        

