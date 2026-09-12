"""Read-only I14 cross-extract duplicate audit. Counts only. Never emits hashes or RFC tokens.

Does not seed, backfill, ingest, or write production tables. Creates a session TEMP TABLE,
aggregates, then rolls back. Refuse dbname memorybox unless MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB=1.
Do not run on FlightSim until founder-authorized.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

HASH_SHAPE = re.compile(r"^[a-f0-9]{64}$")
HEX64 = re.compile(r"\b[a-f0-9]{64}\b", re.I)
TOKEN_COLUMNS = (
    "rfc_message_id",
    "message_id",
    "rfc_id",
    "normalized_rfc",
    "token",
    "value",
)
PROPOSED_STREAMS = ("household_email", "household_calendar", "household_sms")


class AuditError(RuntimeError):
    """Hard-stop for the duplicate audit CLI."""


def catalog_execute(conn: Any, sql: str, params: tuple | list | None = None) -> Any:
    if "%" in sql and not params:
        raise AuditError("unsafe_percent_sql")
    if not params:
        return conn.execute(sql)
    return conn.execute(sql, params)


def uri_class(uri: str | None) -> str:
    text = unquote((uri or "").strip().lower().replace("\\", "/"))
    if text.endswith(".mbox"):
        return "mbox"
    if text.endswith(".ics"):
        return "ics"
    if text.endswith(".csv"):
        return "csv"
    return "other"


def classify_hash(raw: Any) -> tuple[str, str]:
    value = str(raw or "").strip()
    if not value:
        return "", "missing"
    lowered = value.lower()
    if HASH_SHAPE.fullmatch(lowered):
        return lowered, "ok"
    return lowered, "invalid"


def assert_counts_only(payload: dict[str, Any]) -> None:
    blob = json.dumps(payload, default=str)
    if HEX64.search(blob):
        raise AuditError("audit_output_contains_hash_or_hex64")


def _require_not_memorybox(conn: Any) -> str:
    row = catalog_execute(conn, "SELECT current_database() AS d").fetchone()
    name = str(row["d"] if isinstance(row, dict) else row[0]).lower()
    allow = os.environ.get("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", "").strip() == "1"
    if name == "memorybox" and not allow:
        raise AuditError("refused_memorybox_dbname")
    return name


def _table_exists(conn: Any, name: str) -> bool:
    row = catalog_execute(
        conn,
        """
        SELECT 1 AS ok
          FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = %s
        """,
        (name,),
    ).fetchone()
    return bool(row)


def _columns(conn: Any, table: str) -> set[str]:
    rows = catalog_execute(
        conn,
        """
        SELECT column_name AS c
          FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    ).fetchall()
    names = set()
    for row in rows:
        names.add(str(row["c"] if isinstance(row, dict) else row[0]))
    return names


def _create_temp(conn: Any) -> None:
    catalog_execute(
        conn,
        """
        CREATE TEMP TABLE i14_audit_hash_rows (
          evidence_id uuid,
          source_id uuid,
          evidence_kind text,
          source_kind text,
          uri_class text,
          content_hash text,
          hash_status text
        ) ON COMMIT DROP
        """,
    )


def _load_rows(conn: Any) -> None:
    sources = catalog_execute(
        conn,
        "SELECT DISTINCT source_id AS s FROM evidence",
    ).fetchall()
    ids = [r["s"] if isinstance(r, dict) else r[0] for r in sources]
    if not ids:
        ids = [None]
    sql = """
        INSERT INTO i14_audit_hash_rows (
          evidence_id, source_id, evidence_kind, source_kind, uri_class, content_hash, hash_status
        )
        SELECT
          e.id,
          e.source_id,
          e.evidence_kind,
          COALESCE(s.source_kind, ''),
          CASE
            WHEN right(replace(lower(COALESCE(s.uri, '')), '\\', '/'), 5) = '.mbox' THEN 'mbox'
            WHEN right(replace(lower(COALESCE(s.uri, '')), '\\', '/'), 4) = '.ics' THEN 'ics'
            WHEN right(replace(lower(COALESCE(s.uri, '')), '\\', '/'), 4) = '.csv' THEN 'csv'
            ELSE 'other'
          END,
          lower(btrim(COALESCE(e.payload_json->>'content_hash', ''))),
          CASE
            WHEN btrim(COALESCE(e.payload_json->>'content_hash', '')) = '' THEN 'missing'
            WHEN lower(btrim(e.payload_json->>'content_hash')) ~ '^[a-f0-9]{64}$' THEN 'ok'
            ELSE 'invalid'
          END
        FROM evidence e
        LEFT JOIN sources s ON s.id = e.source_id
        WHERE e.source_id IS NOT DISTINCT FROM %s
        """
    for sid in ids:
        catalog_execute(conn, "SET LOCAL statement_timeout = '30s'")
        catalog_execute(conn, sql, (sid,))
    catalog_execute(
        conn,
        """
        CREATE INDEX i14_audit_hash_ok ON i14_audit_hash_rows (content_hash)
          WHERE hash_status = 'ok'
        """,
    )
    catalog_execute(
        conn,
        "CREATE INDEX i14_audit_hash_src ON i14_audit_hash_rows (source_id, content_hash)",
    )


