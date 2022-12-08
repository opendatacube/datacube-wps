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

### State of play (08/12/2022)
- EASI WPS can currently run:
 - Mangrove polygon drill: Calculate number of Woodland, Open Forest and Closed Forest pixels in a polygon
 - Fractional Cover (FC) polygon drill: Calculate proportion of bare soil, photosynthetic vegetation and non-photosynthetic vegetation within a polygon.
 - Water Observations From Space (WOFS) pixel drill: Produce water observations for a point through time as a graph.
- Want to be able to handle Geopolygon, Geomultipolygons and shapefiles (from which we extract polygons) - can currently handle polygons.

- Some considerations when working with the raster data:
 - Statistics to be applied to the polygon (mean, std etc.)
 - Handling of partial pixels - what happens when a polygon straddles an edge or is partially outside of one (exclude? include? more than 50%? less than 50%?)
 - the kind of band math we can do (functions) e.g. fractional cover - bare, dry, veg; total cover, optionally combine with rainfall...

- Next tasks:
 - Deploying in EASI
 - Connect input requests and output results to Terria
 - Test


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

## API
### GetCapabilities
- Returns configured operations and processes in XML format.
- Currently, operations include **GetCapabilities**, **DescribeProcess** and **Execute**. Processes include **Fractional Cover Drill**, **Mangrove Cover Drill** and **WIT polygon drill**
- Locally accessed via http://localhost:8000/?service=WPS&request=GetCapabilities&version=1.0.0

### DescribeProcess
- Returns a description of a configured process in XML format (accepted input formats, data types etc.)
- Returned XML provides framework for input data to execute described process.
- Locally accessed via http://localhost:8000/?service=WPS&version=1.0.0&request=DescribeProcess&identifier=&lt;PROCESS NAME&gt;

### Execute
- Runs a specified process.
- Inputs depend on process configuration.
- Request can be made as either a GET URL or a POST with an XML request document.
- Sendings requests with XML request documents are preferred for tidiness.
- POSTs can be constructed with assistance from Postman standalone app, Postman Chrome browser extension, Firefox Developer Tools or equivalent tools.
- Example of a CURL call:

curl -H "Content-Type: text/xml" -d @wpsrequest.xml -X POST localhost:8000?service=WPS&request=Execute

- Example of an XML request document for a buffer process (not implemented in this repository):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wps:Execute version="1.0.0" service="WPS" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.opengis.net/wps/1.0.0" xmlns:wfs="http://www.opengis.net/wfs" xmlns:wps="http://www.opengis.net/wps/1.0.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:gml="http://www.opengis.net/gml" xmlns:ogc="http://www.opengis.net/ogc" xmlns:wcs="http://www.opengis.net/wcs/1.1.1" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://www.opengis.net/wps/1.0.0 http://schemas.opengis.net/wps/1.0.0/wpsAll.xsd">
  <ows:Identifier>JTS:buffer</ows:Identifier>
  <wps:DataInputs>
    <wps:Input>
      <ows:Identifier>geom</ows:Identifier>
      <wps:Data>
        <wps:ComplexData mimeType="application/wkt"><![CDATA[POINT(0 0)]]></wps:ComplexData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>distance</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>10</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>quadrantSegments</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>1</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>capStyle</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>flat</wps:LiteralData>
      </wps:Data>
    </wps:Input>
  </wps:DataInputs>
  <wps:ResponseForm>
    <wps:RawDataOutput mimeType="application/gml-3.1.1">
      <ows:Identifier>result</ows:Identifier>
    </wps:RawDataOutput>
  </wps:ResponseForm>
</wps:Execute>
```

- See `./example_mangrove_drill.xml` for an example for an implemented process
