"""Reproduce synthetic vehicle evaluation; no real-fleet accuracy claim."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scripts.generate_vehicles import generate_fleet
from analysis import analyze_anomalies
from vehicle_analysis import forecast_vehicle
x,y,specs=generate_fleet();out=analyze_anomalies(x).readings.set_index(['asset_id','timestamp'])
cutoff=pd.Timestamp(int(x.timestamp.min().value)+30*24*3600*10**9,tz='UTC')
y=y[y.timestamp>=cutoff].copy();y['predicted']=[bool(out.loc[(r.asset_id,r.timestamp),r.sensor+'__anomaly']) for r in y.itertuples()]
t=y.is_anomaly.to_numpy();p=y.predicted.to_numpy();tp=int((t&p).sum());fp=int((~t&p).sum());fn=int((t&~p).sum());delays=[];missed=0
for _,g in y[y.is_anomaly].groupby(['asset_id','sensor']):
 for _,event in g.groupby((g.timestamp.diff().dt.total_seconds().fillna(3600)>3600).cumsum()):
  hits=event[event.predicted]
  if hits.empty:missed+=1
  else:delays.append((int(hits.timestamp.min().value)-int(event.timestamp.min().value))/3.6e12)
f=[{'asset':a,'sensor':s,'direction':di,'status':(r:=forecast_vehicle(x,a,s,limit,di,'km')).status,'km':r.operating_hours_at_threshold,'low_km':r.operating_hours_low,'high_km':r.operating_hours_high} for a,_,_,s,_,_,limit,di in specs]
report={'seed':84,'split':'30 days initial reference; last60 days causal online test','tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp),'recall':tp/(tp+fn),'events_detected':len(delays),'events_missed':missed,'mean_delay_hours':float(np.mean(delays)),'forecasts':f,'limitations':'Synthetic spikes evaluated separately from gradual trends. Demonstration thresholds only; not OEM limits. Not real-failure validation.'}
Path('reports/automocion/evaluation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
