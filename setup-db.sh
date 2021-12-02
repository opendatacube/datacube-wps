#!/bin/bash

# Run this script to initialise postgres database container with sample data.
# To regenerate from scratch (e.g. after collection changes), delete SQL dump file and re-run.

if [ ! -f dump.sql ]; then

   echo Rebuilding sample database..

   index="https://explorer-aws.dea.ga.gov.au"

   cmd='docker-compose exec -T wps datacube'

   $cmd system init --no-default-types --no-init-users

   for x in eo eo3 eo3_landsat_ard; do $cmd metadata add $index/metadata-types/$x.odc-type.yaml; done

   for x in ga_ls_wo_3 ga_ls8c_ard_3 ga_ls7e_ard_3 ga_ls5t_ard_3 ga_ls_fc_3 mangrove_cover; do $cmd product add $index/products/$x.odc-product.yaml; done

   stac () { curl -s "$index/stac/search?collections=$1&datetime=$2T00:00:00Z/$3T00:00:00Z&bbox=$4&limit=500" |
	     jq '.features[].links[] | select(.rel == "odc_yaml") | .href'; }

   {
       stac ga_ls_wo_3 2000-01-01 2001-01-01 "137.01,-28.76,137.02,-28.75"

       stac "ga_ls8c_ard_3,ga_ls7e_ard_3,ga_ls_fc_3,ga_ls_wo_3" 2019-03-01 2019-08-01 "146.65,-36.16,147.29,-35.66"

       #stac mangrove_cover 2000-01-01 2006-01-01 "143.98,-14.69,144.27,-14.39"

   } | xargs -L1 $cmd -v dataset add --confirm-ignore-lineage

   xargs -L1 -I{} docker-compose exec -T index s3-to-dc --skip-lineage --no-sign-request {} mangrove_cover << EOF
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2002/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2002/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2001/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2001/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2003/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2003/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2004/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2004/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2005/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2005/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2000/*.yaml'
   's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2000/*.yaml'
EOF
   ls # check dump.sql
   docker-compose exec -T -u postgres postgres pg_dump > dump.sql

else

   echo Reusing cache..

   docker-compose exec -T -u postgres postgres psql < dump.sql

fi
