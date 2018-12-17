FROM opendatacube/datacube-core:latest

RUN apt-get update && apt-get install -y \
    wget unzip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

ADD . .

RUN pip3 install -r requirements.txt \
    && rm -rf $HOME/.cache/pip

WORKDIR /code/logs
WORKDIR /code

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app