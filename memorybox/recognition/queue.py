"""P2-I1 durable recognition queue — full eligible-archive evaluation."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.recognition.constants import REQUEUE_REASONS

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_EXCLUDED = "excluded"


def enqueue_full_eligible_archive(
    *,
    person_id: str | UUID,
    videos: list[dict[str, Any]],
    enqueue_reason: str = "newly_known_person",
    priority: int = 100,
    run_kind: str = "provider_seeded",
) -> dict[str, Any]:
    """Enqueue every listed video (or record exclusion). Never silently omit.

    Each video dict: {
      video_provider_key, video_external_id,
      eligible?: bool (default True),
      reason?: str when not eligible / pre-excluded
      priority?: int (overrides default)
    }

    I8B: exemplar_change / owner_learn / correction / new_video requeue
    completed/failed items. Excluded (e.g. bad codec) stays excluded.
    I1 newly_known_person still does not silently re-run completed work.
    """
    pid = str(person_id)
    created = 0
    excluded = 0
    requeued = 0
    allow_requeue = enqueue_reason in REQUEUE_REASONS
    from memorybox.recognition.allowlist import face_scan_enabled

    if not face_scan_enabled(pid):
        return {
            "person_id": pid,
            "enqueue_reason": enqueue_reason,
            "run_kind": run_kind,
            "enqueued_or_updated": 0,
            "excluded": 0,
            "requeued_hint": 0,
            "total_input": len(videos),
            "skipped": "face_scan_off",
        }
    with connection() as conn:
        for v in videos:
            vpk = str(v.get("video_provider_key") or "").strip()
            veid = str(v.get("video_external_id") or "").strip()
            if not vpk or not veid:
                continue
            eligible = bool(v.get("eligible", True))
            reason = (v.get("reason") or None)
            status = STATUS_QUEUED if eligible else STATUS_EXCLUDED
            if not eligible and not reason:
                reason = "excluded_unspecified"
            item_priority = int(v.get("priority") if v.get("priority") is not None else priority)
            row = conn.execute(
                """
                INSERT INTO recognition_queue_items (
                    person_id, video_provider_key, video_external_id,
                    status, reason, priority, enqueue_reason, run_kind
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (person_id, video_provider_key, video_external_id, enqueue_reason)
                DO UPDATE SET
                    updated_at = now(),
                    priority = LEAST(recognition_queue_items.priority, EXCLUDED.priority),
                    run_kind = EXCLUDED.run_kind,
                    status = CASE
                        WHEN recognition_queue_items.status = 'running'
                        THEN recognition_queue_items.status
                        WHEN recognition_queue_items.status = 'excluded'
                        THEN recognition_queue_items.status
                        WHEN EXCLUDED.status = 'queued'
                             AND recognition_queue_items.status IN ('completed', 'failed')
                             AND EXCLUDED.enqueue_reason IN ('exemplar_change', 'correction', 'owner_learn', 'new_video')
                        THEN 'queued'
                        WHEN recognition_queue_items.status IN ('completed', 'excluded', 'failed')
                             AND EXCLUDED.status = 'queued'
                        THEN recognition_queue_items.status
                        ELSE EXCLUDED.status
                    END,
                    reason = COALESCE(EXCLUDED.reason, recognition_queue_items.reason),
                    finished_at = CASE
                        WHEN EXCLUDED.status = 'queued'
                             AND recognition_queue_items.status IN ('completed', 'failed')
                             AND EXCLUDED.enqueue_reason IN ('exemplar_change', 'correction', 'owner_learn', 'new_video')
                        THEN NULL
                        ELSE recognition_queue_items.finished_at
                    END
                RETURNING id, status
                """,
                (
                    pid,
                    vpk,
                    veid,
                    status,
                    reason,
                    item_priority,
                    enqueue_reason,
                    run_kind,
                ),
            ).fetchone()
            if row and row["status"] == STATUS_EXCLUDED:
                excluded += 1
            elif row and row["status"] == STATUS_QUEUED:
                created += 1
                if allow_requeue:
                    requeued += 1
            elif row:
                created += 1
    return {
        "person_id": pid,
        "enqueue_reason": enqueue_reason,
        "run_kind": run_kind,
        "enqueued_or_updated": created,
        "excluded": excluded,
        "requeued_hint": requeued,
        "total_input": len(videos),
    }


def retry_failed_items(*, person_id: str | UUID | None = None) -> int:
    with connection() as conn:
        if person_id:
            row = conn.execute(
                """
                UPDATE recognition_queue_items
                SET status = 'queued', updated_at = now(), finished_at = NULL
                WHERE status = 'failed' AND person_id = %s::uuid
                """,
                (str(person_id),),
            )
        else:
            row = conn.execute(
                """
                UPDATE recognition_queue_items
                SET status = 'queued', updated_at = now(), finished_at = NULL
                WHERE status = 'failed'
                """
            )
    return int(getattr(row, "rowcount", 0) or 0)


def queue_summary(person_id: str | UUID | None = None) -> dict[str, Any]:
    with connection() as conn:
        if person_id:
            rows = conn.execute(
                """
                SELECT status, COUNT(*)::int AS n
                FROM recognition_queue_items
                WHERE person_id = %s::uuid
                GROUP BY status
                """,
                (str(person_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT status, COUNT(*)::int AS n
                FROM recognition_queue_items
                GROUP BY status
                """
            ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}
    return {
        "by_status": by_status,
        "total": sum(by_status.values()),
        "person_id": str(person_id) if person_id else None,
    }


