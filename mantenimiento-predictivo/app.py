"""Interfaz de la fase 2: datos, indicios de anomalía y proyecciones orientativas."""

import csv
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from analysis import AnalysisConfig, ForecastConfig, analyze_anomalies, estimate_maintenance
from exports import safe_csv
from catalog import render_catalog


# 1. Contrato de datos y límites de esta primera versión.
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
SENSORS = ("temperature_c", "vibration_mm_s", "pressure_bar")
REQUIRED = {"timestamp", "asset_id"}
EXAMPLE = Path(__file__).parent / "examples" / "sensores_demo.csv"


# 2. Lectura y validación independientes de la interfaz.
def load_csv(content: bytes) -> pd.DataFrame:
    """Lee UTF-8, delimitador coma y punto decimal. Nunca guarda el CSV."""
    if len(content) > MAX_BYTES:
        raise ValueError("El archivo supera el límite de 10 MiB.")
    try:
        decoded = content.decode("utf-8-sig")
        header = next(csv.reader(StringIO(decoded)), [])
        if len(header) != len(set(header)):
            raise ValueError("Hay nombres de columnas duplicados.")
        df = pd.read_csv(BytesIO(content), dtype=str, nrows=MAX_ROWS + 1)
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError("Usa un CSV UTF-8 con comas como separador.") from exc

    if df.empty:
        raise ValueError("El CSV debe contener al menos una lectura.")
    if len(df) > MAX_ROWS:
        raise ValueError("El CSV supera el límite de 100.000 lecturas.")
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}.")
    sensors = [column for column in SENSORS if column in df.columns]
    if not sensors:
        raise ValueError(f"Incluye al menos un sensor: {', '.join(SENSORS)}.")

    df["asset_id"] = df["asset_id"].fillna("").str.strip()
    if df["asset_id"].eq("").any():
        raise ValueError("Cada lectura debe identificar su máquina en asset_id.")
    df["timestamp"] = pd.to_datetime(
        df["timestamp"], format="ISO8601", errors="coerce", utc=True
    )
    if df["timestamp"].isna().any():
        raise ValueError("Hay fechas vacías o inválidas; utiliza formato ISO 8601.")
    if df.duplicated(["asset_id", "timestamp"]).any():
        raise ValueError("Hay lecturas duplicadas para una misma máquina y fecha.")

    numeric = sensors + (["operating_hours"] if "operating_hours" in df else [])
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if not np.isfinite(df[column].to_numpy(dtype=float)).all():
            raise ValueError(f"La columna {column} contiene valores vacíos o no numéricos.")
    if "operating_hours" in df and df["operating_hours"].lt(0).any():
        raise ValueError("Las horas de uso no pueden ser negativas.")
    return df.sort_values(["asset_id", "timestamp"]).reset_index(drop=True)


# 3. Interfaz: toda la información de trabajo permanece en la sesión del usuario.
SENSOR_LABELS = {
    "temperature_c": "Temperatura (°C)",
    "vibration_mm_s": "Vibración (mm/s RMS)",
    "pressure_bar": "Presión (bar)",
}
LARGE_EXAMPLE = EXAMPLE.parent / "synthetic" / "sensores_90d.csv"


def _traffic_lights(result, thresholds: dict, window: int) -> pd.DataFrame:
    rows = []
    sensors = [sensor for sensor in SENSORS if sensor in result.readings]
    for asset, group in result.readings.groupby("asset_id", sort=False):
        recent = group.tail(window)
        crossed = [SENSOR_LABELS[s] for s in sensors if (asset, s) in thresholds and float(group[s].iloc[-1]) >= thresholds[(asset, s)]]
        ready = all(bool(group[s + "__ready"].iloc[-1]) for s in sensors)
        found = sum(int(recent[s + "__anomaly"].sum()) for s in sensors)
        joint = int(recent.if_anomaly.sum())
        quality = any(w.startswith(str(asset) + ":") and ("muestreo irregular" in w or "hueco" in w) for w in result.warnings)
        if crossed:
            state, why = "🔴 Rojo", "La última lectura alcanza el umbral configurado: " + ", ".join(crossed) + ". Revisar la señal; no demuestra una avería."
        elif not ready:
            state, why = "🟠 Ámbar", "Datos insuficientes en el tramo reciente: todavía no se puede evaluar."
        elif quality:
            state, why = "🟠 Ámbar", "Hay huecos o muestreo irregular; revisa los avisos de calidad."
        elif found or joint:
            state, why = "🟠 Ámbar", f"En las últimas {len(recent)} lecturas: {found} indicios por sensor y {joint} indicios conjuntos. Conviene revisarlos."
        else:
            state, why = "🟢 Verde", f"Sin indicios detectados en las últimas {len(recent)} lecturas. Esto no garantiza ausencia de problemas."
        rows.append({"Máquina": asset, "Semáforo": state, "Por qué": why})
    return pd.DataFrame(rows)


