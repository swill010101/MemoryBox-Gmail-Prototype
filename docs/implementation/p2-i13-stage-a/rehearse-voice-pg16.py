"""FlightSim PG16 clone rehearsal. Production reads only; no model or service start."""
import argparse
import hashlib
import json
import platform
import shutil
from pathlib import Path
import subprocess
import time
from uuid import uuid4

CONTAINER='memorybox-pg'
TABLES=('speech_transcript_words','i13_transcript_versions','i13_transcript_annotations',
        'recognition_queue_items','speech_queue_items','historian_capture_campaigns','historian_capture_items')

def command(args, *, data=None, timeout=600):
    r=subprocess.run(args,input=data,text=True,capture_output=True,timeout=timeout)
    if r.returncode:
        # No credentials or row payloads are printed by this script.
        raise RuntimeError('Command failed: '+args[0]+' '+str(r.returncode))
    return r.stdout.strip()

def sql(database, query):
    return command(['docker','exec','-i',CONTAINER,'psql','-X','-q','-A','-t','-U','memorybox',
                    '-d',database,'-v','ON_ERROR_STOP=1'],data=query,timeout=600)

def fingerprint_sql():
    return ' UNION ALL '.join("SELECT '"+t+"' AS name,count(*) AS rows,md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) AS digest FROM public."+t+' t' for t in TABLES)

def guard(database):
    if not database.startswith('mb_i13_pre032_restore_') or len(database)!=54 or any(x not in '0123456789abcdef' for x in database[22:]):
        raise ValueError('Invalid generated clone name')
    return "DO $$ BEGIN IF current_database()<>'"+database+"' THEN RAISE EXCEPTION 'Wrong clone'; END IF; END $$;\n"

