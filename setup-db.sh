#!/bin/bash
docker-compose exec -T index datacube system init --no-default-types --no-init-users
docker-compose exec -T index datacube metadata add "$METADATA_CATALOG"
docker-compose exec -T index wget "$PRODUCT_CATALOG" -O product_list.csv
docker-compose exec -T index bash -c "tail -n+2 product_list.csv | grep 'wofs_albers\|ls._fc_albers\|mangrove_cover\|ga_ls_fc_3\|ga_ls_wo_3\|ga_ls8c_ard_3\|ga_ls7e_ard_3\|ga_ls5t_ard_3' | awk -F , '{print \$2}' | xargs datacube -v product add"

cat populate-db.sh | docker-compose exec -T index bash
