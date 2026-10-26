"""Read-only coverage disclosure; does not change the vehicle comparator."""
import sqlite3
import streamlit as st
from fleet_catalog import summary,eligible_models
from i18n import t,number

def render_fleet_resources(lang):
    with st.expander(t('fleet_title')):
        try:
            info=summary()
            if info['dataset_kind']!='curated':raise ValueError('not_curated')
        except (sqlite3.Error,OSError,ValueError,KeyError):
            st.warning(t('fleet_unavailable'));return
        st.write(t('fleet_counts',year=str(int(info['as_of'][:4])-1),models=number(info['eligible_models'],lang),variants=number(info['verified_variants'],lang),limits=number(info['verified_thresholds'],lang)))
        st.info(t('fleet_boundary'))
        for row in eligible_models():
            model,sale,source=row['model'],row['sale'],row['source']
            st.write(model['make']+' '+model['name'])
            market=t({'EUROPE':'fleet_europe','US':'manual_market_us','FR':'fleet_france'}[sale['market']]) if sale['market'] in ('EUROPE','US','FR') else t('fleet_market_code',code=sale['market'])
            st.caption(t('fleet_sales',year=str(sale['year']),units=number(sale['units'],lang),market=market))
            st.link_button(t('source'),source['url'],key='sales:'+sale['id'])
        st.caption(t('fleet_dtc',count=number(info['dtc_regulatory_categories'],lang)))
