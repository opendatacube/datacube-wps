from moto import mock_s3
import boto3
import altair as alt
from vega_datasets import data
import pywps.configuration as config

from datacube_wps.processes import upload_chart_svg_to_S3, upload_chart_html_to_S3

TEST_CHART = chart = (
        alt.Chart(data.cars.url)
        .mark_point()
        .encode(x="Horsepower:Q", y="Miles_per_Gallon:Q", color="Origin:N")
    )

TEST_CFG = "pywps.cfg"

@mock_s3
def test_s3_svg_chart_upload():
    config.load_configuration(TEST_CFG)
    bucket = config.get_config_value("s3", "bucket")
    region = config.get_config_value("s3", "region")
    location = {'LocationConstraint': region}
    client = boto3.client("s3",region_name=region)
    client.create_bucket(Bucket=bucket,CreateBucketConfiguration=location)
    upload_chart_svg_to_S3(TEST_CHART, "abcd")

@mock_s3
def test_s3_html_chart_upload():
    config.load_configuration(TEST_CFG)
    bucket = config.get_config_value("s3", "bucket")
    region = config.get_config_value("s3", "region")
    location = {'LocationConstraint': region}
    client = boto3.client("s3",region_name=region)
    client.create_bucket(Bucket=bucket,CreateBucketConfiguration=location)
    upload_chart_html_to_S3(TEST_CHART, "abcd")
