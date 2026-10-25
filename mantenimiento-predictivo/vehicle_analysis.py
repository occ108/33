"""Directional threshold projections, retaining the industrial engine unchanged."""
from dataclasses import replace
import pandas as pd
from analysis import estimate_maintenance,ForecastConfig

def forecast_vehicle(df:pd.DataFrame,asset:str,sensor:str,limit:float|None,direction:str='above',metric:str='hours',config:ForecastConfig=ForecastConfig()):
    if direction not in ('above','below'):raise ValueError('direction')
    data=df.copy()
    if metric=='km':
        data=data.drop(columns='operating_hours',errors='ignore')
        if 'odometer_km' in data:data['operating_hours']=data.odometer_km
    elif metric!='hours':data=data.drop(columns='operating_hours',errors='ignore')
    if direction=='below':
        data[sensor]=-data[sensor]
        if limit is not None:limit=-limit
    result=estimate_maintenance(data,asset,sensor,limit,config)
    if direction=='below':
        result=replace(result,current_level=None if result.current_level is None else -result.current_level,slope_per_hour=None if result.slope_per_hour is None else -result.slope_per_hour,slope_low=None if result.slope_high is None else -result.slope_high,slope_high=None if result.slope_low is None else -result.slope_low)
    return result
