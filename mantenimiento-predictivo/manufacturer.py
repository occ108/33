"""Explicitly scoped OEM recommendations; no guessing or cross-model fallback."""
import json
import math
from pathlib import Path
from automotive import PARAMETERS
REFERENCES=json.loads((Path(__file__).parent/'catalog/manufacturer_references.json').read_text())['references']

def match_references(identity,parameter,condition):
    if not identity.get('confirmed'):return []
    return [r for r in REFERENCES if
            r['make'].casefold()==identity['make'].strip().casefold() and
            r['model'].casefold()==identity['model'].strip().casefold() and
            r['market']==identity['market'] and r['vehicle_type']==identity['vehicle_type'] and
            r['year_min']<=identity['year']<=r['year_max'] and
            r['parameter']==parameter and r['condition']==condition]

def compare_measurements(identity,measurements,condition):
    results=[]
    for param,value in measurements.items():
        rule=PARAMETERS[param]
        if not math.isfinite(value) or (rule.get('physical_min') is not None and value<rule['physical_min']) or (rule.get('physical_max') is not None and value>rule['physical_max']):
            raise ValueError(param)
        refs=match_references(identity,param,condition)
        plausible=rule['plausible_min']<=value<=rule['plausible_max']
        if not refs:
            results.append(dict(parameter=param,value=value,status='manual_no_reference',reference=None,plausible=plausible));continue
        # Ambiguous/conflicting source data must not produce an automatic verdict.
        if len({(r['operator'],r['value'],r['unit']) for r in refs})!=1:
            results.append(dict(parameter=param,value=value,status='manual_no_reference',reference=None,plausible=plausible));continue
        ref=refs[0]
        if ref['unit']!=rule['unit']:raise ValueError(param)
        reached=value<ref['value'] if ref['operator']=='lt' else value>ref['value']
        results.append(dict(parameter=param,value=value,status='manual_review' if reached else 'manual_not_below',reference=ref,plausible=plausible))
    return results
