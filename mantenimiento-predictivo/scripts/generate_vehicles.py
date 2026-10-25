"""Simplified synthetic fleet. All example limits are invented test fixtures."""
import numpy as np
import pandas as pd

def generate_fleet():
 rng=np.random.default_rng(84);n=2160;h=np.arange(n);frames=[];truth=[]
 specs=[('CAR-01','car','brakes','brake_pad_mm',10,-.0015,5,'below'),('VAN-01','van','electrical','battery_voltage_v',13.6,-.0005,12,'below'),('TRUCK-01','truck','cooling','coolant_temp_c',85,.008,110,'above'),('MOTO-01','motorcycle','tires','tire_pressure_bar',2.8,-.0003,2,'below'),('TRUCK-01','truck','exhaust','dpf_diff_pressure_kpa',2,.008,25,'above')]
 for asset,kind in [('CAR-01','car'),('VAN-01','van'),('TRUCK-01','truck'),('MOTO-01','motorcycle')]:
  f=pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=n,freq='h',tz='UTC'),'asset_id':asset,'vehicle_type':kind,'odometer_km':10000+h*20.,'operating_hours':1000+h*.6})
  for _,_,_,sensor,start,slope,_,_ in specs:
   values=start+rng.normal(0,abs(slope)*8,n)
   if any(s[0]==asset and s[3]==sensor for s in specs):values+=slope*h
   flags=np.zeros(n,bool)
   for point in [850,1400,1900]:values[point:point+2]+=max(abs(slope)*300,.1);flags[point:point+2]=True
   f[sensor]=values
   truth.append(pd.DataFrame({'timestamp':f.timestamp,'asset_id':asset,'sensor':sensor,'is_anomaly':flags}))
  frames.append(f)
 return pd.concat(frames,ignore_index=True),pd.concat(truth,ignore_index=True),specs
if __name__=='__main__':
 from pathlib import Path
 out=Path(__file__).resolve().parents[1]/'examples/vehicles';out.mkdir(exist_ok=True)
 d,l,_=generate_fleet();d.to_csv(out/'fleet.csv',index=False);l.to_csv(out/'truth.csv',index=False)
