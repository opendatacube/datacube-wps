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
    woodland = data.where( data == 1 ).count(['x', 'y']).rename(name_dict={'canopy_cover_class': 'woodland'})
    open_forest = data.where( data == 2).count(['x', 'y']).rename(name_dict={'canopy_cover_class': 'open_forest'})
    closed_forest = data.where( data == 3).count(['x', 'y']).rename(name_dict={ "canopy_cover_class": 'closed_forest'})

    final = xarray.merge([wet, dry, notobservable])
    final = final.to_dataframe().to_csv(header=['Woodland', 'Open Forest', 'Closed Forest'],
                                        date_format="%Y-%m-%d");
    return final


tableStyle = {
    "columns": {
        "Woodland": {
            "units": "#",
            "chartLineColor": "#9FFF4C",
            "active": True
        },
        "Open Forest": {
            "units": "#",
            "chartLineColor": "#5ECC00",
            "active": True
        },
        "Closed Forest": {
            "units": "#",
            "chartLineColor": "#3B7F00",
            "active": True
        }
    }
}

class MangroveDrill(GeometryDrill):
    def __init__(self):
        super(MangroveDrill, self).__init__(
            handler          = _processData,
            identifier       = 'Mangrove Cover Drill',
            version          = '0.1',
            title            = 'Mangrove Cover',
            abstract         = 'Performs Mangrove Polygon Drill',
            store_supported  = True,
            status_supported = True,
            geometry_type    = "polygon",
            products     = [{
                    "name": "mangrove_cover"
                }],
            table_style      = tableStyle,
            output_name      = "Mangrove Cover")
        

