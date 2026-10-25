"""Validated data contract; machine-readable errors, no persistence."""
import csv
from io import BytesIO,StringIO
import numpy as np
import pandas as pd
from automotive import PARAMETERS,SENSORS,CATALOG
MAX_BYTES=10*1024*1024
MAX_ROWS=100000
class DataError(ValueError):
    def __init__(self,code,**params):
        self.code,self.params=code,params
        from i18n import translate
        super().__init__(translate('es',code,**params))
def load_csv(content:bytes)->pd.DataFrame:
    if len(content)>MAX_BYTES:raise DataError('error_size')
    try:
        header=next(csv.reader(StringIO(content.decode('utf-8-sig'))),[])
        if len(header)!=len(set(header)):raise DataError('error_duplicate_columns')
        df=pd.read_csv(BytesIO(content),dtype=str,nrows=MAX_ROWS+1)
    except (UnicodeDecodeError,pd.errors.ParserError,pd.errors.EmptyDataError):raise DataError('error_format') from None
    if df.empty:raise DataError('error_empty')
    if len(df)>MAX_ROWS:raise DataError('error_rows')
    missing={'timestamp','asset_id'}-set(df)
    if missing:raise DataError('error_columns',columns=', '.join(sorted(missing)))
    sensors=[s for s in SENSORS if s in df]
    if not sensors:raise DataError('error_sensor')
    df.asset_id=df.asset_id.fillna('').str.strip()
    if df.asset_id.eq('').any():raise DataError('error_id')
    df.timestamp=pd.to_datetime(df.timestamp,format='ISO8601',utc=True,errors='coerce')
    if df.timestamp.isna().any():raise DataError('error_date')
    if df.duplicated(['asset_id','timestamp']).any():raise DataError('error_duplicates')
    warnings=[]
    for col in sensors+[c for c in ['operating_hours','odometer_km'] if c in df]:
        df[col]=pd.to_numeric(df[col],errors='coerce')
        if not np.isfinite(df[col].to_numpy(float)).all():raise DataError('error_numeric',column=col)
        rule=PARAMETERS.get(col,{'physical_min':0 if col in ['operating_hours','odometer_km','pressure_bar','vibration_mm_s'] else None,'physical_max':None})
        lo,hi=rule.get('physical_min'),rule.get('physical_max')
        bad=(df[col]<lo if lo is not None else pd.Series(False,index=df.index))|(df[col]>hi if hi is not None else False)
        if bad.any():raise DataError('error_physical',column=col,row=int(np.flatnonzero(bad)[0])+2)
        if col in PARAMETERS and ((df[col]<rule['plausible_min'])|(df[col]>rule['plausible_max'])).any():warnings.append(('plausibility',{'column':col}))
    for col,allowed in [('vehicle_type',CATALOG['vehicles']),('component',CATALOG['components'])]:
        if col in df:
            if not df[col].isin(allowed).all():raise DataError('error_category',column=col)
            if df.groupby('asset_id')[col].nunique().gt(1).any():raise DataError('error_identity',column=col)
    keep=set(SENSORS)|{'timestamp','asset_id','vehicle_type','component','operating_hours','odometer_km'}
    unknown=[c for c in df if c not in keep]
    if unknown:warnings.append(('ignored',{'columns':', '.join(unknown)}))
    result=df.drop(columns=unknown).sort_values(['asset_id','timestamp']).reset_index(drop=True)
    result.attrs['warnings']=warnings
    return result
