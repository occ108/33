"""Manual snapshot comparison. Inputs and results stay in the current session."""
import streamlit as st
from automotive import PARAMETERS,CATALOG
from manufacturer import REFERENCES,compare_measurements
from i18n import t,number,translate

def render_manual_entry(vehicle,component,spec,lang):
    st.subheader(t('manual_title'))
    st.caption(t('manual_scope'))
    choices=list(PARAMETERS)
    st.session_state['manual_params:'+component]=st.session_state.get('selected_params:'+component,spec['parameters'])
    selected=st.multiselect(t('manual_parameters'),choices,default=None,placeholder=t('manual_parameters'),format_func=lambda k,locale=lang:PARAMETERS[k]['name'][locale]+' ['+PARAMETERS[k]['unit']+']',key='manual_params:'+component,on_change=remember_parameters,args=(component,))
    with st.expander(t('manual_coverage_title')):
        st.write(t('manual_coverage'))
        for ref in REFERENCES[::2]:st.link_button(ref['make']+' '+ref['model']+' · '+ref['manual'],ref['source_url'],key='oem:'+ref['id'])
    with st.form('manual_form:'+component):
        make=st.text_input(t('manual_make'),max_chars=80,key='manual_make')
        model=st.text_input(t('manual_model'),max_chars=80,key='manual_model')
        year=st.number_input(t('manual_year'),1886,2100,2024,key='manual_year')
        version=st.text_input(t('manual_version'),max_chars=120,key='manual_version')
        st.session_state.manual_market=canonical_choice(st.session_state.get('manual_market','other'),{'US':'manual_market_us','other':'manual_market_other'},'other')
        market=st.radio(t('manual_market'),['other','US'],format_func=lambda k,locale=lang:translate(locale,'manual_market_other') if k=='other' else translate(locale,'manual_market_us'),key='manual_market',index=None,horizontal=True)
        st.session_state.manual_conditions=canonical_choice(st.session_state.get('manual_conditions','unknown'),{k:'manual_'+k for k in ['wet','winter','unknown']},'unknown')
        condition=st.radio(t('manual_conditions'),['wet','winter','unknown'],format_func=lambda k,locale=lang:translate(locale,'manual_'+k),key='manual_conditions',index=None)
        st.caption(t('manual_coverage'))
        confirmed=st.checkbox(t('manual_confirm'),key='manual_confirm')
        values={}
        for param in selected:
            values[param]=st.number_input(PARAMETERS[param]['name'][lang]+' ['+PARAMETERS[param]['unit']+']',value=None,key='reading:'+param)
        submitted=st.form_submit_button(t('manual_compare'),type='primary')
    if submitted:
        st.session_state.pop('manual_snapshot',None)
        measurements={k:float(v) for k,v in values.items() if v is not None}
        if not make.strip() or not model.strip() or not version.strip() or not measurements:
            st.error(t('manual_required'))
        else:
            identity=dict(make=make.strip(),model=model.strip(),year=int(year),version=version.strip(),market=market,vehicle_type=vehicle,confirmed=confirmed)
            try:
                results=compare_measurements(identity,measurements,condition)
            except ValueError as error:
                st.error(t('manual_invalid',parameter=PARAMETERS[str(error)]['name'][lang]))
            else:
                st.session_state.manual_snapshot=dict(identity=identity,results=results)
                st.session_state.pop('content',None)
                st.session_state.pop('validated_data',None)
    snapshot=st.session_state.get('manual_snapshot')
    if not snapshot:return
    st.subheader(t('manual_results'))
    identity=snapshot['identity']
    st.text(t('manual_identity',make=identity['make'],model=identity['model'],year=identity['year'],version=identity['version'],market=t('manual_market_us' if identity['market']=='US' else 'manual_market_other')))
    st.info(t('manual_snapshot'))
    for result in snapshot['results']:
        param=result['parameter'];ref=result['reference']
        with st.container(border=True):
            st.write(PARAMETERS[param]['name'][lang])
            st.metric(t('values'),number(result['value'],lang)+' '+PARAMETERS[param]['unit'])
            if result['status']=='manual_review':st.error(t('manual_review'))
            elif ref:st.info(t('manual_not_below'))
            else:st.warning(t('manual_no_reference'))
            if not result['plausible']:st.warning(t('plausibility',column=param))
            if any(param in s['parameters'] and s['critical'] for s in CATALOG['components'].values()):st.warning(t('critical'))
            if ref:
                st.write(t('manual_reference',value=number(ref['value'],lang),unit=ref['unit'],condition=t('manual_'+ref['condition'])))
                st.caption(t('manual_source_scope',manual=ref['manual'],date=ref['checked_at']))
                st.link_button(t('source'),ref['source_url'])

def remember_parameters(component):
    if st.session_state.get('language_switch'):return
    selected=st.session_state['manual_params:'+component]
    st.session_state['selected_params:'+component]=[k for k,p in PARAMETERS.items() if k in selected or any(name+' ['+p['unit']+']' in selected for name in p['name'].values())]

def canonical_choice(value,choices,fallback):
    for canonical,key in choices.items():
        if value==canonical or any(value==translate(lang,key) for lang in ('es','en','de')):return canonical
    return fallback
