"""I14 migration 035 FlightSim deploy validation. No seed, ingest, or apply on import.

Read-only helpers used by scripts/ops/Deploy-I14Migration035.ps1 and unit tests.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.request import Request

REQUIRED_PRIOR_SHA = "743c76712cb286ccdae3ad1108fb260dbd04770d"
REQUIRED_SHA = "4c13f70aae0d18f217eec4dcf43a98e6b964b14d"
MIGRATION_FILENAME = "035_p2_i14_communications_lineage.sql"
COMMS_TABLES = (
    "comms_logical_sources",
    "comms_source_memberships",
    "comms_extract_instances",
    "comms_source_checkpoint",
    "comms_record_identities",
    "comms_record_identity_aliases",
)
ROLLBACK_DROP_ORDER = (
    "comms_record_identity_aliases",
    "comms_record_identities",
    "comms_source_checkpoint",
    "comms_extract_instances",
    "comms_source_memberships",
    "comms_logical_sources",
)
EXPECTED_VERSIONS = tuple(f"{i:03d}" for i in range(1, 35))
FLIGHTSIM_LEDGER_FILENAMES = {
    "009": "009_person_fact_residence.sql",
    "025": "025_trusted_retrieval_identity.sql",
    "026": "026_backfill_email_retrieval_trust.sql",
    "027": "027_demote_untrusted_email_status.sql",
    "028": "028_communication_rfc_ids.sql",
    "029": "029_communication_rfc_ids_length.sql",
    "030": "030_p2_i13_scope_admission.sql",
    "031": "031_p2_i13_transcript_annotations.sql",
    "032": "032_p2_i13_voice_pilot.sql",
    "033": "033_p2_i13_interactive_learn.sql",
    "034": "034_historian_capture_hc2_tick.sql",
}
HC_PROVIDER_KEY = "namecheap_privateemail_imap_smtp"
HC_PROVIDER_LABEL = "Namecheap Private Email"
FORBIDDEN_SCHEDULE_STATUS = frozenset({"Error", "Disabled", "Not configured"})
EXPECTED_INDEXES = (
    "idx_comms_logical_sources_kind",
    "idx_comms_source_memberships_logical",
    "idx_comms_extract_instances_source",
    "idx_comms_extract_instances_logical",
    "idx_comms_record_identities_logical",
    "idx_comms_record_identity_aliases_canonical",
)
CHECK_NEEDLES = (
    "logical_key ~",
    "source_kind IN",
    "fingerprint ~",
    "landing_alias ~",
    "validation_status IN",
    "ingest_status IN",
    "identity_method IN",
)


class DeployValidationError(RuntimeError):
    """Hard-stop for 035 deploy validation."""


def compact_space(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def validate_ledger_preflight(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Require ordered 001-034, 035 absent, and FlightSim 009 / 025-029 filenames."""
    ledger = [(str(r["version"]), str(r["filename"])) for r in rows]
    versions = [v for v, _ in ledger]
    by_version = {v: f for v, f in ledger}
    problems: list[str] = []
    if "035" in by_version:
        problems.append("035_present")
    if versions != list(EXPECTED_VERSIONS):
        problems.append("version_set_mismatch")
    for ver, name in FLIGHTSIM_LEDGER_FILENAMES.items():
        if by_version.get(ver) != name:
            problems.append(f"filename_mismatch_{ver}")
    if problems:
        raise DeployValidationError("preflight_ledger:" + ",".join(problems))
    return {
        "ok": True,
        "versions": versions,
        "filenames_009_025_029": {k: by_version[k] for k in ("009", "025", "026", "027", "028", "029")},
        "has_035": False,
    }


def pending_from_files(
    applied: dict[str, str],
    local_files: dict[str, str],
) -> dict[str, Any]:
    pending = [local_files[v] for v in sorted(local_files) if v not in applied]
    conflicts = [
        {"version": v, "runtime": applied[v], "release": local_files[v]}
        for v in sorted(applied)
        if v in local_files and local_files[v] != applied[v]
    ]
    replay_025_029 = [v for v in ("025", "026", "027", "028", "029") if v in local_files and v not in applied]
    return {
        "pending": pending,
        "conflicts": conflicts,
        "replay_025_029": replay_025_029,
    }


