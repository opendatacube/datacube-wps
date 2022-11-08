#!/bin/bash

# Run this script to initialise postgres database container with sample data.
# To regenerate from scratch (e.g. after collection changes), delete SQL dump file and re-run.

if [ ! -f dump.sql ]; then

   echo Rebuilding sample database..

   index="https://explorer.csiro.easi-eo.solutions"

   cmd='docker-compose exec -T wps datacube'

   $cmd system init --no-default-types --no-init-users

   for x in eo eo3 eo3_landsat_ard; do $cmd metadata add $index/metadata-types/$x.odc-type.yaml; done

   for x in ga_ls8c_ard_3 ga_ls7e_ard_3 ga_ls5t_ard_3 ga_ls_mangrove_cover_cyear_3 ga_ls_fc_3 ga_ls_wo_3; do $cmd product add $index/products/$x.odc-product.yaml; done

   stac () { curl -s "$index/stac/search?collections=$1&datetime=$2T00:00:00Z/$3T00:00:00Z&bbox=$4&limit=500" |
	     jq '.features[].links[] | select(.rel == "odc_yaml") | .href'; }

   {
       stac "ga_ls8c_ard_3,ga_ls7e_ard_3,ga_ls5t_ard_3,ga_ls_mangrove_cover_cyear_3,ga_ls_fc_3,ga_ls_wo_3" 2019-01-01 2019-04-01 "152.95,-27.5,153.55,-27"  # Brisbane

   } | xargs -L1 $cmd -v dataset add --confirm-ignore-lineage

   docker-compose exec -T -u postgres postgres pg_dump > dump.sql

else

   echo Reusing cache..

   docker-compose exec -T -u postgres postgres psql < dump.sql

fi
