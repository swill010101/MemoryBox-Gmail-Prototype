"""Read-only inspection of eligible older voice-pilot references; never retires or processes media."""
from __future__ import annotations
import json
from memorybox.db import connection

QUERY = """
SELECT a.id::text AS admission_id, a.state, r.created_at, r.stale,
       s->>'annotation_id' AS annotation_id, s->>'key' AS span_key,
       s->>'source_id' AS source_id, s->>'version_id' AS version_id,
       s->>'person_id' AS person_id,
       (aa.id IS NOT NULL) AS annotation_active,
       (ret.annotation_id IS NOT NULL) AS retired,
       r.payload->'results' AS outcomes
FROM i13_voice_pilot_results r
JOIN i13_processing_admissions a ON a.id=r.admission_id
CROSS JOIN LATERAL jsonb_array_elements(a.plan_json->'spans') s
LEFT JOIN i13_active_annotations aa ON aa.id=(s->>'annotation_id')::uuid
LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id=(s->>'annotation_id')::uuid
WHERE a.plan_json->>'purpose'='voice_pilot'
  AND s->>'role'='training'
ORDER BY r.created_at ASC
"""

def main() -> int:
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows=conn.execute(QUERY).fetchall()
    candidates=[]
    for row in rows:
        d=dict(row)
        eligible=(d['state']=='stopped' and not d['stale'] and d['annotation_active'] and not d['retired'])
        candidates.append({
            'admission_id':d['admission_id'],'created_at':str(d['created_at']),'state':d['state'],
            'result_stale':d['stale'],'training_annotation_id':d['annotation_id'],
            'training_key':d['span_key'],'source_id':d['source_id'],'version_id':d['version_id'],
            'person_id':d['person_id'],'annotation_active':d['annotation_active'],'retired':d['retired'],
            'eligible_for_separate_retirement_proposal':eligible,
            'outcome_keys':[x.get('key') for x in (d['outcomes'] or [])],
        })
    print(json.dumps({'read_only':True,'private_audio_processed':False,'database_writes':False,
                      'candidates':candidates,
                      'next':'Choose one eligible older admission only; retirement requires separate approval and never starts reprocessing.'},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
