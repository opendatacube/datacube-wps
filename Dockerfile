# syntax=docker/dockerfile:1
ARG py_env_path=/env
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.8.5 AS builder

ARG UV=https://github.com/astral-sh/uv/releases/download/0.6.6/uv-x86_64-unknown-linux-gnu.tar.gz

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=0 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.10 \
    UV_PROJECT_ENVIRONMENT=/app

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libffi-dev \
      # For shapely with --no-binary.
      libgeos-dev \
      # For Psycopg2.
      libpq-dev \
      python3-dev \
      unzip

ARG py_env_path

WORKDIR /build

ADD --checksum=sha256:4c3426c4919d9f44633ab9884827fa1ad64ad8d993516d636eb955a3835c4a8c --chown=root:root --chmod=644 --link $UV uv.tar.gz

RUN tar xf uv.tar.gz -C /usr/local/bin --strip-components=1 --no-same-owner

COPY --link pyproject.toml uv.lock /build/

# Use a separate cache volume for uv on opendatacube projects, so it is
# not inseparable from pip/poetry/npm/etc. cache stored in /root/.cache.
RUN --mount=type=cache,id=opendatacube-uv-cache,target=/root/.cache \
    uv sync --locked --no-install-project \
      --no-binary-package fiona \
      --no-binary-package rasterio \
      --no-binary-package shapely

ENV PATH=${py_env_path}/bin:$PATH

FROM ghcr.io/osgeo/gdal:ubuntu-small-3.8.5

RUN mkdir -p /code/logs
WORKDIR /code

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PATH=/app/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
      curl \
      libpq5 \
      tini \
      wget \
      git \
    && rm -rf /var/lib/apt/lists/*

# install nodejs & vega-lite (for saving altair charts to svg)
RUN curl -LsS https://raw.githubusercontent.com/tj/n/master/bin/n -o n \
    && bash n lts \
    && rm n \
    && node --version \
    && npm install --engine-strict vega-lite vega-cli canvas

RUN useradd -m -s /bin/bash -N -g 100 -u 1001 wps

ARG py_env_path
# Docker 28.x requires numeric uid/gid with --link when using
# a non-default builder like the CI action does in this repository.
COPY --from=builder --link --chown=1000:1000 /app /app
COPY --from=builder --link /build/*.txt /conf/
COPY --from=builder --link /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder --link /usr/local/bin/uvx /usr/local/bin/uvx

# Put `/usr/local/bin` before env to allow overrides in there
ENV PATH=/usr/local/bin:/app/bin:${py_env_path}/bin:$PATH

ADD . /code
WORKDIR /code
RUN uv pip install -r requirements.txt

RUN chmod 666 /code/pywps.cfg \
    && chmod 666 /code/datacube-wps-config.yaml \
    && chown wps:users /code/logs \
    && chown wps:users /code

ENTRYPOINT ["wps-entrypoint.sh"]

USER wps
CMD gunicorn -b 0.0.0.0:8000 datacube_wps:app
