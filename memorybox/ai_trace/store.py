"""Fail-open AI trace persistence. Store errors never fail the user request."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from memorybox.ai_trace.redact import redact
from memorybox.db import connection

log = logging.getLogger("memorybox.ai_trace")

DEFAULT_MAX = 500
DEFAULT_DAYS = 7
POLL_MS = 750

_SETTING_MAX = "ai_trace_max_traces"
_SETTING_DAYS = "ai_trace_retention_days"
_schema_ready = False
_missing_logged = False

_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS ai_traces (
        trace_id            UUID PRIMARY KEY,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        request_kind        TEXT NOT NULL,
        originating_ask     TEXT,
        session_id          TEXT,
        purpose             TEXT,
        status              TEXT NOT NULL DEFAULT 'running',
        error_class         TEXT,
        model_call_count    INT NOT NULL DEFAULT 0,
        duration_ms         INT,
        initiator           JSONB NOT NULL DEFAULT '{}'::jsonb,
        assembled_context   JSONB,
        final_disposition   JSONB,
        error               JSONB
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_traces_created_at ON ai_traces (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_traces_updated_at ON ai_traces (updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ai_traces_error_class ON ai_traces (error_class)",
    """
    CREATE TABLE IF NOT EXISTS ai_spans (
        span_id             UUID PRIMARY KEY,
        trace_id            UUID NOT NULL REFERENCES ai_traces (trace_id) ON DELETE CASCADE,
        parent_span_id      UUID,
        seq                 INT NOT NULL,
        stage               TEXT NOT NULL,
        component           TEXT NOT NULL,
        operation           TEXT NOT NULL,
        started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        ended_at            TIMESTAMPTZ,
        duration_ms         INT,
        status              TEXT NOT NULL DEFAULT 'running',
        error_class         TEXT,
        assembled_context   JSONB,
        provider_payload    JSONB,
        raw_response        JSONB,
        parsed              JSONB,
        validation          JSONB,
        disposition         JSONB,
        model               JSONB,
        error               JSONB,
        meta                JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_spans_trace_seq ON ai_spans (trace_id, seq)",
    """
    INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key)
    VALUES
        ('ai_trace_max_traces', '500', 'system'),
        ('ai_trace_retention_days', '7', 'system')
    ON CONFLICT (setting_key) DO NOTHING
    """,
)


def tables_exist() -> bool:
    try:
        with connection() as conn:
            row = conn.execute(
                "SELECT to_regclass('public.ai_traces') AS t, "
                "to_regclass('public.ai_spans') AS s"
            ).fetchone()
        return bool((row or {}).get("t") and (row or {}).get("s"))
    except Exception:
        return False


def ensure_schema() -> bool:
    """Create AI trace tables even when schema_migrations already has 009."""
    global _schema_ready
    if _schema_ready or tables_exist():
        _schema_ready = True
        return True
    try:
        with connection() as conn:
            for stmt in _SCHEMA_SQL:
                conn.execute(stmt)
        _schema_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        _warn("ensure_schema", exc)
        return False


def _warn(op: str, exc: BaseException) -> None:
    global _missing_logged
    msg = str(exc)
    if "forced store down" in msg:
        return
    if "does not exist" in msg:
        if _missing_logged:
            return
        _missing_logged = True
        log.warning("ai_trace %s failed (missing table; ensure_schema will retry): %s", op, exc)
        return
    log.warning("ai_trace %s failed: %s", op, exc)


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(redact(value), default=str)


