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

EUGENE = "b67708d8-0262-404d-a230-2cc99900cea4"
TOM = "33509a4c-0869-458a-b0b9-35a669aace16"

CATEGORIES = (
    "eugene_training",
    "eugene_held_out",
    "tom_training",
    "tom_offcamera_held_out",
    "uncertain_no_match",
)

# Canonical eight founder-reviewed assignments (pinned IDs from FlightSim export 2026-09-08).
CANONICAL_EIGHT = [
    {
        "key": "T1",
        "matrix_role": "eugene_training",
        "pilot_role": "training",
        "annotation_id": "d5a3d050-76d6-446e-91d4-ff89986856cb",
        "source_id": "vid-da41273dbd9ac4bb",
        "start": 138.72,
        "end": 144.66,
        "person_id": EUGENE,
        "notes": "Original Eugene training; reference retired — admission 1039c733 stale",
    },
    {
        "key": "H1",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "f47ee4ec-6b28-442a-81b2-152fbe8f45e2",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 325.22,
        "end": 345.56,
        "person_id": EUGENE,
        "notes": "Eugene positive held-out in original Eugene pilot",
    },
    {
        "key": "U1-clear",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "5651a4bd-dffd-4d26-a985-16e8abaf37c2",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 129.64,
        "end": 138.72,
        "person_id": EUGENE,
        "notes": "Clear portion of former U1 window; remainder unreviewed",
    },
    {
        "key": "O1",
        "matrix_role": "tom_offcamera_held_out",
        "pilot_role": "held_out",
        "annotation_id": "3fa1c4e1-d8a6-423f-9c9b-1a229d550945",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 152.24,
        "end": 158.34,
        "person_id": TOM,
        "notes": "Owner-confirmed off-camera Tom; Tom pilot positive held-out",
    },
    {
        "key": "T2",
        "matrix_role": "tom_training",
        "pilot_role": "training",
        "annotation_id": "5e106e50-76ce-4fb2-8f62-0083119154cc",
        "source_id": "vid-da41273dbd9ac4bb",
        "start": 37.12,
        "end": 42.4,
        "person_id": TOM,
        "notes": "Tom training reference for Tom/N1/Patio/reprocessing/overlap controls",
    },
    {
        "key": "N1",
        "matrix_role": "uncertain_no_match",
        "pilot_role": "held_out",
        "annotation_id": "74cc9646-82db-4899-960d-f795f691c524",
        "source_id": "vid-c015e0fe07414fcc",
        "start": 0.0,
        "end": 6.74,
        "person_id": None,
        "speaker_state": "unknown",
        "notes": "TV announcer; Unknown — never assign a Person",
    },
    {
        "key": "R1-gs2-fresh",
        "matrix_role": "eugene_training",
        "pilot_role": "training",
        "annotation_id": "3eb88a19-7249-4ce6-b976-e3066daf205a",
        "source_id": "vid-34df63e61b949890",
        "start": 26.3,
        "end": 34.78,
        "person_id": EUGENE,
        "notes": "Current Eugene training after T1 retirement; reused in overlap pilot",
    },
    {
        "key": "H1-gs2-held-out",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "5d87a6ac-d512-4504-857e-ec8589e8bd78",
        "source_id": "vid-34df63e61b949890",
        "start": 86.42,
        "end": 105.44,
        "person_id": EUGENE,
        "notes": "Lifecycle Eugene held-out on grandpa 002",
    },
]

# Stopped admissions that satisfy each matrix category (do not retry).
CATEGORY_PILOT_EVIDENCE = {
    "eugene_training": [
        {"admission_id": "66fb93af-92a9-4ef1-b3e6-c0f700e89276", "training_key": "R1-gs2-fresh", "stale": False},
        {"admission_id": "1039c733-2149-40b2-b027-97058e032af3", "training_key": "T1", "stale": True},
    ],
    "eugene_held_out": [
        {"admission_id": "1039c733-2149-40b2-b027-97058e032af3", "keys": ["H1", "U1-clear"], "stale": True},
        {"admission_id": "66fb93af-92a9-4ef1-b3e6-c0f700e89276", "keys": ["H1-gs2-held-out"], "stale": False},
        {"admission_id": "339b3a14-5069-4554-846f-dc84d6745c00", "keys": ["E2-1532-overlap-held-out"], "stale": False},
        {"admission_id": "f59050d5-cb4b-4ff7-beee-609b28f7af61", "keys": ["E3-patio-held-out"], "stale": False},
    ],
    "tom_training": [
        {"admission_id": "9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea", "training_key": "T2", "stale": False},
    ],
    "tom_offcamera_held_out": [
        {"admission_id": "9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea", "keys": ["O1"], "decision": "match", "score": 0.487, "stale": False},
    ],
    "uncertain_no_match": [
        {"admission_id": "46cb1d21-b464-4bc4-bf7c-7d0de0202ca6", "keys": ["N1"], "decision": "no_match", "stale": False},
        {"admission_id": "339b3a14-5069-4554-846f-dc84d6745c00", "keys": ["N1-TV-announcer-unknown"], "decision": "no_match", "stale": False},
    ],
}

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
