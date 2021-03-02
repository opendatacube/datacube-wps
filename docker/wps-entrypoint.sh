#!/usr/bin/env bash
set -e

set -e

if [ -e "$WPS_CONFIG_PATH" ]
then
    cp "$WPS_CONFIG_PATH" /code/pywps.cfg
elif [ "$WPS_CONFIG_URL" ]
then
    A=$$; wget -q "$WPS_CONFIG_URL" -O $A.d && mv $A.d /code/pywps.cfg
fi

if [ -e "$DATACUBE_WPS_CONFIG_PATH" ]
then
    cp "$DATACUBE_WPS_CONFIG_PATH" /code/datacube-wps-config.yaml
elif [ "$DATACUBE_WPS_CONFIG_URL" ]
then
    A=$$; wget -q "$DATACUBE_WPS_CONFIG_URL" -O $A.d && mv $A.d /code/datacube-wps-config.yaml
fi

# pywps -c pywps.cfg migrate

# create aws credential in /root/.aws/credentials
# echo "[default]" >> /root/.aws/credentials
# echo "aws_access_key_id=$AWS_ACCESS_KEY_ID" >> /root/.aws/credentials
# echo "aws_secret_access_key=$AWS_SECRET_ACCESS_KEY" >> /root/.aws/credentials
exec "$@"
