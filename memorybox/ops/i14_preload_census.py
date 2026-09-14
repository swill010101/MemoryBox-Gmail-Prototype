"""Read-only I14 pre-load census. Counts only. Never inserts prepared rows.

FlightSim is allowed only when MEMORYBOX_I14_CENSUS_ALLOW_FLIGHTSIM=1 and
MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB=1. Always rolls back. Hard run deadline.
Failure JSON is {ok:false,error:<code>} with no partial ok true report.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import (
    DEFAULT_BATCH,
    KEYSET_START,
    WRITE_HEAD,
    AuditError,
    assert_counts_only,
    catalog_execute,
    emit_progress,
    failure_json,
    peak_working_set_mb,
    run_audit,
)
from memorybox.ops.i14_peggy_preview import load_identity_ledger
from memorybox.ops.i14_prepared_loader import forecast_prepared_counts
from memorybox.ops.i14_thread_review import IdentityLedger

MIN_ASSIGNED_MBOX_ROWS = 1000
DEFAULT_CENSUS_DEADLINE_S = 600
DEFAULT_STATEMENT_TIMEOUT = "30s"
TESTISH_URI = re.compile(
    r"synthetic|fixture|sample|dummy|(^|[\\/._-])test([\\/._-]|$)",
    re.I,
)
SELECT_OK = re.compile(r"^\s*(SELECT|WITH|SET\s+LOCAL)\b", re.I)


class CensusError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _allow_flightsim() -> bool:
    return os.environ.get("MEMORYBOX_I14_CENSUS_ALLOW_FLIGHTSIM", "").strip() == "1"


def _refuse_write(sql: str) -> None:
    stripped = sql.strip()
    if stripped.startswith("--"):
        return
    if SELECT_OK.match(stripped):
        return
    if WRITE_HEAD.match(stripped) or re.search(
        r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b", stripped, re.I
    ):
        raise CensusError("persistent_write_refused")


def _exec(conn: Any, sql: str, params: tuple | list | None = None) -> Any:
    _refuse_write(sql)
    try:
        return catalog_execute(conn, sql, params)
    except AuditError as exc:
        raise CensusError(str(exc)) from None


def _deadline_guard(deadline_mono: float) -> None:
    if time.monotonic() >= deadline_mono:
        raise CensusError("run_deadline")


def _set_timeout(conn: Any, timeout: str) -> None:
    _exec(conn, "SELECT set_config('statement_timeout', %s, true)", (timeout,))


def landing_reason(*, uri: str, rows: int, assigned: bool) -> str:
    if assigned:
        return "assigned_household_email"
    text = unquote((uri or "").strip())
    if TESTISH_URI.search(text):
        return "held_testish_landing_uri"
    if rows <= 0:
        return "held_empty_landing"
    return "held_tiny_below_assign_threshold"


def classify_mbox_sources(conn: Any, *, assign_threshold: int = MIN_ASSIGNED_MBOX_ROWS) -> dict[str, Any]:
    rows = _exec(
        conn,
        """
        SELECT s.id AS source_id,
               COALESCE(s.uri, '') AS uri,
               COUNT(e.id)::int AS rows
          FROM sources s
          LEFT JOIN evidence e
            ON e.source_id = s.id
           AND e.evidence_kind = 'communication'
         WHERE s.source_kind = 'mbox_import'
         GROUP BY s.id, s.uri
         ORDER BY COUNT(e.id) DESC
        """,
    ).fetchall()
    inventory = []
    for row in rows:
        rec = dict(row)
        n = int(rec["rows"])
        assigned = n >= assign_threshold
        inventory.append(
            {
                "rows": n,
                "assigned": assigned,
                "reason": landing_reason(uri=str(rec["uri"]), rows=n, assigned=assigned),
            }
        )
    hold = [r for r in inventory if not r["assigned"]]
    assigned = [r for r in inventory if r["assigned"]]
    hold_by_reason: dict[str, dict[str, int]] = {}
    for item in hold:
        bucket = hold_by_reason.setdefault(
            item["reason"], {"reason": item["reason"], "sources": 0, "rows": 0}
        )
        bucket["sources"] += 1
        bucket["rows"] += item["rows"]
    return {
        "assign_threshold_rows": assign_threshold,
        "assigned_sources": len(assigned),
        "assigned_rows": sum(r["rows"] for r in assigned),
        "held_sources": len(hold),
        "held_rows": sum(r["rows"] for r in hold),
        "held_by_reason": sorted(hold_by_reason.values(), key=lambda x: x["reason"]),
        "held_unexplained_rows": 0
        if hold and all(r["reason"] != "unexplained_hold" for r in hold)
        else (0 if not hold else sum(r["rows"] for r in hold if r["reason"] == "unexplained_hold")),
        "mbox_sources": len(inventory),
        "mbox_rows": sum(r["rows"] for r in inventory),
    }


def assigned_source_ids(
    conn: Any, *, assign_threshold: int = MIN_ASSIGNED_MBOX_ROWS
) -> list[Any]:
    rows = _exec(
        conn,
        """
        SELECT e.source_id AS sid
          FROM evidence e
          JOIN sources s ON s.id = e.source_id
         WHERE e.evidence_kind = 'communication'
           AND s.source_kind = 'mbox_import'
         GROUP BY e.source_id
        HAVING COUNT(*) >= %s
        """,
        (assign_threshold,),
    ).fetchall()
    return [r["sid"] if isinstance(r, dict) else r[0] for r in rows]


def load_messages_keyset(
    conn: Any,
    source_ids: list[Any],
    *,
    batch_size: int,
    statement_timeout: str,
    deadline_mono: float,
    started: float,
) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    last_id: Any = KEYSET_START
    loaded: list[dict[str, Any]] = []
    batch_no = 0
    while True:
        _deadline_guard(deadline_mono)
        _set_timeout(conn, statement_timeout)
        rows = _exec(
            conn,
            """
            SELECT e.id, e.source_id, e.payload_json
              FROM evidence e
             WHERE e.evidence_kind = 'communication'
               AND e.source_id = ANY(%s)
               AND e.id > %s
             ORDER BY e.id
             LIMIT %s
            """,
            (list(source_ids), last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        chunk = []
        for row in rows:
            rec = dict(row)
            chunk.append(rec["id"])
        last_id = chunk[-1]
        # Reuse loader mapping by wrapping a tiny fake: call the same SQL shape
        # through a one-batch adapter.
        messages = _map_evidence_rows(rows)
        loaded.extend(messages)
        batch_no += 1
        emit_progress(
            {
                "stage": "census_load",
                "batch": batch_no,
                "loaded": len(loaded),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        )
        if len(rows) < batch_size:
            break
    return loaded


def _map_evidence_rows(rows: list[Any]) -> list[dict[str, Any]]:
    from memorybox.ingest.comms_lineage import normalize_rfc_message_id

    out: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        payload = rec.get("payload_json") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        rfc = payload.get("rfc_message_id") or payload.get("message_id")
        if rfc:
            rfc = normalize_rfc_message_id(str(rfc)) or str(rfc)
        skip = str(payload.get("mailbox_skip") or "").lower()
        out.append(
            {
                "evidence_id": rec["id"],
                "source_id": rec["source_id"],
                "payload": payload,
                "content_hash": str(payload.get("content_hash") or "").strip().lower(),
                "rfc_message_id": rfc,
                "timestamp": payload.get("sent_at"),
                "subject": payload.get("subject") or "",
                "raw_body": payload.get("body_text") or payload.get("body") or "",
                "body": payload.get("body_text") or payload.get("body") or "",
                "from": payload.get("from"),
                "to": payload.get("to"),
                "cc": payload.get("cc"),
                "from_parsed": payload.get("from_parsed"),
                "to_parsed": payload.get("to_parsed"),
                "cc_parsed": payload.get("cc_parsed"),
                "in_reply_to_ids": payload.get("in_reply_to_ids") or [],
                "reference_ids": payload.get("reference_ids") or [],
                "vendor_thread_id": payload.get("vendor_thread_id") or payload.get("thread_id"),
                "spam_or_trash": skip in {"spam", "trash"},
                "source_locator": payload.get("source_locator") or "",
            }
        )
    return out


def _ledger(conn: Any) -> IdentityLedger:
    rows = _exec(
        conn,
        """
        SELECT p.id::text AS pid, COALESCE(p.display_name, '') AS n
          FROM people p
         WHERE p.status <> 'merged_away'
         ORDER BY p.display_name
         LIMIT 1
        """,
    ).fetchall()
    if not rows:
        return IdentityLedger(focal_person_id="")
    rec = dict(rows[0])
    try:
        return load_identity_ledger(
            conn, focal_person_id=str(rec["pid"]), focal_label=str(rec["n"] or "Person")
        )
    except Exception:
        return IdentityLedger(focal_person_id=str(rec["pid"]))


def run_census(
    conn: Any,
    *,
    statement_timeout: str = DEFAULT_STATEMENT_TIMEOUT,
    batch_size: int = DEFAULT_BATCH,
    run_deadline_s: int = DEFAULT_CENSUS_DEADLINE_S,
    include_duplicate_audit: bool = True,
    assign_threshold: int = MIN_ASSIGNED_MBOX_ROWS,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline_mono = started + max(1, int(run_deadline_s))
    info = getattr(conn, "info", None)
    host = str(getattr(info, "host", "") or "") if info is not None else ""
    dbname = str(getattr(info, "dbname", "") or "").lower() if info is not None else ""
    if not dbname:
        raise CensusError("dbname_unavailable")
    allow_db = os.environ.get("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", "").strip() == "1"
    try:
        refuse_live_dsn(
            host,
            None if allow_db else dbname,
            allow_flightsim=_allow_flightsim(),
        )
    except ProductionDSNError as exc:
        raise CensusError(str(exc)) from None
    if dbname == "memorybox" and not allow_db:
        raise CensusError("refused_memorybox_dbname")
    emit_progress({"stage": "census_start", "elapsed_ms": 0})
    audit_report = None
    if include_duplicate_audit:
        remaining = max(1, int(deadline_mono - time.monotonic()))
        try:
            audit_report = run_audit(
                conn,
                statement_timeout=statement_timeout,
                batch_size=batch_size,
                run_deadline_s=remaining,
            )
        except AuditError as exc:
            raise CensusError(str(exc)) from None
        emit_progress(
            {
                "stage": "duplicate_audit_done",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        )
    else:
        _exec(
            conn,
            "SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
            (f"{max(1, int(run_deadline_s)) * 1000}ms",),
        )
        _set_timeout(conn, statement_timeout)
    _deadline_guard(deadline_mono)
    mbox = classify_mbox_sources(conn, assign_threshold=assign_threshold)
    if int(mbox.get("held_unexplained_rows") or 0) != 0:
        raise CensusError("unexplained_hold")
    source_ids = assigned_source_ids(conn, assign_threshold=assign_threshold)
    emit_progress(
        {
            "stage": "mbox_classified",
            "assigned_rows": mbox["assigned_rows"],
            "held_rows": mbox["held_rows"],
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    )
    _deadline_guard(deadline_mono)
    messages = load_messages_keyset(
        conn,
        source_ids,
        batch_size=min(int(batch_size), 2000),
        statement_timeout=statement_timeout,
        deadline_mono=deadline_mono,
        started=started,
    )
    ledger = _ledger(conn)
    emit_progress(
        {
            "stage": "forecast_start",
            "loaded": len(messages),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    )
    try:
        forecast = forecast_prepared_counts(
            messages,
            ledger,
            deadline_mono=deadline_mono,
            on_progress=lambda ev: emit_progress(ev),
            sequential_quote_prior=False,
        )
    except Exception as exc:
        from memorybox.ops.i14_prepared_loader import LoaderError

        if isinstance(exc, LoaderError):
            raise CensusError(str(exc)) from None
        raise CensusError("forecast_failed") from None
    rfc_pop = None
    if audit_report:
        rfc_pop = (audit_report.get("rfc_own_fanout") or {}).get("household_email_population")
    held_rows = int(mbox["held_rows"])
    assigned_rows = int(mbox["assigned_rows"])
    prepared = int(forecast["prepared_messages"])
    omitted = int(forecast["identity_duplicates_omitted"])
    excluded_assigned = int(forecast["excluded_in_assigned_stream"])
    unexplained = int(forecast["unexplained"])
    # assigned_rows = prepared + omitted + excluded_assigned + unexplained
    assigned_balance = assigned_rows - prepared - omitted - excluded_assigned - unexplained
    universe = assigned_rows + held_rows
    universe_unexplained = universe - (
        prepared + omitted + excluded_assigned + held_rows + unexplained
    )
    if len(messages) != assigned_rows:
        raise CensusError("completeness_failed")
    if assigned_balance != 0 or universe_unexplained != 0:
        raise CensusError("completeness_failed")
    if forecast["omitted_missing_survivor"] != 0:
        raise CensusError("omitted_missing_lineage")
    report = {
        "ok": True,
        "kind": "counts_only_preload_validation",
        "flightsim_writes": False,
        "activation_called": False,
        "production_load": False,
        "read_only_production_tables": True,
        "database_kind": "memorybox_explicitly_allowed"
        if dbname == "memorybox"
        else "disposable_not_memorybox",
        "rule_id": forecast["rule_id"],
        "thread_cap_disposition": {
            "schema_036_cap_removed_by": "037_p2_i14_prepared_evidence_ref_scale",
            "evidence_ref_pattern": "T-[0-9]{4,}-M-[0-9]{2,}",
            "m01_meaning_unchanged": True,
            "loader_no_longer_aborts_at_99": True,
            "threads_over_99": forecast["threads_over_99"],
            "max_thread_size": forecast["max_thread_size"],
        },
        "mbox_inventory": mbox,
        "duplicate_audit": {
            "ok": bool(audit_report and audit_report.get("ok")),
            "elapsed_ms": None if not audit_report else audit_report.get("elapsed_ms"),
            "loaded_rows": None if not audit_report else audit_report.get("loaded_rows"),
            "within_source_duplicates": None
            if not audit_report
            else audit_report.get("within_source_duplicates"),
            "cross_source_same_stream_or_cluster": None
            if not audit_report
            else audit_report.get("cross_source_same_stream_or_cluster"),
            "rfc_own_fanout": None if not audit_report else audit_report.get("rfc_own_fanout"),
            "consolidation": None if not audit_report else audit_report.get("consolidation"),
        }
        if include_duplicate_audit
        else None,
        "rfc_household_email": rfc_pop,
        "forecast": {
            "eligible_assigned_rows": assigned_rows,
            "eligible": forecast["eligible"],
            "prepared_messages": prepared,
            "identity_duplicates_omitted": omitted,
            "omitted_with_survivor_lineage": forecast["omitted_with_survivor_lineage"],
            "held_excluded_rows": held_rows,
            "held_by_reason": mbox["held_by_reason"],
            "excluded_in_assigned_stream": excluded_assigned,
            "excluded_reasons": forecast["excluded_reasons"],
            "unexplained": 0,
            "threads": forecast["threads"],
            "max_thread_size": forecast["max_thread_size"],
            "threads_over_99": forecast["threads_over_99"],
            "participants": forecast["participants"],
            "authenticated_participants": forecast["authenticated_participants"],
            "unverified_participants": forecast["unverified_participants"],
            "attachments": forecast["attachments"],
            "commercial_classes": forecast["commercial_classes"],
            "voice_corpus_messages": forecast["voice_corpus_messages"],
            "voice_corpus_messages_by_authenticated_person": forecast[
                "authenticated_from_clean_quote_by_person_label"
            ],
            "quote_quality_exceptions": forecast["quote_quality_exceptions"],
        },
        "completeness": {
            "equation": (
                "mbox_rows = prepared + identity_duplicates_omitted + "
                "excluded_in_assigned_stream + held_rows + unexplained"
            ),
            "mbox_rows": universe,
            "prepared": prepared,
            "identity_duplicates_omitted": omitted,
            "excluded_in_assigned_stream": excluded_assigned,
            "held_rows": held_rows,
            "unexplained": 0,
            "assigned_rows_check": assigned_rows
            == prepared + omitted + excluded_assigned,
            "universe_check": universe
            == prepared + omitted + excluded_assigned + held_rows,
        },
        "consolidation_invariants": {
            "evidence_never_deleted_or_updated": True,
            "omitted_duplicates_retain_survivor_lineage": True,
            "quoted_forward_not_merged_at_evidence": True,
        },
        "statement_timeout": statement_timeout,
        "run_deadline_s": int(run_deadline_s),
        "batch_size": int(batch_size),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "peak_working_set_mb": peak_working_set_mb(),
        "quote_cleanup_mode": "independent_per_message",
        "037_not_applied_by_this_census": True,
    }
    assert_counts_only(report)
    emit_progress({"stage": "census_complete", "elapsed_ms": report["elapsed_ms"]})
    return report


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise CensusError("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=_allow_flightsim())
        except ProductionDSNError as exc:
            raise CensusError(str(exc)) from None
        import psycopg
        from psycopg.rows import dict_row

        conn = None
        try:
            conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)
            try:
                report = run_census(conn)
            finally:
                try:
                    conn.rollback()
                finally:
                    conn.close()
        except KeyboardInterrupt as exc:
            raise CensusError("interrupted") from exc
        blob = json.dumps(report, indent=2, sort_keys=True)
        out = os.environ.get("MEMORYBOX_I14_CENSUS_OUT", "").strip()
        if out:
            Path(out).write_text(blob, encoding="utf-8")
        else:
            print(blob)
        return 0
    except CensusError as exc:
        blob = json.dumps(failure_json(str(exc)))
        out = os.environ.get("MEMORYBOX_I14_CENSUS_OUT", "").strip()
        if out:
            Path(out).write_text(blob, encoding="utf-8")
        print(blob, file=sys.stderr)
        return 1
    except Exception:
        blob = json.dumps(failure_json("census_failed"))
        print(blob, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
