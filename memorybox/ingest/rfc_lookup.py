"""Durable indexed RFC Message-ID lookup for email communications.

Runtime neighbor walking queries communication_rfc_ids by equality.
Archive JSON/regex extraction is allowed only in this backfill/ingest path.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any
from uuid import UUID

_RFC_ID = re.compile(r"<[^<>\s]{1,200}@[^<>\s]{1,255}>")
_SKIP_CHANNELS = frozenset({"sms", "text", "imessage", "mms", "rcs"})
_BACKFILL_PAGE = 500
RFC_ID_MAX_BYTES = 512
LOOKUP_TABLE = "communication_rfc_ids"


def _norm_rfc(raw: str) -> str:
    """Canonical <local@host>. Empty if missing, folded, or too large for btree."""
    mid = (raw or "").strip()
    if not mid or any(ch.isspace() for ch in mid):
        return ""
    if not mid.startswith("<") and "@" in mid:
        mid = f"<{mid}>"
    mid = mid.lower()
    if not (mid.startswith("<") and mid.endswith(">") and "@" in mid):
        return ""
    inner = mid[1:-1]
    if (
        not inner
        or inner.count("@") < 1
        or "<" in inner
        or ">" in inner
        or any(ch.isspace() for ch in inner)
    ):
        return ""
    if len(mid.encode("utf-8")) > RFC_ID_MAX_BYTES:
        return ""
    if _RFC_ID.fullmatch(mid) is None:
        return ""
    return mid


def _rfc_ids(*parts: Any) -> list[str]:
    found: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple)):
            texts = [str(x) for x in part]
        else:
            texts = [str(part)]
        for text in texts:
            for match in _RFC_ID.findall(text):
                found.append(match.strip())
            bare = text.strip()
            if bare.startswith("<") and bare.endswith(">"):
                found.append(bare)
    out: list[str] = []
    seen: set[str] = set()
    for raw in found:
        nid = _norm_rfc(raw)
        if not nid or nid in seen:
            continue
        seen.add(nid)
        out.append(nid)
    return out


def is_email_communication(evidence_kind: str, payload: dict[str, Any] | None) -> bool:
    if str(evidence_kind or "") != "communication":
        return False
    ch = str((payload or {}).get("evidence_channel") or "email").strip().lower()
    return ch not in _SKIP_CHANNELS


def extract_rfc_lookup_rows(payload: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Return (rfc_id, role) pairs. Mixed-case input is canonicalized."""
    payload = payload or {}
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(raw: str, role: str) -> None:
        nid = _norm_rfc(raw)
        if not nid:
            return
        key = (nid, role)
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    own = str(payload.get("rfc_message_id") or payload.get("message_id") or "")
    if own.strip():
        _add(own, "own")
    for raw in _rfc_ids(payload.get("in_reply_to"), payload.get("in_reply_to_ids")):
        _add(raw, "in_reply_to")
    for raw in _rfc_ids(payload.get("references")):
        _add(raw, "references")
    return out


def replace_communication_rfc_ids(
    evidence_id: UUID | str,
    payload: dict[str, Any] | None,
    *,
    conn: Any,
    evidence_kind: str = "communication",
) -> int:
    """Idempotent replace of lookup rows for one evidence id."""
    conn.execute(
        "DELETE FROM communication_rfc_ids WHERE evidence_id = %s",
        (evidence_id,),
    )
    if not is_email_communication(evidence_kind, payload or {}):
        return 0
    rows = extract_rfc_lookup_rows(payload)
    if not rows:
        return 0
    inserted = 0
    for rfc_id, role in rows:
        conn.execute(
            """
            INSERT INTO communication_rfc_ids (evidence_id, rfc_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (evidence_id, rfc_id, role) DO NOTHING
            """,
            (evidence_id, rfc_id, role),
        )
        inserted += 1
    return inserted


def backfill_communication_rfc_ids(
    conn: Any | None = None,
    *,
    page_size: int = _BACKFILL_PAGE,
) -> dict[str, Any]:
    """Idempotent archive backfill. May scan communications once; runtime walk must not."""
    from memorybox.db import connection as default_connection

    started = time.monotonic()
    processed = 0
    email_n = 0
    row_n = 0

    def _run(c: Any) -> None:
        nonlocal processed, email_n, row_n
        last_id: Any = None
        while True:
            params: list[Any] = []
            id_clause = ""
            if last_id is not None:
                id_clause = "AND id > %s"
                params.append(last_id)
            params.append(int(page_size))
            fetched = c.execute(
                f"""
                SELECT id, evidence_kind, payload_json
                FROM evidence
                WHERE evidence_kind = 'communication'
                {id_clause}
                ORDER BY id
                LIMIT %s
                """,
                params,
            ).fetchall()
            if not fetched:
                break
            for raw in fetched:
                last_id = raw["id"]
                processed += 1
                payload = raw["payload_json"] if isinstance(raw["payload_json"], dict) else {}
                kind = str(raw["evidence_kind"] or "")
                if not is_email_communication(kind, payload):
                    c.execute(
                        "DELETE FROM communication_rfc_ids WHERE evidence_id = %s",
                        (raw["id"],),
                    )
                    continue
                email_n += 1
                row_n += replace_communication_rfc_ids(
                    raw["id"], payload, conn=c, evidence_kind=kind
                )
            if len(fetched) < page_size:
                break

    if conn is not None:
        _run(conn)
    else:
        with default_connection() as c:
            _run(c)
    return {
        "ok": True,
        "processed_communication_n": processed,
        "email_communication_n": email_n,
        "lookup_row_writes": row_n,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "idempotent": True,
    }


def neighbor_timeouts() -> tuple[int, float]:
    """(statement_timeout_ms, stage_deadline_s)."""
    stmt = int(os.environ.get("MEMORYBOX_RFC_NEIGHBOR_STATEMENT_TIMEOUT_MS") or 30_000)
    stage = float(os.environ.get("MEMORYBOX_RFC_NEIGHBOR_STAGE_DEADLINE_S") or 180)
    return max(1, stmt), max(0.0, stage)
