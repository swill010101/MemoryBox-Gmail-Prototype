"""Durable per-video speech queue — never people × every file for transcribe."""
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


def enqueue_videos(
    *,
    videos: list[dict[str, Any]],
    enqueue_reason: str = "transcribe",
    person_id: str | UUID | None = None,
    priority: int = 100,
    force_requeue: bool = False,
) -> dict[str, Any]:
    from memorybox.processing.scope import admit
    admission = admit("voice" if person_id else "transcribe", videos, [str(person_id)] if person_id else [])
    created = 0
    with connection() as conn:
        for v in videos:
            from memorybox.processing.scope import reserve_queue_item
            reserve_queue_item(conn, admission, "voice" if person_id else "transcribe", v, str(person_id) if person_id else None, enqueue_reason)
            vpk = str(v.get("video_provider_key") or "").strip()
            veid = str(v.get("video_external_id") or "").strip()
            if not vpk or not veid:
                continue
            pri = int(v.get("priority") or priority)
            force = bool(force_requeue or v.get("force_requeue"))
            if person_id:
                conn.execute(
                    """
                    INSERT INTO speech_queue_items (
                        video_provider_key, video_external_id, person_id,
                        status, priority, enqueue_reason, i13_admission_id
                    ) VALUES (%s, %s, %s::uuid, 'queued', %s, %s, %s::uuid)
                    ON CONFLICT (video_provider_key, video_external_id, enqueue_reason, person_id)
                    WHERE person_id IS NOT NULL
                    DO UPDATE SET
                        i13_admission_id = EXCLUDED.i13_admission_id,
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
                    (vpk, veid, str(person_id), pri, enqueue_reason, admission.id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO speech_queue_items (
                        video_provider_key, video_external_id, person_id,
                        status, priority, enqueue_reason, i13_admission_id
                    ) VALUES (%s, %s, NULL, 'queued', %s, %s, %s::uuid)
                    ON CONFLICT (video_provider_key, video_external_id, enqueue_reason)
                    WHERE person_id IS NULL
                    DO UPDATE SET
                        i13_admission_id = EXCLUDED.i13_admission_id,
                        status = CASE
                            WHEN speech_queue_items.status = 'running'
                            THEN speech_queue_items.status
                            WHEN %s THEN 'queued'
                            WHEN speech_queue_items.status IN ('completed', 'excluded')
                            THEN speech_queue_items.status
                            ELSE 'queued'
                        END,
                        reason = CASE WHEN %s THEN NULL ELSE speech_queue_items.reason END,
                        finished_at = CASE WHEN %s THEN NULL ELSE speech_queue_items.finished_at END,
                        priority = LEAST(speech_queue_items.priority, EXCLUDED.priority),
                        updated_at = now()
                    """,
                    (vpk, veid, pri, enqueue_reason, admission.id, force, force, force),
                )
            created += 1
    return {"ok": True, "enqueued_or_updated": created, "enqueue_reason": enqueue_reason}


def claim_next_item() -> dict[str, Any] | None:
    from memorybox.processing.scope import load_admission, require_source
    admission = load_admission()
    # Validate state before even selecting/locking a queue row.
    from memorybox.processing.scope import require_admission
    require_admission("transcribe" if "transcribe" in admission.plan["lanes"] else "voice")
    with connection() as conn:
        current = conn.execute("SELECT state,plan_sha256 FROM i13_processing_admissions WHERE id=%s::uuid FOR SHARE",(admission.id,)).fetchone()
        if not current or current["state"] != "started" or current["plan_sha256"] != admission.plan_sha256:
            from memorybox.processing.scope import ScopeDenied
            raise ScopeDenied("admission_changed")
        row = conn.execute(
            "SELECT id::text,person_id::text,video_provider_key,video_external_id,enqueue_reason,attempt_count FROM speech_queue_items "
            "WHERE status='queued' AND i13_admission_id=%s::uuid "
            "ORDER BY priority,created_at FOR UPDATE SKIP LOCKED LIMIT 1",
            (admission.id,),
        ).fetchone()
        if not row:
            return None
        require_source("voice" if row.get("person_id") else "transcribe", row["video_provider_key"], row["video_external_id"], row.get("person_id"))
        conn.execute("UPDATE speech_queue_items SET status='running',started_at=now(),attempt_count=attempt_count+1,updated_at=now() WHERE id=%s::uuid",(row["id"],))
    return dict(row)


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
