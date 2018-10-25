# datacube-wps

Datacube Web Processing Service

* Free software: Apache Software License 2.0

## Flask Dev Server

Modify `pywps.cfg` to point `url` and `outputurl` to `localhost`. `workdir` and `outputpath` should be left as `tmp` and `outputs` respectively for a local dev server and `base_route` should be `/` see example:
```
url=http://localhost:5000
workdir=tmp
outputurl=http://localhost:5000/outputs/
outputpath=outputs
base_route=/
```

Once configured a local server can be run by exporting the `FLASK_APP` environment variable and running flask:

```bash
export FLASK_APP=wps.py
flask run
```

## Gunicorn
Assumes only a single instance of datacube-wps will be started. Multiple instances of datacube-wps will require a shared outputs folder between all instances.

* Define the service URL (e.g https://wps.services.dea.ga.gov.au)
* Modify `pywps.cfg`, in the example case:
```
url=https://wps.services.dea.ga.gov.au
outputurl=https://wps.services.dea.ga.gov.au/outputs/
```
* The wps can be started using gunicorn: `gunicorn -b 0.0.0.0:8000 wps:app`