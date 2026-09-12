"""Read-only I14 cross-extract duplicate audit. Counts only. Never emits hashes or RFC tokens.

Does not seed, backfill, ingest, or write production tables. Session TEMP TABLEs only;
aggregates in SQL; always rolls back. Refuse dbname memorybox unless
MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB=1. Do not run on FlightSim until founder-authorized.

PostgreSQL forbids CREATE TEMP TABLE under SET TRANSACTION READ ONLY (catalog writes to
pg_class). The permitted path is therefore: autocommit off, START TRANSACTION (not READ
ONLY), session TEMP ON COMMIT DROP, execute-gate refusing persistent DML/DDL, rollback on
success and error. Persistent catalogs are unchanged.

SQL strategy: keyset INSERT…SELECT of trim/lower(payload_json->>'content_hash') into TEMP
(WHERE evidence.id > last ORDER BY id LIMIT n). No OFFSET rescan. GROUP BY the full text
(no hashtext, left/substr, or Python hash fetches). Whole-run deadline plus per-statement timeout.

JSON schema (success): ok, read_only_production_tables, database_kind, proposed_streams,
kind_inventory[], uri_class_inventory[], missing_hash, invalid_hash,
within_source_duplicates{colliding_hashes,extra_rows,sources_affected},
cross_source_same_stream_or_cluster{mode,colliding_hashes,extra_rows,...},
same_hash_different_streams_or_clusters{colliding_hashes}, rfc_own_fanout,
stream_map_applied, statement_timeout, persistent_write_gate.

Failure JSON: {ok: false, error: <code>} — never a partial report with ok true.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

HASH_SHAPE = re.compile(r"^[a-f0-9]{64}$")
HEX64 = re.compile(r"\b[a-f0-9]{64}\b", re.I)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
HEX_PREFIX = re.compile(r"\b[a-f0-9]{16,}\b", re.I)
TIMEOUT_SHAPE = re.compile(r"^[0-9]+(ms|s|min)?$")
WRITE_HEAD = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|COPY|CREATE|ALTER|DROP|GRANT|REVOKE|"
    r"COMMENT|VACUUM|CLUSTER|REINDEX|LOCK)\b",
    re.I,
)
TEMP_WRITE_OK = re.compile(
    r"^\s*CREATE\s+TEMP(ORARY)?\s+TABLE\s+i14_audit_|"
    r"^\s*CREATE\s+INDEX\s+i14_audit_|"
    r"^\s*INSERT\s+INTO\s+i14_audit_",
    re.I,
)
TOKEN_COLUMNS = (
    "rfc_message_id",
    "message_id",
    "rfc_id",
    "normalized_rfc",
    "token",
    "value",
)
PROPOSED_STREAMS = ("household_email", "household_calendar", "household_sms")
DEFAULT_STATEMENT_TIMEOUT = "30s"
DEFAULT_BATCH = 10000
DEFAULT_RUN_DEADLINE_S = 180
KEYSET_START = "00000000-0000-0000-0000-000000000000"


class AuditError(RuntimeError):
    """Hard-stop for the duplicate audit CLI. Message is a public error code only."""


def catalog_execute(conn: Any, sql: str, params: tuple | list | None = None) -> Any:
    if "%" in sql and not params:
        raise AuditError("unsafe_percent_sql")
    _refuse_persistent_write(sql)
    try:
        if not params:
            return conn.execute(sql)
        return conn.execute(sql, params)
    except Exception as exc:
        if _is_query_canceled(exc):
            raise AuditError("statement_timeout") from None
        raise


def _is_query_canceled(exc: BaseException) -> bool:
    try:
        from psycopg.errors import QueryCanceled

        if isinstance(exc, QueryCanceled):
            return True
    except ImportError:
        pass
    text = type(exc).__name__.lower() + " " + str(exc).lower()
    return "querycanceled" in text.replace(" ", "") or "statement timeout" in text or "query_canceled" in text


def _refuse_persistent_write(sql: str) -> None:
    stripped = sql.strip()
    if stripped.startswith("--"):
        return
    if re.search(r"\bINSERT\s+INTO\s+i14_audit_", stripped, re.I):
        return
    if TEMP_WRITE_OK.match(stripped):
        return
    if WRITE_HEAD.match(stripped) or re.search(
        r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b", stripped, re.I
    ):
        raise AuditError("persistent_write_refused")


def uri_class(uri: str | None) -> str:
    from urllib.parse import unquote

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
    if payload.get("ok") is True and payload.get("error"):
        raise AuditError("complete_report_must_not_include_error")
    if HEX64.search(blob):
        raise AuditError("audit_output_contains_hash_or_hex64")
    if UUID_RE.search(blob):
        raise AuditError("audit_output_contains_uuid")
    if EMAIL_RE.search(blob):
        raise AuditError("audit_output_contains_address")
    if HEX_PREFIX.search(blob):
        raise AuditError("audit_output_contains_hash_prefix")
    lowered = blob.lower()
    for marker in (".mbox", ".ics", "://", "\\\\"):
        if marker in lowered:
            raise AuditError("audit_output_contains_uri_or_filename")


def _require_not_memorybox(conn: Any) -> str:
    row = catalog_execute(conn, "SELECT current_database() AS d").fetchone()
    name = str(row["d"] if isinstance(row, dict) else row[0]).lower()
    allow = os.environ.get("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", "").strip() == "1"
    if name == "memorybox" and not allow:
        raise AuditError("refused_memorybox_dbname")
    return name


def emit_progress(event: dict[str, Any]) -> None:
    payload = dict(event)
    payload.pop("ok", None)
    assert_counts_only(payload)
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _deadline_guard(deadline_mono: float) -> None:
    if time.monotonic() >= deadline_mono:
        raise AuditError("run_deadline")


def _begin_audit_transaction(conn: Any) -> None:
    if getattr(conn, "autocommit", False):
        raise AuditError("autocommit_not_allowed")
    info = getattr(conn, "info", None)
    status = getattr(info, "transaction_status", None)
    name = getattr(status, "name", None) or str(status or "")
    if str(name).endswith("INERROR"):
        raise AuditError("aborted_transaction")
    if str(name).endswith("INTRANS"):
        raise AuditError("transaction_already_open")


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


def _set_timeout(conn: Any, timeout: str) -> None:
    if not TIMEOUT_SHAPE.fullmatch(timeout):
        raise AuditError("invalid_statement_timeout")
    catalog_execute(conn, "SELECT set_config('statement_timeout', %s, true)", (timeout,))


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


_LOAD_SQL = """
        WITH ins AS (
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
          WHERE e.id > %s
          ORDER BY e.id
          LIMIT %s
          RETURNING evidence_id
        )
        SELECT
          (SELECT COUNT(*) FROM ins) AS n,
          (SELECT evidence_id FROM ins ORDER BY evidence_id DESC LIMIT 1) AS m
        """


def _load_rows(
    conn: Any,
    *,
    statement_timeout: str,
    batch_size: int = DEFAULT_BATCH,
    deadline_mono: float | None = None,
) -> int:
    last_id: Any = KEYSET_START
    loaded = 0
    batch_no = 0
    started = time.monotonic()
    while True:
        if deadline_mono is not None:
            _deadline_guard(deadline_mono)
        _set_timeout(conn, statement_timeout)
        row = catalog_execute(conn, _LOAD_SQL, (last_id, batch_size)).fetchone()
        rec = dict(row) if not isinstance(row, dict) else row
        n = int(rec["n"] or 0)
        if n <= 0:
            break
        last_id = rec["m"]
        loaded += n
        batch_no += 1
        emit_progress(
            {
                "stage": "load",
                "batch": batch_no,
                "loaded": loaded,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        )
        if n < batch_size:
            break
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
    emit_progress(
        {
            "stage": "load_indexes",
            "loaded": loaded,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    )
    return loaded


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


def plan_cost_tree(plan: Any) -> list[dict[str, Any]]:
    """Sanitized EXPLAIN nodes: node type and costs only."""
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        rec = {
            "node": str(node.get("Node Type") or node.get("Strategy") or "unknown"),
            "startup_cost": node.get("Startup Cost"),
            "total_cost": node.get("Total Cost"),
            "plan_rows": node.get("Plan Rows"),
        }
        out.append(rec)
        for child in node.get("Plans") or []:
            walk(child)

    if isinstance(plan, list) and plan:
        walk(plan[0].get("Plan") if isinstance(plan[0], dict) else plan[0])
    elif isinstance(plan, dict):
        walk(plan.get("Plan") or plan)
    return out


def run_audit(
    conn: Any,
    *,
    stream_map: dict[str, str] | None = None,
    statement_timeout: str = DEFAULT_STATEMENT_TIMEOUT,
    batch_size: int = DEFAULT_BATCH,
    run_deadline_s: int = DEFAULT_RUN_DEADLINE_S,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline_mono = started + max(1, int(run_deadline_s))
    _begin_audit_transaction(conn)
    dbname = _require_not_memorybox(conn)
    _set_timeout(conn, statement_timeout)
    catalog_execute(
        conn,
        "SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
        (f"{max(1, int(run_deadline_s)) * 1000}ms",),
    )
    _create_temp(conn)
    emit_progress({"stage": "temp_ready", "elapsed_ms": int((time.monotonic() - started) * 1000)})
    _deadline_guard(deadline_mono)
    loaded = _load_rows(
        conn,
        statement_timeout=statement_timeout,
        batch_size=batch_size,
        deadline_mono=deadline_mono,
    )
    _deadline_guard(deadline_mono)
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
        "statement_timeout": statement_timeout,
        "run_deadline_s": int(run_deadline_s),
        "persistent_write_gate": True,
        "loaded_rows": int(loaded),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
    _deadline_guard(deadline_mono)
    assert_counts_only(report)
    emit_progress({"stage": "complete", "loaded": int(loaded), "elapsed_ms": report["elapsed_ms"]})
    return report


def failure_json(code: str) -> dict[str, Any]:
    return {"ok": False, "error": str(code)}


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

    conn = None
    try:
        conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)
        try:
            report = run_audit(conn, stream_map=stream_map)
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
    except AuditError:
        raise
    except KeyboardInterrupt as exc:
        raise AuditError("interrupted") from exc
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(json.dumps(failure_json(str(exc))), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(json.dumps(failure_json("audit_failed")), file=sys.stderr)
        raise SystemExit(1) from None
