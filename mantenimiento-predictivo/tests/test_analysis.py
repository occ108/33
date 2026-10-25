import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import AnalysisConfig, analyze_anomalies, quality_warnings, _time_steps


def frame(size=400, sensors=3, noise=False):
    rng = np.random.default_rng(42)
    data = {
        "timestamp": pd.date_range("2026-01-01", periods=size, freq="h", tz="UTC"),
        "asset_id": ["M1"] * size,
    }
    for i, name in enumerate(["temperature_c", "vibration_mm_s", "pressure_bar"][:sensors]):
        data[name] = 50.0 + i + (rng.normal(0, .1, size) if noise else np.zeros(size))
    return pd.DataFrame(data)


class AnomalyTests(unittest.TestCase):
    def test_spikes_and_exact_past_baseline(self):
        data = frame(sensors=1)
        data.loc[100, "temperature_c"] = 70
        result = analyze_anomalies(data)
        self.assertTrue(result.readings.loc[100, "temperature_c__anomaly"])
        self.assertEqual(result.readings.loc[100, "temperature_c__baseline"], 50)
        self.assertFalse(result.readings.loc[:23, "temperature_c__ready"].any())
        self.assertEqual(result.summary.n_anomalies.iloc[0], 1)
        self.assertFalse(result.readings.if_ready.any())

    def test_constant_and_short_series(self):
        result = analyze_anomalies(frame())
        self.assertFalse(result.readings.temperature_c__anomaly.any())
        self.assertFalse(result.readings.if_anomaly.any())
        short = analyze_anomalies(frame(9))
        self.assertEqual(set(short.summary.status), {"datos_insuficientes"})
        self.assertFalse(short.readings.temperature_c__ready.any())

    def test_exact_window_median_and_mad(self):
        data = frame(80, sensors=1, noise=True)
        config = AnalysisConfig(window=30, min_history=12)
        result = analyze_anomalies(data, config)
        for index in [12, 29, 30, 79]:
            past = data.temperature_c.iloc[max(0, index - 30):index].to_numpy()
            median = np.median(past)
            mad = np.median(np.abs(past - median))
            expected = abs(data.temperature_c.iloc[index] - median) / (1.4826 * mad)
            self.assertAlmostEqual(result.readings.temperature_c__baseline.iloc[index], median, places=11)
            self.assertAlmostEqual(result.readings.temperature_c__score.iloc[index], expected, places=9)

    def test_gaps_irregularity_and_baseline_restart(self):
        data = frame(160, sensors=1)
        times = data.timestamp.astype("int64").to_numpy(copy=True)
        times[80:] += 72 * 3_600_000_000_000
        times[20] += 20 * 60_000_000_000
        data["timestamp"] = pd.to_datetime(times, utc=True)
        result = analyze_anomalies(data)
        self.assertTrue(any("irregular" in warning for warning in result.warnings))
        self.assertTrue(any("hueco" in warning for warning in quality_warnings(data)))
        self.assertFalse(result.readings.loc[80:103, "temperature_c__ready"].any())
        self.assertTrue(result.readings.loc[104, "temperature_c__ready"])

    def test_extreme_finite_values(self):
        data = frame()
        data.loc[:, "temperature_c"] = 1e308
        data.loc[300, "temperature_c"] = -1e308
        result = analyze_anomalies(data)
        ready = result.readings.temperature_c__ready
        self.assertTrue(np.isfinite(result.readings.loc[ready, "temperature_c__score"]).all())
        self.assertTrue(np.isfinite(result.readings.loc[ready, "temperature_c__baseline"]).all())
        self.assertTrue(result.readings.loc[300, "temperature_c__anomaly"])
        self.assertTrue(np.isfinite(result.readings.loc[result.readings.if_ready, "if_score"]).all())
        tiny = frame(80, sensors=1)
        tiny["temperature_c"] = 1e-320
        tiny.loc[60, "temperature_c"] = 1e308
        tiny_result = analyze_anomalies(tiny)
        self.assertTrue(tiny_result.readings.loc[60, "temperature_c__anomaly"])

    def test_forest_spikes_determinism_and_causality(self):
        data = frame(500, noise=True)
        data.loc[300, ["temperature_c", "vibration_mm_s", "pressure_bar"]] = [70, 80, 90]
        a = analyze_anomalies(data)
        b = analyze_anomalies(data)
        pd.testing.assert_frame_equal(a.readings, b.readings)
        self.assertTrue(a.readings.loc[300, "if_anomaly"])
        self.assertFalse(a.readings.loc[:191, "if_ready"].any())
        self.assertTrue(a.readings.loc[192, "if_ready"])
        extended = frame(600, noise=True)
        extended.iloc[:500] = data
        extended.loc[550, "temperature_c"] = 1e308
        future = analyze_anomalies(extended)
        for column in ["temperature_c__score", "temperature_c__baseline", "if_score", "if_anomaly"]:
            pd.testing.assert_series_equal(a.readings[column], future.readings[column].iloc[:500])
        # Un cambio de frecuencia futuro no debe cambiar reinicios del pasado.
        past_with_gap = data.copy()
        ticks = past_with_gap.timestamp.astype("int64").to_numpy(copy=True)
        ticks[200:] += 10 * 3_600_000_000_000
        past_with_gap["timestamp"] = pd.to_datetime(ticks, utc=True)
        more = frame(1000, noise=True)
        more["timestamp"] = pd.date_range(
            pd.Timestamp(int(ticks[-1]) + 60_000_000_000, tz="UTC"),
            periods=1000, freq="min"
        )
        past_result = analyze_anomalies(past_with_gap)
        changed_cadence = analyze_anomalies(pd.concat([past_with_gap, more], ignore_index=True))
        for column in ["temperature_c__score", "temperature_c__ready", "temperature_c__anomaly"]:
            pd.testing.assert_series_equal(past_result.readings[column], changed_cadence.readings[column].iloc[:500])
        self.assertEqual(list(data.columns), ["timestamp", "asset_id", "temperature_c", "vibration_mm_s", "pressure_bar"])

    def test_machine_isolation(self):
        first, second = frame(100, sensors=1), frame(100, sensors=1)
        second["asset_id"] = "M2"
        second["temperature_c"] += 300
        data = pd.concat([first, second], ignore_index=True)
        result = analyze_anomalies(data)
        self.assertEqual(len(result.summary), 2)
        self.assertFalse(result.readings.temperature_c__anomaly.any())

    def test_forest_warmup_does_not_retroactively_score_prefix(self):
        data = frame(193, noise=True)
        before = analyze_anomalies(data.head(191))
        at_boundary = analyze_anomalies(data.head(192))
        after = analyze_anomalies(data)
        self.assertFalse(before.readings.if_ready.any())
        self.assertFalse(at_boundary.readings.if_ready.any())
        self.assertTrue(after.readings.loc[192, "if_ready"])
        for column in ["if_ready", "if_anomaly", "if_score"]:
            pd.testing.assert_series_equal(before.readings[column], after.readings[column].iloc[:191])
            pd.testing.assert_series_equal(at_boundary.readings[column], after.readings[column].iloc[:192])
        self.assertTrue(any("193" in warning for warning in at_boundary.warnings))

    def test_precise_regular_intervals_and_wide_date_ranges(self):
        for frequency in ["ns", "us"]:
            with self.subTest(frequency=frequency):
                data = frame(80, sensors=1)
                data["timestamp"] = pd.date_range("2026-01-01", periods=80, freq=frequency, tz="UTC")
                self.assertEqual(quality_warnings(data), [])
                result = analyze_anomalies(data)
                self.assertTrue(result.readings.loc[24:, "temperature_c__ready"].all())
        data = frame(2, sensors=1)
        data["timestamp"] = pd.to_datetime(["1700-01-01T00:00:00Z", "2240-01-01T00:00:00Z"])
        steps, nominal = _time_steps(data)
        expected = (int(data.timestamp.iloc[1].value) - int(data.timestamp.iloc[0].value)) / 3.6e12
        self.assertEqual(steps.tolist(), [expected])
        self.assertEqual(nominal, expected)
        self.assertGreater(nominal, 0)

    def test_invalid_configuration(self):
        for kwargs in [{"window": 5}, {"z_threshold": 0}, {"if_train_size": 10}, {"if_contamination": 0}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AnalysisConfig(**kwargs)
