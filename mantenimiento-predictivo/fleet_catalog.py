"""Offline catalogue validation and indexed, read-only lookups. No user telemetry."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import contextmanager
from jsonschema import Draft202012Validator,FormatChecker
ROOT=Path(__file__).parent
# Operational policy includes European countries/territories, Cyprus and Turkey;
# sales aggregated over a wider OEM region do not establish this geography.
EUROPE=frozenset('AL AD AT BY BE BA BG HR CY CZ DK EE FO FI FR DE GI GR GG VA HU IS IE IM IT JE LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM RS SK SI ES SJ SE CH TR UA GB XK'.split())
MARKETS=EUROPE|{'US','EUROPE'}
SCHEMA=ROOT/'schemas/fleet-catalog-v1.schema.json'
BUNDLE=ROOT/'catalog/fleet2025/catalog.json'
DATABASE=ROOT/'catalog/fleet2025/catalog.sqlite'
TABLES={'sources':'source','models':'model','variants':'variant','sales':'sale','parameters':'parameter','dtcs':'dtc','faults':'fault','coverage':'coverage','thresholds':'threshold'}

class CatalogError(ValueError):pass

def load_bundle(path=BUNDLE):
    def invalid(value):raise CatalogError('nonfinite_json')
    def unique_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise CatalogError('duplicate_json_key:'+key)
            result[key]=value
        return result
    return json.loads(Path(path).read_text(),parse_constant=invalid,object_pairs_hook=unique_pairs)

def eligibility(sale,as_of):
    year=dt.date.fromisoformat(as_of).year-1
    checks=[(sale['year']==year,'not_last_calendar_year'),
            (sale['period_start']==f'{year}-01-01' and sale['period_end']==f'{year}-12-31','incomplete_year'),
            (sale['metric']=='sales','not_sales'),(sale['units']>50,'not_over_50'),
            (sale['market'] in MARKETS and sale['geography_status']=='in_scope','geography_unverified'),
            (sale['identity_scope']=='exact_model','not_exact_model'),(sale['verification']=='verified','unverified')]
    return next(((False,reason) for ok,reason in checks if not ok),(True,'eligible'))

def validate_bundle(bundle,*,allow_benchmark=False):
    validator=Draft202012Validator(json.loads(SCHEMA.read_text()),format_checker=FormatChecker())
    error=next(validator.iter_errors(bundle),None)
    if error:raise CatalogError('schema:'+ '/'.join(map(str,error.absolute_path))+':'+error.message)
    if bundle['dataset_kind']=='benchmark' and not allow_benchmark:raise CatalogError('benchmark_not_publishable')
    entities={}
    for name in TABLES:
        rows=bundle[name];entities[name]={r['id']:r for r in rows}
        if len(entities[name])!=len(rows):raise CatalogError('duplicate_id:'+name)
    def get(table,key):
        try:return entities[table][key]
        except KeyError:raise CatalogError('foreign_key:'+table+':'+str(key)) from None
    as_of=dt.date.fromisoformat(bundle['as_of'])
    for source in bundle['sources']:
        if dt.date.fromisoformat(source['retrieved_at'])>as_of:raise CatalogError('future_source')
        if source['published_at'] and source['published_at']>source['retrieved_at']:raise CatalogError('future_publication')
        if source['reuse'] in ('open_licensed','licensed') and not source['license']:raise CatalogError('license_missing')
        if source['redistribution_allowed'] and (source['reuse'] not in ('open_licensed','licensed') or not source['license']):raise CatalogError('redistribution_rights_missing')
    for model in bundle['models']:get('sources',model['source_id'])
    for variant in bundle['variants']:
        get('models',variant['model_id'])
        if variant['source_id']:get('sources',variant['source_id'])
        if variant['verification']=='verified' and variant['source_id'] and get('sources',variant['source_id'])['source_kind']!='oem_technical':raise CatalogError('variant_source_kind')
        if variant['verification']=='verified' and variant['market'] not in MARKETS-{'EUROPE'}:raise CatalogError('variant_market_unverified')
        if variant['verification']=='verified' and not all([variant['variant_code'],variant['generation'],variant['source_id'],variant['model_year']]):raise CatalogError('variant_scope_missing')
    for sale in bundle['sales']:
        get('models',sale['model_id']);source=get('sources',sale['source_id'])
        if sale['verification']=='verified' and source['source_kind']!='sales':raise CatalogError('sales_source_kind')
        if sale['verification']=='verified' and get('models',sale['model_id'])['identity_status']!='verified':raise CatalogError('model_identity_pending')
        if sale['period_start']>sale['period_end']:raise CatalogError('invalid_sales_period')
    if len({p['column'] for p in bundle['parameters']})!=len(bundle['parameters']):raise CatalogError('duplicate_parameter_column')
    for parameter in bundle['parameters']:
        lo,hi=parameter['physical_min'],parameter['physical_max']
        if any(v is not None and not math.isfinite(v) for v in (lo,hi)):raise CatalogError('nonfinite_physical_range')
        if lo is not None and hi is not None and lo>=hi:raise CatalogError('physical_range')
    for dtc in bundle['dtcs']:
        if dtc['namespace']=='manufacturer' and not dtc['make']:raise CatalogError('dtc_make_missing')
        if dtc['verification']=='verified' and not dtc['source_id']:raise CatalogError('dtc_source_missing')
        if dtc['source_id']:get('sources',dtc['source_id'])
        if dtc['verification']=='verified':
            source=get('sources',dtc['source_id'])
            if dtc['definition_kind']=='regulatory_category':
                if source['source_kind']!='regulation' or dtc['namespace']!='generic' or dtc['full_sae_description'] is not None:raise CatalogError('regulatory_category_scope')
            else:
                if not source['redistribution_allowed']:raise CatalogError('dtc_reuse_not_permitted')
                if dtc['definition_kind']=='oem_definition' and (source['source_kind']!='oem_technical' or dtc['namespace']!='manufacturer' or not dtc['ecu']):raise CatalogError('oem_dtc_scope_missing')
                if dtc['definition_kind']=='sae_definition' and (source['source_kind']!='standard' or not dtc['full_sae_description']):raise CatalogError('sae_definition_missing')
    for row in bundle['coverage']:
        variant=get('variants',row['variant_id']);get('faults',row['fault_id'])
        for key in row['parameters']:get('parameters',key)
        for key in row['dtc_ids']:
            dtc=get('dtcs',key)
            if dtc['namespace']=='manufacturer' and dtc['make'].strip().casefold()!=get('models',variant['model_id'])['make'].strip().casefold():raise CatalogError('cross_make_dtc')
        if row['source_id']:get('sources',row['source_id'])
        if row['status']=='documented':
            if not row['source_id'] or variant['verification']!='verified':raise CatalogError('unverified_diagnostic_link')
            source=get('sources',row['source_id'])
            if not source['redistribution_allowed'] or source['source_kind']!='oem_technical':raise CatalogError('diagnostic_reuse_not_permitted')
            if any((get('dtcs',key)['verification']!='verified' or get('dtcs',key)['definition_kind']=='regulatory_category') for key in row['dtc_ids']):raise CatalogError('unverified_dtc_link')
        elif row['dtc_ids']:raise CatalogError('unverified_dtc_link')
    scopes={}
    for row in bundle['thresholds']:
        variant=get('variants',row['variant_id']);param=get('parameters',row['parameter_id'])
        if row['unit']!=param['unit']:raise CatalogError('unit_mismatch')
        if row['source_id']:get('sources',row['source_id'])
        if row['valid_from']>row['valid_until']:raise CatalogError('invalid_validity')
        lo,hi=row['lower'],row['upper']
        if any(v is not None and not math.isfinite(v) for v in (lo,hi)):raise CatalogError('nonfinite_limit')
        if lo is not None and hi is not None and lo>=hi:raise CatalogError('invalid_limits')
        for value in (lo,hi):
            if value is not None and ((param['physical_min'] is not None and value<param['physical_min']) or (param['physical_max'] is not None and value>param['physical_max'])):raise CatalogError('impossible_limit')
        if row['status']=='verified':
            if not row['source_id'] or variant['verification']!='verified' or (lo is None and hi is None):raise CatalogError('threshold_evidence_missing')
            source=get('sources',row['source_id'])
            if not source['redistribution_allowed'] or source['source_kind']!='oem_technical':raise CatalogError('threshold_reuse_not_permitted')
            for prior in scopes.setdefault((row['variant_id'],row['parameter_id'],row['condition']),[]):
                if row['valid_from']<=prior['valid_until'] and prior['valid_from']<=row['valid_until']:raise CatalogError('ambiguous_threshold')
            scopes[(row['variant_id'],row['parameter_id'],row['condition'])].append(row)
        elif lo is not None or hi is not None:raise CatalogError('unverified_numeric_limit')
    # Registration/name-only data never confers eligibility on a variant.
    return entities

def _json(row):return json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))

def build_database(bundle,destination,*,allow_benchmark=False):
    validate_bundle(bundle,allow_benchmark=allow_benchmark)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.catalog-',suffix='.sqlite',dir=destination.parent);os.close(fd)
    temporary=Path(name)
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript((ROOT/'schemas/fleet-catalog-v1.sql').read_text())
            db.executemany('INSERT INTO metadata VALUES (?,?)',[(k,str(bundle[k])) for k in ('schema_version','dataset_kind','as_of','region_policy')]+[('bundle_sha256',hashlib.sha256(_json(bundle).encode()).hexdigest())])
            for r in bundle['sources']:db.execute('INSERT INTO source VALUES (?,?,?,?,?)',(r['id'],r['title'],r['url'],r['reuse'],_json(r)))
            for r in bundle['models']:db.execute('INSERT INTO model VALUES (?,?,?,?,?,?)',(r['id'],r['make'],r['name'],r['vehicle_class'],r['source_id'],_json(r)))
            for r in bundle['variants']:db.execute('INSERT INTO variant VALUES (?,?,?,?,?,?,?,?)',(r['id'],r['model_id'],r['market'],r['model_year'],r['engine_code'],r['generation'],r['verification'],_json(r)))
            for r in bundle['sales']:
                ok,reason=eligibility(r,bundle['as_of']);db.execute('INSERT INTO sale VALUES (?,?,?,?,?,?,?,?,?,?)',(r['id'],r['model_id'],r['source_id'],r['year'],r['market'],r['metric'],r['units'],int(ok),reason,_json(r)))
            for r in bundle['parameters']:db.execute('INSERT INTO parameter VALUES (?,?,?)',(r['id'],r['unit'],_json(r)))
            for r in bundle['dtcs']:db.execute('INSERT INTO dtc VALUES (?,?,?,?,?,?,?)',(r['id'],r['code'],r['namespace'],r['make'],r['source_id'],r['verification'],_json(r)))
            for r in bundle['faults']:db.execute('INSERT INTO fault VALUES (?,?,?)',(r['id'],r['category'],_json(r)))
            for r in bundle['coverage']:
                db.execute('INSERT INTO coverage VALUES (?,?,?,?,?,?)',(r['id'],r['variant_id'],r['fault_id'],r['status'],r['source_id'],_json(r)))
                db.executemany('INSERT INTO coverage_dtc VALUES (?,?)',[(r['id'],k) for k in r['dtc_ids']]);db.executemany('INSERT INTO coverage_parameter VALUES (?,?)',[(r['id'],k) for k in r['parameters']])
            for r in bundle['thresholds']:db.execute('INSERT INTO threshold VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['variant_id'],r['parameter_id'],r['unit'],r['condition'],r['lower'],r['upper'],r['status'],r['source_id'],r['valid_from'],r['valid_until'],_json(r)))
            if db.execute('PRAGMA foreign_key_check').fetchall():raise CatalogError('foreign_key_check')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise CatalogError('integrity_check')
            db.execute('ANALYZE')
        os.chmod(temporary,0o644)
        with temporary.open('rb') as f:os.fsync(f.fileno())
        os.replace(temporary,destination)
        # Single-writer offline job, never called from a Streamlit user request.
        fd=os.open(destination.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)
    return summary(destination)

@contextmanager
def read_database(path=DATABASE):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row
    try:yield db
    finally:db.close()

def summary(path=DATABASE):
    with read_database(path) as db:
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        return {**meta,'models':db.execute('SELECT count(*) FROM model').fetchone()[0],
                'eligible_models':db.execute('SELECT count(DISTINCT model_id) FROM sale WHERE eligible=1').fetchone()[0],
                'verified_variants':db.execute("SELECT count(*) FROM variant WHERE verification='verified'").fetchone()[0],
                'verified_thresholds':db.execute("SELECT count(*) FROM threshold WHERE status='verified'").fetchone()[0],
                'documented_diagnostics':db.execute("SELECT count(*) FROM coverage WHERE status='documented'").fetchone()[0],
                'dtc_definitions':db.execute("SELECT count(*) FROM dtc WHERE verification='verified' AND json_extract(payload,'$.definition_kind')!='regulatory_category'").fetchone()[0],
                'dtc_regulatory_categories':db.execute("SELECT count(*) FROM dtc WHERE verification='verified' AND json_extract(payload,'$.definition_kind')='regulatory_category'").fetchone()[0]}

def eligible_models(path=DATABASE,limit=50):
    with read_database(path) as db:
        rows=db.execute('SELECT m.payload model,s.payload sale,x.payload source FROM sale s JOIN model m ON m.id=s.model_id JOIN source x ON x.id=s.source_id WHERE s.eligible=1 ORDER BY m.make,m.name LIMIT ?', (min(max(int(limit),1),100),)).fetchall()
        return [{'model':json.loads(r['model']),'sale':json.loads(r['sale']),'source':json.loads(r['source'])} for r in rows]

def lookup_thresholds(variant_id,parameter_id,condition,at,path=DATABASE):
    # Exact variant only. No family/model fallback or implicit unit conversion.
    dt.date.fromisoformat(at)
    with read_database(path) as db:
        rows=db.execute("SELECT t.payload FROM threshold t JOIN variant v ON v.id=t.variant_id WHERE t.variant_id=? AND t.parameter_id=? AND t.condition=? AND t.status='verified' AND t.valid_from<=? AND t.valid_until>=? AND v.verification='verified' AND EXISTS (SELECT 1 FROM sale s WHERE s.model_id=v.model_id AND s.eligible=1 AND s.year=?)",(variant_id,parameter_id,condition,at,at,dt.date.fromisoformat(at).year-1)).fetchall()
        return json.loads(rows[0]['payload']) if len(rows)==1 else None
