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
SCHEMA_REVIEW_SHA = "4c13f70aae0d18f217eec4dcf43a98e6b964b14d"
REQUIRED_SHA = SCHEMA_REVIEW_SHA
MIGRATION_RELPATH = "memorybox/migrations/035_p2_i14_communications_lineage.sql"
MIGRATION_FILENAME = "035_p2_i14_communications_lineage.sql"
OPS_PACK_PATHS = (
    "scripts/ops/Deploy-I14Migration035.ps1",
    "memorybox/ops/i14_migration_035.py",
    "memorybox/ops/__init__.py",
    "tests/test_i14_035_deploy.py",
    "docs/ops/I14_MIGRATION_035_FLIGHTSIM.md",
    MIGRATION_RELPATH,
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
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
EXPECTED_PKS = {
    "comms_logical_sources": ["id"],
    "comms_source_memberships": ["source_id"],
    "comms_extract_instances": ["id"],
    "comms_source_checkpoint": ["logical_source_id"],
    "comms_record_identities": ["id"],
    "comms_record_identity_aliases": ["id"],
}
EXPECTED_COLUMNS = {
    "comms_logical_sources": [
        "id",
        "logical_key",
        "source_kind",
        "label",
        "is_configured",
        "is_enabled",
        "timezone_name",
        "created_at",
        "updated_at",
    ],
    "comms_source_memberships": ["source_id", "logical_source_id", "created_at"],
    "comms_extract_instances": [
        "id",
        "logical_source_id",
        "source_id",
        "fingerprint",
        "landing_alias",
        "landing_basename",
        "byte_size",
        "source_modified_at",
        "validation_status",
        "ingest_status",
        "started_at",
        "completed_at",
        "failure_category",
        "created_at",
        "updated_at",
    ],
    "comms_source_checkpoint": [
        "logical_source_id",
        "last_success_at",
        "last_closed_source_date",
        "current_extract_instance_id",
        "last_failure_category",
        "created_at",
        "updated_at",
    ],
    "comms_record_identities": [
        "id",
        "logical_source_id",
        "evidence_id",
        "source_kind",
        "first_extract_instance_id",
        "created_at",
    ],
    "comms_record_identity_aliases": [
        "id",
        "canonical_record_id",
        "logical_source_id",
        "identity_method",
        "record_key",
        "native_id_class",
        "created_at",
    ],
}
EXPECTED_UNIQUES = (
    ("comms_logical_sources", ("source_kind", "logical_key")),
    ("comms_source_memberships", ("source_id", "logical_source_id")),
    ("comms_extract_instances", ("logical_source_id", "fingerprint")),
    ("comms_extract_instances", ("logical_source_id", "id")),
    ("comms_record_identities", ("evidence_id",)),
    ("comms_record_identities", ("id", "logical_source_id")),
    ("comms_record_identity_aliases", ("logical_source_id", "identity_method", "record_key")),
)
EXPECTED_FKS = (
    ("comms_source_memberships", ("source_id",), "sources", ("id",), "r"),
    ("comms_source_memberships", ("logical_source_id",), "comms_logical_sources", ("id",), "r"),
    ("comms_extract_instances", ("logical_source_id",), "comms_logical_sources", ("id",), "r"),
    ("comms_extract_instances", ("source_id",), "sources", ("id",), "r"),
    ("comms_extract_instances", ("source_id", "logical_source_id"), "comms_source_memberships", ("source_id", "logical_source_id"), "r"),
    ("comms_source_checkpoint", ("logical_source_id",), "comms_logical_sources", ("id",), "r"),
    ("comms_source_checkpoint", ("logical_source_id", "current_extract_instance_id"), "comms_extract_instances", ("logical_source_id", "id"), "r"),
    ("comms_record_identities", ("logical_source_id",), "comms_logical_sources", ("id",), "r"),
    ("comms_record_identities", ("evidence_id",), "evidence", ("id",), "r"),
    ("comms_record_identities", ("logical_source_id", "first_extract_instance_id"), "comms_extract_instances", ("logical_source_id", "id"), "r"),
    ("comms_record_identity_aliases", ("canonical_record_id", "logical_source_id"), "comms_record_identities", ("id", "logical_source_id"), "r"),
)
EXPECTED_CHECKS = (
    ("comms_logical_sources", "comms_logical_sources_logical_key_check", ("logical_key",)),
    ("comms_logical_sources", "comms_logical_sources_source_kind_check", ("source_kind",)),
    ("comms_logical_sources", "comms_logical_sources_label_check", ("label",)),
    ("comms_logical_sources", "comms_logical_sources_timezone_name_check", ("timezone_name",)),
    ("comms_extract_instances", "comms_extract_instances_fingerprint_check", ("fingerprint",)),
    ("comms_extract_instances", "comms_extract_instances_landing_alias_check", ("landing_alias",)),
    ("comms_extract_instances", "comms_extract_instances_landing_basename_check", ("landing_basename",)),
    ("comms_extract_instances", "comms_extract_instances_byte_size_check", ("byte_size",)),
    ("comms_extract_instances", "comms_extract_instances_validation_status_check", ("validation_status",)),
    ("comms_extract_instances", "comms_extract_instances_ingest_status_check", ("ingest_status",)),
    ("comms_extract_instances", "comms_extract_instances_failure_category_check", ("failure_category",)),
    ("comms_source_checkpoint", "comms_source_checkpoint_last_failure_category_check", ("last_failure_category",)),
    ("comms_record_identities", "comms_record_identities_source_kind_check", ("source_kind",)),
    ("comms_record_identity_aliases", "comms_record_identity_aliases_identity_method_check", ("identity_method",)),
    ("comms_record_identity_aliases", "comms_record_identity_aliases_record_key_check", ("record_key",)),
    ("comms_record_identity_aliases", "comms_record_identity_aliases_native_id_class_check", ("native_id_class",)),
)


class DeployValidationError(RuntimeError):
    """Hard-stop for 035 deploy validation."""


def require_full_sha(value: str, *, label: str) -> str:
    text = (value or "").strip().lower()
    if not _FULL_SHA.fullmatch(text):
        raise DeployValidationError(f"{label}_not_full_sha")
    return text


def assert_ops_pack_present(root: Path) -> None:
    missing = [rel for rel in OPS_PACK_PATHS if not (root / rel).is_file()]
    if missing:
        raise DeployValidationError("ops_pack_missing:" + ",".join(missing))


def assert_release_state(
    *,
    head: str,
    release_sha: str,
    origin_sha: str | None,
    schema_is_ancestor: bool,
    migration_head_oid: str,
    migration_schema_oid: str,
    allow_offline_origin: bool,
    files_present: Iterable[str],
) -> dict[str, Any]:
    rel = require_full_sha(release_sha, label="release")
    got = require_full_sha(head, label="head")
    if got != rel:
        raise DeployValidationError("head_ne_release_sha")
    if not schema_is_ancestor:
        raise DeployValidationError("not_descendant_of_schema_review")
    if not allow_offline_origin:
        if not origin_sha:
            raise DeployValidationError("origin_unresolved")
        if require_full_sha(origin_sha, label="origin") != rel:
            raise DeployValidationError("origin_ne_release_sha")
    if not migration_head_oid or migration_head_oid != migration_schema_oid:
        raise DeployValidationError("035_sql_differs_from_schema_review")
    present = {p.replace("\\", "/") for p in files_present}
    missing = [p for p in OPS_PACK_PATHS if p not in present]
    if missing:
        raise DeployValidationError("ops_pack_missing:" + ",".join(missing))
    return {
        "ok": True,
        "release_sha": rel,
        "schema_review_sha": SCHEMA_REVIEW_SHA,
        "035_blob": migration_head_oid,
        "offline_origin": bool(allow_offline_origin),
    }


def inspect_release_repo(
    repo: Path,
    release_sha: str,
    *,
    allow_offline_origin: bool,
    git_runner: Callable[..., str] | None = None,
) -> dict[str, Any]:
    run = git_runner or (lambda *args, **kwargs: _git(repo, *args, **kwargs))
    head = run("rev-parse", "HEAD")
    origin = None
    if not allow_offline_origin:
        origin = run("rev-parse", "origin/codex/p2-i14-communications")
    ancestor_rc = run("merge-base", "--is-ancestor", SCHEMA_REVIEW_SHA, "HEAD", _ok=(0, 1))
    schema_is_ancestor = ancestor_rc == "0"
    head_blob = run("rev-parse", f"HEAD:{MIGRATION_RELPATH}")
    schema_blob = run("rev-parse", f"{SCHEMA_REVIEW_SHA}:{MIGRATION_RELPATH}")
    present = [p for p in OPS_PACK_PATHS if (repo / p).is_file()]
    return assert_release_state(
        head=head,
        release_sha=release_sha,
        origin_sha=origin,
        schema_is_ancestor=schema_is_ancestor,
        migration_head_oid=head_blob,
        migration_schema_oid=schema_blob,
        allow_offline_origin=allow_offline_origin,
        files_present=present,
    )


def _git(repo: Path, *args: str, _ok: tuple[int, ...] = (0,)) -> str:
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in _ok:
        raise DeployValidationError("git_failed:" + " ".join(args))
    if args[:2] == ("merge-base", "--is-ancestor"):
        return str(proc.returncode)
    return (proc.stdout or "").strip()


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


# Same non-secret defaults as startmb.ps1 Load-MbEnv (FlightSim production boot).
STARTMB_NONSECRET_DEFAULTS = {
    "MEMORYBOX_DATABASE_URL": "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox",
    "MEMORYBOX_QDRANT_URL": "http://127.0.0.1:6333",
    "MEMORYBOX_QDRANT_COLLECTION": "memorybox_evidence",
    "MEMORYBOX_HOST": "0.0.0.0",
    "MEMORYBOX_PORT": "8790",
    "MEMORYBOX_P1_RUNTIME_HOST": "1",
    "MEMORYBOX_HC_EMAIL_PROVIDER": "privateemail",
    "MEMORYBOX_HC_USER_EMAIL": "memorybox@marvinbot.net",
    "MEMORYBOX_RECOGNITION_DRAIN": "1",
    "MEMORYBOX_PHOTO_PROVIDER": "immich",
    "MEMORYBOX_VIDEO_PROVIDER": "hvrt",
    "MEMORYBOX_VIDEO_WORKER_URL": "http://127.0.0.1:8791",
    "MEMORYBOX_VIDEO_WORKER_HOST": "127.0.0.1",
    "MEMORYBOX_VIDEO_WORKER_PORT": "8791",
    "MEMORYBOX_VIDEO_MEDIA_ROOT": r"P:\photos\home videos",
}
REQUIRED_RUNTIME_ENV = ("MEMORYBOX_DATABASE_URL", "MEMORYBOX_QDRANT_URL")
_USERINFO_RE = re.compile(r"(://)([^/@\s]+):([^/@\s]+)@")
_SECRET_KEY_RE = re.compile(r"(PASSWORD|TOKEN|SECRET|CREDENTIAL|APP_PASSWORD)", re.I)


def apply_startmb_nonsecret_defaults(env: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    out = dict(env)
    sources: dict[str, str] = {}
    for key, value in STARTMB_NONSECRET_DEFAULTS.items():
        current = (out.get(key) or "").strip()
        if current:
            sources[key] = "process_or_dotenv"
        else:
            out[key] = value
            sources[key] = "startmb.ps1 Load-MbEnv default"
    return out, sources


def sanitize_endpoint(url: str) -> str:
    cleaned = _USERINFO_RE.sub(r"\1", (url or "").strip())
    if "://" not in cleaned:
        return "set" if cleaned else "missing"
    rest = cleaned.split("://", 1)[1]
    hostport = rest.split("/", 1)[0]
    scheme = cleaned.split("://", 1)[0]
    return f"{scheme}://{hostport}"


def redact_process_text(text: str) -> str:
    return _USERINFO_RE.sub(r"\1***:***@", text or "")[:800]


def assert_runtime_env(env: dict[str, str]) -> dict[str, Any]:
    missing = [name for name in REQUIRED_RUNTIME_ENV if not (env.get(name) or "").strip()]
    if missing:
        raise DeployValidationError("runtime_env_missing:" + ",".join(missing))
    settings: list[dict[str, str]] = []
    blob_parts: list[str] = []
    for name in REQUIRED_RUNTIME_ENV:
        identity = sanitize_endpoint(env[name])
        settings.append({"name": name, "endpoint": identity})
        blob_parts.append(identity)
    qsrc = "process_or_dotenv"
    qurl = (env.get("MEMORYBOX_QDRANT_URL") or "").strip()
    if qurl == STARTMB_NONSECRET_DEFAULTS["MEMORYBOX_QDRANT_URL"]:
        qsrc = "startmb.ps1 Load-MbEnv default"
    report = {
        "ok": True,
        "settings": settings,
        "qdrant_source": qsrc,
        "qdrant_endpoint": sanitize_endpoint(qurl),
    }
    dumped = json.dumps(report)
    if _SECRET_KEY_RE.search(dumped):
        raise DeployValidationError("runtime_env_report_leaked_secret_name")
    for part in blob_parts:
        if "@" in (env.get("MEMORYBOX_DATABASE_URL") or "") and ":" in (env.get("MEMORYBOX_DATABASE_URL") or ""):
            userinfo = (env.get("MEMORYBOX_DATABASE_URL") or "").split("://", 1)[-1].split("@", 1)[0]
            if ":" in userinfo and userinfo.split(":", 1)[1] and userinfo.split(":", 1)[1] in dumped:
                raise DeployValidationError("runtime_env_report_leaked_secret")
    return report


def _is_config_failure(text: str) -> bool:
    lower = (text or "").lower()
    return (
        "memorybox_qdrant_url is required" in lower
        or "memorybox_database_url is required" in lower
        or "settings.from_env" in lower
        or "from_env()" in lower
    )


def interpret_migrate_process(exit_code: int, stdout: str, stderr: str) -> dict[str, Any]:
    raw = (stdout or "").strip()
    stderr_s = redact_process_text(stderr or "")
    stdout_s = redact_process_text(stdout or "")
    parsed: dict[str, Any] | None = None
    if raw:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict) and "applied" in loaded:
            parsed = loaded
    if parsed is not None:
        assert_migrate_applied(parsed)
        out = dict(parsed)
        out["process_exit_code"] = int(exit_code)
        if int(exit_code) != 0:
            out["exit_nonzero_after_applied"] = True
        return out
    combined = (stdout_s + "\n" + stderr_s).strip()
    detail = combined[:400] if combined else "(empty stdout/stderr)"
    if int(exit_code) != 0:
        if _is_config_failure(f"{stdout}\n{stderr}"):
            raise DeployValidationError("migrate_not_started:configuration:" + detail)
        raise DeployValidationError(
            "migrate_failed:sql_or_runtime:exit=" + str(exit_code) + ":stderr=" + detail
        )
    raise DeployValidationError("migrate_invalid_output:" + detail)


def untracked_collisions(untracked: Iterable[str], incoming_paths: Iterable[str]) -> list[str]:
    incoming = {p.replace("\\", "/").lstrip("./") for p in incoming_paths}
    hits: list[str] = []
    for raw in untracked:
        path = raw.replace("\\", "/").lstrip("./")
        if path in incoming:
            hits.append(path)
    return sorted(hits)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(x) for x in value]