def _row(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    out = dict(row)
    for key, val in list(out.items()):
        if isinstance(val, datetime):
            out[key] = val.isoformat()
        elif isinstance(val, UUID):
            out[key] = str(val)
    return out


def read_settings() -> dict[str, int]:
    max_traces = _env_int("MEMORYBOX_AI_TRACE_MAX", 0)
    days = _env_int("MEMORYBOX_AI_TRACE_DAYS", 0)
    try:
        with connection() as conn:
            rows = conn.execute(
                "SELECT setting_key, value_text FROM memorybox_runtime_settings "
                "WHERE setting_key IN (%s, %s)",
                (_SETTING_MAX, _SETTING_DAYS),
            ).fetchall()
        by_key = {r["setting_key"]: r["value_text"] for r in rows}
        if max_traces <= 0:
            max_traces = int(by_key.get(_SETTING_MAX) or DEFAULT_MAX)
        if days <= 0:
            days = int(by_key.get(_SETTING_DAYS) or DEFAULT_DAYS)
    except Exception as exc:  # noqa: BLE001
        _warn("settings read", exc)
        if max_traces <= 0:
            max_traces = DEFAULT_MAX
        if days <= 0:
            days = DEFAULT_DAYS
    return {
        "max_traces": max(1, int(max_traces)),
        "retention_days": max(1, int(days)),
        "poll_ms": POLL_MS,
    }


def write_settings(*, max_traces: int | None = None, retention_days: int | None = None) -> dict[str, int]:
    try:
        with connection() as conn:
            if max_traces is not None:
                conn.execute(
                    """
                    INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key, updated_at)
                    VALUES (%s, %s, 'owner', now())
                    ON CONFLICT (setting_key) DO UPDATE
                    SET value_text = EXCLUDED.value_text, actor_key = 'owner', updated_at = now()
                    """,
                    (_SETTING_MAX, str(max(1, int(max_traces)))),
                )
            if retention_days is not None:
                conn.execute(
                    """
                    INSERT INTO memorybox_runtime_settings (setting_key, value_text, actor_key, updated_at)
                    VALUES (%s, %s, 'owner', now())
                    ON CONFLICT (setting_key) DO UPDATE
                    SET value_text = EXCLUDED.value_text, actor_key = 'owner', updated_at = now()
                    """,
                    (_SETTING_DAYS, str(max(1, int(retention_days)))),
                )
    except Exception as exc:  # noqa: BLE001
        _warn("settings write", exc)
    cleanup()
    return read_settings()


def insert_trace(
    *,
    trace_id: str,
    request_kind: str,
    originating_ask: str | None,
    session_id: str | None = None,
    purpose: str | None = None,
    initiator: dict[str, Any] | None = None,
    assembled_context: dict[str, Any] | None = None,
) -> bool:
    ensure_schema()
    try:
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_traces (
                    trace_id, request_kind, originating_ask, session_id, purpose,
                    status, initiator, assembled_context
                ) VALUES (%s, %s, %s, %s, %s, 'running', %s::jsonb, %s::jsonb)
                """,
                (
                    trace_id,
                    request_kind,
                    originating_ask,
                    session_id,
                    purpose,
                    _json(initiator or {}),
                    _json(assembled_context),
                ),
            )
        return True
    except Exception as exc:  # noqa: BLE001
        _warn("insert_trace", exc)
        return False


def update_trace(
    trace_id: str,
    *,
    status: str | None = None,
    error_class: str | None = None,
    purpose: str | None = None,
    assembled_context: dict[str, Any] | None = None,
    final_disposition: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    bump_model_calls: int = 0,
) -> bool:
    try:
        sets = ["updated_at = now()"]
        args: list[Any] = []
        if status is not None:
            sets.append("status = %s")
            args.append(status)
        if error_class is not None:
            sets.append("error_class = %s")
            args.append(error_class)
        if purpose is not None:
            sets.append("purpose = %s")
            args.append(purpose)
        if assembled_context is not None:
            sets.append("assembled_context = %s::jsonb")
            args.append(_json(assembled_context))
        if final_disposition is not None:
            sets.append("final_disposition = %s::jsonb")
            args.append(_json(final_disposition))
        if error is not None:
            sets.append("error = %s::jsonb")
            args.append(_json(error))
        if duration_ms is not None:
            sets.append("duration_ms = %s")
            args.append(duration_ms)
        if bump_model_calls:
            sets.append("model_call_count = model_call_count + %s")
            args.append(int(bump_model_calls))
        args.append(trace_id)
        ensure_schema()
        with connection() as conn:
            conn.execute(
                f"UPDATE ai_traces SET {', '.join(sets)} WHERE trace_id = %s",
                args,
            )
        return True
    except Exception as exc:  # noqa: BLE001
        _warn("update_trace", exc)
        return False


def next_seq(trace_id: str) -> int:
    try:
        with connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS n FROM ai_spans WHERE trace_id = %s",
                (trace_id,),
            ).fetchone()
        return int((row or {}).get("n") or 0) + 1
    except Exception as exc:  # noqa: BLE001
        _warn("next_seq", exc)
        return 1


def insert_span(
    *,
    trace_id: str,
    stage: str,
    component: str,
    operation: str,
    parent_span_id: str | None = None,
    status: str = "ok",
    error_class: str | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    duration_ms: int | None = None,
    assembled_context: dict[str, Any] | None = None,
    provider_payload: dict[str, Any] | None = None,
    raw_response: dict[str, Any] | None = None,
    parsed: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    disposition: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    span_id: str | None = None,
) -> str | None:
    sid = span_id or str(uuid4())
    start = started_at or _now()
    end = ended_at or _now()
    if duration_ms is None:
        duration_ms = max(0, int((end - start).total_seconds() * 1000))
    ensure_schema()
    try:
        seq = next_seq(trace_id)
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_spans (
                    span_id, trace_id, parent_span_id, seq, stage, component, operation,
                    started_at, ended_at, duration_ms, status, error_class,
                    assembled_context, provider_payload, raw_response, parsed,
                    validation, disposition, model, error, meta
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb
                )
                """,
                (
                    sid,
                    trace_id,
                    parent_span_id,
                    seq,
                    stage,
                    component,
                    operation,
                    start,
                    end,
                    duration_ms,
                    status,
                    error_class,
                    _json(assembled_context),
                    _json(provider_payload),
                    _json(raw_response),
                    _json(parsed),
                    _json(validation),
                    _json(disposition),
                    _json(model),
                    _json(error),
                    _json(meta or {}),
                ),
            )
        if operation in ("chat", "embed"):
            update_trace(trace_id, bump_model_calls=1)
        return sid
    except Exception as exc:  # noqa: BLE001
        _warn("insert_span", exc)
        return None


