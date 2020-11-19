ARG V_BASE=3.0.4
ARG py_env_path=/env

FROM opendatacube/geobase:wheels-${V_BASE} as env_builder
ARG py_env_path

RUN mkdir -p /conf

COPY requirements.txt /conf

RUN env-build-tool new /conf/requirements.txt

ENV PATH=${py_env_path}/bin:$PATH

FROM opendatacube/geobase:runner-${V_BASE}

RUN mkdir -p /code/logs
WORKDIR /code

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y && apt-get install -y --fix-missing --no-install-recommends \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# include webdriver installed by apt in path
ENV PATH="/usr/lib/chromium-browser/:${PATH}"
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

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 datacube_wps:app
