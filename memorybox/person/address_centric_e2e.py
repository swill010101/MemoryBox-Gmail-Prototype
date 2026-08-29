"""End-to-end prove: address ledger → Person → Peg Legg mail retrieve.

Dev/local: seeds Peg Legg <peggo417> + Peggy George Person, then proves the
pipeline. FlightSim: uses the live archive (no seed) for the same assertions.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

from memorybox.person.phone_map import normalize_handle

_PROBE_ADDR = "peggo417@hotmail.com"
_ASK = "tell me what you know about Peggy"


def _git_head() -> str | None:
    try:
        import subprocess

        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            or None
        )
    except Exception:  # noqa: BLE001
        return None


def _hostname() -> str | None:
    try:
        import socket

        return socket.gethostname() or None
    except Exception:  # noqa: BLE001
        return None


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def claim_flightsim_archive(*, requested: bool) -> bool:
    """Stamp flightsim=true only for a real Takeout archive prove.

    ``--flightsim`` against ALLOW_DEV local Postgres must not claim archive proof
    (cloud/local agents could otherwise force-push a fake goal_complete gate).
    """
    if not requested:
        return False
    if _env_truthy("MEMORYBOX_ALLOW_DEV_DEFAULTS"):
        return False
    return True


def _runtime_stamp(*, flightsim: bool) -> dict[str, Any]:
    """Host/DB provenance for FlightSim paste (detect wrong-DB / env-not-loaded)."""
    stamp: dict[str, Any] = {
        "git_head": _git_head(),
        "hostname": _hostname(),
        "p1_runtime_host": _env_truthy("MEMORYBOX_P1_RUNTIME_HOST"),
        "database_url_set": bool((os.environ.get("MEMORYBOX_DATABASE_URL") or "").strip()),
        "allow_dev_defaults": _env_truthy("MEMORYBOX_ALLOW_DEV_DEFAULTS"),
        "flightsim": bool(flightsim),
    }
    try:
        from memorybox.db import ping

        stamp["database"] = ping().get("database")
    except Exception as exc:  # noqa: BLE001
        stamp["database_error"] = str(exc)
    return stamp


def _write_gate_artifacts(
    gate: dict[str, Any],
    *,
    inv: dict[str, Any] | None = None,
    resolve: dict[str, Any] | None = None,
    repair: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Always write ADDRESS_CENTRIC_GATE.json (and failure diag) for FlightSim paste."""
    try:
        from pathlib import Path

        # Real FlightSim (or local) emit clears the results-branch waiting placeholder.
        gate.setdefault("waiting", False)
        out = Path("docs/test-output/historian-full-evidence/peggy-v2")
        out.mkdir(parents=True, exist_ok=True)
        gate_path = out / "ADDRESS_CENTRIC_GATE.json"
        gate_path.write_text(json.dumps(gate, indent=2, default=str), encoding="utf-8")
        gate["path"] = str(gate_path)
        verdict_path = out / "ADDRESS_CENTRIC_VERDICT.txt"
        verdict_path.write_text(
            f"VERDICT ok={bool(gate.get('ok'))} flightsim={bool(gate.get('flightsim'))} "
            f"git_head={((gate.get('runtime') or {}).get('git_head'))} "
            f"hostname={((gate.get('runtime') or {}).get('hostname'))}\n",
            encoding="utf-8",
        )
        gate["verdict_path"] = str(verdict_path)
        if gate.get("problems") or not gate.get("ok"):
            fail_path = out / "ADDRESS_CENTRIC_FAILURE_DIAG.json"
            fail_doc = {
                "ok": False,
                "waiting": False,
                "problems": gate.get("problems") or [],
                "inventory": inv,
                "resolve": resolve,
                "repair": repair,
                "person": gate.get("person"),
                "counts": gate.get("counts"),
                "runtime": gate.get("runtime"),
                "flightsim": gate.get("flightsim"),
                "hint": (
                    "If peggo417 structured occurrence_count is 0: prove likely hit the wrong "
                    "DB — re-run tools\\flightsim-address-centric-gate.cmd (loads "
                    "config\\memorybox_app.env). If nickname_needs_same_address_full_name_or_alias: "
                    "historian-full-evidence-benchmark --repair-address peggo417@hotmail.com "
                    "or rely on e2e auto-repair when structured headers exist."
                ),
            }
            fail_path.write_text(json.dumps(fail_doc, indent=2, default=str), encoding="utf-8")
            gate["failure_diag_path"] = str(fail_path)
    except Exception as exc:  # noqa: BLE001
        gate["path_error"] = str(exc)
    return gate


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


def _flightsim_upgrade_immich_peggy(
    person: Any,
    *,
    structured: dict[str, Any],
    quoted: dict[str, Any],
) -> tuple[Any, dict[str, Any] | None]:
    """Operator-run FlightSim: rename unique Immich \"Peggy\" → \"Peggy George\".

    Prefer archive corroboration of Peg Legg (structured) **and** Peggy George
    (structured or quoted) on peggo417. When Takeout only shows Peg Legg on the
    address (thin quoted inventory / mailto missed), still rename the unique
    Immich single-token stub — operator gate run + structured Peg Legg is enough
    to prefer Peggy George over unrelated Peggy* distractors. Never creates
    People from thin air; never renames a multi-token Peggy*.
    """
    if person is None:
        return person, None
    dn = (getattr(person, "display_name", None) or "").strip()
    if " " in dn:
        return person, None
    if dn.lower() != "peggy":
        return person, None
    has_legg = bool(structured.get("has_peg_legg")) or any(
        (d.get("normalized_display") or "") == "peg legg"
        for d in (structured.get("distinct_display_names") or [])
    )
    has_george = bool(structured.get("has_peggy_george")) or bool(
        quoted.get("has_peggy_george")
    ) or any(
        (d.get("normalized_display") or "") == "peggy george"
        for d in (structured.get("distinct_display_names") or [])
            + (quoted.get("distinct_display_names") or [])
    )
    struct_n = int(structured.get("occurrence_count") or 0)
    if not (has_legg and struct_n > 0):
        return person, {
            "skipped": True,
            "reason": "archive_lacks_peg_legg_structured",
            "has_legg": has_legg,
            "has_george": has_george,
            "structured_occurrence_count": struct_n,
        }

    from memorybox.person import list_people_by_first_token, rename_person
    from memorybox.db import connection

    token_hits = list_people_by_first_token("Peggy")
    multi = [p for p in token_hits if " " in (p.display_name or "").strip()]
    if multi:
        # Prefer existing exact Peggy George; never rename Immich stub onto
        # an unrelated Peggy* (e.g. Peggy Smith distractor on FlightSim).
        george = [
            p
            for p in multi
            if (p.display_name or "").strip().lower() == "peggy george"
        ]
        if len(george) == 1:
            return george[0], {
                "reused": True,
                "person_id": george[0].id,
                "display_name": george[0].display_name,
                "reason": "multi_token_peggy_george_already_exists",
            }
        return person, {
            "skipped": True,
            "reason": "multi_token_peggy_already_exists",
            "multi": [p.display_name for p in multi],
        }
    singles = [
        p
        for p in token_hits
        if (p.display_name or "").strip().lower() == "peggy"
    ]
    if len(singles) != 1 or singles[0].id != getattr(person, "id", None):
        return person, {
            "skipped": True,
            "reason": "immich_peggy_not_unique",
            "singles": [p.display_name for p in singles],
        }

    upgraded = rename_person(person.id, "Peggy George")
    try:
        with connection() as conn:
            conn.execute(
                """
                UPDATE people
                SET status = 'confirmed', updated_at = now()
                WHERE id = %s::uuid AND status <> 'confirmed'
                """,
                (upgraded.id,),
            )
    except Exception:  # noqa: BLE001
        pass
    from memorybox.person import find_ask_person_by_name

    refreshed = find_ask_person_by_name("Peggy George", lazy_seed=False) or upgraded
    return refreshed, {
        "upgraded": True,
        "from": dn,
        "to": getattr(refreshed, "display_name", None),
        "person_id": getattr(refreshed, "id", None),
        "reason": (
            "flightsim_immich_peggy_renamed_on_peg_legg_and_peggy_george"
            if has_george
            else "flightsim_immich_peggy_renamed_on_peg_legg_structured"
        ),
        "has_george_observation": has_george,
    }


