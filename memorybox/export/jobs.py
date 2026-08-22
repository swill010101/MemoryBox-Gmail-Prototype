"""Thin async export jobs (uses existing jobs table — no job platform)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.export.package import ExportError, build_export_package


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_export_job(
    *,
    destination: str | None = None,
    make_zip: bool = False,
) -> dict[str, Any]:
    """Create a jobs row and run export on a background thread."""
    job_id = uuid4()
    payload = {
        "destination": destination,
        "make_zip": bool(make_zip),
    }
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, job_kind, status, progress_pct, message, payload_json, started_at
            )
            VALUES (%s, 'export', 'running', 0, %s, %s::jsonb, %s)
            """,
            (job_id, "Export starting", json.dumps(payload), _now()),
        )

    def _run() -> None:
        def progress(msg: str, pct: float | None = None) -> None:
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET message = %s,
                        progress_pct = COALESCE(%s, progress_pct),
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (msg, pct, _now(), job_id),
                )

        try:
            result = build_export_package(
                destination_parent=destination,
                make_zip=make_zip,
                progress=progress,
            )
            out = {
                "export_root": str(result.export_root),
                "zip_path": str(result.zip_path) if result.zip_path else None,
                "created_at": result.created_at,
                "counts": result.counts,
            }
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'done',
                        progress_pct = 100,
                        message = %s,
                        payload_json = payload_json || %s::jsonb,
                        finished_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        result.job_message,
                        json.dumps({"result": out}),
                        _now(),
                        _now(),
                        job_id,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'error',
                        error_message = %s,
                        message = %s,
                        finished_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (str(exc), f"Export failed: {exc}", _now(), _now(), job_id),
                )

    threading.Thread(target=_run, name=f"export-{job_id}", daemon=True).start()
    return get_export_job(str(job_id))


def get_export_job(job_id: str) -> dict[str, Any]:
    try:
        jid = UUID(str(job_id))
    except ValueError as exc:
        raise ExportError("invalid job id") from exc
    with connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = %s", (jid,)).fetchone()
    if not row or row.get("job_kind") != "export":
        raise ExportError("export job not found")
    payload = row.get("payload_json") or {}
    if not isinstance(payload, dict):
        payload = {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "progress_pct": row.get("progress_pct"),
        "message": row.get("message"),
        "error_message": row.get("error_message"),
        "destination": payload.get("destination") or (result or {}).get("export_root"),
        "export_root": (result or {}).get("export_root"),
        "zip_path": (result or {}).get("zip_path"),
        "counts": (result or {}).get("counts"),
        "started_at": row.get("started_at").isoformat() if row.get("started_at") else None,
        "finished_at": row.get("finished_at").isoformat()
        if row.get("finished_at")
        else None,
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }
