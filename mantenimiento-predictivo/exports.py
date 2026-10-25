"""Exportaciones de resultados sin persistencia ni fórmulas ejecutables."""

from __future__ import annotations

import csv
from io import StringIO
import math

import pandas as pd


def _safe_cell(value: object) -> str:
    """Convierte un escalar a texto y neutraliza posibles fórmulas de hoja de cálculo."""
    if value is None or value is pd.NA or value is pd.NaT:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    # Las celdas habituales evitan consultar pandas.isna en cada iteración.
    if not isinstance(value, (str, int, float, bool, pd.Timestamp)):
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def safe_csv(df: pd.DataFrame) -> bytes:
    """Devuelve CSV UTF-8 sin alterar ``df`` y protege celdas y cabeceras.

    Ante ``=``, ``+``, ``-`` o ``@``, incluso después de espacios, tabuladores
    o saltos de línea iniciales, se antepone un apóstrofe. Esta decisión también
    convierte los números negativos en texto en la hoja de cálculo: se prioriza
    impedir la ejecución de fórmulas sobre conservar su tipo numérico al exportar.
    Los valores ausentes se escriben como campos vacíos. Se recorren las filas
    sin crear una copia del DataFrame de cadenas. No se guarda ningún archivo.
    """
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(_safe_cell(column) for column in df.columns)
    for row in df.itertuples(index=False, name=None):
        writer.writerow(_safe_cell(value) for value in row)
    return buffer.getvalue().encode("utf-8")
