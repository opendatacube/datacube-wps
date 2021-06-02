from datetime import datetime, timezone

import numpy as np
import pandas as pd
import xarray as xr
from datacube.model import Measurement
from datacube.virtual.impl import Transformation
from datacube.virtual.transformations import ApplyMask

from . import PolygonDrill, geometry_mask

ls_timezone = timezone.utc


def ls8_on(dataset):
    LS8_START_DATE = datetime(2013, 1, 1, tzinfo=ls_timezone)
    return dataset.center_time >= LS8_START_DATE


def ls7_on(dataset):
    LS7_STOP_DATE = datetime(2003, 5, 31, tzinfo=ls_timezone)
    LS7_STOP_AGAIN = datetime(2013, 5, 31, tzinfo=ls_timezone)
    LS7_START_AGAIN = datetime(2010, 1, 1, tzinfo=ls_timezone)
    return dataset.center_time <= LS7_STOP_DATE or (dataset.center_time >= LS7_START_AGAIN
                                                    and dataset.center_time <= LS7_STOP_AGAIN)


def ls5_on_1ym(dataset):
    LS5_START_AGAIN = datetime(2003, 1, 1, tzinfo=ls_timezone)
    LS5_STOP_DATE = datetime(1999, 12, 31, tzinfo=ls_timezone)
    LS5_STOP_AGAIN = datetime(2011, 12, 31, tzinfo=ls_timezone)
    return dataset.center_time <= LS5_STOP_DATE or (dataset.center_time >= LS5_START_AGAIN
                                                    and dataset.center_time <= LS5_STOP_AGAIN)


class WIT(PolygonDrill):
    def __init__(self, about, input, style):
        super().__init__(about, input, style)
        self.mask_all_touched = True
        print("mask all touch", self.mask_all_touched)

    def process_data(self, data, parameters):
        feature = parameters.get('feature')
        adays = parameters.get('aggregate', 0)
        geomask = geometry_mask(feature, data.geobox, invert=True, all_touched=self.mask_all_touched)

        if adays > 0:
            aggregated = aggregate_over_time(data, adays)
        else:
            aggregated = data
        total_area = geomask.astype('int').sum()
        print("polygon area", total_area)
        re_wit = cal_area(aggregated)
        re_wit = re_wit[(re_wit['valid']/total_area) > 0.9].dropna()
        re_wit = re_wit.drop(columns=['valid']).div(re_wit['valid'], axis=0)
        re_wit['geometry'] = feature.geom.convex_hull.to_wkt()
        return re_wit

    def render_chart(self, df):
        pass


class TWnMask(Transformation):
    def __init__(self, category='wetness', coeffs=None):
        self.category = category
        if coeffs is None:
            self.coeffs = {
                 'brightness': {'blue': 0.2043, 'green': 0.4158, 'red': 0.5524, 'nir': 0.5741,
                                'swir1': 0.3124, 'swir2': 0.2303},
                 'greenness': {'blue': -0.1603, 'green': -0.2819, 'red': -0.4934, 'nir': 0.7940,
                               'swir1': -0.0002, 'swir2': -0.1446},
                 'wetness': {'blue': 0.0315, 'green': 0.2021, 'red': 0.3102, 'nir': 0.1594,
                             'swir1': -0.6806, 'swir2': -0.6109}
            }
        else:
            self.coeffs = coeffs
        self.var_name = f'TC{category[0].upper()}'

    def compute(self, data):
        tci_var = 0
        for key in self.coeffs[self.category].keys():
            nodata = getattr(data[key], 'nodata', -1)
            data[key] = data[key].where(data[key] > nodata)
            tci_var += data[key] * self.coeffs[self.category][key]
        tci_var.data[np.isnan(tci_var.data)] = -9999
        tci_var = tci_var.astype(np.float32)
        tci_var.attrs = dict(nodata=-9999, units=1, crs=data.attrs['crs'])
        tci_var = tci_var.to_dataset(name=self.var_name)

        def make_mask():
            water_value = (((data.water & (1 << 7)) != 0)
                           & (((data.water & (1 << 6)) | (data.water & (1 << 5)) | (data.water & (1 << 1))
                               | (data.water & 1)) == 0)).astype('int16')
            water_value.attrs = dict(nodata=0, units=1, crs=data.attrs['crs'])
            water_value = water_value.to_dataset(name='water')

            pmask = (((data.fmask != 2) & (data.fmask != 3) & (data.fmask != 0) & (data.nbart_contiguity == 1))
                     & (((data.water & (1 << 7)) | (data.water & (1 << 6)) | (data.water & (1 << 5))
                         | (data.water & (1 << 1)) | (data.water & 1)) == 0))
            pmask.attrs = dict(nodata=False, units=1, crs=data.attrs['crs'])
            pmask = pmask.to_dataset(name='pmask')
            return pmask.merge(water_value)
        pmask = tci_var.merge(make_mask())
        pmask.attrs = data.attrs
        return pmask

    def measurements(self, input_measurements):
        return {self.var_name: Measurement(name=self.var_name, dtype='float32', nodata=-9999, units='1'),
                'water': Measurement(name='water', dtype='int16', nodata=0, units='1'),
                'pmask': Measurement(name='pmask', dtype='bool', nodata=False, units='1')}


