"""Durable per-video speech queue — never people × every file for transcribe."""
from __future__ import annotations

import json
from typing import Any

from memorybox.db import connection

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_EXCLUDED = "excluded"


def enqueue_videos(
    *,
    videos: list[dict[str, Any]],
    enqueue_reason: str = "transcribe",
    person_id: str | UUID | None = None,
    priority: int = 100,
) -> dict[str, Any]:
    created = 0
    with connection() as conn:
        for v in videos:
            vpk = str(v.get("video_provider_key") or "").strip()
            veid = str(v.get("video_external_id") or "").strip()
            if not vpk or not veid:
                continue
            pri = int(v.get("priority") or priority)
            if person_id:
                conn.execute(
                    """
                    INSERT INTO speech_queue_items (
                        video_provider_key, video_external_id, person_id,
                        status, priority, enqueue_reason
                    ) VALUES (%s, %s, %s::uuid, 'queued', %s, %s)
                    ON CONFLICT (video_provider_key, video_external_id, enqueue_reason, person_id)
                    WHERE person_id IS NOT NULL
                    DO UPDATE SET
                        status = CASE
                            WHEN speech_queue_items.status = 'running'
                            THEN speech_queue_items.status
                            WHEN speech_queue_items.status IN ('completed', 'failed')
                            THEN 'queued'
                            ELSE 'queued'
                        END,
                        priority = LEAST(speech_queue_items.priority, EXCLUDED.priority),
                        updated_at = now(),
                        finished_at = NULL
                    """,
                    (vpk, veid, str(person_id), pri, enqueue_reason),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO speech_queue_items (
                        video_provider_key, video_external_id, person_id,
                        status, priority, enqueue_reason
                    ) VALUES (%s, %s, NULL, 'queued', %s, %s)
                    ON CONFLICT (video_provider_key, video_external_id, enqueue_reason)
                    WHERE person_id IS NULL
                    DO UPDATE SET
                        status = CASE
                            WHEN speech_queue_items.status = 'running'
                            THEN speech_queue_items.status
                            WHEN speech_queue_items.status IN ('completed', 'excluded')
                            THEN speech_queue_items.status
                            ELSE 'queued'
                        END,
                        priority = LEAST(speech_queue_items.priority, EXCLUDED.priority),
                        updated_at = now()
                    """,
                    (vpk, veid, pri, enqueue_reason),
                )
            created += 1
    return {"ok": True, "enqueued_or_updated": created, "enqueue_reason": enqueue_reason}


def claim_next_item() -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE speech_queue_items q
            SET status = 'running', started_at = now(),
                attempt_count = attempt_count + 1, updated_at = now()
            WHERE q.id = (
                SELECT id FROM speech_queue_items
                WHERE status = 'queued'
                ORDER BY priority ASC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id::text, video_provider_key, video_external_id,
                      person_id::text, enqueue_reason, attempt_count
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
    with connection() as conn:
        conn.execute(
            """
            UPDATE speech_queue_items
            SET status = %s, reason = %s, result_json = %s::jsonb,
                finished_at = now(), updated_at = now()
            WHERE id = %s::uuid
            """,
            (status, reason, json.dumps(result or {}), item_id),
        )


def queue_summary() -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*)::int AS n
            FROM speech_queue_items
            GROUP BY status
            """
        ).fetchall()
    by = {r["status"]: r["n"] for r in rows}
    return {"by_status": by, "total": sum(by.values())}


def list_queue_items(
    *,
    status: str | None = None,
    enqueue_reason: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["TRUE"]
    args: list[Any] = []
    if status:
        clauses.append("status = %s")
        args.append(status)
    if enqueue_reason:
        clauses.append("enqueue_reason = %s")
        args.append(enqueue_reason)
    args.append(int(limit))
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id::text, video_provider_key, video_external_id, person_id::text,
                   status, enqueue_reason, priority, reason, attempt_count
            FROM speech_queue_items
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(args),
        ).fetchall()
    return [dict(r) for r in rows]


def already_done_video_ids(*, enqueue_reason: str = "transcribe") -> set[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT video_external_id
            FROM speech_queue_items
            WHERE enqueue_reason = %s
              AND status IN ('queued', 'running', 'completed', 'excluded', 'failed')
            """,
            (enqueue_reason,),
        ).fetchall()
    return {str(r["video_external_id"]) for r in rows}