def assert_only_035_pending(report: dict[str, Any]) -> None:
    if report.get("pending") != [MIGRATION_FILENAME]:
        raise DeployValidationError("pending_not_only_035")
    if report.get("replay_025_029"):
        raise DeployValidationError("would_replay_025_029")
    conflict_versions = {c["version"] for c in report.get("conflicts") or []}
    if not {"009", "025"} <= conflict_versions:
        raise DeployValidationError("expected_009_025_filename_conflicts_missing")


def assert_migrate_applied(payload: dict[str, Any]) -> None:
    applied = list(payload.get("applied") or [])
    if len(applied) != 1 or applied[0] != MIGRATION_FILENAME:
        raise DeployValidationError("migrate_result_not_only_035")


def untracked_collisions(untracked: Iterable[str], incoming_paths: Iterable[str]) -> list[str]:
    incoming = {p.replace("\\", "/").lstrip("./") for p in incoming_paths}
    hits: list[str] = []
    for raw in untracked:
        path = raw.replace("\\", "/").lstrip("./")
        if path in incoming:
            hits.append(path)
    return sorted(hits)


def assert_health_ok(payload: dict[str, Any]) -> None:
    pending = list(payload.get("migrations", {}).get("pending") or [])
    if payload.get("ok") is not True or pending:
        raise DeployValidationError("health_not_ok_or_pending")


def sanitize_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok"),
        "increment": payload.get("increment"),
        "database_ok": (payload.get("database") or {}).get("ok"),
        "pending": list((payload.get("migrations") or {}).get("pending") or []),
        "applied_n": len((payload.get("migrations") or {}).get("applied") or []),
    }


def poll_health(
    url: str,
    *,
    timeout_sec: float = 60,
    interval_sec: float = 1,
    opener: Callable[[str], dict[str, Any]] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    fetch = opener or _http_json
    sleep = sleeper or time.sleep
    deadline = time.monotonic() + timeout_sec
    last_fail: dict[str, Any] = {"ok": False, "error": "not_started"}
    payload: dict[str, Any] | None = None
    while True:
        try:
            payload = fetch(url)
            assert_health_ok(payload)
            return {"ok": True, "health": sanitize_health(payload)}
        except Exception as exc:
            last_fail = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]}
            if payload is not None:
                last_fail["health"] = sanitize_health(payload)
        if time.monotonic() >= deadline:
            break
        sleep(interval_sec)
    raise DeployValidationError("health_poll_timeout:" + json.dumps(last_fail, sort_keys=True))


