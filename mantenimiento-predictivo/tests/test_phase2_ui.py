import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
class InterfaceRegression(unittest.TestCase):
 def test_small_and_large_buttons(self):
  a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
  a.button(key='small_demo').click().run(timeout=30)
  self.assertEqual([m.value for m in a.metric],['9','2']);self.assertFalse(a.exception)
  a.button(key='demo').click().run(timeout=30)
  self.assertEqual(a.session_state.validated_data.asset_id.nunique(),4);self.assertFalse(a.exception)
 def test_language_preserves_data_and_results(self):
  a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
  a.button(key='demo').click().run(timeout=30)
  raw=a.session_state.content
  for lang in ['en','de','es']:
   a.radio(key='language_choice').set_value(lang).run(timeout=30)
   self.assertFalse(a.exception);self.assertEqual(raw,a.session_state.content)
   self.assertEqual(a.session_state.validated_data.asset_id.nunique(),4)
 def test_lower_threshold_and_locale_safety(self):
  from i18n import LOCALES
  a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
  a.button(key='demo').click().run(timeout=30)
  self.assertEqual(a.selectbox(key='sensor').value,'brake_pad_mm')
  next(x for x in a.checkbox if x.key.startswith('enabled:')).check().run(timeout=30)
  next(x for x in a.number_input if x.key.startswith('limit:')).set_value(5.).run(timeout=30)
  for lang in ['es','en','de']:
   a.radio(key='language_choice').set_value(lang).run(timeout=30)
   self.assertFalse(a.exception)
   self.assertTrue(any(LOCALES[lang]['critical']==w.value for w in a.warning))
   self.assertTrue(any(LOCALES[lang]['estimated']==m.value for m in a.markdown))
   self.assertEqual(next(x for x in a.number_input if x.key.startswith('limit:')).value,5.)
 def test_chart_sampling_regression(self):
  import numpy as np
  import pandas as pd
  from app import _chart_sample
  d=pd.DataFrame({'temperature_c__anomaly':np.zeros(10000,bool)})
  d.loc[[123,4567,9999],'temperature_c__anomaly']=True
  sample=_chart_sample(d,'temperature_c')
  self.assertLessEqual(len(sample),3000);self.assertEqual(sample.temperature_c__anomaly.sum(),3)
 def test_legacy_planner_freshness(self):
  from i18n import LOCALES
  a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
  a.button(key='small_demo').click().run(timeout=30)
  self.assertFalse(a.exception)
  self.assertTrue(a.dataframe[-1].value[LOCALES['es']['priority']].eq(LOCALES['es']['stale']).all())