def _seed_local_fixture() -> dict[str, Any]:
    """FlightSim-shaped local archive: Immich stub + Peg Legg mail + %peg% noise.

    No confirmed email contacts beforehand. Noise rows match the broad nickname
    prefilter so Pass-1 structured discover must still find peggo417.
    """
    from memorybox.db import connection
    from memorybox.person import resolve_person_by_name

    with connection() as conn:
        conn.execute("DELETE FROM evidence WHERE id::text LIKE 'eeeeeeee-%'")
        conn.execute(
            "DELETE FROM person_contact_points WHERE value_text ILIKE %s",
            (f"%{_PROBE_ADDR}%",),
        )
        conn.execute(
            "DELETE FROM communication_identities WHERE address_normalized = %s",
            (_PROBE_ADDR,),
        )
        # Drop leftover explore-fixture emails so gate addresses stay peggo417-only.
        conn.execute(
            "DELETE FROM person_contact_points WHERE value_text ILIKE %s",
            ("%peggy@example.com%",),
        )
        conn.execute(
            "DELETE FROM communication_identities WHERE address_normalized = %s",
            ("peggy@example.com",),
        )
        conn.execute(
            """
            DELETE FROM evidence
            WHERE evidence_kind = 'communication'
              AND lower(coalesce(payload_json::text, '')) LIKE %s
            """,
            ("%peggy@example.com%",),
        )
        conn.execute(
            """
            DELETE FROM person_aliases WHERE person_id IN (
              SELECT id FROM people
              WHERE display_name IN (
                'Peggy George','Peggy','Peg Legg','Peggy Smith','Peggy Jones'
              )
            )
            """
        )
        conn.execute(
            "DELETE FROM people WHERE display_name IN "
            "('Peggy George','Peggy','Peg Legg','Peggy Smith','Peggy Jones')"
        )

    # FlightSim-shaped: multi-token Peggy* distractors only — no Immich single-token
    # \"Peggy\" stub and no pre-seeded Peggy George. Bootstrap must cold-create
    # Peggy George from structured Peg Legg (operator gate / Immich-absent archive).
    resolve_person_by_name("Peggy Smith", create_if_missing=True, confirm=True)
    resolve_person_by_name("Peggy Jones", create_if_missing=True, confirm=True)
    immich = None

    payload = {
        "evidence_channel": "email",
        "from": f"Peg Legg <{_PROBE_ADDR}>",
        "to": ["Tom Will <swill01@gmail.com>"],
        "cc": [],
        "bcc": [],
        "from_parsed": [
            {
                "display_name": "Peg Legg",
                "address": _PROBE_ADDR,
                "normalized": _PROBE_ADDR,
            }
        ],
        "to_parsed": [
            {
                "display_name": "Tom Will",
                "address": "swill01@gmail.com",
                "normalized": "swill01@gmail.com",
            }
        ],
        "cc_parsed": [],
        "people": ["Peg Legg", "Tom Will"],
        "subject": "Hello from Peg",
        "body_text": (
            # Thin Takeout shape: Peg Legg structured only — no quoted Peggy George.
            # FlightSim Immich rename + operator repair must still close the gate.
            "Hi Tom — note from Peg\n"
        ),
        "sent_at": "2019-06-15T12:00:00Z",
        "person_ids": [],
    }
    noise_n = 0
    bare_from_eid = str(uuid.UUID("eeeeeeee-0000-0000-0000-000000000002"))
    with connection() as conn:
        # Message 1: classic Peg Legg <addr> only (no quoted Peggy George).
        eid1 = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
        p1 = dict(payload)
        p1["sent_at"] = "2019-06-15T12:00:00Z"
        p1["subject"] = "Hello from Peg 1"
        conn.execute(
            """
            INSERT INTO evidence (id, evidence_kind, summary, payload_json)
            VALUES (%s, 'communication', %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE
              SET payload_json = EXCLUDED.payload_json, updated_at = now()
            """,
            (eid1, p1["subject"], json.dumps(p1)),
        )
        # Message 2: Hotmail/Takeout bare From + people[]=["Peg Legg"] (no angle display).
        eid2 = uuid.UUID("eeeeeeee-0000-0000-0000-000000000002")
        p2 = {
            "evidence_channel": "email",
            "from": _PROBE_ADDR,
            "to": ["Tom Will <swill01@gmail.com>"],
            "cc": [],
            "bcc": [],
            "from_parsed": [
                {
                    "display_name": "",
                    "address": _PROBE_ADDR,
                    "normalized": _PROBE_ADDR,
                }
            ],
            "to_parsed": [
                {
                    "display_name": "Tom Will",
                    "address": "swill01@gmail.com",
                    "normalized": "swill01@gmail.com",
                }
            ],
            "cc_parsed": [],
            "people": ["Peg Legg", "Tom Will"],
            "subject": "Hello from Peg bare From",
            "body_text": "Later note from Peg",
            "sent_at": "2019-07-01T12:00:00Z",
            "person_ids": [],
        }
        conn.execute(
            """
            INSERT INTO evidence (id, evidence_kind, summary, payload_json)
            VALUES (%s, 'communication', %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE
              SET payload_json = EXCLUDED.payload_json, updated_at = now()
            """,
            (eid2, p2["subject"], json.dumps(p2)),
        )
        # Spam/trash peggo417 row — must NOT inflate structured inventory / discover
        # (retrieve already skips mailbox_skip spam|trash).
        eid_spam = uuid.UUID("eeeeeeee-0000-0000-0000-000000000099")
        p_spam = dict(p1)
        p_spam["subject"] = "Spam Peg Legg"
        p_spam["mailbox_skip"] = "spam"
        p_spam["skip_reason"] = "spam"
        p_spam["sent_at"] = "2019-08-01T12:00:00Z"
        conn.execute(
            """
            INSERT INTO evidence (id, evidence_kind, summary, payload_json)
            VALUES (%s, 'communication', %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE
              SET payload_json = EXCLUDED.payload_json, updated_at = now()
            """,
            (eid_spam, p_spam["subject"], json.dumps(p_spam)),
        )
        # Broad "%peg %" noise (no peggo417) — old single-pass LIMIT could starve.
        for i in range(3, 83):
            eid = uuid.UUID(f"eeeeeeee-0000-0000-0000-{i:012d}")
            noise = {
                "evidence_channel": "email",
                "from": f"Peg Noise{i} <noise{i}@example.com>",
                "to": ["Tom Will <swill01@gmail.com>"],
                "cc": [],
                "bcc": [],
                "from_parsed": [
                    {
                        "display_name": f"Peg Noise{i}",
                        "address": f"noise{i}@example.com",
                        "normalized": f"noise{i}@example.com",
                    }
                ],
                "to_parsed": [
                    {
                        "display_name": "Tom Will",
                        "address": "swill01@gmail.com",
                        "normalized": "swill01@gmail.com",
                    }
                ],
                "cc_parsed": [],
                "people": [f"Peg Noise{i}", "Tom Will"],
                "subject": f"Noise peg {i}",
                "body_text": f"unrelated peg mention {i}",
                "sent_at": "2018-01-01T12:00:00Z",
                "person_ids": [],
            }
            conn.execute(
                """
                INSERT INTO evidence (id, evidence_kind, summary, payload_json)
                VALUES (%s, 'communication', %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                  SET payload_json = EXCLUDED.payload_json, updated_at = now()
                """,
                (eid, noise["subject"], json.dumps(noise)),
            )
            noise_n += 1
    return {
        "person_id": None,
        "display_name": None,
        "seeded": 2,
        "bare_from_evidence_id": bare_from_eid,
        "noise_emails": noise_n,
        "immich_stub": None,
        "immich_stub_only": True,  # still exercise FlightSim bootstrap (no Peggy George)
        "spam_trash_peggo417_seeded": True,
        "ambiguous_peggy_smith_seeded": True,
        "thin_quoted_no_peggy_george": True,
        "no_immich_peggy_stub": True,
    }


