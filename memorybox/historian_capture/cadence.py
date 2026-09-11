"""HC-2 autonomous Historian Capture tick: lock, heartbeat, CLI, public status."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from memorybox.db import connect

# Session advisory lock class/object. Distinct from processing hashtextextended keys.
HC_TICK_LOCK_CLASS = 0x4D4248  # 'MBH'
HC_TICK_LOCK_OBJECT = 0x5449434B  # 'TICK' truncated to 32-bit via mask below
HC_TICK_LOCK_OBJECT &= 0x7FFFFFFF

DELAYED_AFTER = timedelta(minutes=15)
DEFAULT_MAX_SENDS_PER_TICK = 5
SANITIZED_FAILURES = frozenset(
    {
        "already_running",
        "imap_unavailable",
        "smtp_unavailable",
        "smtp_send_failed",
        "authentication_failed",
        "configuration_invalid",
        "missing_credentials",
        "missing_user_email",
        "unavailable",
        "poll_failed",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(v: datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc).isoformat()


def _parse_iso(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def state_dir() -> Path:
    home = (
        os.environ.get("MEMORYBOX_HC_STATE_DIR")
        or os.environ.get("MEMORYBOX_HOME")
        or os.environ.get("MEMORYBOX_DATA_DIR")
        or ""
    ).strip()
    root = Path(home) if home else Path(__file__).resolve().parents[2]
    return root / ".memorybox_hc_state"


def heartbeat_path() -> Path:
    override = (os.environ.get("MEMORYBOX_HC_TICK_HEARTBEAT") or "").strip()
    if override:
        return Path(override)
    return state_dir() / "tick_heartbeat.json"


def tick_log_path() -> Path:
    return state_dir() / "tick.log"


def tick_history_path() -> Path:
    override = (os.environ.get("MEMORYBOX_HC_TICK_HISTORY") or "").strip()
    if override:
        return Path(override)
    return state_dir() / "tick_history.json"


def task_status_path() -> Path:
    return state_dir() / "tick_task_status.json"


HISTORY_KEEP = 200
ADMIN_HISTORY_LIMIT = 20


def max_sends_per_tick() -> int:
    raw = (os.environ.get("MEMORYBOX_HC_MAX_SENDS_PER_TICK") or "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return DEFAULT_MAX_SENDS_PER_TICK


def sanitize_failure_category(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower()
    if key in SANITIZED_FAILURES:
        return key
    if "imap" in key or "poll" in key:
        return "imap_unavailable"
    if "smtp" in key or "send" in key:
        return "smtp_unavailable"
    if "auth" in key:
        return "authentication_failed"
    return "unavailable"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)


def load_heartbeat() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    path = heartbeat_path()
    if path.is_file():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}
    if (os.environ.get("MEMORYBOX_HC_HEARTBEAT_SKIP_DB") or "").strip() in {"1", "true", "yes"}:
        return payload
    try:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM historian_capture_tick_heartbeat WHERE id = 1"
            ).fetchone()
            conn.commit()
        finally:
            conn.close()
        if row:
            db_payload = dict(row.get("payload_json") or {}) if isinstance(row, dict) else {}
            merged = {
                "started_at": _iso(row.get("started_at")) if row.get("started_at") else db_payload.get("started_at"),
                "completed_at": _iso(row.get("completed_at"))
                if row.get("completed_at")
                else db_payload.get("completed_at"),
                "result": row.get("result") or db_payload.get("result"),
                "duration_ms": row.get("duration_ms"),
                "replies_found": row.get("replies_found"),
                "replies_imported": row.get("replies_imported"),
                "outbound_attempted": row.get("outbound_attempted"),
                "outbound_sent": row.get("outbound_sent"),
                "deferred": row.get("deferred"),
                "failure_category": row.get("failure_category"),
                "already_running": (row.get("result") == "already_running"),
                "last_successful_at": db_payload.get("last_successful_at"),
            }
            file_updated = _parse_iso(payload.get("updated_at"))
            db_updated = row.get("updated_at")
            if isinstance(db_updated, datetime):
                if db_updated.tzinfo is None:
                    db_updated = db_updated.replace(tzinfo=timezone.utc)
                if file_updated is None or db_updated >= file_updated:
                    payload = {**payload, **{k: v for k, v in merged.items() if v is not None}}
            elif not payload:
                payload = merged
    except Exception:
        pass
    return payload


def persist_heartbeat(payload: dict[str, Any]) -> None:
    now = _utc_now()
    record = {
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
        "result": payload.get("result") or "ok",
        "duration_ms": payload.get("duration_ms"),
        "replies_found": int(payload.get("replies_found") or 0),
        "replies_imported": int(payload.get("replies_imported") or 0),
        "outbound_attempted": int(payload.get("outbound_attempted") or 0),
        "outbound_sent": int(payload.get("outbound_sent") or 0),
        "deferred": int(payload.get("deferred") or 0),
        "failure_category": sanitize_failure_category(payload.get("failure_category")),
        "already_running": bool(payload.get("already_running") or payload.get("result") == "already_running"),
        "last_successful_at": payload.get("last_successful_at"),
        "updated_at": _iso(now),
    }
    _atomic_write_json(heartbeat_path(), record)
    append_run_history(record)
    if (os.environ.get("MEMORYBOX_HC_HEARTBEAT_SKIP_DB") or "").strip() in {"1", "true", "yes"}:
        return
    try:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO historian_capture_tick_heartbeat (
                    id, started_at, completed_at, result, duration_ms,
                    replies_found, replies_imported, outbound_attempted, outbound_sent,
                    deferred, failure_category, payload_json, updated_at
                ) VALUES (
                    1, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s::jsonb, now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    result = EXCLUDED.result,
                    duration_ms = EXCLUDED.duration_ms,
                    replies_found = EXCLUDED.replies_found,
                    replies_imported = EXCLUDED.replies_imported,
                    outbound_attempted = EXCLUDED.outbound_attempted,
                    outbound_sent = EXCLUDED.outbound_sent,
                    deferred = EXCLUDED.deferred,
                    failure_category = EXCLUDED.failure_category,
                    payload_json = EXCLUDED.payload_json,
                    updated_at = now()
                """,
                (
                    _parse_iso(record["started_at"]),
                    _parse_iso(record["completed_at"]),
                    record["result"],
                    record["duration_ms"],
                    record["replies_found"],
                    record["replies_imported"],
                    record["outbound_attempted"],
                    record["outbound_sent"],
                    record["deferred"],
                    record["failure_category"],
                    json.dumps(record),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def _history_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
        "duration_ms": payload.get("duration_ms"),
        "result": payload.get("result"),
        "replies_found": int(payload.get("replies_found") or 0),
        "replies_imported": int(payload.get("replies_imported") or 0),
        "outbound_attempted": int(payload.get("outbound_attempted") or 0),
        "outbound_sent": int(payload.get("outbound_sent") or 0),
        "deferred": int(payload.get("deferred") or 0),
        "failure_category": sanitize_failure_category(payload.get("failure_category")),
        "already_running": bool(
            payload.get("already_running") or payload.get("result") == "already_running"
        ),
    }


