import boto3
from moto import mock_s3

from datacube_wps.impl import create_app

def test_ping(client):
    r = client.get('/ping')
    assert r.status_code == 200


def test_head(client):
    r = client.head('/')
    assert r.status_code == 200


@mock_s3
def xtest_mangrove(client):
    conn = boto3.resource('s3', region_name='ap-southeast-2')
    conn.create_bucket(Bucket='dea-wps-results', CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-2'})

    headers = {'Content-Type': 'text/xml;charset=UTF-8', 'cache-control': 'max-age=0'}

    data = """<?xml version="1.0" encoding="UTF-8"?>
    <wps:Execute version="1.0.0" service="WPS" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.opengis.net/wps/1.0.0" xmlns:wfs="http://www.opengis.net/wfs" xmlns:wps="http://www.opengis.net/wps/1.0.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:gml="http://www.opengis.net/gml" xmlns:ogc="http://www.opengis.net/ogc" xmlns:wcs="http://www.opengis.net/wcs/1.1.1" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://www.opengis.net/wps/1.0.0 http://schemas.opengis.net/wps/1.0.0/wpsAll.xsd">
      <ows:Identifier>WOfSDrill</ows:Identifier>
      <wps:DataInputs>
        <wps:Input>
          <ows:Identifier>geometry</ows:Identifier>
          <wps:Data>
            <wps:ComplexData>{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[146.85029736971987,-32.94459759906837,-1822.7196235501208]}}]}</wps:ComplexData>
          </wps:Data>
        </wps:Input>
      </wps:DataInputs>
      <wps:ResponseForm>
        <wps:ResponseDocument storeExecuteResponse="true" status="true"/>
      </wps:ResponseForm>
    </wps:Execute>
    """

    r = client.post('/?service=WPS&request=Execute', headers=headers, data=data)
    assert r.status_code == 200
