import altair
import xarray

from . import PolygonDrill, chart_dimensions, log_call

# Mangrove cover product version 3 (ga_ls_mangrove_cover_cyear_3) does not contain crs,resolution in its products def
# - https://cmi.ga.gov.au/data-products/dea/634/dea-mangrove-canopy-cover-landsat#processing = UTM, 30 m
# - https://cmi.ga.gov.au/data-products/dea/191/dea-mangrove-canopy-cover-landsat-deprecated#processing = Albers, 25 m
# Need to pass through load_hints (output_crs, resolution) to the geobox calculations
# 1. test_api calls .__init__.PolygonDrill.query_handler()
#    - query_handler accepts a "parameters" arg that could be used
# 2. query_handler calls self.input_data()
#    - the parameters arg is not passed in here but could be
# 3. input_data calls self.input.* = datacube.virtual.Product()
#    - https://github.com/opendatacube/datacube-core/blob/develop/datacube/virtual/impl.py#L313
#    - the Product() is created from datacube-wps-config.yaml by .impl.create_process(), which calls datacube.virtual.construct()
# 4. bag = self.input.query(...)
#    - {bag: [datacube.model.Dataset], geopolygon: query-poly, product_definitions: {product-name: datacube.model.Product}}
# 5. box = self.input.group(bag)
#    - {box: xarray.DataArray, geobox: None, load_natively: True, product_definitions: {product-name: datacube.model.Product}, geopolygon: query-poly}
#    - Product.group(..., group_settings: dict) could be used to pass in 'output_crs', 'resolution', 'align'
# Solution
# 1. In .__init__.PolygonDrill.input_data, check if the bag datasets have a grid_spec and if not
#    - get output_crs, resolution and/or align from datacube-wps-config.yaml
#    - if output_crs is None, calculate the most common CRS from the bag datasets
#    - call self.input.group(bag, output_crs, resolution, align)

class MangroveDrill(PolygonDrill):

    @log_call
    def process_data(self, data, parameters):
        data = data.compute()

        # TODO raise ProcessError('query returned no data') when appropriate
        woodland = data.where(data == 1).count(['x', 'y'])
        woodland = woodland.rename(name_dict={'canopy_cover_class': 'Woodland'})
        open_forest = data.where(data == 2).count(['x', 'y'])
        open_forest = open_forest.rename(name_dict={'canopy_cover_class': 'Open Forest'})
        closed_forest = data.where(data == 3).count(['x', 'y'])
        closed_forest = closed_forest.rename(name_dict={"canopy_cover_class": 'Closed Forest'})

        final = xarray.merge([woodland, open_forest, closed_forest])
        result = final.to_dataframe()
        result = result.drop('spatial_ref', axis=1)
        result.reset_index(inplace=True)
        return result

    @log_call
    def render_chart(self, df):
        width, height = chart_dimensions(self.style)

        melted = df.melt('time', var_name='Cover Type', value_name='Area')
        melted = melted.dropna()

        style = self.style['table']['columns']
        cover_types = ['Woodland', 'Open Forest', 'Closed Forest']

        chart = altair.Chart(melted,
                             width=width,
                             height=height,
                             title='Percentage of Area - Mangrove Canopy Cover')
        chart = chart.mark_area()
        chart = chart.encode(x='time:T',
                             y=altair.Y('Area:Q', stack='normalize'),
                             color=altair.Color('Cover Type:N',
                                                scale=altair.Scale(domain=cover_types,
                                                                   range=[style[ct]['chartLineColor']
                                                                          for ct in cover_types])),
                             tooltip=[altair.Tooltip(field='time', format='%d %B, %Y', title='Date', type='temporal'),
                                      'Area:Q',
                                      'Cover Type:N'])

        return chart

    @log_call
    def render_outputs(self, df, chart):
        return super().render_outputs(df, chart, is_enabled=True, name="Mangrove Cover",
                                      header=['Woodland', 'Open Forest', 'Closed Forest'])
