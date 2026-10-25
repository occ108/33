import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import ForecastConfig, estimate_maintenance


def degrading(size=240, slope=.05, noise=.02):
    time = np.arange(size, dtype=float)
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=size, freq="h", tz="UTC"),
        "asset_id": "M1", "temperature_c": 50 + time * slope + rng.normal(0, noise, size),
        "operating_hours": 1000 + time * .75,
    })


class ForecastTests(unittest.TestCase):
    def test_degradation_interval_and_usage(self):
        data = degrading()
        original = data.copy(deep=True)
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "estimated")
        self.assertIsNotNone(result.predicted_at)
        self.assertLessEqual(result.earliest_at, result.predicted_at)
        self.assertLessEqual(result.predicted_at, result.latest_at)
        self.assertAlmostEqual(result.slope_per_hour, .05, delta=.001)
        self.assertAlmostEqual(result.remaining_hours, (70 - (50 + 239 * .05)) / .05, delta=2)
        self.assertAlmostEqual(result.remaining_operating_hours / result.remaining_hours, .75, delta=.01)
        self.assertLessEqual(result.operating_hours_low, result.operating_hours_at_threshold)
        self.assertLessEqual(result.operating_hours_at_threshold, result.operating_hours_high)
        pd.testing.assert_frame_equal(data, original)

    def test_constant_short_and_unconfigured(self):
        data = degrading(slope=0, noise=0)
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "no_degradation")
        self.assertIsNone(result.predicted_at)
        self.assertIn("Sin degradación apreciable", result.message)
        self.assertEqual(estimate_maintenance(data.head(9), "M1", "temperature_c", 70).status, "insufficient_data")
        self.assertEqual(estimate_maintenance(data, "M1", "temperature_c", None).status, "not_configured")

    def test_reached_and_horizon(self):
        data = degrading()
        reached = estimate_maintenance(data, "M1", "temperature_c", 55)
        self.assertEqual(reached.status, "threshold_reached")
        self.assertEqual(reached.remaining_hours, 0)
        distant = estimate_maintenance(data, "M1", "temperature_c", 200)
        self.assertEqual(distant.status, "beyond_horizon")
        self.assertIsNone(distant.predicted_at)

    def test_usage_reset_or_constant_does_not_stop_calendar(self):
        for mode in ["reset", "constant", "absent"]:
            with self.subTest(mode=mode):
                data = degrading()
                if mode == "reset":
                    data.loc[200:, "operating_hours"] -= 1000
                elif mode == "constant":
                    data["operating_hours"] = 1000.0
                else:
                    data = data.drop(columns="operating_hours")
                result = estimate_maintenance(data, "M1", "temperature_c", 70)
                self.assertEqual(result.status, "estimated")
                self.assertIsNone(result.remaining_operating_hours)
                self.assertTrue(result.operating_message)

    def test_usage_reset_before_recent_window_is_not_forgotten(self):
        data = degrading()
        data.loc[20:, "operating_hours"] -= 500
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "estimated")
        self.assertIsNotNone(result.predicted_at)
        self.assertIsNone(result.operating_hours_at_threshold)
        self.assertIsNone(result.remaining_operating_hours)
        self.assertIn("reinicio", result.operating_message)

    def test_microsecond_sampling_has_finite_projection_without_false_warning(self):
        data = degrading(noise=0).drop(columns="operating_hours")
        data["timestamp"] = pd.date_range("2026-01-01", periods=len(data), freq="us", tz="UTC")
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "estimated")
        self.assertTrue(np.isfinite(result.remaining_hours))
        self.assertAlmostEqual(result.remaining_hours * 3.6e9, 161, places=6)
        self.assertGreater(result.predicted_at, data.timestamp.iloc[-1])
        self.assertFalse(any("irregular" in warning for warning in result.warnings))

    def test_gap_recent_segment_and_irregular_times(self):
        data = degrading()
        ticks = data.timestamp.astype("int64").to_numpy(copy=True)
        ticks[220:] += 72 * 3_600_000_000_000
        data["timestamp"] = pd.to_datetime(ticks, utc=True)
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "insufficient_data")
        self.assertEqual(result.n_points, 20)
        self.assertTrue(any("hueco" in message for message in result.warnings))
        data = degrading()
        ticks = data.timestamp.astype("int64").to_numpy(copy=True)
        ticks[::3] += 20 * 60_000_000_000
        data["timestamp"] = pd.to_datetime(ticks, utc=True)
        result = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(result.status, "estimated")
        self.assertTrue(any("irregular" in message for message in result.warnings))

    def test_extreme_values_and_determinism(self):
        data = degrading()
        a = estimate_maintenance(data, "M1", "temperature_c", 70)
        b = estimate_maintenance(data, "M1", "temperature_c", 70)
        self.assertEqual(a, b)
        data["temperature_c"] = 1e308
        result = estimate_maintenance(data, "M1", "temperature_c", 1e308)
        self.assertEqual(result.status, "threshold_reached")
        for field in ["current_level", "slope_per_hour", "slope_low", "slope_high"]:
            self.assertTrue(np.isfinite(getattr(result, field)))

    def test_config_and_missing_selection(self):
        for params in [{"window": 5}, {"max_points": 16}, {"max_points": 2000}, {"confidence": 1}]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                ForecastConfig(**params)
        with self.assertRaises(ValueError):
            estimate_maintenance(degrading(), "missing", "temperature_c", 70)
        with self.assertRaises(ValueError):
            estimate_maintenance(degrading(), "M1", "pressure_bar", 70)
        with self.assertRaises(ValueError):
            estimate_maintenance(degrading(), "M1", "temperature_c", np.inf)
