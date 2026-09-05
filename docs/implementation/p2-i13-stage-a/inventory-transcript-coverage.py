"""Read-only exact-corpus transcript coverage; no MB imports or processing."""
import json
import os
from pathlib import Path
import psycopg

def inventory(conn, manifest):
    result=[]
    for source in manifest['sources']:
        provider,vid=source['provider_key'],source['video_external_id']
        count,runs,first,last=conn.execute("SELECT count(*),count(DISTINCT processing_run_id),min(t_start),max(t_end) FROM speech_transcript_words WHERE video_provider_key=%s AND video_external_id=%s",(provider,vid)).fetchone()
        result.append({'provider_key':provider,'source_id':vid,'source_sha256':source['source_sha256'],
            'stored_word_rows':count,'recorded_run_count':runs,'first_word_sec':first,'last_word_sec':last,
            'transcript_available':count>0,'owner_coverage':'not_established_by_word_counts'})
    return {'read_only':True,'manifest_id':manifest['id'],'manifest_version':manifest['version'],'sources':result,
        'limits':'Stored evidence counts only; no identity, text, complete speech coverage or recognition accuracy is inferred.'}

def main():
    manifest=json.loads(Path(__file__).with_name('bounded-manifest-proposal.json').read_text(encoding='utf-8'))['manifest']
    if len(manifest['sources'])!=22:raise SystemExit('Unexpected manifest; stop.')
    with psycopg.connect(os.environ['MEMORYBOX_DATABASE_URL'],connect_timeout=5,
        options='-c default_transaction_read_only=on -c statement_timeout=20000 -c lock_timeout=3000') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        print(json.dumps(inventory(conn,manifest),indent=2,default=str))
if __name__=='__main__':main()
