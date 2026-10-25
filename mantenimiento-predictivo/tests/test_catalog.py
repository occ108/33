import unittest
import csv
import hashlib
from io import StringIO
from pathlib import Path
from streamlit.testing.v1 import AppTest
from catalog import load_catalog, search_catalog

class CatalogTests(unittest.TestCase):
    def test_provenance_and_scope(self):
        data=load_catalog()
        self.assertEqual(len(data['datasets']),6)
        self.assertEqual(len({d['id'] for d in data['datasets']}),6)
        for entry in data['datasets']:
            self.assertTrue(entry['url'].startswith('https://'))
            self.assertTrue(entry['evidence_url'].startswith('https://'))
            self.assertTrue(entry['adaptation'])
            self.assertFalse(entry['directly_compatible'])
        self.assertFalse(next(d for d in data['datasets'] if d['id']=='cwru')['license_verified'])

    def test_filters_and_empty_result(self):
        data=load_catalog()
        self.assertEqual([d['id'] for d in search_catalog(data,'MetroPT')],['metro'])
        self.assertEqual([d['id'] for d in search_catalog(data,equipment=['Rodamientos'])],['cwru'])
        self.assertEqual(search_catalog(data,'noexiste2345'),[])
        self.assertEqual(len(data['datasets']),6)

    def test_original_snapshot_integrity_and_size(self):
        snapshot=next(d for d in load_catalog()['datasets'] if d['id']=='ai4i')['snapshot']
        data=(Path(__file__).resolve().parents[1]/'resources'/snapshot['file']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),snapshot['sha256'])
        rows=list(csv.DictReader(StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(len(rows),10000)
        self.assertNotIn('timestamp',rows[0])

    def test_available_before_upload_and_searchable(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Case Western' in v.value for v in app.markdown))
        app.text_input(key='resource_search').set_value('MetroPT').run(timeout=30)
        self.assertEqual(len(app.exception),0)
        names='\n'.join(v.value for v in app.markdown)
        self.assertIn('MetroPT',names)
        self.assertNotIn('Case Western',names)
