#!/usr/bin/env bash
set -e

if [ "$WPS_CONFIG_URL" ]
then
    A=$$; ( wget -q "$WPS_CONFIG_URL" -O $A.d && mv $A.d /code/pywps.cfg ) || (rm $A.d; echo "Failed to download WMS config file")
fi

docker-entrypoint.sh "$@"