def load_run_history(*, limit: int | None = None) -> list[dict[str, Any]]:
    path = tick_history_path()
    runs: list[dict[str, Any]] = []
    if path.is_file():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            raw = parsed.get("runs") if isinstance(parsed, dict) else parsed
            if isinstance(raw, list):
                runs = [_history_entry(r) for r in raw if isinstance(r, dict)]
        except Exception:
            runs = []
    runs.sort(key=lambda r: str(r.get("completed_at") or r.get("started_at") or ""), reverse=True)
    if limit is not None:
        return runs[: max(0, int(limit))]
    return runs[:HISTORY_KEEP]


def append_run_history(payload: dict[str, Any]) -> None:
    entry = _history_entry(payload)
    runs = load_run_history(limit=HISTORY_KEEP)
    runs = [entry, *runs][:HISTORY_KEEP]
    _atomic_write_json(tick_history_path(), {"runs": runs})


def append_tick_log(payload: dict[str, Any]) -> None:
    path = tick_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=True, default=str)
    if len(line) > 4000:
        line = line[:4000]
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = [ln for ln in existing.splitlines() if ln.strip()]
        lines.append(line)
        path.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def acquire_tick_lock(conn: Any) -> bool:
    row = conn.execute(
        "SELECT pg_try_advisory_lock(%s, %s) AS ok",
        (HC_TICK_LOCK_CLASS, HC_TICK_LOCK_OBJECT),
    ).fetchone()
    return bool(row and row["ok"])