def _chart_sample(group: pd.DataFrame, sensor: str, limit: int = 3000) -> pd.DataFrame:
    """Acota la vista conservando los indicios escasos y una referencia temporal."""
    if len(group) <= limit:
        return group
    marked = np.flatnonzero(group[sensor + "__anomaly"].to_numpy())
    marked_limit = limit * 2 // 3
    if len(marked) > marked_limit:
        marked = marked[np.linspace(0, len(marked) - 1, marked_limit, dtype=int)]
    regular = np.linspace(0, len(group) - 1, limit - len(marked), dtype=int)
    return group.iloc[np.unique(np.concatenate([marked, regular]))]


def _anomaly_chart(group: pd.DataFrame, sensor: str) -> None:
    # La vista se acota; las puntuaciones y la descarga conservan todas las filas.
    total, total_marked = len(group), int(group[sensor + "__anomaly"].sum())
    group = _chart_sample(group, sensor)
    if len(group) < total:
        shown = int(group[sensor + "__anomaly"].sum())
        st.caption(f"Gráfico reducido: {len(group)} de {total} lecturas y {shown} de {total_marked} indicios. La descarga conserva todos los resultados.")
    plot = group[["timestamp", sensor, sensor + "__baseline", sensor + "__anomaly"]].copy()
    plot.columns = ["Fecha", "Lectura", "Referencia", "Indicio"]
    x = alt.X("Fecha:T", title="Fecha (UTC)", scale=alt.Scale(type="utc"))
    base = alt.Chart(plot).encode(x=x)
    reading = base.mark_line(color="#147d92").encode(y=alt.Y("Lectura:Q", title=SENSOR_LABELS[sensor]), tooltip=["Fecha:T", "Lectura:Q"])
    reference = base.mark_line(color="#718096", strokeDash=[5, 4]).encode(y="Referencia:Q")
    marks = base.transform_filter(alt.datum.Indicio).mark_circle(color="#d94635", size=65).encode(y="Lectura:Q", tooltip=["Fecha:T", "Lectura:Q"])
    st.altair_chart(reading + reference + marks, width="stretch")
    st.caption("Azul: lectura · Gris discontinuo: referencia de su pasado · Rojo: indicio por sensor. No es una predicción de fallo.")


