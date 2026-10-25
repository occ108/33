"""Session-local translation and explicit locale formatting; no cookies."""
import tomllib
from pathlib import Path
import pandas as pd
LOCALES={lang:tomllib.loads((Path(__file__).parent/'locales'/f'{lang}.toml').read_text()) for lang in ('es','en','de')}
def translate(lang:str,key:str,**params)->str:return LOCALES[lang][key].format(**params)
def t(key:str,**params)->str:
    import streamlit as st
    return translate(st.session_state.get('lang','es'),key,**params)
def number(value,lang:str)->str:
    text=f'{value:,.3f}'.rstrip('0').rstrip('.')
    return text.translate(str.maketrans({',':'.','.':','})) if lang in ('es','de') else text
def date(value,lang:str)->str:
    if value is None or pd.isna(value):return translate(lang,'unknown')
    d=pd.Timestamp(value)
    if lang=='en':return f'{d.day:02d} '+('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[d.month-1])+f' {d.year} {d:%H:%M} UTC'
    return d.strftime('%d.%m.%Y %H:%M UTC')
def initial_language(query,accept:str)->str:
    if query in LOCALES:return query
    for item in accept.split(','):
        lang=item.split(';')[0].strip().split('-')[0].lower()
        if lang in LOCALES:return lang
    return 'es'
