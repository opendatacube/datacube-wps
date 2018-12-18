import pywps
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, Format, FORMATS
from osgeo import ogr
import json

import datacube
from datacube.utils import geometry

import rasterio.features

import csv
import io
import xarray

import boto3
import botocore
from botocore.client import Config
import pywps.configuration as config

from dateutil.parser import parse

def _uploadToS3(filename, data, mimetype):
    session = boto3.Session()
    bucket = config.get_config_value('s3', 'bucket')
    s3 = session.client('s3')
    s3.upload_fileobj(
        data,
        bucket,
        filename,
        ExtraArgs={
            'ACL':'public-read',
            'ContentType': mimetype
        }
    )
    # Create unsigned s3 client for determining public s3 url
    s3 = session.client('s3', config=Config(signature_version=botocore.UNSIGNED))
    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        ExpiresIn=0,
        Params={
            'Bucket': bucket,
            'Key': filename
        }
    )
    return url

# From https://stackoverflow.com/a/16353080
class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)

# Defines the format for the returned object
# in this case a JSON object containing a CSV
_json_format = Format('application/vnd.terriajs.catalog-member+json',
                     schema='https://tools.ietf.org/html/rfc7159',
                     encoding="utf-8")

def geometry_mask(geoms, src_crs, geobox, all_touched=False, invert=False):
    gs = [geometry.Geometry(geom, crs=datacube.utils.geometry.CRS(src_crs)).to_crs(geobox.crs) for geom in geoms]
    return rasterio.features.geometry_mask(gs,
                                           out_shape=geobox.shape,
                                           transform=geobox.affine,
                                           all_touched=all_touched,
                                           invert=invert)

def _getData(shape, product, crs, time=None, extra_query={}):
    with datacube.Datacube() as dc:
        dc_crs = datacube.utils.geometry.CRS(crs)
        g = geometry.Geometry(shape, crs=dc_crs)
        query = {
            'geopolygon': g
        }
        if time is not None:
            first, second = time;
            time = (first.strftime("%Y-%m-%d"), second.strftime("%Y-%m-%d"))
            query['time'] = time
        print("loading data!", query)
        data = dc.load(product=product, group_by='solar_day', **query, **extra_query)
        print("data load done!")
        return data

# Data is a list of Datasets (returned from dc.load and masked if polygons)
def _processData(data, **kwargs):
    data = data.mean(dim=('x','y'))

    output_json = json.dumps(output_obj, cls=DatetimeEncoder)

    output_str = output_json

    response.outputs['timeseries'].output_format = str(_json_format)
    response.outputs['timeseries'].data = output_str

    return data


# Product output JSON
def _createOutputJson(data, **kwargs):
  pass

def _datetimeExtractor(data):
  return parse(json.loads(data)["properties"]["timestamp"]["date-time"])

# GeometryDrill is the base class providing Datacube WPS functionality.
# It is a pywps Process class that has been extended to provide additional
# functionality specific to Datacube.
# In order to create a custom drill, GeometryDrill can be subclassed or
# passed arguments on construction to modify it's behavior.
class GeometryDrill(Process):

    def __init__(self, handler, identifier, title, abstract='', profile=[], metadata=[],
                 version='None', store_supported=False, status_supported=False,
                 products=[], output_name=None, geometry_type="polygon",
                 custom_outputs=None, custom_data_loader=None, mask=True):

        assert len(products) > 0
        assert geometry_type in [ "polygon", "point" ]
        inputs = [ComplexInput('geometry',
                               'Geometry',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://geojson.org/geojson-spec.html#' + geometry_type)
                                                 ]),
                  ComplexInput('start',
                               'Start Date',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://www.w3.org/TR/xmlschema-2/#dateTime')
                                                 ]),
                  ComplexInput('end',
                               'End date',
                               supported_formats=[
                                                    Format('application/vnd.geo+json', schema='http://www.w3.org/TR/xmlschema-2/#dateTime')
                                                 ])]
        if custom_outputs is None:
          outputs = [ComplexOutput('timeseries',
                                   'Timeseries Drill',
                                   supported_formats=[
                                                          _json_format
                                                     ],
                                   as_reference=False)]
        else:
          outputs = custom_outputs

        self.products = products
        self.custom_handler = handler
        self.output_name = output_name if output_name is not None else "default"
        self.geometry_type = geometry_type
        self.custom_outputs = custom_outputs
        self.data_loader = _getData if custom_data_loader is None else custom_data_loader
        self.do_mask = mask

        super(GeometryDrill, self).__init__(
            handler          = self._handler,
            identifier       = identifier,
            version          = version,
            title            = title,
            abstract         = abstract,
            inputs           = inputs,
            outputs          = outputs,
            store_supported  = store_supported,
            status_supported = status_supported)

    def _handler(self, request, response):
        # Create geometry
        stream       = request.inputs['geometry'][0].stream
        request_json = json.loads(stream.readline())
        time = (_datetimeExtractor(request.inputs['start'][0].data),
                _datetimeExtractor(request.inputs['end'][0].data))
        crs = None

        if hasattr(request_json, 'crs'):
            crs = request_json['crs']['properties']['name']

        features = request_json['features']
        if len(features) < 1:
            # Can't drill if there is no geometry
            raise pywps.InvalidParameterException()

        data = []
        for feature in features:
            geometry = feature['geometry']

            if crs is None and hasattr(feature, 'crs'):
                crs = feature['crs']['properties']['name']
            elif crs is None and not hasattr(feature, 'crs'):
                # Terria doesn't provide the CRS for the polygon
                # Must assume the crs according to spec
                # http://geojson.org/geojson-spec.html#coordinate-reference-system-objects
                crs = 'urn:ogc:def:crs:OGC:1.3:CRS84'
            # Can do custom loading of data here
            for p in self.products:
              product = p['name']
              query = p.get('additional_query', {})
              d = self.data_loader(
                geometry,
                product,
                crs,
                time,
                query)
              if (len(d) > 0):
                data.append(d)

        masked = []
        if self.geometry_type == 'point' or not self.do_mask:
          masked = data
        elif len(data) != 0:
            masked = []
            for d in data:
              mask = geometry_mask([f['geometry'] for f in features], crs, d.geobox, invert=True)
              for band in d.data_vars:
                try:
                    d[band] = d[band].where(mask, other=d[band].attrs['nodata'])
                except AttributeError:
                    d[band] = d[band].where(mask)
              masked.append(d)


        outputs = self.custom_handler(masked, process_id=self.uuid)
        for ident, output_value in outputs.items():
          if "data" in output_value:
            response.outputs[ident].data = output_value['data']
          if "output_format" in output_value:
            response.outputs[ident].output_format = output_value['output_format']
          if "url" in output_value:
            response.outputs[ident].url = output_value['url']
        return response

