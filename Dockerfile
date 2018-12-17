FROM opendatacube/datacube-core:1.6.1

WORKDIR /code

ADD . .

RUN pip3 install -r requirements.txt \
    && rm -rf $HOME/.cache/pip

RUN pip3 install git+https://github.com/opendatacube/dea-proto.git@2da959d3747e4bb0db8025407220bb2589bbee10 --no-deps \
    && rm -rf $HOME/.cache/pip

WORKDIR /code/logs
WORKDIR /code

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app