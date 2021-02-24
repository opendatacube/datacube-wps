import pytest

from datacube.utils.geometry import CRS, Geometry

from datacube_wps.impl import read_process_catalog
from datacube_wps.processes.fcdrill import FCDrill
from datacube_wps.processes.mangrovedrill import MangroveDrill
from datacube_wps.processes.wofsdrill import WOfSDrill


def test_fc():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    fc = [entry for entry in catalog if isinstance(entry, FCDrill)][0]
    poly = Geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    (147.28271484375003, -35.89238773935897),
                    (147.03277587890628, -35.663990911348115),
                    (146.65237426757815, -35.90684930677119),
                    (147.09182739257815, -36.15894422111004),
                    (147.28271484375003, -35.89238773935897),
                ]
            ],
        },
        crs=CRS("EPSG:4326"),
    )
    results = fc.query_handler(time=("2019-03-05", "2019-07-10"), feature=poly)
    assert "data" in results
    assert "chart" in results


def test_mangrove():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    fc = [entry for entry in catalog if isinstance(entry, MangroveDrill)][0]
    poly = Geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    (143.98956298828125, -14.689881366618762),
                    (144.26422119140625, -14.689881366618762),
                    (144.26422119140625, -14.394778454856146),
                    (143.98956298828125, -14.394778454856146),
                    (143.98956298828125, -14.689881366618762),
                ]
            ],
        },
        crs=CRS("EPSG:4326"),
    )
    results = fc.query_handler(time=("2000", "2005"), feature=poly)
    assert "data" in results
    assert "chart" in results

#@pytest.mark.xfail(reason="Pixel drills need special config")
def test_wofs():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    wofs = [entry for entry in catalog if isinstance(entry, WOfSDrill)][0]
    point = Geometry(
        {"type": "Point", "coordinates": [137.01475095074406, -28.752777955850917, 0]},
        crs=CRS("EPSG:4326"),
    )
    results = wofs.query_handler(time="2000", feature=point)
    assert "data" in results
    assert "chart" in results
