"""Video face observations, appearance ranges, and correction withdrawals."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.recognition.constants import (
    LINEAGE_NATIVE,
    METHOD_NATIVE,
    RANGE_GAP_SEC,
)


def start_processing_run(
    *,
    person_id: str | None,
    run_kind: str,
    trigger: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO recognition_processing_runs (
                person_id, run_kind, trigger, status, meta_json
            ) VALUES (%s::uuid, %s, %s, 'running', %s::jsonb)
            RETURNING id::text
            """,
            (person_id, run_kind, trigger, json.dumps(meta or {})),
        ).fetchone()
    return str(row["id"])


def finish_processing_run(
    run_id: str,
    *,
    status: str = "completed",
    detail: str | None = None,
    candidate_count: int = 0,
    accepted_count: int = 0,
    uncertain_count: int = 0,
    range_count: int = 0,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE recognition_processing_runs SET
                status = %s, detail = %s,
                candidate_count = %s, accepted_count = %s,
                uncertain_count = %s, range_count = %s,
                finished_at = now()
            WHERE id = %s::uuid
            """,
            (
                status,
                detail,
                int(candidate_count),
                int(accepted_count),
                int(uncertain_count),
                int(range_count),
                run_id,
            ),
        )


def insert_observation(
    *,
    video_provider_key: str,
    video_external_id: str,
    t_sec: float,
    bbox: dict[str, Any] | None,
    person_id: str | None,
    confidence: float | None,
    match_score: float | None,
    review_state: str,
    embedding_model: str | None,
    exemplar_id: str | None,
    processing_run_id: str | None,
    meta: dict[str, Any] | None = None,
) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO video_face_observations (
                video_provider_key, video_external_id, t_sec, bbox_json,
                person_id, confidence, match_score, review_state,
                embedding_model, exemplar_id, processing_run_id, meta_json
            ) VALUES (
                %s, %s, %s, %s::jsonb, %s::uuid, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::jsonb
            )
            RETURNING id::text
            """,
            (
                video_provider_key,
                video_external_id,
                float(t_sec),
                json.dumps(bbox or {}),
                person_id,
                confidence,
                match_score,
                review_state,
                embedding_model,
                exemplar_id,
                processing_run_id,
                json.dumps(meta or {}),
            ),
        ).fetchone()
    return str(row["id"])


def delete_native_observations_for_video(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
) -> None:
    """Rebuildable I8B observations only — never touch I1/HVRT moments here."""
    with connection() as conn:
        conn.execute(
            """
            DELETE FROM video_face_observations
            WHERE video_external_id = %s
              AND (person_id = %s::uuid OR person_id IS NULL)
            """,
            (video_external_id, person_id),
        )
        conn.execute(
            """
            DELETE FROM face_appearance_moments
            WHERE person_id = %s::uuid
              AND video_external_id = %s
              AND (
                COALESCE(evidence_lineage, '') = %s
                OR COALESCE(method, '') = %s
              )
              AND COALESCE(status, 'accepted') <> 'withdrawn'
            """,
            (person_id, video_external_id, LINEAGE_NATIVE, LINEAGE_NATIVE),
        )


def group_assigned_into_ranges(
    observations: list[dict[str, Any]],
    *,
    gap_sec: float = RANGE_GAP_SEC,
) -> list[dict[str, Any]]:
    assigned = sorted(
        [o for o in observations if o.get("review_state") == "assigned" and o.get("person_id")],
        key=lambda o: float(o["t_sec"]),
    )
    ranges: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for o in assigned:
        t = float(o["t_sec"])
        if cur is None:
            cur = {
                "start_sec": t,
                "end_sec": t,
                "observation_ids": [o["id"]],
                "scores": [float(o.get("match_score") or 0)],
                "person_id": o["person_id"],
            }
            continue
        if t - float(cur["end_sec"]) <= gap_sec:
            cur["end_sec"] = t
            cur["observation_ids"].append(o["id"])
            cur["scores"].append(float(o.get("match_score") or 0))
        else:
            ranges.append(cur)
            cur = {
                "start_sec": t,
                "end_sec": t,
                "observation_ids": [o["id"]],
                "scores": [float(o.get("match_score") or 0)],
                "person_id": o["person_id"],
            }
    if cur:
        ranges.append(cur)
    for r in ranges:
        scores = r.pop("scores")
        r["confidence"] = max(scores) if scores else 0.0
        r["end_sec"] = max(float(r["end_sec"]), float(r["start_sec"]) + 0.5)
    return ranges