def assert_health_ok(payload: dict[str, Any]) -> None:
    pending = _as_str_list((payload.get("migrations") or {}).get("pending"))
    if payload.get("ok") is not True or pending:
        raise DeployValidationError("health_not_ok_or_pending")


def _database_ok(payload: dict[str, Any]) -> bool:
    db = payload.get("database") or {}
    return db.get("status") == "ok" or db.get("ok") is True


def assert_health_pending_only_035(payload: dict[str, Any]) -> dict[str, Any]:
    """Pre-apply: serve reachable, DB up, pending is exactly 035.

    Top-level /health ok is false whenever pending is non-empty. That is expected
    after the release checkout puts 035 on disk and must not fail preflight.
    """
    mig = payload.get("migrations") or {}
    pending = _as_str_list(mig.get("pending"))
    problems: list[str] = []
    if not _database_ok(payload):
        problems.append("database_not_ok")
    if mig.get("status") != "ok":
        problems.append("migrations_status_not_ok")
    if pending != [MIGRATION_FILENAME]:
        problems.append("pending_not_only_035")
    if problems:
        raise DeployValidationError(
            "health_preflight:"
            + ",".join(problems)
            + ":"
            + json.dumps(sanitize_health(payload), sort_keys=True)
        )
    out = sanitize_health(payload)
    out["preflight_ok"] = True
    return out