def assert_email_status(payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(payload.get("provider_key") or "")
    if payload.get("ok") is not True:
        raise DeployValidationError("hc_email_not_ok")
    if provider != HC_PROVIDER_KEY:
        raise DeployValidationError("hc_provider_not_namecheap")
    return {"ok": True, "provider_key": provider, "reason": payload.get("reason")}


def historian_recurring_services(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in payload.get("services") or []:
        kind = str(item.get("kind") or "")
        title = str(item.get("title") or "")
        ident = str(item.get("id") or "")
        if kind == "recurring_service" and (
            ident == "historian_capture_email" or "historian capture" in title.lower()
        ):
            out.append(item)
    return out


def assert_scheduled_services(payload: dict[str, Any]) -> dict[str, Any]:
    services = historian_recurring_services(payload)
    if len(services) != 1:
        raise DeployValidationError("hc_recurring_service_count")
    status = str(services[0].get("status") or "")
    if status in FORBIDDEN_SCHEDULE_STATUS:
        raise DeployValidationError("hc_schedule_status:" + status)
    return {
        "ok": True,
        "status": status,
        "delayed": status == "Delayed",
        "id": services[0].get("id"),
        "kind": services[0].get("kind"),
    }


def _norm_fk(defn: str) -> str:
    return compact_space(defn).lower()


def assert_035_contract(snapshot: dict[str, Any]) -> dict[str, Any]:
    tables = set(snapshot.get("tables") or [])
    missing = [t for t in COMMS_TABLES if t not in tables]
    if missing:
        raise DeployValidationError("missing_tables:" + ",".join(missing))
    rows = snapshot.get("row_counts") or {}
    nonempty = [t for t in COMMS_TABLES if int(rows.get(t, -1)) != 0]
    if nonempty:
        raise DeployValidationError("comms_tables_not_empty:" + ",".join(nonempty))
    pks = snapshot.get("primary_keys") or {}
    expected_pk = {
        "comms_logical_sources": ["id"],
        "comms_source_memberships": ["source_id"],
        "comms_extract_instances": ["id"],
        "comms_source_checkpoint": ["logical_source_id"],
        "comms_record_identities": ["id"],
        "comms_record_identity_aliases": ["id"],
    }
    for table, cols in expected_pk.items():
        if list(pks.get(table) or []) != cols:
            raise DeployValidationError(f"pk_mismatch_{table}")
    fks = [_norm_fk(x) for x in snapshot.get("foreign_keys") or []]
    required_fks = (
        "foreignkey(source_id)referencessources(id)ondeleterestrict",
        "foreignkey(logical_source_id)referencescomms_logical_sources(id)ondeleterestrict",
        "foreignkey(source_id,logical_source_id)referencescomms_source_memberships(source_id,logical_source_id)ondeleterestrict",
        "foreignkey(logical_source_id,current_extract_instance_id)referencescomms_extract_instances(logical_source_id,id)ondeleterestrict",
        "foreignkey(logical_source_id,first_extract_instance_id)referencescomms_extract_instances(logical_source_id,id)ondeleterestrict",
        "foreignkey(canonical_record_id,logical_source_id)referencescomms_record_identities(id,logical_source_id)ondeleterestrict",
        "foreignkey(evidence_id)referencesevidence(id)ondeleterestrict",
    )
    for needle in required_fks:
        if not any(needle in item for item in fks):
            raise DeployValidationError("missing_fk:" + needle)
    if any("ondeletesetnull" in item for item in fks):
        raise DeployValidationError("unexpected_on_delete_set_null")
    if str(snapshot.get("checkpoint_confdeltype") or "") != "r":
        raise DeployValidationError("checkpoint_fk_not_restrict")
    unique_blob = "\n".join(compact_space(str(u)).lower() for u in snapshot.get("uniques") or [])
    unique_needles = (
        "unique(source_kind,logical_key)",
        "unique(source_id,logical_source_id)",
        "unique(logical_source_id,fingerprint)",
        "unique(logical_source_id,id)",
        "unique(evidence_id)",
        "unique(id,logical_source_id)",
        "unique(logical_source_id,identity_method,record_key)",
    )
    for needle in unique_needles:
        if needle not in unique_blob:
            raise DeployValidationError("missing_unique:" + needle)
    extract_uniques = [
        compact_space(str(u)).lower()
        for t, u in snapshot.get("uniques_by_table") or []
        if t == "comms_extract_instances"
    ]
    if any(item == "unique(source_id)" for item in extract_uniques):
        raise DeployValidationError("extract_unique_source_id")
    indexes = snapshot.get("indexes") or {}
    for name in EXPECTED_INDEXES:
        if name not in indexes:
            raise DeployValidationError("missing_index:" + name)
    if indexes.get("idx_comms_extract_instances_source") is not False:
        raise DeployValidationError("source_id_index_must_be_nonunique")
    checks = "\n".join(str(c) for c in snapshot.get("checks") or []).lower()
    for needle in CHECK_NEEDLES:
        if needle.lower() not in checks:
            raise DeployValidationError("missing_check:" + needle)
    counts = snapshot.get("baseline_counts") or {}
    after = snapshot.get("after_counts") or {}
    if counts and after != counts:
        raise DeployValidationError("baseline_counts_changed")
    return {
        "ok": True,
        "tables": list(COMMS_TABLES),
        "empty": True,
        "checkpoint_delete": "RESTRICT",
        "source_membership": "pk_source_id",
        "extract_source_id_unique": False,
    }


def collect_schema_snapshot(conn: Any, *, baseline_counts: dict[str, int] | None = None) -> dict[str, Any]:
    def q(sql: str, params: tuple = ()) -> list[Any]:
        cur = conn.execute(sql, params)
        return list(cur.fetchall())

    tables = {
        r[0] if not isinstance(r, dict) else r["t"]
        for r in q(
            "SELECT tablename AS t FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'comms_%'"
        )
    }
    row_counts = {}
    for name in COMMS_TABLES:
        if name in tables:
            n = q(f"SELECT COUNT(*) AS n FROM {name}")[0]
            row_counts[name] = int(n[0] if not isinstance(n, dict) else n["n"])
    pks: dict[str, list[str]] = {}
    for row in q(
        """
        SELECT c.relname AS t, array_agg(a.attname ORDER BY x.n) AS cols
        FROM pg_constraint k
        JOIN pg_class c ON c.oid = k.conrelid
        JOIN LATERAL unnest(k.conkey) WITH ORDINALITY AS x(attnum, n) ON TRUE
        JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = x.attnum
        WHERE k.contype = 'p' AND c.relname LIKE 'comms_%'
        GROUP BY c.relname
        """
    ):
        if isinstance(row, dict):
            pks[row["t"]] = list(row["cols"])
        else:
            pks[row[0]] = list(row[1])
    fks = []
    uniques = []
    uniques_by_table = []
    checks = []
    for row in q(
        """
        SELECT c.relname AS t, k.contype, pg_get_constraintdef(k.oid) AS d
        FROM pg_constraint k
        JOIN pg_class c ON c.oid = k.conrelid
        WHERE c.relname LIKE 'comms_%'
        """
    ):
        table, ctype, defn = (row["t"], row["contype"], row["d"]) if isinstance(row, dict) else row
        if ctype == "f":
            fks.append(defn)
        elif ctype == "u":
            uniques.append(defn)
            uniques_by_table.append((table, defn))
        elif ctype == "c":
            checks.append(defn)
    ck = q(
        """
        SELECT confdeltype AS d
        FROM pg_constraint
        WHERE conrelid = 'comms_source_checkpoint'::regclass
          AND contype = 'f'
          AND pg_get_constraintdef(oid) LIKE '%current_extract_instance_id%'
        """
    )
    ck_del = None
    if ck:
        item = ck[0]
        ck_del = item["d"] if isinstance(item, dict) else item[0]
    indexes = {}
    for row in q(
        """
        SELECT c.relname AS n, i.indisunique AS u
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        WHERE t.relname LIKE 'comms_%'
        """
    ):
        name, uniq = (row["n"], row["u"]) if isinstance(row, dict) else row
        indexes[name] = bool(uniq)
    after = {}
    for key, sql in (
        ("evidence", "SELECT COUNT(*) AS n FROM evidence"),
        ("sources", "SELECT COUNT(*) AS n FROM sources"),
        ("communication_rfc_ids", "SELECT COUNT(*) AS n FROM communication_rfc_ids"),
    ):
        item = q(sql)[0]
        after[key] = int(item["n"] if isinstance(item, dict) else item[0])
    return {
        "tables": sorted(tables),
        "row_counts": row_counts,
        "primary_keys": pks,
        "foreign_keys": fks,
        "uniques": uniques,
        "uniques_by_table": uniques_by_table,
        "checks": checks,
        "checkpoint_confdeltype": ck_del,
        "indexes": indexes,
        "after_counts": after,
        "baseline_counts": baseline_counts or after,
    }


def rollback_empty_035(conn: Any, *, file_absent: bool) -> dict[str, Any]:
    if not file_absent:
        raise DeployValidationError("035_file_still_on_disk")
    counts = {}
    for name in COMMS_TABLES:
        present = conn.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS e", (f"public.{name}",)
        ).fetchone()
        exists = bool(present["e"] if isinstance(present, dict) else present[0])
        if not exists:
            counts[name] = 0
            continue
        n = conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()
        counts[name] = int(n["n"] if isinstance(n, dict) else n[0])
    nonempty = [n for n, c in counts.items() if c]
    if nonempty:
        raise DeployValidationError("rollback_blocked_nonempty:" + ",".join(nonempty))
    for name in ROLLBACK_DROP_ORDER:
        conn.execute(f"DROP TABLE IF EXISTS {name}")
    conn.execute(
        "DELETE FROM schema_migrations WHERE version = %s AND filename = %s",
        ("035", MIGRATION_FILENAME),
    )
    return {"ok": True, "dropped": list(ROLLBACK_DROP_ORDER), "counts_before_drop": counts}


def _http_json(url: str) -> dict[str, Any]:
    req = Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: i14_migration_035 <command>", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "constants":
        return _emit(
            {
                "required_prior_sha": REQUIRED_PRIOR_SHA,
                "required_sha": REQUIRED_SHA,
                "migration_filename": MIGRATION_FILENAME,
                "comms_tables": list(COMMS_TABLES),
                "rollback_drop_order": list(ROLLBACK_DROP_ORDER),
            }
        )
    if cmd == "assert-applied":
        payload = json.loads(sys.stdin.read() or "{}")
        assert_migrate_applied(payload)
        return _emit({"ok": True})
    if cmd == "assert-health":
        payload = json.loads(sys.stdin.read() or "{}")
        assert_health_ok(payload)
        return _emit(sanitize_health(payload))
    if cmd == "assert-email":
        payload = json.loads(sys.stdin.read() or "{}")
        return _emit(assert_email_status(payload))
    if cmd == "assert-scheduled":
        payload = json.loads(sys.stdin.read() or "{}")
        return _emit(assert_scheduled_services(payload))
    if cmd == "poll-health":
        url = args[1] if len(args) > 1 else "http://127.0.0.1:8790/health"
        return _emit(poll_health(url))
    if cmd == "rollback-empty-035":
        import os

        import psycopg
        from psycopg.rows import dict_row

        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise DeployValidationError("MEMORYBOX_DATABASE_URL_missing")
        root = Path(__file__).resolve().parents[2]
        file_absent = not (root / "memorybox" / "migrations" / MIGRATION_FILENAME).is_file()
        with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
            return _emit(rollback_empty_035(conn, file_absent=file_absent))
    if cmd in {"preflight-ledger", "pending", "verify-schema", "baseline-counts"}:
        import os

        import psycopg
        from psycopg.rows import dict_row

        from memorybox.migrate import _migration_files

        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise DeployValidationError("MEMORYBOX_DATABASE_URL_missing")
        root = Path(__file__).resolve().parents[2]
        with psycopg.connect(
            dsn,
            autocommit=True,
            row_factory=dict_row,
            options="-c default_transaction_read_only=on -c statement_timeout=30000",
        ) as conn:
            if conn.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] != "on":
                raise DeployValidationError("not_read_only")
            if cmd == "preflight-ledger":
                rows = conn.execute(
                    "SELECT version, filename FROM schema_migrations ORDER BY version"
                ).fetchall()
                report = validate_ledger_preflight(rows)
                comms = {
                    n: conn.execute(
                        "SELECT to_regclass(%s) IS NOT NULL AS e", (f"public.{n}",)
                    ).fetchone()["e"]
                    for n in COMMS_TABLES
                }
                if any(comms.values()):
                    raise DeployValidationError("comms_tables_already_exist")
                counts = {
                    "evidence": conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],
                    "sources": conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"],
                    "communication_rfc_ids": conn.execute(
                        "SELECT COUNT(*) AS n FROM communication_rfc_ids"
                    ).fetchone()["n"],
                }
                report["comms_tables"] = comms
                report["counts"] = counts
                return _emit(report)
            if cmd == "baseline-counts":
                return _emit(
                    {
                        "evidence": conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],
                        "sources": conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"],
                        "communication_rfc_ids": conn.execute(
                            "SELECT COUNT(*) AS n FROM communication_rfc_ids"
                        ).fetchone()["n"],
                    }
                )
            if cmd == "pending":
                files = {
                    p.name.split("_", 1)[0]: p.name
                    for p in _migration_files(root / "memorybox" / "migrations")
                }
                applied = {
                    r["version"]: r["filename"]
                    for r in conn.execute("SELECT version, filename FROM schema_migrations")
                }
                report = pending_from_files(applied, files)
                assert_only_035_pending(report)
                return _emit(report)
            if cmd == "verify-schema":
                baseline = json.loads(sys.stdin.read() or "{}")
                snap = collect_schema_snapshot(conn, baseline_counts=baseline or None)
                result = assert_035_contract(snap)
                result["counts"] = snap["after_counts"]
                return _emit(result)
    print("unknown_command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeployValidationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from exc
