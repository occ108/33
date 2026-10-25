"""Publica proyecciones reproducibles de señales sintéticas; no evalúa fallos reales."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import ForecastConfig, estimate_maintenance
from scripts.generate_synthetic import generate_synthetic


def evaluate_forecast() -> dict:
    dataset = generate_synthetic()
    asset = dataset.metadata["degradation_asset"]
    config = ForecastConfig()
    estimates = {}
    for sensor, threshold in dataset.metadata["illustrative_upper_thresholds"].items():
        result = estimate_maintenance(dataset.data, asset, sensor, threshold, config)
        estimates[sensor] = {
            "threshold": threshold,
            "generator_slope_per_hour": dataset.metadata["degradation_slopes_per_calendar_hour"][sensor],
            "result": asdict(result),
        }
    return {
        "asset_id": asset, "config": asdict(config), "estimates": estimates,
        "limitations": [
            "Los umbrales solo son ejemplos sintéticos, no normas ni órdenes de mantenimiento.",
            "Comparar la pendiente con la del generador no valida predicción de fallos ni cobertura de la banda temporal.",
            "La proyección supone que la tendencia reciente continúa y no cambian carga, régimen ni calibración.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "forecast.json")
    args = parser.parse_args()
    result = evaluate_forecast()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, ensure_ascii=False, default=lambda v: v.isoformat()) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
