"""Read-only inventory of fresh Eugene voice-reference candidates; never processes media or writes data."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from memorybox.db import connection

PERSON_ID='b67708d8-0262-404d-a230-2cc99900cea4'
QUERY="""
SELECT a.id::text AS annotation_id, a.version_id::text AS version_id, v.provider_key, v.source_id,
       a.t_start, a.t_end, cardinality(a.word_ids) AS words, a.reason,
       (ret.annotation_id IS NOT NULL) AS retired,
       COALESCE(uses.pilot_uses, '[]'::jsonb) AS pilot_uses
FROM i13_active_annotations a
JOIN i13_transcript_versions v ON v.id=a.version_id
LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id=a.id
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object('admission_id',ad.id::text,'key',span->>'key','role',span->>'role')
                   ORDER BY ad.created_at, span->>'key') AS pilot_uses
  FROM i13_processing_admissions ad
  CROSS JOIN LATERAL jsonb_array_elements(ad.plan_json->'spans') span
  WHERE ad.plan_json->>'purpose'='voice_pilot' AND span->>'annotation_id'=a.id::text
) uses ON true
WHERE a.person_id=%s::uuid
ORDER BY a.t_start, a.created_at
"""

def classify(row: dict) -> dict:
    uses=row.get('pilot_uses') or []
    return {
        'annotation_id':row['annotation_id'], 'version_id':row['version_id'],
        'provider_key':row['provider_key'], 'source_id':row['source_id'],
        't_start':float(row['t_start']), 't_end':float(row['t_end']), 'words':int(row['words']),
        'reason':row['reason'], 'retired':bool(row['retired']), 'prior_pilot_uses':uses,
        # A fresh reprocessing reference must be active, unretired, and absent from every past pilot.
        'eligible_fresh_reference':not row['retired'] and not uses,
    }

def main() -> int:
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows=[classify(dict(row)) for row in conn.execute(QUERY,(PERSON_ID,)).fetchall()]
    eligible=[row for row in rows if row['eligible_fresh_reference']]
    next_step=('Select exactly one listed fresh reference for a new bounded reprocessing proposal.' if eligible
               else 'No fresh Eugene reference exists. Save one new clear Eugene owner assignment in MemoryBox; do not edit or reuse retired T1.')
    print(json.dumps({'ok':True,'read_only':True,'private_audio_processed':False,'database_writes':False,
                      'person_id':PERSON_ID,'candidates':rows,'fresh_reference_count':len(eligible),'next':next_step},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
