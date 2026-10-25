"""Genera históricos sintéticos y etiquetas separadas para una evaluación reproducible.

Los picos son anomalías puntuales conocidas. La degradación gradual se etiqueta
por separado: no constituye un fallo real ni valida una predicción de averías.
Importar este módulo no escribe archivos.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SENSORS = ("temperature_c", "vibration_mm_s", "pressure_bar")
SEED = 42


@dataclass(frozen=True)
class SyntheticDataset:
    """Lecturas compatibles con load_csv, etiquetas largas y definición del experimento."""

    data: pd.DataFrame
    truth: pd.DataFrame
    metadata: dict[str, Any]


def generate_synthetic(seed: int = SEED, days: int = 90, assets: int = 5) -> SyntheticDataset:
    """Devuelve ``assets`` históricos horarios, sin guardar ni modificar datos externos.

    La última máquina degrada temperatura y vibración durante el último tercio.
    ``truth.is_anomaly`` identifica exclusivamente los picos de 3 horas; la
    degradación está en ``truth.is_degradation``. El prefijo temporal de un tercio
    es entrenamiento y el resto prueba (30 y 60 días con los parámetros por defecto).
    Las unidades y umbrales son ejemplos inventados, no límites industriales.
    """
    if not isinstance(days, int) or days < 6:
        raise ValueError("days debe ser un entero de al menos 6 días.")
    if not isinstance(assets, int) or not 1 <= assets <= 99:
        raise ValueError("assets debe ser un entero entre 1 y 99.")
    rng = np.random.default_rng(seed)
    count = days * 24
    hour = np.arange(count, dtype=np.float64)
    timestamps = pd.date_range("2026-01-01", periods=count, freq="h", tz="UTC")
    training_rows = count // 3
    degradation_start = 2 * count // 3
    point_fraction = (0.12, 0.23, 0.40, 0.48, 0.56, 0.66, 0.75, 0.84, 0.93)
    sensor_patterns = ((0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2), (0,), (1, 2))
    frames: list[pd.DataFrame] = []
    labels: list[pd.DataFrame] = []
    events: list[dict[str, Any]] = []

    for number in range(1, assets + 1):
        asset_id = f"M-{number:03d}"
        daily = np.sin(2 * np.pi * hour / 24 + number / 3)
        weekly = np.sin(2 * np.pi * hour / (24 * 7))
        temperature = 46 + 2 * number + 0.35 * daily + 0.10 * weekly + rng.normal(0, 0.18, count)
        vibration = 1.2 + 0.12 * number + 0.025 * daily + rng.normal(0, 0.025, count)
        pressure = 4 + 0.05 * number + 0.025 * weekly + rng.normal(0, 0.025, count)
        values = np.column_stack((temperature, vibration, pressure))
        degradation = np.zeros((count, len(SENSORS)), dtype=bool)
        if number == assets:
            elapsed = np.maximum(hour - degradation_start, 0)
            values[:, 0] += elapsed * 0.025
            values[:, 1] += elapsed * 0.002
            degradation[degradation_start:, :2] = True

        point_labels = np.zeros((count, len(SENSORS)), dtype=bool)
        event_ids = np.full((count, len(SENSORS)), "", dtype=object)
        for event_number, (fraction, sensor_indices) in enumerate(zip(point_fraction, sensor_patterns), 1):
            start = max(48, int(fraction * count) + number - 1)
            stop = min(start + 3, count)
            if start >= stop:
                continue
            event_id = f"{asset_id}-E{event_number:02d}"
            for sensor in sensor_indices:
                amplitude = (7.0, 1.5, 0.8)[sensor]
                sign = -1 if sensor != 1 and event_number % 2 == 0 else 1
                values[start:stop, sensor] += sign * amplitude
                point_labels[start:stop, sensor] = True
                event_ids[start:stop, sensor] = event_id
            events.append({
                "event_id": event_id,
                "asset_id": asset_id,
                "start": timestamps[start].isoformat(),
                "end_exclusive": (timestamps[stop - 1].to_pydatetime() + timedelta(hours=1)).isoformat(),
                "sensors": [SENSORS[index] for index in sensor_indices],
                "split": "train" if start < training_rows else "test",
            })

        frame = pd.DataFrame({"timestamp": timestamps, "asset_id": asset_id})
        for sensor_index, sensor in enumerate(SENSORS):
            frame[sensor] = np.round(values[:, sensor_index], 6)
            labels.append(pd.DataFrame({
                "timestamp": timestamps,
                "asset_id": asset_id,
                "sensor": sensor,
                "is_anomaly": point_labels[:, sensor_index],
                "event_id": event_ids[:, sensor_index],
                "is_degradation": degradation[:, sensor_index],
            }))
        # Cada máquina acumula aproximadamente 45 minutos de trabajo por hora real.
        frame["operating_hours"] = np.round(800 + number * 100 + hour * 0.75, 6)
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    truth = pd.concat(labels, ignore_index=True).sort_values(
        ["asset_id", "timestamp", "sensor"], kind="stable"
    ).reset_index(drop=True)
    metadata = {
        "seed": seed,
        "days": days,
        "assets": assets,
        "readings": len(data),
        "sampling": "hourly; no gaps or interpolation",
        "timezone": "UTC",
        "start": timestamps[0].isoformat(),
        "train_end_exclusive": timestamps[training_rows].isoformat(),
        "test_start_inclusive": timestamps[training_rows].isoformat(),
        "test_end_exclusive": (timestamps[-1].to_pydatetime() + timedelta(hours=1)).isoformat(),
        "degradation_asset": f"M-{assets:03d}",
        "degradation_start": timestamps[degradation_start].isoformat(),
        "degradation_slopes_per_calendar_hour": {"temperature_c": 0.025, "vibration_mm_s": 0.002},
        "operating_hours_per_calendar_hour": 0.75,
        "illustrative_upper_thresholds": {"temperature_c": 82.0, "vibration_mm_s": 3.8},
        "threshold_warning": "Synthetic demonstration values only; not standards or maintenance instructions.",
        "truth_format": "Long table: one row per asset/timestamp/sensor, including negative labels.",
        "point_label_definition": "is_anomaly marks injected 3-hour spikes only; is_degradation separately marks gradual drift.",
        "failure_labels": "None: synthetic anomalies and drift do not represent labelled real failures.",
        "injected_events": events,
    }
    return SyntheticDataset(data=data, truth=truth, metadata=metadata)


def write_dataset(dataset: SyntheticDataset, output_dir: Path) -> dict[str, Path]:
    """Escribe solo el conjunto sintético solicitado, nunca archivos subidos."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "data": output_dir / "sensores_90d.csv",
        "truth": output_dir / "etiquetas_90d.csv",
        "metadata": output_dir / "metadata.json",
    }
    dataset.data.to_csv(paths["data"], index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    dataset.truth.to_csv(paths["truth"], index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    paths["metadata"].write_text(json.dumps(dataset.metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "examples" / "synthetic")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--assets", type=int, default=5)
    args = parser.parse_args()
    result = generate_synthetic(seed=args.seed, days=args.days, assets=args.assets)
    paths = write_dataset(result, args.output_dir)
    print(f"{len(result.data)} lecturas sintéticas; {len(result.truth)} etiquetas por sensor.")
    for name, path in paths.items():
        print(f"{name}: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
