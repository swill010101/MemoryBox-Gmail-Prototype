"""Read-only preflight for the one selected Eugene T1 retirement; no mutation or media access."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from memorybox.db import connection

ADMISSION_ID='1039c733-2149-40b2-b027-97058e032af3'
ANNOTATION_ID='d5a3d050-76d6-446e-91d4-ff89986856cb'
PERSON_ID='b67708d8-0262-404d-a230-2cc99900cea4'
EXPECTED_OUTCOMES=['H1','O1','U1-clear']
QUERY="""
SELECT a.state, r.stale, s->>'key' AS training_key, s->>'person_id' AS person_id,
       (aa.id IS NOT NULL) AS annotation_active,
       (ret.annotation_id IS NOT NULL) AS retired,
       r.payload->'results' AS outcomes
FROM i13_processing_admissions a
JOIN i13_voice_pilot_results r ON r.admission_id=a.id
CROSS JOIN LATERAL jsonb_array_elements(a.plan_json->'spans') s
LEFT JOIN i13_active_annotations aa ON aa.id=(s->>'annotation_id')::uuid
LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id=(s->>'annotation_id')::uuid
WHERE a.id=%s::uuid AND s->>'annotation_id'=%s AND s->>'role'='training'
"""
def validate_candidate(row: dict) -> dict:
    if not row or row['state']!='stopped' or row['stale'] or row['training_key']!='T1': raise RuntimeError('T1 admission is not a current stopped result')
    if row['person_id']!=PERSON_ID or not row['annotation_active'] or row['retired']: raise RuntimeError('T1 reference is no longer eligible')
    if sorted(x.get('key') for x in (row['outcomes'] or []))!=EXPECTED_OUTCOMES: raise RuntimeError('T1 dependent outcomes changed')
    return {'admission_id':ADMISSION_ID,'annotation_id':ANNOTATION_ID,'training_key':'T1',
            'dependent_outcomes':EXPECTED_OUTCOMES,'current_result_stale':False,
            'expected_after_retirement':'Only admission 1039c733-2149-40b2-b027-97058e032af3 becomes stale; no reprocessing starts.'}
def main() -> int:
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        row=conn.execute(QUERY,(ADMISSION_ID,ANNOTATION_ID)).fetchone()
    result=validate_candidate(dict(row) if row else {})
    print(json.dumps({'ok':True,'mode':'check_only','private_audio_processed':False,'database_writes':False,**result},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
