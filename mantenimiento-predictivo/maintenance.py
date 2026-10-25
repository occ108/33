"""Plan orientativo de revisión por equipo, sin órdenes ni persistencia de datos."""
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from analysis import ForecastConfig, SENSORS, estimate_maintenance


@dataclass(frozen=True)
class PlanConfig:
    """Reglas organizativas configurables; no son límites normativos."""
    lead_hours: float = 72
    freshness_hours: float = 72
    planning_days: int = 30

    def __post_init__(self) -> None:
        if not np.isfinite(self.lead_hours) or not 0 <= self.lead_hours <= 2160:
            raise ValueError('La antelación debe estar entre 0 y 2160 horas.')
        if not np.isfinite(self.freshness_hours) or self.freshness_hours <= 0:
            raise ValueError('La antigüedad admitida debe ser positiva y finita.')
        if not 1 <= self.planning_days <= 90:
            raise ValueError('El plazo de planificación debe estar entre 1 y 90 días.')


def build_maintenance_plan(
    df: pd.DataFrame, thresholds: Mapping[tuple[str, str], float],
    reference_time: pd.Timestamp, config: PlanConfig = PlanConfig(),
    forecast_config: ForecastConfig = ForecastConfig(),
) -> pd.DataFrame:
    """Prioriza revisiones respecto a una fecha explícita sin modificar el histórico.

    Rechaza datos atrasados o fechas futuras antes de proponer un plazo actual.
    La revisión orientativa precede al extremo temprano de la banda por la
    antelación elegida. Si la banda no tiene extremo temprano no inventa un plazo.
    No calcula probabilidades, vida útil restante ni órdenes de mantenimiento.
    """
    reference = pd.Timestamp(reference_time)
    if pd.isna(reference):
        raise ValueError('La fecha de referencia no puede estar vacía.')
    reference = reference.tz_localize('UTC') if reference.tzinfo is None else reference.tz_convert('UTC')
    assets = set(df.asset_id)
    for (asset, sensor), limit in thresholds.items():
        if asset not in assets or sensor not in SENSORS or sensor not in df or not np.isfinite(limit):
            raise ValueError('Hay un umbral sin máquina/sensor válido o sin valor finito.')
    rows = []
    for asset, group in df.sort_values(['asset_id','timestamp']).groupby('asset_id', sort=False):
        last = group.timestamp.iloc[-1]
        age = (int(reference.value) - int(last.value)) / 3.6e12
        row = {'Máquina': asset, 'Prioridad': '', 'Motivo': '', 'Última lectura (UTC)': last,
               'Revisar antes de (UTC)': pd.NaT, 'Sensor de referencia': '',
               'Cruce orientativo (UTC)': pd.NaT, 'Banda inicial (UTC)': pd.NaT,
               'Banda final (UTC)': pd.NaT, 'Horas de uso hasta el umbral': np.nan}
        rank = 4
        if age < -.25:
            row.update(Prioridad='Revisar fechas', Motivo='Hay lecturas futuras respecto a la referencia. Confirma zona horaria y reloj.')
        elif age > config.freshness_hours:
            row.update(Prioridad='Actualizar datos', Motivo=f'La última lectura tiene {age:.1f} horas respecto a la referencia. No se propone una fecha actual con ese histórico.')
        elif len(group) < forecast_config.min_points:
            row.update(Prioridad='Datos insuficientes', Motivo=f'Se necesitan al menos {forecast_config.min_points} lecturas recientes para estimar una tendencia.')
        else:
            limits = [(sensor, thresholds[(asset,sensor)]) for sensor in SENSORS if (asset,sensor) in thresholds]
            if not limits:
                row.update(Prioridad='Configurar umbrales', Motivo='Configura límites por sensor con el responsable de mantenimiento.')
            else:
                candidates = []
                for sensor, limit in limits:
                    estimate = estimate_maintenance(group, asset, sensor, limit, forecast_config)
                    candidate = dict(row)
                    candidate['Sensor de referencia'] = sensor
                    candidate['Motivo'] = estimate.message
                    candidate['Horas de uso hasta el umbral'] = estimate.remaining_operating_hours
                    if float(group[sensor].iloc[-1]) >= limit or estimate.status == 'threshold_reached':
                        candidate.update(Prioridad='Revisión prioritaria', Motivo='La última lectura o la tendencia alcanza el umbral configurado. Confirmar la señal; no demuestra una avería.')
                        candidate['Revisar antes de (UTC)'] = reference
                        candidate['Horas de uso hasta el umbral'] = 0.0 if estimate.status == 'threshold_reached' else np.nan
                        priority = 0
                    elif estimate.status == 'estimated' and estimate.earliest_at is not None:
                        try:
                            due = pd.Timestamp(int(estimate.earliest_at.value) - int(round(config.lead_hours * 3.6e12)), tz='UTC')
                            hours_until = (int(due.value) - int(reference.value)) / 3.6e12
                            priority = 0 if hours_until <= 0 else 1 if hours_until <= config.planning_days * 24 else 2
                            candidate['Prioridad'] = ('Revisión prioritaria','Planificar revisión','Seguimiento')[priority]
                            candidate['Revisar antes de (UTC)'] = max(due,reference)
                            candidate['Cruce orientativo (UTC)'] = estimate.predicted_at
                            candidate['Banda inicial (UTC)'] = estimate.earliest_at
                            candidate['Banda final (UTC)'] = estimate.latest_at
                            candidate['Motivo'] = f'Revisar con {config.lead_hours:g} h de antelación al extremo temprano de la banda orientativa; confirmar condiciones de operación.'
                        except (OverflowError, ValueError):
                            priority = 4
                            candidate.update(Prioridad='Revisar fechas', Motivo='El plazo de revisión supera el rango de fechas admitido.')
                    elif estimate.status in ('no_degradation','beyond_horizon'):
                        priority = 3
                        candidate['Prioridad'] = 'Seguimiento sin fecha'
                    else:
                        priority = 4
                        candidate['Prioridad'] = 'Revisar datos'
                    if estimate.warnings:
                        candidate['Motivo'] += ' Consultar los avisos de calidad e incertidumbre de la estimación.'
                    candidates.append((priority,candidate))
                rank,row = min(candidates,key=lambda item:(item[0],item[1]['Revisar antes de (UTC)'].value if pd.notna(item[1]['Revisar antes de (UTC)']) else pd.Timestamp.max.value))
        row['_rank'] = rank
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['_rank','Revisar antes de (UTC)','Máquina'],na_position='last').drop(columns='_rank').reset_index(drop=True)
