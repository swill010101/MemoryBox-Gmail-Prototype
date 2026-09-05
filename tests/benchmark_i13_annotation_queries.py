"""Explicit synthetic local PostgreSQL benchmark; never reads runtime data."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    if os.environ.get('I13_SYNTHETIC_PG_TEST')!='1':raise SystemExit('Explicit synthetic test opt-in required')
    spec=importlib.util.spec_from_file_location('annotation_tests',ROOT/'tests/test_i13_annotations.py')
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    fixture=tests.Database();fixture.setUp()
    try:
        old=subprocess.check_output(['git','show','195725ddc49b22d127c98f037ec26104196df4eb:memorybox/migrations/031_p2_i13_transcript_annotations.sql'],cwd=ROOT,text=True)
        old=old[old.index('CREATE VIEW i13_effective_words AS'):].replace('i13_effective_words','i13_before_words').replace('i13_effective_moments','i13_before_moments')
        with fixture.connection() as c:
            c.execute("SET LOCAL statement_timeout='20s'")
            c.execute(old)
            for source in [tests.SOURCE,'synthetic-unrelated']:
                words=[{'id':str(uuid4()),'t_start':i*.1,'t_end':i*.1+.05,'token':'synthetic'+str(i)} for i in range(4087)]
                moments=[{'id':str(uuid4()),'t_start':i*2.4,'t_end':i*2.4+2.4,'person_id':None,'speaker_state':'anonymous','status':'accepted','meta_json':{'synthetic_padding':'x'*300}} for i in range(177)]
                c.execute('INSERT INTO i13_transcript_versions(provider_key,source_id,machine) VALUES (%s,%s,%s::jsonb)',('hvrt',source,json.dumps({'words':words,'turns':[],'moments':moments})))
            proof={'kind':'synthetic_4087_words_177_moments_per_source','queries':[]}
            for label,oldview,newview,predicate,ordering in [('words','i13_before_words','i13_effective_words','provider_key','word_index'),('moments','i13_before_moments','i13_effective_moments','video_provider_key','t_start,id')]:
                sourcecol='source_id' if label=='words' else 'video_external_id'
                results=[];times=[]
                for view in [oldview,newview]:
                    sql=f'SELECT * FROM {view} WHERE {predicate}=%s AND {sourcecol}=%s ORDER BY {ordering}'
                    started=perf_counter();rows=c.execute(sql,('hvrt',tests.SOURCE)).fetchall();times.append(round((perf_counter()-started)*1000,2));results.append(rows)
                plan=c.execute('EXPLAIN (ANALYZE,BUFFERS,TIMING OFF,FORMAT JSON) '+sql,('hvrt',tests.SOURCE)).fetchone()['QUERY PLAN'][0]
                scans=[]
                def walk(node):
                    if node.get('Node Type')=='Function Scan':scans.append({k:node.get(k) for k in ['Alias','Actual Rows','Actual Loops']})
                    for child in node.get('Plans',[]):walk(child)
                walk(plan['Plan'])
                entry={'query':label,'old_ms':times[0],'new_ms':times[1],'same_rows':results[0]==results[1],'rows':len(results[1]),'function_scans':scans}
                proof['queries'].append(entry)
                if not entry['same_rows']:raise AssertionError('Projection changed')
                if any(s['Actual Loops']!=1 for s in scans):raise AssertionError('Array expanded more than once for selected source')
            proof['passed']=True
            proof['limits']='Synthetic PostgreSQL 17; FlightSim PostgreSQL 16 remeasurement required. Timings are observations, not a fixed acceptance threshold.'
            (ROOT/'docs/implementation/p2-i13-stage-a/annotation-query-performance-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(proof,indent=2))
    finally:fixture.tearDown()
if __name__=='__main__':main()
