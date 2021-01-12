# datacube-wps
[![Scan](https://github.com/opendatacube/datacube-wps/workflows/Scan/badge.svg)](https://github.com/opendatacube/datacube-wps/actions?query=workflow%3AScan)
[![Linting](https://github.com/opendatacube/datacube-wps/workflows/Linting/badge.svg)](https://github.com/opendatacube/datacube-wps/actions?query=workflow%3ALinting)
[![Tests](https://github.com/opendatacube/datacube-wps/workflows/Tests/badge.svg)](https://github.com/opendatacube/datacube-wps/actions?query=workflow%3ATests)
[![Docker](https://github.com/opendatacube/datacube-wps/workflows/Docker/badge.svg)](https://github.com/opendatacube/datacube-wps/actions?query=workflow%3ADocker)
[![CoveCov](https://codecov.io/gh/opendatacube/datacube-wps/branch/master/graph/badge.svg)](https://codecov.io/gh/opendatacube/datacube-wps)

Datacube Web Processing Service

* Free software: Apache Software License 2.0

Datacube WPS is based on PYWPS (https://github.com/geopython/pywps) version 4.2.4

Available processes are below:
* FCDrill
* WOfSDrill

## Flask Dev Server

To run the WPS on localhost modify `pywps.cfg` to point `url` and `outputurl` to `localhost`. `workdir` and `outputpath` should be left as `tmp` and `outputs` respectively for a local dev server and `base_route` should be `/` see example:
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

## Changing Processes in WPS
The processes which are available to users of the WPS are enumerated in the `DEA_WPS_config.yaml` file.

### Resource allocation
The environment variable `DATACUBE_WPS_NUM_WORKERS` sets the number of workers (defaults to 4).

# WPS development testing from Web
## Workflow testing - from terria to wps service
1. Generate a specific terria catalog for wps terria testing http://terria-catalog-tool.dev.dea.ga.gov.au/wps
   - Enter the wps service url or leave default
   - Click Create Catalog button
   - verify the services listed in `json` format is correct
   - change file name if required or leave default
   - Click download catalog button to get a copy of the generated catalog
2. Go to http://terria-cube.terria.io/#clean, Add data
3. Select tab my data
4. Add local data and select the downloaded file

## Individual service debugging testing
### Collect payload
This part is flow-on from Workflow testing
1. Open DevToolsUI and go to `network` tab
2. Under `Data Catalogue` add the wps service needed for testing
3. Complete the Terria form and click Run Analysis button
4. The network will start to run
5. Click on Name = `?service=WPS&request=Execute` and open `Headers` tab
6. The following are used for testing with API tool
   - `xml` under Request Payload
   - `Request URL` under General
### Testing with web API tool
1. Go to http://www.apirequest.io/
2. URL = `request URL` from Collect payload point 6
3. Request body = `xml` from Collect payload point 6
