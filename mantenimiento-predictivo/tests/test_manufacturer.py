import copy
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from manufacturer import REFERENCES,compare_measurements
from automotive import PARAMETERS
PROJECT=Path(__file__).resolve().parents[1]

class ManufacturerTests(unittest.TestCase):
 def setUp(self):
  self.identity=dict(make='Tesla',model='Model 3',year=2024,market='US',vehicle_type='car',confirmed=True)
 def test_scoping_no_cross_model_fallback(self):
  for changes in [dict(model='Corolla'),dict(make='Toyota'),dict(year=2023),dict(year=2027),dict(market='other'),dict(confirmed=False),dict(vehicle_type='truck')]:
   with self.subTest(changes=changes):
    self.assertIsNone(compare_measurements(self.identity|changes,{'tire_tread_mm':2},'wet')[0]['reference'])
  self.assertIsNone(compare_measurements(self.identity,{'tire_tread_mm':2},'unknown')[0]['reference'])
  self.assertIsNone(compare_measurements(self.identity,{'oil_pressure_bar':2},'wet')[0]['reference'])
 def test_condition_and_boundary(self):
  for value,condition,status in [(2.9,'wet','manual_review'),(3.,'wet','manual_not_below'),(3.5,'wet','manual_not_below'),(3.5,'winter','manual_review'),(4.,'winter','manual_not_below')]:
   with self.subTest(value=value,condition=condition):self.assertEqual(compare_measurements(self.identity,{'tire_tread_mm':value},condition)[0]['status'],status)
 def test_invalid_values(self):
  for value in [-1,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):compare_measurements(self.identity,{'tire_tread_mm':value},'wet')
 def test_reference_integrity(self):
  self.assertEqual(len({r['id'] for r in REFERENCES}),len(REFERENCES))
  self.assertEqual(len({r['model'] for r in REFERENCES}),4)
  for r in REFERENCES:
   self.assertTrue(r['source_url'].startswith('https://www.tesla.com/ownersmanual/'))
   self.assertEqual(r['unit'],PARAMETERS[r['parameter']]['unit'])
   self.assertEqual(len(r['source_sha256']),64)
   self.assertTrue(r['quote']);self.assertTrue(r['checked_at']);self.assertLessEqual(r['year_min'],r['year_max'])

class ManualEntryTests(unittest.TestCase):
 def app(self):return AppTest.from_file(str(PROJECT/'app.py')).run(timeout=30)
 def submit(self,a):
  a.selectbox(key='component').select('tires').run(timeout=30)
  a.text_input(key='manual_make').set_value('Tesla')
  a.text_input(key='manual_model').set_value('Model 3')
  a.text_input(key='manual_version').set_value('2024+ generation')
  a.radio(key='manual_market').set_value('US')
  a.checkbox(key='manual_confirm').check()
  a.radio(key='manual_conditions').set_value('wet')
  a.number_input(key='reading:tire_tread_mm').set_value(2.5)
  next(b for b in a.button if b.key.startswith('FormSubmitter:')).click().run(timeout=30)
 def test_form_comparison_no_upload_and_language_preservation(self):
  a=self.app()
  self.assertFalse(a.get('file_uploader'))
  self.submit(a)
  self.assertFalse(a.exception)
  self.assertEqual(a.session_state.manual_snapshot['results'][0]['status'],'manual_review')
  for lang in ['en','de','es']:
   a.radio(key='language_choice').set_value(lang).run(timeout=30)
   self.assertFalse(a.exception)
   self.assertEqual(a.selectbox(key='component').value,'tires')
   self.assertEqual(a.radio(key='manual_market').value,'US')
   self.assertEqual(a.radio(key='manual_conditions').value,'wet')
   self.assertEqual(a.number_input(key='reading:tire_tread_mm').value,2.5)
   self.assertEqual(a.session_state.manual_snapshot['results'][0]['status'],'manual_review')
 def test_required_fields(self):
  a=self.app()
  next(b for b in a.button if b.key.startswith('FormSubmitter:')).click().run(timeout=30)
  self.assertTrue(a.error);self.assertFalse(a.exception)
  self.assertNotIn('manual_snapshot',a.session_state)
 def test_missing_reference_and_impossible_value(self):
  a=self.app();self.submit(a)
  a.text_input(key='manual_make').set_value('Toyota')
  next(b for b in a.button if b.key.startswith('FormSubmitter:')).click().run(timeout=30)
  self.assertEqual(a.session_state.manual_snapshot['results'][0]['status'],'manual_no_reference')
  a.number_input(key='reading:tire_tread_mm').set_value(-1.)
  next(b for b in a.button if b.key.startswith('FormSubmitter:')).click().run(timeout=30)
  self.assertTrue(a.error);self.assertNotIn('manual_snapshot',a.session_state)
