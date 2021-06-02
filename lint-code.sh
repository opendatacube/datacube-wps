set -eu
set -x

isort --check --diff .
pycodestyle --max-line-length=120 datacube_wps tests
pylint -j 2 --reports no datacube_wps --disable=C,R,redefined-builtin,fixme,arguments-differ
bandit -s B101,B104 -r .

set +x