def persist_native_range(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    start_sec: float,
    end_sec: float,
    observation_ids: list[str],
    confidence: float,
    processing_run_id: str | None,
    model_version: str,
    meta: dict[str, Any] | None = None,
) -> str:
    from memorybox.recognition.process import (
        ensure_timeslot_play_url,
        upsert_appearance_moment,
    )

    mid = upsert_appearance_moment(
        person_id=person_id,
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        start_sec=start_sec,
        end_sec=end_sec,
        face_external_id=None,
        method=METHOD_NATIVE,
        confidence=confidence,
        confirmation_state="system_associated",
        play_url=ensure_timeslot_play_url(
            video_external_id=video_external_id,
            start_sec=start_sec,
            video_provider_key=video_provider_key,
        ),
        meta={"processing_run_id": processing_run_id, **(meta or {})},
    )
    ids = [UUID(x) for x in observation_ids if x]
    with connection() as conn:
        conn.execute(
            """
            UPDATE face_appearance_moments SET
                evidence_lineage = %s,
                model_version = %s,
                observation_ids = %s::uuid[],
                processing_run_id = %s::uuid,
                status = 'accepted',
                updated_at = now()
            WHERE id = %s::uuid
            """,
            (LINEAGE_NATIVE, model_version, ids, processing_run_id, mid),
        )
    return mid


def record_withdrawal(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    start_sec: float,
    end_sec: float,
    appearance_id: str | None = None,
    observation_id: str | None = None,
    reason: str | None = None,
) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO identity_withdrawals (
                person_id, video_provider_key, video_external_id,
                start_sec, end_sec, appearance_id, observation_id, reason
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid, %s::uuid, %s)
            RETURNING id::text
            """,
            (
                person_id,
                video_provider_key,
                video_external_id,
                float(start_sec),
                float(end_sec),
                appearance_id,
                observation_id,
                reason,
            ),
        ).fetchone()
        if appearance_id:
            conn.execute(
                """
                UPDATE face_appearance_moments
                SET status = 'withdrawn', confirmation_state = 'owner_corrected',
                    updated_at = now()
                WHERE id = %s::uuid
                """,
                (appearance_id,),
            )
        conn.execute(
            """
            UPDATE video_face_observations
            SET review_state = 'withdrawn', person_id = NULL
            WHERE video_provider_key = %s AND video_external_id = %s
              AND person_id = %s::uuid
              AND t_sec >= %s AND t_sec <= %s
            """,
            (
                video_provider_key,
                video_external_id,
                person_id,
                float(start_sec) - 0.05,
                float(end_sec) + 0.05,
            ),
        )
    return str(row["id"])


def list_withdrawals(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id::text, start_sec, end_sec, reason, created_at
            FROM identity_withdrawals
            WHERE person_id = %s::uuid
              AND video_provider_key = %s
              AND video_external_id = %s
            """,
            (person_id, video_provider_key, video_external_id),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


def overlaps_withdrawal(t_sec: float, withdrawals: list[dict[str, Any]]) -> bool:
    t = float(t_sec)
    for w in withdrawals:
        if float(w["start_sec"]) - 0.25 <= t <= float(w["end_sec"]) + 0.25:
            return True
    return False


