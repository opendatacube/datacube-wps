import xarray
import altair
from . import PolygonDrill, log_call, chart_dimensions


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
