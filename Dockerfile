ARG py_env_path=/env

FROM opendatacube/geobase-builder as env_builder

ARG py_env_path

RUN mkdir -p /conf

COPY requirements.txt /conf
COPY constraints.txt /conf

RUN env-build-tool new /conf/requirements.txt /conf/constraints.txt ${py_env_path}

ENV PATH=${py_env_path}/bin:$PATH

FROM opendatacube/geobase-runner

RUN mkdir -p /code/logs
WORKDIR /code

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && apt-get install -y --fix-missing --no-install-recommends \
    curl \
    wget \
    npm \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install vega-lite vega-cli canvas

COPY --from=env_builder /bin/tini /bin/tini
ARG py_env_path
COPY --from=env_builder $py_env_path $py_env_path

ENV LC_ALL=C.UTF-8
ENV SHELL=bash
# Put `/usr/local/bin` before env to allow overrides in there
ENV PATH=/usr/local/bin:${py_env_path}/bin:$PATH

ADD . /code
WORKDIR /code
RUN pip install --no-deps .

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

RUN useradd -m -s /bin/bash -N -g 100 -u 1001 wps

RUN chmod 777 /code/pywps.cfg \
    && chmod 777 /code/datacube-wps-config.yaml \
    && chown wps:users /code/logs \
    && chown wps:users /code

ENTRYPOINT ["wps-entrypoint.sh"]

USER wps
CMD gunicorn -b 0.0.0.0:8000 datacube_wps:app