def sanitize_health(payload: dict[str, Any]) -> dict[str, Any]:
    db = payload.get("database") or {}
    return {
        "ok": payload.get("ok"),
        "increment": payload.get("increment"),
        "database_ok": _database_ok(payload),
        "database_status": db.get("status"),
        "pending": _as_str_list((payload.get("migrations") or {}).get("pending")),
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


def catalog_execute(conn: Any, sql: str, params: tuple | list | None = None) -> Any:
    """Never pass an empty parameter tuple to SQL that contains '%'."""
    if "%" in sql and not params:
        raise DeployValidationError("unsafe_percent_sql")
    if not params:
        return conn.execute(sql)
    return conn.execute(sql, params)


def _as_cols(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(x) for x in value]


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
    for table, cols in EXPECTED_PKS.items():
        if list(pks.get(table) or []) != cols:
            raise DeployValidationError(f"pk_mismatch_{table}")
    columns = snapshot.get("columns") or {}
    for table, cols in EXPECTED_COLUMNS.items():
        if list(columns.get(table) or []) != cols:
            raise DeployValidationError(f"columns_mismatch_{table}")
    fks = list(snapshot.get("foreign_keys") or [])
    def _fk_key(item: dict[str, Any]) -> tuple:
        return (
            str(item.get("table") or ""),
            tuple(_as_cols(item.get("columns"))),
            str(item.get("foreign_table") or ""),
            tuple(_as_cols(item.get("foreign_columns"))),
            str(item.get("confdeltype") or ""),
        )
    have_fks = {_fk_key(x) for x in fks if isinstance(x, dict)}
    for table, cols, ft, fcols, deltype in EXPECTED_FKS:
        if (table, cols, ft, fcols, deltype) not in have_fks:
            raise DeployValidationError(f"missing_fk:{table}:{','.join(cols)}")
    if any(str(x.get("confdeltype") or "") == "n" for x in fks if isinstance(x, dict)):
        raise DeployValidationError("unexpected_on_delete_set_null")
    ck_del = str(snapshot.get("checkpoint_confdeltype") or "")
    if ck_del != "r":
        raise DeployValidationError("checkpoint_fk_not_restrict")
    uniques = [x for x in (snapshot.get("uniques") or []) if isinstance(x, dict)]
    have_u = {(str(u.get("table") or ""), tuple(_as_cols(u.get("columns")))) for u in uniques}
    for table, cols in EXPECTED_UNIQUES:
        if (table, cols) not in have_u:
            raise DeployValidationError(f"missing_unique:{table}:{','.join(cols)}")
    if any(
        str(u.get("table")) == "comms_extract_instances" and _as_cols(u.get("columns")) == ["source_id"]
        for u in uniques
    ):
        raise DeployValidationError("extract_unique_source_id")
    indexes = snapshot.get("indexes") or {}
    for name in EXPECTED_INDEXES:
        if name not in indexes:
            raise DeployValidationError("missing_index:" + name)
    if indexes.get("idx_comms_extract_instances_source") is not False:
        raise DeployValidationError("source_id_index_must_be_nonunique")
    checks = [x for x in (snapshot.get("checks") or []) if isinstance(x, dict)]
    by_name = {(str(c.get("table") or ""), str(c.get("name") or "")): c for c in checks}
    for table, name, cols in EXPECTED_CHECKS:
        got = by_name.get((table, name))
        if not got:
            raise DeployValidationError(f"missing_check:{name}")
        if str(got.get("contype") or "") != "c":
            raise DeployValidationError(f"check_contype:{name}")
        if got.get("convalidated") is not True:
            raise DeployValidationError(f"check_not_validated:{name}")
        if _as_cols(got.get("columns")) != list(cols):
            raise DeployValidationError(f"check_columns:{name}")
    # pg_get_constraintdef text is ignored even if present (IN vs = ANY).
    ledger = snapshot.get("ledger_035") or {}
    if str(ledger.get("version") or "") != "035" or str(ledger.get("filename") or "") != MIGRATION_FILENAME:
        raise DeployValidationError("ledger_035_row_mismatch")
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
        "ledger_035": MIGRATION_FILENAME,
        "checks_structural": True,
    }


