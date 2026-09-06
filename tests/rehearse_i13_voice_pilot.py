"""Local synthetic PG17 dump/restore clone rehearsal; no production DSN accepted."""
import json,os,sys,tempfile,subprocess
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['I13_SYNTHETIC_PG_TEST']='1'
from test_i13_voice_pilot import Database,ROOT

def main():
    case=Database();case.apply_pilot_migration=False;case.setUp()
    clone='i13_pilot_clone_'+uuid4().hex
    tools=Path('C:/Program Files/PostgreSQL/17/bin')
    host=['-h','127.0.0.1','-p','55439','-U','i13_test']
    proof={'kind':'synthetic_pg17_dump_restore_clone','runtime_access':False,'clone':clone}
    try:
        with tempfile.TemporaryDirectory(prefix='i13-pilot-clone-')as d:
            dump=Path(d)/'synthetic.dump'
            subprocess.run([str(tools/'pg_dump.exe'),*host,'-d','i13_annotation_test','-n',case.schema,'-Fc','-f',str(dump)],check=True,capture_output=True)
            subprocess.run([str(tools/'createdb.exe'),*host,clone],check=True,capture_output=True)
            subprocess.run([str(tools/'pg_restore.exe'),*host,'-d',clone,'--exit-on-error',str(dump)],check=True,capture_output=True)
        with psycopg.connect(host='127.0.0.1',port=55439,user='i13_test',dbname=clone,options='-c search_path='+case.schema,row_factory=dict_row)as c:
            before=c.execute('SELECT count(*) n FROM i13_transcript_annotations').fetchone()['n']
            c.execute((ROOT/'memorybox/migrations/032_p2_i13_voice_pilot.sql').read_text())
            proof['migration_applied_on_clone']=True
            proof['annotations_unchanged']=c.execute('SELECT count(*) n FROM i13_transcript_annotations').fetchone()['n']==before
            proof['empty_new_runs']=c.execute('SELECT count(*) n FROM i13_voice_pilot_runs').fetchone()['n']==0
            c.rollback()
            proof['rollback_removes_new_table']=c.execute("SELECT to_regclass('i13_voice_pilot_runs') missing").fetchone()['missing'] is None
            c.commit()
            c.execute((ROOT/'memorybox/migrations/032_p2_i13_voice_pilot.sql').read_text())
            c.commit()
            proof['commit_creates_new_table']=c.execute("SELECT to_regclass('i13_voice_pilot_runs') present").fetchone()['present'] is not None
            proof['server_version']=c.execute('SHOW server_version').fetchone()['server_version']
        proof['passed']=all(proof[k]for k in ['migration_applied_on_clone','annotations_unchanged','empty_new_runs','rollback_removes_new_table','commit_creates_new_table'])
        (ROOT/'docs/implementation/p2-i13-stage-a/voice-pilot-clone-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(json.dumps(proof,indent=2))
        if not proof['passed']:raise RuntimeError('rehearsal failed')
    finally:
        case.tearDown()
        # Preserve the isolated synthetic clone for inspection; never drop runtime DBs.
if __name__=='__main__':main()
