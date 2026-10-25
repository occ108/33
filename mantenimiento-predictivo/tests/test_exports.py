import csv
from io import StringIO
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exports import safe_csv


def rows_of(frame):
    return list(csv.reader(StringIO(safe_csv(frame).decode("utf-8"))))


class ExportTests(unittest.TestCase):
    def test_formulas_and_headers_are_neutralized(self):
        values = ["=1+1", "+SUM(A1:A3)", "-2+3", "@SUM(A1:A3)",
                  "   =1", "\t+1", "\r\n-1", "\u2003@SUM(A1:A3)"]
        for header in ["=cabecera", " +cabecera", "\t-cabecera", "\r\n@cabecera"]:
            with self.subTest(header=header):
                result = rows_of(pd.DataFrame({header: values}))
                self.assertEqual(result[0], ["'" + header])
                self.assertEqual([row[0] for row in result[1:]], ["'" + value for value in values])

    def test_negative_numbers_are_safe_text_and_missing_values_blank(self):
        data = pd.DataFrame({"valor": [-3.5, 0.0, 2.5, float("nan"), pd.NA, None]})
        result = rows_of(data)
        self.assertEqual(result, [["valor"], ["'-3.5"], ["0.0"], ["2.5"], [""], [""], [""]])

    def test_normal_values_quotes_newlines_and_unicode_round_trip(self):
        data = pd.DataFrame({"máquina": ['BOMBA-001', 'Equipo "A", línea 2', 'dos\r\nlíneas'],
                             "temperatura": [20, 21, 22]})
        result = rows_of(data)
        self.assertEqual(result[0], ["máquina", "temperatura"])
        self.assertEqual([row[0] for row in result[1:]], data["máquina"].tolist())
        self.assertEqual([row[1] for row in result[1:]], ["20", "21", "22"])

    def test_original_frame_and_headers_are_unchanged(self):
        data = pd.DataFrame({"=nombre": ["=1", "normal"], "lectura": [-2, 3]})
        original = data.copy(deep=True)
        safe_csv(data)
        pd.testing.assert_frame_equal(data, original)


if __name__ == "__main__":
    unittest.main()
