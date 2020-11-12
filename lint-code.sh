set -eu
set -x

pylint -j 2 --reports no datacube_wps --disable=C,R

set +x