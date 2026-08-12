"""Increment 3 acceptance demonstrations."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from memorybox.config import Settings, settings
from memorybox.ingest import rebuild_index, store
from memorybox.ingest.comms_calendar import ingest_ics
from memorybox.ingest.comms_email import ingest_mbox

FIXTURES = Path(__file__).resolve().parents[1] / "providers" / "_fixtures"
EMAIL_FIXTURE = FIXTURES / "i3_synthetic.mbox"
ICS_FIXTURE = FIXTURES / "i3_synthetic.ics"

EMAIL_REQUIRED_KEYS = {
    "message_id",
    "subject",
    "from",
    "to",
    "cc",
    "bcc",
    "sent_at",
    "body_text",
    "source_locator",
    "provenance",
    "content_hash",
}
CAL_REQUIRED_KEYS = {
    "event_uid",
    "title",
    "summary",
    "start",
    "end",
    "timezone",
    "location",
    "description",
    "organizer",
    "attendees",
    "recurrence",
    "source_locator",
    "provenance",
    "content_hash",
}


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    p = row["payload_json"]
    if isinstance(p, str):
        return json.loads(p)
    return dict(p)


def prove_increment_3(cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or settings
    checks: dict[str, Any] = {}
    problems: list[str] = []

    # --- Email synthetic ---
    email_before = EMAIL_FIXTURE.read_bytes()
    email_res = ingest_mbox(str(EMAIL_FIXTURE), label="i3 synthetic mbox")
    email_after = EMAIL_FIXTURE.read_bytes()
    checks["i3_a_email_ingest"] = bool(email_res.get("ok"))
    checks["i3_b_email_original_untouched"] = email_before == email_after
    if not email_res.get("ok"):
        problems.append(f"email ingest: {email_res.get('error')}")

    email_ids = email_res.get("evidence_ids") or []
    email_payload_ok = False
    if email_ids:
        from uuid import UUID

        row = store.get_evidence(UUID(email_ids[0]))
        assert row is not None
        payload = _payload(row)
        missing = EMAIL_REQUIRED_KEYS - set(payload.keys())
        email_payload_ok = (
            row["evidence_kind"] == "communication"
            and not missing
            and "SYNTHETIC_EMAIL_MARKER_GRANDPA_CHRISTMAS" in (payload.get("body_text") or "")
        )
        if missing:
            problems.append(f"email payload missing: {sorted(missing)}")
    checks["i3_a_email_payload_contract"] = email_payload_ok

    # --- Calendar synthetic ---
    ics_before = ICS_FIXTURE.read_bytes()
    cal_res = ingest_ics(str(ICS_FIXTURE), label="i3 synthetic ics")
    ics_after = ICS_FIXTURE.read_bytes()
    checks["i3_a2_calendar_ingest"] = bool(cal_res.get("ok"))
    checks["i3_b_calendar_original_untouched"] = ics_before == ics_after
    if not cal_res.get("ok"):
        problems.append(f"calendar ingest: {cal_res.get('error')}")

    cal_ids = cal_res.get("evidence_ids") or []
    cal_payload_ok = False
    if cal_ids:
        from uuid import UUID

        row = store.get_evidence(UUID(cal_ids[0]))
        assert row is not None
        payload = _payload(row)
        missing = CAL_REQUIRED_KEYS - set(payload.keys())
        cal_payload_ok = row["evidence_kind"] == "calendar_event" and not missing
        if missing:
            problems.append(f"calendar payload missing: {sorted(missing)}")
    checks["i3_a2_calendar_payload_contract"] = cal_payload_ok

    # --- Real smoke (where practical) ---
    smoke: dict[str, Any] = {"email": None, "calendar": None}
    smoke_limit = int(__import__("os").environ.get("MEMORYBOX_SMOKE_LIMIT", "5") or "5")
    if cfg.smoke_mbox_uri:
        smoke_email = ingest_mbox(
            cfg.smoke_mbox_uri, limit=smoke_limit, label="i3 real smoke mbox"
        )
        smoke["email"] = {
            "ok": smoke_email.get("ok"),
            "inserted": smoke_email.get("inserted"),
            "skipped": smoke_email.get("skipped"),
            "evidence_count": len(smoke_email.get("evidence_ids") or []),
            "evidence_ids": smoke_email.get("evidence_ids") or [],
            "limit": smoke_limit,
        }
        checks["i3_a_real_email_smoke"] = bool(smoke_email.get("ok"))
    else:
        checks["i3_a_real_email_smoke"] = "skipped_no_MEMORYBOX_SMOKE_MBOX_URI"
    if cfg.smoke_ics_uri:
        smoke_cal = ingest_ics(
            cfg.smoke_ics_uri, limit=smoke_limit, label="i3 real smoke ics"
        )
        smoke["calendar"] = {
            "ok": smoke_cal.get("ok"),
            "inserted": smoke_cal.get("inserted"),
            "skipped": smoke_cal.get("skipped"),
            "evidence_count": len(smoke_cal.get("evidence_ids") or []),
            "evidence_ids": smoke_cal.get("evidence_ids") or [],
            "limit": smoke_limit,
        }
        checks["i3_a2_real_calendar_smoke"] = bool(smoke_cal.get("ok"))
    else:
        checks["i3_a2_real_calendar_smoke"] = "skipped_no_MEMORYBOX_SMOKE_ICS_URI"

    # --- I3-C: no sqlite dual-write in ingest modules (static) ---
    ingest_root = Path(__file__).resolve().parent
    sqlite_hits = []
    for p in ingest_root.glob("*.py"):
        if p.name in ("acceptance.py",):
            continue
        t = p.read_text(encoding="utf-8")
        if re.search(r"^\s*import sqlite3|^\s*from sqlite3|sqlite3\.", t, re.M):
            sqlite_hits.append(p.name)
    checks["i3_c_no_sqlite_dual_write"] = not sqlite_hits
    if sqlite_hits:
        problems.append(f"sqlite references in ingest: {sqlite_hits}")

    # --- I3-D rebuild ---
    expected_ids = list(dict.fromkeys([*email_ids, *cal_ids]))
    cleared = rebuild_index.clear_collection(cfg)
    after_clear = rebuild_index.indexed_evidence_ids(cfg)
    rebuild = rebuild_index.rebuild_comms_index(cfg)
    after_rebuild = set(rebuild_index.indexed_evidence_ids(cfg))
    ids_restored = all(eid in after_rebuild for eid in expected_ids)
    retrieval = rebuild_index.fixed_retrieval_test(
        query_text="SYNTHETIC_EMAIL_MARKER_GRANDPA_CHRISTMAS Christmas Dinner",
        expected_evidence_ids=expected_ids[:1],  # at least the synthetic email
        cfg=cfg,
    )
    # Also expect picnic/christmas calendar in index set
    checks["i3_d_clear_empties_or_ready"] = cleared.get("ok") and len(after_clear) == 0
    checks["i3_d_rebuild_ok"] = bool(rebuild.get("ok"))
    checks["i3_d_evidence_ids_restored"] = ids_restored
    checks["i3_d_fixed_retrieval"] = bool(retrieval.get("ok"))
    if not rebuild.get("ok"):
        problems.append(f"rebuild: {rebuild.get('error')}")
    if not ids_restored:
        problems.append("rebuild missing expected evidence ids")
    if not retrieval.get("ok"):
        problems.append(f"retrieval missing: {retrieval.get('missing')}")

    # --- I3-E visible failure ---
    fail = ingest_mbox(str(FIXTURES / "does_not_exist.mbox"))
    checks["i3_e_missing_mbox_visible"] = (
        fail.get("ok") is False and bool(fail.get("error")) and bool(fail.get("job_id"))
    )

    # --- I3-G hardcode scan ---
    hardcoded = rebuild_index.assert_no_forbidden_hardcodes()
    checks["i3_g_no_forbidden_hardcodes"] = not hardcoded
    if hardcoded:
        problems.append(f"hardcodes: {hardcoded}")

    # --- I3-F runnable ---
    from memorybox.app import health

    h = health()
    checks["i3_f_health_ok"] = bool(h.get("ok"))

    # smoke skips don't fail acceptance
    required = [
        k
        for k, v in checks.items()
        if not (isinstance(v, str) and v.startswith("skipped_"))
    ]
    ok = all(checks[k] is True for k in required) and not problems
    return {
        "ok": ok,
        "increment": 3,
        "checks": checks,
        "problems": problems,
        "synthetic": {
            "email_evidence_ids": email_ids,
            "calendar_evidence_ids": cal_ids,
            "rebuild_indexed": rebuild.get("indexed"),
            "retrieval_hit_count": len(retrieval.get("hit_ids") or []),
        },
        "real_smoke": smoke,
        "config": {
            "qdrant_collection": cfg.qdrant_collection,
            "qdrant_url_scheme": (
                "memory"
                if cfg.qdrant_url in (":memory:", "memory", "mem")
                else ("path" if cfg.qdrant_url.startswith("path:") else "network")
            ),
            "allow_dev_defaults": cfg.allow_dev_defaults,
            "smoke_mbox_configured": bool(cfg.smoke_mbox_uri),
            "smoke_ics_configured": bool(cfg.smoke_ics_uri),
        },
    }
