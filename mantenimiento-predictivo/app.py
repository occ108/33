"""Axion: session-local multilingual maintenance review."""
from pathlib import Path
from dataclasses import asdict
import json
import hashlib
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
from automotive import CATALOG,PARAMETERS,SENSORS,LEGACY
from data_contract import load_csv,DataError,MAX_BYTES,MAX_ROWS
from i18n import translate,t,number,date,initial_language
from analysis import analyze_anomalies,AnalysisConfig
from vehicle_analysis import forecast_vehicle
from exports import safe_csv
from maintenance import build_maintenance_plan
from catalog import load_catalog
ROOT=Path(__file__).parent
EXAMPLE=ROOT/'examples/sensores_demo.csv'

def main():
 st.set_page_config(page_title='Axion',page_icon=str(ROOT/'assets/favicon.png'),layout='wide')
 if 'lang' not in st.session_state:
  st.session_state.lang=initial_language(st.query_params.get('lang'),st.context.headers.get('Accept-Language',''))
 lang=st.session_state.lang
 st.logo(str(ROOT/'assets/logo.svg'))
 st.radio(t('language'),['es','en','de'],horizontal=True,format_func=lambda k,locale=lang:translate(locale,'language_'+k),key='language_choice',index=['es','en','de'].index(lang),on_change=change_language)
 lang=st.session_state.lang
 st.markdown(f'<h1 style="font-size:1.8rem;margin-bottom:0">{t("product")}</h1>',unsafe_allow_html=True)
 st.caption(t('tagline'))
 st.info(t('honesty'))
 st.session_state.vehicle=st.session_state.get('selected_vehicle','car')
 vehicle=st.selectbox(t('vehicle'),list(CATALOG['vehicles']),format_func=lambda k:CATALOG['vehicles'][k][lang],key='vehicle',index=None,on_change=remember_selection,args=('vehicle','selected_vehicle'))
 options=[k for k,c in CATALOG['components'].items() if vehicle in c['vehicles']]
 st.session_state.component=st.session_state.get('selected_component') if st.session_state.get('selected_component') in options else options[0]
 component=st.selectbox(t('component'),options,format_func=lambda k:CATALOG['components'][k]['name'][lang],key='component',index=None,on_change=remember_selection,args=('component','selected_component'))
 spec=CATALOG['components'][component]
 st.caption(spec['description'][lang])
 if spec['critical']:st.warning(t('critical'))
 st.caption(t('interval',metric=spec['usage_metric']))
 from manual_entry import render_manual_entry
 render_manual_entry(vehicle,component,spec,lang)
 st.session_state.language_switch=False
 if st.button(t('demo'),key='demo',type='secondary'):
  st.session_state.pop('manual_snapshot',None)
  st.session_state.content=(ROOT/'examples/vehicles/fleet.csv').read_bytes();st.session_state.synthetic=True
  st.session_state.sensor='brake_pad_mm'
  st.rerun()
 st.caption(t('privacy'));st.caption(t('cold'))
 if 'content' not in st.session_state:
  if 'manual_snapshot' not in st.session_state:st.info(t('empty'))
  render_resources(lang);return
 try:
  df=load_csv(st.session_state.content)
 except DataError as error:
  st.error(t(error.code,**error.params));render_resources(lang);return
 st.session_state.validated_data=df
 if st.session_state.get('synthetic'):st.caption(t('synthetic'))
 for code,params in df.attrs.get('warnings',[]):st.warning(t(code,**params))
 a,b=st.columns(2);a.metric(t('rows'),number(len(df),lang),border=True);b.metric(t('assets'),number(df.asset_id.nunique(),lang),border=True)
 asset=st.selectbox(t('asset'),df.asset_id.unique().tolist(),key='asset')
 sensors=[s for s in SENSORS if s in df]
 sensor=st.selectbox(t('sensor'),sensors,format_func=lambda k:PARAMETERS[k]['name'][lang] if k in PARAMETERS else t(k),key='sensor')
 group=df[df.asset_id.eq(asset)]
 if any(c['critical'] and sensor in c['parameters'] for c in CATALOG['components'].values()):st.warning(t('critical'))
 if 'component' in group and CATALOG['components'][group.component.iloc[-1]]['critical']:st.warning(t('critical'))
 with st.sidebar:
  st.header(t('controls'))
  window=st.number_input(t('window'),24,336,48,24,key='window')
  sensitivity=st.number_input(t('sensitivity'),1.,20.,4.5,.5,key='sensitivity')
  st.caption(t('oem'))
  setting=f'{hashlib.sha256(st.session_state.content).hexdigest()[:12]}:{asset}:{sensor}'
  enabled=st.checkbox(t('enable'),key='enabled:'+setting)
  warning_limit=st.number_input(t('warning_limit'),value=None,disabled=not enabled,key='warning:'+setting)
  default=PARAMETERS.get(sensor,{}).get('direction','above')
  directions=['below','above'] if default=='below' else ['above','below']
  direction=st.radio(t('direction'),directions,format_func=lambda k,locale=lang:translate(locale,'lower' if k=='below' else 'upper'),key='direction:'+setting)
  if default=='both':
   low_limit=st.number_input(t('low_limit'),value=None,disabled=not enabled,key='low:'+setting)
   high_limit=st.number_input(t('high_limit'),value=None,disabled=not enabled,key='high:'+setting)
   if low_limit is not None and high_limit is not None and low_limit>=high_limit:
    st.error(t('error_limits'));return
   limit=low_limit if direction=='below' else high_limit
  else:limit=st.number_input(t('limit'),value=None,disabled=not enabled,key='limit:'+setting)
 cfg=AnalysisConfig(window=int(window),z_threshold=float(sensitivity))
 digest=hashlib.sha256(st.session_state.content).hexdigest()
 cache_key=(digest,int(window),float(sensitivity))
 if st.session_state.get('analysis_key')!=cache_key:
  with st.spinner(t('checking')):st.session_state.result=analyze_anomalies(df,cfg)
  st.session_state.analysis_key=cache_key
 result=st.session_state.result
 selected=result.readings[result.readings.asset_id.eq(asset)]
 unit=PARAMETERS.get(sensor,{}).get('unit',{'temperature_c':'°C','vibration_mm_s':'mm/s RMS','pressure_bar':'bar'}.get(sensor,''))
 if enabled and limit is not None:
  crossed=float(group[sensor].iloc[-1]) <= limit if direction=='below' else float(group[sensor].iloc[-1]) >= limit
 else:crossed=False
 if enabled and default=='both':
  crossed=(low_limit is not None and float(group[sensor].iloc[-1])<=low_limit) or (high_limit is not None and float(group[sensor].iloc[-1])>=high_limit)
 ready=bool(selected[sensor+'__ready'].iloc[-1]);flags=int(selected.tail(int(window))[sensor+'__anomaly'].sum())
 state=t('threshold_reached') if crossed else t('short') if not ready else t('amber') if flags else t('green')
 if enabled and warning_limit is not None and not crossed:
  warned=float(group[sensor].iloc[-1]) <= warning_limit if direction=='below' else float(group[sensor].iloc[-1]) >= warning_limit
  if warned:state=t('amber')
 color='#DC2626' if crossed else '#D97706' if flags or not ready or state==t('amber') else '#16A34A'
 icon='🔴' if crossed else '⚠️' if color=='#D97706' else '●'
 with st.container(border=True):st.markdown(f'<p style="border-left:5px solid {color};padding:12px;color:#1F2937">{icon} {state}</p>',unsafe_allow_html=True)
 data_tab,anomaly_tab,maintenance_tab=st.tabs([t('data'),t('anomalies'),t('maintenance')])
 with data_tab:
  preview=df.head(100).copy()
  for col in preview:
   if pd.api.types.is_numeric_dtype(preview[col]):preview[col]=preview[col].map(lambda v:number(v,lang))
  preview.timestamp=preview.timestamp.map(lambda v:date(v,lang))
  st.dataframe(preview,hide_index=True)
 with anomaly_tab:
  fleet=[]
  for aid,g in result.readings.groupby('asset_id',sort=False):
   sufficient=all(bool(g[c+'__ready'].iloc[-1]) for c in sensors)
   unusual=any(bool(g.tail(int(window))[c+'__anomaly'].any()) for c in sensors)
   reached=False
   for c in sensors:
    key=f'{digest[:12]}:{aid}:{c}'
    if not st.session_state.get('enabled:'+key):continue
    mode=st.session_state.get('direction:'+key,PARAMETERS.get(c,{}).get('direction','above'))
    candidates=[('below',st.session_state.get('low:'+key)),('above',st.session_state.get('high:'+key))] if PARAMETERS.get(c,{}).get('direction')=='both' else [(mode,st.session_state.get('limit:'+key))]
    reached=reached or any(v is not None and (float(g[c].iloc[-1])<=v if side=='below' else float(g[c].iloc[-1])>=v) for side,v in candidates)
   code='threshold_reached' if reached else 'short' if not sufficient else 'amber' if unusual else 'green'
   fleet.append({t('asset'):aid,t('status'):('🔴 ' if code=='threshold_reached' else '⚠️ ' if code!='green' else '● ')+t(code)})
  st.dataframe(pd.DataFrame(fleet),hide_index=True)
  if result.warnings:st.warning(t('quality'))
  plot=_chart_sample(selected,sensor).copy()
  if len(plot)<len(selected):st.caption(t('chart_reduced',count=number(len(plot),lang)))
  # Render formatted time strings to avoid browser-language-dependent dates.
  plot['_date']=plot.timestamp.map(lambda v:date(v,lang));plot['_value']=plot[sensor].map(lambda v:number(v,lang))
  x=alt.X('timestamp:T',title=t('time'),scale=alt.Scale(type='utc'),axis=alt.Axis(labelExpr="utcFormat(datum.value, '%d.%m.%Y')" if lang!='en' else "utcFormat(datum.value, '%d %b %Y')",labelLimit=130,labelOverlap=True))
  y=alt.Y(f'{sensor}:Q',title=f'{PARAMETERS[sensor]["name"][lang] if sensor in PARAMETERS else sensor} [{unit}]',axis=alt.Axis(labelExpr="replace(format(datum.value, '.2~f'), '.', ',')" if lang!='en' else "format(datum.value, '.2~f')"))
  chart=alt.Chart(plot).mark_line(color='#1F4E79').encode(x=x,y=y,tooltip=[alt.Tooltip('_date:N',title=t('time')),alt.Tooltip('_value:N',title=t('values'))])
  marks=alt.Chart(plot[plot[sensor+'__anomaly']]).mark_circle(color='#DC2626',size=50).encode(x=x,y=y)
  if enabled and limit is not None:chart=chart+alt.Chart(pd.DataFrame({'threshold':[limit]})).mark_rule(color='#D97706').encode(y='threshold:Q')
  st.altair_chart(chart+marks,width='stretch')
  st.download_button(t('download'),safe_csv(result.readings),'results.csv','text/csv',key='results_download')
 with maintenance_tab:
  metric='hours' if sensor in LEGACY else spec['usage_metric']
  # A CSV component takes precedence over the landing-page template selection.
  if sensor not in LEGACY:metric='km' if 'odometer_km' in df else 'hours'
  estimate=forecast_vehicle(df,asset,sensor,limit if enabled else None,direction,metric)
  st.write(t(estimate.status))
  if estimate.predicted_at is not None:
   st.write(t('estimate',date=date(estimate.predicted_at,lang)))
   st.write(t('band',low=date(estimate.earliest_at,lang),high=date(estimate.latest_at,lang)))
  if estimate.operating_hours_at_threshold is not None:
   st.write(t('usage_estimate',unit=metric if metric in ('km',) else t('hours'),value=number(estimate.operating_hours_at_threshold,lang),low=number(estimate.operating_hours_low,lang),high=number(estimate.operating_hours_high,lang)))
  else:st.caption(t('counter'))
  if estimate.predicted_at is not None and estimate.current_level is not None and estimate.slope_per_hour is not None:
   last=group.timestamp.iloc[-1]
   horizon=min(float(estimate.remaining_hours or 0),2160.)
   if horizon>0:
    hours=np.linspace(0,horizon,30)
    future=pd.DataFrame({'_date':[date(pd.Timestamp(int(last.value)+int(h*3.6e12),tz='UTC'),lang) for h in hours],'mean':estimate.current_level+hours*estimate.slope_per_hour,'low':estimate.current_level+hours*(estimate.slope_low or 0),'high':estimate.current_level+hours*(estimate.slope_high or 0)})
    future['timestamp']=[pd.Timestamp(int(last.value)+int(h*3.6e12),tz='UTC') for h in hours]
    axis=alt.X('timestamp:T',scale=alt.Scale(type='utc'),title=t('time'),axis=alt.Axis(labelExpr="utcFormat(datum.value, '%d.%m.%Y')" if lang!='en' else "utcFormat(datum.value, '%d %b %Y')",labelOverlap=True))
    area=alt.Chart(future).mark_area(opacity=.15,color='#1F4E79').encode(x=axis,y=alt.Y('low:Q',title=unit,axis=alt.Axis(labelExpr="replace(format(datum.value, '.2~f'), '.', ',')" if lang!='en' else "format(datum.value, '.2~f')")),y2='high:Q')
    line=alt.Chart(future).mark_line(color='#1F4E79').encode(x=axis,y='mean:Q')
    st.altair_chart(area+line,width='stretch')
  st.caption(t('uncertainty'))
  st.subheader(t('plan'))
  mode=st.radio(t('plan'),['today','historical'],format_func=lambda k,locale=lang:translate(locale,k),key='plan_reference')
  reference=pd.Timestamp.now(tz='UTC') if mode=='today' else df.timestamp.max()
  plan_data=df.copy();plan_limits={}
  prefix=hashlib.sha256(st.session_state.content).hexdigest()[:12]
  for aid in df.asset_id.unique():
   for param in sensors:
    key=f'{prefix}:{aid}:{param}'
    sign=st.session_state.get('direction:'+key,PARAMETERS.get(param,{}).get('direction','above'))
    value=st.session_state.get(('low:' if sign=='below' else 'high:')+key) if PARAMETERS.get(param,{}).get('direction')=='both' else st.session_state.get('limit:'+key)
    if st.session_state.get('enabled:'+key) and value is not None:
     plan_limits[(aid,param)]=-value if sign=='below' else value
     if sign=='below':plan_data.loc[plan_data.asset_id.eq(aid),param]=-plan_data.loc[plan_data.asset_id.eq(aid),param]
  plan=build_maintenance_plan(plan_data,plan_limits,reference)
  keys={'Revisión prioritaria':'urgent','Planificar revisión':'schedule','Seguimiento':'monitor','Seguimiento sin fecha':'monitor','Datos insuficientes':'short','Configurar umbrales':'configure','Actualizar datos':'stale','Revisar fechas':'dates','Revisar datos':'review'}
  visible=pd.DataFrame({t('asset'):plan['Máquina'],t('priority'):plan['Prioridad'].map(lambda v:t(keys[v])),t('why'):plan['Prioridad'].map(lambda v:t(keys[v]+'_why')),t('review_date'):plan['Revisar antes de (UTC)'].map(lambda v:date(v,lang))})
  st.dataframe(visible,hide_index=True)
  st.download_button(t('plan_download'),safe_csv(visible),'review_plan.csv','text/csv',key='plan_download')
  st.download_button(t('download_estimates'),safe_csv(pd.DataFrame([{'asset_id':asset,'sensor':sensor,**asdict(estimate)}]).drop(columns=['message','warnings','operating_message'])),'estimate.csv','text/csv',key='estimate_download')
 render_resources(lang)

