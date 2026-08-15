"""Shared ingest helpers: jobs + Source/Evidence writes (PostgreSQL only)."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection


def start_job(job_kind: str, *, message: str = "", payload: dict | None = None) -> UUID:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO jobs (job_kind, status, message, payload_json, started_at)
            VALUES (%s, 'running', %s, %s::jsonb, now())
            RETURNING id
            """,
            (job_kind, message, json.dumps(payload or {})),
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
            (status, message, error_message, job_id),
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
            (evidence_kind, source_id, summary, json.dumps(payload)),
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
            (json.dumps(payload), evidence_id),
        )

    if conn is not None:
        _run(conn)
        return
    with connection() as c:
        _run(c)
