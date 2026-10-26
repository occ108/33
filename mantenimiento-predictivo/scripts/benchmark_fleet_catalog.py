"""Synthetic index microbenchmark in a temporary DB, never a production import."""
import argparse,json,random,resource,shutil,sqlite3,statistics,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_catalog import DATABASE,read_database,_json
parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=100000);parser.add_argument('--queries',type=int,default=1000)
a=parser.parse_args()
if a.rows<1 or a.queries<1:raise SystemExit('positive sizes required')
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'synthetic.sqlite';shutil.copyfile(DATABASE,path)
 with sqlite3.connect(path) as db:
  db.execute("UPDATE metadata SET value='benchmark' WHERE key='dataset_kind'")
  template=json.loads(db.execute('SELECT payload FROM threshold LIMIT 1').fetchone()[0])
  start=time.perf_counter()
  def rows():
   for i in range(a.rows):
    r=template|dict(id=f'benchmark-{i}',condition=f'benchmark-condition-{i}')
    yield (r['id'],r['variant_id'],r['parameter_id'],r['unit'],r['condition'],None,None,'missing_oem',None,r['valid_from'],r['valid_until'],_json(r))
  db.executemany('INSERT INTO threshold VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',rows());db.commit();db.execute('ANALYZE')
  seconds=time.perf_counter()-start
 sql="SELECT payload FROM threshold WHERE variant_id=? AND parameter_id=? AND condition=? AND status=?"
 samples={status:[] for status in ['missing_oem','verified']};rng=random.Random(2025)
 with read_database(path) as db:
  plan=[tuple(row) for row in db.execute('EXPLAIN QUERY PLAN '+sql,(template['variant_id'],template['parameter_id'],'benchmark-condition-0','missing_oem'))]
  for _ in range(a.queries):
   condition=f'benchmark-condition-{rng.randrange(a.rows)}'
   for status in samples:
    start=time.perf_counter_ns();found=db.execute(sql,(template['variant_id'],template['parameter_id'],condition,status)).fetchall();samples[status].append((time.perf_counter_ns()-start)/1e6)
    assert len(found)==(1 if status=='missing_oem' else 0)
 assert any('idx_threshold_lookup' in str(row) for row in plan)
 def metrics(values):
  ordered=sorted(values);return dict(p50_ms=statistics.median(values),p95_ms=ordered[min(len(ordered)-1,int(len(ordered)*.95))])
 print(json.dumps(dict(kind='synthetic_index_microbenchmark_not_Render_SLA',rows_added=a.rows,queries_per_case=a.queries,populate_seconds=seconds,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,database_mib=path.stat().st_size/1024**2,query_plan=plan,pending_hit=metrics(samples['missing_oem']),verified_miss=metrics(samples['verified']),limitations='Single local SQLite process, warmed OS cache; no concurrency, network, full import/schema throughput or real diagnostics evaluated.'),indent=2))
