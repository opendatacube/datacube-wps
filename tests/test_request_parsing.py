import io

import flask
import pytest
from datacube.utils.geometry import Geometry

from datacube_wps.processes import _get_feature, _parse_geom

TEST_FEATURE = {
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [125.6, 10.1]},
        "properties": {"name": "Dinagat Islands"},
        "crs": {"properties": {"name": "EPSG:4326"}},
    }]
}

def test_geom_parse():
    assert isinstance(_parse_geom(TEST_FEATURE), Geometry)
