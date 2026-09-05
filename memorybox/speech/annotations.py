"""Owner overlays only: no embeddings, processing, queue or provider dependencies."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from uuid import UUID
from memorybox.db import connection

MANIFEST = Path(__file__).resolve().parents[2] / 'docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json'

class AnnotationError(ValueError):
    pass

def corpus():
    raw = MANIFEST.read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != 'd256caa2ef1829eb26fba1f78655d4b1d16f8f0ffa753367e44515bf0ac69344':
        raise AnnotationError('annotation_manifest_changed_requires_review')
    document = json.loads(raw)
    sources = document['manifest']['sources']
    if len(sources) != 22 or len({(s['provider_key'], s['video_external_id']) for s in sources}) != 22:
        raise AnnotationError('invalid_annotation_manifest')
    return document['manifest']

def require_member(provider, source):
    if not any((s['provider_key'], s['video_external_id']) == (provider, source) for s in corpus()['sources']):
        raise AnnotationError('source_outside_annotation_manifest')

def validate_span(machine, word_ids):
    if not 1 <= len(word_ids) <= 500 or len(set(word_ids)) != len(word_ids):
        raise AnnotationError('invalid_word_selection')
    words = machine['words']
    positions = {str(w['id']): i for i,w in enumerate(words)}
    try: indexes = [positions[str(UUID(x))] for x in word_ids]
    except (KeyError, ValueError): raise AnnotationError('word_source_version_mismatch')
    if indexes != list(range(indexes[0], indexes[0]+len(indexes))):
        raise AnnotationError('select_contiguous_words_in_order')
    selected = [words[i] for i in indexes]
    t0,t1=min(float(w['t_start']) for w in selected),max(float(w['t_end']) for w in selected)
    if not math.isfinite(t0) or not math.isfinite(t1) or t0<0 or t1<t0: raise AnnotationError('invalid_machine_word_bounds')
    return t0,t1

def _api(row):
    return json.loads(json.dumps(dict(row), default=str)) if row else None

def save_annotation(provider, source, actor, payload):
    require_member(provider, source)
    body = dict(payload)
    digest = hashlib.sha256(json.dumps([provider,source,actor,body],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with connection() as conn:
        conn.execute("SET LOCAL lock_timeout='5s'")
        # All writes for this source, including new transcript publication, use
        # the same transaction-scoped lock. No worker lock is enabled here.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(provider+':'+source,))
        old = conn.execute('SELECT * FROM i13_transcript_annotations WHERE request_id=%s::uuid',(body['request_id'],)).fetchone()
        if old:
            if old['request_digest'] != digest: raise AnnotationError('request_id_conflict')
            return {'ok':True,'annotation':_api(old),'replayed':True}
        v = conn.execute('SELECT * FROM i13_current_transcripts WHERE provider_key=%s AND source_id=%s',(provider,source)).fetchone()
        if not v or str(v['id']) != body['version_id']: raise AnnotationError('stale_transcript_version')
        head = conn.execute('SELECT id FROM i13_transcript_annotations WHERE version_id=%s ORDER BY sequence DESC LIMIT 1',(v['id'],)).fetchone()
        if (str(head['id']) if head else None) != body['expected_head']: raise AnnotationError('stale_annotation_revision')
        t0,t1=validate_span(v['machine'],body['word_ids'])
        duration=next(s['duration_sec'] for s in corpus()['sources'] if (s['provider_key'],s['video_external_id'])==(provider,source))
        if t1 > duration: raise AnnotationError('selection_exceeds_source_duration')
        if not conn.execute('SELECT id FROM people WHERE id=%s::uuid',(actor,)).fetchone(): raise AnnotationError('owner_not_configured')
        person=body.get('person_id')
        if (body['speaker_state']=='person') != bool(person): raise AnnotationError('person_assignment_required')
        if person and not conn.execute('SELECT id FROM people WHERE id=%s::uuid',(person,)).fetchone(): raise AnnotationError('invalid_person')
        active = conn.execute('SELECT * FROM i13_active_annotations WHERE version_id=%s',(v['id'],)).fetchall()
        prior = body.get('supersedes')
        if prior:
            matching=next((a for a in active if str(a['id'])==prior),None)
            if not matching or [str(x) for x in matching['word_ids']] != body['word_ids']:
                raise AnnotationError('revision_must_match_active_span')
        elif body['action']=='withdraw': raise AnnotationError('withdraw_requires_active_revision')
        selected=set(body['word_ids'])
        for a in active:
            if str(a['id'])!=prior and selected.intersection(str(x) for x in a['word_ids']):
                raise AnnotationError('overlap_requires_exact_revision')
        row=conn.execute("""INSERT INTO i13_transcript_annotations
        (version_id,word_ids,t_start,t_end,action,speaker_state,person_id,correction,actor_id,reason,supersedes,request_id,request_digest)
        VALUES (%s,%s::uuid[],%s,%s,%s,%s,%s::uuid,%s,%s::uuid,%s,%s::uuid,%s::uuid,%s) RETURNING *""",
        (v['id'],body['word_ids'],t0,t1,body['action'],body['speaker_state'],person,body.get('correction'),actor,body['reason'],prior,body['request_id'],digest)).fetchone()
    return {'ok':True,'annotation':_api(row),'replayed':False}

def transcript(provider, source):
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if not provider:
            ps=conn.execute('SELECT DISTINCT provider_key FROM i13_current_transcripts WHERE source_id=%s',(source,)).fetchall()
            if len(ps)>1: raise AnnotationError('provider_required_for_ambiguous_source')
            provider=str(ps[0]['provider_key']) if ps else ''
        v=conn.execute('SELECT * FROM i13_current_transcripts WHERE provider_key=%s AND source_id=%s',(provider,source)).fetchone()
        if not v:
            queue=conn.execute("SELECT status,reason,enqueue_reason FROM speech_queue_items WHERE video_provider_key=%s AND video_external_id=%s AND enqueue_reason='transcribe' ORDER BY updated_at DESC NULLS LAST,created_at DESC LIMIT 1",(provider,source)).fetchone()
            return {'ok':True,'words':[],'turns':[],'moments':[],'full_text':'','word_count':0,'queue':_api(queue)}
        words=[_api(r) for r in conn.execute('SELECT * FROM i13_effective_words WHERE version_id=%s ORDER BY word_index',(v['id'],)).fetchall()]
        moments=[_api(r) for r in conn.execute('SELECT * FROM i13_effective_moments WHERE version_id=%s ORDER BY t_start',(v['id'],)).fetchall()]
        history=[_api(r) for r in conn.execute('SELECT a.*,(a.version_id<>%s) AS stale FROM i13_transcript_annotations a JOIN i13_transcript_versions v ON v.id=a.version_id WHERE v.provider_key=%s AND v.source_id=%s ORDER BY a.sequence',(v['id'],provider,source)).fetchall()]
        current=[a for a in history if not a['stale']]
        editable=any((s['provider_key'],s['video_external_id'])==(provider,source) for s in corpus()['sources'])
        return {'ok':True,'video_external_id':source,'provider_key':provider,'version_id':str(v['id']),
            'expected_head':current[-1]['id'] if current else None,'annotation_enabled':editable,
            'machine':v['machine'],'words':words,'turns':v['machine']['turns'],'moments':moments,
            'history':history,'full_text':' '.join(w['token'] for w in words if w['token']),
            'word_count':len(words),'queue':None}

def export_coverage():
    manifest=corpus()
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        result=[]
        for source in manifest['sources']:
            v=conn.execute('SELECT * FROM i13_current_transcripts WHERE provider_key=%s AND source_id=%s',(source['provider_key'],source['video_external_id'])).fetchone()
            truth=[]; count=0; covered=set()
            if v:
                count=len(v['machine']['words'])
                truth=[_api(r) for r in conn.execute('SELECT * FROM i13_active_annotations WHERE version_id=%s ORDER BY t_start',(v['id'],)).fetchall()]
                covered={x for a in truth for x in a['word_ids']}
            result.append({'provider_key':source['provider_key'],'source_id':source['video_external_id'],
                'source_sha256':source['source_sha256'],'version_id':str(v['id']) if v else None,
                'word_count':count,'reviewed_words':len(covered),'unreviewed_words':count-len(covered),
                'transcript_available':bool(count),'truth':truth,'coverage_tags':[],
                'coverage_review_complete':False})
    return {'read_only':True,'manifest_id':manifest['id'],'manifest_version':manifest['version'],
        'sources':result,'limits':'Word coverage only. Face/audio quality and scenario coverage require separate owner review.'}
