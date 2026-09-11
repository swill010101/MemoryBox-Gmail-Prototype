"""Owner-facing scheduled-service status for Admin Processing Jobs (HC-2)."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

from memorybox.historian_capture.cadence import (
    ADMIN_HISTORY_LIMIT,
    DELAYED_AFTER,
    _iso,
    _parse_iso,
    _utc_now,
    load_heartbeat,
    load_run_history,
    sanitize_failure_category,
    task_status_path,
)
from memorybox.historian_capture.email_adapter import HC_MAILBOX, email_adapter_status

HC_TASK_NAME = "MemoryBox Historian Capture Tick"
INTERVAL = timedelta(minutes=5)
SCHTASKS_TIMEOUT_SEC = 2
TASK_STATE_TTL = timedelta(seconds=60)
_TASK_STATE_MEM: dict[str, Any] = {}
ERROR_RESULTS = frozenset(
    {
        "imap_unavailable",
        "smtp_unavailable",
        "smtp_send_failed",
        "authentication_failed",
        "configuration_invalid",
        "missing_credentials",
        "missing_user_email",
        "unavailable",
        "poll_failed",
    }
)
PROVIDER_LABELS = {
    "namecheap_privateemail_imap_smtp": "Namecheap Private Email",
    "marvin_historian_gmail": "Gmail API",
    "fake_historian_email": "Test email provider",
}


def _task_ttl() -> timedelta:
    raw = (os.environ.get("MEMORYBOX_HC_TASK_STATUS_TTL_SECONDS") or "").strip()
    if raw:
        try:
            return timedelta(seconds=max(5, int(raw)))
        except ValueError:
            pass
    return TASK_STATE_TTL


def _structured_task_state(
    *, registered: bool, enabled: bool, source: str, checked_at: datetime | None = None
) -> dict[str, Any]:
    return {
        "registered": bool(registered),
        "enabled": bool(enabled) if registered else False,
        "source": source,
        "checked_at": _iso(checked_at or _utc_now()),
    }


def _read_task_status_file() -> dict[str, Any] | None:
    path = task_status_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or "registered" not in data:
        return None
    checked = _parse_iso(data.get("updated_at") or data.get("checked_at"))
    return {
        "registered": bool(data.get("registered")),
        "enabled": bool(data.get("enabled")),
        "source": "file",
        "checked_at": _iso(checked) if checked else None,
        "_checked": checked,
    }


def persist_task_status(*, registered: bool, enabled: bool, source: str = "cache") -> None:
    payload = {
        "registered": bool(registered),
        "enabled": bool(enabled) if registered else False,
        "task_name": HC_TASK_NAME,
        "updated_at": _iso(_utc_now()),
        "source": source,
    }
    path = task_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _query_schtasks() -> dict[str, Any] | None:
    """Bounded Windows truth check. Returns structured flags only — never stdout."""
    try:
        proc = subprocess.run(
            ["schtasks", "/Query", "/TN", HC_TASK_NAME, "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=SCHTASKS_TIMEOUT_SEC,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return _structured_task_state(registered=False, enabled=False, source="schtasks")
    status_line = ""
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            status_line = stripped.split(":", 1)[-1].strip().lower()
            break
    enabled = status_line not in {"disabled", ""}
    return _structured_task_state(registered=True, enabled=enabled, source="schtasks")


def scheduler_registration_state(*, now: datetime | None = None) -> dict[str, Any]:
    """Prefer current structured cache; schtasks is a 2s truth check when cache is stale.

    GET /admin/api/scheduled-services does not spawn schtasks on every browser request
    when tick_task_status.json or the in-process cache is newer than the TTL (60s).
    """
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    raw = (os.environ.get("MEMORYBOX_HC_TASK_STATE") or "").strip().lower()
    if raw in {"missing", "not_registered", "none", "unregistered"}:
        return _structured_task_state(registered=False, enabled=False, source="env", checked_at=now)
    if raw in {"disabled"}:
        return _structured_task_state(registered=True, enabled=False, source="env", checked_at=now)
    if raw in {"enabled", "active"}:
        return _structured_task_state(registered=True, enabled=True, source="env", checked_at=now)
    skip_query = (os.environ.get("MEMORYBOX_HC_SKIP_TASK_QUERY") or "").strip() in {
        "1",
        "true",
        "yes",
    }
    ttl = _task_ttl()
    mem_at = _parse_iso(_TASK_STATE_MEM.get("checked_at"))
    if mem_at is not None and (now - mem_at) <= ttl and "registered" in _TASK_STATE_MEM:
        return {
            "registered": bool(_TASK_STATE_MEM.get("registered")),
            "enabled": bool(_TASK_STATE_MEM.get("enabled")),
            "source": str(_TASK_STATE_MEM.get("source") or "memory"),
            "checked_at": _TASK_STATE_MEM.get("checked_at"),
        }
    file_state = _read_task_status_file()
    file_fresh = bool(
        file_state
        and file_state.get("_checked")
        and (now - file_state["_checked"]) <= ttl  # type: ignore[operator]
    )
    if file_fresh and file_state:
        out = {
            "registered": file_state["registered"],
            "enabled": file_state["enabled"],
            "source": "file",
            "checked_at": file_state.get("checked_at"),
        }
        _TASK_STATE_MEM.clear()
        _TASK_STATE_MEM.update(out)
        return out
    if skip_query:
        if file_state:
            return {
                "registered": file_state["registered"],
                "enabled": file_state["enabled"],
                "source": "file",
                "checked_at": file_state.get("checked_at"),
            }
        return _structured_task_state(registered=False, enabled=False, source="skipped", checked_at=now)
    probed = _query_schtasks() if os.name == "nt" else None
    if probed is not None:
        persist_task_status(
            registered=bool(probed.get("registered")),
            enabled=bool(probed.get("enabled")),
            source="schtasks",
        )
        _TASK_STATE_MEM.clear()
        _TASK_STATE_MEM.update(probed)
        return probed
    if file_state:
        return {
            "registered": file_state["registered"],
            "enabled": file_state["enabled"],
            "source": "file_stale",
            "checked_at": file_state.get("checked_at"),
        }
    return _structured_task_state(registered=False, enabled=False, source="unavailable", checked_at=now)


def _provider_label(status: dict[str, Any]) -> str:
    mode = (os.environ.get("MEMORYBOX_HC_EMAIL_PROVIDER") or "privateemail").strip().lower()
    if mode in {"privateemail", "auto", ""}:
        return "Namecheap Private Email"
    if mode == "gmail":
        return "Gmail API"
    if mode == "fake":
        return "Test email provider"
    key = str(status.get("provider_key") or "")
    return PROVIDER_LABELS.get(key, "Historian Capture email")


def _mailbox(status: dict[str, Any]) -> str:
    for key in ("capture_mailbox", "transport_email", "configured_email", "user_email"):
        value = str(status.get(key) or "").strip()
        if value and "@" in value and "example.invalid" not in value.lower():
            return value
    env_mail = (os.environ.get("MEMORYBOX_HC_USER_EMAIL") or "").strip()
    if env_mail and "@" in env_mail and "example.invalid" not in env_mail.lower():
        return env_mail
    return HC_MAILBOX


def derive_service_status(
    *,
    now: datetime,
    registered: bool,
    enabled: bool,
    heartbeat: dict[str, Any],
) -> str:
    """Founder precedence: Not configured → Disabled → Error → Delayed → Active."""
    if not registered:
        return "Not configured"
    if not enabled:
        return "Disabled"
    result = str(heartbeat.get("result") or "")
    if result in ERROR_RESULTS:
        return "Error"
    last_success = _parse_iso(heartbeat.get("last_successful_at"))
    if last_success is None and result in {"ok", "smtp_partial"}:
        last_success = _parse_iso(heartbeat.get("completed_at"))
    if last_success is not None and (now - last_success) <= DELAYED_AFTER:
        return "Active"
    return "Delayed"


def historian_capture_service(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    sched = scheduler_registration_state()
    hb = load_heartbeat()
    mail = email_adapter_status()
    status = derive_service_status(
        now=now,
        registered=bool(sched.get("registered")),
        enabled=bool(sched.get("enabled")),
        heartbeat=hb,
    )
    last_success = _parse_iso(hb.get("last_successful_at"))
    if last_success is None and hb.get("result") in {"ok", "smtp_partial"}:
        last_success = _parse_iso(hb.get("completed_at"))
    completed = _parse_iso(hb.get("completed_at"))
    next_run = None
    if sched.get("registered") and sched.get("enabled") and completed is not None:
        next_run = completed + INTERVAL
    last_error = None
    if str(hb.get("result") or "") in ERROR_RESULTS:
        last_error = sanitize_failure_category(hb.get("failure_category") or hb.get("result"))
    runs = []
    for raw in load_run_history(limit=ADMIN_HISTORY_LIMIT):
        item = dict(raw)
        item["emails_sent"] = int(raw.get("outbound_sent") or 0)
        runs.append(item)
    return {
        "id": "historian_capture_email",
        "kind": "recurring_service",
        "title": "Historian Capture email",
        "status": status,
        "schedule": "Every 5 minutes",
        "provider": _provider_label(mail),
        "mailbox": _mailbox(mail),
        "last_successful_run_at": _iso(last_success),
        "next_expected_run_at": _iso(next_run),
        "last_result": hb.get("result"),
        "replies_imported": int(hb.get("replies_imported") or 0),
        "emails_sent": int(hb.get("outbound_sent") or 0),
        "actions_deferred": int(hb.get("deferred") or 0),
        "last_error": last_error,
        "already_running": bool(hb.get("already_running") or hb.get("result") == "already_running"),
        "scheduler_registered": bool(sched.get("registered")),
        "scheduler_enabled": bool(sched.get("enabled")),
        "recent_runs": runs,
    }


def list_scheduled_services(*, now: datetime | None = None) -> dict[str, Any]:
    """Extensible collection; only Historian Capture is implemented now."""
    return {"ok": True, "services": [historian_capture_service(now=now)]}
