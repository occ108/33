import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from app import load_csv
from scripts.generate_synthetic import SENSORS, generate_synthetic, write_dataset


class SyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = generate_synthetic()

    def test_shape_contract_size_and_operating_hours(self):
        data = self.dataset.data
        self.assertEqual(len(data), 5 * 90 * 24)
        self.assertEqual(data.asset_id.nunique(), 5)
        raw = data.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ").encode()
        self.assertLess(len(raw), 10 * 1024 * 1024)
        loaded = load_csv(raw)
        self.assertEqual(len(loaded), len(data))
        for _, group in loaded.groupby("asset_id"):
            self.assertTrue(group.operating_hours.is_monotonic_increasing)
            self.assertTrue(group.timestamp.diff().dropna().dt.total_seconds().eq(3600).all())

    def test_determinism_and_seed_changes_measurements(self):
        repeated = generate_synthetic()
        pd.testing.assert_frame_equal(self.dataset.data, repeated.data)
        pd.testing.assert_frame_equal(self.dataset.truth, repeated.truth)
        self.assertEqual(self.dataset.metadata, repeated.metadata)
        changed = generate_synthetic(seed=43)
        self.assertFalse(self.dataset.data.temperature_c.equals(changed.data.temperature_c))

    def test_truth_alignment_and_events_on_both_sides_of_split(self):
        truth = self.dataset.truth
        self.assertEqual(len(truth), len(self.dataset.data) * 3)
        self.assertEqual(set(truth.sensor), set(SENSORS))
        keys = self.dataset.data[["timestamp", "asset_id"]]
        joined = truth.merge(keys, on=["timestamp", "asset_id"], how="left", indicator=True)
        self.assertTrue(joined["_merge"].eq("both").all())
        self.assertTrue(truth.loc[truth.is_anomaly, "event_id"].ne("").all())
        self.assertTrue(truth.loc[~truth.is_anomaly, "event_id"].eq("").all())
        split = pd.Timestamp(self.dataset.metadata["test_start_inclusive"])
        self.assertTrue(truth.loc[truth.timestamp < split, "is_anomaly"].any())
        self.assertTrue(truth.loc[truth.timestamp >= split, "is_anomaly"].any())
        self.assertEqual(len(self.dataset.metadata["injected_events"]), 45)

    def test_gradual_degradation_only_on_last_asset(self):
        truth = self.dataset.truth
        drift = truth.loc[truth.is_degradation]
        self.assertEqual(set(drift.asset_id), {"M-005"})
        self.assertEqual(set(drift.sensor), {"temperature_c", "vibration_mm_s"})
        clean = self.dataset.data.merge(
            truth.loc[truth.sensor.eq("temperature_c"), ["timestamp", "asset_id", "is_anomaly"]],
            on=["timestamp", "asset_id"],
        ).query("asset_id == 'M-005' and not is_anomaly")
        first = clean.iloc[-7 * 24:-6 * 24].temperature_c.median()
        last = clean.iloc[-24:].temperature_c.median()
        self.assertGreater(last - first, 2.0)

    def test_writes_three_reproducible_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_dataset(self.dataset, Path(tmp))
            self.assertEqual(set(paths), {"data", "truth", "metadata"})
            self.assertEqual(len(load_csv(paths["data"].read_bytes())), 10800)
            metadata = json.loads(paths["metadata"].read_text())
            self.assertEqual(metadata["seed"], 42)
            before = {name: path.read_bytes() for name, path in paths.items()}
            write_dataset(self.dataset, Path(tmp))
            self.assertEqual(before, {name: path.read_bytes() for name, path in paths.items()})

    def test_invalid_generation_parameters(self):
        for kwargs in ({"days": 0}, {"days": 3.2}, {"assets": 0}, {"assets": 100}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generate_synthetic(**kwargs)


if __name__ == "__main__":
    unittest.main()