def rehearsal_sql(database,migration,commit):
    fingerprints=fingerprint_sql()
    return ("BEGIN; SET LOCAL search_path=public; SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='120s';\n"+guard(database)+
      "DO $$ BEGIN IF to_regclass('public.i13_voice_pilot_runs') IS NOT NULL OR EXISTS(SELECT 1 FROM schema_migrations WHERE version='032') THEN RAISE EXCEPTION '032 already present'; END IF; END $$;\n"+
      'CREATE TEMP TABLE before_fingerprints ON COMMIT DROP AS '+fingerprints+';\n'+migration+'\n'+
      'CREATE TEMP TABLE after_fingerprints ON COMMIT DROP AS '+fingerprints+';\n'+
      "DO $$ BEGIN IF EXISTS((SELECT * FROM before_fingerprints EXCEPT ALL SELECT * FROM after_fingerprints) UNION ALL (SELECT * FROM after_fingerprints EXCEPT ALL SELECT * FROM before_fingerprints)) THEN RAISE EXCEPTION 'Existing data changed'; END IF; IF EXISTS(SELECT 1 FROM i13_voice_pilot_runs) THEN RAISE EXCEPTION 'Unexpected pilot run'; END IF; END $$;\n"+
      ("INSERT INTO schema_migrations(version,filename) VALUES('032','032_p2_i13_voice_pilot.sql'); COMMIT;\n" if commit else 'ROLLBACK;\n'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-sha',required=True);p.add_argument('--rehearse',action='store_true')
    a=p.parse_args()
    if platform.node().split('.')[0].casefold()!='flightsim':raise RuntimeError('This helper targets FlightSim only')
    root=Path(__file__).resolve().parents[3]
    if command(['git','-C',str(root),'rev-parse','HEAD'])!=a.expected_sha:raise RuntimeError('Release SHA mismatch')
    if command(['git','-C',str(root),'status','--porcelain']):raise RuntimeError('Release must be clean')
    pre=json.loads(sql('memorybox',"BEGIN READ ONLY; SET LOCAL statement_timeout='20s'; SELECT json_build_object('database',current_database(),'database_bytes',pg_database_size(current_database()),'server_version_num',current_setting('server_version_num')::int,'latest_migration',(SELECT max(version) FROM schema_migrations),'annotation_present',to_regclass('public.i13_transcript_annotations') IS NOT NULL,'pilot_present',to_regclass('public.i13_voice_pilot_runs') IS NOT NULL); COMMIT;"))
    if pre['database']!='memorybox' or not 160000<=pre['server_version_num']<170000 or pre['latest_migration']!='031' or not pre['annotation_present'] or pre['pilot_present']:
        raise RuntimeError('Runtime prerequisites changed; stop without writes')
    print(json.dumps({'read_only_preflight':pre,'rehearsal_requested':a.rehearse}),flush=True)
    if not a.rehearse:return
    if '(PostgreSQL) 16.' not in command(['docker','exec',CONTAINER,'pg_dump','--version']):raise RuntimeError('PG16 dump tool required')
    if shutil.disk_usage('C:/').free < pre['database_bytes']*3+2_000_000_000:raise RuntimeError('Insufficient backup free space')
    disk=command(['docker','exec',CONTAINER,'df','-Pk','/tmp','/var/lib/postgresql/data'])
    for line in disk.splitlines()[1:]:
        if int(line.split()[-3])*1024 < pre['database_bytes']*3+2_000_000_000:raise RuntimeError('Insufficient container free space')
    token=uuid4().hex;clone='mb_i13_pre032_restore_'+token;guard(clone)
    backup=Path('C:/MemoryBox-backups')/('i13-pre032-'+token)
    backup.mkdir(parents=True,exist_ok=False)
    remote='/tmp/mb-i13-pre032-'+token
    command(['docker','exec',CONTAINER,'mkdir',remote])
    command(['docker','exec','-e','PGOPTIONS=-c default_transaction_read_only=on',CONTAINER,
             'pg_dump','-U','memorybox','-d','memorybox','--format=custom','--lock-wait-timeout=5000','--file='+remote+'/memorybox.dump'])
    dump=backup/'memorybox.dump'
    command(['docker','cp',CONTAINER+':'+remote+'/memorybox.dump',str(dump)])
    with dump.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
    remote_hash=command(['docker','exec',CONTAINER,'sha256sum',remote+'/memorybox.dump']).split()[0]
    if checksum!=remote_hash or dump.stat().st_size==0:raise RuntimeError('Backup verification failed')
    proof={'release_sha':a.expected_sha,'backup_file':str(dump),'backup_bytes':dump.stat().st_size,
           'backup_sha256':checksum,'container_hash_matches':True,'clone':clone,'production_migrated':False,
           'model_started':False,'source_preflight':pre}
    proof_path=backup/'rehearsal-proof.json'
    proof_path.write_text(json.dumps(proof,indent=2))
    # Restore the Windows backup, rather than relying on the original container dump.
    restored=remote+'/verified-backup.dump'
    command(['docker','cp',str(dump),CONTAINER+':'+restored])
    if command(['docker','exec',CONTAINER,'sha256sum',restored]).split()[0]!=checksum:raise RuntimeError('Restore copy mismatch')
    command(['docker','exec',CONTAINER,'createdb','-U','memorybox','--template=template0',clone])
    command(['docker','exec',CONTAINER,'pg_restore','-U','memorybox','-d',clone,'--exit-on-error','--no-owner','--no-privileges',restored])
    migration=(root/'memorybox/migrations/032_p2_i13_voice_pilot.sql').read_text()
    proof['migration_sha256']=hashlib.sha256(migration.replace('\r\n','\n').encode()).hexdigest()
    started=time.monotonic();sql(clone,rehearsal_sql(clone,migration,False))
    if sql(clone,"SELECT to_regclass('public.i13_voice_pilot_runs') IS NULL")!='t':raise RuntimeError('Rollback failed')
    proof['rollback_verified']=True
    sql(clone,rehearsal_sql(clone,migration,True))
    proof['clone_result']=json.loads(sql(clone,"SELECT json_build_object('version',current_setting('server_version'),'migration032',(SELECT filename FROM schema_migrations WHERE version='032'),'runs',(SELECT count(*) FROM i13_voice_pilot_runs),'attempts',(SELECT count(*) FROM i13_voice_pilot_attempts),'events',(SELECT count(*) FROM i13_voice_pilot_events),'retirements',(SELECT count(*) FROM i13_voice_pilot_retirements))"))
    proof['rehearsal_seconds']=round(time.monotonic()-started,2)
    proof['existing_table_fingerprints_unchanged']=True
    proof['production_pilot_absent']=sql('memorybox',"BEGIN READ ONLY; SELECT to_regclass('public.i13_voice_pilot_runs') IS NULL AND NOT EXISTS(SELECT 1 FROM schema_migrations WHERE version='032'); COMMIT;")=='t'
    if not proof['production_pilot_absent']:raise RuntimeError('Unexpected production schema change')
    proof['passed']=True;proof_path.write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__,'automatic_retry':False}))
        raise SystemExit(2)
