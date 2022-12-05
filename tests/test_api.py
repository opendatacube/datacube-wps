import pytest
from datacube.utils.geometry import CRS, Geometry

from datacube_wps.impl import read_process_catalog
from datacube_wps.processes.fcdrill import FCDrill
from datacube_wps.processes.mangrovedrill import MangroveDrill
from datacube_wps.processes.witprocess import WIT
from datacube_wps.processes.wofsdrill import WOfSDrill


def test_fc():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    fc = [entry for entry in catalog if isinstance(entry, FCDrill)][0]
    poly = Geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [153.1, -27.4],
                    [153.3, -27.4],
                    [153.3, -27.2],
                    [153.1, -27.2],
                    [153.1, -27.4],
                ]
            ],
        },
        crs=CRS("EPSG:4326"),
    )
    results = fc.query_handler(time=("2019-01-05", "2019-03-10"), feature=poly)
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
                    [153.1, -27.4],
                    [153.3, -27.4],
                    [153.3, -27.2],
                    [153.1, -27.2],
                    [153.1, -27.4],
                ]
            ],
        },
        crs=CRS("EPSG:4326"),
    )
    results = fc.query_handler(time=("2019", "2020"), feature=poly)
    assert "data" in results
    assert "chart" in results


def test_wofs():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    wofs = [entry for entry in catalog if isinstance(entry, WOfSDrill)][0]
    point = Geometry(
        {
            "type": "Point",
            "coordinates": [153.1, -27.4, 0]
        },
        crs=CRS("EPSG:4326"),
    )
    results = wofs.query_handler(time="2019", feature=point)
    assert "data" in results
    assert "chart" in results


@pytest.mark.xfail(reason="Appears to be an incomplete implementation")
def test_wit():
    catalog = read_process_catalog("datacube-wps-config.yaml")
    wit_proc = [entry for entry in catalog if isinstance(entry, WIT)][0]
    poly = Geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [153.1, -27.4],
                    [153.3, -27.4],
                    [153.3, -27.2],
                    [153.1, -27.2],
                    [153.1, -27.4],
                ]
            ],
        },
        crs=CRS("EPSG:4326"),
        # crs=CRS("EPSG:3577"),
    )
    results = wit_proc.query_handler(time=("2019","2020"), feature=poly)
    assert "data" in results
    assert "chart" in results
