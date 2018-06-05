FROM opendatacube/datacube-core:latest

RUN pip3 install \
    flask scikit-image gunicorn \
    && rm -rf $HOME/.cache/pip

RUN apt-get update && apt-get install -y \
    wget unzip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

RUN git clone https://github.com/roarmstrong/pywps src

ADD . .

WORKDIR src/pywps
RUN pip3 install -e . --no-deps
WORKDIR /code

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app