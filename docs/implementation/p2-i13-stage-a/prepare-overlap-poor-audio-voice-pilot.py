"""Read-only preflight for the bounded overlap/poor-audio Eugene voice pilot proposal."""
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
PROPOSAL = ROOT / "docs/implementation/p2-i13-stage-a/overlap-poor-audio-voice-pilot-proposal.json"


def load_selection(path: Path = PROPOSAL) -> dict:
    proposal = json.loads(path.read_text(encoding="utf-8-sig"))
    if proposal.get("processing_authorized") is not False or proposal.get("purpose") != "voice_pilot":
        raise RuntimeError("Proposal is not design-only voice-pilot evidence.")
    spans = proposal.get("selections")
    if not isinstance(spans, list) or len(spans) != 4:
        raise RuntimeError("Proposal must contain exactly four spans.")
    if [span.get("role") for span in spans] != ["training", "held_out", "held_out", "held_out"]:
        raise RuntimeError("Proposal span roles changed.")
    if not proposal.get("founder_waiver_ref") or not proposal.get("owner_interval_confirmation_ref"):
        raise RuntimeError("Founder waiver and owner interval confirmation must be recorded before preflight.")
    return proposal


def same_timestamp(actual: object, expected: object) -> bool:
    return abs(float(actual) - float(expected)) <= 0.000001


def validate_rows(proposal: dict, rows: list[dict]) -> dict:
    by_id = {row["annotation_id"]: row for row in rows}
    expected = {span["annotation_id"]: span for span in proposal["selections"]}
    if set(by_id) != set(expected):
        raise RuntimeError("Selected annotations changed or are unavailable.")

    for annotation_id, span in expected.items():
        row = by_id[annotation_id]
        for key in ("version_id", "source_id", "provider_key"):
            if row[key] != span[key]:
                raise RuntimeError("Selected annotation identity changed.")
        if not same_timestamp(row["t_start"], span["start"]) or not same_timestamp(row["t_end"], span["end"]):
            raise RuntimeError("Selected annotation timing changed.")
        if not row["active"] or row["retired"]:
            raise RuntimeError("Selected annotation is not active evidence.")

        key = span["key"]
        uses = row.get("pilot_uses") or []
        if key == "T-gs2-reuse":
            if row["person_id"] != EUGENE_ID or row["speaker_state"] != "person":
                raise RuntimeError("Eugene training reference changed.")
        elif key == "E2-1532-overlap-held-out":
            if row["person_id"] != EUGENE_ID or row["speaker_state"] != "person":
                raise RuntimeError("Eugene overlap held-out changed.")
            if uses:
                raise RuntimeError("Overlap held-out annotation already used in a prior voice pilot.")
        elif key == "O2-tom-offcamera-negative":
            if row["person_id"] != TOM_ID or row["speaker_state"] != "person":
                raise RuntimeError("Tom off-camera control changed.")
            if uses:
                raise RuntimeError("Tom off-camera control already used in a prior voice pilot.")
        elif key == "N1-TV-announcer-unknown":
            if row["person_id"] is not None or row["speaker_state"] != "unknown":
                raise RuntimeError("Unknown TV announcer control changed.")
        else:
            raise RuntimeError("Unexpected span key.")

    return {
        "work_items": 4,
        "audio_seconds": proposal["budget"]["selected_audio_seconds"],
        "training_key": proposal["selections"][0]["key"],
        "held_out_keys": [span["key"] for span in proposal["selections"][1:]],
        "founder_waiver_ref": proposal["founder_waiver_ref"],
        "owner_interval_confirmation_ref": proposal["owner_interval_confirmation_ref"],
    }


def main() -> int:
    if os.environ.get("MEMORYBOX_RECOGNITION_DRAIN") != "0" or os.environ.get("MEMORYBOX_SPEECH_DRAIN") != "0":
        raise RuntimeError("Both drains must be explicitly off.")
    if os.environ.get("MEMORYBOX_I13_ADMISSION_ID"):
        raise RuntimeError("Admission must be unset for preflight.")

    from memorybox.db import connection

    proposal = load_selection()
    ids = [span["annotation_id"] for span in proposal["selections"]]
    query = """
    SELECT a.id::text AS annotation_id, a.version_id::text AS version_id,
           v.provider_key, v.source_id, a.t_start, a.t_end,
           a.person_id::text AS person_id, a.speaker_state,
           (active.id IS NOT NULL) AS active,
           (ret.annotation_id IS NOT NULL) AS retired,
           COALESCE(uses.pilot_uses, '[]'::jsonb) AS pilot_uses
    FROM i13_transcript_annotations a
    JOIN i13_transcript_versions v ON v.id=a.version_id
    LEFT JOIN i13_active_annotations active ON active.id=a.id
    LEFT JOIN i13_voice_pilot_retirements ret ON ret.annotation_id=a.id
    LEFT JOIN LATERAL (
      SELECT jsonb_agg(jsonb_build_object('admission_id', ad.id::text, 'key', span->>'key', 'role', span->>'role')) AS pilot_uses
      FROM i13_processing_admissions ad
      CROSS JOIN LATERAL jsonb_array_elements(ad.plan_json->'spans') span
      WHERE ad.plan_json->>'purpose'='voice_pilot' AND span->>'annotation_id'=a.id::text
    ) uses ON true
    WHERE a.id = ANY(%s::uuid[])
    """
    with connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = [dict(row) for row in conn.execute(query, (ids,)).fetchall()]
    result = validate_rows(proposal, rows)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "check_only",
                "private_audio_processed": False,
                "database_writes": False,
                "admission_created": False,
                **result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": "validation_failed",
                    "code": str(exc),
                    "message": "Preflight failed; no media or database writes occurred.",
                }
            )
        )
        raise SystemExit(2)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "message": "Preflight failed; no media or database writes occurred.",
                }
            )
        )
        raise SystemExit(2)