def recognition_status(*, person_id: str | None = None) -> dict[str, Any]:
    with connection() as conn:
        if person_id:
            obs = conn.execute(
                """
                SELECT review_state, COUNT(*)::int AS n
                FROM video_face_observations
                WHERE person_id = %s::uuid OR person_id IS NULL
                GROUP BY review_state
                """,
                (person_id,),
            ).fetchall()
            ranges = conn.execute(
                """
                SELECT COALESCE(evidence_lineage, 'unknown') AS lineage,
                       COALESCE(status, 'accepted') AS status,
                       COUNT(*)::int AS n
                FROM face_appearance_moments
                WHERE person_id = %s::uuid
                GROUP BY 1, 2
                """,
                (person_id,),
            ).fetchall()
            latest = conn.execute(
                """
                SELECT id::text, run_kind, status, candidate_count, accepted_count,
                       uncertain_count, range_count, started_at, finished_at, detail
                FROM recognition_processing_runs
                WHERE person_id = %s::uuid
                ORDER BY started_at DESC
                LIMIT 5
                """,
                (person_id,),
            ).fetchall()
            exemplars = conn.execute(
                """
                SELECT COUNT(*)::int AS n FROM face_evidence
                WHERE person_id = %s::uuid
                  AND COALESCE(withdrawn, false) = false
                  AND embedding_json IS NOT NULL
                """,
                (person_id,),
            ).fetchone()
        else:
            obs = conn.execute(
                """
                SELECT review_state, COUNT(*)::int AS n
                FROM video_face_observations
                GROUP BY review_state
                """
            ).fetchall()
            ranges = conn.execute(
                """
                SELECT COALESCE(evidence_lineage, 'unknown') AS lineage,
                       COALESCE(status, 'accepted') AS status,
                       COUNT(*)::int AS n
                FROM face_appearance_moments
                GROUP BY 1, 2
                """
            ).fetchall()
            latest = conn.execute(
                """
                SELECT id::text, run_kind, status, candidate_count, accepted_count,
                       uncertain_count, range_count, started_at, finished_at, detail
                FROM recognition_processing_runs
                ORDER BY started_at DESC
                LIMIT 8
                """
            ).fetchall()
            exemplars = conn.execute(
                """
                SELECT COUNT(*)::int AS n FROM face_evidence
                WHERE COALESCE(withdrawn, false) = false
                  AND embedding_json IS NOT NULL
                """
            ).fetchone()
    runs = []
    for r in latest:
        d = dict(r)
        for k in ("started_at", "finished_at"):
            if d.get(k) is not None and hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        runs.append(d)
    return {
        "person_id": person_id,
        "active_exemplars": int(exemplars["n"] if exemplars else 0),
        "observations_by_state": {r["review_state"]: r["n"] for r in obs},
        "ranges_by_lineage_status": [
            {"lineage": r["lineage"], "status": r["status"], "n": r["n"]} for r in ranges
        ],
        "recent_runs": runs,
    }


def list_people_on_video(video_external_id: str) -> list[dict[str, Any]]:
    """People already taught or ranged on this clip (owner Learn first)."""
    vid = (video_external_id or "").strip()
    if not vid:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    with connection() as conn:
        taught = conn.execute(
            """
            SELECT p.id::text AS person_id,
                   p.display_name,
                   MAX(e.created_at) AS last_at
            FROM face_evidence e
            JOIN people p ON p.id = e.person_id
            WHERE COALESCE(e.withdrawn, false) = false
              AND e.method IN ('owner_learn', 'owner_confirm', 'owner_correct')
              AND (
                e.source_asset_id = %s
                OR COALESCE(e.exemplar_meta_json->>'video_external_id', '') = %s
              )
            GROUP BY p.id, p.display_name
            """,
            (vid, vid),
        ).fetchall()
        seen = conn.execute(
            """
            SELECT p.id::text AS person_id,
                   p.display_name,
                   MAX(m.updated_at) AS last_at,
                   BOOL_OR(COALESCE(m.evidence_lineage, '') = 'mb_native_i8b') AS native
            FROM face_appearance_moments m
            JOIN people p ON p.id = m.person_id
            WHERE m.video_external_id = %s
              AND COALESCE(m.status, 'accepted') <> 'withdrawn'
            GROUP BY p.id, p.display_name
            """,
            (vid,),
        ).fetchall()
    for r in taught:
        pid = str(r["person_id"])
        by_id[pid] = {
            "person_id": pid,
            "display_name": r.get("display_name") or "Person",
            "taught": True,
            "on_video": True,
            "native": False,
        }
    for r in seen:
        pid = str(r["person_id"])
        cur = by_id.get(pid) or {
            "person_id": pid,
            "display_name": r.get("display_name") or "Person",
            "taught": False,
            "on_video": True,
            "native": False,
        }
        cur["on_video"] = True
        cur["native"] = cur.get("native") or bool(r.get("native"))
        by_id[pid] = cur
    people = list(by_id.values())
    people.sort(key=lambda p: (0 if p.get("taught") else 1, str(p.get("display_name") or "").lower()))
    return people
