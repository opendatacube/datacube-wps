#!/usr/bin/env python3

import os
import logging
import argparse

import flask
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics

import yaml

import pywps
from pywps import Service

from datacube.utils import import_function
from datacube.virtual import construct

from flask import Flask, request


LOG_FORMAT = ('%(asctime)s] [%(levelname)s] file=%(pathname)s line=%(lineno)s '
              'module=%(module)s function=%(funcName)s %(message)s')


def setup_logger():
    logger = logging.getLogger('PYWPS')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)


setup_logger()


def initialise_prometheus(app, log=None):
    if os.environ.get("prometheus_multiproc_dir", False):
        metrics = GunicornInternalPrometheusMetrics(app)
        if log:
            log.info("Prometheus metrics enabled")
        return metrics
    return None


def initialise_prometheus_register(metrics):
    # Register routes with Prometheus - call after all routes set up.
    if os.environ.get("prometheus_multiproc_dir", False):
        metrics.register_default(
            metrics.summary(
                'flask_wps_request_full_url', 'Request summary by request url',
                labels={
                    'query_request': lambda: request.args.get('request'),
                    'query_url': lambda: request.full_path
                }
            )
        )


if os.environ.get("SENTRY_KEY") and os.environ.get("SENTRY_PROJECT"):
    sentry_sdk.init(dsn="https://%s@sentry.io/%s" % (os.environ["SENTRY_KEY"], os.environ["SENTRY_PROJECT"]),
                    integrations=[FlaskIntegration()])

app = flask.Flask(__name__)

app.url_map.strict_slashes = False


metrics = initialise_prometheus(app)



def create_process(process, input, **settings):
    process_class = import_function(process)
    return process_class(input=construct(**input), **settings)


def read_process_catalog(catalog_filename):
    with open(catalog_filename) as fl:
        config = yaml.load(fl, Loader=yaml.CLoader)

    return [create_process(**settings) for settings in config['processes']]


service = []


@app.after_request
def apply_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'max-age=0'
    return response


@app.route('/', methods=['GET', 'POST'])
def wps():
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script for starting an datacube-wps instance")
    parser.add_argument('-d', '--daemon',
                        action='store_true', help="run in daemon mode")
    parser.add_argument('-a', '--all-addresses',
                        action='store_true', help=("run flask using IPv4 0.0.0.0 (all network interfaces), "
                                                   "otherwise bind to 127.0.0.1 (localhost). "
                                                   "This maybe necessary in systems that only run Flask"))
    args = parser.parse_args()

    if args.all_addresses:
        bind_host = '0.0.0.0'
    else:
        bind_host = '127.0.0.1'

    if args.daemon:
        pid = None
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno)) from e

        if pid == 0:
            os.setsid()
            app.run(threaded=True, host=bind_host)
        else:
            os._exit(0)  # pylint: disable=protected-access
    else:
        app.run(threaded=True, host=bind_host)


# Note: register your default metrics after all routes have been set up.
# Also note, that Gauge metrics registered as default will track the /metrics endpoint, and this can't be disabled at the moment.
initialise_prometheus_register(metrics)