def list_queue_items(
    *,
    person_id: str | UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if person_id:
        clauses.append("person_id = %s::uuid")
        args.append(str(person_id))
    if status:
        clauses.append("status = %s")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(int(limit))
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   status, reason, priority, enqueue_reason, attempt_count,
                   result_json, created_at, updated_at, started_at, finished_at,
                   COALESCE(run_kind, 'provider_seeded') AS run_kind
            FROM recognition_queue_items
            {where}
            ORDER BY priority ASC, created_at ASC
            LIMIT %s
            """,
            tuple(args),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("created_at", "updated_at", "started_at", "finished_at"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
        if d.get("result_json") is not None and not isinstance(d["result_json"], dict):
            d["result_json"] = json.loads(d["result_json"]) if isinstance(d["result_json"], str) else d["result_json"]
        out.append(d)
    return out


def claim_next_item(*, person_id: str | UUID | None = None) -> dict[str, Any] | None:
    with connection() as conn:
        if person_id:
            row = conn.execute(
                """
                UPDATE recognition_queue_items q
                SET status = 'running', started_at = now(),
                    attempt_count = attempt_count + 1, updated_at = now()
                WHERE q.id = (
                    SELECT id FROM recognition_queue_items
                    WHERE status = 'queued' AND person_id = %s::uuid
                    ORDER BY priority ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id::text, person_id::text, video_provider_key, video_external_id,
                          enqueue_reason, attempt_count
                """,
                (str(person_id),),
            ).fetchone()
        else:
            row = conn.execute(
                """
                UPDATE recognition_queue_items q
                SET status = 'running', started_at = now(),
                    attempt_count = attempt_count + 1, updated_at = now()
                WHERE q.id = (
                    SELECT id FROM recognition_queue_items
                    WHERE status = 'queued'
                    ORDER BY priority ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id::text, person_id::text, video_provider_key, video_external_id,
                          enqueue_reason, attempt_count
                """
            ).fetchone()
    return dict(row) if row else None


def complete_item(
    item_id: str,
    *,
    status: str,
    reason: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    if status not in {STATUS_COMPLETED, STATUS_FAILED, STATUS_EXCLUDED}:
        raise ValueError(f"invalid terminal status {status}")
    with connection() as conn:
        conn.execute(
            """
            UPDATE recognition_queue_items
            SET status = %s, reason = %s, result_json = %s::jsonb,
                finished_at = now(), updated_at = now()
            WHERE id = %s::uuid
            """,
            (status, reason, json.dumps(result or {}), item_id),
        )
