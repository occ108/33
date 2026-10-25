"""Evaluación temporal reproducible; solo genera informes de datos sintéticos."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import AnalysisConfig, analyze_anomalies
from scripts.generate_synthetic import generate_synthetic, SENSORS


def scores(truth: np.ndarray, predicted: np.ndarray, ready: np.ndarray) -> dict:
    """Cuenta resultados y cobertura; no mezcla lecturas no evaluadas con negativas."""
    truth, predicted, ready = [np.asarray(a, dtype=bool) for a in (truth, predicted, ready)]
    tp = int(np.sum(truth & predicted & ready))
    fp = int(np.sum(~truth & predicted & ready))
    fn = int(np.sum(truth & ~predicted & ready))
    return {
        "evaluated": int(ready.sum()), "total": len(truth),
        "positive_unscored": int(np.sum(truth & ~ready)),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def evaluate() -> dict:
    dataset = generate_synthetic()
    config = AnalysisConfig()
    output = analyze_anomalies(dataset.data, config)
    wide = output.readings.set_index(["asset_id", "timestamp"])
    truth = dataset.truth.copy()
    for sensor in SENSORS:
        mask = truth.sensor.eq(sensor)
        keys = pd.MultiIndex.from_frame(truth.loc[mask, ["asset_id", "timestamp"]])
        truth.loc[mask, "prediction"] = wide.loc[keys, sensor + "__anomaly"].to_numpy()
        truth.loc[mask, "ready"] = wide.loc[keys, sensor + "__ready"].to_numpy()
    split = pd.Timestamp(dataset.metadata["test_start_inclusive"])
    report = {
        "seed": dataset.metadata["seed"],
        "config": asdict(config),
        "train_end_exclusive": split.isoformat(),
        "test_start_inclusive": split.isoformat(),
        "design": "Parámetros fijados antes de evaluar. Referencia móvil causal; IsolationForest solo aprende del prefijo inicial de cada máquina. Las etiquetas nunca se pasan al detector.",
        "rolling": {}, "isolation_forest": {},
        "limitations": [
            "Una sola simulación y semilla; no estima rendimiento en maquinaria real.",
            "La verdad positiva son picos inyectados. La degradación gradual está separada y puede contabilizarse como falso positivo, especialmente con IsolationForest.",
            "La línea base móvil se actualiza con lecturas pasadas del periodo de prueba: evaluación online, sin mirar al futuro.",
            "La demora se mide dentro del evento de 3 horas; los eventos no detectados se cuentan aparte.",
            "El método robusto se cuenta por máquina/instante/sensor; el conjunto por máquina/instante con al menos un sensor anómalo. Sus métricas no tienen la misma unidad de observación.",
        ],
    }
    for name, mask in [("train", truth.timestamp.lt(split)), ("test", truth.timestamp.ge(split))]:
        selected = truth.loc[mask]
        report["rolling"][name] = scores(selected.is_anomaly, selected.prediction, selected.ready)
    events = []
    for event in dataset.metadata["injected_events"]:
        if event["split"] != "test":
            continue
        selected = truth.loc[truth.event_id.eq(event["event_id"])]
        hits = selected.loc[selected.prediction.astype(bool) & selected.ready.astype(bool)]
        delay = None if hits.empty else float((hits.timestamp.min() - pd.Timestamp(event["start"])).total_seconds() / 3600)
        events.append({"event_id": event["event_id"], "delay_hours": delay})
    delays = [event["delay_hours"] for event in events if event["delay_hours"] is not None]
    report["rolling"]["test_events"] = {
        "total": len(events), "detected": len(delays), "missed": len(events) - len(delays),
        "mean_delay_hours_detected": float(np.mean(delays)) if delays else None,
        "max_delay_hours_detected": max(delays) if delays else None,
        "events": events,
    }
    joint_truth = truth.groupby(["asset_id", "timestamp"], sort=False).is_anomaly.any()
    for name, mask in [("train", joint_truth.index.get_level_values("timestamp") < split), ("test", joint_truth.index.get_level_values("timestamp") >= split)]:
        selected = joint_truth.loc[mask]
        rows = wide.loc[selected.index]
        report["isolation_forest"][name] = scores(selected, rows.if_anomaly, rows.if_ready)
    joint_events = []
    for event in dataset.metadata["injected_events"]:
        if event["split"] != "test":
            continue
        keys = pd.MultiIndex.from_frame(truth.loc[truth.event_id.eq(event["event_id"]), ["asset_id", "timestamp"]].drop_duplicates())
        rows = wide.loc[keys]
        hits = rows.loc[rows.if_anomaly & rows.if_ready]
        delay = None if hits.empty else float((hits.index.get_level_values("timestamp").min() - pd.Timestamp(event["start"])).total_seconds() / 3600)
        joint_events.append({"event_id": event["event_id"], "delay_hours": delay})
    joint_delays = [event["delay_hours"] for event in joint_events if event["delay_hours"] is not None]
    report["isolation_forest"]["test_events"] = {
        "total": len(joint_events), "detected": len(joint_delays), "missed": len(joint_events) - len(joint_delays),
        "mean_delay_hours_detected": float(np.mean(joint_delays)) if joint_delays else None,
        "max_delay_hours_detected": max(joint_delays) if joint_delays else None,
        "events": joint_events,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "evaluation.json")
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rolling": report["rolling"]["test"], "events": {k:v for k,v in report["rolling"]["test_events"].items() if k != "events"}, "isolation_forest": report["isolation_forest"]["test"]}, indent=2))


if __name__ == "__main__":
    main()