def release_tick_lock(conn: Any) -> None:
    conn.execute(
        "SELECT pg_advisory_unlock(%s, %s)",
        (HC_TICK_LOCK_CLASS, HC_TICK_LOCK_OBJECT),
    )


@contextmanager
def hc_tick_lock() -> Iterator[bool]:
    conn = connect()
    conn.autocommit = True
    held = False
    try:
        held = acquire_tick_lock(conn)
        yield held
    finally:
        if held:
            try:
                release_tick_lock(conn)
            except Exception:
                pass
        conn.close()


def cadence_public_status(*, now: datetime | None = None) -> dict[str, Any]:
    """Sanitized cadence status for the existing HC email-status payload / UI."""
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    hb = load_heartbeat()
    last_success = _parse_iso(hb.get("last_successful_at"))
    if last_success is None and hb.get("result") in {"ok", "smtp_partial"}:
        last_success = _parse_iso(hb.get("completed_at"))

    configured = bool(hb) and hb.get("result") not in (None, "never", "")
    delayed = False
    display_state = "not_configured"
    minutes_ago = None
    if configured:
        ref = last_success or _parse_iso(hb.get("completed_at")) or _parse_iso(hb.get("started_at"))
        if ref is not None:
            minutes_ago = max(0, int((now - ref).total_seconds() // 60))
            delayed = (now - ref) > DELAYED_AFTER
        display_state = "delayed" if delayed else "active"
        if hb.get("result") == "already_running" and last_success is None and not delayed:
            display_state = "active"
    summary = "Automatic checks not configured"
    if display_state == "active":
        if last_success:
            local = last_success.astimezone()
            summary = f"Automatic checks active — last checked {local.strftime('%-I:%M %p').lstrip() if os.name != 'nt' else local.strftime('%I:%M %p').lstrip('0')}"
        else:
            summary = "Automatic checks active"
    elif display_state == "delayed":
        if minutes_ago is None:
            summary = "Automatic checks delayed"
        else:
            summary = f"Automatic checks delayed — last successful check {minutes_ago} minutes ago"
    return {
        "configured": configured,
        "delayed": delayed,
        "display_state": display_state,
        "summary": summary,
        "last_tick_started_at": hb.get("started_at"),
        "last_successful_at": _iso(last_success),
        "last_completed_at": hb.get("completed_at"),
        "last_result": hb.get("result"),
        "duration_ms": hb.get("duration_ms"),
        "replies_found": hb.get("replies_found"),
        "replies_imported": hb.get("replies_imported"),
        "outbound_attempted": hb.get("outbound_attempted"),
        "outbound_sent": hb.get("outbound_sent"),
        "deferred": hb.get("deferred"),
        "failure_category": sanitize_failure_category(hb.get("failure_category")),
        "already_running": bool(hb.get("already_running")),
        "interval_seconds": 300,
        "history_href": "/admin/jobs/ui?mb_return=/historian-capture/ui#scheduled-services",
    }


def _provider_blocks_outbound(status: dict[str, Any]) -> str | None:
    if status.get("ok"):
        return None
    return sanitize_failure_category(str(status.get("reason") or "unavailable"))


def run_historian_capture_tick(
    *,
    now: datetime | None = None,
    adapter: Any | None = None,
    dry_run: bool = False,
    acquire_lock: bool = True,
) -> dict[str, Any]:
    """Singleton HC tick: lock → poll/ingest → due outbound (capped) → heartbeat."""
    from memorybox.historian_capture import _tick_scheduler_unlocked
    from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

    started = _utc_now()
    now = now or started
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    adapter = adapter or get_email_adapter()

    def _finish(body: dict[str, Any], *, result: str, failure: str | None = None) -> dict[str, Any]:
        ended = _utc_now()
        duration_ms = int((ended - started).total_seconds() * 1000)
        ingest = body.get("ingest") or {}
        outbound_sent = len(body.get("sent") or []) + len(body.get("reminders") or [])
        outbound_attempted = int(body.get("outbound_attempted") or outbound_sent + len(body.get("failed") or []))
        record = {
            "started_at": _iso(started),
            "completed_at": _iso(ended),
            "result": result,
            "duration_ms": duration_ms,
            "replies_found": int(ingest.get("examined") or ingest.get("replies_found") or 0),
            "replies_imported": int(
                ingest.get("created")
                if isinstance(ingest.get("created"), int)
                else len(ingest.get("created") or [])
            ),
            "outbound_attempted": outbound_attempted,
            "outbound_sent": outbound_sent,
            "deferred": len(body.get("deferred") or []),
            "failure_category": failure,
            "already_running": result == "already_running",
        }
        if result in {"ok", "smtp_partial"}:
            record["last_successful_at"] = _iso(ended)
        else:
            prev = load_heartbeat()
            record["last_successful_at"] = prev.get("last_successful_at")
            if not record["last_successful_at"] and prev.get("result") in {"ok", "smtp_partial"}:
                record["last_successful_at"] = prev.get("completed_at")
        persist_heartbeat(record)
        public = {
            **body,
            "ok": result in {"ok", "already_running", "smtp_partial"},
            "result": result,
            "dry_run": dry_run,
            "duration_ms": duration_ms,
            "failure_category": failure,
            "started_at": _iso(started),
            "completed_at": _iso(ended),
        }
        append_tick_log(
            {
                "result": result,
                "duration_ms": duration_ms,
                "replies_imported": record["replies_imported"],
                "outbound_sent": outbound_sent,
                "deferred": record["deferred"],
                "failure_category": failure,
                "dry_run": dry_run,
            }
        )
        return public

    if acquire_lock:
        with hc_tick_lock() as held:
            if not held:
                return _finish(
                    {
                        "sent": [],
                        "failed": [],
                        "reminders": [],
                        "no_responses": [],
                        "deferred": [],
                        "ingest": {},
                        "email_provider": email_adapter_status(),
                    },
                    result="already_running",
                    failure="already_running",
                )
            return _run_tick_body(
                now=now,
                adapter=adapter,
                dry_run=dry_run,
                finish=_finish,
                provider_status=email_adapter_status(),
                unlocked=_tick_scheduler_unlocked,
            )
    return _run_tick_body(
        now=now,
        adapter=adapter,
        dry_run=dry_run,
        finish=_finish,
        provider_status=email_adapter_status(),
        unlocked=_tick_scheduler_unlocked,
    )


def _run_tick_body(
    *,
    now: datetime,
    adapter: Any,
    dry_run: bool,
    finish: Any,
    provider_status: dict[str, Any],
    unlocked: Any,
) -> dict[str, Any]:
    blocked = _provider_blocks_outbound(provider_status)
    if getattr(adapter, "provider_key", None) == "fake_historian_email":
        blocked = None
    body = unlocked(
        now=now,
        adapter=adapter,
        dry_run=dry_run,
        max_sends=max_sends_per_tick(),
        skip_followups=bool(blocked),
        skip_all_outbound=bool(blocked),
    )
    ingest = body.get("ingest") or {}
    poll_failed = ingest.get("ok") is False
    failure = None
    result = "ok"
    if blocked:
        failure = blocked
        result = blocked if blocked in SANITIZED_FAILURES else "unavailable"
        body["deferred"] = list(body.get("deferred") or []) 
    if poll_failed:
        failure = sanitize_failure_category(str(ingest.get("reason") or "imap_unavailable"))
        result = "imap_unavailable"
    if body.get("failed"):
        failure = failure or "smtp_send_failed"
        result = "smtp_partial" if (body.get("sent") or body.get("reminders")) else "smtp_send_failed"
        if result == "smtp_send_failed":
            # SMTP miss is retryable; not an operational crash.
            pass
    if dry_run:
        result = "ok"
        failure = failure if poll_failed or blocked else None
    return finish(body, result=result, failure=failure)


def cli_hc_tick(*, dry_run: bool = False) -> int:
    payload = run_historian_capture_tick(dry_run=dry_run)
    print(json.dumps(payload, indent=2, default=str))
    result = payload.get("result")
    if result in {"ok", "already_running", "smtp_partial"}:
        return 0
    if result in {"imap_unavailable", "smtp_send_failed", "smtp_unavailable"}:
        return 2
    if result in {"configuration_invalid", "missing_credentials", "missing_user_email", "unavailable"}:
        return 3
    return 1
