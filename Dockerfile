FROM opendatacube/datacube-core:1.7

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium-browser \
    chromium-chromedriver \
    && rm -rf /var/lib/apt/lists/*

# include webdriver installed by apt in path
ENV PATH="/usr/lib/chromium-browser/:${PATH}"

ADD requirements.txt .

RUN pip3 install --upgrade pip \
    && rm -rf $HOME/.cache/pip

RUN pip3 install -r requirements.txt \
    && rm -rf $HOME/.cache/pip

RUN pip install -U 'aiobotocore[awscli,boto3]' \
    && rm -rf $HOME/.cache/pip

RUN pip3 install git+https://github.com/opendatacube/dea-proto.git@2da959d3747e4bb0db8025407220bb2589bbee10 --no-deps \
    && rm -rf $HOME/.cache/pip

#RUN pip install --extra-index-url="https://packages.dea.gadevs.ga" \
#    odc-apps-cloud \
#    odc-apps-dc-tools \
#    && rm -rf $HOME/.cache/pip

ADD . .

WORKDIR /code/logs
WORKDIR /code

COPY docker/credentials ~/.aws/credentials

COPY docker/config ~/.aws/config

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app
