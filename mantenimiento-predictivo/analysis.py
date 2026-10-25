"""Análisis causal y explicable de históricos industriales, sin interfaz ni persistencia.

Los resultados señalan comportamientos inusuales, nunca probabilidades de avería.
Las ventanas se expresan en lecturas, no en horas; no se rellenan huecos.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from automotive import SENSORS
_BLOCK_SIZE = 1024
_NUMERICAL_FLOOR = 1e-9


@dataclass(frozen=True)
class AnalysisConfig:
    """Parámetros de detección; la línea base excluye siempre la lectura actual."""

    window: int = 48
    min_history: int = 24
    z_threshold: float = 4.5
    if_enabled: bool = True
    if_train_size: int = 168
    if_min_train: int = 96
    if_estimators: int = 64
    if_contamination: float = 0.01
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.min_history < 3 or self.window < self.min_history:
            raise ValueError("La ventana debe contener al menos el mínimo de historia (>=3).")
        if not np.isfinite(self.z_threshold) or self.z_threshold <= 0:
            raise ValueError("El umbral de desviación debe ser positivo y finito.")
        if self.if_min_train < 3 or self.if_train_size < self.if_min_train:
            raise ValueError("El entrenamiento conjunto debe respetar su mínimo de datos.")
        if self.if_estimators < 1 or not 0 < self.if_contamination <= 0.5:
            raise ValueError("Parámetros del análisis conjunto fuera de rango.")


@dataclass(frozen=True)
class AnomalyResult:
    """Lecturas con indicadores, resumen por activo/sensor y avisos de calidad."""

    readings: pd.DataFrame
    summary: pd.DataFrame
    warnings: list[str]


def _time_steps(group: pd.DataFrame) -> tuple[np.ndarray, float]:
    # Restar enteros Python antes de convertir conserva intervalos de ns/us y
    # evita desbordar int64 entre fechas válidas separadas más de 292 años.
    ticks = group["timestamp"].astype("int64").to_numpy()
    steps = np.fromiter(
        ((int(right) - int(left)) / 3.6e12 for left, right in zip(ticks[:-1], ticks[1:])),
        dtype=float, count=max(len(ticks) - 1, 0),
    )
    positive = steps[steps > 0]
    return steps, float(np.median(positive)) if positive.size else 0.0


def quality_warnings(df: pd.DataFrame) -> list[str]:
    """Describe irregularidad (>10%) y huecos (>3 veces el intervalo mediano).

    No modifica las lecturas ni interpreta los intervalos ausentes como mediciones.
    """
    warnings: list[str] = []
    for asset, group in df.sort_values(["asset_id", "timestamp"]).groupby("asset_id", sort=False):
        steps, nominal = _time_steps(group)
        if nominal <= 0:
            continue
        irregular = np.abs(steps - nominal) > nominal * 0.1
        gaps = steps > nominal * 3
        if irregular.any():
            warnings.append(
                f"{asset}: muestreo irregular; {100 * irregular.mean():.1f}% de los intervalos "
                f"se aparta más del 10% del intervalo mediano ({nominal:.3g} h). "
                "No se interpola ni se rellenan lecturas."
            )
        if gaps.any():
            warnings.append(
                f"{asset}: {int(gaps.sum())} hueco(s) superior(es) a tres veces el intervalo "
                "mediano. No se rellenan datos; la línea base se reinicia ante "
                "separaciones largas respecto a los intervalos anteriores."
            )
    return warnings


def _history_score(history: np.ndarray, current: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mediana/MAD exactas por fila; normalización exclusivamente con su pasado."""
    magnitude = np.maximum(np.max(np.abs(history), axis=1), _NUMERICAL_FLOOR)
    normalized = history / magnitude[:, None]
    center = np.median(normalized, axis=1)
    mad = np.median(np.abs(normalized - center[:, None]), axis=1)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        floor = np.maximum(_NUMERICAL_FLOOR / magnitude, 8 * np.finfo(float).eps)
        spread = np.maximum(1.4826 * mad, floor)
        # Un extremo actual puede superar el rango de su pasado; se satura la
        # puntuación, no la lectura original, sin producir infinitos exportables.
        score = np.abs(current / magnitude - center) / spread
    score = np.nan_to_num(score, nan=0.0, posinf=np.finfo(float).max)
    return center * magnitude, score