def get_trace(trace_id: str) -> dict[str, Any] | None:
    ensure_schema()
    try:
        with connection() as conn:
            head = conn.execute(
                "SELECT * FROM ai_traces WHERE trace_id = %s", (trace_id,)
            ).fetchone()
            if not head:
                return None
            spans = conn.execute(
                "SELECT * FROM ai_spans WHERE trace_id = %s ORDER BY seq ASC",
                (trace_id,),
            ).fetchall()
        return {**_row(head), "spans": [_row(s) for s in spans]}
    except Exception as exc:  # noqa: BLE001
        _warn("get_trace", exc)
        return None


def list_traces(
    *,
    q: str | None = None,
    error_class: str | None = None,
    updated_after: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    where: list[str] = []
    args: list[Any] = []
    if q:
        where.append(
            "("
            "originating_ask ILIKE %s OR purpose ILIKE %s OR CAST(trace_id AS text) ILIKE %s "
            "OR COALESCE(error_class, '') ILIKE %s OR COALESCE(status, '') ILIKE %s"
            ")"
        )
        like = f"%{q}%"
        args.extend([like, like, like, like, like])
    if error_class:
        where.append("error_class = %s")
        args.append(error_class)
    if updated_after:
        where.append("updated_at > %s")
        args.append(updated_after)
    sql = "SELECT * FROM ai_traces"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT %s"
    args.append(max(1, min(int(limit), 500)))
    ensure_schema()
    try:
        with connection() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_row(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        _warn("list_traces", exc)
        return []


def clear_all() -> dict[str, Any]:
    ensure_schema()
    try:
        with connection() as conn:
            spans = conn.execute("SELECT COUNT(*) AS n FROM ai_spans").fetchone()
            traces = conn.execute("SELECT COUNT(*) AS n FROM ai_traces").fetchone()
            conn.execute("DELETE FROM ai_spans")
            conn.execute("DELETE FROM ai_traces")
        return {
            "ok": True,
            "cleared_traces": int((traces or {}).get("n") or 0),
            "cleared_spans": int((spans or {}).get("n") or 0),
        }
    except Exception as exc:  # noqa: BLE001
        _warn("clear_all", exc)
        return {"ok": False, "error": str(exc)}


def cleanup() -> dict[str, Any]:
    ensure_schema()
    settings = read_settings()
    days = settings["retention_days"]
    max_traces = settings["max_traces"]
    deleted = 0
    try:
        with connection() as conn:
            row = conn.execute(
                "DELETE FROM ai_traces WHERE created_at < now() - (%s || ' days')::interval "
                "RETURNING trace_id",
                (str(days),),
            ).fetchall()
            deleted += len(row or [])
            extra = conn.execute(
                """
                DELETE FROM ai_traces WHERE trace_id IN (
                    SELECT trace_id FROM ai_traces
                    ORDER BY created_at DESC
                    OFFSET %s
                )
                RETURNING trace_id
                """,
                (max_traces,),
            ).fetchall()
            deleted += len(extra or [])
        return {"ok": True, "deleted": deleted, **settings}
    except Exception as exc:  # noqa: BLE001
        _warn("cleanup", exc)
        return {"ok": False, "error": str(exc), **settings}