def collect_schema_snapshot(conn: Any, *, baseline_counts: dict[str, int] | None = None) -> dict[str, Any]:
    names = list(COMMS_TABLES)

    def q(sql: str, params: tuple | list | None = None) -> list[Any]:
        cur = catalog_execute(conn, sql, params)
        return list(cur.fetchall())

    present = {
        r["t"] if isinstance(r, dict) else r[0]
        for r in q(
            "SELECT tablename AS t FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(%s)",
            (names,),
        )
    }
    columns: dict[str, list[str]] = {t: [] for t in COMMS_TABLES if t in present}
    for row in q(
        """
        SELECT table_name AS t, column_name AS c
          FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = ANY(%s)
         ORDER BY table_name, ordinal_position
        """,
        (names,),
    ):
        rec = dict(row) if not isinstance(row, dict) else row
        columns.setdefault(str(rec["t"]), []).append(str(rec["c"]))
    row_counts = {}
    for name in COMMS_TABLES:
        if name in present:
            n = q(f"SELECT COUNT(*) AS n FROM {name}")[0]
            row_counts[name] = int(n["n"] if isinstance(n, dict) else n[0])
    pks: dict[str, list[str]] = {}
    fks: list[dict[str, Any]] = []
    uniques: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for row in q(
        """
        SELECT
          cl.relname AS t,
          k.conname AS n,
          k.contype AS ctype,
          k.convalidated AS validated,
          k.confdeltype AS deltype,
          nf.relname AS ft,
          ARRAY(
            SELECT a.attname
              FROM unnest(k.conkey) WITH ORDINALITY AS x(attnum, ord)
              JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = x.attnum
             ORDER BY x.ord
          ) AS cols,
          ARRAY(
            SELECT a.attname
              FROM unnest(COALESCE(k.confkey, '{}'::int2[])) WITH ORDINALITY AS x(attnum, ord)
              JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = x.attnum
             ORDER BY x.ord
          ) AS fcols
        FROM pg_constraint k
        JOIN pg_class cl ON cl.oid = k.conrelid
        LEFT JOIN pg_class nf ON nf.oid = k.confrelid
        WHERE cl.relname = ANY(%s)
        """,
        (names,),
    ):
        rec = dict(row) if not isinstance(row, dict) else row
        table = str(rec["t"])
        ctype = str(rec["ctype"])
        cols = _as_cols(rec.get("cols"))
        if ctype == "p":
            pks[table] = cols
        elif ctype == "f":
            fks.append(
                {
                    "table": table,
                    "name": str(rec["n"]),
                    "columns": cols,
                    "foreign_table": str(rec.get("ft") or ""),
                    "foreign_columns": _as_cols(rec.get("fcols")),
                    "confdeltype": str(rec.get("deltype") or ""),
                }
            )
        elif ctype == "u":
            uniques.append({"table": table, "name": str(rec["n"]), "columns": cols})
        elif ctype == "c":
            checks.append(
                {
                    "table": table,
                    "name": str(rec["n"]),
                    "columns": cols,
                    "contype": "c",
                    "convalidated": bool(rec.get("validated")),
                }
            )
    ck_del = None
    for fk in fks:
        if (
            fk["table"] == "comms_source_checkpoint"
            and fk["columns"] == ["logical_source_id", "current_extract_instance_id"]
        ):
            ck_del = fk["confdeltype"]
            break
    indexes = {}
    for row in q(
        """
        SELECT c.relname AS n, i.indisunique AS u
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        WHERE t.relname = ANY(%s)
        """,
        (names,),
    ):
        rec = dict(row) if not isinstance(row, dict) else row
        indexes[str(rec["n"])] = bool(rec["u"])
    after = {}
    for key, sql in (
        ("evidence", "SELECT COUNT(*) AS n FROM evidence"),
        ("sources", "SELECT COUNT(*) AS n FROM sources"),
        ("communication_rfc_ids", "SELECT COUNT(*) AS n FROM communication_rfc_ids"),
    ):
        item = q(sql)[0]
        after[key] = int(item["n"] if isinstance(item, dict) else item[0])
    ledger_rows = q(
        "SELECT version, filename FROM schema_migrations WHERE version = %s",
        ("035",),
    )
    ledger_035 = {}
    if ledger_rows:
        item = ledger_rows[0]
        ledger_035 = {
            "version": str(item["version"] if isinstance(item, dict) else item[0]),
            "filename": str(item["filename"] if isinstance(item, dict) else item[1]),
        }
    return {
        "tables": sorted(present),
        "row_counts": row_counts,
        "columns": columns,
        "primary_keys": pks,
        "foreign_keys": fks,
        "uniques": uniques,
        "checks": checks,
        "checkpoint_confdeltype": ck_del,
        "indexes": indexes,
        "after_counts": after,
        "baseline_counts": baseline_counts or after,
        "ledger_035": ledger_035,
    }


