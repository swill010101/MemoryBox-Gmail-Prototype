"""Shared ingest helpers: jobs + Source/Evidence writes (PostgreSQL only)."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection


def strip_pg_nuls(value: str | None) -> str:
    """PostgreSQL text/jsonb cannot store U+0000; strip, do not rewrite originals."""
    if not value:
        return value or ""
    if "\x00" not in value:
        return value
    return value.replace("\x00", "")


def sanitize_pg(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, str):
        return strip_pg_nuls(obj)
    if isinstance(obj, dict):
        return {sanitize_pg(k) if isinstance(k, str) else k: sanitize_pg(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_pg(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_pg(x) for x in obj)
    return obj


def start_job(job_kind: str, *, message: str = "", payload: dict | None = None) -> UUID:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO jobs (job_kind, status, message, payload_json, started_at)
            VALUES (%s, 'running', %s, %s::jsonb, now())
            RETURNING id
            """,
            (job_kind, strip_pg_nuls(message), json.dumps(sanitize_pg(payload or {}))),
        ).fetchone()
        assert row is not None
        return row["id"]


def finish_job(
    job_id: UUID,
    *,
    status: str,
    message: str = "",
    error_message: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = %s, message = %s, error_message = %s,
                finished_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (
                status,
                strip_pg_nuls(message),
                None if error_message is None else strip_pg_nuls(error_message),
                job_id,
            ),
        )


def upsert_source(
    *,
    source_kind: str,
    label: str,
    uri: str,
    metadata: dict[str, Any],
) -> UUID:
    with connection() as conn:
        existing = conn.execute(
            "SELECT id FROM sources WHERE uri = %s AND source_kind = %s LIMIT 1",
            (uri, source_kind),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE sources
                SET label = %s, metadata_json = %s::jsonb, updated_at = now()
                WHERE id = %s
                """,
                (label, json.dumps(metadata), existing["id"]),
            )
            return existing["id"]
        row = conn.execute(
            """
            INSERT INTO sources (
                source_kind, label, uri, authoritative_original_mode, metadata_json
            )
            VALUES (%s, %s, %s, 'referenced', %s::jsonb)
            RETURNING id
            """,
            (source_kind, label, uri, json.dumps(metadata)),
        ).fetchone()
        assert row is not None
        return row["id"]


def evidence_exists_by_hash(
    source_id: UUID, content_hash: str, *, conn: Any | None = None
) -> UUID | None:
    def _run(c: Any) -> UUID | None:
        row = c.execute(
            """
            SELECT id FROM evidence
            WHERE source_id = %s AND payload_json->>'content_hash' = %s
            LIMIT 1
            """,
            (source_id, content_hash),
        ).fetchone()
        return row["id"] if row else None

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def hashes_for_source(source_id: UUID, *, conn: Any | None = None) -> dict[str, UUID]:
    """content_hash → evidence id for one Source (one query)."""

    def _run(c: Any) -> dict[str, UUID]:
        rows = c.execute(
            """
            SELECT id, payload_json->>'content_hash' AS h
            FROM evidence
            WHERE source_id = %s
            """,
            (source_id,),
        ).fetchall()
        out: dict[str, UUID] = {}
        for r in rows:
            h = str(r.get("h") or "")
            if h:
                out[h] = r["id"]
        return out

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def insert_evidence(
    *,
    evidence_kind: str,
    source_id: UUID,
    summary: str,
    payload: dict[str, Any],
    conn: Any | None = None,
) -> UUID:
    def _run(c: Any) -> UUID:
        row = c.execute(
            """
            INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                evidence_kind,
                source_id,
                strip_pg_nuls(summary),
                json.dumps(sanitize_pg(payload)),
            ),
        ).fetchone()
        assert row is not None
        return row["id"]

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def list_indexable_evidence() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json, source_id
            FROM evidence
            WHERE evidence_kind IN ('communication', 'calendar_event')
            ORDER BY created_at
            """
        ).fetchall()
        return [dict(r) for r in rows]


def find_sms_export_source(
    *, conn: Any | None = None, uri: str | None = None
) -> dict[str, Any] | None:
    """Prefer an exact URI, then the FlightSim 1085-session export, else most rows."""

    def _run(c: Any) -> dict[str, Any] | None:
        if uri:
            hit = c.execute(
                """
                SELECT s.id, s.uri, s.label, s.updated_at,
                       (SELECT count(*) FROM evidence e WHERE e.source_id = s.id) AS n
                FROM sources s
                WHERE s.source_kind = 'sms_export' AND s.uri = %s
                LIMIT 1
                """,
                (str(uri),),
            ).fetchone()
            if hit:
                return dict(hit)
        rows = c.execute(
            """
            SELECT s.id, s.uri, s.label, s.updated_at,
                   (SELECT count(*) FROM evidence e WHERE e.source_id = s.id) AS n
            FROM sources s
            WHERE s.source_kind = 'sms_export'
            ORDER BY n DESC, s.updated_at DESC
            """
        ).fetchall()
        if not rows:
            return None
        preferred = None
        for r in rows:
            row_uri = str(r.get("uri") or "").casefold()
            if "1085 chat sessions" in row_uri or row_uri.endswith(
                "messages - 1085 chat sessions.csv"
            ):
                preferred = dict(r)
                break
        return preferred or dict(rows[0])

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def list_evidence_for_source(
    source_id: UUID, *, conn: Any | None = None
) -> list[dict[str, Any]]:
    """All evidence rows for one Source (SMS backfill / unique export match)."""

    def _run(c: Any) -> list[dict[str, Any]]:
        rows = c.execute(
            """
            SELECT id, evidence_kind, summary, payload_json, source_id
            FROM evidence
            WHERE source_id = %s
            ORDER BY created_at
            """,
            (source_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def get_evidence(evidence_id: UUID, *, conn: Any | None = None) -> dict[str, Any] | None:
    def _run(c: Any) -> dict[str, Any] | None:
        row = c.execute(
            "SELECT id, evidence_kind, summary, payload_json, source_id FROM evidence WHERE id = %s",
            (evidence_id,),
        ).fetchone()
        return dict(row) if row else None

    if conn is not None:
        return _run(conn)
    with connection() as c:
        return _run(c)


def update_evidence_payload(
    evidence_id: UUID, payload: dict[str, Any], *, conn: Any | None = None
) -> None:
    def _run(c: Any) -> None:
        c.execute(
            """
            UPDATE evidence
            SET payload_json = %s::jsonb, updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(sanitize_pg(payload)), evidence_id),
        )

    if conn is not None:
        _run(conn)
        return
    with connection() as c:
        _run(c)
