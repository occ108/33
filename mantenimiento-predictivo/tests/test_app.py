import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from app import EXAMPLE, load_csv


class CSVTests(unittest.TestCase):
    def test_example_and_single_sensor(self):
        data = load_csv(EXAMPLE.read_bytes())
        self.assertEqual(len(data), 9)
        self.assertEqual(data.asset_id.nunique(), 2)
        self.assertEqual(str(data.timestamp.dt.tz), "UTC")
        minimal = b"timestamp,asset_id,temperature_c\n2026-01-01T00:00:00Z,M1,20\n"
        self.assertEqual(load_csv(minimal).temperature_c.iloc[0], 20)

    def test_invalid_data_rejected(self):
        cases = {
            "empty": b"",
            "no_rows": b"timestamp,asset_id,temperature_c\n",
            "missing_id": b"timestamp,temperature_c\n2026-01-01,20\n",
            "no_sensor": b"timestamp,asset_id\n2026-01-01,M1\n",
            "bad_date": b"timestamp,asset_id,temperature_c\ninvalid,M1,20\n",
            "empty_id": b"timestamp,asset_id,temperature_c\n2026-01-01, ,20\n",
            "not_numeric": b"timestamp,asset_id,temperature_c\n2026-01-01,M1,error\n",
            "missing_value": b"timestamp,asset_id,temperature_c\n2026-01-01,M1,\n",
            "infinite": b"timestamp,asset_id,temperature_c\n2026-01-01,M1,inf\n",
            "duplicate_header": b"timestamp,asset_id,temperature_c,temperature_c\n2026-01-01,M1,20,21\n",
            "duplicate_reading": b"timestamp,asset_id,temperature_c\n2026-01-01,M1,20\n2026-01-01,M1,21\n",
            "negative_hours": b"timestamp,asset_id,temperature_c,operating_hours\n2026-01-01,M1,20,-1\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_csv(content)

    def test_limits(self):
        with patch("data_contract.MAX_BYTES", 8), self.assertRaisesRegex(ValueError, "10 MiB"):
            load_csv(EXAMPLE.read_bytes())
        with patch("data_contract.MAX_ROWS", 2), self.assertRaisesRegex(ValueError, "100.000"):
            load_csv(EXAMPLE.read_bytes())


class InterfaceTests(unittest.TestCase):
    def test_demo_and_asset_selection(self):
        a=AppTest.from_file(str(PROJECT/'app.py')).run(timeout=30)
        a.button(key='small_demo').click().run(timeout=30)
        self.assertFalse(a.exception)
        self.assertEqual([m.value for m in a.metric],['9','2'])
        self.assertEqual(len(a.dataframe[0].value),9)
        a.selectbox(key='asset').select('BOMBA-002').run(timeout=30)
        self.assertFalse(a.exception)
