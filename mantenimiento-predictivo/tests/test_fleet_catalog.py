import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from fleet_catalog import (load_bundle,validate_bundle,eligibility,build_database,read_database,summary,lookup_thresholds,CatalogError)
ROOT=Path(__file__).resolve().parents[1]

class FleetCatalogTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.bundle=load_bundle()
 def data(self):return copy.deepcopy(self.bundle)
 def test_three_model_bundle_and_release_gates(self):
  import subprocess,sys
  sample=load_bundle(ROOT/'examples/fleet2025_three_models.json');validate_bundle(sample)
  self.assertEqual(len(sample['models']),3)
  for profile,status in [('preview',0),('diagnostic',2)]:
   proc=subprocess.run([sys.executable,str(ROOT/'scripts/check_fleet_release.py'),'--profile',profile],capture_output=True,text=True,check=False)
   self.assertEqual(proc.returncode,status,proc.stderr)
   result=json.loads(proc.stdout)
   self.assertEqual(result['coverage']['eligible_models'],14)
   if profile=='diagnostic':self.assertIn('no_verified_oem_thresholds',result['blockers'])
 def test_strict_eligibility(self):
  sale=self.bundle['sales'][0]
  for n,expected in [(49,False),(50,False),(51,True)]:self.assertEqual(eligibility(sale|{'units':n},'2026-10-26')[0],expected)
  for edit in [dict(year=2024),dict(metric='registrations'),dict(metric='deliveries'),dict(geography_status='mixed_region'),dict(market='GLOBAL'),dict(identity_scope='family'),dict(verification='pending'),dict(period_start='2025-02-01')]:
   with self.subTest(edit=edit):self.assertFalse(eligibility(sale|edit,'2026-10-26')[0])
  self.assertFalse(eligibility(sale,'2027-01-01')[0])
 def test_examples_do_not_fabricate_oem_coverage(self):
  validate_bundle(self.bundle)
  self.assertEqual(len(self.bundle['models']),14)
  self.assertEqual({m['id'] for m in self.bundle['models']} >= {'renault-clio-5','renault-kangoo-van','subaru-forester'},True)
  self.assertTrue(all(r['lower'] is None and r['upper'] is None and r['status']=='missing_oem' for r in self.bundle['thresholds']))
  self.assertTrue(all(v['model_year'] is None and v['engine_code'] is None and v['verification']=='pending' for v in self.bundle['variants']))
  for variant in self.bundle['variants']:
   self.assertEqual({r['fault_id'] for r in self.bundle['coverage'] if r['variant_id']==variant['id']},{'mechanical','electrical','thermal','predictive','dtc'})
  self.assertTrue(all(not row['dtc_ids'] for row in self.bundle['coverage']))
  self.assertEqual({r['definition_kind'] for r in self.bundle['dtcs']},{'regulatory_category'})
 def test_schema_rejects_extra_fields_or_bad_dtc(self):
  for mutate in [lambda b:b.update(secret='never allowed'),lambda b:b['dtcs'][0].update(code='P9999'),lambda b:b['sales'][0].update(units=51.5)]:
   b=self.data();mutate(b)
   with self.assertRaises(CatalogError):validate_bundle(b)
 def test_duplicate_ids_and_orphans(self):
  b=self.data();b['models'].append(b['models'][0])
  with self.assertRaisesRegex(CatalogError,'duplicate_id'):validate_bundle(b)
  b=self.data();b['coverage'][0]['parameters']=['missing']
  with self.assertRaisesRegex(CatalogError,'foreign_key'):validate_bundle(b)
 def test_units_and_unverified_numbers_rejected(self):
  for edit,reason in [(dict(unit='psi'),'unit_mismatch'),(dict(lower=1.),'unverified_numeric_limit'),(dict(lower=float('inf')),'nonfinite_limit'),(dict(lower=9.,upper=1.),'invalid_limits')]:
   b=self.data();b['thresholds'][0].update(edit)
   with self.subTest(edit=edit),self.assertRaisesRegex(CatalogError,reason):validate_bundle(b)
 def test_no_regulatory_dtc_model_link(self):
  b=self.data();b['coverage'][0]['dtc_ids']=[b['dtcs'][0]['id']]
  with self.assertRaisesRegex(CatalogError,'unverified_dtc_link'):validate_bundle(b)
 def test_strict_json_and_benchmark_guard(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'bad.json'
   for text in ['{"a":1,"a":2}','{"a":NaN}']:
    path.write_text(text)
    with self.assertRaises(CatalogError):load_bundle(path)
  b=self.data();b['dataset_kind']='benchmark'
  with self.assertRaisesRegex(CatalogError,'benchmark_not_publishable'):validate_bundle(b)
 def test_atomic_import_integrity_idempotence_and_readonly(self):
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/'catalog.sqlite';first=build_database(self.bundle,target);raw=target.read_bytes()
   b=self.data();bad=dict(b['models'][0]);bad['id']='duplicate-business-key';b['models'].append(bad)
   # JSON-valid and FK-valid, but SQL unique business identity fails mid-import.
   with self.assertRaises(sqlite3.IntegrityError):build_database(b,target)
   self.assertEqual(raw,target.read_bytes());self.assertEqual(list(Path(folder).glob('.catalog-*')),[])
   self.assertEqual(build_database(self.bundle,target),first)
   self.assertEqual(first['eligible_models'],14);self.assertEqual(first['verified_thresholds'],0)
   with read_database(target) as db:
    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
    with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM model')
   self.assertIsNone(lookup_thresholds("x' OR 1=1 --",'engine_rpm','unknown','2026-10-26',target))
 def fixture(self):
  b=self.data();b['dataset_kind']='benchmark'
  source=b['sources'][0];source.update(source_kind='oem_technical',reuse='licensed',license='TEST FIXTURE ONLY',redistribution_allowed=True)
  # Sales retain their actual sales source; create a separate synthetic OEM source.
  s=copy.deepcopy(source);s['id']='test-oem';source.update(source_kind='sales',reuse='citation_only',license=None,redistribution_allowed=False);b['sources'].append(s)
  v=b['variants'][0];v.update(verification='verified',market='FR',model_year=2025,variant_code='TEST-VARIANT',generation='TEST-GENERATION',source_id=s['id'])
  r=b['thresholds'][0];r.update(status='verified',source_id=s['id'],lower=100.,upper=9000.,condition='TEST-CONDITION',valid_until='2027-12-31')
  return b,v,r
 def test_exact_scoped_lookup_and_stale_sales(self):
  b,v,r=self.fixture()
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'catalog.sqlite';build_database(b,path,allow_benchmark=True)
   self.assertEqual(lookup_thresholds(v['id'],r['parameter_id'],'TEST-CONDITION','2026-10-26',path)['id'],r['id'])
   for vid,condition,date in [('wrong','TEST-CONDITION','2026-10-26'),(v['id'],'wrong','2026-10-26'),(v['id'],'TEST-CONDITION','2025-10-26'),(v['id'],'TEST-CONDITION','2027-10-26')]:
    self.assertIsNone(lookup_thresholds(vid,r['parameter_id'],condition,date,path))
 def test_duplicate_columns_nonfinite_metadata_and_rights(self):
  b=self.data();b['parameters'][1]['column']=b['parameters'][0]['column']
  with self.assertRaisesRegex(CatalogError,'duplicate_parameter_column'):validate_bundle(b)
  b=self.data();b['parameters'][0]['physical_min']=-float('inf')
  with self.assertRaisesRegex(CatalogError,'nonfinite_physical_range'):validate_bundle(b)
  b,v,r=self.fixture();b['sources'][-1].update(reuse='citation_only',license=None)
  with self.assertRaisesRegex(CatalogError,'redistribution_rights_missing'):validate_bundle(b,allow_benchmark=True)
  b,v,r=self.fixture();v['market']='JP'
  with self.assertRaisesRegex(CatalogError,'variant_market_unverified'):validate_bundle(b,allow_benchmark=True)
 def test_manufacturer_dtc_cannot_cross_make(self):
  b,v,r=self.fixture()
  code=b['dtcs'][0];code.update(code='P1234',namespace='manufacturer',make='Toyota',ecu='TEST-ECU',definition_kind='oem_definition',source_id='test-oem')
  coverage=b['coverage'][0];coverage.update(status='documented',source_id='test-oem',dtc_ids=[code['id']])
  with self.assertRaisesRegex(CatalogError,'cross_make_dtc'):validate_bundle(b,allow_benchmark=True)
  code['make']='Renault';validate_bundle(b,allow_benchmark=True)
 def test_overlapping_or_unauthorized_thresholds_blocked(self):
  b,v,r=self.fixture();duplicate=copy.deepcopy(r);duplicate['id']='overlap';b['thresholds'].append(duplicate)
  with self.assertRaisesRegex(CatalogError,'ambiguous_threshold'):validate_bundle(b,allow_benchmark=True)
  b,v,r=self.fixture();b['sources'][-1]['redistribution_allowed']=False
  with self.assertRaisesRegex(CatalogError,'threshold_reuse_not_permitted'):validate_bundle(b,allow_benchmark=True)

class FleetResourcesTests(unittest.TestCase):
 def test_unavailable_catalogue_preserves_primary_form(self):
  from unittest.mock import patch
  with patch('fleet_resources.summary',side_effect=sqlite3.DatabaseError('internal detail must stay hidden')):
   app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
   self.assertFalse(app.exception)
   self.assertTrue(any('temporalmente' in w.value for w in app.warning))
   self.assertTrue(any(b.label=='Comprobar mediciones' for b in app.button))

 def test_three_languages_disclose_coverage_without_upload(self):
  from i18n import LOCALES
  app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
  for lang in ['es','en','de']:
   app.radio(key='language_choice').set_value(lang).run(timeout=30)
   self.assertFalse(app.exception);self.assertFalse(app.get('file_uploader'))
   self.assertTrue(any(LOCALES[lang]['fleet_boundary']==v.value for v in app.info))
   text='\n'.join(v.value for v in app.markdown)
   self.assertTrue(any('24.405' in v.value and LOCALES[lang]['fleet_france'] in v.value for v in app.caption) if lang!='en' else any('24,405' in v.value and 'France' in v.value for v in app.caption))
   for name in ['Renault Clio 5','Renault Kangoo VAN','Subaru Forester']:self.assertIn(name,text)
