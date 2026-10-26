"""Machine-readable data release gate. Does not deploy or infer OEM coverage."""
import argparse,datetime as dt,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_catalog import load_bundle,validate_bundle,summary,DATABASE
parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['preview','diagnostic'],default='preview');parser.add_argument('--database',type=Path,default=DATABASE);args=parser.parse_args()
bundle=load_bundle();validate_bundle(bundle);info=summary(args.database)
import hashlib
from fleet_catalog import _json
if hashlib.sha256(_json(bundle).encode()).hexdigest()!=info['bundle_sha256']:raise SystemExit('bundle/database mismatch')
reasons=[]
if info['dataset_kind']!='curated':reasons.append('synthetic_database')
if int(info['as_of'][:4])!=dt.date.today().year:reasons.append('stale_catalogue_year')
if info['eligible_models']<3:reasons.append('fewer_than_three_verified_models')
if args.profile=='diagnostic':
 if info['verified_variants']==0:reasons.append('no_verified_variants')
 if info['verified_thresholds']==0:reasons.append('no_verified_oem_thresholds')
 if info['documented_diagnostics']==0:reasons.append('no_documented_model_diagnostics')
 reasons.append('complete_europe_us_sales_denominator_not_verified')
print(json.dumps(dict(profile=args.profile,status='not_ready' if reasons else 'ready_with_known_limitations',blockers=reasons,coverage=info),indent=2))
raise SystemExit(2 if reasons else 0)