def main() -> None:
    st.set_page_config(page_title="Mantenimiento Predictivo Ligero", page_icon="⚙️", layout="wide")
    st.title("Mantenimiento Predictivo Ligero")
    st.caption("Fase 2 · Indicios de anomalía y planificación orientativa")
    st.info("Una variación del sensor no demuestra una avería. Las estimaciones orientan una revisión y no predicen fallos.")
    render_catalog()
    with st.expander("Formato del CSV"):
        st.markdown(
            "Columnas obligatorias: `timestamp` y `asset_id`, más al menos un sensor: "
            "`temperature_c` (°C), `vibration_mm_s` (mm/s RMS) o `pressure_bar` (bar). "
            "`operating_hours` es opcional. Usa UTF-8, comas y punto decimal. "
            "Las fechas sin zona horaria se interpretan como UTC. "
            "Límites: 10 MiB y 100.000 lecturas. No se interpolan ni rellenan datos ausentes."
        )
        st.download_button("Descargar CSV sintético de ejemplo", data=EXAMPLE.read_bytes(), file_name="sensores_demo.csv", mime="text/csv")
        st.download_button("Descargar histórico sintético de 90 días", data=LARGE_EXAMPLE.read_bytes(), file_name="sensores_90d.csv", mime="text/csv")
    demo = st.checkbox("Probar con datos sintéticos")
    large_demo = st.checkbox("Probar histórico de 90 días")
    uploaded = st.file_uploader("Sube el histórico de sensores", type=["csv"], disabled=demo or large_demo)
    st.caption("Los CSV no se guardan. El análisis y los ajustes se mantienen únicamente en tu sesión; no se usa una caché global de datos.")
    if not demo and not large_demo and uploaded is None:
        st.write("Descarga un ejemplo, activa una demostración o sube un CSV para comenzar.")
        return
    if demo and large_demo:
        st.info("Está seleccionado el ejemplo pequeño; desactívalo para utilizar el histórico de 90 días.")
    content = EXAMPLE.read_bytes() if demo else LARGE_EXAMPLE.read_bytes() if large_demo else uploaded.getvalue()
    large_demo = large_demo and not demo
    try:
        df = load_csv(content)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.success("CSV válido. Los datos están listos para explorar.")
    readings, assets = st.columns(2)
    readings.metric("Lecturas", len(df))
    assets.metric("Máquinas", df["asset_id"].nunique())
    selected_asset = st.selectbox("Máquina", df["asset_id"].unique().tolist())
    sensors = [sensor for sensor in SENSORS if sensor in df]
    selected_sensor = st.selectbox("Sensor", sensors, format_func=lambda sensor: SENSOR_LABELS[sensor])

    with st.sidebar:
        st.header("Cómo se revisan las señales")
        window = int(st.number_input("Lecturas de referencia", min_value=24, max_value=336, value=48, step=24, help="Se comparan con lecturas anteriores, sin incluir la actual. Una ventana de lecturas no equivale siempre a horas."))
        min_history = int(st.number_input("Mínimo de lecturas previas", min_value=3, max_value=window, value=min(24, window), step=1))
        sensitivity = float(st.number_input("Desviación necesaria para señalar", min_value=1.0, max_value=20.0, value=4.5, step=0.5, help="Un valor menor señala más cambios y puede producir más falsas alertas."))
        joint = st.checkbox("Análisis conjunto complementario", value=True, help="Compara varios sensores; necesita al menos dos y 193 lecturas. No señala por sí solo qué sensor causa el cambio.")
        trend_window = int(st.number_input("Lecturas recientes para la tendencia", min_value=48, max_value=720, value=168, step=24))
        horizon = int(st.number_input("Horizonte máximo (días)", min_value=1, max_value=90, value=90, step=1))
        st.subheader("Umbrales de " + str(selected_asset))
        st.caption("Define un umbral superior con tu responsable de mantenimiento. Se conserva por máquina y sensor solo en esta sesión.")
        if large_demo and selected_asset == "M-005":
            st.warning("82 °C y 3,8 mm/s son valores orientativos inventados para la demostración: no son normas ni dictámenes.")
        namespace = sha256(content).hexdigest()[:16]
        all_settings = st.session_state.setdefault("phase2_thresholds", {})
        settings = all_settings.setdefault(namespace, {})
        for sensor in sensors:
            setting_key = str(selected_asset) + "\0" + sensor
            illustrative = {"temperature_c": 82.0, "vibration_mm_s": 3.8}.get(sensor) if large_demo and selected_asset == "M-005" else None
            previous = settings.get(setting_key, {"enabled": illustrative is not None, "value": illustrative})
            widget = namespace + sha256(setting_key.encode()).hexdigest()[:16]
            enabled = st.checkbox("Activar umbral · " + SENSOR_LABELS[sensor], value=previous["enabled"], key="enabled_" + widget)
            value = st.number_input("Umbral superior · " + SENSOR_LABELS[sensor], value=previous["value"], step=0.1, disabled=not enabled, key="limit_" + widget, placeholder="Introduce tu límite")
            settings[setting_key] = {"enabled": enabled, "value": value}
        thresholds = {}
        for asset in df.asset_id.unique():
            for sensor in sensors:
                entry = settings.get(str(asset) + "\0" + sensor)
                if entry and entry["enabled"] and entry["value"] is not None:
                    thresholds[(asset, sensor)] = float(entry["value"])

    config = AnalysisConfig(window=window, min_history=min_history, z_threshold=sensitivity, if_enabled=joint)
    result = analyze_anomalies(df, config)
    forecast_config = ForecastConfig(window=trend_window, max_horizon_hours=horizon * 24)
    data_tab, anomalies_tab, maintenance_tab = st.tabs(["Datos", "Anomalías", "Mantenimiento"])
    with data_tab:
        st.dataframe(df.head(100), hide_index=True)
        st.caption("Vista previa de las primeras 100 lecturas. Las fechas se interpretan en UTC.")
        series = df.loc[df.asset_id.eq(selected_asset), ["timestamp", selected_sensor]]
        if len(series) > 3000:
            series = series.iloc[np.linspace(0, len(series) - 1, 3000, dtype=int)]
            st.caption("Vista del histórico reducida a 3.000 puntos; el análisis utiliza todas las lecturas.")
        st.line_chart(series.set_index("timestamp"))
        for warning in result.warnings:
            st.warning(warning)
    with anomalies_tab:
        st.subheader("Semáforo por máquina")
        st.caption(f"Resume las últimas {window} lecturas, no toda la vida de la máquina. Los umbrales solo se usan donde se han configurado.")
        lights = _traffic_lights(result, thresholds, window)
        st.dataframe(lights.head(500), hide_index=True)
        selected = result.readings.loc[result.readings.asset_id.eq(selected_asset)]
        if not selected[selected_sensor + "__ready"].any():
            st.info(f"Datos insuficientes: hacen falta al menos {min_history + 1} lecturas consecutivas para buscar indicios; el CSV pequeño solo es una prueba de carga.")
        st.write("Los puntos rojos son indicios respecto al pasado de este sensor. El análisis conjunto es complementario y no atribuye sus indicios a un sensor concreto.")
        _anomaly_chart(selected, selected_sensor)
        summary = result.summary.rename(columns={"asset_id": "Máquina", "sensor": "Sensor", "n_readings": "Lecturas", "n_evaluated": "Evaluadas", "n_anomalies": "Indicios por sensor", "if_evaluated": "Evaluadas conjuntamente", "if_anomalies": "Indicios conjuntos", "status": "Estado", "why": "Explicación"})
        summary["Sensor"] = summary["Sensor"].map(SENSOR_LABELS)
        summary["Estado"] = summary["Estado"].replace({"evaluado": "Evaluado", "datos_insuficientes": "Datos insuficientes"})
        st.dataframe(summary.head(500), hide_index=True)
        st.download_button("Descargar resultados de anomalías (CSV seguro)", safe_csv(result.readings), "resultados_anomalias.csv", "text/csv")
        st.caption("La descarga protege celdas y cabeceras frente a fórmulas; los números negativos se exportan como texto seguro.")
    with maintenance_tab:
        st.subheader("Llegada orientativa al umbral superior")
        st.write("La fecha supone que continúa la tendencia reciente y no cambian la carga ni el régimen de trabajo. No es una fecha de avería ni una orden de mantenimiento.")
        group = df.loc[df.asset_id.eq(selected_asset)]
        st.caption("Todas las duraciones parten de la última lectura del histórico (UTC): " + group.timestamp.iloc[-1].strftime("%Y-%m-%d %H:%M") + "; no de la fecha actual.")
        if len(group) < forecast_config.min_points:
            st.info(f"Datos insuficientes: hacen falta al menos {forecast_config.min_points} lecturas recientes para estimar una tendencia; hay {len(group)}.")
        forecast = estimate_maintenance(df, selected_asset, selected_sensor, thresholds.get((selected_asset, selected_sensor)), forecast_config)
        st.write(forecast.message)
        if forecast.predicted_at is not None:
            st.write("**Fecha orientativa (UTC):** " + forecast.predicted_at.strftime("%Y-%m-%d %H:%M"))
            st.write(f"**Horas de calendario restantes:** {forecast.remaining_hours:,.1f}")
            early = forecast.earliest_at.strftime("%Y-%m-%d %H:%M") if forecast.earliest_at is not None else "indeterminada"
            late = forecast.latest_at.strftime("%Y-%m-%d %H:%M") if forecast.latest_at is not None else "indeterminada"
            st.write(f"**Banda orientativa (UTC):** {early} a {late}")
            st.caption("Esta banda combina incertidumbre de la pendiente y dispersión de los datos. No tiene una cobertura calibrada del 95 % para la fecha de llegada.")
        if forecast.remaining_operating_hours is not None:
            st.write(f"**Horas de uso restantes:** {forecast.remaining_operating_hours:,.1f}")
            st.write(f"**Contador estimado al umbral:** {forecast.operating_hours_at_threshold:,.1f} h; banda {forecast.operating_hours_low:,.1f}–{forecast.operating_hours_high:,.1f} h acumuladas.")
        st.caption(forecast.operating_message)
        for warning in forecast.warnings:
            st.warning(warning)
        forecast_rows = []
        for sensor in sensors:
            estimate = forecast if sensor == selected_sensor else estimate_maintenance(df, selected_asset, sensor, thresholds.get((selected_asset, sensor)), forecast_config)
            row = {"asset_id": selected_asset, "sensor": sensor, "threshold": thresholds.get((selected_asset, sensor)), **asdict(estimate)}
            row["warnings"] = " | ".join(row["warnings"])
            forecast_rows.append(row)
        st.download_button("Descargar estimaciones (CSV seguro)", safe_csv(pd.DataFrame(forecast_rows)), "estimaciones_mantenimiento.csv", "text/csv")
        st.caption("Selecciona otra máquina para configurar sus propios límites y revisar sus estimaciones.")
    st.caption("Una variación del sensor no demuestra una avería. Sin etiquetas reales de fallos no se puede afirmar predicción de fallos.")


if __name__ == "__main__":
    main()