def remember_selection(widget,stored):
 if st.session_state.get('language_switch'):return
 value=st.session_state[widget]
 choices=CATALOG['vehicles'] if widget=='vehicle' else {k:c['name'] for k,c in CATALOG['components'].items()}
 for canonical,names in choices.items():
  if value==canonical or value in names.values():st.session_state[stored]=canonical;break

def change_language():
 st.session_state.language_switch=True
 st.session_state.lang=st.session_state.language_choice
 st.query_params['lang']=st.session_state.lang

def render_resources(lang):
 with st.expander(t('resources')):
  with st.expander(t('format')):
   st.write(t('format_help'))
   if st.button(t('small_demo'),key='small_demo'):
    st.session_state.pop('manual_snapshot',None);st.session_state.content=EXAMPLE.read_bytes();st.session_state.synthetic=True;st.rerun()
  query=st.text_input(t('search'),key='resource_search')
  for entry in load_catalog()['datasets']:
   if query.casefold() not in entry['name'].casefold():continue
   st.markdown('**'+entry['name']+'**')
   st.caption(t('license',license=entry['license'] if entry['license_verified'] else t('unknown')))
   kind={'Sintético':'kind_synthetic','Simulado':'kind_synthetic','Banco experimental':'kind_bench','Operación real':'kind_real','Proceso industrial':'kind_process'}[entry['data_kind']]
   st.caption(t('resource_meta',kind=t(kind),size=number(entry['records'],lang) if entry['records'] else t('unknown')))
   st.link_button(t('source'),entry['url'])
   with st.expander(t('details')):st.write(t('source_note'))
  with st.expander(t('about')):st.write(t('about_body'))

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

if __name__ == "__main__":
 main()