def _rolling_scores(values: np.ndarray, config: AnalysisConfig) -> tuple[np.ndarray, np.ndarray]:
    size = len(values)
    baseline = np.full(size, np.nan)
    score = np.full(size, np.nan)
    # El calentamiento usa toda la historia disponible hasta completar ventana.
    for index in range(config.min_history, min(config.window, size)):
        baseline[index], score[index] = (
            result[0] for result in _history_score(values[:index][None, :], values[index:index + 1])
        )
    if size > config.window:
        windows = np.lib.stride_tricks.sliding_window_view(values, config.window)[:-1]
        for start in range(0, len(windows), _BLOCK_SIZE):
            stop = min(start + _BLOCK_SIZE, len(windows))
            output = slice(config.window + start, config.window + stop)
            baseline[output], score[output] = _history_score(windows[start:stop], values[output])
    return baseline, score


def _forest_scores(values: np.ndarray, config: AnalysisConfig) -> tuple[np.ndarray, np.ndarray, str | None]:
    size = len(values)
    scores, flags = np.full(size, np.nan), np.zeros(size, dtype=bool)
    if not config.if_enabled:
        return scores, flags, None
    if values.shape[1] < 2:
        return scores, flags, "el análisis conjunto necesita al menos dos sensores"
    # Mantener fija la referencia evita que ampliar el futuro cambie el modelo.
    train_end = config.if_train_size
    score_start = train_end + 24
    if size <= score_start:
        return scores, flags, (
            f"el análisis conjunto necesita al menos {score_start + 1} lecturas: "
            f"{train_end} de referencia, 24 de calentamiento posterior y una evaluable"
        )

    from sklearn.ensemble import IsolationForest

    training = values[:train_end]
    if len(training) > 2048:
        training = training[np.linspace(0, len(training) - 1, 2048, dtype=int)]
    magnitude = np.max(np.abs(training), axis=0)
    magnitude[magnitude == 0] = 1.0
    normalized = training / magnitude
    center = np.median(normalized, axis=0)
    spread = np.maximum(1.4826 * np.median(np.abs(normalized - center), axis=0), 1e-9)

    def transform(batch: np.ndarray) -> np.ndarray:
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            transformed = (batch / magnitude - center) / spread
        return np.clip(np.nan_to_num(transformed, nan=0, posinf=1e6, neginf=-1e6), -1e6, 1e6).astype(np.float32)

    model = IsolationForest(
        n_estimators=config.if_estimators, max_samples=min(256, len(training)),
        contamination=config.if_contamination, random_state=config.random_state, n_jobs=1,
    ).fit(transform(training))
    for start in range(score_start, size, 8192):
        stop = min(start + 8192, size)
        decision = model.decision_function(transform(values[start:stop]))
        scores[start:stop] = -decision  # Positivo significa indicio conjunto.
        flags[start:stop] = decision < 0
    return scores, flags, None


def analyze_anomalies(df: pd.DataFrame, config: AnalysisConfig = AnalysisConfig()) -> AnomalyResult:
    """Analiza un DataFrame validado por load_csv, independientemente por máquina.

    Devuelve ``sensor__baseline``, ``sensor__score``, ``sensor__anomaly`` y
    ``sensor__ready``; ``if_*`` corresponde al método conjunto complementario.
    ``ready=False`` distingue ausencia de análisis de ausencia de indicios.
    La referencia robusta se reinicia tras huecos. Isolation Forest usa solo un
    prefijo fijo de referencia y nunca se ajusta con las observaciones posteriores.
    Tras la referencia deja 24 lecturas de calentamiento sin puntuar; la primera
    evaluable es siempre la posición ``if_train_size + 24`` (contando desde cero).
    """
    readings = df.sort_values(["asset_id", "timestamp"]).reset_index(drop=True).copy()
    sensors = [sensor for sensor in SENSORS if sensor in readings]
    if not sensors:
        raise ValueError("No hay sensores reconocidos para analizar.")
    warnings = quality_warnings(readings)
    for sensor in sensors:
        readings[sensor + "__baseline"] = np.nan
        readings[sensor + "__score"] = np.nan
        readings[sensor + "__anomaly"] = False
        readings[sensor + "__ready"] = False
    readings["if_score"] = np.nan
    readings["if_anomaly"] = False
    readings["if_ready"] = False
    summary: list[dict] = []
    for asset, positions in readings.groupby("asset_id", sort=False).indices.items():
        group = readings.iloc[positions]
        steps, _ = _time_steps(group)
        # La regla de reinicio tampoco puede consultar intervalos futuros.
        previous_step = pd.Series(steps).where(steps > 0).shift(1).rolling(
            config.window, min_periods=1
        ).median().to_numpy()
        boundaries = np.flatnonzero(steps > previous_step * 3) + 1
        segments = np.split(np.arange(len(group)), boundaries)
        forest_score, forest_flag, forest_warning = _forest_scores(group[sensors].to_numpy(dtype=float), config)
        forest_ready = np.isfinite(forest_score)
        readings.loc[positions, "if_score"] = forest_score
        readings.loc[positions, "if_anomaly"] = forest_flag
        readings.loc[positions, "if_ready"] = forest_ready
        if forest_warning:
            warnings.append(f"{asset}: {forest_warning}.")
        for sensor in sensors:
            baseline, scores = np.full(len(group), np.nan), np.full(len(group), np.nan)
            values = group[sensor].to_numpy(dtype=float)
            for segment in segments:
                baseline[segment], scores[segment] = _rolling_scores(values[segment], config)
            ready = np.isfinite(scores)
            flags = ready & (scores > config.z_threshold)
            for suffix, data in [("baseline", baseline), ("score", scores), ("anomaly", flags), ("ready", ready)]:
                readings.loc[positions, sensor + "__" + suffix] = data
            why = (
                f"{int(ready.sum())} lecturas comparadas con la mediana y MAD de su pasado."
                if ready.any() else
                f"Datos insuficientes: hacen falta al menos {config.min_history + 1} lecturas consecutivas."
            )
            summary.append({
                "asset_id": asset, "sensor": sensor, "n_readings": len(group),
                "n_evaluated": int(ready.sum()), "n_anomalies": int(flags.sum()),
                "if_evaluated": int(forest_ready.sum()), "if_anomalies": int(forest_flag.sum()),
                "status": "evaluado" if ready.any() else "datos_insuficientes", "why": why,
            })
    return AnomalyResult(readings, pd.DataFrame(summary), warnings)