def mask_data(loaded):
    def make_mask():
        # water mask
        # flags = {'cloud': False,
        #    'cloud_shadow': False,
        #    'noncontiguous': False,
        #    'water_observed': False,
        #    'nodata': False
        #    }
        # water value
        # flags = {'cloud': False,
        #    'cloud_shadow': False,
        #    'noncontiguous': False,
        #    'water_observed': True,
        #    'nodata': False
        #    }
        water_value = (((loaded.water & (1 << 7)) != 0)
                       & (((loaded.water & (1 << 6)) | (loaded.water & (1 << 5)) | (loaded.water & (1 << 1))
                           | (loaded.water & 1)) == 0)).astype('int16').to_dataset(name='water')
        pmask = (((loaded.fmask != 2) & (loaded.fmask != 3) & (loaded.fmask != 0) & (loaded.nbart_contiguity == 1))
                 & (((loaded.water & (1 << 7)) | (loaded.water & (1 << 6)) | (loaded.water & (1 << 5))
                     | (loaded.water & (1 << 1)) | (loaded.water & 1)) == 0)).to_dataset(name='pmask')
        return pmask.merge(water_value)

    pmask = make_mask()
    loaded = loaded.drop(['fmask', 'nbart_contiguity', 'water']).merge(pmask)
    loaded = ApplyMask('pmask', apply_to=['bs', 'pv', 'npv', 'TCW']).compute(loaded)
    return loaded


def average_over_day(masked):
    tmp = xr.Dataset()
    for var in masked.data_vars:
        if var != 'water':
            valid_var = ~(np.abs(masked[var] - masked[var].attrs['nodata']) < 1e-5)
            # to suppress the warnings from dask if using `mean`
            # haven't got another way
            tmp[var] = ((masked[var].where(valid_var).sum('time', skipna=False, keep_attrs=True) / masked.time.shape[0])
                        .fillna(masked[var].attrs['nodata']).astype('float32'))
        else:
            tmp[var] = masked[var].astype('int16').sum('time', keep_attrs=True).astype('int16')
        tmp[var].attrs = masked[var].attrs

    tmp = tmp.expand_dims(time=masked.time[0:1], axis=0)
    tmp.attrs = masked.attrs
    return tmp


def aggregate_data(masked):
    tmp = masked[dict(time=[0])].copy(deep=True)
    for time in masked.time.data[1:]:
        for var in masked.data_vars:
            if var != 'water':
                valid_var = ~(np.abs(tmp[var] - masked[var].attrs['nodata']) < 1e-5) | tmp.water > 0
            else:
                valid_var = ~(np.abs(tmp.TCW - masked.TCW.attrs['nodata']) < 1e-5) | tmp.water > 0
            tmp[var] = tmp[var].where(valid_var, 0) + masked[var].sel(time=time).where(~valid_var, 0)
            tmp[var].attrs = masked[var].attrs
    return tmp


def aggregate_over_time(masked, days):
    i_start = 0
    i_end = i_start + 1
    aggregated = None
    print("aggregate over days", days)
    while i_end < masked.time.size:
        time = masked.time.data[i_start]
        while np.abs(time - masked.time.data[i_end]).astype('timedelta64[D]') < np.timedelta64(days, 'D'):
            i_end += 1
            if i_end >= masked.time.size:
                break
        if days > 1:
            tmp = aggregate_data(masked[dict(time=np.arange(i_start, i_end))])
        else:
            tmp = average_over_day(masked[dict(time=np.arange(i_start, i_end))])
        if aggregated is None:
            aggregated = tmp
        else:
            aggregated = xr.concat([aggregated, tmp], dim='time')
        i_start = i_end
        i_end = i_start + 1
    print("finish aggregating", datetime.now())
    return aggregated


def cal_area(aggregated, wet_threshold=-350):
    non_columns = ['spatial_ref']
    re = aggregated.water.sum(dim=['x', 'y']).load().to_dataframe(name='water').drop(columns=non_columns)
    valid = np.abs(aggregated.TCW - aggregated.TCW.attrs['nodata']) > 1e-5
    tcw = valid.astype('int').sum(dim=['x', 'y']).load().to_dataframe(name='tcw').drop(columns=non_columns)
    re.insert(0, 'valid', re['water'] + tcw['tcw'])
    re = pd.merge(re, ((aggregated.TCW > wet_threshold).astype('int')
                       .sum(dim=['x', 'y']).load().to_dataframe(name='wet').drop(columns=non_columns)),
                  on=['time'], how='inner')
    fc_com = ((aggregated[['bs', 'pv', 'npv']].where(((aggregated.TCW < wet_threshold) & valid), 0) / 100)
              .sum(dim=['x', 'y']).load())
    for var in fc_com.data_vars:
        re = pd.merge(re, fc_com[var].to_dataframe(name=var).drop(columns=non_columns), on=['time'], how='inner')
    return re
