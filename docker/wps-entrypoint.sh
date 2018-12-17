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

docker-entrypoint.sh "$@"