"""Read-only inventory of all voice-pilot admissions and result staleness; never processes media or writes data."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from memorybox.db import connection

QUERY = """
SELECT a.id::text AS admission_id,
       a.state,
       r.stale,
       r.created_at,
       (SELECT s->>'key'
        FROM jsonb_array_elements(a.plan_json->'spans') s
        WHERE s->>'role' = 'training'
        LIMIT 1) AS training_key,
       (SELECT s->>'annotation_id'
        FROM jsonb_array_elements(a.plan_json->'spans') s
        WHERE s->>'role' = 'training'
        LIMIT 1) AS training_annotation_id,
       (SELECT count(*) FROM i13_voice_pilot_attempts att WHERE att.admission_id = a.id) AS attempts,
       r.payload->'results' AS results
FROM i13_processing_admissions a
JOIN i13_voice_pilot_results r ON r.admission_id = a.id
WHERE a.plan_json->>'purpose' = 'voice_pilot'
ORDER BY r.created_at ASC
"""


def main() -> int:
    with connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows = [dict(row) for row in conn.execute(QUERY).fetchall()]
    current = [row for row in rows if not row['stale']]
    stale = [row for row in rows if row['stale']]
    print(json.dumps({
        'ok': True,
        'read_only': True,
        'private_audio_processed': False,
        'database_writes': False,
        'admission_count': len(rows),
        'current_count': len(current),
        'stale_count': len(stale),
        'admissions': rows,
        'next': 'Use for Gate 2 evidence review only; no processing is authorized by this report.',
    }, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
