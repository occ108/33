"""Comprueba la interpretación visible, los umbrales y la compatibilidad del flujo."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]


class Phase2InterfaceTests(unittest.TestCase):
    def test_chart_reduction_preserves_sparse_indications(self):
        from app import _chart_sample
        frame = pd.DataFrame({"temperature_c__anomaly": np.zeros(10000, dtype=bool)})
        frame.loc[[123, 4567, 9999], "temperature_c__anomaly"] = True
        selected = _chart_sample(frame, "temperature_c")
        self.assertLessEqual(len(selected), 3000)
        self.assertEqual(int(selected.temperature_c__anomaly.sum()), 3)
        self.assertEqual(len(frame), 10000)

    def start(self):
        app = AppTest.from_file(str(PROJECT / "app.py")).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        return app

    def test_small_example_explains_insufficient_data(self):
        app = self.start()
        app.checkbox[0].check().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([tab.label for tab in app.tabs], ["Datos", "Anomalías", "Mantenimiento"])
        self.assertEqual([metric.value for metric in app.metric], ["9", "2"])
        self.assertEqual(len(app.dataframe[0].value), 9)
        self.assertTrue(any("Datos insuficientes" in info.value for info in app.info))
        self.assertTrue(app.dataframe[1].value["Semáforo"].str.contains("Ámbar").all())
        self.assertFalse(any("**Fecha orientativa" in mark.value for mark in app.markdown))

    def test_large_example_forecast_and_machine_settings(self):
        app = self.start()
        app.checkbox[1].check().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([metric.value for metric in app.metric], ["10800", "5"])
        app.selectbox[0].select("M-005").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        content = "\n".join(mark.value for mark in app.markdown)
        self.assertIn("**Fecha orientativa (UTC):**", content)
        self.assertIn("**Banda orientativa (UTC):**", content)
        self.assertIn("**Horas de uso restantes:**", content)
        self.assertTrue(any("no de la fecha actual" in cap.value for cap in app.caption))
        self.assertTrue(any("no son normas" in warning.value for warning in app.warning))
        limit = next(field for field in app.number_input if field.label == "Umbral superior · Temperatura (°C)")
        self.assertEqual(limit.value, 82.0)
        limit.set_value(60.0).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        lights = app.dataframe[1].value
        self.assertIn("Rojo", lights.loc[lights["Máquina"].eq("M-005"), "Semáforo"].iloc[0])
        app.selectbox[0].select("M-001").run(timeout=30)
        active = next(field for field in app.checkbox if field.label == "Activar umbral · Temperatura (°C)")
        self.assertFalse(active.value)
        app.selectbox[0].select("M-005").run(timeout=30)
        limit = next(field for field in app.number_input if field.label == "Umbral superior · Temperatura (°C)")
        self.assertEqual(limit.value, 60.0)

    def test_small_example_has_priority_and_joint_can_be_disabled(self):
        app = self.start()
        app.checkbox[0].check().run(timeout=30)
        app.checkbox[1].check().run(timeout=30)
        self.assertEqual([metric.value for metric in app.metric], ["9", "2"])
        joint = next(field for field in app.checkbox if field.label == "Análisis conjunto complementario")
        joint.uncheck().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("ejemplo pequeño" in info.value for info in app.info))


if __name__ == "__main__":
    unittest.main()
