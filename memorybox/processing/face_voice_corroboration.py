"""Read-only face/voice corroboration for bounded I13 owner assignments.

Face and voice evidence remain independent. This module reports interval overlap and
pilot outcomes transparently; it does not merge scores or override either modality.
"""
from __future__ import annotations

from typing import Any

from memorybox.processing.i13_canonical_assignments import (
    CANONICAL_EIGHT,
    CATEGORY_PILOT_EVIDENCE,
    PROVIDER,
)

POLICY_VERSION = "i13-fvc-v1"
POLICY_SUMMARY = (
    "Face and voice evidence remain independent. Corroboration reports same-source "
    "interval overlap and bounded voice-pilot outcomes only; it never merges "
    "confidence or replaces owner review."
)

FACE_QUERY = """
SELECT id::text, person_id::text, start_sec, end_sec, method, confidence,
       confirmation_state, authority, COALESCE(status, 'accepted') AS status
FROM face_appearance_moments
WHERE video_provider_key = %s AND video_external_id = %s
  AND start_sec < %s AND end_sec > %s
ORDER BY start_sec
"""

VOICE_PILOT_QUERY = """
SELECT r.admission_id::text, r.stale, r.created_at, r.payload,
       a.state, a.plan_json->'spans' AS spans,
       a.plan_json->'thresholds' AS thresholds
FROM i13_voice_pilot_results r
JOIN i13_processing_admissions a ON a.id = r.admission_id
ORDER BY r.created_at DESC
"""


def intervals_overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    return float(start_a) < float(end_b) and float(start_b) < float(end_a)


def classify_corroboration(
    *,
    voice_person_id: str | None,
    speaker_state: str | None,
    matrix_role: str,
    face_moments: list[dict[str, Any]],
) -> dict[str, Any]:
    unknown = speaker_state == "unknown" or not voice_person_id
    same_person = [
        moment
        for moment in face_moments
        if voice_person_id and moment.get("person_id") == voice_person_id
    ]
    other_person = [
        moment
        for moment in face_moments
        if voice_person_id and moment.get("person_id") not in (None, voice_person_id)
    ]
    off_camera_expected = matrix_role == "tom_offcamera_held_out"

    if unknown:
        return {
            "status": "voice_unknown",
            "expected_off_camera": False,
            "summary": "Voice interval has no assigned Person; overlapping face evidence is listed independently.",
            "face_overlap_count": len(face_moments),
            "same_person_face_count": 0,
            "other_person_face_count": 0,
        }
    if same_person:
        return {
            "status": "corroborated",
            "expected_off_camera": off_camera_expected,
            "summary": "Independent face and voice evidence agree on the same Person for this interval.",
            "same_person_face_count": len(same_person),
            "other_person_face_count": len(other_person),
        }
    if other_person:
        return {
            "status": "face_other_person",
            "expected_off_camera": off_camera_expected,
            "summary": "Face evidence overlaps a different Person than the owner voice assignment.",
            "same_person_face_count": 0,
            "other_person_face_count": len(other_person),
        }
    if off_camera_expected:
        return {
            "status": "off_camera_voice_only",
            "expected_off_camera": True,
            "summary": "Off-camera voice assignment with no same-Person face overlap; absence of face is expected.",
            "same_person_face_count": 0,
            "other_person_face_count": 0,
        }
    return {
        "status": "voice_only",
        "expected_off_camera": False,
        "summary": "Owner voice assignment exists without overlapping same-Person face evidence on this interval.",
        "same_person_face_count": 0,
        "other_person_face_count": 0,
    }


def _serialize_face(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "moment_id": row.get("id"),
        "person_id": row.get("person_id"),
        "start_sec": float(row.get("start_sec") or 0),
        "end_sec": float(row.get("end_sec") or 0),
        "method": row.get("method"),
        "confidence": row.get("confidence"),
        "confirmation_state": row.get("confirmation_state"),
        "authority": row.get("authority"),
        "status": row.get("status"),
    }


def _voice_evidence_for_annotation(
    annotation_id: str,
    pilot_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for row in pilot_rows:
        spans = {str(span.get("annotation_id")): span for span in (row.get("spans") or [])}
        span = spans.get(annotation_id)
        if not span:
            continue
        outcomes = {
            str(outcome.get("key")): outcome
            for outcome in (row.get("payload") or {}).get("results") or []
        }
        outcome = outcomes.get(str(span.get("key")))
        if not outcome:
            continue
        return {
            "admission_id": row.get("admission_id"),
            "span_key": span.get("key"),
            "stale": bool(row.get("stale")),
            "state": row.get("state"),
            "created_at": row.get("created_at"),
            "decision": outcome.get("decision"),
            "score": outcome.get("score"),
            "expected_match": outcome.get("expected_match"),
            "thresholds": row.get("thresholds"),
        }
    return None


def _load_face_moments(conn, provider: str, source_id: str, start: float, end: float) -> list[dict[str, Any]]:
    rows = conn.execute(FACE_QUERY, (provider, source_id, end, start)).fetchall()
    return [_serialize_face(dict(row)) for row in rows]


def _load_voice_pilot_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(VOICE_PILOT_QUERY).fetchall()
    return [dict(row) for row in rows]


def build_report(*, conn) -> dict[str, Any]:
    pilot_rows = _load_voice_pilot_rows(conn)
    assignments: list[dict[str, Any]] = []
    for item in CANONICAL_EIGHT:
        start = float(item["start"])
        end = float(item["end"])
        source_id = str(item["source_id"])
        face_moments = _load_face_moments(conn, PROVIDER, source_id, start, end)
        voice_evidence = _voice_evidence_for_annotation(str(item["annotation_id"]), pilot_rows)
        classification = classify_corroboration(
            voice_person_id=item.get("person_id"),
            speaker_state=item.get("speaker_state", "person" if item.get("person_id") else "unknown"),
            matrix_role=str(item["matrix_role"]),
            face_moments=face_moments,
        )
        assignments.append(
            {
                "key": item["key"],
                "matrix_role": item["matrix_role"],
                "annotation_id": item["annotation_id"],
                "source_id": source_id,
                "provider_key": PROVIDER,
                "interval": {"start_sec": start, "end_sec": end},
                "voice_person_id": item.get("person_id"),
                "speaker_state": item.get("speaker_state", "person" if item.get("person_id") else "unknown"),
                "face_evidence": face_moments,
                "voice_evidence": voice_evidence,
                "corroboration": classification,
                "notes": item.get("notes"),
            }
        )

    status_counts: dict[str, int] = {}
    for row in assignments:
        status = row["corroboration"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "ok": True,
        "read_only": True,
        "processing_started": False,
        "policy_version": POLICY_VERSION,
        "policy_summary": POLICY_SUMMARY,
        "assignment_count": len(assignments),
        "status_counts": status_counts,
        "assignments": assignments,
        "category_pilot_evidence": CATEGORY_PILOT_EVIDENCE,
        "limits": (
            "Bounded canonical eight assignments only. Independent evidence is preserved; "
            "corroboration does not authorize processing or change stored face/voice records."
        ),
    }


def build_report_from_connection() -> dict[str, Any]:
    from memorybox.db import connection

    with connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return build_report(conn=conn)
