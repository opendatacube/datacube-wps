FROM opendatacube/datacube-core:1.7

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium-browser \
    chromium-chromedriver \
    curl \
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


RUN pip install --extra-index-url="https://packages.dea.gadevs.ga" \
   odc-apps-cloud \
   odc-apps-dc-tools \
   && rm -rf $HOME/.cache/pip

ADD . .

WORKDIR /code/logs
WORKDIR /code

# COPY docker/credentials /root/.aws/credentials

# COPY docker/config /root/.aws/config

COPY docker/wps-entrypoint.sh /usr/local/bin/wps-entrypoint.sh

ENTRYPOINT ["wps-entrypoint.sh"]

CMD gunicorn -b 0.0.0.0:8000 wps:app