def rollback_sql() -> str:
    checks = []
    for name in COMMS_TABLES:
        checks.append(
            f"""
IF to_regclass('public.{name}') IS NOT NULL THEN
  IF (SELECT COUNT(*) FROM {name}) <> 0 THEN
    RAISE EXCEPTION 'rollback_blocked_nonempty:{name}';
  END IF;
END IF;"""
        )
    drops = "\n".join(f"DROP TABLE IF EXISTS {n};" for n in ROLLBACK_DROP_ORDER)
    body = "\n".join(checks)
    return f"""BEGIN;
DO $mb035$
BEGIN
{body}
END
$mb035$;
{drops}
DELETE FROM schema_migrations
 WHERE version = '035'
   AND filename = '{MIGRATION_FILENAME}';
COMMIT;
"""


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
                "schema_review_sha": SCHEMA_REVIEW_SHA,
                "migration_filename": MIGRATION_FILENAME,
                "comms_tables": list(COMMS_TABLES),
                "rollback_drop_order": list(ROLLBACK_DROP_ORDER),
                "ops_pack_paths": list(OPS_PACK_PATHS),
            }
        )
    if cmd == "assert-ops-pack":
        root = Path(__file__).resolve().parents[2]
        assert_ops_pack_present(root)
        return _emit({"ok": True, "paths": list(OPS_PACK_PATHS)})
    if cmd == "assert-release":
        root = Path(__file__).resolve().parents[2]
        offline = "--offline" in args
        sha_args = [a for a in args[1:] if not a.startswith("-")]
        if not sha_args:
            raise DeployValidationError("release_sha_missing")
        return _emit(
            inspect_release_repo(root, sha_args[0], allow_offline_origin=offline)
        )
    if cmd == "print-rollback-sql":
        print(rollback_sql())
        return 0
    if cmd == "assert-applied":
        payload = json.loads(sys.stdin.read() or "{}")
        assert_migrate_applied(payload)
        return _emit({"ok": True})
    if cmd == "assert-runtime-env":
        import os

        return _emit(assert_runtime_env(dict(os.environ)))
    if cmd == "interpret-migrate":
        payload = json.loads(sys.stdin.read() or "{}")
        return _emit(
            interpret_migrate_process(
                int(payload.get("exit_code") or 1),
                str(payload.get("stdout") or ""),
                str(payload.get("stderr") or ""),
            )
        )
    if cmd == "assert-health":
        payload = json.loads(sys.stdin.read() or "{}")
        assert_health_ok(payload)
        return _emit(sanitize_health(payload))
    if cmd == "assert-health-preflight":
        payload = json.loads(sys.stdin.read() or "{}")
        return _emit(assert_health_pending_only_035(payload))
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
