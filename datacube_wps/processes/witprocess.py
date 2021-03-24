from datacube.virtual.transformations import ApplyMask
import numpy as np
import xarray as xr
import pandas as pd
from . import geometry_mask, PolygonDrill

class WIT(PolygonDrill):
    def process_data(self, data, parameters):
        feature = parameters.get('feature')
        adays = parameters.get('aggregate', 0)
        geomask = geometry_mask(feature, data.geobox, invert=True)
        masked = mask_data(data)
        if adays > 0:
            aggregated = aggregate_over_time(masked, adays)
        else:
            aggregated = masked
        total_area = geomask.astype('int').sum()
        print("polygon area", total_area)
        re_wit = cal_area(aggregated) 
        print("wit in area", re_wit)
        re_wit = re_wit[(re_wit['valid']/total_area) > 0.9].dropna() / total_area
        return re_wit
    
    def render_chart(self, df):
        pass

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
        water_value = (((loaded.water & (1 << 7)) != 0) & (((loaded.water & (1 << 6)) | (loaded.water & (1 << 5)) | (loaded.water & (1 << 1)) | (loaded.water & 1)) == 0)).to_dataset(name='water')
        pmask = (((loaded.fmask != 2) & (loaded.fmask != 3) & (loaded.fmask != 0) & (loaded.nbart_contiguity == 1)) & (((loaded.water & (1 << 7)) | (loaded.water & (1 << 6)) | (loaded.water & (1 << 5)) | (loaded.water & (1 << 1)) | (loaded.water & 1)) == 0)).to_dataset(name='pmask')
        return pmask.merge(water_value)
        
    pmask = make_mask()
    loaded = loaded.drop(['fmask', 'nbart_contiguity', 'water']).merge(pmask)
    loaded = ApplyMask('pmask', apply_to=['bs', 'pv', 'npv', 'TCW']).compute(loaded)
    return loaded

def aggregate_data(masked):    
    tmp = masked[dict(time=[0])].copy(deep=True)
    for time in masked.time.data[1:]:
        for var in masked.data_vars:
            if var != 'water':
                valid_var = ~(np.abs(tmp[var] - masked[var].attrs['nodata']) < 1e-5) | tmp.water
                tmp[var] = (tmp[var].where(valid_var, 0) 
                        + masked[var].sel(time=time).where(~valid_var, 0))
            else:
                valid_water = ~(np.abs(tmp.TCW - masked.TCW.attrs['nodata']) < 1e-5) | tmp.water
                tmp['water'] = tmp.water.where(valid_water, False) | masked.water.sel(time=time).where(~valid_water, False)
            tmp[var].attrs = masked[var].attrs
    return tmp

def aggregate_over_time(masked, days):
    i_start = 0
    i_end = i_start + 1
    aggregated = None
    while i_end < masked.time.size:
        time = masked.time.data[i_start]
        while (np.abs(time - masked.time.data[i_end]).astype('timedelta64[D]')
                                                 < np.timedelta64(days, 'D')):
            i_end += 1
            if i_end >= masked.time.size:
                break
        print("aggregate over", masked.time.data[np.arange(i_start, i_end)])
        tmp = aggregate_data(masked[dict(time=np.arange(i_start, i_end))])
        if aggregated is None:
            aggregated = tmp
        else:
            aggregated = xr.concat([aggregated, tmp], dim='time')
        i_start = i_end
        i_end = i_start + 1
    return aggregated

def cal_area(aggregated, wet_threshold=-350):
    non_columns = ['spatial_ref']
    re = aggregated.water.astype('int').sum(dim=['x', 'y']).load().to_dataframe(name='water').drop(columns=non_columns)
    valid = np.abs(aggregated.TCW - aggregated.TCW.attrs['nodata']) > 1e-5
    tcw = valid.astype('int').sum(dim=['x', 'y']).load().to_dataframe(name='tcw').drop(columns=non_columns)
    re.insert(0, 'valid', re['water'] + tcw['tcw'])
    re = pd.merge(re, (aggregated.TCW > wet_threshold).astype('int').sum(dim=['x', 'y']).load().to_dataframe(name='wet').drop(columns=non_columns),
                  on=['time'], how='inner')
    fc_com = (aggregated[['bs', 'pv', 'npv']].where(((aggregated.TCW < wet_threshold) & valid), 0) / 100).sum(dim=['x', 'y']).load()
    for var in fc_com.data_vars:
        re = pd.merge(re, fc_com[var].to_dataframe(name=var).drop(columns=non_columns), on=['time'], how='inner')
    return re