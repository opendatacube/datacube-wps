import os

import flask
import yaml
from pywps import Service

from datacube.utils import import_function
from datacube.virtual import construct

from .startup_utils import setup_logger, initialise_prometheus, initialise_prometheus_register, setup_sentry


def create_process(process, input, **settings):
    process_class = import_function(process)
    return process_class(input=construct(**input), **settings)


def read_process_catalog(catalog_filename):
    with open(catalog_filename) as fl:
        config = yaml.load(fl, Loader=yaml.CLoader)

    return [create_process(**settings) for settings in config['processes']]


def create_app():
    # pylint: disable=unused-variable

    setup_logger()
    setup_sentry()

    app = flask.Flask(__name__)   # pylint: disable=redefined-outer-name
    app.url_map.strict_slashes = False

    metrics = initialise_prometheus(app)

    service = []

    @app.after_request
    def apply_cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'max-age=0'
        return response

    @app.route('/', methods=['GET', 'POST', 'HEAD'])
    def wps():
        if flask.request.method == 'HEAD':
            return ""

        if not service:
            service.append(Service(read_process_catalog('datacube-wps-config.yaml'), ['pywps.cfg']))
        return service[0]

    @app.route('/ping')
    def ping():
        return 'system is healthy'

    @app.route('/outputs/' + '<path:filename>')
    def outputfile(filename):
        targetfile = os.path.join('outputs', filename)
        if os.path.isfile(targetfile):
            file_ext = os.path.splitext(targetfile)[1]
            with open(targetfile, mode='rb') as f:
                file_bytes = f.read()
            mime_type = None
            if 'xml' in file_ext:
                mime_type = 'text/xml'
            return flask.Response(file_bytes, content_type=mime_type)

        flask.abort(404)

    # Note: register your default metrics after all routes have been set up.
    # Also note, that Gauge metrics registered as default will track the /metrics endpoint,
    # and this can't be disabled at the moment.
    initialise_prometheus_register(metrics)

    return app
