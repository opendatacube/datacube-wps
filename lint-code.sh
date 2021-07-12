set -eu
set -x

isort --check --diff .
# Consider replacing pycodestyle with autopep8 or flake8
# See discussions here : https://github.com/pre-commit/pre-commit-hooks/issues/319
pycodestyle --max-line-length=120 datacube_wps tests
pylint -j 2 --reports no datacube_wps --disable=C,R,redefined-builtin,fixme,arguments-differ
bandit -s B101,B104 -r .

set +x
