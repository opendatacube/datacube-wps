#!/usr/bin/env python3

import os
import flask
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

import pywps
from pywps import Service
from processes.fcdrill import FCDrill
from processes.wofsdrill import WOfSDrill
from processes.mangrovedrill import MangroveDrill

import logging
import yaml

logger = logging.getLogger('PYWPS')
handler = logging.StreamHandler()
format = ('%(asctime)s] [%(levelname)s] file=%(pathname)s line=%(lineno)s '
          'module=%(module)s function=%(funcName)s %(message)s')
handler.setFormatter(logging.Formatter(format))
logger.addHandler(handler)


if os.environ.get("SENTRY_KEY") and os.environ.get("SENTRY_PROJECT"):
    sentry_sdk.init(
        dsn="https://%s@sentry.io/%s" % (os.environ["SENTRY_KEY"], os.environ["SENTRY_PROJECT"]),
        integrations=[FlaskIntegration()]
    )

app = flask.Flask(__name__)

app.url_map.strict_slashes = False

process_classes = {
    'WOfSDrill': WOfSDrill,
    'FCDrill': FCDrill,
    'MangroveDrill': MangroveDrill
}

with open('DEA_WPS_config.yaml') as fl:
    config = yaml.load(fl)

processes = [process_classes[proc_name](proc_settings['about'], proc_settings['style'])
             for proc_name, proc_settings in config['processes'].items()]

service = Service(processes, ['pywps.cfg'])


@app.after_request
def apply_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'max-age=0'
    return response


@app.route('/', methods=['GET', 'POST'])
def wps():
    return service


@app.route('/ping')
def ping():
    return 'system is healthy'


@app.route('/outputs/'+'<path:filename>')
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
    else:
        flask.abort(404)


if __name__ == "__main__":
    import argparse

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
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if (pid == 0):
            os.setsid()
            app.run(threaded=True, host=bind_host)
        else:
            os._exit(0)
    else:
        app.run(threaded=True, host=bind_host)