@dataclass(frozen=True)
class ForecastConfig:
    """Ventana reciente en lecturas y límites de coste/horizonte de proyección."""

    window: int = 168
    min_points: int = 48
    max_points: int = 128
    max_horizon_hours: float = 2160.0
    confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.min_points < 3 or self.window < self.min_points or self.max_points < self.min_points:
            raise ValueError("La ventana y el submuestreo deben permitir el mínimo de puntos (>=3).")
        if self.max_points > 512:
            raise ValueError("Theil–Sen se limita a un máximo de 512 puntos.")
        if not np.isfinite(self.max_horizon_hours) or self.max_horizon_hours <= 0:
            raise ValueError("El horizonte debe ser positivo y finito.")
        if not 0.5 < self.confidence < 1:
            raise ValueError("La confianza de la pendiente debe estar entre 0,5 y 1.")


@dataclass(frozen=True)
class ForecastResult:
    """Estimación hasta un umbral superior; ningún campo representa una avería.

    Las fechas y horas de uso son ``None`` si no se pueden estimar. La banda
    combina límites de pendiente y dispersión residual: no acredita una cobertura
    estadística de la fecha de cruce, ni una probabilidad de fallo.
    """

    status: str
    message: str
    predicted_at: pd.Timestamp | None = None
    earliest_at: pd.Timestamp | None = None
    latest_at: pd.Timestamp | None = None
    remaining_hours: float | None = None
    remaining_hours_low: float | None = None
    remaining_hours_high: float | None = None
    slope_per_hour: float | None = None
    slope_low: float | None = None
    slope_high: float | None = None
    operating_hours_at_threshold: float | None = None
    operating_hours_low: float | None = None
    operating_hours_high: float | None = None
    remaining_operating_hours: float | None = None
    operating_message: str = "No se ha incluido un contador de horas de uso."
    current_level: float | None = None
    n_points: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Trend:
    slope: float
    low: float
    high: float
    level: float
    residual_band: float
    x_span: float
    y_scale: float


def _fit_trend(x: np.ndarray, y: np.ndarray, confidence: float) -> _Trend:
    """Normaliza ambos ejes antes de un Theil–Sen de coste acotado por el llamante."""
    from scipy.stats import norm, theilslopes

    span = float(np.max(x) - np.min(x))
    if span <= 0 or not np.isfinite(span):
        raise ValueError("El eje de ajuste no tiene variación utilizable.")
    x_normalized = (x - x[-1]) / span
    scale = max(float(np.max(np.abs(y))), _NUMERICAL_FLOOR)
    normalized = y / scale
    fit = theilslopes(normalized, x_normalized, alpha=confidence, method="joint")
    residuals = normalized - (fit.intercept + fit.slope * x_normalized)
    residual_mad = float(np.median(np.abs(residuals - np.median(residuals))))
    band = float(norm.ppf((1 + confidence) / 2)) * 1.4826 * residual_mad
    return _Trend(float(fit.slope), float(fit.low_slope), float(fit.high_slope),
                  float(fit.intercept), band, span, scale)


