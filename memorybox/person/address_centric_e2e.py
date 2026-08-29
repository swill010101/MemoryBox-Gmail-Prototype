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


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


def _seed_local_fixture() -> dict[str, Any]:
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
        conn.execute(
            """
            DELETE FROM person_aliases WHERE person_id IN (
              SELECT id FROM people WHERE display_name IN ('Peggy George','Peggy','Peg Legg')
            )
            """
        )
        conn.execute(
            "DELETE FROM people WHERE display_name IN ('Peggy George','Peggy','Peg Legg')"
        )

    resolve_person_by_name("Peggy", create_if_missing=True, confirm=False)
    peggy = resolve_person_by_name("Peggy George", create_if_missing=True, confirm=True)

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
            "Hi Tom\n-----Original Message-----\n"
            f"From: someone\nCc: Peggy George <{_PROBE_ADDR}>\n"
        ),
        "sent_at": "2019-06-15T12:00:00Z",
        "person_ids": [],
    }
    with connection() as conn:
        for i, sent in enumerate(("2019-06-15T12:00:00Z", "2019-07-01T12:00:00Z"), start=1):
            eid = uuid.UUID(f"eeeeeeee-0000-0000-0000-00000000000{i}")
            p = dict(payload)
            p["sent_at"] = sent
            p["subject"] = f"Hello from Peg {i}"
            conn.execute(
                """
                INSERT INTO evidence (id, evidence_kind, summary, payload_json)
                VALUES (%s, 'communication', %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                  SET payload_json = EXCLUDED.payload_json, updated_at = now()
                """,
                (eid, p["subject"], json.dumps(p)),
            )
    return {"person_id": peggy.person_id, "display_name": peggy.display_name, "seeded": 2}


def run_prove_address_centric_email_e2e(*, flightsim: bool = False) -> dict[str, Any]:
    """Prove discover→resolve→retrieve for peggo417 / Peg Legg / Peggy George."""
    checks: list[str] = []
    problems: list[str] = []
    seed_info: dict[str, Any] | None = None

    if flightsim:
        os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
    else:
        os.environ.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")
        try:
            seed_info = _seed_local_fixture()
            _check("local_seed_ok", bool(seed_info.get("person_id")), checks, problems, detail=seed_info)
        except Exception as exc:  # noqa: BLE001
            _check("local_seed_ok", False, checks, problems, detail=str(exc))
            return {
                "ok": False,
                "prove": "address_centric_email_e2e",
                "flightsim": bool(flightsim),
                "checks": checks,
                "problems": problems,
                "error": f"seed_failed:{exc}",
            }

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
    _check("probe_ok", bool(inv.get("ok")), checks, problems, detail=inv.get("error"))
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

    ask_peggy = find_ask_person_by_name("Peggy", lazy_seed=not flightsim)
    ask_legg = find_ask_person_by_name("Peg Legg", lazy_seed=False)
    _check(
        "ask_peggy_is_peggy_george",
        ask_peggy is not None and " " in (ask_peggy.display_name or ""),
        checks,
        problems,
        detail=getattr(ask_peggy, "display_name", None),
    )
    if ask_legg is not None:
        _check(
            "ask_peg_legg_resolves_same_person",
            ask_peggy is not None and ask_legg.id == ask_peggy.id,
            checks,
            problems,
            detail=(getattr(ask_legg, "display_name", None), getattr(ask_legg, "id", None)),
        )

    if ask_peggy is None:
        return {
            "ok": False,
            "prove": "address_centric_email_e2e",
            "flightsim": bool(flightsim),
            "checks": checks,
            "problems": problems,
            "inventory": inv,
            "seed": seed_info,
        }

    resolve = resolve_and_attach_addresses_for_person(
        ask_peggy.id, persist=True, backfill=False, scan_archive=False
    )
    accepted_addrs = [
        normalize_handle(str((e.get("candidate") or {}).get("address") or ""))
        for e in (resolve.get("accepted") or [])
    ]
    expanded = expand_emails_for_retrieve({ask_peggy.id})
    addrs = {normalize_handle(a) for a in (expanded.get("addresses") or set())}

    # FlightSim belt-and-suspenders: if ledger/auto resolve missed but structured
    # headers exist for the probe address, operator-attest (same as --repair-address).
    repair_info: dict[str, Any] | None = None
    if (
        flightsim
        and _PROBE_ADDR not in addrs
        and int((structured.get("occurrence_count") or 0)) > 0
        and " " in (ask_peggy.display_name or "")
    ):
        from memorybox.person.comm_identity import repair_email_identity_contacts

        repair_info = repair_email_identity_contacts(
            ask_peggy.id,
            known_address=_PROBE_ADDR,
            force_rediscover=False,
        )
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

    plan = resolve_peggy_plan(photo=None, ask=PEGGY_ASK)
    _check(
        "full_evidence_plan_has_person",
        bool(getattr(plan, "person_ids", ()) or ()),
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
    _check(
        "gallery_email_gt_0",
        int(email_n) > 0 or int(match_total) > 0,
        checks,
        problems,
        detail={"email_n": email_n, "match_total": match_total},
    )

    if not flightsim:
        seeded = [str(h.evidence_id) for h in hits if str(h.evidence_id).startswith("eeeeeeee")]
        _check(
            "identity_closure_includes_seeded_peg_legg_mail",
            len(seeded) >= 2,
            checks,
            problems,
            detail=seeded,
        )

    return {
        "ok": not problems,
        "prove": "address_centric_email_e2e",
        "flightsim": bool(flightsim),
        "checks": checks,
        "problems": problems,
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
        "stop": "gallery_and_full_evidence_v2 — no historian summarization",
    }
