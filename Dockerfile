FROM opendatacube/datacube-core:latest

RUN pip3 install -e git+https://github.com/roarmstrong/pywps.git@develop#egg=pywps \
    && rm -rf $HOME/.cache/pip

RUN pip3 install \
    flask scikit-image gunicorn rasterio==1.0.2 \
    && rm -rf $HOME/.cache/pip

RUN apt-get update && apt-get install -y \
    wget unzip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

ADD . .

WORKDIR /code/logs
WORKDIR /code

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app