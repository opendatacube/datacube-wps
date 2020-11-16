#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset

# init datacube with only relevant products
datacube system init --no-default-types --no-init-users
datacube metadata add https://raw.githubusercontent.com/GeoscienceAustralia/dea-config/a4f39b485b33608a016032d9987251881fec4b6f/workspaces/sandbox-metadata.yaml
wget https://raw.githubusercontent.com/GeoscienceAustralia/dea-config/a4f39b485b33608a016032d9987251881fec4b6f/workspaces/sandbox-products.csv -O product_list.csv
tail -n+2 product_list.csv | grep 'wofs_albers\|ls._fc_albers\|mangrove_cover' | awk -F, '{print $2}' | xargs datacube -v product add
rm product_list.csv

# index mangrove cover datasets for tests
datacube dataset add --confirm-ignore-lineage \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2002/MANGROVE_COVER_3577_13_-17_20020101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2002/MANGROVE_COVER_3577_13_-16_20020101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2001/MANGROVE_COVER_3577_13_-17_20010101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2001/MANGROVE_COVER_3577_13_-16_20010101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2003/MANGROVE_COVER_3577_13_-17_20030101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2003/MANGROVE_COVER_3577_13_-16_20030101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2004/MANGROVE_COVER_3577_13_-17_20040101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2004/MANGROVE_COVER_3577_13_-16_20040101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2005/MANGROVE_COVER_3577_13_-17_20050101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2005/MANGROVE_COVER_3577_13_-16_20050101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-17/2000/MANGROVE_COVER_3577_13_-17_20000101.yaml' \
    's3://dea-public-data/mangrove_cover/v2.0.2/x_13/y_-16/2000/MANGROVE_COVER_3577_13_-16_20000101.yaml'

# index fc datasets for test case
datacube dataset add --confirm-ignore-lineage \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/04/02/LS8_OLI_FC_3577_13_-41_20190402000235.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/04/02/LS8_OLI_FC_3577_13_-40_20190402000235.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/03/17/LS8_OLI_FC_3577_13_-41_20190317000238.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/03/25/LS8_OLI_FC_3577_13_-40_20190325235626.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/05/04/LS8_OLI_FC_3577_13_-40_20190504000229.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/03/25/LS8_OLI_FC_3577_13_-41_20190325235626.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/04/10/LS8_OLI_FC_3577_13_-41_20190410235621.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/04/26/LS8_OLI_FC_3577_13_-41_20190426235616.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/05/28/LS8_OLI_FC_3577_13_-41_20190528235634.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/03/09/LS8_OLI_FC_3577_13_-41_20190309235630.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/05/20/LS8_OLI_FC_3577_13_-41_20190520000240.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/03/17/LS8_OLI_FC_3577_13_-40_20190317000238.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/04/18/LS8_OLI_FC_3577_13_-40_20190418000229.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/05/12/LS8_OLI_FC_3577_13_-41_20190512235625.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/05/28/LS8_OLI_FC_3577_13_-40_20190528235634.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/05/20/LS8_OLI_FC_3577_13_-40_20190520000240.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/04/18/LS8_OLI_FC_3577_13_-41_20190418000229.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/05/12/LS8_OLI_FC_3577_13_-40_20190512235625.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/04/10/LS8_OLI_FC_3577_13_-40_20190410235621.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/03/09/LS8_OLI_FC_3577_13_-40_20190309235630.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-41/2019/05/04/LS8_OLI_FC_3577_13_-41_20190504000229.yaml' \
    's3://dea-public-data/fractional-cover/fc/v2.2.1/ls8/x_13/y_-40/2019/04/26/LS8_OLI_FC_3577_13_-40_20190426235616.yaml'

datacube dataset add --confirm-ignore-lineage \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/04/26/LS_WATER_3577_13_-40_20190426235616000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/04/26/LS_WATER_3577_13_-41_20190426235616000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/03/17/LS_WATER_3577_13_-40_20190317000238500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/03/17/LS_WATER_3577_13_-41_20190317000238500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/03/25/LS_WATER_3577_13_-40_20190325235626000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/03/25/LS_WATER_3577_13_-41_20190325235626000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/04/02/LS_WATER_3577_13_-40_20190402000235000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/04/02/LS_WATER_3577_13_-41_20190402000235000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/04/18/LS_WATER_3577_13_-40_20190418000229500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/04/18/LS_WATER_3577_13_-41_20190418000229500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/05/20/LS_WATER_3577_13_-40_20190520000240000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/05/20/LS_WATER_3577_13_-41_20190520000240000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/04/10/LS_WATER_3577_13_-40_20190410235621500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/04/10/LS_WATER_3577_13_-41_20190410235621500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/03/08/LS_WATER_3577_13_-40_20190308235612000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/03/08/LS_WATER_3577_13_-41_20190308235612000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/05/04/LS_WATER_3577_13_-40_20190504000229500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/05/04/LS_WATER_3577_13_-41_20190504000229500000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/05/12/LS_WATER_3577_13_-40_20190512235625000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/05/12/LS_WATER_3577_13_-41_20190512235625000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/03/09/LS_WATER_3577_13_-40_20190309235630000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/03/09/LS_WATER_3577_13_-41_20190309235630000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-40/2019/05/28/LS_WATER_3577_13_-40_20190528235634000000.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_13/y_-41/2019/05/28/LS_WATER_3577_13_-41_20190528235634000000.yaml'


# index datasets for the wofs drill
datacube dataset add --confirm-ignore-lineage \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/02/18/LS_WATER_3577_4_-32_20000218003700000000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/01/01/LS_WATER_3577_4_-32_20000101003706500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/04/22/LS_WATER_3577_4_-32_20000422003636500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/10/15/LS_WATER_3577_4_-32_20001015003424500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/09/29/LS_WATER_3577_4_-32_20000929003445500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/02/02/LS_WATER_3577_4_-32_20000202003706500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/05/08/LS_WATER_3577_4_-32_20000508003628500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/05/24/LS_WATER_3577_4_-32_20000524003616500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/07/27/LS_WATER_3577_4_-32_20000727003530500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/08/12/LS_WATER_3577_4_-32_20000812003524000000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/11/16/LS_WATER_3577_4_-32_20001116003439500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/08/28/LS_WATER_3577_4_-32_20000828003515500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/10/31/LS_WATER_3577_4_-32_20001031003440500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/01/17/LS_WATER_3577_4_-32_20000117003706500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/12/18/LS_WATER_3577_4_-32_20001218003443500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/06/25/LS_WATER_3577_4_-32_20000625003603500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/07/11/LS_WATER_3577_4_-32_20000711003548500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/04/06/LS_WATER_3577_4_-32_20000406003644500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/12/02/LS_WATER_3577_4_-32_20001202003440500000_v1526711988.yaml' \
    's3://dea-public-data/WOfS/WOFLs/v2.1.5/combined/x_4/y_-32/2000/09/13/LS_WATER_3577_4_-32_20000913003457500000_v1526711988.yaml'

pytest tests/