def _count_status(conn: Any, status: str) -> int:
    row = catalog_execute(
        conn,
        "SELECT COUNT(*) AS n FROM i14_audit_hash_rows WHERE hash_status = %s",
        (status,),
    ).fetchone()
    return int(row["n"] if isinstance(row, dict) else row[0])


def _kind_inventory(conn: Any) -> list[dict[str, Any]]:
    rows = catalog_execute(
        conn,
        """
        SELECT evidence_kind, source_kind, COUNT(*) AS rows,
               COUNT(DISTINCT source_id) AS distinct_sources
          FROM i14_audit_hash_rows
         GROUP BY evidence_kind, source_kind
         ORDER BY evidence_kind, source_kind
        """,
    ).fetchall()
    out = []
    for row in rows:
        rec = dict(row) if not isinstance(row, dict) else row
        out.append(
            {
                "evidence_kind": rec["evidence_kind"],
                "source_kind": rec["source_kind"],
                "rows": int(rec["rows"]),
                "distinct_sources": int(rec["distinct_sources"]),
            }
        )
    return out


def _uri_inventory(conn: Any) -> list[dict[str, Any]]:
    rows = catalog_execute(
        conn,
        """
        SELECT uri_class, source_kind, COUNT(*) AS rows,
               COUNT(DISTINCT source_id) AS distinct_sources
          FROM i14_audit_hash_rows
         GROUP BY uri_class, source_kind
         ORDER BY uri_class, source_kind
        """,
    ).fetchall()
    out = []
    for row in rows:
        rec = dict(row) if not isinstance(row, dict) else row
        out.append(
            {
                "uri_class": rec["uri_class"],
                "source_kind": rec["source_kind"],
                "rows": int(rec["rows"]),
                "distinct_sources": int(rec["distinct_sources"]),
            }
        )
    return out


def _within_source(conn: Any) -> dict[str, int]:
    row = catalog_execute(
        conn,
        """
        WITH dup AS (
          SELECT source_id, content_hash, COUNT(*) AS n
            FROM i14_audit_hash_rows
           WHERE hash_status = 'ok'
           GROUP BY source_id, content_hash
          HAVING COUNT(*) > 1
        )
        SELECT COUNT(*) AS colliding_hashes,
               COALESCE(SUM(n - 1), 0) AS extra_rows,
               COUNT(DISTINCT source_id) AS sources_affected
          FROM dup
        """,
    ).fetchone()
    rec = dict(row) if not isinstance(row, dict) else row
    return {
        "colliding_hashes": int(rec["colliding_hashes"]),
        "extra_rows": int(rec["extra_rows"]),
        "sources_affected": int(rec["sources_affected"]),
    }


def _cross_source_in_cluster(conn: Any, *, stream_map: dict[str, str] | None) -> dict[str, Any]:
    if stream_map:
        catalog_execute(
            conn,
            """
            CREATE TEMP TABLE i14_audit_stream_map (
              source_id uuid PRIMARY KEY,
              logical_key text NOT NULL
            ) ON COMMIT DROP
            """,
        )
        for sid, key in stream_map.items():
            catalog_execute(
                conn,
                "INSERT INTO i14_audit_stream_map (source_id, logical_key) VALUES (%s, %s)",
                (sid, key),
            )
        row = catalog_execute(
            conn,
            """
            WITH tagged AS (
              SELECT r.content_hash, r.source_id, m.logical_key
                FROM i14_audit_hash_rows r
                JOIN i14_audit_stream_map m ON m.source_id = r.source_id
               WHERE r.hash_status = 'ok'
            ),
            dup AS (
              SELECT logical_key, content_hash,
                     COUNT(DISTINCT source_id) AS sources,
                     COUNT(*) AS n
                FROM tagged
               GROUP BY logical_key, content_hash
              HAVING COUNT(DISTINCT source_id) > 1
            )
            SELECT COUNT(*) AS colliding_hashes,
                   COALESCE(SUM(n - sources), 0) AS extra_rows,
                   COUNT(DISTINCT logical_key) AS streams_affected
              FROM dup
            """,
        ).fetchone()
        rec = dict(row) if not isinstance(row, dict) else row
        return {
            "mode": "assigned_stream",
            "colliding_hashes": int(rec["colliding_hashes"]),
            "extra_rows": int(rec["extra_rows"]),
            "streams_affected": int(rec["streams_affected"]),
        }
    row = catalog_execute(
        conn,
        """
        WITH dup AS (
          SELECT source_kind, uri_class, content_hash,
                 COUNT(DISTINCT source_id) AS sources,
                 COUNT(*) AS n
            FROM i14_audit_hash_rows
           WHERE hash_status = 'ok'
           GROUP BY source_kind, uri_class, content_hash
          HAVING COUNT(DISTINCT source_id) > 1
        )
        SELECT COUNT(*) AS colliding_hashes,
               COALESCE(SUM(n - sources), 0) AS extra_rows
          FROM dup
        """,
    ).fetchone()
    rec = dict(row) if not isinstance(row, dict) else row
    return {
        "mode": "unassigned_cluster",
        "colliding_hashes": int(rec["colliding_hashes"]),
        "extra_rows": int(rec["extra_rows"]),
    }


