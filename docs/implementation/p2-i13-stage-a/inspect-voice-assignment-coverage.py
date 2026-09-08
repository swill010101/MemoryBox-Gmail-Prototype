"""Read-only coverage of the canonical eight owner voice assignments vs I13 matrix categories.

Maps founder-reviewed assignments to the five required evidence categories, checks that
no annotation serves both training and held-out in the same pilot role set, and records
which stopped voice-pilot admissions already measured each category.

Never processes media or writes database state. Optional JSON output path via
MEMORYBOX_I13_COVERAGE_OUTPUT (use E: paths; do not commit private exports).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybox.processing.i13_canonical_assignments import (  # noqa: E402
    CANONICAL_EIGHT,
    CATEGORIES,
    CATEGORY_PILOT_EVIDENCE,
)

ACTIVE_QUERY = """
SELECT a.id::text AS annotation_id,
       a.version_id::text AS version_id,
       v.source_id,
       a.t_start,
       a.t_end,
       a.person_id::text AS person_id,
       a.speaker_state,
       (ret.annotation_id IS NOT NULL) AS retired
FROM i13_active_annotations active
JOIN i13_transcript_annotations a ON a.id = active.id
JOIN i13_transcript_versions v ON v.id = a.version_id
LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id = a.id
WHERE a.id = ANY(%s::uuid[])
"""


def _load_db_active(ids: list[str]) -> dict[str, dict]:
    from memorybox.db import connection

    with connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = conn.execute(ACTIVE_QUERY, (ids,)).fetchall()
    return {str(row["annotation_id"]): dict(row) for row in rows}


def _role_conflicts() -> list[str]:
    training = {item["annotation_id"] for item in CANONICAL_EIGHT if item["pilot_role"] == "training"}
    held_out = {item["annotation_id"] for item in CANONICAL_EIGHT if item["pilot_role"] == "held_out"}
    overlap = training & held_out
    return [f"annotation {aid} appears in both training and held-out sets" for aid in sorted(overlap)]


def build_report(*, db_active: dict[str, dict] | None = None) -> dict:
    conflicts = _role_conflicts()
    rows = []
    for item in CANONICAL_EIGHT:
        active = (db_active or {}).get(item["annotation_id"])
        rows.append(
            {
                **item,
                "active_in_db": active is not None if db_active is not None else None,
                "retired_in_db": active.get("retired") if active else None,
                "db_interval": (
                    {"start": active["t_start"], "end": active["t_end"]} if active else None
                ),
            }
        )

    category_table = []
    missing = []
    for category in CATEGORIES:
        assignments = [r for r in rows if r["matrix_role"] == category]
        evidence = CATEGORY_PILOT_EVIDENCE.get(category, [])
        current_evidence = [e for e in evidence if not e.get("stale")]
        ok = bool(assignments) and bool(current_evidence)
        if not ok:
            missing.append(category)
        category_table.append(
            {
                "category": category,
                "assignments": [{"key": a["key"], "annotation_id": a["annotation_id"]} for a in assignments],
                "current_pilot_evidence": current_evidence,
                "satisfied": ok,
            }
        )

    return {
        "ok": not conflicts and not missing,
        "read_only": True,
        "checkpoint_note": "Repository checkpoint includes Gate 3 complete and six stopped current voice pilots; this report validates the canonical eight assignments against the five-category matrix.",
        "canonical_assignment_count": len(CANONICAL_EIGHT),
        "assignments": rows,
        "category_coverage": category_table,
        "training_held_out_conflicts": conflicts,
        "missing_categories": missing,
        "smallest_next_pilot": (
            "none_required"
            if not missing and not conflicts
            else "design_new_plan_for_missing_categories_only"
        ),
        "additional_annotation_required": False if not missing else True,
        "limits": "Matrix coverage only. Face/voice corroboration and full I13 acceptance are separate.",
    }


def main() -> int:
    db_active = None
    try:
        ids = [item["annotation_id"] for item in CANONICAL_EIGHT]
        db_active = _load_db_active(ids)
    except Exception as exc:
        db_active = None
        db_error = f"{type(exc).__name__}: {exc}"
    else:
        db_error = None

    report = build_report(db_active=db_active)
    if db_error:
        report["db_unavailable"] = db_error
        report["note"] = "Category satisfaction uses pinned admissions from repo reports when DB is unavailable."

    out_path = os.environ.get("MEMORYBOX_I13_COVERAGE_OUTPUT", "").strip()
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["output_file"] = str(path)

    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
