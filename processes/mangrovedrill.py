import pywps
from osgeo import ogr
import json
from functools import partial

import datacube
from datacube.utils import geometry

import rasterio.features

import csv
import io
import boto3
import xarray
from processes.geometrydrill import GeometryDrill, _json_format, DatetimeEncoder
from pywps.inout.formats import FORMATS

from processes.utils import log_call


# Data is a list of Datasets (returned from dc.load and masked if polygons)
@log_call
def _processData(datas, style, **kwargs):
    data = datas[0]
    woodland = data.where( data == 1 ).count(['x', 'y']).drop('extent').rename(name_dict={'canopy_cover_class': 'woodland'})
    open_forest = data.where( data == 2).count(['x', 'y']).drop('extent').rename(name_dict={'canopy_cover_class': 'open_forest'})
    closed_forest = data.where( data == 3).count(['x', 'y']).drop('extent').rename(name_dict={ "canopy_cover_class": 'closed_forest'})

    final = xarray.merge([woodland, open_forest, closed_forest])
    final = final.to_dataframe().to_csv(header=['Woodland', 'Open Forest', 'Closed Forest'],
                                        date_format="%Y-%m-%d");

    output_dict = {
        "data": final,
        "isEnabled": True,
        "type": "csv",
        "name": "Mangrove Cover",
        "tableStyle": style
    }

    output_json = json.dumps(output_dict, cls=DatetimeEncoder)

    output = {
        "timeseries": {
            "output_format": FORMATS.JSON,
            "data": output_json
        }
    }

    return output


class MangroveDrill(GeometryDrill):
    def __init__(self, about, style):
        super().__init__(
            handler          = partial(_processData, style=style),
            products     = [{
                    "name": "mangrove_cover"
                }],
            **about)
