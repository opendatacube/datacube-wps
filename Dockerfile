ARG py_env_path=/env

FROM csiroeasi/geobase-builder:develop.latest as env_builder

ARG py_env_path

RUN mkdir -p /conf

COPY requirements.txt /conf
COPY constraints.txt /conf
RUN python3 -m venv ${py_env_path} && \
    ${py_env_path}/bin/python -m pip  install --no-cache-dir ${PIP_EXTRA_ARGS} -U pip wheel setuptools setuptools_scm scikit-build -c /conf/constraints.txt

RUN ${py_env_path}/bin/python -m pip  install --no-cache-dir -r /conf/requirements.txt -c /conf/constraints.txt

ENV PATH=${py_env_path}/bin:$PATH

FROM csiroeasi/geobase-runner:develop.latest

RUN mkdir -p /code/logs
WORKDIR /code

ENV DEBIAN_FRONTEND=noninteractive

# Use for local builds to find a local apt mirror
# RUN apt-get update -y && apt install -y --fix-missing --no-install-recommends wget ca-certificates && \
#   wget http://ftp.us.debian.org/debian/pool/main/n/netselect/netselect_0.3.ds1-29_amd64.deb && \
#   dpkg -i netselect_0.3.ds1-29_amd64.deb && \
#   export APT_MIRROR=$(netselect -s 1 -t 20 $(wget -qO - mirrors.ubuntu.com/mirrors.txt) | awk '{print $2}') && \
#   echo $APT_MIRROR && \
#   sed -i -r "s#http:\/\/archive.ubuntu.com\/ubuntu\/#${APT_MIRROR}#" /etc/apt/sources.list

RUN apt-get update -y && apt-get install -y --fix-missing --no-install-recommends \
    curl \
    wget \
    git \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# install nodejs & vega-lite (for saving altair charts to svg)
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash - \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --fix-missing --no-install-recommends \
  nodejs

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
