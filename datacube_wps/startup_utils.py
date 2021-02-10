import os
import logging

from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import request

LOG_FORMAT = ('%(asctime)s] [%(levelname)s] file=%(pathname)s line=%(lineno)s '
              'module=%(module)s function=%(funcName)s %(message)s')


def setup_logger():
    logger = logging.getLogger('PYWPS')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)


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


def setup_sentry():
    if os.environ.get("SENTRY_KEY") and os.environ.get("SENTRY_PROJECT"):
        sentry_sdk.init(dsn="https://%s@sentry.io/%s" % (os.environ["SENTRY_KEY"], os.environ["SENTRY_PROJECT"]),
                        integrations=[FlaskIntegration()])
