"""Validated offline catalogue build; no network and no user-data ingestion."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_catalog import BUNDLE,DATABASE,load_bundle,build_database
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=BUNDLE)
    parser.add_argument('--output',type=Path,default=DATABASE)
    args=parser.parse_args()
    print(json.dumps(build_database(load_bundle(args.input),args.output),ensure_ascii=False,indent=2))
