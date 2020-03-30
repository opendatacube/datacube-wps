#!/usr/bin/env python3

# Copyright (c) 2016 PyWPS Project Steering Committee
# 
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import flask
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

import pywps
from pywps import Service
from processes.fcdrill import FcDrill
from processes.wofsdrill import WofsDrill

import logging
import yaml

logger = logging.getLogger('PYWPS')
handler = logging.StreamHandler()
format = '%(asctime)s] [%(levelname)s] file=%(pathname)s line=%(lineno)s module=%(module)s function=%(funcName)s %(message)s'
handler.setFormatter(logging.Formatter(format))
logger.addHandler(handler)


if os.environ.get("SENTRY_KEY") and os.environ.get("SENTRY_PROJECT"):
   sentry_sdk.init(
        dsn="https://%s@sentry.io/%s" % (os.environ["SENTRY_KEY"], os.environ["SENTRY_PROJECT"]),
        integrations = [FlaskIntegration()]
   )

app = flask.Flask(__name__)

app.url_map.strict_slashes = False

with open('DEA_WPS_config.yaml') as fl:
    config = yaml.load(fl)

processes = [
    WofsDrill(config['processes']['WOfSDrill']['about'], config['processes']['WOfSDrill']['style']),
    FcDrill(config['processes']['FCDrill']['about'], config['processes']['FCDrill']['style'])
]

# For the process list on the home page

process_descriptor = {}
for process in processes:
    abstract = process.abstract
    identifier = process.identifier
    process_descriptor[identifier] = abstract

# This is, how you start PyWPS instance
service = Service(processes, ['pywps.cfg'])


@app.after_request
def apply_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'max-age=0'
    return response


# @app.route('/')
# def index():
#     server_url = pywps.configuration.get_config_value("server", "url")
#     request_url = flask.request.url
#     return flask.render_template('home.html', request_url=request_url,
#                                  server_url=server_url,
#                                  process_descriptor=process_descriptor)

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

    parser = argparse.ArgumentParser(
        description="""Script for starting an example PyWPS
                       instance with sample processes""",
        epilog="""Do not use this service in a production environment.
         It's intended to be running in test environment only!
        For more documentation, visit http://pywps.org/doc
        """
        )
    parser.add_argument('-d', '--daemon',
                        action='store_true', help="run in daemon mode")
    parser.add_argument('-a','--all-addresses',
                        action='store_true', help="run flask using IPv4 0.0.0.0 (all network interfaces),"  +  
                            "otherwise bind to 127.0.0.1 (localhost).  This maybe necessary in systems that only run Flask") 
    args = parser.parse_args()
    
    if args.all_addresses:
        bind_host='0.0.0.0'
    else:
        bind_host='127.0.0.1'

    if args.daemon:
        pid = None
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if (pid == 0):
            os.setsid()
            app.run(threaded=True,host=bind_host)
        else:
            os._exit(0)
    else:
        app.run(threaded=True,host=bind_host)
