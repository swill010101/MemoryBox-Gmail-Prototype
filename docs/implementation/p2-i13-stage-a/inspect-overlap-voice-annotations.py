"""Read-only inventory of active Eugene/Tom voice annotations for overlap pilot planning."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EUGENE_ID = "b67708d8-0262-404d-a230-2cc99900cea4"
TOM_ID = "33509a4c-0869-458a-b0b9-35a669aace16"
EXCLUDED_EUGENE_SOURCE = "vid-c57dbd21f993f6d1"

QUERY = """
SELECT a.id::text AS annotation_id,
       a.version_id::text AS version_id,
       v.provider_key,
       v.source_id,
       s.relative_path,
       a.t_start,
       a.t_end,
       a.person_id::text AS person_id,
       p.display_name AS person_name,
       a.speaker_state,
       cardinality(a.word_ids) AS word_count,
       (ret.annotation_id IS NOT NULL) AS retired,
       COALESCE(uses.pilot_uses, '[]'::jsonb) AS pilot_uses
FROM i13_active_annotations active
JOIN i13_transcript_annotations a ON a.id = active.id
JOIN i13_transcript_versions v ON v.id = a.version_id
LEFT JOIN people p ON p.id = a.person_id
LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id = a.id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object('admission_id', ad.id::text, 'key', span->>'key')) AS pilot_uses
    FROM i13_processing_admissions ad
    CROSS JOIN LATERAL jsonb_array_elements(ad.plan_json->'spans') span
    WHERE ad.plan_json->>'purpose' = 'voice_pilot'
      AND span->>'annotation_id' = a.id::text
) uses ON true
LEFT JOIN LATERAL (
    SELECT src->>'relative_path' AS relative_path
    FROM jsonb_array_elements(%s::jsonb) src
    WHERE src->>'video_external_id' = v.source_id
    LIMIT 1
) s ON true
WHERE a.person_id IN (%s::uuid, %s::uuid)
   OR (a.person_id IS NULL AND a.speaker_state = 'unknown')
ORDER BY v.source_id, a.t_start
"""


def main() -> int:
    manifest = json.loads(
        (Path(__file__).with_name("bounded-manifest-proposal.json")).read_text(encoding="utf-8-sig")
    )["manifest"]
    manifest_json = json.dumps(manifest["sources"])

    from memorybox.db import connection

    with connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = [
            dict(row)
            for row in conn.execute(QUERY, (manifest_json, EUGENE_ID, TOM_ID)).fetchall()
        ]

    eugene = [r for r in rows if r.get("person_id") == EUGENE_ID]
    tom = [r for r in rows if r.get("person_id") == TOM_ID]
    unknown = [r for r in rows if r.get("person_id") is None]
    eugene_on_1532 = [r for r in eugene if r["source_id"] == EXCLUDED_EUGENE_SOURCE]

    print(
        json.dumps(
            {
                "ok": True,
                "read_only": True,
                "eugene_active_count": len(eugene),
                "tom_active_count": len(tom),
                "unknown_active_count": len(unknown),
                "eugene_on_excluded_1532": eugene_on_1532,
                "eugene_annotations": eugene,
                "tom_annotations": tom,
                "unknown_annotations": unknown,
                "note": "Eugene assignments on vid-c57dbd21f993f6d1 must not train or held-out Eugene voice evidence.",
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": str(exc)}))
        raise SystemExit(2)
