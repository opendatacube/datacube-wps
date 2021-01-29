from moto import mock_s3
import altair as alt
from vega_datasets import data

from datacube_wps.processes import upload_chart_svg_to_S3, upload_chart_html_to_S3

TEST_CHART = chart = (
        alt.Chart(data.cars.url)
        .mark_point()
        .encode(x="Horsepower:Q", y="Miles_per_Gallon:Q", color="Origin:N")
    )

@mock_s3
def test_s3_svg_chart_upload():
    upload_chart_svg_to_S3(TEST_CHART, "abcd")

@mock_s3
def test_s3_html_chart_upload():
    upload_chart_html_to_S3(TEST_CHART, "abcd")