def _cross_cluster_or_stream(conn: Any, *, stream_map: dict[str, str] | None) -> dict[str, int]:
    if stream_map:
        row = catalog_execute(
            conn,
            """
            WITH tagged AS (
              SELECT r.content_hash, m.logical_key
                FROM i14_audit_hash_rows r
                JOIN i14_audit_stream_map m ON m.source_id = r.source_id
               WHERE r.hash_status = 'ok'
            ),
            spread AS (
              SELECT content_hash, COUNT(DISTINCT logical_key) AS streams
                FROM tagged
               GROUP BY content_hash
              HAVING COUNT(DISTINCT logical_key) > 1
            )
            SELECT COUNT(*) AS colliding_hashes FROM spread
            """,
        ).fetchone()
    else:
        row = catalog_execute(
            conn,
            """
            WITH spread AS (
              SELECT content_hash, COUNT(DISTINCT (source_kind || ':' || uri_class)) AS clusters
                FROM i14_audit_hash_rows
               WHERE hash_status = 'ok'
               GROUP BY content_hash
              HAVING COUNT(DISTINCT (source_kind || ':' || uri_class)) > 1
            )
            SELECT COUNT(*) AS colliding_hashes FROM spread
            """,
        ).fetchone()
    rec = dict(row) if not isinstance(row, dict) else row
    return {"colliding_hashes": int(rec["colliding_hashes"])}


def _rfc_fanout(conn: Any) -> dict[str, Any]:
    if not _table_exists(conn, "communication_rfc_ids"):
        return {"present": False, "skipped": "table_absent"}
    cols = _columns(conn, "communication_rfc_ids")
    if "evidence_id" not in cols:
        return {"present": True, "skipped": "no_evidence_id_column"}
    token_col = next((c for c in TOKEN_COLUMNS if c in cols), None)
    if not token_col:
        return {"present": True, "skipped": "no_token_column"}
    role_filter = "AND lower(btrim(role::text)) = 'own'" if "role" in cols else ""
    if not token_col.replace("_", "").isalnum():
        return {"present": True, "skipped": "unsafe_token_column"}
    sql = f"""
        WITH own AS (
          SELECT evidence_id, lower(btrim({token_col}::text)) AS tok
            FROM communication_rfc_ids
           WHERE {token_col} IS NOT NULL
             AND btrim({token_col}::text) <> ''
             {role_filter}
        ),
        fan AS (
          SELECT tok, COUNT(DISTINCT evidence_id) AS n
            FROM own
           GROUP BY tok
          HAVING COUNT(DISTINCT evidence_id) > 1
        )
        SELECT COUNT(*) AS token_groups,
               COALESCE(SUM(n - 1), 0) AS extra_evidence_rows
          FROM fan
        """
    row = catalog_execute(conn, sql).fetchone()
    rec = dict(row) if not isinstance(row, dict) else row
    return {
        "present": True,
        "skipped": None,
        "token_groups": int(rec["token_groups"]),
        "extra_evidence_rows": int(rec["extra_evidence_rows"]),
    }


def run_audit(conn: Any, *, stream_map: dict[str, str] | None = None) -> dict[str, Any]:
    dbname = _require_not_memorybox(conn)
    catalog_execute(conn, "SET LOCAL statement_timeout = '30s'")
    _create_temp(conn)
    _load_rows(conn)
    report = {
        "ok": True,
        "read_only_production_tables": True,
        "database_kind": "disposable_not_memorybox" if dbname != "memorybox" else "memorybox_explicitly_allowed",
        "proposed_streams": list(PROPOSED_STREAMS),
        "kind_inventory": _kind_inventory(conn),
        "uri_class_inventory": _uri_inventory(conn),
        "missing_hash": _count_status(conn, "missing"),
        "invalid_hash": _count_status(conn, "invalid"),
        "within_source_duplicates": _within_source(conn),
        "cross_source_same_stream_or_cluster": _cross_source_in_cluster(conn, stream_map=stream_map),
        "same_hash_different_streams_or_clusters": _cross_cluster_or_stream(conn, stream_map=stream_map),
        "rfc_own_fanout": _rfc_fanout(conn),
        "stream_map_applied": bool(stream_map),
    }
    assert_counts_only(report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
    if not dsn:
        raise AuditError("MEMORYBOX_DATABASE_URL_missing")
    stream_map = None
    if "--stream-map" in args:
        idx = args.index("--stream-map")
        raw = json.loads(Path(args[idx + 1]).read_text(encoding="utf-8"))
        stream_map = {str(k): str(v) for k, v in raw.items()}
        bad = [v for v in stream_map.values() if v not in PROPOSED_STREAMS]
        if bad:
            raise AuditError("stream_map_unknown_logical_key")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            report = run_audit(conn, stream_map=stream_map)
            conn.rollback()
        except Exception:
            conn.rollback()
            raise
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from exc
