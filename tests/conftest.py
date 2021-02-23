import pytest
from datacube_wps import create_app


@pytest.fixture
def app():
    return create_app()
