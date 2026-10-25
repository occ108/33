"""Manufacturer-independent catalogue. No maintenance limits are inferred."""
import json
from pathlib import Path
CATALOG=json.loads((Path(__file__).parent/'catalog/automocion.json').read_text())
PARAMETERS=CATALOG['parameters']
LEGACY=('temperature_c','vibration_mm_s','pressure_bar')
SENSORS=LEGACY+tuple(PARAMETERS)
