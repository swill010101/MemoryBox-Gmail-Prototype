"""Pilot persistence only. Never writes legacy speech/recognition/owner records."""
import getpass
import json
from uuid import UUID
from memorybox.db import connection
from memorybox.speech.annotations import corpus, validate_span
from .scope import ScopeDenied, digest
from .voice_pilot import validate

def check_annotations(c, plan, *, lock_sources=True):
    parent = corpus()
    if digest(parent) != plan['parent_manifest_sha256'] or parent != plan['manifest']:
        raise ScopeDenied('pilot_parent_changed')
    # Mutating paths serialize with annotation/transcript publication. Diagnostics read only.
    if lock_sources:
        for key in sorted({s['provider_key']+':'+s['source_id'] for s in plan['spans']}):
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
    for s in plan['spans']:
        row=c.execute("""SELECT a.*,v.machine,v.provider_key,v.source_id FROM i13_active_annotations a
          JOIN i13_current_transcripts v ON v.id=a.version_id WHERE a.id=%s::uuid""",(s['annotation_id'],)).fetchone()
        if not row: raise ScopeDenied('pilot_annotation_changed')
        row_person_id=str(row['person_id']) if row['person_id'] else None
        if str(row['version_id'])!=s['version_id'] or row_person_id!=s.get('person_id') or row['provider_key']!=s['provider_key'] or row['source_id']!=s['source_id'] or [str(x) for x in row['word_ids']]!=s['word_ids']:
            raise ScopeDenied('pilot_annotation_changed')
        if 'speaker_state' in s and row['speaker_state']!=s['speaker_state']:
            raise ScopeDenied('pilot_annotation_changed')
        if validate_span(row['machine'],s['word_ids'])!=(s['start'],s['end']): raise ScopeDenied('pilot_span_changed')
        if c.execute('SELECT 1 FROM i13_voice_pilot_retirements WHERE annotation_id=%s::uuid',(s['annotation_id'],)).fetchone():
            raise ScopeDenied('pilot_reference_or_evidence_retired')

def checked(c, identifier, *, allow_stopped=False, lock_sources=True):
    UUID(identifier)
    c.execute("SET LOCAL lock_timeout='5s'")
    c.execute("SET LOCAL statement_timeout='20s'")
    row=c.execute('SELECT * FROM i13_processing_admissions WHERE id=%s::uuid'+(' FOR SHARE' if lock_sources else ''),(identifier,)).fetchone()
    if not row: raise ScopeDenied('admission_not_found')
    plan=row['plan_json']; validate(plan)
    valid_state = row['state']=='started' or (allow_stopped and row['state']=='stopped')
    if row['plan_sha256']!=digest(plan) or not valid_state or not row['start_ref']:
        raise ScopeDenied('pilot_not_started_or_changed')
    check_annotations(c,plan,lock_sources=lock_sources)
    return plan

def load(identifier):
    with connection() as c:
        c.execute("SET LOCAL statement_timeout='20s'")
        return checked(c,identifier)

def load_for_check(identifier):
    """Read current evidence for an already-stopped pilot; never authorizes work."""
    with connection() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        c.execute("SET LOCAL statement_timeout='20s'")
        return checked(c,identifier,allow_stopped=True,lock_sources=False)

def claim(identifier):
    with connection() as c:
        plan=checked(c,identifier)
        row=c.execute('INSERT INTO i13_voice_pilot_runs(admission_id) VALUES(%s::uuid) ON CONFLICT DO NOTHING RETURNING admission_id',(identifier,)).fetchone()
        if not row: raise ScopeDenied('pilot_already_attempted_no_retry')
    return plan

def reserve(identifier, key):
    with connection() as c:
        plan=checked(c,identifier)
        if key not in {s['key'] for s in plan['spans']}: raise ScopeDenied('pilot_unknown_span')
        row=c.execute('INSERT INTO i13_voice_pilot_attempts(admission_id,span_key) VALUES(%s::uuid,%s) ON CONFLICT DO NOTHING RETURNING span_key',(identifier,key)).fetchone()
        if not row: raise ScopeDenied('pilot_span_already_attempted')

def publish(identifier, vectors, results, provenance):
    with connection() as c:
        plan=checked(c,identifier)
        count=c.execute('SELECT count(*) AS n FROM i13_voice_pilot_attempts WHERE admission_id=%s::uuid',(identifier,)).fetchone()['n']
        if count!=4 or len(vectors)!=4 or len(results)!=3: raise ScopeDenied('pilot_incomplete')
        reference={'annotation_id':plan['spans'][0]['annotation_id'],'vector':vectors[0], 'provenance':provenance}
        for kind,payload in [('reference',reference),('result',{'results':results,'provenance':provenance})]:
            c.execute('INSERT INTO i13_voice_pilot_events(admission_id,kind,payload) VALUES(%s::uuid,%s,%s::jsonb)',(identifier,kind,json.dumps(payload,allow_nan=False)))

def failed(identifier, error_code):
    with connection() as c:
        c.execute("SET LOCAL lock_timeout='5s'")
        c.execute("SET LOCAL statement_timeout='20s'")
        c.execute("INSERT INTO i13_voice_pilot_events(admission_id,kind,payload) VALUES(%s::uuid,'failed',%s::jsonb)",(identifier,json.dumps({'error_type':error_code})))

def retire(annotation_id, reason):
    if not reason.strip(): raise ScopeDenied('retirement_reason_required')
    with connection() as c:
        c.execute("SET LOCAL lock_timeout='5s'")
        c.execute("SET LOCAL statement_timeout='20s'")
        r=c.execute('SELECT v.provider_key,v.source_id FROM i13_transcript_annotations a JOIN i13_transcript_versions v ON v.id=a.version_id WHERE a.id=%s::uuid',(annotation_id,)).fetchone()
        if not r: raise ScopeDenied('annotation_not_found')
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(r['provider_key']+':'+r['source_id'],))
        c.execute('INSERT INTO i13_voice_pilot_retirements(annotation_id,reason,actor) VALUES(%s::uuid,%s,%s) ON CONFLICT DO NOTHING',(annotation_id,reason,getpass.getuser()))
        affected=c.execute("SELECT id::text FROM i13_processing_admissions WHERE plan_json->>'purpose'='voice_pilot' AND EXISTS(SELECT 1 FROM jsonb_array_elements(plan_json->'spans') s WHERE s->>'annotation_id'=%s)",(annotation_id,)).fetchall()
    return {'retired':annotation_id,'affected_admissions':[r['id'] for r in affected],'reprocessing_started':False}
