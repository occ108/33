import unittest,string
from pathlib import Path
import pandas as pd
from automotive import CATALOG,PARAMETERS
from data_contract import load_csv,DataError
from i18n import LOCALES
class AutomotiveTests(unittest.TestCase):
 def test_catalog(self):
  for c in CATALOG['components'].values():
   self.assertEqual(set(c['name']),{'es','en','de'});self.assertEqual(set(c['description']),{'es','en','de'})
   self.assertTrue(set(c['parameters'])<=set(PARAMETERS));self.assertIsNone(c['reference_interval'])
  for col,p in PARAMETERS.items():
   self.assertTrue(p['unit']);self.assertIn(p['direction'],['above','below','both']);self.assertIsNone(p['alert'])
   self.assertIn(col,load_csv(f'timestamp,asset_id,{col}\n2026-01-01,A,{(p["plausible_min"]+p["plausible_max"])/2}\n'.encode()))
 def test_locale_keys_and_placeholders(self):
  for lang,values in LOCALES.items():
   self.assertEqual(set(values),set(LOCALES['es']))
   for key,value in values.items():
    fields=lambda s:{f for _,f,_,_ in string.Formatter().parse(s) if f}
    self.assertEqual(fields(value),fields(LOCALES['es'][key]),(lang,key))
 def test_reject_and_warn(self):
  with self.assertRaises(DataError):load_csv(b'timestamp,asset_id,oil_pressure_bar\n2026-01-01,A,-1\n')
  d=load_csv(b'timestamp,asset_id,engine_rpm,misc\n2026-01-01,A,20000,hello\n')
  self.assertNotIn('misc',d);self.assertEqual(len(d.attrs['warnings']),2)
 def test_below_and_kilometres(self):
  from vehicle_analysis import forecast_vehicle
  n=240
  d=pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=n,freq='h',tz='UTC'),'asset_id':'A','brake_pad_mm':10-pd.Series(range(n))*.01,'odometer_km':10000+pd.Series(range(n))*20})
  r=forecast_vehicle(d,'A','brake_pad_mm',5,'below','km')
  self.assertEqual(r.status,'estimated');self.assertLessEqual(r.operating_hours_low,r.operating_hours_at_threshold);self.assertGreater(r.operating_hours_at_threshold,d.odometer_km.iloc[-1])
 def test_language_precedence(self):
  from i18n import initial_language,number
  self.assertEqual(initial_language('de','en-US'),'de')
  self.assertEqual(initial_language(None,'en-US,en;q=0.9'),'en')
  self.assertEqual(initial_language(None,'xx'),'es')
  self.assertEqual(number(10000.5,'de'),'10.000,5')
 def test_constant_below_does_not_force_date(self):
  from vehicle_analysis import forecast_vehicle
  d=load_csv(('timestamp,asset_id,brake_pad_mm\n'+''.join(f'2026-01-{1+i//24:02d}T{i%24:02d}:00:00Z,A,8\n' for i in range(72))).encode())
  self.assertEqual(forecast_vehicle(d,'A','brake_pad_mm',5,'below','km').status,'no_degradation')
 def test_old_csv_retained(self):
  d=load_csv((Path(__file__).resolve().parents[1]/'examples/sensores_demo.csv').read_bytes())
  self.assertEqual(len(d),9);self.assertEqual(d.asset_id.nunique(),2)
