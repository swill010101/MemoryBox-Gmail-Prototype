"""P2-I1 durable recognition queue — full eligible-archive evaluation."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection

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
) -> dict[str, Any]:
    """Enqueue every listed video (or record exclusion). Never silently omit.

    Each video dict: {
      video_provider_key, video_external_id,
      eligible?: bool (default True),
      reason?: str when not eligible / pre-excluded
    }
    """
    pid = str(person_id)
    created = 0
    excluded = 0
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
            row = conn.execute(
                """
                INSERT INTO recognition_queue_items (
                    person_id, video_provider_key, video_external_id,
                    status, reason, priority, enqueue_reason
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (person_id, video_provider_key, video_external_id, enqueue_reason)
                DO UPDATE SET
                    updated_at = now(),
                    priority = LEAST(recognition_queue_items.priority, EXCLUDED.priority),
                    status = CASE
                        WHEN recognition_queue_items.status IN ('completed', 'excluded', 'failed')
                             AND EXCLUDED.status = 'queued'
                        THEN recognition_queue_items.status
                        WHEN recognition_queue_items.status = 'running'
                        THEN recognition_queue_items.status
                        ELSE EXCLUDED.status
                    END,
                    reason = COALESCE(EXCLUDED.reason, recognition_queue_items.reason)
                RETURNING id, status
                """,
                (pid, vpk, veid, status, reason, int(priority), enqueue_reason),
            ).fetchone()
            if row and row["status"] == STATUS_EXCLUDED:
                excluded += 1
            elif row:
                created += 1
    return {
        "person_id": pid,
        "enqueue_reason": enqueue_reason,
        "enqueued_or_updated": created,
        "excluded": excluded,
        "total_input": len(videos),
    }


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
                   result_json, created_at, updated_at, started_at, finished_at
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
