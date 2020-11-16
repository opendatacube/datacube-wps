#!/bin/bash
datacube system init --no-default-types --no-init-users
datacube metadata add "$METADATA_CATALOG"
wget "$PRODUCT_CATALOG" -O product_list.csv
tail -n+2 product_list.csv | awk -F, '{print $2}' | xargs datacube -v product add
rm product_list.csv

datacube product list
