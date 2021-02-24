#!/usr/bin/env python3

import os
import argparse

from .impl import create_app


app = create_app()


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
