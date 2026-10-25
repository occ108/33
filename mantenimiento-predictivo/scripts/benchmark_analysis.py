"""Mide en un proceso nuevo el flujo CSV + análisis de 100.000 lecturas sintéticas."""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import platform
import resource
import sys
from time import perf_counter

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from app import load_csv
from analysis import AnalysisConfig, analyze_anomalies, estimate_maintenance
from exports import safe_csv
from maintenance import build_maintenance_plan


def benchmark(rows: int = 100_000) -> dict:
    """Incluye el pico RSS de imports, construcción, lectura y análisis; no usa datos reales."""
    if rows < 1000 or rows > 100_000 or rows % 5:
        raise ValueError("rows debe ser múltiplo de 5, entre 1.000 y 100.000.")
    rng = np.random.default_rng(42)
    n = rows // 5
    index = np.tile(np.arange(n), 5)
    df = pd.DataFrame({
        "timestamp": np.tile(pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC"), 5),
        "asset_id": np.repeat([f"M-{i:03}" for i in range(1, 6)], n),
        "temperature_c": np.round(50 + .0001 * index + rng.normal(0, .3, rows), 5),
        "vibration_mm_s": np.round(2 + .00001 * index + rng.normal(0, .03, rows), 5),
        "pressure_bar": np.round(4 + rng.normal(0, .04, rows), 5),
        "operating_hours": .75 * index + 1000,
    })
    content = df.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ").encode()
    del df
    gc.collect()
    start = perf_counter()
    parsed = load_csv(content)
    loaded = perf_counter()
    result = analyze_anomalies(parsed, AnalysisConfig())
    analyzed = perf_counter()
    estimates = [
        estimate_maintenance(parsed, asset, sensor, threshold)
        for asset in parsed.asset_id.unique()
        for sensor, threshold in {"temperature_c": 82.0, "vibration_mm_s": 3.8, "pressure_bar": 6.0}.items()
    ]
    forecasted = perf_counter()
    plan = build_maintenance_plan(parsed, {(asset,sensor):limit for asset in parsed.asset_id.unique() for sensor,limit in {'temperature_c':82.,'vibration_mm_s':3.8,'pressure_bar':6.}.items()}, parsed.timestamp.max())
    exported = safe_csv(result.readings)
    plan_export = safe_csv(plan)
    finished = perf_counter()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return {
        "rows": rows, "assets": 5, "sensors": 3, "csv_bytes": len(content),
        "csv_seconds": loaded - start, "analysis_seconds": analyzed - loaded,
        "forecast_seconds": forecasted - analyzed, "forecast_count": len(estimates),
        "plan_and_export_seconds": finished - forecasted, "plan_rows":len(plan), "export_bytes": len(exported),
        "pipeline_seconds": finished - start, "peak_rss_mib": peak,
        "rss_includes": "Imports de Streamlit y dependencias, generación de CSV, validación, anomalías, 15 estimaciones, plan de revisión y CSV seguros. Un proceso nuevo, una ejecución, cinco máquinas. No es una medida de concurrencia.",
        "budget_rss_mib": 400, "within_memory_budget": peak < 400,
        "analysis_target_seconds": 5, "within_time_target": analyzed - loaded < 5,
        "result_rows": len(result.readings), "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "benchmark.json")
    args = parser.parse_args()
    result = benchmark(args.rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