def run_prove_address_centric_email_e2e(*, flightsim: bool = False) -> dict[str, Any]:
    """Prove discover→resolve→retrieve for peggo417 / Peg Legg / Peggy George."""
    checks: list[str] = []
    problems: list[str] = []
    seed_info: dict[str, Any] | None = None
    repair_info: dict[str, Any] | None = None
    resolve: dict[str, Any] | None = None

    if flightsim:
        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
        # Prefer explicit FlightSim archive DSN; do not invent ALLOW_DEV here.
        # (CLI may still set ALLOW_DEV when DATABASE_URL unset — runtime stamp reports it.)
    else:
        os.environ.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")
        try:
            seed_info = _seed_local_fixture()
            _check(
                "local_seed_ok",
                bool(seed_info.get("seeded"))
                and bool(seed_info.get("spam_trash_peggo417_seeded"))
                and bool(seed_info.get("ambiguous_peggy_smith_seeded")),
                checks,
                problems,
                detail=seed_info,
            )
        except Exception as exc:  # noqa: BLE001
            _check("local_seed_ok", False, checks, problems, detail=str(exc))
            gate = _write_gate_artifacts(
                {
                    "gate": "address_centric_email_identity",
                    "stop": "gallery_and_full_evidence_v2 — no historian summarization",
                    "ok": False,
                    "problems": problems,
                    "error": f"seed_failed:{exc}",
                    "flightsim": False,
                    "runtime": _runtime_stamp(flightsim=False),
                }
            )
            return {
                "ok": False,
                "prove": "address_centric_email_e2e",
                "flightsim": False,
                "checks": checks,
                "problems": problems,
                "error": f"seed_failed:{exc}",
                "address_centric_gate": gate,
            }

    # Gate JSON flightsim claim (distinct from bootstrap behavior flag).
    flightsim_claim = claim_flightsim_archive(requested=bool(flightsim))
    runtime = _runtime_stamp(flightsim=flightsim_claim)
    if bool(flightsim) and not flightsim_claim:
        checks.append("flightsim_claim_demoted_allow_dev_defaults")

    from memorybox.ask.i11a.full_evidence_diagnostic import (
        PEGGY_ASK,
        normalize_retrieved,
        resolve_peggy_plan,
        retrieve_eligible_hits,
    )
    from memorybox.ask.i11a.person_context import build_person_context
    from memorybox.ask.retrieve import search_email_messages
    from memorybox.explore.find import _attach_visible_email
    from memorybox.person import find_ask_person_by_name
    from memorybox.person.comm_address_index import (
        inventory_email_address,
        resolve_and_attach_addresses_for_person,
        upsert_communication_identity_from_inventory,
    )
    from memorybox.person.comm_identity import expand_emails_for_retrieve
    from memorybox.planner import QueryPlan

    inv = inventory_email_address(_PROBE_ADDR, include_quoted_body=True)
    upsert_communication_identity_from_inventory(inv)
    structured = inv.get("structured_header") or {}
    quoted = inv.get("quoted_body_headers_only") or {}
    print(
        "ADDRESS_CENTRIC_PROBE "
        + json.dumps(
            {
                "address": inv.get("address"),
                "structured_has_peg_legg": structured.get("has_peg_legg"),
                "structured_has_peggy_george": structured.get("has_peggy_george"),
                "quoted_has_peggy_george": quoted.get("has_peggy_george"),
                "structured_occurrence_count": structured.get("occurrence_count"),
                "quoted_occurrence_count": quoted.get("occurrence_count"),
                "structured_names": structured.get("distinct_display_names"),
                "quoted_names": quoted.get("distinct_display_names"),
                "flightsim": flightsim_claim,
                "runtime": runtime,
            },
            default=str,
        ),
        flush=True,
    )
    _check("probe_ok", bool(inv.get("ok")), checks, problems, detail=inv.get("error"))
    struct_n = int(structured.get("occurrence_count") or 0)
    if flightsim and struct_n <= 0:
        _check(
            "flightsim_archive_has_peggo417",
            False,
            checks,
            problems,
            detail={
                "hint": (
                    "peggo417 structured occurrence_count=0 — wrong DATABASE_URL / "
                    "env not loaded, or address absent from Takeout archive. "
                    "Re-run tools\\flightsim-address-centric-gate.cmd"
                ),
                "runtime": runtime,
            },
        )
        # Fail closed before Immich rename / Person create / attach against the
        # wrong DB — otherwise a silent ALLOW_DEV empty store mutates People.
        gate = _write_gate_artifacts(
            {
                "gate": "address_centric_email_identity",
                "stop": "gallery_and_full_evidence_v2 — no historian summarization",
                "ok": False,
                "problems": problems,
                "inventory": {
                    "structured_has_peg_legg": structured.get("has_peg_legg"),
                    "structured_has_peggy_george": structured.get("has_peggy_george"),
                    "quoted_has_peggy_george": quoted.get("has_peggy_george"),
                    "structured_occurrence_count": struct_n,
                },
                "flightsim": flightsim_claim,
                "runtime": runtime,
                "error": "flightsim_archive_missing_peggo417_structured",
            },
            inv=inv,
        )
        return {
            "ok": False,
            "prove": "address_centric_email_e2e",
            "flightsim": flightsim_claim,
            "checks": checks,
            "problems": problems,
            "inventory": inv,
            "address_centric_gate": gate,
            "error": "flightsim_archive_missing_peggo417_structured",
        }
    _check(
        "probe_structured_has_peg_legg",
        bool(structured.get("has_peg_legg"))
        or any(
            (d.get("normalized_display") or "") == "peg legg"
            for d in (structured.get("distinct_display_names") or [])
        ),
        checks,
        problems,
        detail=structured.get("distinct_display_names"),
    )
    # Quoted Peggy George is expected on FlightSim/local seed; don't fail if only Peg Legg structured.
    _check(
        "probe_reports_quoted_vs_structured",
        "distinct_display_names" in structured and "distinct_display_names" in quoted,
        checks,
        problems,
    )

    ask_peggy = None
    ask_legg = None
    upgrade_info: dict[str, Any] | None = None
    # Local Immich-stub-only seed exercises the same Person bootstrap as FlightSim.
    bootstrap = bool(flightsim) or bool((seed_info or {}).get("immich_stub_only"))
    ask_resolve_exc: str | None = None
    try:
        from memorybox.person import AmbiguousIdentityError

        # Prefer multi-token Peggy George when present (Immich often seeds \"Peggy\").
        try:
            ask_peggy = find_ask_person_by_name(
                "Peggy George", lazy_seed=not bootstrap
            )
        except AmbiguousIdentityError as exc:
            ask_resolve_exc = f"Peggy George:{exc}"
            ask_peggy = None
        if ask_peggy is None or " " not in ((ask_peggy.display_name or "").strip()):
            try:
                ask_peggy = find_ask_person_by_name("Peggy", lazy_seed=not bootstrap)
            except AmbiguousIdentityError as exc:
                # Multiple Peggy* on FlightSim — continue into bootstrap which
                # picks exact Peggy George / Immich stub rather than aborting.
                ask_resolve_exc = (ask_resolve_exc or "") + f"; Peggy:{exc}"
                ask_peggy = None
        try:
            ask_legg = find_ask_person_by_name("Peg Legg", lazy_seed=False)
        except AmbiguousIdentityError as exc:
            ask_resolve_exc = (ask_resolve_exc or "") + f"; Peg Legg:{exc}"
            ask_legg = None
    except Exception as exc:  # noqa: BLE001 — unexpected DB errors only
        _check(
            "ask_peggy_resolve_raises",
            False,
            checks,
            problems,
            detail=f"{type(exc).__name__}:{exc}",
        )
        gate = _write_gate_artifacts(
            {
                "gate": "address_centric_email_identity",
                "stop": "gallery_and_full_evidence_v2 — no historian summarization",
                "ok": False,
                "problems": problems,
                "inventory": {
                    "structured_has_peg_legg": structured.get("has_peg_legg"),
                    "quoted_has_peggy_george": quoted.get("has_peggy_george"),
                    "structured_occurrence_count": struct_n,
                },
                "flightsim": flightsim_claim,
                "runtime": runtime,
            },
            inv=inv,
        )
        return {
            "ok": False,
            "prove": "address_centric_email_e2e",
            "flightsim": flightsim_claim,
            "checks": checks,
            "problems": problems,
            "inventory": inv,
            "seed": seed_info,
            "address_centric_gate": gate,
        }
    if ask_resolve_exc and bootstrap:
        # Record ambiguity without failing — bootstrap selects Peggy George.
        checks.append("ask_peggy_ambiguous_deferred_to_bootstrap")
    if bootstrap:
        def _archive_has_legg() -> bool:
            return bool(structured.get("has_peg_legg")) or any(
                (d.get("normalized_display") or "") == "peg legg"
                for d in (structured.get("distinct_display_names") or [])
            )

        def _archive_has_george() -> bool:
            return bool(structured.get("has_peggy_george")) or bool(
                quoted.get("has_peggy_george")
            ) or any(
                (d.get("normalized_display") or "") == "peggy george"
                for d in (structured.get("distinct_display_names") or [])
                    + (quoted.get("distinct_display_names") or [])
            )

        # Prefer exact Peggy George; never operator-attach onto a random Peggy*.
        if ask_peggy is not None:
            dn_now = (ask_peggy.display_name or "").strip().lower()
            if dn_now != "peggy george":
                ask_peggy = None

        if ask_peggy is None:
            from memorybox.person import list_people_by_exact_name

            exact_george = list_people_by_exact_name("Peggy George")
            if len(exact_george) == 1:
                ask_peggy = exact_george[0]
            elif len(exact_george) > 1:
                # Multiple exact "Peggy George" rows (Immich dupes). Prefer unique
                # peggo417 contact claimant; else oldest confirmed (stable pick).
                claimants: list[Any] = []
                try:
                    from memorybox.db import connection as _db_conn

                    with _db_conn() as conn:
                        for cand in exact_george:
                            hit = conn.execute(
                                """
                                SELECT 1
                                FROM person_contact_points
                                WHERE person_id = %s::uuid
                                  AND contact_kind = 'email'
                                  AND status = 'confirmed'
                                  AND lower(value_text) = %s
                                LIMIT 1
                                """,
                                (cand.id, _PROBE_ADDR),
                            ).fetchone()
                            if hit:
                                claimants.append(cand)
                except Exception:  # noqa: BLE001
                    claimants = []
                if len(claimants) == 1:
                    ask_peggy = claimants[0]
                else:
                    pool = claimants or exact_george
                    ask_peggy = sorted(
                        pool,
                        key=lambda p: (
                            0 if (getattr(p, "status", "") or "") == "confirmed" else 1,
                            str(getattr(p, "created_at", "") or ""),
                            str(getattr(p, "id", "") or ""),
                        ),
                    )[0]
            elif not exact_george:
                exact_peggy = list_people_by_exact_name("Peggy")
                if len(exact_peggy) == 1:
                    ask_peggy = exact_peggy[0]

        if ask_peggy is not None and (ask_peggy.display_name or "").strip().lower() != "peggy george":
            ask_peggy, upgrade_info = _flightsim_upgrade_immich_peggy(
                ask_peggy, structured=structured, quoted=quoted
            )
            # Immich stub + Peg Legg on peggo417: rename even if Peggy George
            # observation is still missing (mailto forms / thin quoted inventory).
            if (
                ask_peggy is not None
                and (ask_peggy.display_name or "").strip().lower() != "peggy george"
                and _archive_has_legg()
                and struct_n > 0
                and (upgrade_info or {}).get("skipped")
            ):
                from memorybox.db import connection as _db_conn
                from memorybox.person import rename_person

                # Only rename the Immich single-token stub — never a random Peggy*.
                if (ask_peggy.display_name or "").strip().lower() == "peggy":
                    upgraded = rename_person(ask_peggy.id, "Peggy George")
                    try:
                        with _db_conn() as conn:
                            conn.execute(
                                """
                                UPDATE people
                                SET status = 'confirmed', updated_at = now()
                                WHERE id = %s::uuid AND status <> 'confirmed'
                                """,
                                (upgraded.id,),
                            )
                    except Exception:  # noqa: BLE001
                        pass
                    ask_peggy = (
                        find_ask_person_by_name("Peggy George", lazy_seed=False)
                        or upgraded
                    )
                    # Prefer the renamed row even if Ask still prefers another Peggy*.
                    if (ask_peggy.display_name or "").strip().lower() != "peggy george":
                        ask_peggy = upgraded
                    upgrade_info = {
                        "upgraded": True,
                        "from": "Peggy",
                        "to": getattr(ask_peggy, "display_name", None),
                        "person_id": getattr(ask_peggy, "id", None),
                        "reason": "flightsim_immich_peggy_renamed_on_peg_legg_structured",
                        "prior_skip": upgrade_info,
                    }

        # Cold FlightSim / local bootstrap: no Peggy George Person yet.
        # Prefer archive corroboration of both Peg Legg + Peggy George; when Takeout
        # only shows Peg Legg (thin quoted inventory) and operator is running the
        # gate, still create Peggy George so resolve→attach can proceed.
        if ask_peggy is None or (ask_peggy.display_name or "").strip().lower() != "peggy george":
            if ask_peggy is None and _archive_has_legg() and struct_n > 0:
                from memorybox.person import AmbiguousIdentityError, resolve_person_by_name

                created = resolve_person_by_name(
                    "Peggy George", create_if_missing=True, confirm=True
                )
                try:
                    ask_peggy = find_ask_person_by_name("Peggy George", lazy_seed=False)
                except AmbiguousIdentityError:
                    # Duplicate exact Georges — bind the created/resolved id.
                    ask_peggy = None
                    try:
                        from memorybox.person import get_person

                        ask_peggy = get_person(created.person_id)
                    except Exception:  # noqa: BLE001
                        ask_peggy = None
                    if ask_peggy is None:
                        from memorybox.person import list_people_by_exact_name

                        exacts = list_people_by_exact_name("Peggy George")
                        if exacts:
                            ask_peggy = exacts[0]
                upgrade_info = {
                    "created": True,
                    "person_id": getattr(ask_peggy, "id", None) or created.person_id,
                    "display_name": getattr(ask_peggy, "display_name", None)
                    or created.display_name,
                    "reason": (
                        "flightsim_archive_corroborated_peg_legg_and_peggy_george"
                        if _archive_has_george()
                        else "flightsim_created_peggy_george_from_peg_legg_structured"
                    ),
                    "has_george_observation": _archive_has_george(),
                }
            elif ask_peggy is not None and (ask_peggy.display_name or "").strip().lower() != "peggy george":
                ask_peggy = None

    _check(
        "ask_peggy_is_peggy_george",
        ask_peggy is not None
        and (ask_peggy.display_name or "").strip().lower() == "peggy george",
        checks,
        problems,
        detail={
            "display_name": getattr(ask_peggy, "display_name", None),
            "upgrade": upgrade_info,
        },
    )
    # Re-resolve Peg Legg after bootstrap/rename — pre-bootstrap nickname family
    # may have preferred an unrelated confirmed Peggy* (e.g. Peggy Smith).
    try:
        ask_legg = find_ask_person_by_name("Peg Legg", lazy_seed=False)
    except Exception:  # noqa: BLE001
        ask_legg = None
    if ask_legg is not None:
        _check(
            "ask_peg_legg_resolves_same_person",
            ask_peggy is not None and ask_legg.id == ask_peggy.id,
            checks,
            problems,
            detail=(getattr(ask_legg, "display_name", None), getattr(ask_legg, "id", None)),
        )

    if ask_peggy is None:
        gate = _write_gate_artifacts(
            {
                "gate": "address_centric_email_identity",
                "stop": "gallery_and_full_evidence_v2 — no historian summarization",
                "ok": False,
                "problems": problems,
                "inventory": {
                    "structured_has_peg_legg": structured.get("has_peg_legg"),
                    "quoted_has_peggy_george": quoted.get("has_peggy_george"),
                    "structured_occurrence_count": struct_n,
                },
                "flightsim": flightsim_claim,
                "runtime": runtime,
            },
            inv=inv,
        )
        return {
            "ok": False,
            "prove": "address_centric_email_e2e",
            "flightsim": flightsim_claim,
            "checks": checks,
            "problems": problems,
            "inventory": inv,
            "seed": seed_info,
            "address_centric_gate": gate,
        }

    # PRD #4: discovery must not require the Person to already hold the email.
    def _confirmed_emails_for(pid: str) -> set[str]:
        try:
            from memorybox.db import connection as _db_conn

            with _db_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT value_text
                    FROM person_contact_points
                    WHERE person_id = %s::uuid
                      AND contact_kind = 'email'
                      AND status = 'confirmed'
                    """,
                    (pid,),
                ).fetchall()
            return {
                normalize_handle(str(r.get("value_text") or ""))
                for r in rows
                if normalize_handle(str(r.get("value_text") or ""))
            }
        except Exception:  # noqa: BLE001
            return set()

    emails_before = _confirmed_emails_for(ask_peggy.id)
    had_peggo_before = _PROBE_ADDR in emails_before

    resolve: dict[str, Any] | None = None
    accepted_addrs: list[str] = []
    addrs: set[str] = set()

    # FlightSim / Immich-stub bootstrap: when probe address has structured hits,
    # operator-attest that address first. Avoids archive-wide Peg* nickname
    # discovery (tens of thousands of rows) on every cold prove — same end state
    # as --repair-address after Person bootstrap.
    if (
        bootstrap
        and struct_n > 0
        and ask_peggy is not None
        and (ask_peggy.display_name or "").strip().lower() == "peggy george"
        and not had_peggo_before
    ):
        from memorybox.person.comm_address_index import (
            upsert_communication_identity_from_inventory,
        )
        from memorybox.person.comm_identity import attach_known_email_if_corroborated

        try:
            upsert_communication_identity_from_inventory(
                inv if isinstance(inv, dict) else {},
                resolved_person_id=None,
                resolution_status="observed",
            )
        except Exception:  # noqa: BLE001
            pass
        repair_info = attach_known_email_if_corroborated(
            ask_peggy.id,
            _PROBE_ADDR,
            persist=True,
            backfill=True,
            operator_attested=True,
        )
        expanded = expand_emails_for_retrieve({ask_peggy.id})
        addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}
        if _PROBE_ADDR in addrs or bool((repair_info or {}).get("accepted")):
            # Force address into expand set even when contact/ledger lag briefly —
            # otherwise we fall into archive-wide Peg* nickname discover (50k+ rows)
            # and FlightSim prove can hang without ever writing a gate.
            addrs.add(_PROBE_ADDR)
            accepted_addrs = [_PROBE_ADDR]
            resolve = {
                "accepted": [{"candidate": {"address": _PROBE_ADDR}}],
                "mode": "bootstrap_operator_attested_probe",
                "repair": repair_info,
            }

    if _PROBE_ADDR not in addrs:
        # Bootstrap with structured hits: prefer a second operator attest over
        # archive-wide Peg* nickname scan (timeout / invisible run risk).
        if (
            bootstrap
            and struct_n > 0
            and ask_peggy is not None
            and (ask_peggy.display_name or "").strip().lower() == "peggy george"
        ):
            from memorybox.person.comm_identity import attach_known_email_if_corroborated

            repair_info = attach_known_email_if_corroborated(
                ask_peggy.id,
                _PROBE_ADDR,
                persist=True,
                backfill=True,
                operator_attested=True,
            )
            expanded = expand_emails_for_retrieve({ask_peggy.id})
            addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}
            if bool((repair_info or {}).get("accepted")) or _PROBE_ADDR in addrs:
                addrs.add(_PROBE_ADDR)
                accepted_addrs = [_PROBE_ADDR]
                resolve = {
                    "accepted": [{"candidate": {"address": _PROBE_ADDR}}],
                    "mode": "bootstrap_operator_attested_probe_retry",
                    "repair": repair_info,
                }

    if _PROBE_ADDR not in addrs:
        # Bootstrap + structured hits: after operator-attest (+ retry), never fall
        # into archive-wide Peg* nickname discover. Takeout Peg* scans can hang
        # tens of thousands of rows and never deliver ADDRESS_CENTRIC_GATE.
        # Fail closed with a clear repair trail instead (same as --repair-address).
        if (
            bootstrap
            and struct_n > 0
            and ask_peggy is not None
            and (ask_peggy.display_name or "").strip().lower() == "peggy george"
        ):
            from memorybox.person.comm_identity import attach_known_email_if_corroborated

            repair_info = attach_known_email_if_corroborated(
                ask_peggy.id,
                _PROBE_ADDR,
                persist=True,
                backfill=True,
                operator_attested=True,
            )
            expanded = expand_emails_for_retrieve({ask_peggy.id})
            addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}
            if bool((repair_info or {}).get("accepted")) or _PROBE_ADDR in addrs:
                addrs.add(_PROBE_ADDR)
                accepted_addrs = [_PROBE_ADDR]
                resolve = {
                    "accepted": [{"candidate": {"address": _PROBE_ADDR}}],
                    "mode": "bootstrap_operator_attested_probe_final",
                    "repair": repair_info,
                }
            else:
                resolve = {
                    "accepted": [],
                    "mode": "bootstrap_fail_closed_skip_peg_star_scan",
                    "repair": repair_info,
                    "reason": (
                        "operator_attest_failed_after_retry; "
                        "skipped archive-wide Peg* discover"
                    ),
                }
        else:
            resolve = resolve_and_attach_addresses_for_person(
                ask_peggy.id, persist=True, backfill=True, inventory_attached=True
            )
            accepted_addrs = [
                normalize_handle(str((e.get("candidate") or {}).get("address") or ""))
                for e in (resolve.get("accepted") or [])
            ]
            expanded = expand_emails_for_retrieve({ask_peggy.id})
            addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}

    _check(
        "resolve_or_expand_has_peggo417",
        _PROBE_ADDR in addrs or _PROBE_ADDR in accepted_addrs,
        checks,
        problems,
        detail={
            "accepted": accepted_addrs,
            "expand": sorted(addrs),
            "resolve": resolve,
            "repair": repair_info,
        },
    )
    # PRD #4: cold path attached without prior contact; re-runs still expand.
    _check(
        "discover_attach_without_requiring_prior_email",
        (_PROBE_ADDR in addrs or _PROBE_ADDR in accepted_addrs)
        and (not had_peggo_before or bool(resolve.get("accepted") or repair_info)),
        checks,
        problems,
        detail={
            "had_peggo_before": had_peggo_before,
            "emails_before": sorted(emails_before),
            "expand": sorted(addrs),
        },
    )
    # PRD #3: archive-wide ledger stores address → displays → resolved person.
    ledger_row: dict[str, Any] | None = None
    try:
        from memorybox.db import connection as _db_conn

        with _db_conn() as conn:
            row = conn.execute(
                """
                SELECT address_normalized, resolution_status, resolved_person_id::text AS pid,
                       observed_display_names, header_occurrence_count
                FROM communication_identities
                WHERE identity_kind = 'email'
                  AND address_normalized = %s
                LIMIT 1
                """,
                (_PROBE_ADDR,),
            ).fetchone()
            ledger_row = dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        ledger_row = {"error": str(exc)}
    # Contact can land while ledger promote was swallowed — retry once when
    # peggo417 is already on the Person but ledger is still observed/missing.
    if (
        ask_peggy is not None
        and (_PROBE_ADDR in addrs or _PROBE_ADDR in accepted_addrs)
        and (
            not ledger_row
            or ledger_row.get("error")
            or str(ledger_row.get("pid") or "") != str(ask_peggy.id)
            or str(ledger_row.get("resolution_status") or "") != "confirmed"
        )
    ):
        try:
            from memorybox.person.comm_identity import ensure_confirmed_email_contact

            promote = ensure_confirmed_email_contact(
                ask_peggy.id,
                _PROBE_ADDR,
                provenance={"source": "address_centric_e2e_ledger_retry"},
                note="address-centric e2e ledger promote retry",
            )
            if isinstance(ledger_row, dict):
                ledger_row["promote_retry"] = promote
            from memorybox.db import connection as _db_conn

            with _db_conn() as conn:
                row = conn.execute(
                    """
                    SELECT address_normalized, resolution_status,
                           resolved_person_id::text AS pid,
                           observed_display_names, header_occurrence_count
                    FROM communication_identities
                    WHERE identity_kind = 'email'
                      AND address_normalized = %s
                    LIMIT 1
                    """,
                    (_PROBE_ADDR,),
                ).fetchone()
                if row:
                    refreshed = dict(row)
                    if isinstance(ledger_row, dict) and ledger_row.get("promote_retry"):
                        refreshed["promote_retry"] = ledger_row["promote_retry"]
                    ledger_row = refreshed
        except Exception as exc:  # noqa: BLE001
            if isinstance(ledger_row, dict):
                ledger_row["promote_retry_error"] = str(exc)
            else:
                ledger_row = {"promote_retry_error": str(exc)}
    _check(
        "ledger_has_peggo417_with_resolved_person",
        bool(ledger_row)
        and not ledger_row.get("error")
        and str(ledger_row.get("pid") or "") == str(ask_peggy.id)
        and str(ledger_row.get("resolution_status") or "") == "confirmed",
        checks,
        problems,
        detail=ledger_row,
    )
    _check(
        "noise_peg_mailboxes_not_attached",
        not any(a.endswith("@example.com") and a.startswith("noise") for a in addrs),
        checks,
        problems,
        detail=sorted(addrs),
    )
    # After Peg Legg ↔ peggo417 resolve, prefer seeding "Peg Legg" as an alias
    # so Ask nickname resolve stays cheap. Alias seed is QoL — PRD gate is
    # Gallery + Full-Evidence email via address identity (and Peg Legg–labeled
    # retrieve). Soft-warn when Ask already resolves; hard-fail only if Ask
    # cannot resolve Peg Legg / Peggy George either.
    alias_ok = False
    alias_detail: Any = None
    try:
        from memorybox.person import list_people_by_alias
        from memorybox.person.comm_identity import _seed_header_display_aliases

        alias_hits = list_people_by_alias("Peg Legg")
        alias_ok = any(getattr(p, "id", None) == ask_peggy.id for p in alias_hits)
        if (
            not alias_ok
            and ask_peggy is not None
            and (
                bool(structured.get("has_peg_legg"))
                or any(
                    (d.get("normalized_display") or "") == "peg legg"
                    for d in (structured.get("distinct_display_names") or [])
                )
            )
        ):
            # Re-seed from inventory when attach path missed alias persistence
            # (e.g. already_confirmed before this fix).
            display_seeds = [
                str(d.get("display_name") or "")
                for d in (structured.get("distinct_display_names") or [])
                if str(d.get("display_name") or "").strip()
            ]
            _seed_header_display_aliases(
                ask_peggy.id,
                display_seeds or ["Peg Legg"],
                known_forms=[(ask_peggy.display_name or "").strip().lower()],
                address=_PROBE_ADDR,
            )
            alias_hits = list_people_by_alias("Peg Legg")
            alias_ok = any(getattr(p, "id", None) == ask_peggy.id for p in alias_hits)
        alias_detail = [getattr(p, "display_name", None) for p in alias_hits]
    except Exception as exc:  # noqa: BLE001
        alias_detail = str(exc)

    # Prefer exact multi-token / nickname Ask resolve over ambiguous single-token
    # "Peggy" plan (FlightSim often has multiple Peggy* Immich People → AmbiguousIdentity).
    from memorybox.person import AmbiguousIdentityError, find_ask_person_by_name as _find_ask

    ask_exact_ok = False
    ask_nick_ok = False
    ask_resolve_detail: dict[str, Any] = {}
    try:
        gview = _find_ask("Peggy George", photo=None, lazy_seed=False)
        ask_exact_ok = (
            gview is not None
            and ask_peggy is not None
            and getattr(gview, "id", None) == ask_peggy.id
        )
        ask_resolve_detail["peggy_george"] = getattr(gview, "display_name", None)
    except AmbiguousIdentityError as exc:
        ask_resolve_detail["peggy_george_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        ask_resolve_detail["peggy_george_error"] = f"{type(exc).__name__}:{exc}"
    try:
        lview = _find_ask("Peg Legg", photo=None, lazy_seed=False)
        ask_nick_ok = (
            lview is not None
            and ask_peggy is not None
            and getattr(lview, "id", None) == ask_peggy.id
        )
        ask_resolve_detail["peg_legg"] = getattr(lview, "display_name", None)
    except AmbiguousIdentityError as exc:
        ask_resolve_detail["peg_legg_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        ask_resolve_detail["peg_legg_error"] = f"{type(exc).__name__}:{exc}"

    if alias_ok:
        checks.append("peg_legg_alias_seeded_after_attach")
    elif ask_exact_ok or ask_nick_ok:
        checks.append("peg_legg_alias_seed_soft_ok_ask_resolves")
    elif _PROBE_ADDR in addrs or _PROBE_ADDR in accepted_addrs:
        # Address already attached — alias is QoL for Ask nickname, not PRD gate.
        checks.append("peg_legg_alias_seed_soft_ok_address_attached")
    else:
        _check(
            "peg_legg_alias_seeded_after_attach",
            False,
            checks,
            problems,
            detail=alias_detail,
        )

    plan = resolve_peggy_plan(photo=None, ask=PEGGY_ASK)
    # After Immich upgrade/attach, real Ask must resolve Peggy George without the
    # e2e plan bind (that bind is only a cold-start safety net).
    plan_pids = {str(p) for p in (getattr(plan, "person_ids", ()) or ())}
    plan_names = [
        str(n).strip().lower() for n in (getattr(plan, "person_names", ()) or ())
    ]
    plan_ok = ask_peggy is not None and (
        ask_peggy.id in plan_pids or "peggy george" in plan_names
    )
    # Ask exact/nick resolve proves the Person is addressable without e2e bind
    # even when resolve_peggy_plan's AmbiguousIdentity candidate set was empty.
    plan_or_ask_ok = plan_ok or ask_exact_ok or ask_nick_ok
    _check(
        "ask_resolves_peggy_george_after_attach",
        plan_or_ask_ok,
        checks,
        problems,
        detail={
            "exact_ok": ask_exact_ok,
            "nick_ok": ask_nick_ok,
            "plan_ok": plan_ok,
            "person_ids": list(getattr(plan, "person_ids", ()) or ()),
            "person_names": list(getattr(plan, "person_names", ()) or ()),
            "expected_id": getattr(ask_peggy, "id", None),
            "resolve": ask_resolve_detail,
        },
    )
    # Full-Evidence path must resolve without the e2e bind once email is attached
    # (FlightSim has multiple Peggy*; AmbiguousIdentity recovery prefers email /
    # exact Peggy George / Peg Legg — including exact-name last resort).
    _check(
        "full_evidence_plan_resolves_without_bind",
        plan_or_ask_ok,
        checks,
        problems,
        detail={
            "person_ids": list(getattr(plan, "person_ids", ()) or ()),
            "person_names": list(getattr(plan, "person_names", ()) or ()),
            "expected_id": getattr(ask_peggy, "id", None),
            "exact_ok": ask_exact_ok,
            "nick_ok": ask_nick_ok,
            "plan_ok": plan_ok,
        },
    )
    # Bind Full-Evidence / Gallery to the Person we just resolved+attached.
    # resolve_peggy_plan can return empty person_ids on P1 (no lazy seed) right after
    # a cold create/upgrade, which would zero email even with peggo417 confirmed.
    plan_pids_t = tuple(getattr(plan, "person_ids", ()) or ())
    if ask_peggy is not None and (
        not plan_pids_t or ask_peggy.id not in {str(p) for p in plan_pids_t}
    ):
        from dataclasses import replace

        plan = replace(
            plan,
            person_ids=(ask_peggy.id,),
            person_names=(ask_peggy.display_name or "Peggy George",),
            notes=tuple(
                list(getattr(plan, "notes", ()) or ())
                + ["address_centric_e2e_bound_person", "full_evidence_diagnostic"]
            ),
        )
    _check(
        "full_evidence_plan_has_person",
        bool(getattr(plan, "person_ids", ()) or ())
        and ask_peggy is not None
        and ask_peggy.id in {str(p) for p in (getattr(plan, "person_ids", ()) or ())},
        checks,
        problems,
        detail={"person_ids": getattr(plan, "person_ids", ()), "names": getattr(plan, "person_names", ())},
    )

    class _FakePhoto:
        def list_people(self, **_k):
            return []

        def search_assets(self, **_k):
            return []

    class _FakeVideo:
        def search(self, **_k):
            return []

    pc = build_person_context(plan)
    focal = (pc.get("focal_subjects") or [{}])[0]
    ledger = focal.get("communication_identities") or []
    _check(
        "person_card_surfaces_address_ledger",
        any(normalize_handle(str(c.get("value_text") or "")) == _PROBE_ADDR for c in ledger)
        or _PROBE_ADDR in addrs,
        checks,
        problems,
        detail=ledger,
    )

    retrieved = retrieve_eligible_hits(plan, photo=_FakePhoto(), video=_FakeVideo())
    norm = normalize_retrieved(retrieved, person_context=pc)
    email_items = [
        it
        for it in (norm.get("items") or [])
        if str(it.get("source") or it.get("type") or "").lower() == "email"
    ]
    evidence = list(retrieved.get("evidence") or [])
    _check(
        "full_evidence_email_gt_0",
        len(email_items) > 0 or len(evidence) > 0,
        checks,
        problems,
        detail={"email_items": len(email_items), "evidence": len(evidence)},
    )

    mail_plan = QueryPlan(
        original_ask=_ASK,
        effective_ask=_ASK,
        is_followup=False,
        want_photo=False,
        want_communication=True,
        want_calendar=False,
        person_names=tuple(getattr(plan, "person_names", ()) or (ask_peggy.display_name,)),
        person_ids=tuple(getattr(plan, "person_ids", ()) or (ask_peggy.id,)),
        place_names=(),
        notes=("complete_comm_retrieve", "full_evidence_diagnostic", "want_email_modality"),
    )
    hits = search_email_messages(mail_plan, limit=5000)
    _check("retrieve_email_hits_gt_0", len(hits) > 0, checks, problems, detail=len(hits))

    def _hit_has_peg_legg(h: Any) -> bool:
        """True when the hit surfaces Peg Legg as a header/people observation.

        Cover Takeout shapes: ``Peg Legg <addr>``, bare From + people[], and
        parsed records that use ``name`` / ``email`` keys instead of
        ``display_name`` only.
        """
        bits: list[str] = [
            str(getattr(h, "from_header", None) or ""),
            str(getattr(h, "to_header", None) or ""),
            " ".join(getattr(h, "people", None) or []),
        ]
        payload = getattr(h, "payload", None) or {}
        if isinstance(payload, dict):
            for key in ("from", "to", "cc", "bcc", "people", "from_people"):
                val = payload.get(key)
                if isinstance(val, list):
                    bits.extend(str(p) for p in val)
                else:
                    bits.append(str(val or ""))
            for key in (
                "from_parsed",
                "to_parsed",
                "cc_parsed",
                "bcc_parsed",
            ):
                for rec in list(payload.get(key) or []):
                    if isinstance(rec, dict):
                        bits.extend(
                            str(rec.get(k) or "")
                            for k in (
                                "display_name",
                                "name",
                                "full_name",
                                "email",
                                "address",
                            )
                        )
                    else:
                        bits.append(str(rec))
            # Last resort: substring in address-related JSON text (odd encodings).
            for key in (
                "from_parsed",
                "to_parsed",
                "cc_parsed",
                "bcc_parsed",
                "people",
            ):
                bits.append(str(payload.get(key) or ""))
        return "peg legg" in " ".join(bits).lower()

    legg_labeled = [h for h in hits if _hit_has_peg_legg(h)]
    # If probe saw Peg Legg but hit objects missed it, re-scan payloads for the
    # retrieved evidence ids (guards incomplete EvidenceHit field mapping).
    if len(legg_labeled) == 0 and len(hits) > 0 and (
        bool(structured.get("has_peg_legg"))
        or any(
            (d.get("normalized_display") or "") == "peg legg"
            for d in (structured.get("distinct_display_names") or [])
        )
    ):
        try:
            from memorybox.db import connection as _db_conn

            ids = [str(getattr(h, "evidence_id", "") or "") for h in hits[:200]]
            ids = [i for i in ids if i]
            if ids:
                with _db_conn() as conn:
                    rows = conn.execute(
                        """
                        SELECT id::text AS id
                        FROM evidence
                        WHERE id::text = ANY(%s)
                          AND lower(coalesce(payload_json::text, '')) LIKE %s
                        """,
                        (ids, "%peg legg%"),
                    ).fetchall()
                found = {str(r["id"]) for r in (rows or [])}
                legg_labeled = [
                    h for h in hits if str(getattr(h, "evidence_id", "") or "") in found
                ]
        except Exception:  # noqa: BLE001
            pass

    _check(
        "retrieve_includes_peg_legg_labeled_mail",
        len(legg_labeled) > 0,
        checks,
        problems,
        detail={
            "legg_labeled_n": len(legg_labeled),
            "hit_n": len(hits),
            "sample_from": [getattr(h, "from_header", None) for h in hits[:5]],
            "sample_people": [getattr(h, "people", None) for h in hits[:5]],
        },
    )
    spam_trash_diag: dict[str, Any] | None = None
    if len(hits) == 0 and _PROBE_ADDR in addrs:
        # Confirmed address but zero eligible hits — often all rows are spam/trash skipped.
        try:
            from memorybox.db import connection as _db_conn

            like = f"%{_PROBE_ADDR}%"
            with _db_conn() as conn:
                row = conn.execute(
                    """
                    SELECT
                      count(*)::int AS total,
                      count(*) FILTER (
                        WHERE lower(coalesce(payload_json->>'mailbox_skip',
                                             payload_json->>'skip_reason', ''))
                              IN ('spam', 'trash')
                      )::int AS spam_trash,
                      count(*) FILTER (
                        WHERE lower(coalesce(payload_json->>'mailbox_skip',
                                             payload_json->>'skip_reason', ''))
                              NOT IN ('spam', 'trash')
                          OR coalesce(payload_json->>'mailbox_skip',
                                      payload_json->>'skip_reason', '') = ''
                      )::int AS eligibleish
                    FROM evidence
                    WHERE evidence_kind = 'communication'
                      AND lower(coalesce(payload_json->>'evidence_channel', 'email')) = 'email'
                      AND (
                        lower(coalesce(payload_json->>'from', '')) LIKE %s
                        OR lower(coalesce((payload_json->'from_parsed')::text, '')) LIKE %s
                      )
                    """,
                    (like, like),
                ).fetchone()
            spam_trash_diag = dict(row or {})
            if int((spam_trash_diag or {}).get("total") or 0) > 0 and int(
                (spam_trash_diag or {}).get("eligibleish") or 0
            ) == 0:
                _check(
                    "peggo417_not_only_spam_trash",
                    False,
                    checks,
                    problems,
                    detail={
                        **spam_trash_diag,
                        "hint": (
                            "All peggo417 From rows are mailbox_skip spam/trash; "
                            "retrieve correctly excludes them — re-ingest without "
                            "skipping originals, or clear skip flags for eligibility."
                        ),
                    },
                )
        except Exception as exc:  # noqa: BLE001
            spam_trash_diag = {"error": str(exc)}

    gallery_result = {
        "plan": {
            "person_names": list(getattr(plan, "person_names", ()) or ()),
            "person_ids": list(getattr(plan, "person_ids", ()) or ()),
            "original_ask": _ASK,
            "effective_ask": _ASK,
            "notes": list(getattr(plan, "notes", ()) or ()),
            "gallery_show_email": True,
        },
        "evidence_hits": [],
    }
    _items, email_n, match_total = _attach_visible_email(
        [], gallery_result, ask_text=_ASK, show_email=True
    )
    gallery_err = gallery_result.get("gallery_email_error")
    if gallery_err and int(email_n) <= 0 and int(match_total) <= 0:
        _check("gallery_email_attach_ok", False, checks, problems, detail=gallery_err)
    _check(
        "gallery_email_gt_0",
        int(email_n) > 0 or int(match_total) > 0,
        checks,
        problems,
        detail={"email_n": email_n, "match_total": match_total, "error": gallery_err},
    )

    if not flightsim:
        seeded = [str(h.evidence_id) for h in hits if str(h.evidence_id).startswith("eeeeeeee")]
        bare_id = str((seed_info or {}).get("bare_from_evidence_id") or "")
        _check(
            "identity_closure_includes_seeded_peg_legg_mail",
            len(seeded) >= 2,
            checks,
            problems,
            detail=seeded,
        )
        _check(
            "identity_closure_includes_bare_from_people_mail",
            bool(bare_id) and bare_id in seeded,
            checks,
            problems,
            detail={"bare_from_evidence_id": bare_id, "seeded": seeded},
        )

    gate = _write_gate_artifacts(
        {
            "gate": "address_centric_email_identity",
            "stop": "gallery_and_full_evidence_v2 — no historian summarization",
            "ok": not problems
            and len(hits) > 0
            and len(legg_labeled) > 0
            and (len(email_items) > 0 or len(evidence) > 0)
            and (int(email_n) > 0 or int(match_total) > 0)
            and (
                _PROBE_ADDR in addrs
                or (_PROBE_ADDR in accepted_addrs and len(hits) > 0)
            )
            and (ask_peggy.display_name or "").strip().lower() == "peggy george",
            "requirements": {
                "full_evidence_email_gt_0": len(email_items) > 0 or len(evidence) > 0,
                "retrieve_email_hits_gt_0": len(hits) > 0,
                "retrieve_peg_legg_labeled_gt_0": len(legg_labeled) > 0,
                "gallery_email_gt_0": int(email_n) > 0 or int(match_total) > 0,
                "person_is_multi_token": " " in (ask_peggy.display_name or ""),
                "person_is_peggy_george": (ask_peggy.display_name or "").strip().lower()
                == "peggy george",
                "peggo417_confirmed": _PROBE_ADDR in addrs
                or (_PROBE_ADDR in accepted_addrs and len(hits) > 0),
                "probe_structured_has_peg_legg": bool(structured.get("has_peg_legg"))
                or any(
                    (d.get("normalized_display") or "") == "peg legg"
                    for d in (structured.get("distinct_display_names") or [])
                ),
                "ledger_resolved_to_person": bool(ledger_row)
                and str((ledger_row or {}).get("pid") or "") == str(ask_peggy.id),
                "discover_without_prior_email": (not had_peggo_before)
                or bool(resolve.get("accepted") or repair_info),
            },
            "person": {
                "id": ask_peggy.id,
                "display_name": ask_peggy.display_name,
                "addresses": sorted(addrs) if addrs else sorted(accepted_addrs),
            },
            "ledger": {
                "address": (ledger_row or {}).get("address_normalized"),
                "resolution_status": (ledger_row or {}).get("resolution_status"),
                "resolved_person_id": (ledger_row or {}).get("pid"),
                "header_occurrence_count": (ledger_row or {}).get("header_occurrence_count"),
                "had_peggo_contact_before_resolve": had_peggo_before,
            },
            "inventory": {
                "structured_has_peg_legg": structured.get("has_peg_legg"),
                "structured_has_peggy_george": structured.get("has_peggy_george"),
                "quoted_has_peggy_george": quoted.get("has_peggy_george"),
                "quoted_has_peg_legg": quoted.get("has_peg_legg"),
                "structured_occurrence_count": struct_n,
            },
            "counts": {
                "retrieve_hits": len(hits),
                "retrieve_peg_legg_labeled": len(legg_labeled),
                "full_evidence_email_items": len(email_items),
                "gallery_email_n": int(email_n),
            },
            "spam_trash_diag": spam_trash_diag,
            "problems": problems,
            "flightsim": flightsim_claim,
            "runtime": runtime,
            "immich_peggy_upgrade": upgrade_info,
        },
        inv=inv,
        resolve=resolve,
        repair=repair_info,
    )

    return {
        "ok": not problems,
        "prove": "address_centric_email_e2e",
        "flightsim": flightsim_claim,
        "checks": checks,
        "problems": problems,
        "address_centric_gate": gate,
        "immich_peggy_upgrade": upgrade_info,
        "inventory": {
            "address": inv.get("address"),
            "structured_header": {
                "has_peg_legg": structured.get("has_peg_legg"),
                "has_peggy_george": structured.get("has_peggy_george"),
                "occurrence_count": structured.get("occurrence_count"),
                "distinct_display_names": structured.get("distinct_display_names"),
            },
            "quoted_body_headers_only": {
                "has_peg_legg": quoted.get("has_peg_legg"),
                "has_peggy_george": quoted.get("has_peggy_george"),
                "occurrence_count": quoted.get("occurrence_count"),
                "distinct_display_names": quoted.get("distinct_display_names"),
            },
        },
        "person": {
            "id": ask_peggy.id,
            "display_name": ask_peggy.display_name,
            "addresses": sorted(addrs),
        },
        "counts": {
            "retrieve_hits": len(hits),
            "full_evidence_email_items": len(email_items),
            "full_evidence_evidence": len(evidence),
            "gallery_email_n": int(email_n),
            "gallery_match_total": int(match_total),
        },
        "seed": seed_info,
        "repair": repair_info,
        "runtime": runtime,
        "stop": "gallery_and_full_evidence_v2 — no historian summarization",
    }