def _finite_float(value: np.longdouble | float) -> float | None:
    if not np.isfinite(value) or abs(value) > np.finfo(float).max:
        return None
    return float(value)


def _projection(trend: _Trend, threshold: float) -> tuple[float | None, float | None, float | None]:
    """Horas/unidades del eje hasta el umbral y envolvente orientativa."""
    target = np.longdouble(threshold) / trend.y_scale
    nominal = (target - trend.level) / trend.slope * trend.x_span
    early = max(np.longdouble(0), (target - trend.level - trend.residual_band) / trend.high * trend.x_span)
    late = max(np.longdouble(0), (target - trend.level + trend.residual_band) / trend.low * trend.x_span)
    return _finite_float(nominal), _finite_float(early), _finite_float(late)


def _date_after(timestamp: pd.Timestamp, hours: float | None) -> pd.Timestamp | None:
    if hours is None:
        return None
    ticks = int(timestamp.value) + int(round(hours * 3.6e12))
    bounds = np.iinfo(np.int64)
    if not bounds.min < ticks <= bounds.max:
        return None
    return pd.Timestamp(ticks, tz="UTC")


def _usage_estimate(
    group: pd.DataFrame, sample_indices: np.ndarray, threshold: float, config: ForecastConfig,
    historical_reset: bool = False,
) -> dict:
    if "operating_hours" not in group:
        return {}
    hours = group.operating_hours.to_numpy(dtype=float)
    if historical_reset or np.any(np.diff(hours) < 0):
        return {"operating_message": "Se detecta un reinicio o descenso del contador en el histórico; no se proyecta en horas de uso."}
    if len(np.unique(hours)) < 3:
        return {"operating_message": "El contador no tiene variación suficiente para estimar horas de uso."}
    fit = _fit_trend(hours[sample_indices], group.iloc[sample_indices]["_forecast_value"].to_numpy(), config.confidence)
    if fit.level >= np.longdouble(threshold) / fit.y_scale:
        value = float(hours[-1])
        return {
            "operating_hours_at_threshold": value, "operating_hours_low": value,
            "operating_hours_high": value, "remaining_operating_hours": 0.0,
            "operating_message": "La tendencia ajustada ya alcanza el umbral en el contador actual.",
        }
    if fit.low <= 0 or fit.slope <= 0:
        return {"operating_message": "Sin degradación apreciable respecto a las horas de uso."}
    remaining, low, high = _projection(fit, threshold)
    if remaining is None or low is None or high is None:
        return {"operating_message": "La estimación en horas de uso queda fuera del rango numérico utilizable."}
    values = [_finite_float(np.longdouble(hours[-1]) + val) for val in [remaining, low, high]]
    if any(value is None for value in values):
        return {"operating_message": "El valor proyectado del contador supera el rango numérico utilizable."}
    return {
        "operating_hours_at_threshold": values[0], "operating_hours_low": values[1],
        "operating_hours_high": values[2], "remaining_operating_hours": remaining,
        "operating_message": "Horas de uso orientativas; no se convierten a calendario suponiendo funcionamiento continuo.",
    }


