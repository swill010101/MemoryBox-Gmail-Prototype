"""Disposable I14 identity/ingest transaction helpers. Never writes FlightSim unless a later auth.

Refuse dbname memorybox. Use SAVEPOINT per record so unique conflicts do not abort the session.
Advisory locks use SHA-256 bytes, not hashtext().
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.errors import UniqueViolation

OUT_INSERTED = "inserted"
OUT_REUSED = "reused"
OUT_ALIAS_CONFLICT = "alias_conflict"
OUT_ELIGIBLE_BACKFILL = "eligible_for_backfill"
OUT_NEEDS_POLICY = "needs_canonical_policy"
OUT_CHECKED_UNCHANGED = "checked_unchanged"
OUT_MEMBERSHIP_CONFLICT = "membership_conflict"

KIND_TO_SOURCE = {"email": "email", "calendar": "calendar", "sms": "sms"}


class IdentityError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AliasOwned(Exception):
    """Candidate alias already bound to a different canonical."""


@dataclass
class RecordResult:
    code: str
    evidence_id: UUID | None = None


def _dbname(conn: Any) -> str:
    row = conn.execute("SELECT current_database() AS d").fetchone()
    name = str(row["d"] if isinstance(row, dict) else row[0])
    if name.lower() == "memorybox":
        raise IdentityError("refused_memorybox_dbname")
    return name


def _lock(conn: Any, logical_source_id: Any, aliases: list[tuple[str, str]]) -> None:
    material = str(logical_source_id) + "\n" + "\n".join(
        sorted(f"{m}\t{k}" for m, k in aliases)
    )
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    k1 = int.from_bytes(digest[0:4], "big", signed=True)
    k2 = int.from_bytes(digest[4:8], "big", signed=True)
    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (k1, k2))


def ensure_logical_source(
    conn: Any, *, source_kind: str, logical_key: str, label: str
) -> UUID:
    _dbname(conn)
    row = conn.execute(
        """
        INSERT INTO comms_logical_sources (logical_key, source_kind, label)
        VALUES (%s, %s, %s)
        ON CONFLICT (source_kind, logical_key) DO UPDATE
           SET label = EXCLUDED.label
        RETURNING id
        """,
        (logical_key, source_kind, label),
    ).fetchone()
    return row["id"] if isinstance(row, dict) else row[0]


def ensure_membership(conn: Any, *, source_id: Any, logical_source_id: Any) -> str:
    existing = conn.execute(
        "SELECT logical_source_id AS l FROM comms_source_memberships WHERE source_id = %s",
        (source_id,),
    ).fetchone()
    if existing:
        have = existing["l"] if isinstance(existing, dict) else existing[0]
        if str(have) != str(logical_source_id):
            return OUT_MEMBERSHIP_CONFLICT
        return "ok"
    conn.execute(
        """
        INSERT INTO comms_source_memberships (source_id, logical_source_id)
        VALUES (%s, %s)
        """,
        (source_id, logical_source_id),
    )
    return "ok"


def register_extract(
    conn: Any,
    *,
    logical_source_id: Any,
    source_id: Any,
    fingerprint: str,
    landing_alias: str,
    landing_basename: str,
) -> tuple[str, UUID]:
    _dbname(conn)
    row = conn.execute(
        """
        SELECT id FROM comms_extract_instances
         WHERE logical_source_id = %s AND fingerprint = %s
        """,
        (logical_source_id, fingerprint),
    ).fetchone()
    if row:
        eid = row["id"] if isinstance(row, dict) else row[0]
        return OUT_CHECKED_UNCHANGED, eid
    row = conn.execute(
        """
        INSERT INTO comms_extract_instances (
          logical_source_id, source_id, fingerprint, landing_alias, landing_basename,
          validation_status, ingest_status
        ) VALUES (%s, %s, %s, %s, %s, 'valid', 'running')
        RETURNING id
        """,
        (logical_source_id, source_id, fingerprint, landing_alias, landing_basename),
    ).fetchone()
    return "new_extract", row["id"] if isinstance(row, dict) else row[0]


def _canonicals_for_aliases(
    conn: Any, logical_source_id: Any, aliases: list[tuple[str, str]]
) -> list[UUID]:
    found: set[str] = set()
    ids: list[UUID] = []
    for method, key in aliases:
        row = conn.execute(
            """
            SELECT canonical_record_id AS id
              FROM comms_record_identity_aliases
             WHERE logical_source_id = %s AND identity_method = %s AND record_key = %s
            """,
            (logical_source_id, method, key),
        ).fetchone()
        if not row:
            continue
        cid = row["id"] if isinstance(row, dict) else row[0]
        token = str(cid)
        if token not in found:
            found.add(token)
            ids.append(cid)
    return ids


def _add_missing_aliases(
    conn: Any, *, canonical_id: Any, logical_source_id: Any, aliases: list[tuple[str, str]]
) -> None:
    for method, key in aliases:
        row = conn.execute(
            """
            SELECT canonical_record_id AS c
              FROM comms_record_identity_aliases
             WHERE logical_source_id = %s AND identity_method = %s AND record_key = %s
            """,
            (logical_source_id, method, key),
        ).fetchone()
        if row:
            owner = row["c"] if isinstance(row, dict) else row[0]
            if str(owner) != str(canonical_id):
                raise AliasOwned()
            continue
        conn.execute(
            """
            INSERT INTO comms_record_identity_aliases (
              canonical_record_id, logical_source_id, identity_method, record_key
            ) VALUES (%s, %s, %s, %s)
            """,
            (canonical_id, logical_source_id, method, key),
        )


def _historical_matches(
    conn: Any,
    *,
    stream_source_ids: list[Any],
    content_hash: str,
    rfc_own: str | None,
) -> list[UUID]:
    rows = conn.execute(
        """
        SELECT e.id
          FROM evidence e
         WHERE e.source_id = ANY(%s)
           AND lower(btrim(COALESCE(e.payload_json->>'content_hash', ''))) = %s
           AND NOT EXISTS (
             SELECT 1 FROM comms_record_identities i WHERE i.evidence_id = e.id
           )
        """,
        (stream_source_ids, content_hash.lower()),
    ).fetchall()
    ids = [r["id"] if isinstance(r, dict) else r[0] for r in rows]
    if rfc_own:
        rfc_rows = conn.execute(
            """
            SELECT DISTINCT r.evidence_id AS id
              FROM communication_rfc_ids r
              JOIN evidence e ON e.id = r.evidence_id
             WHERE e.source_id = ANY(%s)
               AND lower(btrim(r.rfc_message_id)) = %s
               AND lower(btrim(r.role::text)) = 'own'
               AND NOT EXISTS (
                 SELECT 1 FROM comms_record_identities i WHERE i.evidence_id = r.evidence_id
               )
            """,
            (stream_source_ids, rfc_own.lower()),
        ).fetchall()
        extra = [r["id"] if isinstance(r, dict) else r[0] for r in rfc_rows]
        for eid in extra:
            if eid not in ids:
                ids.append(eid)
    return ids


def apply_record(
    conn: Any,
    *,
    logical_source_id: Any,
    extract_instance_id: Any,
    source_id: Any,
    source_kind: str,
    evidence_kind: str,
    content_hash: str,
    aliases: list[tuple[str, str]],
    stream_source_ids: list[Any],
    rfc_own: str | None = None,
    summary: str = "synthetic",
) -> RecordResult:
    """One logical record. Caller holds the transaction; this uses a savepoint."""
    _dbname(conn)
    aliases = [(m, k) for m, k in aliases if k and len(k) >= 3]
    if not aliases:
        raise IdentityError("aliases_required")
    conn.execute("SAVEPOINT i14_rec")
    try:
        _lock(conn, logical_source_id, aliases)
        canonicals = _canonicals_for_aliases(conn, logical_source_id, aliases)
        if len(canonicals) >= 2:
            conn.execute("ROLLBACK TO SAVEPOINT i14_rec")
            return RecordResult(OUT_ALIAS_CONFLICT)
        if len(canonicals) == 1:
            cid = canonicals[0]
            ev = conn.execute(
                "SELECT evidence_id AS e FROM comms_record_identities WHERE id = %s",
                (cid,),
            ).fetchone()
            _add_missing_aliases(
                conn, canonical_id=cid, logical_source_id=logical_source_id, aliases=aliases
            )
            conn.execute("RELEASE SAVEPOINT i14_rec")
            eid = ev["e"] if isinstance(ev, dict) else ev[0]
            return RecordResult(OUT_REUSED, eid)
        hist = _historical_matches(
            conn,
            stream_source_ids=stream_source_ids,
            content_hash=content_hash,
            rfc_own=rfc_own,
        )
        if len(hist) >= 2:
            conn.execute("ROLLBACK TO SAVEPOINT i14_rec")
            return RecordResult(OUT_NEEDS_POLICY)
        if len(hist) == 1:
            conn.execute("ROLLBACK TO SAVEPOINT i14_rec")
            return RecordResult(OUT_ELIGIBLE_BACKFILL, hist[0])
        ev_row = conn.execute(
            """
            INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                evidence_kind,
                source_id,
                summary,
                json.dumps({"content_hash": content_hash.lower()}),
            ),
        ).fetchone()
        evid = ev_row["id"] if isinstance(ev_row, dict) else ev_row[0]
        rec = conn.execute(
            """
            INSERT INTO comms_record_identities (
              logical_source_id, evidence_id, source_kind, first_extract_instance_id
            ) VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (logical_source_id, evid, source_kind, extract_instance_id),
        ).fetchone()
        cid = rec["id"] if isinstance(rec, dict) else rec[0]
        _add_missing_aliases(
            conn, canonical_id=cid, logical_source_id=logical_source_id, aliases=aliases
        )
        conn.execute("RELEASE SAVEPOINT i14_rec")
        return RecordResult(OUT_INSERTED, evid)
    except (UniqueViolation, AliasOwned):
        conn.execute("ROLLBACK TO SAVEPOINT i14_rec")
        return RecordResult(OUT_ALIAS_CONFLICT)
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT i14_rec")
        raise
