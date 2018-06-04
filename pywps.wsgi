#!/usr/bin/env python3

from pywps.app.Service import Service

# processes need to be installed in PYTHON_PATH
from processes.polygondrill import PolygonDrill

processes = [
    PolygonDrill()
]

# Service accepts two parameters:
# 1 - list of process instances
# 2 - list of configuration files
application = Service(
    processes,
    ['pywps.cfg']
)
