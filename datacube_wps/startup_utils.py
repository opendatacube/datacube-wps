import logging
import os

import sentry_sdk
from prometheus_flask_exporter.multiprocess import \
    GunicornInternalPrometheusMetrics
from sentry_sdk.integrations.flask import FlaskIntegration

LOG_FORMAT = ('%(asctime)s] [%(levelname)s] file=%(pathname)s line=%(lineno)s '
              'module=%(module)s function=%(funcName)s %(message)s')


def setup_logger():
    logger = logging.getLogger('PYWPS')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)


def initialise_prometheus(app, log=None):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR", False):
        metrics = GunicornInternalPrometheusMetrics(app)
        if log:
            log.info("Prometheus metrics enabled")
        return metrics
    return None


def setup_sentry():
    env = os.environ

    if "SENTRY_KEY" in env and "SENTRY_PROJECT" in env and "SENTRY_ORG" in env:
        sentry_sdk.init(
            dsn="https://%s@o%s.ingest.sentry.io/%s" % (env["SENTRY_KEY"],
                                                        env["SENTRY_ORG"],
                                                        env["SENTRY_PROJECT"]),
            environment=env.get("SENTRY_ENV_TAG", "dev"),
            integrations=[FlaskIntegration()]
        )