def estimate_maintenance(
    df: pd.DataFrame, asset_id: str, sensor: str, threshold: float | None,
    config: ForecastConfig = ForecastConfig(),
) -> ForecastResult:
    """Proyecta una señal creciente hasta un umbral superior elegido por el usuario.

    Usa únicamente el último segmento tras huecos y la ventana reciente; Theil–Sen
    se limita a ``max_points`` observaciones existentes repartidas en el tiempo.
    Se exige pendiente inferior positiva. No se extrapola más allá del horizonte
    configurado ni se rellenan huecos. Los límites son una banda orientativa y no
    un intervalo calibrado de llegada al umbral o de fallo.
    """
    if threshold is None:
        return ForecastResult("not_configured", "Configura un umbral superior para obtener una estimación orientativa.")
    if not np.isfinite(threshold):
        raise ValueError("El umbral debe ser finito.")
    if sensor not in SENSORS or sensor not in df:
        raise ValueError("Selecciona un sensor presente en el histórico.")
    group = df.loc[df.asset_id.eq(asset_id)].sort_values("timestamp").copy()
    if group.empty:
        raise ValueError("La máquina seleccionada no aparece en el histórico.")
    historical_reset = "operating_hours" in group and bool(
        np.any(np.diff(group.operating_hours.to_numpy(dtype=float)) < 0)
    )
    warnings = quality_warnings(group)
    steps, _ = _time_steps(group)
    previous = pd.Series(steps).where(steps > 0).shift(1).rolling(48, min_periods=1).median().to_numpy()
    gaps = np.flatnonzero(steps > previous * 3) + 1
    if gaps.size:
        group = group.iloc[int(gaps[-1]):]
        warnings.append("La tendencia utiliza solo el último segmento posterior a un hueco, sin interpolar.")
    group = group.tail(config.window).copy()
    common = {"warnings": warnings, "n_points": len(group)}
    if len(group) < config.min_points:
        return ForecastResult(
            "insufficient_data",
            f"Datos insuficientes: hacen falta {config.min_points} lecturas recientes tras el último hueco; hay {len(group)}.",
            **common,
        )
    ticks = group.timestamp.astype("int64").to_numpy()
    reference = int(ticks[0])
    hours = np.fromiter(
        ((int(tick) - reference) / 3.6e12 for tick in ticks), dtype=float, count=len(ticks)
    )
    if len(group) <= config.max_points:
        indices = np.arange(len(group))
    else:
        targets = np.linspace(hours[0], hours[-1], config.max_points)
        indices = np.unique(np.clip(np.searchsorted(hours, targets), 0, len(group) - 1))
    if len(indices) < 3:
        return ForecastResult("insufficient_data", "No hay suficientes instantes distintos para ajustar la tendencia.", **common)
    group["_forecast_value"] = group[sensor]
    fit = _fit_trend(hours[indices], group.iloc[indices][sensor].to_numpy(dtype=float), config.confidence)
    level = _finite_float(np.longdouble(fit.level) * fit.y_scale)
    slope = _finite_float(np.longdouble(fit.slope) * fit.y_scale / fit.x_span)
    low_slope = _finite_float(np.longdouble(fit.low) * fit.y_scale / fit.x_span)
    high_slope = _finite_float(np.longdouble(fit.high) * fit.y_scale / fit.x_span)
    common.update(current_level=level, slope_per_hour=slope, slope_low=low_slope, slope_high=high_slope)
    if level is None or any(value is None for value in [slope, low_slope, high_slope]):
        return ForecastResult("numerical_limit", "Los valores exceden el rango numérico de una tendencia fiable; no se fuerza una fecha.", **common)
    last = group.timestamp.iloc[-1]
    if level >= threshold:
        return ForecastResult(
            "threshold_reached", "La tendencia ajustada ya alcanza el umbral superior configurado.",
            predicted_at=last, earliest_at=last, latest_at=last,
            remaining_hours=0.0, remaining_hours_low=0.0, remaining_hours_high=0.0,
            **_usage_estimate(group, indices, threshold, config, historical_reset), **common,
        )
    if fit.low <= 0 or fit.slope <= 0:
        return ForecastResult(
            "no_degradation", "Sin degradación apreciable: la tendencia no es claramente creciente.",
            **_usage_estimate(group, indices, threshold, config, historical_reset), **common,
        )
    remaining, early, late = _projection(fit, threshold)
    warnings.append(
        "Banda orientativa basada en pendiente y dispersión residual; no es un intervalo calibrado de fecha ni una probabilidad de fallo."
    )
    if remaining is None or remaining > config.max_horizon_hours:
        return ForecastResult(
            "beyond_horizon",
            f"La llegada al umbral supera el horizonte de {config.max_horizon_hours:g} horas; no se fuerza una fecha.",
            **common,
        )
    if late is not None and late > config.max_horizon_hours:
        late = None
        warnings.append("El extremo tardío de la banda supera el horizonte; queda indeterminado.")
    predicted = _date_after(last, remaining)
    earliest = _date_after(last, early) if early is not None and early <= config.max_horizon_hours else None
    latest = _date_after(last, late)
    if predicted is None:
        return ForecastResult("numerical_limit", "La fecha proyectada queda fuera del rango de fechas admitido.", **common)
    return ForecastResult(
        "estimated", "Estimación orientativa de llegada al umbral si continúa la tendencia reciente.",
        predicted_at=predicted, earliest_at=earliest, latest_at=latest,
        remaining_hours=remaining, remaining_hours_low=early, remaining_hours_high=late,
        **_usage_estimate(group, indices, threshold, config, historical_reset), **common,
    )
