set -eu
set -x

pylint -j 2 --reports no datacube_wps --disable=C,R,redefined-builtin,fixme,arguments-differ

set +x
