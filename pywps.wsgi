#!/usr/bin/env python3

from wps import app

if __name__ == "__main__":
    app.run()

# from pywps.app.Service import Service

# # processes need to be installed in PYTHON_PATH
# from processes.polygondrill import PolygonDrill

# processes = [
#     PolygonDrill()
# ]

# class WPS(object):
#     def __init__(self, app):
#         self.app = app

#     def __call__(self, environ, response):
#         def add_cors(status, headers, exc_info=None):
#             headers.append(("Access-Control-Allow-Origin", "*"))
#             return response(status, headers, exc_info)

#         return self.app(environ, add_cors)

# # Service accepts two parameters:
# # 1 - list of process instances
# # 2 - list of configuration files
# application = WPS(Service(
#     processes,
#     ['pywps.cfg']
# ))
