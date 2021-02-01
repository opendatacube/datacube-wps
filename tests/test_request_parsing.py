import io

import flask
import pytest
from datacube.utils.geometry import Geometry

from datacube_wps.processes import _parse_geom, _get_time

TEST_FEATURE = {
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [125.6, 10.1]},
        "properties": {"name": "Dinagat Islands"},
        "crs": {"properties": {"name": "EPSG:4326"}},
    }]
}

class requests_mock_time:
    def __init__(self):
        self.inputs = {"start": [mock_date_data()], "end": [mock_date_data()]}

class mock_date_data:
    def __init__(self):
        self.data = """{
            "properties": {
                "timestamp" :
                {
                    "date-time" : "2021-02-01"
                }
            }
        }"""

def test_geom_parse():
    assert isinstance(_parse_geom(TEST_FEATURE), Geometry)

def test_time_parse():
    assert _get_time(requests_mock_time())
