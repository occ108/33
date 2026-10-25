"""Fase 1: carga y validación de históricos; todavía no ejecuta modelos."""

import csv
from io import BytesIO, StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


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


# 3. Interfaz: ejemplo, carga, errores comprensibles y vista previa.
def main() -> None:
    st.set_page_config(page_title="Mantenimiento Predictivo Ligero", page_icon="⚙️", layout="wide")
    st.title("Mantenimiento Predictivo Ligero")
    st.caption("Fase 1 · Carga y calidad de datos para pymes industriales")
    st.info("Esta versión valida históricos. Todavía no detecta anomalías ni estima fallos.")
    with st.expander("Formato del CSV", expanded=True):
        st.markdown(
            "Columnas obligatorias: `timestamp` y `asset_id`, más al menos un sensor: "
            "`temperature_c` (°C), `vibration_mm_s` (mm/s RMS) o `pressure_bar` (bar). "
            "`operating_hours` es opcional. Usa UTF-8, comas y punto decimal. "
            "Las fechas sin zona horaria se interpretan como UTC. "
            "Límites: 10 MiB y 100.000 lecturas. No se rellenan datos ausentes automáticamente."
        )
        st.download_button(
            "Descargar CSV sintético de ejemplo", data=EXAMPLE.read_bytes(),
            file_name="sensores_demo.csv", mime="text/csv"
        )

    demo = st.checkbox("Probar con datos sintéticos")
    uploaded = st.file_uploader("Sube el histórico de sensores", type=["csv"], disabled=demo)
    st.caption("No se configura almacenamiento persistente de archivos en esta fase. Usa datos sintéticos o anonimizados.")
    if not demo and uploaded is None:
        st.write("Descarga el ejemplo o activa la demostración para comenzar.")
        return

    try:
        df = load_csv(EXAMPLE.read_bytes() if demo else uploaded.getvalue())
    except ValueError as exc:
        st.error(str(exc))
        return

    st.success("CSV válido. Los datos están listos para explorar.")
    readings, assets = st.columns(2)
    readings.metric("Lecturas", len(df))
    assets.metric("Máquinas", df["asset_id"].nunique())
    st.dataframe(df.head(100), hide_index=True)
    selected_asset = st.selectbox("Máquina", df["asset_id"].unique().tolist())
    selected_sensor = st.selectbox("Sensor", [column for column in SENSORS if column in df])
    series = df.loc[df["asset_id"].eq(selected_asset)].set_index("timestamp")
    st.line_chart(series[[selected_sensor]])
    st.caption("Gráfico exploratorio: una variación del sensor no demuestra una avería.")


# 4. Punto de entrada. El motor analítico se incorporará en la fase 2.
if __name__ == "__main__":
    main()
