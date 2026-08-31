"""Acceptance for trusted-for-retrieval identity (Phase 1)."""
from __future__ import annotations

import inspect
import json
from typing import Any

from memorybox.person.comm_identity import _header_records, corroborate_email_candidate
from memorybox.person.trusted_identity import (
    ADDRESS_CENTRIC_FLIGHTSIM_LEGACY,
    _trusted_verdict_from_rows,
    apply_email_contact_trust,
    classify_contact_trust,
    format_phase1_human_report,
    reclassify_person_email_trust,
    retrieve_keys_from_contact_rows,
)
from memorybox.profile.facts import add_contact


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


def _phase1_gate_envelope(
    *,
    flightsim_requested: bool,
    flightsim_report: dict[str, Any],
    checks: list[str],
    problems: list[str],
) -> dict[str, Any]:
    """Verifier-shaped Phase 1 file. Raw report-only JSON fails C2/C2b/C2c."""
    runtime = _trusted_identity_runtime(flightsim_requested=flightsim_requested)
    return {
        "ok": not problems and bool(flightsim_report.get("ok")),
        "prove": "trusted_identity_retrieval",
        "flightsim": runtime.get("flightsim"),
        "waiting": False,
        "runtime": runtime,
        "checks": list(checks),
        "problems": list(problems),
        "flightsim_report": flightsim_report,
        "phase1": {
            "ok": flightsim_report.get("ok"),
            "trusted_addresses": flightsim_report.get("trusted_addresses"),
            "counts": flightsim_report.get("counts"),
            "per_trusted_address": flightsim_report.get("per_trusted_address"),
            "unique_emails_by_trusted_address": flightsim_report.get(
                "unique_emails_by_trusted_address"
            ),
            "unique_only_via_trusted_address": flightsim_report.get(
                "unique_only_via_trusted_address"
            ),
            "shared_across_trusted_addresses": flightsim_report.get(
                "shared_across_trusted_addresses"
            ),
            "unsupported_retrieve_addresses": flightsim_report.get(
                "unsupported_retrieve_addresses"
            ),
            "unsupported_retrieve_hit_count": flightsim_report.get(
                "unsupported_retrieve_hit_count"
            ),
            "untrusted_n": flightsim_report.get("untrusted_n"),
            "untrusted_by_reason": flightsim_report.get("untrusted_by_reason"),
            "untrusted_sample": flightsim_report.get("untrusted_sample"),
            "retrieve_hit_count": flightsim_report.get("retrieve_hit_count"),
            "gallery_email_count": flightsim_report.get("gallery_email_count"),
            "phase1_summary": flightsim_report.get("phase1_summary"),
        },
        "phase": 1,
        "stop": "phase_1_trusted_identity — no Gemma/Sol/chunking",
    }


def _write_phase1_gate_files(envelope: dict[str, Any]) -> str:
    from pathlib import Path as _P

    out = _P("docs") / "test-output" / "trusted-full-evidence-v2"
    out.mkdir(parents=True, exist_ok=True)
    text = __import__("json").dumps(envelope, indent=2, default=str)
    (out / "TRUSTED_IDENTITY_GATE.json").write_text(text, encoding="utf-8")
    (out / "PHASE1_prove.json").write_text(text, encoding="utf-8")
    summary = (envelope.get("phase1") or {}).get("phase1_summary") or ""
    if summary:
        (out / "PHASE1_SUMMARY.txt").write_text(str(summary), encoding="utf-8")
    return str(out / "TRUSTED_IDENTITY_GATE.json")


def run_prove_trusted_identity_retrieval(*, flightsim: bool = False) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    owner = classify_contact_trust(
        {"actor_key": "owner", "provenance_json": {"source": "person_profile"}}
    )
    _check(
        "owner_profile_contact_is_trusted",
        owner.get("retrieval_trust") == "trusted",
        checks,
        problems,
        detail=owner,
    )
    attested = classify_contact_trust(
        {
            "actor_key": "comm_identity_expand",
            "provenance_json": {
                "source": "comm_identity_operator_attested",
                "operator_attested": True,
            },
        }
    )
    _check(
        "operator_attest_is_trusted",
        attested.get("retrieval_trust") == "trusted",
        checks,
        problems,
        detail=attested,
    )
    auto = classify_contact_trust(
        {
            "actor_key": "comm_identity_expand",
            "provenance_json": {"source": "comm_identity_expand"},
        }
    )
    _check(
        "auto_expand_is_untrusted",
        auto.get("retrieval_trust") == "untrusted",
        checks,
        problems,
        detail=auto,
    )
    unknown = classify_contact_trust(
        {"actor_key": "mystery", "provenance_json": {}}
    )
    legacy_n = int(ADDRESS_CENTRIC_FLIGHTSIM_LEGACY["address_count"])
    legacy_rows = [
        {
            "address": f"auto{i}@example.test",
            "actor_key": "comm_identity_expand",
            "provenance_json": {"source": "comm_identity_expand"},
        }
        for i in range(legacy_n)
    ]
    legacy_rows.append(
        {
            "address": ADDRESS_CENTRIC_FLIGHTSIM_LEGACY["peggo417"],
            "actor_key": "owner",
            "provenance_json": {"source": "person_profile"},
        }
    )
    legacy_keys = retrieve_keys_from_contact_rows(legacy_rows)
    _check(
        "flightsim_700_expand_rows_are_not_retrieve_keys",
        legacy_keys.get("trusted_addresses")
        == [ADDRESS_CENTRIC_FLIGHTSIM_LEGACY["peggo417"]]
        and len(legacy_keys.get("unsupported_if_used_as_retrieve_keys") or [])
        == legacy_n
        and int(ADDRESS_CENTRIC_FLIGHTSIM_LEGACY["retrieve_hits"]) == 42_554,
        checks,
        problems,
        detail={
            "trusted": legacy_keys.get("trusted_addresses"),
            "untrusted_n": len(legacy_keys.get("untrusted_addresses") or []),
        },
    )
    _check(
        "unknown_provenance_fail_closed",
        unknown.get("retrieval_trust") == "untrusted",
        checks,
        problems,
        detail=unknown,
    )
    apply_src = inspect.getsource(apply_email_contact_trust)
    reclass_src = inspect.getsource(reclassify_person_email_trust)
    _check(
        "reclassify_keeps_ledger_when_sibling_trusted",
        "addr not in trusted_addrs" in reclass_src,
        checks,
        problems,
    )
    summary = format_phase1_human_report(
        {
            "display_name": "Example Person",
            "ok": True,
            "counts": {"trusted_for_retrieval": 1, "candidate": 2},
            "per_trusted_address": [
                {
                    "address": "a@example.test",
                    "why_trusted": "canonical_or_owner:owner",
                    "actor_key": "owner",
                    "provenance_source": "person_profile",
                    "unique_structured_messages": 3,
                }
            ],
            "unique_emails_by_trusted_address": {"a@example.test": 3},
            "unique_only_via_trusted_address": {"a@example.test": 3},
            "shared_across_trusted_addresses": 0,
            "retrieve_hit_count": 3,
            "gallery_email_count": 3,
            "unsupported_retrieve_addresses": [],
            "unsupported_retrieve_hit_count": 0,
            "untrusted_n": 2,
            "untrusted_by_reason": {"auto_expand:comm_identity_expand": 2},
            "untrusted_sample": [
                {
                    "address": "noise@example.test",
                    "why_untrusted": "auto_expand:comm_identity_expand",
                    "actor_key": "comm_identity_expand",
                    "provenance_source": "comm_identity_expand",
                }
            ],
        }
    )
    _check(
        "phase1_summary_lists_why_counts_gallery",
        "why=canonical_or_owner:owner" in summary
        and "unique_only=3" in summary
        and "gallery_email_count: 3" in summary
        and "unsupported_retrieve_hit_count: 0" in summary
        and "untrusted_n: 2" in summary
        and "noise@example.test" in summary
        and "do not widen" in summary,
        checks,
        problems,
        detail=summary,
    )
    _check(
        "apply_trust_keeps_prior_trusted_rows",
        "kept_prior_trust" in apply_src
        and "_trusted_verdict_from_rows" in apply_src
        and "LIMIT 1" not in apply_src
        and "Never rewrite owner/operator provenance" in apply_src
        and apply_src.count("actor_key = %s") == 2,
        checks,
        problems,
    )
    mixed = _trusted_verdict_from_rows(
        [
            {
                "actor_key": "comm_identity_expand",
                "provenance_json": {"source": "comm_identity_expand"},
            },
            {
                "actor_key": "owner",
                "provenance_json": {"source": "person_profile"},
            },
        ]
    )
    _check(
        "mixed_rows_keep_owner_profile_trust",
        mixed is not None and mixed.get("retrieval_trust") == "trusted",
        checks,
        problems,
        detail=mixed,
    )
    add_src = inspect.getsource(add_contact)
    _check(
        "add_contact_promotes_existing_profile_email",
        "person_profile" in add_src
        and "owner_confirmed" in add_src
        and "retrieval_trust" in add_src,
        checks,
        problems,
    )

    bare = _header_records(
        {
            "from": "peggo417@hotmail.com",
            "from_parsed": [
                {
                    "display_name": "",
                    "address": "peggo417@hotmail.com",
                    "normalized": "peggo417@hotmail.com",
                }
            ],
            "to": ["Tom Will <swill01@gmail.com>"],
            "to_parsed": [
                {
                    "display_name": "Tom Will",
                    "address": "swill01@gmail.com",
                    "normalized": "swill01@gmail.com",
                }
            ],
            "people": ["Peg Legg", "Tom Will"],
            "body_text": "hi",
        }
    )
    from_dn = [
        r.get("display_name")
        for r in bare
        if r.get("address") == "peggo417@hotmail.com"
    ]
    _check(
        "people_array_does_not_fill_from_display",
        all(not str(x or "").strip() for x in from_dn) or not from_dn,
        checks,
        problems,
        detail=bare,
    )

    quoted_only = {
        "address": "someone@example.com",
        "display_names": {"Peg Legg": 4},
        "occurrences": 4,
        "evidence_ids": ["e1"],
        "header_fields": ["from"],
        "inventory": {
            "quoted_body_headers_only": {
                "distinct_display_names": [
                    {"display_name": "Peggy George", "count": 2}
                ]
            }
        },
    }
    from unittest.mock import patch

    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-1",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_identity.connection"
    ) as conn_ctx:
        conn = conn_ctx.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.side_effect = [
            [{"id": "person-1", "display_name": "Peggy George"}],
            [{"id": "person-1", "display_name": "Peggy George"}],
        ]
        dec = corroborate_email_candidate("person-1", quoted_only)
    _check(
        "quoted_headers_do_not_confirm_ownership",
        not bool(dec.get("accepted")),
        checks,
        problems,
        detail=dec,
    )

    from memorybox.ask import retrieve as retrieve_mod
    from memorybox.person import comm_identity as ci
    from memorybox.person import phone_map as pm

    keep_src = inspect.getsource(retrieve_mod.search_email_messages)
    blob_src = inspect.getsource(retrieve_mod._email_person_blob)
    where_src = inspect.getsource(retrieve_mod._person_scoped_comm_where)
    header_src = inspect.getsource(ci._header_records)
    expand_src = inspect.getsource(ci.expand_emails_for_retrieve)
    snap_src = inspect.getsource(ci.person_identity_snapshot)
    claim_src = inspect.getsource(ci._address_claimed_by)
    sql_src = inspect.getsource(retrieve_mod._sql_confirmed_email_addrs)
    _check(
        "retrieve_keep_does_not_use_name_blob",
        "_email_person_blob" not in keep_src
        and "people" not in keep_src.split("def _keep")[1][:900],
        checks,
        problems,
    )
    _check(
        "thread_extras_still_require_trusted_keep",
        "if tid in thread_ids and str(r[\"id\"]) not in have and _keep(payload, r):"
        in keep_src,
        checks,
        problems,
        detail="thread extras must re-apply trusted _keep",
    )
    _check(
        "email_person_blob_omits_people_array",
        "people" not in blob_src,
        checks,
        problems,
        detail=blob_src,
    )
    hit_src = inspect.getsource(retrieve_mod._email_hit)
    header_people_src = inspect.getsource(retrieve_mod.structured_header_display_names)
    _check(
        "email_hit_does_not_copy_people_array",
        'payload.get("people")' not in hit_src
        and "structured_header_display_names" in hit_src
        and "from_parsed" in header_people_src
        and 'payload.get("people")' not in header_people_src,
        checks,
        problems,
    )
    pack_src = (
        __import__("pathlib").Path(__file__).resolve().parents[1] / "correlate" / "pack.py"
    ).read_text(encoding="utf-8")
    _check(
        "correlation_email_hits_omit_people_array",
        "structured_header_display_names" in pack_src
        and 'kind == "email"' in pack_src,
        checks,
        problems,
    )
    backfill_src = inspect.getsource(ci.backfill_email_person_ids)
    _check(
        "backfill_sql_omits_people_array",
        "payload_json->'people'" not in backfill_src,
        checks,
        problems,
    )
    _check(
        "email_sql_empty_trusted_skips_person_ids_gin",
        "no_trusted_retrieve_addresses" in where_src
        and "confirmed_emails is not None" in where_src,
        checks,
        problems,
    )
    _check(
        "header_records_do_not_assign_from_people",
        "from_people" not in header_src,
        checks,
        problems,
    )
    inv_src = inspect.getsource(
        __import__(
            "memorybox.person.comm_address_index",
            fromlist=["inventory_email_address"],
        ).inventory_email_address
    )
    _check(
        "inventory_counts_structured_hits_with_sql_count",
        "SELECT COUNT(*) AS n FROM evidence" in inv_src
        and "display_limit" in inv_src,
        checks,
        problems,
    )
    attach_src = inspect.getsource(
        __import__(
            "memorybox.person.comm_identity",
            fromlist=["attach_known_email_if_corroborated"],
        ).attach_known_email_if_corroborated
    )
    _check(
        "attach_known_does_not_confirm_via_people_array",
        "payload_json->'people'" not in attach_src
        and 'payload.get("people")' not in attach_src,
        checks,
        problems,
    )
    discover_ci = inspect.getsource(
        __import__(
            "memorybox.person.comm_identity",
            fromlist=["discover_email_candidates_from_archive"],
        ).discover_email_candidates_from_archive
    )
    discover_idx = inspect.getsource(
        __import__(
            "memorybox.person.comm_address_index",
            fromlist=["find_addresses_for_person_forms"],
        ).find_addresses_for_person_forms
    )
    _check(
        "discover_sql_omits_people_array",
        "payload_json->'people'" not in discover_ci
        and "payload_json->'people'" not in discover_idx,
        checks,
        problems,
    )
    _check(
        "expand_retrieve_is_trusted_only",
        "trusted_emails_for_people" in expand_src and "trusted_only" in expand_src,
        checks,
        problems,
    )
    email_search_src = inspect.getsource(retrieve_mod.search_email_messages)
    resolve_src = inspect.getsource(retrieve_mod._resolve_person_ids_from_names)
    _check(
        "name_only_email_resolves_person_then_trusted",
        "_resolve_person_ids_from_names" in email_search_src
        and "create_if_missing=False" in resolve_src
        and "lazy_seed=False" in resolve_src
        and "never name-blob retrieve" in email_search_src,
        checks,
        problems,
    )
    _check(
        "identity_snapshot_emails_are_trusted_classified",
        "classify_contact_trust" in snap_src and "retrieval_trust" in snap_src,
        checks,
        problems,
    )
    _check(
        "claimed_by_requires_trusted_not_any_confirmed",
        "classify_contact_trust" in claim_src
        and "identity_kind) = 'email'" not in claim_src
        and "Provider email rows are not trusted-for-retrieval" in claim_src,
        checks,
        problems,
    )
    report_src = inspect.getsource(
        __import__(
            "memorybox.person.trusted_identity",
            fromlist=["report_named_person_identity_trust"],
        ).report_named_person_identity_trust
    )
    _check(
        "phase1_ok_requires_gallery_mail",
        "gallery_email_count" in report_src and "gallery_scope_error" in report_src,
        checks,
        problems,
    )
    find_src = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "memorybox"
        / "explore"
        / "find.py"
    ).read_text(encoding="utf-8", errors="replace")
    attach_src = find_src.split("def _attach_visible_email")[-1].split("def _attach_calendar")[0]
    from memorybox.explore.find import items_from_ask_result

    gallery_email = items_from_ask_result(
        {
            "evidence_hits": [
                {
                    "evidence_id": "e-people-fill",
                    "evidence_kind": "communication",
                    "channel": "email",
                    "from_header": "",
                    "people": ["Peg Legg", "Random Cooccur"],
                    "summary": "hi",
                }
            ]
        }
    )
    ge = next((r for r in gallery_email if r.get("type") == "email"), {})
    _check(
        "gallery_email_from_does_not_use_people_array",
        ge.get("from") != "Peg Legg"
        and not ge.get("people")
        and "Never payload people[] on the card" in find_src,
        checks,
        problems,
        detail={"from": ge.get("from"), "people": ge.get("people")},
    )
    _check(
        "gallery_reresolves_trusted_retrieve",
        "search_email_messages" in attach_src
        and "Do not keep pre-attached emails" in attach_src
        and "if already:" not in attach_src,
        checks,
        problems,
    )
    index_src = inspect.getsource(pm._index_confirmed_handles)
    _check(
        "sms_handle_index_emails_require_trusted",
        "classify_contact_trust" in index_src
        and "retrieval_trust" in index_src
        and "apple_id', 'email'" not in index_src
        and "'email')" not in index_src.split("provider_identities")[-1][:400],
        checks,
        problems,
    )
    verify_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "verify-trusted-identity-gate.py"
    )
    _check(
        "flightsim_verifier_rejects_allow_dev_and_empty_gallery",
        verify_path.is_file()
        and "allow_dev_defaults" in verify_path.read_text(encoding="utf-8")
        and "gallery_email_count" in verify_path.read_text(encoding="utf-8")
        and "cursor-cloud" in verify_path.read_text(encoding="utf-8")
        and "42554" in verify_path.read_text(encoding="utf-8"),
        checks,
        problems,
    )
    import importlib.util

    _vspec = importlib.util.spec_from_file_location(
        "verify_trusted_identity_gate", verify_path
    )
    _vmod = importlib.util.module_from_spec(_vspec)  # type: ignore[arg-type]
    assert _vspec and _vspec.loader
    _vspec.loader.exec_module(_vmod)
    fake = _vmod.audit_gate(
        {
            "ok": True,
            "flightsim": True,
            "waiting": False,
            "runtime": {
                "hostname": "cursor",
                "p1_runtime_host": True,
                "allow_dev_defaults": False,
            },
            "phase1": {
                "trusted_addresses": ["a@example.test"],
                "per_trusted_address": [{"address": "a@example.test", "why_trusted": "owner"}],
                "unsupported_retrieve_addresses": [],
                "unsupported_retrieve_hit_count": 0,
                "retrieve_hit_count": 3,
                "gallery_email_count": 3,
                "unique_only_via_trusted_address": {"a@example.test": 3},
            },
        }
    )
    _check(
        "verifier_rejects_cursor_hostname",
        not fake.get("ok") and any("C2c" in p for p in (fake.get("problems") or [])),
        checks,
        problems,
        detail=fake.get("problems"),
    )
    allow_dev_leftover = _vmod.audit_gate(
        {
            "ok": True,
            "flightsim": False,
            "waiting": False,
            "runtime": {
                "hostname": "FlightSim",
                "p1_runtime_host": True,
                "allow_dev_defaults": True,
                "flightsim": False,
            },
            "phase1": {
                "trusted_addresses": ["peggo417@hotmail.com"],
                "per_trusted_address": [
                    {"address": "peggo417@hotmail.com", "why_trusted": "owner_or_operator_attested"}
                ],
                "unsupported_retrieve_addresses": [],
                "unsupported_retrieve_hit_count": 0,
                "retrieve_hit_count": 5716,
                "gallery_email_count": 5716,
                "unique_only_via_trusted_address": {"peggo417@hotmail.com": 5716},
            },
        }
    )
    _check(
        "verifier_rejects_allow_dev_on_flightsim_host",
        not allow_dev_leftover.get("ok")
        and any("C2a" in p for p in (allow_dev_leftover.get("problems") or [])),
        checks,
        problems,
        detail=allow_dev_leftover.get("problems"),
    )
    flightsim_pass = _vmod.audit_gate(
        {
            "ok": True,
            "flightsim": True,
            "waiting": False,
            "runtime": {
                "hostname": "FlightSim",
                "p1_runtime_host": True,
                "allow_dev_defaults": False,
                "flightsim": True,
            },
            "phase1": {
                "trusted_addresses": ["peggo417@hotmail.com"],
                "per_trusted_address": [
                    {"address": "peggo417@hotmail.com", "why_trusted": "owner_or_operator_attested"}
                ],
                "unsupported_retrieve_addresses": [],
                "unsupported_retrieve_hit_count": 0,
                "retrieve_hit_count": 5716,
                "gallery_email_count": 5716,
                "unique_only_via_trusted_address": {"peggo417@hotmail.com": 5716},
            },
        }
    )
    _check(
        "verifier_accepts_flightsim_host_without_allow_dev",
        flightsim_pass.get("ok") is True and flightsim_pass.get("goal_complete") is True,
        checks,
        problems,
        detail=flightsim_pass.get("problems"),
    )
    gate_txt = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "flightsim-trusted-identity-gate.cmd"
    ).read_text(encoding="utf-8", errors="replace")
    mig026 = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "memorybox"
        / "migrations"
        / "026_backfill_email_retrieval_trust.sql"
    ).read_text(encoding="utf-8")
    _check(
        "migrate_backfills_email_trust_fail_closed",
        "SET DEFAULT 'untrusted'" in mig026
        and "ELSE 'untrusted'" in mig026
        and "comm_identity_expand" in mig026
        and "person_profile" in mig026
        and "Do not delete rows" in mig026,
        checks,
        problems,
    )
    mig027 = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "memorybox"
        / "migrations"
        / "027_demote_untrusted_email_status.sql"
    ).read_text(encoding="utf-8")
    _check(
        "migrate_demotes_untrusted_confirmed_status",
        "retrieval_trust = 'untrusted'" in mig027
        and "status = 'candidate'" in mig027
        and "resolution_status = 'observed'" in mig027
        and "Keep the rows" in mig027,
        checks,
        problems,
    )
    fed_claim = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.full_evidence_diagnostic",
            fromlist=["_pick_exact_peggy_george"],
        )._pick_exact_peggy_george
    )
    _check(
        "peggy_claimant_requires_trusted_email",
        "retrieval_trust = 'trusted'" in fed_claim
        and "status = 'confirmed'" not in fed_claim,
        checks,
        problems,
    )
    prove_ps1 = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "flightsim-trusted-identity-prove.ps1"
    ).read_text(encoding="utf-8")
    _check(
        "flightsim_gate_runs_phase1_prove_before_pipeline",
        "errorlevel 1" in gate_txt
        and "verify-trusted-identity-gate.py" in gate_txt
        and "-Step Phase1Verify" in gate_txt
        and "Phase 1 already PASS" in gate_txt
        and "goto phase2_freeze" in gate_txt
        and "flightsim-trusted-identity-prove.ps1" in gate_txt
        and "WindowsPowerShell" in gate_txt
        and "ExecutionPolicy Bypass" in gate_txt
        and gate_txt.find(":phase2_freeze")
        < gate_txt.find("-Step Preflight")
        < gate_txt.find("-Step Freeze")
        < gate_txt.find("-Step Pipeline")
        < gate_txt.find("-Step VerifyReports")
        and "-Step Chunks" not in gate_txt
        and "trusted FEV2 freeze" in gate_txt
        and "--authorize-phase3" not in gate_txt
        and "Phase 3 is not authorized" in gate_txt
        and "Phase 3 chunk models (after Phase 2 verifier)" not in gate_txt
        and "evidence(flightsim): trusted-identity Phase 1 gate" in gate_txt
        and "TRUSTED_IDENTITY_GATE.json" in gate_txt
        and "PHASE2_SUMMARY.txt" in gate_txt
        and "PHASE2_PREFLIGHT.json" in gate_txt
        and "git pull --rebase" in gate_txt
        and "checkout -B" in gate_txt
        and "reset --hard" in gate_txt
        and "cursor/p2-i11a-trusted-identity-retrieve-49da" in gate_txt
        and "cursor/flightsim-trusted-identity-result-49da" in gate_txt
        and "HEAD:%RESULT_BRANCH%" in gate_txt
        and "--force" not in gate_txt,
        checks,
        problems,
    )
    _check(
        "flightsim_prove_ps1_loads_startmb_env_and_runs_fev2",
        "Import-DotEnvFile" in prove_ps1
        and "MEMORYBOX_P1_RUNTIME_HOST" in prove_ps1
        and "WindowsApps" in prove_ps1
        and "prove-trusted-identity-retrieval" in prove_ps1
        and "Phase1Verify" in prove_ps1
        and "PHASE2_GATE_STARTED.txt" in prove_ps1
        and "fev2-preflight" in prove_ps1
        and "freeze-trusted-full-evidence-v2" in prove_ps1
        and "--reuse-if-coverage-ok" in prove_ps1
        and "run-trusted-evidence-pipeline" in prove_ps1
        and "verify-trusted-fev2-reports.py" in prove_ps1
        and "run-trusted-fev2-chunked-models" in prove_ps1
        and prove_ps1.find("fev2-preflight")
        < prove_ps1.find("freeze-trusted-full-evidence-v2")
        < prove_ps1.find("run-trusted-evidence-pipeline")
        < prove_ps1.find("run-trusted-fev2-chunked-models"),
        checks,
        problems,
    )
    reset_cmd = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "flightsim-trusted-identity-reset.cmd"
    ).read_text(encoding="utf-8")
    _check(
        "flightsim_reset_hard_resets_trusted_identity_branch_without_force_push",
        "cursor/p2-i11a-trusted-identity-retrieve-49da" in reset_cmd
        and "reset --hard" in reset_cmd
        and "checkout -B" in reset_cmd
        and "--force" not in reset_cmd
        and "p2-i11a-address-centric-email-49da" not in reset_cmd,
        checks,
        problems,
    )
    pre_mod = __import__(
        "memorybox.ask.i11a.trusted_fev2_preflight",
        fromlist=["run_phase2_preflight"],
    )
    pre_src = inspect.getsource(pre_mod)
    _check(
        "phase2_preflight_records_gemma_and_sol_without_skipping_freeze",
        "PHASE2_PREFLIGHT.json" in pre_src
        and "has_gemma4_26b" in pre_src
        and "MEMORYBOX_CLOUD_LLM_MODEL" in pre_src
        and hasattr(pre_mod, "run_phase2_preflight"),
        checks,
        problems,
    )
    _check(
        "flightsim_gate_fails_closed_on_pipeline_skip",
        "-Step Pipeline" in gate_txt
        and "if errorlevel 1" in gate_txt[gate_txt.find("-Step Pipeline") :]
        and gate_txt.find("-Step Pipeline")
        < gate_txt.find("-Step VerifyReports"),
        checks,
        problems,
    )
    fev2_verify_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "verify-trusted-fev2-reports.py"
    )
    _check(
        "fev2_report_verifier_exists",
        fev2_verify_path.is_file()
        and "email_reached_model_and_grounded_output" in fev2_verify_path.read_text(encoding="utf-8")
        and "gemma4:26b" in fev2_verify_path.read_text(encoding="utf-8")
        and "P3-0" in fev2_verify_path.read_text(encoding="utf-8")
        and "evidence_lost" in fev2_verify_path.read_text(encoding="utf-8"),
        checks,
        problems,
    )
    _fspec = importlib.util.spec_from_file_location(
        "verify_trusted_fev2_reports", fev2_verify_path
    )
    _fmod = importlib.util.module_from_spec(_fspec)  # type: ignore[arg-type]
    assert _fspec and _fspec.loader
    _fspec.loader.exec_module(_fmod)
    _check(
        "fev2_verifier_pairs_reports_to_fixture_hash",
        hasattr(_fmod, "_match_hash_or_latest")
        and "Do not pair Sol with a stale Gemma hash" in fev2_verify_path.read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
    )
    skip_audit = _fmod.audit_fev2_reports(
        {"ok": False, "skipped": True, "error": "ollama_model_missing:gemma4:26b"},
        None,
    )
    _check(
        "fev2_verifier_rejects_missing_or_skipped_reports",
        skip_audit.get("ok") is False,
        checks,
        problems,
        detail=skip_audit.get("problems"),
    )
    good_hash = "abc123"
    good_rep = {
        "ok": True,
        "model": "gemma4:26b",
        "input_sha256": good_hash,
        "chunking": False,
        "email_reached_model_and_grounded_output": True,
        "invented_or_unsupported_claims": [],
    }
    sol_rep = {
        **good_rep,
        "model": "sol-test",
        "provider": "cloud",
    }
    pass_audit = _fmod.audit_fev2_reports(good_rep, sol_rep, fixture_hash=good_hash)
    _check(
        "fev2_verifier_accepts_paired_grounded_reports",
        pass_audit.get("ok") is True,
        checks,
        problems,
        detail=pass_audit.get("problems"),
    )
    starved_hash = "3cf95fa44db905af8a10f250e89da9d59138d315c6ff7272c1e2957b231259e8"
    starve_rep = {**good_rep, "input_sha256": starved_hash}
    starve_sol = {**sol_rep, "input_sha256": starved_hash}
    starve_audit = _fmod.audit_fev2_reports(
        starve_rep,
        starve_sol,
        fixture_hash=starved_hash,
        fixture={
            "input_sha256": starved_hash,
            "evidence_type_counts": {"email": 1, "person": 1},
        },
    )
    _check(
        "fev2_verifier_rejects_legacy_one_email_3cf95fa4_freeze",
        starve_audit.get("ok") is False
        and any("P2-15" in str(p) for p in (starve_audit.get("problems") or [])),
        checks,
        problems,
        detail=starve_audit.get("problems"),
    )
    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        fixture_is_single_pass_coverage_ok,
        run_trusted_full_evidence_v2,
    )

    _check(
        "coverage_helper_rejects_3cf95fa4_prefix",
        fixture_is_single_pass_coverage_ok({"input_sha256": starved_hash, "evidence_type_counts": {"email": 1}})
        is False
        and fixture_is_single_pass_coverage_ok(
            {
                "input_sha256": "aa" * 32,
                "evidence_type_counts": {"email": 12},
                "archive_email_count": 5716,
                "paste_format": "trusted_email_threads_v1",
            }
        )
        is True
        and fixture_is_single_pass_coverage_ok(
            {
                "input_sha256": "bb" * 32,
                "evidence_type_counts": {"email": 12},
                "archive_email_count": 5716,
            }
        )
        is False,
        checks,
        problems,
    )
    pipe_mod = __import__(
        "memorybox.ask.i11a.trusted_evidence_pipeline",
        fromlist=["load_reusable_year_fair_freeze"],
    )
    _check(
        "pipeline_reuses_year_fair_freeze_helper",
        hasattr(pipe_mod, "load_reusable_year_fair_freeze")
        and "load_reusable_year_fair_freeze" in inspect.getsource(pipe_mod.run_trusted_evidence_pipeline)
        and hasattr(pipe_mod, "load_reusable_phase1_report")
        and "load_reusable_phase1_report" in inspect.getsource(pipe_mod.run_trusted_evidence_pipeline)
        and "--reuse-if-coverage-ok" in inspect.getsource(
            __import__("memorybox.__main__", fromlist=["main"]).main
        ),
        checks,
        problems,
    )
    gate_dir = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "docs"
        / "test-output"
        / "trusted-full-evidence-v2"
    )
    reused_p1 = pipe_mod.load_reusable_phase1_report(gate_dir)
    _check(
        "pipeline_reuses_flightsim_phase1_gate_without_rescan",
        bool(reused_p1)
        and reused_p1.get("ok") is True
        and "peggo417@hotmail.com" in (reused_p1.get("trusted_addresses") or []),
        checks,
        problems,
        detail=(reused_p1 or {}).get("reused_from"),
    )
    run_src = inspect.getsource(run_trusted_full_evidence_v2)
    _check(
        "phase2_run_refuses_starved_legacy_fixture",
        "trusted_email_starved_fixture" in run_src
        and "fixture_is_single_pass_coverage_ok" in run_src,
        checks,
        problems,
    )
    loss_audit = _fmod.audit_fev2_reports(
        good_rep,
        sol_rep,
        fixture_hash=good_hash,
        chunk_structure={"ok": False, "evidence_lost": ["email:1"]},
    )
    _check(
        "fev2_verifier_rejects_lossy_chunk_structure",
        loss_audit.get("ok") is False
        and any("P3-0" in str(p) for p in (loss_audit.get("problems") or [])),
        checks,
        problems,
        detail=loss_audit.get("problems"),
    )
    _env_export = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "export-memorybox-app-env.py"
    )
    _espec = importlib.util.spec_from_file_location("export_memorybox_app_env", _env_export)
    _emod = importlib.util.module_from_spec(_espec)  # type: ignore[arg-type]
    assert _espec and _espec.loader
    _espec.loader.exec_module(_emod)
    tmp_env = __import__("tempfile").NamedTemporaryFile(
        "w", suffix=".env", delete=False, encoding="utf-8"
    )
    tmp_env.write('MEMORYBOX_CLOUD_LLM_MODEL="sol-quoted"\r\n')
    tmp_env.close()
    parsed_env = _emod.parse_env_file(__import__("pathlib").Path(tmp_env.name))
    export_src = _env_export.read_text(encoding="utf-8")
    _check(
        "app_env_loader_strips_quotes_and_cr",
        parsed_env.get("MEMORYBOX_CLOUD_LLM_MODEL") == "sol-quoted",
        checks,
        problems,
        detail=parsed_env,
    )
    _check(
        "pipeline_loads_flightsim_app_env_before_sol",
        "apply_flightsim_app_env" in inspect.getsource(pipe_mod.run_trusted_evidence_pipeline)
        and "apply_flightsim_app_env" in run_src
        and "apply_unset_keys_to_environ" in export_src
        and "_REPO_ROOT" in export_src,
        checks,
        problems,
    )
    _check(
        "export_app_env_can_apply_to_os_environ",
        hasattr(_emod, "apply_unset_keys_to_environ")
        and hasattr(_emod, "env_files"),
        checks,
        problems,
    )
    cloud_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.historian_provider",
            fromlist=["_CloudOpenAICompatChat"],
        )._CloudOpenAICompatChat
    )
    _check(
        "cloud_sol_sets_max_tokens_so_json_is_not_cut_off",
        '"max_tokens"' in cloud_src
        and "MEMORYBOX_CLOUD_LLM_MAX_TOKENS" in cloud_src
        and "MEMORYBOX_CLOUD_LLM_MAX_TOKENS" in export_src,
        checks,
        problems,
    )
    _check(
        "cloud_chat_retries_http_429",
        "429" in cloud_src
        and "Retry-After" in cloud_src
        and "time.sleep" in cloud_src
        and "HTTPError" in cloud_src,
        checks,
        problems,
    )
    import io as _io
    import os as _os
    import urllib.error as _ue
    from unittest.mock import patch as _patch

    _prev_url = _os.environ.get("MEMORYBOX_CLOUD_LLM_BASE_URL")
    _prev_key = _os.environ.get("MEMORYBOX_CLOUD_LLM_API_KEY")
    _os.environ["MEMORYBOX_CLOUD_LLM_BASE_URL"] = "https://example.test/v1"
    _os.environ["MEMORYBOX_CLOUD_LLM_API_KEY"] = "test-key"
    _cloud_calls = {"n": 0}

    class _Hdr:
        def get(self, name, default=""):
            return "1" if str(name) == "Retry-After" else default

    class _OkResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}],'
                b'"usage":{"total_tokens":1}}'
            )

    def _urlopen_429_then_ok(req, timeout=None):
        _ = req, timeout
        _cloud_calls["n"] += 1
        if _cloud_calls["n"] < 3:
            raise _ue.HTTPError(
                "https://example.test/v1/chat/completions",
                429,
                "Too Many Requests",
                _Hdr(),
                _io.BytesIO(b""),
            )
        return _OkResp()

    _retry_ok = False
    _retry_detail: dict[str, object] = {}
    try:
        from memorybox.ask.i11a.historian_provider import _CloudOpenAICompatChat
        from memorybox.providers.llm.dto import ChatMessage

        with _patch(
            "urllib.request.urlopen", _urlopen_429_then_ok
        ), _patch("memorybox.ask.i11a.historian_provider.time.sleep", lambda _s: None):
            _out = _CloudOpenAICompatChat(
                chat_model="sol-test", timeout_seconds=5
            ).chat([ChatMessage(role="user", content="hi")])
        _retry_ok = _cloud_calls["n"] == 3 and "ok" in (_out.content or "")
        _retry_detail = {"calls": _cloud_calls["n"], "content": _out.content}
    except Exception as exc:  # noqa: BLE001
        _retry_detail = {"error": f"{type(exc).__name__}:{exc}", "calls": _cloud_calls["n"]}
    finally:
        if _prev_url is None:
            _os.environ.pop("MEMORYBOX_CLOUD_LLM_BASE_URL", None)
        else:
            _os.environ["MEMORYBOX_CLOUD_LLM_BASE_URL"] = _prev_url
        if _prev_key is None:
            _os.environ.pop("MEMORYBOX_CLOUD_LLM_API_KEY", None)
        else:
            _os.environ["MEMORYBOX_CLOUD_LLM_API_KEY"] = _prev_key
    _check(
        "cloud_chat_recovers_after_http_429",
        _retry_ok,
        checks,
        problems,
        detail=_retry_detail,
    )
    escaped_sets = _emod.cmd_set_lines(
        {"MEMORYBOX_CLOUD_LLM_API_KEY": r'pre&post|x>y<z^q%pct"q'}
    )
    _check(
        "cmd_set_escapes_metacharacters",
        bool(escaped_sets)
        and "^&" in escaped_sets[0]
        and "^|" in escaped_sets[0]
        and "^>" in escaped_sets[0]
        and "^<" in escaped_sets[0]
        and "^^" in escaped_sets[0]
        and "%%" in escaped_sets[0]
        and '"' not in escaped_sets[0].split("=", 1)[-1][:-1],
        checks,
        problems,
        detail=escaped_sets,
    )
    _check(
        "gate_comments_phase2_summary_only",
        'gh pr comment 77 --body-file "%EVIDENCE_DIR%\\PHASE2_SUMMARY.txt"'
        in gate_txt
        and 'gh pr comment 77 --body-file "%EVIDENCE_DIR%\\PHASE1_SUMMARY.txt"'
        not in gate_txt
        and 'gh pr comment 77 --body-file "%EVIDENCE_DIR%\\PHASE3_SUMMARY.txt"'
        not in gate_txt,
        checks,
        problems,
    )
    _check(
        "flightsim_gate_clears_allow_dev_before_prove",
        "set MEMORYBOX_P1_RUNTIME_HOST=1" in gate_txt
        and "set MEMORYBOX_ALLOW_DEV_DEFAULTS=" in gate_txt
        and "MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333" in gate_txt
        and gate_txt.find("set MEMORYBOX_ALLOW_DEV_DEFAULTS=")
        < gate_txt.find("-Step Phase1")
        and gate_txt.find("MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333")
        < gate_txt.find("-Step Migrate")
        and "export-memorybox-app-env.py" in gate_txt
        and "MEMORYBOX_OLLAMA_BASE_URL=http://127.0.0.1:11434" in gate_txt
        and "started_pre_migrate" in gate_txt
        and "FEV2_paste_*.txt" in gate_txt
        and gate_txt.find("started_pre_migrate")
        < gate_txt.find("export-memorybox-app-env.py")
        < gate_txt.find("-Step Migrate"),
        checks,
        problems,
    )
    config_src = open(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "config.py",
        encoding="utf-8",
    ).read()
    _check(
        "p1_runtime_defaults_localhost_qdrant_without_allow_dev",
        'qdrant_default = "http://127.0.0.1:6333"' in config_src
        and "MEMORYBOX_P1_RUNTIME_HOST" in config_src,
        checks,
        problems,
    )
    main_src = open(
        __import__("pathlib").Path(__file__).resolve().parents[2] / "memorybox" / "__main__.py",
        encoding="utf-8",
    ).read()
    _check(
        "flightsim_cli_clears_allow_dev",
        "_apply_trusted_identity_flightsim_env" in main_src
        and 'MEMORYBOX_ALLOW_DEV_DEFAULTS"] = ""' in main_src
        and main_src.count("_apply_trusted_identity_flightsim_env") >= 3
        and 'if "--flightsim" in argv_list:' in main_src
        and main_src.find('if "--flightsim" in argv_list:')
        < main_src.find('MEMORYBOX_ALLOW_DEV_DEFAULTS"] = "1"'),
        checks,
        problems,
    )
    runtime_src = open(
        __import__("pathlib").Path(__file__).resolve().parent / "trusted_identity_acceptance.py",
        encoding="utf-8",
    ).read()
    _check(
        "runtime_stamp_demotes_allow_dev_flightsim_claim",
        '"flightsim": bool(flightsim_requested) and p1 and not allow_dev' in runtime_src,
        checks,
        problems,
    )
    envelope_shape = _phase1_gate_envelope(
        flightsim_requested=False,
        flightsim_report={
            "ok": True,
            "trusted_addresses": ["a@example.com"],
            "retrieve_hit_count": 1,
            "gallery_email_count": 1,
        },
        checks=["shape"],
        problems=[],
    )
    _check(
        "phase1_prove_json_is_verifier_envelope",
        isinstance(envelope_shape.get("runtime"), dict)
        and "hostname" in envelope_shape["runtime"]
        and "p1_runtime_host" in envelope_shape["runtime"]
        and "allow_dev_defaults" in envelope_shape["runtime"]
        and isinstance(envelope_shape.get("phase1"), dict)
        and envelope_shape.get("waiting") is False
        and envelope_shape.get("prove") == "trusted_identity_retrieval"
        and "_write_phase1_gate_files" in runtime_src
        and ("PHASE1_prove.json" in runtime_src and runtime_src.count("_write_phase1_gate_files") >= 2),
        checks,
        problems,
        detail={k: envelope_shape.get(k) for k in ("runtime", "waiting", "prove")},
    )
    _check(
        "retrieve_sql_omits_people_array",
        "people" not in sql_src,
        checks,
        problems,
        detail=sql_src,
    )
    pg_src = inspect.getsource(retrieve_mod.search_evidence_pg)
    comm_kw = (
        pg_src.split("evidence_kind = 'communication'")[1].split("evidence_kind <>")[0]
        if "evidence_kind = 'communication'" in pg_src
        else ""
    )
    _check(
        "keyword_comm_search_omits_people_array",
        "evidence_kind = 'communication'" in pg_src
        and "payload_json->>'from'" in pg_src
        and "from_parsed" in pg_src
        and "people" not in comm_kw
        and "payload_json::text" not in comm_kw,
        checks,
        problems,
        detail=comm_kw[:400],
    )
    qdrant_src = inspect.getsource(retrieve_mod.search_evidence_qdrant)
    filt_src = inspect.getsource(retrieve_mod.filter_email_hits_to_trusted)
    orch_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "memorybox"
        / "ask"
        / "orchestrator.py"
    )
    orch_src = orch_path.read_text(encoding="utf-8")
    _check(
        "qdrant_comm_blob_omits_people_array",
        "_structured_comm_search_blob" in qdrant_src
        and "json.dumps(_payload_dict" not in qdrant_src,
        checks,
        problems,
    )
    _check(
        "ask_filters_email_hits_to_trusted",
        "email_payload_trusted" in filt_src
        and orch_src.count("filter_email_hits_to_trusted") >= 2,
        checks,
        problems,
    )
    from memorybox.ask.retrieve import EvidenceHit, filter_email_hits_to_trusted
    from memorybox.planner import QueryPlan
    from unittest.mock import patch

    dirty = EvidenceHit(
        evidence_id="ev-people-only",
        evidence_kind="communication",
        summary="cooccur",
        score=1.0,
        excerpt="",
        source="qdrant",
        channel="email",
        payload={"people": ["Peggy George"], "from": "noise@example.test"},
    )
    with patch.object(
        retrieve_mod,
        "_resolve_person_ids_from_names",
        return_value={"person-peggy"},
    ), patch.object(
        retrieve_mod,
        "_confirmed_emails_for_people",
        return_value={"peggo417@hotmail.com"},
    ):
        cleaned = filter_email_hits_to_trusted(
            QueryPlan(
                original_ask="tell me about Peggy",
                effective_ask="tell me about Peggy",
                is_followup=False,
                want_photo=False,
                want_communication=True,
                want_calendar=False,
                person_names=("Peggy George",),
                person_ids=(),
                place_names=(),
                time_start=None,
                time_end=None,
                temporal_windows=(),
            ),
            [dirty],
        )
    _check(
        "qdrant_people_array_email_dropped_without_trusted_header",
        cleaned == [],
        checks,
        problems,
        detail=cleaned,
    )
    sms_hit = EvidenceHit(
        evidence_id="ev-sms-comm",
        evidence_kind="communication",
        summary="text",
        score=1.0,
        excerpt="",
        source="qdrant",
        channel="",
        payload={
            "evidence_channel": "sms",
            "sender_name": "Peggy",
            "body_text": "hi",
        },
    )
    with patch.object(
        retrieve_mod,
        "_resolve_person_ids_from_names",
        return_value={"person-peggy"},
    ), patch.object(
        retrieve_mod,
        "_confirmed_emails_for_people",
        return_value={"peggo417@hotmail.com"},
    ):
        kept_sms = filter_email_hits_to_trusted(
            QueryPlan(
                original_ask="tell me about Peggy",
                effective_ask="tell me about Peggy",
                is_followup=False,
                want_photo=False,
                want_communication=True,
                want_calendar=False,
                person_names=("Peggy George",),
                person_ids=(),
                place_names=(),
                time_start=None,
                time_end=None,
                temporal_windows=(),
            ),
            [sms_hit],
        )
    _check(
        "trusted_email_filter_keeps_sms_when_channel_missing",
        [h.evidence_id for h in kept_sms] == ["ev-sms-comm"]
        and "evidence_channel" in inspect.getsource(retrieve_mod.hit_comm_channel),
        checks,
        problems,
        detail=kept_sms,
    )
    elig_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.full_evidence_diagnostic",
            fromlist=["retrieve_eligible_hits"],
        ).retrieve_eligible_hits
    )
    _check(
        "complete_retrieve_filters_email_to_trusted",
        "filter_email_hits_to_trusted" in elig_src,
        checks,
        problems,
    )
    cons_src = inspect.getsource(retrieve_mod.filter_hits_by_constraints)
    who_src = inspect.getsource(retrieve_mod.hit_who_blob)
    _check(
        "constraint_filter_email_omits_people_array",
        "hit_who_blob" in cons_src
        and "Never people[]" in who_src
        and "from_header" in who_src
        and 'h.people or []' in who_src,
        checks,
        problems,
    )
    trip_src = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "memorybox"
        / "ask"
        / "trip_discovery.py"
    ).read_text(encoding="utf-8")
    _check(
        "trip_discovery_email_omits_people_array",
        "def _hit_who_blob" in trip_src
        and trip_src.count("_hit_who_blob(h)") >= 2
        and '" ".join(h.people or [])' not in trip_src.replace("return \" \".join(h.people or [])", ""),
        checks,
        problems,
    )

    flightsim_report: dict[str, Any] = {}
    if flightsim:
        from memorybox.person.trusted_identity import report_named_person_identity_trust

        flightsim_report = report_named_person_identity_trust("Peggy George")
        _check(
            "flightsim_unsupported_retrieve_addresses_zero",
            flightsim_report.get("ok") is True
            and not flightsim_report.get("unsupported_retrieve_addresses")
            and not flightsim_report.get("unsupported_retrieve_hit_count"),
            checks,
            problems,
            detail=flightsim_report.get("unsupported_retrieve_addresses"),
        )
        _check(
            "flightsim_has_trusted_identity",
            bool(flightsim_report.get("trusted_addresses")),
            checks,
            problems,
            detail=flightsim_report.get("trusted"),
        )
        _check(
            "flightsim_retrieve_has_trusted_mail",
            int(flightsim_report.get("retrieve_hit_count") or 0) > 0,
            checks,
            problems,
            detail={
                "retrieve_hit_count": flightsim_report.get("retrieve_hit_count"),
                "error": flightsim_report.get("retrieve_scope_error"),
            },
        )
        _check(
            "flightsim_gallery_shows_trusted_mail",
            int(flightsim_report.get("gallery_email_count") or 0) > 0
            and not flightsim_report.get("gallery_scope_error"),
            checks,
            problems,
            detail={
                "gallery_email_count": flightsim_report.get("gallery_email_count"),
                "error": flightsim_report.get("gallery_scope_error"),
            },
        )
        try:
            envelope = _phase1_gate_envelope(
                flightsim_requested=True,
                flightsim_report=flightsim_report,
                checks=checks,
                problems=problems,
            )
            _write_phase1_gate_files(envelope)
            flightsim_report["phase1_report_path"] = (
                "docs/test-output/trusted-full-evidence-v2/PHASE1_prove.json"
            )
        except Exception:  # noqa: BLE001
            pass

    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        PHASE2_REPORT_KEYS,
        build_phase2_model_report,
        fev2_input_sha256,
        item_evidence_ids,
        score_email_grounding,
        select_single_pass_items,
        validate_fev2_document,
    )

    items = [
        {"source": "person", "item_id": "p1", "text": "card"},
        {"source": "sms", "item_id": "s1", "text": "hi"},
        {
            "source": "email",
            "item_id": "e-trust",
            "evidence_id": "ev-trust",
            "from": "peggo417@hotmail.com",
            "sent_at": "2020-01-02",
        },
        {
            "source": "email",
            "item_id": "e-other",
            "evidence_id": "ev-other",
            "from": "noise@example.com",
            "sent_at": "2020-01-03",
        },
    ]
    picked = select_single_pass_items(
        items, trusted_addrs={"peggo417@hotmail.com"}, token_budget=50_000
    )
    ids = {str(i.get("item_id")) for i in picked}
    _check(
        "single_pass_keeps_trusted_email_drops_untrusted",
        "e-trust" in ids and "e-other" not in ids and "p1" in ids and "s1" in ids,
        checks,
        problems,
        detail=ids,
    )
    parsed_only = select_single_pass_items(
        [
            {
                "source": "email",
                "item_id": "e-parsed",
                "from": "",
                "from_parsed": [
                    {"display_name": "", "address": "peggo417@hotmail.com"}
                ],
            }
        ],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=50_000,
    )
    _check(
        "single_pass_keeps_hotmail_from_parsed",
        any(i.get("item_id") == "e-parsed" for i in parsed_only),
        checks,
        problems,
        detail=parsed_only,
    )
    from memorybox.ask.i11a.full_evidence_diagnostic import (
        _structured_email_fields,
        format_item_block,
    )

    structured = _structured_email_fields(
        {
            "from_parsed": [
                {"display_name": "", "address": "peggo417@hotmail.com"}
            ],
            "people": ["Peg Legg", "Random"],
        },
        {},
    )
    _check(
        "fev2_email_fields_omit_people_array",
        "peggo417@hotmail.com" in (structured.get("addresses") or [])
        and "Peg Legg" not in (structured.get("participants") or [])
        and "Random" not in (structured.get("participants") or []),
        checks,
        problems,
        detail=structured,
    )
    paste = format_item_block(
        {
            "source": "email",
            "item_id": "email-1",
            "evidence_id": "ev-1",
            "from": "peggo417@hotmail.com",
            "people": ["Peg Legg"],
            "participants": ["Peg Legg"],
            "addresses": ["peggo417@hotmail.com"],
        }
    )
    _check(
        "fev2_paste_omits_email_people_array",
        "people:" not in paste.lower()
        and "participants:" not in paste.lower()
        and "evidence_id: ev-1" in paste
        and "peggo417@hotmail.com" in paste,
        checks,
        problems,
        detail=paste,
    )
    from memorybox.ask.i11a.full_evidence_diagnostic import (
        _canonical_alias_texts,
        _person_fact_items,
    )
    from memorybox.ask.i11a.trusted_full_evidence_v2 import format_trusted_fev2_paste

    expand_aliases = [
        {
            "alias_text": "random header",
            "actor_key": "comm_identity_expand",
            "provenance": {"source": "comm_identity_header_alias"},
        }
        for _ in range(80)
    ]
    owner_aliases = [
        {
            "alias_text": "Peg Legg",
            "actor_key": "owner",
            "provenance": {"source": "person_profile"},
        }
    ]
    _check(
        "person_facts_drop_auto_expand_header_aliases",
        _canonical_alias_texts(expand_aliases + owner_aliases) == ["Peg Legg"],
        checks,
        problems,
        detail=_canonical_alias_texts(expand_aliases + owner_aliases),
    )
    fat_facts = _person_fact_items(
        {
            "focal_subjects": [
                {
                    "person_id": "p-peg",
                    "display_name": "Peggy George",
                    "aliases": expand_aliases + owner_aliases,
                    "communication_identities": [
                        {"contact_kind": "email", "value_text": "peggo417@hotmail.com"}
                    ],
                    "known_relationships": [],
                    "inferred_relationships": [],
                    "allowed_relationship_labels": ["sibling"],
                }
            ]
        }
    )
    fat_body = str((fat_facts[0] or {}).get("body") or "")
    _check(
        "person_fact_item_omits_expand_alias_dump",
        "Peg Legg" in fat_body
        and "random header" not in fat_body
        and "comm_identity_expand" not in fat_body,
        checks,
        problems,
        detail=fat_body[:400],
    )
    rel_facts = _person_fact_items(
        {
            "focal_subjects": [
                {
                    "person_id": "p-peg",
                    "display_name": "Peggy George",
                    "aliases": owner_aliases,
                    "known_relationships": [
                        {
                            "from_person_id": "p-peg",
                            "to_person_id": f"p-{i}",
                            "role_kind": "sibling",
                            "provenance": {"dump": "x" * 200},
                        }
                        for i in range(80)
                    ],
                    "inferred_relationships": [
                        {
                            "from_person_id": "p-peg",
                            "to_person_id": f"q-{i}",
                            "role_kind": "friend",
                            "provenance": {"dump": "y" * 200},
                        }
                        for i in range(80)
                    ],
                }
            ]
        }
    )
    rel_body = str((rel_facts[0] or {}).get("body") or "")
    rel_known = (rel_facts[0] or {}).get("facts", {}).get("known_relationships") or []
    rel_inf = (rel_facts[0] or {}).get("facts", {}).get("inferred_relationships") or []
    _check(
        "person_fact_item_caps_relationship_provenance",
        len(rel_known) == 24
        and len(rel_inf) == 12
        and "dump" not in rel_body,
        checks,
        problems,
        detail={"known": len(rel_known), "inferred": len(rel_inf)},
    )
    starved = select_single_pass_items(
        [
            {
                "source": "person",
                "item_id": "person:huge",
                "body": "x" * 200_000,
                "facts": {"aliases": ["noise"] * 200},
            },
            {
                "source": "email",
                "item_id": "e-keep",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "body": "hello",
            },
        ],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=20_000,
    )
    starved_ids = {str(i.get("item_id")) for i in starved}
    _check(
        "fat_person_facts_do_not_starve_trusted_email",
        "e-keep" in starved_ids,
        checks,
        problems,
        detail=starved_ids,
    )
    trusted_paste = format_trusted_fev2_paste(
        [
            {
                "source": "email",
                "item_id": "email:992d6453-3376-425c-a62b-fa05db1b4a3e",
                "evidence_id": "992d6453-3376-425c-a62b-fa05db1b4a3e",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "body": "wish list",
            }
        ],
        ask="tell me about this person",
        person_context={},
    )
    tag_line = ""
    for line in trusted_paste.splitlines():
        if line.startswith("Turn tags:"):
            tag_line = line
            break
    _check(
        "trusted_fev2_paste_lists_real_evidence_ids",
        "992d6453-3376-425c-a62b-fa05db1b4a3e" in tag_line
        and "email_1" in tag_line,
        checks,
        problems,
        detail=tag_line or trusted_paste[:400],
    )
    empty_trusted = select_single_pass_items(
        items, trusted_addrs=set(), token_budget=50_000
    )
    empty_ids = {str(i.get("item_id")) for i in empty_trusted}
    _check(
        "single_pass_empty_trusted_drops_all_email",
        "e-trust" not in empty_ids and "e-other" not in empty_ids and "p1" in empty_ids,
        checks,
        problems,
        detail=empty_ids,
    )
    crowded = select_single_pass_items(
        [
            {
                "source": "sms",
                "item_id": f"sms{i}",
                "body": "n" * 8000,
                "text": "n" * 8000,
            }
            for i in range(40)
        ]
        + [x for x in items if x.get("source") == "email"],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=20_000,
    )
    crowded_ids = {str(i.get("item_id")) for i in crowded}
    _check(
        "single_pass_reserves_budget_for_trusted_email",
        "e-trust" in crowded_ids and "e-other" not in crowded_ids,
        checks,
        problems,
        detail=crowded_ids,
    )
    packed = select_single_pass_items(
        [
            {
                "source": "story",
                "item_id": f"st{i}",
                "body": "s" * 8000,
            }
            for i in range(30)
        ]
        + [
            {
                "source": "email",
                "item_id": f"em{i}",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "body": "hi",
            }
            for i in range(8)
        ],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=20_000,
    )
    packed_ids = {str(i.get("item_id")) for i in packed}
    _check(
        "single_pass_packs_trusted_email_before_stories",
        all(f"em{i}" in packed_ids for i in range(8)),
        checks,
        problems,
        detail=packed_ids,
    )
    prompt_order = select_single_pass_items(
        [
            {
                "source": "person",
                "item_id": "p-card",
                "body": "person card",
                "facts": {"display_name": "Peggy George"},
            },
            {
                "source": "email",
                "item_id": "e-first",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "body": "christmas wish list",
                "evidence_id": "ev-mail-1",
            },
        ],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=20_000,
    )
    prompt_paste = format_trusted_fev2_paste(
        prompt_order,
        ask="tell me what you know",
        person_context={
            "focal_subjects": [
                {
                    "display_name": "Peggy George",
                    "communication_identities": [
                        {"contact_kind": "email", "value_text": "peggo417@hotmail.com"}
                    ],
                }
            ]
        },
        trusted_addresses=["peggo417@hotmail.com"],
    )
    _check(
        "single_pass_orders_email_before_person_in_model_prompt",
        prompt_order
        and str(prompt_order[0].get("source")) == "email"
        and "===== TRUSTED EMAIL THREADS =====" in prompt_paste
        and "BEGIN THREAD" in prompt_paste
        and "END THREAD" in prompt_paste
        and "christmas wish list" in prompt_paste
        and "Peggy George said:" in prompt_paste
        and prompt_paste.find("christmas wish list")
        < prompt_paste.find("Turn tags:")
        and str(prompt_order[0].get("cite_as") or "") == "email_1"
        and "[email_1]" in prompt_paste
        and "people:" not in prompt_paste.lower(),
        checks,
        problems,
        detail=prompt_paste[:500],
    )
    thread_paste = format_trusted_fev2_paste(
        [
            {
                "source": "email",
                "item_id": "e-rick",
                "evidence_id": "ev-rick",
                "subject": "Re: Harbor dinner",
                "timestamp": "2020-01-01T18:00:00Z",
                "from": "Rick <rick@example.test>",
                "from_parsed": [
                    {"display_name": "Rick", "address": "rick@example.test"}
                ],
                "addresses": ["rick@example.test", "peggo417@hotmail.com"],
                "body": "Peg, dinner is at seven.",
            },
            {
                "source": "email",
                "item_id": "e-peg",
                "evidence_id": "ev-peg",
                "subject": "Harbor dinner",
                "timestamp": "2020-01-01T18:10:00Z",
                "from": "peggo417@hotmail.com",
                "from_parsed": [
                    {
                        "display_name": "Peg Legg",
                        "address": "peggo417@hotmail.com",
                    }
                ],
                "addresses": ["rick@example.test", "peggo417@hotmail.com"],
                "body": "See you there.",
            },
        ],
        ask="tell me what you know about this person",
        person_context={
            "focal_subjects": [
                {
                    "display_name": "Peggy George",
                    "communication_identities": [
                        {"contact_kind": "email", "value_text": "peggo417@hotmail.com"}
                    ],
                }
            ]
        },
        trusted_addresses=["peggo417@hotmail.com"],
    )
    _check(
        "fev2_paste_is_dated_speaker_threads",
        "BEGIN THREAD: Harbor dinner" in thread_paste
        and "END THREAD" in thread_paste
        and "Rick said:" in thread_paste
        and "Peggy George said:" in thread_paste
        and thread_paste.find("Rick said:") < thread_paste.find("Peggy George said:")
        and "Peg, dinner is at seven." in thread_paste
        and "See you there." in thread_paste
        and "people:" not in thread_paste.lower(),
        checks,
        problems,
        detail=thread_paste,
    )
    from memorybox.ask.authored import plain_email_body
    from memorybox.ask.i11a.trusted_full_evidence_v2 import FEV2_SYSTEM

    _check(
        "html_only_takeout_email_becomes_plain_body",
        "Hello Pegs" in plain_email_body(
            {"body_html": "<p>Hello Pegs</p><br>Stay warm"}
        )
        and plain_email_body({"body_text": "plain wins", "body_html": "<p>nope</p>"})
        == "plain wins",
        checks,
        problems,
    )
    _check(
        "fev2_system_has_role_and_summarization_objective",
        "family historian" in FEV2_SYSTEM
        and "Objective:" in FEV2_SYSTEM
        and "who said what" in FEV2_SYSTEM
        and "ASK" in FEV2_SYSTEM,
        checks,
        problems,
        detail=FEV2_SYSTEM[:240],
    )
    l1_items = [
        {
            "item_id": "person:peggy",
            "source": "person",
            "native_id": "pid-1",
            "timestamp": "1947-01-01",
            "title": "Person facts",
            "body": "Peggy George",
            "facts": {"display_name": "Peggy George"},
        }
    ]
    for i in range(24):
        year = 2000 + (i % 12)
        eid = f"mail-{i:03d}"
        l1_items.append(
            {
                "item_id": f"email:{eid}",
                "source": "email",
                "native_id": eid,
                "evidence_id": eid,
                "timestamp": f"{year}-06-15T12:00:00Z",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "from_parsed": [
                    {
                        "address": "peggo417@hotmail.com",
                        "normalized": "peggo417@hotmail.com",
                    }
                ],
                "subject": f"Note {i}",
                "body": ("planning dinner with family. " * 120),
                "thread_id": f"t-{i // 4}",
            }
        )
    l1_selected = select_single_pass_items(
        l1_items,
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=100_000,
    )
    l1_paste = format_trusted_fev2_paste(
        l1_selected,
        ask="tell me what you know about this person",
        person_context={},
    )
    l1_body = {
        "ask": "tell me what you know about this person",
        "trusted_addresses": ["peggo417@hotmail.com"],
        "person_context": {},
        "items": l1_selected,
        "email_evidence_ids": [
            x
            for it in l1_selected
            for x in item_evidence_ids(it)
            if it.get("source") == "email"
        ],
        "user_message": l1_paste,
        "system": "sys",
        "chunking": False,
        "evidence_type_counts": {
            "email": sum(1 for it in l1_selected if it.get("source") == "email"),
            "person": 1,
        },
    }
    l1_body["input_sha256"] = fev2_input_sha256(l1_body)
    import tempfile as _l1_tempfile
    from pathlib import Path as _L1Path

    l1_fx = _L1Path(_l1_tempfile.mkdtemp()) / "FEV2_yearfair_l1.json"
    l1_fx.write_text(__import__("json").dumps(l1_body), encoding="utf-8")
    from memorybox.ask.i11a.trusted_fev2_chunking import compare_chunked_vs_unchunked

    l1_cmp = compare_chunked_vs_unchunked(l1_fx)
    _check(
        "year_fair_fev2_l1_chunk_structure_covers_items",
        l1_cmp.get("ok") is True
        and not (l1_cmp.get("evidence_lost") or [])
        and "email_thread" in (l1_cmp.get("l1_unit_kinds") or {})
        and int(l1_cmp.get("chunk_count") or 0) >= 2
        and int((l1_body.get("evidence_type_counts") or {}).get("email") or 0) >= 8,
        checks,
        problems,
        detail={
            "ok": l1_cmp.get("ok"),
            "kinds": l1_cmp.get("l1_unit_kinds"),
            "lost": l1_cmp.get("evidence_lost"),
            "emails": (l1_body.get("evidence_type_counts") or {}).get("email"),
        },
    )
    freeze_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_full_evidence_v2",
            fromlist=["freeze_trusted_full_evidence_v2"],
        ).freeze_trusted_full_evidence_v2
    )
    _check(
        "freeze_pins_person_id_not_peggy_resolver",
        "resolve_peggy_plan" not in freeze_src
        and "person_ids=(str(person_id),)" in freeze_src
        and "PEGGY FULL-FIDELITY" not in freeze_src
        and "format_trusted_fev2_paste" in freeze_src,
        checks,
        problems,
    )
    _check(
        "single_pass_freeze_skips_unbounded_immich",
        "retrieve_eligible_hits" not in freeze_src
        and "want_still=False" in freeze_src
        and "single_pass_no_unbounded_immich" in freeze_src,
        checks,
        problems,
    )
    _check(
        "single_pass_freeze_skips_unbounded_sms",
        "search_email_messages" in freeze_src
        and "search_sms_messages" not in freeze_src
        and "single_pass_no_unbounded_sms" in freeze_src
        and "retrieve_eligible_hits" not in freeze_src
        and "search_calendar_events(plan, limit=12)" in freeze_src
        and "search_stories(plan, limit=12)" in freeze_src
        and "search_journals(plan, limit=12)" in freeze_src
        and "want_calendar=complete_trusted" in freeze_src
        and "single_pass_no_calendar_scan" in freeze_src
        and "_trim_fev2_email_payloads" in freeze_src
        and "SINGLE_PASS_EMAIL_RETRIEVE_CAP" in freeze_src
        and "cap_single_pass_retrieved_emails" in freeze_src,
        checks,
        problems,
    )
    _check(
        "freeze_cli_omits_fixture_dump",
        'if k != "fixture"' in main_src
        and "printed = {k: v for k, v in payload.items()" in main_src,
        checks,
        problems,
    )
    from memorybox.ask.retrieve import EvidenceHit
    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        SINGLE_PASS_EMAIL_RETRIEVE_CAP,
        cap_single_pass_retrieved_emails,
    )

    archive_hits = [
        EvidenceHit(
            evidence_id=f"e{year}-{i}",
            evidence_kind="email_message",
            summary=f"{year} {i}",
            score=1.0,
            excerpt="",
            source="email_mbox",
            sent_at=f"{year}-06-01T12:00:00Z",
            channel="email",
            match_total=400,
        )
        for year in range(2005, 2015)
        for i in range(40)
    ]
    sampled = cap_single_pass_retrieved_emails(archive_hits)
    sample_years = {(h.sent_at or "")[:4] for h in sampled}
    _check(
        "single_pass_year_fair_caps_complete_archive",
        len(archive_hits) == 400
        and len(sampled) == SINGLE_PASS_EMAIL_RETRIEVE_CAP
        and sample_years == {str(y) for y in range(2005, 2015)},
        checks,
        problems,
        detail={"n": len(sampled), "years": sorted(sample_years)},
    )
    retrieve_complete = inspect.getsource(
        __import__("memorybox.ask.retrieve", fromlist=["_complete_comm_retrieve"])._complete_comm_retrieve
    )
    retrieve_email = inspect.getsource(
        __import__("memorybox.ask.retrieve", fromlist=["search_email_messages"]).search_email_messages
    )
    _check(
        "trusted_fev2_retrieve_year_fairs_not_complete_archive",
        'if "trusted_full_evidence_v2" in notes:' in retrieve_complete
        and "return False" in retrieve_complete
        and "trusted_full_evidence_v2" in retrieve_email
        and "keywords = []" in retrieve_email
        and "_year_fair_email_hits_light_scan" in retrieve_email,
        checks,
        problems,
    )
    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        remap_placeholder_evidence_ids,
        single_pass_email_coverage_ok,
        validate_fev2_document,
    )

    _check(
        "single_pass_refuses_one_email_when_archive_is_large",
        single_pass_email_coverage_ok(
            retrieved_email_n=5716, selected_email_n=1, complete_trusted=False
        )
        is False
        and single_pass_email_coverage_ok(
            retrieved_email_n=5716, selected_email_n=8, complete_trusted=False
        )
        is True
        and single_pass_email_coverage_ok(
            retrieved_email_n=3, selected_email_n=1, complete_trusted=False
        )
        is True,
        checks,
        problems,
    )
    _check(
        "freeze_fail_closed_when_trusted_email_starved",
        "trusted_email_starved" in freeze_src
        and "single_pass_email_coverage_ok" in freeze_src,
        checks,
        problems,
    )
    fixture_items = [
        {
            "source": "person",
            "item_id": "person:cc6eb438-86a9-405c-89aa-6c6fc43de076",
            "native_id": "cc6eb438-86a9-405c-89aa-6c6fc43de076",
        },
        {
            "source": "email",
            "item_id": "email:992d6453-3376-425c-a62b-fa05db1b4a3e",
            "evidence_id": "992d6453-3376-425c-a62b-fa05db1b4a3e",
        },
    ]
    remapped = remap_placeholder_evidence_ids(
        {
            "claims": [
                {
                    "text": "Peg sent a wish list",
                    "evidence_ids": ["email_1", "person_1"],
                }
            ],
            "episodes": [
                {"title": "wishlist", "evidence_ids": ["email_1"]}
            ],
            "relationships": [
                {
                    "from": "cc6eb438-86a9-405c-89aa-6c6fc43de076",
                    "to": "other",
                    "role": "sibling",
                    "evidence_ids": ["person_1"],
                }
            ],
        },
        fixture_items,
    )
    allowed_ids = {
        "person:cc6eb438-86a9-405c-89aa-6c6fc43de076",
        "cc6eb438-86a9-405c-89aa-6c6fc43de076",
        "email:992d6453-3376-425c-a62b-fa05db1b4a3e",
        "992d6453-3376-425c-a62b-fa05db1b4a3e",
    }
    remapped_ground = validate_fev2_document(
        remapped,
        allowed_ids=allowed_ids,
        email_evidence_ids={
            "992d6453-3376-425c-a62b-fa05db1b4a3e",
            "email:992d6453-3376-425c-a62b-fa05db1b4a3e",
        },
    )
    _check(
        "phase2_remaps_email_1_person_1_placeholders",
        remapped["claims"][0]["evidence_ids"][0]
        == "992d6453-3376-425c-a62b-fa05db1b4a3e"
        and remapped["claims"][0]["evidence_ids"][1]
        == "person:cc6eb438-86a9-405c-89aa-6c6fc43de076"
        and remapped_ground.get("ok")
        and not remapped_ground.get("invented_evidence_ids"),
        checks,
        problems,
        detail=remapped_ground,
    )
    from pathlib import Path as _P

    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        all_fixture_evidence_ids,
        build_phase2_model_report,
    )

    _legacy_fx = (
        _P("docs")
        / "test-output"
        / "trusted-full-evidence-v2"
        / "FEV2_20260829T215848Z_3cf95fa4.json"
    )
    _legacy_rep = (
        _P("docs")
        / "test-output"
        / "trusted-full-evidence-v2"
        / "FEV2REPORT_ollama_gemma4-26b_3cf95fa4.json"
    )
    if _legacy_fx.is_file() and _legacy_rep.is_file():
        _fx = json.loads(_legacy_fx.read_text(encoding="utf-8"))
        _rep = json.loads(_legacy_rep.read_text(encoding="utf-8"))
        _doc = {
            "episodes": _rep.get("episodes"),
            "claims": _rep.get("claims"),
            "relationships": _rep.get("relationships"),
            "narrator": _rep.get("narrator"),
        }
        _items = list(_fx.get("items") or [])
        _rewritten = remap_placeholder_evidence_ids(_doc, _items)
        _ground = validate_fev2_document(
            _rewritten,
            allowed_ids=all_fixture_evidence_ids(_items),
            email_evidence_ids={str(x) for x in (_fx.get("email_evidence_ids") or [])},
        )
        _phase2 = build_phase2_model_report(
            fixture=_fx,
            document=_rewritten,
            provider="ollama",
            model="gemma4:26b",
            grounding=_ground,
        )
        refused_legacy = run_trusted_full_evidence_v2(
            _legacy_fx, provider="ollama", model="gemma4:26b"
        )
        _check(
            "run_refuses_flightsim_3cf95fa4_starved_fixture",
            refused_legacy.get("ok") is False
            and refused_legacy.get("error") == "trusted_email_starved_fixture",
            checks,
            problems,
            detail=refused_legacy.get("error"),
        )
        _check(
            "remap_recovers_flightsim_gemma_placeholder_ids",
            _phase2.get("ok") is True
            and _phase2.get("email_reached_model_and_grounded_output") is True
            and not (_phase2.get("invented_or_unsupported_claims") or []),
            checks,
            problems,
            detail={
                "ok": _phase2.get("ok"),
                "invented": _ground.get("invented_evidence_ids"),
                "cited": _ground.get("email_evidence_cited"),
            },
        )
    huge_mail = select_single_pass_items(
        [
            {
                "source": "email",
                "item_id": f"em-big-{i}",
                "from": "peggo417@hotmail.com",
                "addresses": ["peggo417@hotmail.com"],
                "body": "H" * 80_000,
            }
            for i in range(8)
        ],
        trusted_addrs={"peggo417@hotmail.com"},
        token_budget=20_000,
    )
    _check(
        "single_pass_truncates_huge_email_bodies",
        len(huge_mail) >= 8
        and all(
            len(str(i.get("body") or "")) < 8_000 for i in huge_mail
        ),
        checks,
        problems,
        detail=len(huge_mail),
    )
    run_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_full_evidence_v2",
            fromlist=["run_trusted_full_evidence_v2"],
        ).run_trusted_full_evidence_v2
    )
    _check(
        "phase2_preflights_established_gemma_model",
        "ollama_has_model" in run_src and "ollama_model_missing" in run_src,
        checks,
        problems,
    )
    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        FEV2_OLLAMA_NUM_CTX_MIN,
        fev2_ollama_num_ctx,
    )

    _check(
        "fev2_ollama_num_ctx_covers_year_fair_paste",
        fev2_ollama_num_ctx(100_000) >= 100_000
        and fev2_ollama_num_ctx(1_000) == FEV2_OLLAMA_NUM_CTX_MIN
        and "num_ctx=fev2_ollama_num_ctx" in run_src,
        checks,
        problems,
        detail=fev2_ollama_num_ctx(100_000),
    )
    chunk_chat_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_fev2_chunking",
            fromlist=["_chat_chunk"],
        )._chat_chunk
    )
    chunk_run_src_ctx = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_fev2_chunking",
            fromlist=["run_provider_over_chunks"],
        ).run_provider_over_chunks
    )
    _check(
        "phase3_chunks_use_trusted_email_first_paste_and_num_ctx",
        "format_trusted_fev2_paste" in chunk_run_src_ctx
        and "format_cloud_paste" not in chunk_run_src_ctx
        and "num_ctx=fev2_ollama_num_ctx" in chunk_chat_src,
        checks,
        problems,
    )
    ollama_http_src = open(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "providers"
        / "llm"
        / "_ollama_http.py",
        encoding="utf-8",
    ).read()
    _check(
        "ollama_has_model_accepts_latest_tag",
        'n == f"{want}:latest"' in ollama_http_src,
        checks,
        problems,
    )
    ground = score_email_grounding(
        {
            "claims": [
                {"text": "Peggy emailed", "evidence_ids": ["ev-trust"]},
            ],
            "episodes": [],
        },
        email_evidence_ids={"ev-trust"},
    )
    _check(
        "grounding_requires_email_citation",
        bool(ground.get("ok")) and ground.get("claims_citing_email") == 1,
        checks,
        problems,
        detail=ground,
    )
    miss = score_email_grounding(
        {"claims": [{"text": "invented", "evidence_ids": []}], "episodes": []},
        email_evidence_ids={"ev-trust"},
    )
    _check(
        "grounding_fails_when_email_unused",
        not miss.get("ok"),
        checks,
        problems,
        detail=miss,
    )
    body = {
        "ask": "tell me about Peggy",
        "trusted_addresses": ["peggo417@hotmail.com"],
        "person_context": {"focal_subjects": []},
        "items": picked,
        "email_evidence_ids": ["ev-trust"],
        "chunking": False,
    }
    h1 = fev2_input_sha256(body)
    h2 = fev2_input_sha256(body)
    _check("fev2_hash_stable", h1 == h2 and len(h1) == 64, checks, problems, detail=h1)

    p2 = build_phase2_model_report(
        fixture=body,
        document={
            "episodes": [{"title": "mail", "when": "2020", "evidence_ids": ["ev-trust"]}],
            "claims": [{"text": "Peggy emailed", "evidence_ids": ["ev-trust"]}],
            "relationships": [],
            "narrator": "grounded",
        },
        provider="ollama",
        model="gemma4:26b",
        grounding=ground,
        timing_ms=12,
        usage={"total_tokens": 9},
    )
    _check(
        "phase2_report_has_required_fields",
        all(k in p2 for k in PHASE2_REPORT_KEYS) and bool(p2.get("ok")),
        checks,
        problems,
        detail={k: k in p2 for k in PHASE2_REPORT_KEYS},
    )
    pipe_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_evidence_pipeline",
            fromlist=["run_trusted_evidence_pipeline"],
        ).run_trusted_evidence_pipeline
    )
    _check(
        "pipeline_stops_on_phase1_failure",
        "phase_1_failed" in pipe_src and "do not widen" in pipe_src.lower(),
        checks,
        problems,
    )
    _check(
        "pipeline_writes_phase1_human_summary",
        "PHASE1_SUMMARY_" in pipe_src and "phase1_summary" in pipe_src,
        checks,
        problems,
    )
    phase2_sum_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_evidence_pipeline",
            fromlist=["format_phase2_summary"],
        ).format_phase2_summary
    )
    phase2_write_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_evidence_pipeline",
            fromlist=["_write_phase2_summary_files"],
        )._write_phase2_summary_files
    )
    _check(
        "pipeline_writes_phase2_human_summary",
        "phase2_summary" in pipe_src
        and "_write_phase2_summary_files" in pipe_src
        and "PHASE2_SUMMARY.txt" in phase2_write_src
        and "TRUSTED-EVIDENCE PHASE 2 SUMMARY" in phase2_sum_src,
        checks,
        problems,
    )
    _check(
        "pipeline_stops_after_phase2_unless_authorized",
        "phase_3_requires_explicit_authorization" in pipe_src
        and "phase_2_complete" in pipe_src
        and "authorize_phase3" in pipe_src
        and pipe_src.find("if both_single_pass and authorize_phase3")
        < pipe_src.find("compare_chunked_vs_unchunked")
        and pipe_src.find("if both_single_pass and authorize_phase3")
        < pipe_src.find("run_chunked_models_after_single_pass"),
        checks,
        problems,
    )
    _check(
        "pipeline_reuses_existing_phase2_reports",
        "load_reusable_phase2_run" in pipe_src
        and "blocked_until_gemma_ok" in pipe_src
        and "grounding_invented_ids" in inspect.getsource(
            __import__(
                "memorybox.ask.i11a.trusted_evidence_pipeline",
                fromlist=["_model_fail_error"],
            )._model_fail_error
        ),
        checks,
        problems,
    )
    from memorybox.ask.i11a.trusted_evidence_pipeline import (
        load_reusable_phase2_run as _load_p2,
        format_phase2_summary as _fmt_p2,
    )
    import tempfile
    from pathlib import Path as _Tmp

    _p2_dir = _Tmp(tempfile.mkdtemp())
    _p2_hash = "fe8a128c" + ("0" * 56)
    _p2_fail = {
        "ok": False,
        "input_sha256": _p2_hash,
        "validation": {
            "ok": False,
            "invented_evidence_ids": ["email_1", "person_1"],
        },
        "invented_or_unsupported_claims": [
            {"id": "email_1", "reason": "invented_evidence_id"}
        ],
        "email_reached_model_and_grounded_output": False,
    }
    (
        _p2_dir / f"FEV2REPORT_ollama_gemma4-26b_{_p2_hash[:8]}.json"
    ).write_text(__import__("json").dumps(_p2_fail), encoding="utf-8")
    _reused_fail = _load_p2(
        _p2_dir, provider="ollama", model="gemma4:26b", fixture_hash=_p2_hash
    )
    _check(
        "pipeline_reuses_failed_gemma_report_with_reason",
        _reused_fail is not None
        and _reused_fail.get("ok") is False
        and _reused_fail.get("reused") is True
        and "grounding_invented_ids:email_1" in str(_reused_fail.get("error") or ""),
        checks,
        problems,
        detail=_reused_fail,
    )
    _p2_summary = _fmt_p2(
        {
            "ok": False,
            "stop": "phase_2_gemma_incomplete — do not chunk-with-models yet",
            "freeze": {"ok": True, "reused": True},
            "gemma": {
                "ok": False,
                "skipped": False,
                "reused": True,
                "error": "grounding_invented_ids:email_1,person_1",
            },
            "sol": {
                "ok": False,
                "skipped": True,
                "reused": False,
                "error": "blocked_until_gemma_ok — fix Gemma grounding before paying Sol",
            },
        }
    )
    _check(
        "phase2_summary_includes_reuse_and_fail_reason",
        "reused=True" in _p2_summary
        and "grounding_invented_ids:email_1,person_1" in _p2_summary
        and "blocked_until_gemma_ok" in _p2_summary,
        checks,
        problems,
        detail=_p2_summary,
    )
    _check(
        "pipeline_defers_larger_set_until_both_single_pass",
        "after_both_single_pass_reports_only" in pipe_src
        and "complete_trusted=True" not in pipe_src,
        checks,
        problems,
    )
    compare_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_fev2_chunking",
            fromlist=["compare_chunked_vs_unchunked"],
        ).compare_chunked_vs_unchunked
    )
    _check(
        "chunk_compare_fails_closed_without_raising",
        "l1_chunker" in compare_src
        and "except Exception" in compare_src
        and "_fev2_l1_pack_kwargs" in compare_src,
        checks,
        problems,
    )
    from memorybox.ask.i11a.trusted_fev2_chunking import ready_for_chunk_models
    import tempfile
    from pathlib import Path as _Tmp

    tmp_fx = _Tmp(tempfile.mkdtemp()) / "fx.json"
    fx_body = dict(body)
    fx_body["system"] = "sys"
    fx_body["user_message"] = "msg"
    fx_hash = fev2_input_sha256(fx_body)
    fx_body["input_sha256"] = fx_hash
    tmp_fx.write_text(__import__("json").dumps(fx_body), encoding="utf-8")
    blocked = ready_for_chunk_models(tmp_fx, {}, {})
    _check(
        "chunk_models_blocked_without_both_reports",
        not blocked.get("ok") and "blocked_until_both" in str(blocked.get("error") or ""),
        checks,
        problems,
        detail=blocked,
    )
    ready = ready_for_chunk_models(
        tmp_fx,
        {
            "ok": True,
            "input_sha256": fx_hash,
            "email_reached_model_and_grounded_output": True,
        },
        {
            "ok": True,
            "input_sha256": fx_hash,
            "email_reached_model_and_grounded_output": True,
        },
    )
    _check(
        "chunk_models_ready_when_both_single_pass_match_hash",
        bool(ready.get("ok")) and ready.get("input_sha256") == fx_hash,
        checks,
        problems,
        detail=ready,
    )
    chunk_run_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_fev2_chunking",
            fromlist=["run_chunked_models_after_single_pass"],
        ).run_chunked_models_after_single_pass
    )
    _check(
        "chunk_models_write_phase3_human_summary",
        "PHASE3_SUMMARY.txt" in chunk_run_src
        and "TRUSTED-EVIDENCE PHASE 3 SUMMARY" in chunk_run_src,
        checks,
        problems,
    )
    from_dir_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_fev2_chunking",
            fromlist=["run_chunked_models_from_dir"],
        ).run_chunked_models_from_dir
    )
    _check(
        "chunk_from_dir_pairs_reports_to_fixture_hash",
        "missing_phase2_reports_for_fixture_hash" in from_dir_src
        and "fixture_is_single_pass_coverage_ok" in from_dir_src
        and "no_sol_model" in from_dir_src
        and from_dir_src.count("PHASE3_SUMMARY.txt") >= 3,
        checks,
        problems,
    )

    invented = validate_fev2_document(
        {
            "episodes": [],
            "claims": [{"text": "nope", "evidence_ids": ["ev-invented"]}],
        },
        allowed_ids={"ev-trust"},
        email_evidence_ids={"ev-trust"},
    )
    _check(
        "fev2_fails_closed_on_invented_ids",
        not invented.get("ok") and "ev-invented" in (invented.get("invented_evidence_ids") or []),
        checks,
        problems,
        detail=invented,
    )

    from memorybox.ask.i11a.trusted_fev2_chunking import merge_chunk_documents

    merged = merge_chunk_documents(
        [
            {
                "episodes": [{"title": "a", "when": "2020-01-01", "evidence_ids": ["ev-trust"]}],
                "claims": [{"text": "Peggy emailed", "evidence_ids": ["ev-trust"]}],
            },
            {
                "episodes": [],
                "claims": [{"text": "Peggy emailed", "evidence_ids": ["ev-trust"]}],
            },
        ],
        allowed_ids={"ev-trust"},
        email_evidence_ids={"ev-trust"},
    )
    from memorybox.ask.i11a.full_evidence_l1_chunker import group_email_threads

    threaded = group_email_threads(
        [
            {
                "item_id": "e1",
                "subject": "Re: Harbor dinner",
                "addresses": ["peggo417@hotmail.com", "swill01@gmail.com"],
                "timestamp": "2020-01-01",
            },
            {
                "item_id": "e2",
                "subject": "Harbor dinner",
                "addresses": ["swill01@gmail.com", "peggo417@hotmail.com"],
                "timestamp": "2020-01-02",
            },
            {
                "item_id": "e3",
                "subject": "Harbor dinner",
                "addresses": ["other@example.test"],
                "timestamp": "2020-01-03",
            },
        ]
    )
    _check(
        "email_threads_group_by_subject_and_addresses_without_thread_id",
        len(threaded) == 2
        and {frozenset(u.get("item_ids") or []) for u in threaded}
        == {frozenset({"e1", "e2"}), frozenset({"e3"})},
        checks,
        problems,
        detail=[{"ids": u.get("item_ids"), "tid": u.get("thread_id")} for u in threaded],
    )
    hotmail_threaded = group_email_threads(
        [
            {
                "item_id": "h1",
                "subject": "Re: Sunday",
                "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": ""}],
                "people": ["Random Cooccur"],
                "timestamp": "2020-02-01",
            },
            {
                "item_id": "h2",
                "subject": "Sunday",
                "from": "peggo417@hotmail.com",
                "people": ["Someone Else"],
                "timestamp": "2020-02-02",
            },
            {
                "item_id": "h3",
                "subject": "Sunday",
                "from_parsed": [{"address": "other@example.test"}],
                "people": ["Peg Legg"],
                "timestamp": "2020-02-03",
            },
        ]
    )
    _check(
        "email_threads_group_hotmail_from_parsed_without_people_array",
        len(hotmail_threaded) == 2
        and {frozenset(u.get("item_ids") or []) for u in hotmail_threaded}
        == {frozenset({"h1", "h2"}), frozenset({"h3"})},
        checks,
        problems,
        detail=[
            {"ids": u.get("item_ids"), "tid": u.get("thread_id")} for u in hotmail_threaded
        ],
    )
    _check(
        "chunk_merge_dedupes_claims",
        merged.get("ok") and len((merged.get("document") or {}).get("claims") or []) == 1,
        checks,
        problems,
        detail=merged,
    )

    from memorybox.ask.authored import plain_email_body as _plain_body
    from memorybox.ask.i11a.trusted_email_review import (
        EMAIL_REVIEW_SYSTEM,
        LightRow,
        PreparedMessage,
        classify_body_source,
        attach_rfc_neighbors,
        classify_review_authorship,
        encode_replay_binding,
        extract_non_service_text,
        fetch_rfc_neighbor_rows,
        group_conversations,
        looks_like_residual_promo,
        NeighborFetchError,
        NeighborFetchResult,
        participation_exclusion_reason,
        plan_gemma_replay,
        replay_binding_payload,
        _neighbor_row_matches_wanted,
        _light_row_from_neighbor_raw,
        _norm_rfc,
        _RFC_NEIGHBOR_SQL,
        _RFC_NEIGHBOR_PAGE_SIZE,
        _estimate_tokens,
        _has_independent_human_speech,
        _payload_sort_key,
        _parse_sent_at,
        _propose_shorter_interval,
        _sanitation_measurement,
        prepare_trusted_email_review,
        propose_five_year_interval,
        render_model_paste,
        run_trusted_email_review_gemma,
        sanitize_review_tree,
        sanitize_text_block,
        segment_review_body,
        _ECARD_EVENT_MARKER,
        _prepare_message,
    )
    from memorybox.ask.authored import authored_email_text as _authored_text
    from datetime import datetime, timezone as _tz
    from memorybox.ingest.rfc_lookup import (
        extract_rfc_lookup_rows,
        replace_communication_rfc_ids,
    )

    _html = classify_body_source(
        {
            "body_html": "<style>x{}</style><script>alert(1)</script><p>Hello Pegs</p>",
        }
    )
    _check(
        "review_html_strips_style_script_keeps_prose",
        _html[0] == "html_recovered"
        and "Hello Pegs" in _html[1]
        and "alert" not in _html[1]
        and "x{}" not in _html[1],
        checks,
        problems,
        detail=_html,
    )
    _check(
        "review_plain_body_prefers_body_text",
        _plain_body({"body_text": "plain wins", "body_html": "<p>nope</p>"}) == "plain wins",
        checks,
        problems,
    )
    _rows = []
    for year, authored, rfc in (
        (2005, True, False),
        (2008, True, True),
        (2009, True, True),
        (2010, True, True),
        (2011, True, True),
        (2012, True, True),
        (2018, False, False),
    ):
        _rows.append(
            LightRow(
                evidence_id=f"e-{year}",
                sent_at=datetime(year, 6, 1, tzinfo=_tz.utc),
                thread_id="tid-a" if rfc else "",
                rfc_message_id=f"<m{year}@x>" if rfc else "",
                reply_ids=[f"<m{year-1}@x>"] if rfc else [],
                from_addrs={"peggo417@hotmail.com"} if authored else {"other@x.test"},
                addresses={"peggo417@hotmail.com"} if authored else {"other@x.test"},
                peggy_authored=authored,
                subject="Re: Harbor",
                skip=False,
            )
        )
    _prop = propose_five_year_interval(_rows)
    _check(
        "review_proposes_five_year_window_with_most_peggy_authored",
        _prop.get("ok") is True
        and str(_prop.get("start") or "").startswith("2008")
        and str(_prop.get("end") or "").startswith("2012")
        and int(_prop.get("peggy_authored") or 0) >= 5
        and "Peggy-authored" in str(_prop.get("why") or ""),
        checks,
        problems,
        detail=_prop,
    )
    _g = group_conversations(
        [
            LightRow(
                evidence_id="a",
                sent_at=datetime(2009, 1, 1, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<a@x>",
                reply_ids=[],
                from_addrs={"peggo417@hotmail.com"},
                addresses={"peggo417@hotmail.com", "rick@x.test"},
                peggy_authored=True,
                subject="Dinner",
                skip=False,
            ),
            LightRow(
                evidence_id="b",
                sent_at=datetime(2009, 1, 2, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<b@x>",
                reply_ids=["<a@x>"],
                from_addrs={"rick@x.test"},
                addresses={"peggo417@hotmail.com", "rick@x.test"},
                peggy_authored=False,
                subject="Re: Dinner",
                skip=False,
            ),
            LightRow(
                evidence_id="c",
                sent_at=datetime(2009, 2, 1, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="",
                reply_ids=[],
                from_addrs={"sue@x.test"},
                addresses={"sue@x.test", "other@x.test"},
                peggy_authored=False,
                subject="Unrelated",
                skip=False,
            ),
            LightRow(
                evidence_id="d",
                sent_at=datetime(2009, 2, 2, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="",
                reply_ids=[],
                from_addrs={"other@x.test"},
                addresses={"sue@x.test", "other@x.test"},
                peggy_authored=False,
                subject="Unrelated",
                skip=False,
            ),
        ]
    )
    _g_by = {tuple(sorted(x["message_ids"])): x["grouping"] for x in _g}
    _check(
        "review_rfc_reply_is_confirmed_subject_fallback_is_uncertain",
        _g_by.get(tuple(sorted(["a", "b"]))) == "confirmed"
        and _g_by.get(tuple(sorted(["c", "d"]))) == "uncertain",
        checks,
        problems,
        detail=_g,
    )
    _solo = group_conversations(
        [
            LightRow(
                evidence_id="solo",
                sent_at=datetime(2009, 3, 1, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<solo@x>",
                reply_ids=[],
                from_addrs={"peggo417@hotmail.com"},
                addresses={"peggo417@hotmail.com"},
                peggy_authored=True,
                subject="Alone",
                skip=False,
            )
        ]
    )
    _miss = group_conversations(
        [
            LightRow(
                evidence_id="orphan",
                sent_at=datetime(2009, 3, 2, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<orphan@x>",
                reply_ids=["<missing-parent@x>"],
                from_addrs={"peggo417@hotmail.com"},
                addresses={"peggo417@hotmail.com"},
                peggy_authored=True,
                subject="Re: Gone",
                skip=False,
            )
        ]
    )
    _check(
        "review_message_id_alone_is_singleton_not_confirmed_conversation",
        len(_solo) == 1
        and _solo[0]["grouping"] == "singleton"
        and _miss[0]["grouping"] == "missing_parent",
        checks,
        problems,
        detail={"solo": _solo, "miss": _miss},
    )
    _long = "HEADUNIQUE " + ("word " * 3000) + " TAILUNIQUE"
    _seg_plain = segment_review_body(_long)
    _seg_html = classify_body_source(
        {"body_html": "<p>" + "x" * 9000 + " HTMLTAILUNIQUE</p>"}
    )
    _fwd = segment_review_body(
        "See you.\n\nBegin forwarded message:\nFrom: Sam\nYes.\n"
    )
    _check(
        "review_prep_keeps_long_plain_and_html_tails",
        "TAILUNIQUE" in _seg_plain["lead"]
        and "HEADUNIQUE" in _seg_plain["lead"]
        and _seg_html[0] == "html_recovered"
        and "HTMLTAILUNIQUE" in _seg_html[1],
        checks,
        problems,
    )
    _check(
        "review_prep_keeps_short_quotes_and_forward_not_as_sender",
        any("Yes." in str(q.get("body") or "") for q in _fwd["quote_turns"])
        and _fwd["lead"].startswith("See you.")
        and not any(
            str(q.get("from") or "").startswith("Peggy") for q in _fwd["quote_turns"]
        ),
        checks,
        problems,
        detail=_fwd,
    )
    _capped, _ = _authored_text(_long)
    _uncapped, _ = _authored_text(_long, max_chars=None)
    _check(
        "review_prep_lossless_vs_capped_authored_helper",
        "TAILUNIQUE" not in _capped
        and "TAILUNIQUE" in _uncapped
        and "TAILUNIQUE" in _seg_plain["lead"],
        checks,
        problems,
        detail={"capped_len": len(_capped), "uncapped_len": len(_uncapped)},
    )
    _orig = segment_review_body(
        "Ok.\n\n-----Original Message-----\nFrom: Sam Example <sam@example.test>\n"
        "Sent: Mon, 1 Jan 2009 12:00:00 -0600\nSubject: X\n\nYes short.\n"
    )
    _dash_fwd = segment_review_body(
        "Ok.\n\n-----Forwarded message-----\nFrom: Sam Example <sam@example.test>\n"
        "Date: Mon, 1 Jan 2009 12:00:00 -0600\n\nUnique fwd body.\n"
    )
    _hdr = segment_review_body(
        "Ok.\n\nFrom: Sam Example <sam@example.test>\nSent: Monday, January 1, 2009 12:00 PM\n"
        "To: peg@example.test\n\nHeader-block unique.\n"
    )
    _nested = segment_review_body(
        "Thanks.\n\nOn Mon, Jan 1, 2009 at 3:14 PM, Sam Example <sam@example.test> wrote:\n"
        "Outer unique.\n\nOn Sun, Dec 31, 2008 at 9:00 AM, Pat Example <pat@example.test> wrote:\n"
        "Nested unique inner.\n"
    )
    _inline = segment_review_body("See below.\n> inline unique quote\n")
    _html_fwd = classify_body_source(
        {
            "body_html": (
                "<p>See you.</p><p>Begin forwarded message:</p>"
                "<p>From: Sam Example &lt;sam@example.test&gt;</p>"
                "<p>Date: Mon, 1 Jan 2009 12:00:00 -0600</p>"
                "<p>Yes unique html fwd.</p>"
            )
        }
    )
    _html_seg = segment_review_body(_html_fwd[1])
    _check(
        "review_prep_keeps_forward_original_header_nested_inline_html",
        any("Yes short." in str(q.get("body") or "") for q in _orig["quote_turns"])
        and any("Sam Example" in str(q.get("from") or "") for q in _orig["quote_turns"])
        and any("1 Jan 2009" in str(q.get("when") or "") for q in _orig["quote_turns"])
        and any("Unique fwd body." in str(q.get("body") or "") for q in _dash_fwd["quote_turns"])
        and any("Header-block unique." in str(q.get("body") or "") for q in _hdr["quote_turns"])
        and any("Nested unique inner." in str(q.get("body") or "") for q in _nested["quote_turns"])
        and any("inline unique quote" in str(q.get("body") or "") for q in _inline["quote_turns"])
        and _html_fwd[0] == "html_recovered"
        and any("Yes unique html fwd." in str(q.get("body") or "") for q in _html_seg["quote_turns"])
        and _orig["lead"] == "Ok."
        and _inline["lead"] == "See below.",
        checks,
        problems,
        detail={
            "orig": _orig,
            "dash": _dash_fwd,
            "hdr": _hdr,
            "nested": _nested,
            "inline": _inline,
            "html": _html_seg,
        },
    )
    _same_subj = group_conversations(
        [
            LightRow(
                evidence_id="u1",
                sent_at=datetime(2009, 4, 1, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<u1@x>",
                reply_ids=[],
                from_addrs={"a@x.test"},
                addresses={"a@x.test", "b@x.test"},
                peggy_authored=False,
                subject="Picnic",
                skip=False,
            ),
            LightRow(
                evidence_id="u2",
                sent_at=datetime(2009, 4, 2, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<u2@x>",
                reply_ids=[],
                from_addrs={"b@x.test"},
                addresses={"a@x.test", "b@x.test"},
                peggy_authored=False,
                subject="Re: Picnic",
                skip=False,
            ),
        ]
    )
    _check(
        "review_unrelated_shared_subject_is_uncertain_not_confirmed",
        len(_same_subj) == 1 and _same_subj[0]["grouping"] == "uncertain",
        checks,
        problems,
        detail=_same_subj,
    )
    _svc = classify_review_authorship(
        lead=(
            "This is an automated notification. Your card was updated. "
            "Do not reply to this email."
        ),
        from_trusted=True,
    )
    _check(
        "review_service_notice_is_not_personal_speech",
        _svc["kind"] == "service_generated" and _svc["peggy_personal"] is False,
        checks,
        problems,
        detail=_svc,
    )
    _svc_msg = _prepare_message(
        "svc-1",
        {
            "sent_at": "2009-01-01T12:00:00Z",
            "subject": "Notice",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "This is an automated notification. Card updated. "
                "Do not reply to this email."
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _svc_sys, _svc_user, _ = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2008-01-01", "end": "2012-12-31"},
        conversations=[
            {
                "grouping": "singleton",
                "grouping_detail": "identified_message_id_no_reply_edge",
                "messages": [_svc_msg],
            }
        ],
    )
    _check(
        "review_paste_does_not_label_service_as_person_said",
        "not personal speech" in _svc_user
        and "Peggy George said:" not in _svc_user
        and "source text is evidence" in _svc_sys.lower(),
        checks,
        problems,
        detail=_svc_user[:400],
    )
    _weak = classify_review_authorship(
        lead="See you Friday. Click unsubscribe if this was forwarded.",
        from_trusted=True,
    )
    _check(
        "review_weak_keyword_is_unresolved_not_service",
        _weak["kind"] == "unresolved" and _weak["peggy_personal"] is False,
        checks,
        problems,
        detail=_weak,
    )
    _greet = classify_review_authorship(
        lead="Hi Sam — thanks. This is an automated notification. Do not reply to this email.",
        from_trusted=True,
    )
    _check(
        "review_personal_greeting_kept_beside_service_notice",
        _greet["kind"] == "personal_plus_service"
        and _greet["peggy_personal"] is True
        and "Hi Sam" in _greet["personal_lead"],
        checks,
        problems,
        detail=_greet,
    )
    _check(
        "review_service_only_and_unresolved_packets_are_excluded",
        participation_exclusion_reason([_svc_msg])
        == "service_only_no_personal_contribution"
        and participation_exclusion_reason(
            [
                _prepare_message(
                    "weak-1",
                    {
                        "sent_at": "2009-01-01T12:00:00Z",
                        "from_parsed": [
                            {"address": "peggo417@hotmail.com", "display_name": "Peg"}
                        ],
                        "from": "peggo417@hotmail.com",
                        "body_text": (
                            "Dinner Friday. Click unsubscribe if this was forwarded."
                        ),
                    },
                    trusted={"peggo417@hotmail.com"},
                    in_interval=True,
                    packet_texts=[],
                )
            ]
        )
        == "no_attributable_personal_contribution",
        checks,
        problems,
    )
    _tmpl = (
        "Your e-card was delivered. The recipient can open the card from this notice. "
        "This notice describes a card that was sent; it does not include the card artwork. "
        "Card delivery confirmation follows. "
    ) * 6 + "This is an automated notification. Do not reply to this email."
    _long_svc = classify_review_authorship(lead=_tmpl, from_trusted=True)
    _html_svc = _prepare_message(
        "html-svc",
        {
            "sent_at": "2009-01-02T12:00:00Z",
            "subject": "Card notice",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_html": "<p>" + _tmpl + "</p>",
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _thanks = _prepare_message(
        "thanks-1",
        {
            "sent_at": "2009-01-02T13:00:00Z",
            "subject": "Re: Card notice",
            "from_parsed": [{"address": "sam@example.test", "display_name": "Sam"}],
            "from": "Sam <sam@example.test>",
            "body_text": (
                "Thanks for sending that.\n\n-----Original Message-----\n"
                "From: Peg <peggo417@hotmail.com>\n\n" + _tmpl
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _check(
        "review_long_template_before_footer_is_not_personal",
        _long_svc["kind"] == "service_generated"
        and _long_svc["peggy_personal"] is False
        and _html_svc.authorship_kind == "service_generated"
        and _html_svc.peggy_personal is False
        and participation_exclusion_reason([_html_svc, _thanks])
        == "service_only_no_personal_contribution",
        checks,
        problems,
        detail={
            "plain": _long_svc,
            "html_kind": _html_svc.authorship_kind,
            "thanks_kind": _thanks.authorship_kind,
            "quotes": _thanks.quote_dedupe,
        },
    )
    _mention = classify_review_authorship(
        lead="I mailed a Hallmark card Friday after the party.",
        from_trusted=True,
    )
    _check(
        "review_personal_card_mention_is_not_service_exclusion",
        _mention["kind"] == "personal" and _mention["peggy_personal"] is True,
        checks,
        problems,
        detail=_mention,
    )
    _footer_only = classify_review_authorship(
        lead=(
            ("Family seasonal paragraph. " * 50)
            + "This is an automated notification. Do not reply to this email."
        ),
        from_trusted=True,
    )
    _ecard_no_footer = classify_review_authorship(
        lead=(
            "You have received an e-card greeting. "
            "Click here to view your greeting."
        ),
        from_trusted=True,
    )
    _check(
        "review_footer_or_ecard_signals_are_not_personal_without_greeting",
        _footer_only["kind"] == "service_generated"
        and _footer_only["peggy_personal"] is False
        and _ecard_no_footer["kind"] == "service_generated"
        and _ecard_no_footer["peggy_personal"] is False,
        checks,
        problems,
        detail={"footer_only": _footer_only, "ecard_no_footer": _ecard_no_footer},
    )
    _hi_card = classify_review_authorship(
        lead="Hi, your e-card is ready. This is an automated message.",
        from_trusted=True,
    )
    _i_sent = classify_review_authorship(
        lead="I sent you an e-card because I miss you.",
        from_trusted=True,
    )
    _check(
        "review_greeting_plus_card_notice_is_not_personal",
        _hi_card["kind"] == "service_generated"
        and _hi_card["peggy_personal"] is False
        and _i_sent["kind"] == "personal"
        and _i_sent["peggy_personal"] is True,
        checks,
        problems,
        detail={"hi_card": _hi_card, "i_sent": _i_sent},
    )
    _mixed_kept, _mixed_omit = extract_non_service_text(
        "See you Friday.\n\nThis is an automated notification. Do not reply to this email."
    )
    _mixed_msg = _prepare_message(
        "mixed-q",
        {
            "sent_at": "2009-01-04T12:00:00Z",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "Ok.\n\n-----Original Message-----\nFrom: Sam <sam@example.test>\n\n"
                "See you Friday.\n\nThis is an automated notification. "
                "Do not reply to this email."
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _check(
        "review_mixed_quote_keeps_personal_portion",
        _mixed_kept == "See you Friday."
        and "automated" in _mixed_omit
        and "See you Friday." in (_mixed_msg.quoted or "")
        and "automated notification" not in (_mixed_msg.quoted or ""),
        checks,
        problems,
        detail={"kept": _mixed_kept, "quoted": _mixed_msg.quoted, "dedupe": _mixed_msg.quote_dedupe},
    )
    _card_notice = (
        "You received an e-card greeting.\n"
        "View your e-card\n"
        "Click here to view your greeting.\n"
        "https://notify.example.test/click?utm_source=ecard\n"
        "Home | Cards | Gifts\n"
        "Unsubscribe | Privacy Policy\n"
        "This is an automated notification. Do not reply to this email.\n"
    )
    _card_wrap = _prepare_message(
        "card-wrap",
        {
            "sent_at": "2013-05-12T15:00:00Z",
            "subject": "A card for you",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "Thinking of you this week.\n\n"
                + _card_notice
                + "\n-----Original Message-----\n"
                "From: Card Notice <notice@cards.example.test>\n"
                "Sent: Sun, 12 May 2013 10:00:00 +0000\n\n"
                + _card_notice
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _card_reply = _prepare_message(
        "card-reply",
        {
            "sent_at": "2013-05-12T18:00:00Z",
            "subject": "Re: A card for you",
            "from_parsed": [{"address": "sam@example.test", "display_name": "Sam"}],
            "from": "Sam <sam@example.test>",
            "body_text": (
                "That was sweet — thank you.\n\n"
                "> Thinking of you this week.\n"
                "> You received an e-card greeting.\n"
                "> View your e-card\n"
                "> https://notify.example.test/click?utm_source=ecard\n"
                "> Unsubscribe | Privacy Policy\n"
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[_card_wrap.authored, _card_wrap.quoted],
    )
    _, _card_user, _card_cites = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2011-01-01", "end": "2015-12-31"},
        conversations=[
            {
                "grouping": "confirmed",
                "grouping_detail": "shared_thread_id_or_in_reply_to_match",
                "messages": [_card_wrap, _card_reply],
            }
        ],
    )
    _card_low = _card_user.lower()
    _check(
        "review_hallmark_thread_keeps_wrapper_strips_template_and_dupes",
        _card_wrap.authorship_kind == "personal"
        and _card_wrap.peggy_personal is True
        and participation_exclusion_reason([_card_wrap, _card_reply]) is None
        and "Thinking of you this week." in _card_user
        and "That was sweet — thank you." in _card_user
        and "[email_1]" in _card_user
        and "[email_2]" in _card_user
        and {_c.get("cite_as") for _c in _card_cites} == {"email_1", "email_2"}
        and "view your e-card" not in _card_low
        and "unsubscribe" not in _card_low
        and "notify.example.test" not in _card_low
        and "utm_source" not in _card_low
        and "home | cards" not in _card_low
        and _card_user.count("Thinking of you this week.") == 1
        and "I mailed a Hallmark card Friday after the party." 
        in _prepare_message(
            "card-mention",
            {
                "sent_at": "2013-05-13T12:00:00Z",
                "from_parsed": [
                    {"address": "peggo417@hotmail.com", "display_name": "Peg"}
                ],
                "from": "peggo417@hotmail.com",
                "body_text": "I mailed a Hallmark card Friday after the party.",
            },
            trusted={"peggo417@hotmail.com"},
            in_interval=True,
            packet_texts=[],
        ).authored,
        checks,
        problems,
        detail={
            "wrap_kind": _card_wrap.authorship_kind,
            "wrap_authored": _card_wrap.authored,
            "wrap_quoted": _card_wrap.quoted,
            "wrap_dedupe": _card_wrap.quote_dedupe,
            "reply_quoted": _card_reply.quoted,
            "paste_tail": _card_user[-600:],
        },
    )
    _newsletter = (
        "<table><tr><td>SHOP NOW | Home | Deals</td></tr></table>\n"
        "Huge sale this weekend click "
        "https://track.example.test/c?utm_campaign=sale\n"
        "You are receiving this email because you subscribed.\n"
        "Unsubscribe | Privacy Policy | Terms\n"
        "© 2014 Example Shop. All rights reserved.\n"
    )
    _fwd_news = _prepare_message(
        "fwd-news",
        {
            "sent_at": "2014-03-08T12:00:00Z",
            "subject": "Fwd: Weekend sale",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "FYI — this is the store update I mentioned.\n\n"
                "---------- Forwarded message ----------\n"
                "From: Store Newsletter <news@shop.example.test>\n"
                "Date: Sat, 8 Mar 2014 09:00:00 +0000\n"
                "Subject: Weekend sale\n\n"
                + _newsletter
                + "\nOn Fri, 7 Mar 2014, Store Newsletter wrote:\n"
                "You are receiving this email because you subscribed.\n"
                "Unsubscribe | Privacy Policy\n"
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _, _news_user, _news_cites = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2011-01-01", "end": "2015-12-31"},
        conversations=[
            {
                "grouping": "singleton",
                "grouping_detail": "identified_message_id_no_reply_edge",
                "messages": [_fwd_news],
            }
        ],
    )
    _news_low = _news_user.lower()
    _check(
        "review_forwarded_newsletter_keeps_fyi_strips_chrome",
        _fwd_news.authorship_kind == "personal"
        and _fwd_news.peggy_personal is True
        and participation_exclusion_reason([_fwd_news]) is None
        and "FYI — this is the store update I mentioned." in _news_user
        and "[email_1]" in _news_user
        and {_c.get("cite_as") for _c in _news_cites} == {"email_1"}
        and "shop now" not in _news_low
        and "unsubscribe" not in _news_low
        and "privacy policy" not in _news_low
        and "all rights reserved" not in _news_low
        and "you are receiving this email" not in _news_low
        and "track.example.test" not in _news_low
        and "utm_campaign" not in _news_low
        and "<table" not in _news_low
        and "huge sale" not in _news_low,
        checks,
        problems,
        detail={
            "kind": _fwd_news.authorship_kind,
            "authored": _fwd_news.authored,
            "quoted": _fwd_news.quoted,
            "dedupe": _fwd_news.quote_dedupe,
            "paste_tail": _news_user[-600:],
        },
    )
    _long_residual = (
        "View your e-card\n"
        + ("Seasonal joy awaits in this special greeting experience. " * 8)
        + "Share smiles today.\n"
        "This is an automated notification. Do not reply to this email.\n"
    )
    _resid_msg = _prepare_message(
        "resid-1",
        {
            "sent_at": "2013-06-01T12:00:00Z",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": _long_residual,
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _check(
        "review_residual_promo_after_template_is_not_personal",
        _resid_msg.peggy_personal is False
        and _resid_msg.authorship_kind == "service_generated"
        and "Seasonal joy" not in (_resid_msg.authored or ""),
        checks,
        problems,
        detail={"kind": _resid_msg.authorship_kind, "authored": _resid_msg.authored},
    )
    _fp_promo = (
        "We're excited to share our seasonal collection with our members this week.\n"
        "View your e-card\n"
        "This is an automated notification. Do not reply to this email.\n"
    )
    _fp_msg = _prepare_message(
        "resid-fp-1",
        {
            "sent_at": "2013-06-01T12:00:00Z",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": _fp_promo,
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _check(
        "review_first_person_promo_is_not_peggy_speech",
        _fp_msg.peggy_personal is False
        and _fp_msg.authorship_kind == "service_generated"
        and "seasonal collection" not in (_fp_msg.authored or "").lower()
        and looks_like_residual_promo(
            "We're excited to share our seasonal collection with our members this week.",
            had_service_context=True,
        )
        is True
        and looks_like_residual_promo(
            "I mailed a Hallmark card Friday after the party."
        )
        is False
        and looks_like_residual_promo(
            "I sent you an e-card because I miss you."
        )
        is False,
        checks,
        problems,
        detail={"kind": _fp_msg.authorship_kind, "authored": _fp_msg.authored},
    )
    _mixed_line = sanitize_text_block(
        "I picked this for you — view your e-card"
    )
    _check(
        "review_mixed_line_keeps_personal_clause",
        "I picked this for you" in str(_mixed_line.get("text") or "")
        and "view your e-card" not in str(_mixed_line.get("text") or "").lower(),
        checks,
        problems,
        detail=_mixed_line,
    )
    _img_msg = _prepare_message(
        "img-1",
        {
            "sent_at": "2013-06-02T12:00:00Z",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": "Dinner Friday.\n[image]\n[cid:logo@shop]",
            "attachments": [
                {"filename": "picnic.jpg", "content_type": "image/jpeg"}
            ],
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _, _img_user, _ = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2011-01-01", "end": "2015-12-31"},
        conversations=[
            {
                "grouping": "singleton",
                "grouping_detail": "identified_message_id_no_reply_edge",
                "messages": [_img_msg],
            }
        ],
    )
    _check(
        "review_generic_image_stripped_real_attachment_marked",
        "Dinner Friday." in _img_user
        and "[attached image: picnic.jpg/image/jpeg]" in _img_user
        and "[image]" not in _img_user
        and "[cid:logo@shop]" not in _img_user
        and "generic [image]" in EMAIL_REVIEW_SYSTEM.lower(),
        checks,
        problems,
        detail=_img_user[-400:],
    )
    _deep = "UNIQUE_DEEPEST picnic lemonade"
    for _i in range(7):
        _deep = (
            f"Wrap layer {_i}.\n\n-----Original Message-----\n"
            f"From: Nest{_i} <n{_i}@x.test>\n\n{_deep}"
        )
    _deep_tree = sanitize_review_tree(_deep)
    _deep_blob = json.dumps(_deep_tree)
    _check(
        "review_deep_nest_keeps_unique_text_with_uncertainty",
        "UNIQUE_DEEPEST picnic lemonade" in _deep_blob
        and any(
            str(d.get("action") or "").startswith("depth_fallback")
            for d in (_deep_tree.get("omissions") or [])
        )
        and (
            any(
                "nested_forward_depth_uncertain" in str(q.get("uncertainty") or "")
                for q in (_deep_tree.get("quote_turns") or [])
            )
            or "depth_fallback" in _deep_blob
        ),
        checks,
        problems,
        detail={
            "lead": _deep_tree.get("lead"),
            "quotes": _deep_tree.get("quote_turns"),
            "omissions": _deep_tree.get("omissions"),
        },
    )
    _check(
        "review_ecard_event_marker_is_generic",
        "greeting card" in _ECARD_EVENT_MARKER
        and "Hallmark" not in _ECARD_EVENT_MARKER
        and "Threadless" not in _ECARD_EVENT_MARKER,
        checks,
        problems,
    )
    _five_src = inspect.getsource(propose_five_year_interval)
    _check(
        "review_five_year_grouping_is_not_sanitation",
        "Retrieval-window control" in _five_src
        and "Not a substitute for evidence-packet sanitation" in _five_src
        and _prop.get("ok") is True
        and str(_prop.get("start") or "").startswith("2008"),
        checks,
        problems,
        detail=_prop,
    )
    _cst = _payload_sort_key(
        "b", {"sent_at": "2009-01-01T10:00:00-06:00"}
    )
    _utc = _payload_sort_key(
        "a", {"sent_at": "2009-01-01T12:00:00+00:00"}
    )
    _check(
        "review_sort_uses_normalized_timezone",
        _utc[0] < _cst[0]
        and "2009-01-01T10:00:00-06:00" < "2009-01-01T12:00:00+00:00",
        checks,
        problems,
        detail={"utc": str(_utc[0]), "cst": str(_cst[0])},
    )
    _naive_parsed = _parse_sent_at("2009-06-01T12:00:00")
    _aware_parsed = _parse_sent_at("2009-06-01T12:00:00Z")
    _check(
        "review_parse_sent_at_naive_iso_is_utc",
        _naive_parsed is not None
        and _naive_parsed.tzinfo is not None
        and _aware_parsed is not None
        and _naive_parsed == _aware_parsed,
        checks,
        problems,
        detail={"naive": str(_naive_parsed), "aware": str(_aware_parsed)},
    )

    def _light(eid: str, when: datetime) -> LightRow:
        return LightRow(
            evidence_id=eid,
            sent_at=when,
            thread_id="",
            rfc_message_id="",
            reply_ids=[],
            from_addrs={"peggo417@hotmail.com"},
            addresses={"peggo417@hotmail.com"},
            peggy_authored=True,
            subject="x",
            skip=False,
        )

    _shorter_mixed = _propose_shorter_interval(
        [
            _light("naive", datetime(2009, 1, 2, 12, 0, 0)),
            _light("aware", datetime(2009, 1, 1, 12, 0, 0, tzinfo=_tz.utc)),
            _light("offset", datetime(2009, 1, 3, 6, 0, 0, tzinfo=_tz.utc)),
        ],
        datetime(2009, 1, 1, tzinfo=_tz.utc),
        datetime(2009, 12, 31, 23, 59, 59, tzinfo=_tz.utc),
        usable=70,
        estimated_full=100,
    )
    _check(
        "review_shorter_interval_sorts_naive_and_aware",
        _shorter_mixed.get("ok") is True
        and _shorter_mixed.get("start") == "2009-01-01"
        and _shorter_mixed.get("end") == "2009-01-02",
        checks,
        problems,
        detail=_shorter_mixed,
    )
    _linked = attach_rfc_neighbors(
        [
            LightRow(
                evidence_id="child",
                sent_at=datetime(2009, 1, 2, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<child@x>",
                reply_ids=["<parent@x>"],
                from_addrs={"peggo417@hotmail.com"},
                addresses={"peggo417@hotmail.com"},
                peggy_authored=True,
                subject="Re: Dinner",
                skip=False,
            )
        ],
        [
            LightRow(
                evidence_id="parent",
                sent_at=datetime(2009, 1, 1, tzinfo=_tz.utc),
                thread_id="",
                rfc_message_id="<parent@x>",
                reply_ids=[],
                from_addrs={"sam@example.test"},
                addresses={"sam@example.test"},
                peggy_authored=False,
                subject="Dinner",
                skip=False,
            )
        ],
    )
    _check(
        "review_reply_neighbor_without_trusted_from_is_attached",
        {r.evidence_id for r in _linked} == {"child", "parent"},
        checks,
        problems,
        detail=[r.evidence_id for r in _linked],
    )
    _fetch_src = inspect.getsource(fetch_rfc_neighbor_rows)
    _where = _RFC_NEIGHBOR_SQL.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    _check(
        "review_rfc_neighbor_fetch_is_targeted_and_keyset_paged",
        "communication_rfc_ids" in _RFC_NEIGHBOR_SQL
        and "r.rfc_id = ANY(%s)" in _RFC_NEIGHBOR_SQL
        and "regexp_split_to_array" not in _RFC_NEIGHBOR_SQL
        and "jsonb_array_elements" not in _RFC_NEIGHBOR_SQL
        and "payload_json" not in _where
        and "LIMIT 8000" not in _RFC_NEIGHBOR_SQL
        and "OFFSET" not in _RFC_NEIGHBOR_SQL.upper()
        and "{id_clause}" in _RFC_NEIGHBOR_SQL
        and "id > %s" in _fetch_src
        and "NeighborFetchResult" in _fetch_src
        and "rfc_neighbor_query_saturated" not in _fetch_src
        and "statement_timeout" in _fetch_src,
        checks,
        problems,
        detail=_where,
    )

    def _neighbor_catalog_row(
        eid: str,
        rfc: str,
        *,
        in_reply_to: str = "",
        refs: str = "",
    ) -> dict:
        return {
            "id": eid,
            "sent_at": "2009-01-01T12:00:00Z",
            "thread_id": "",
            "rfc_message_id": rfc,
            "in_reply_to": in_reply_to,
            "in_reply_to_ids": [],
            "refs": refs,
            "from_parsed": [],
            "from_header": "other@example.test",
            "subject": "Re: Dinner",
            "ch": "email",
        }

    class _NeighborPageConn:
        def __init__(self, catalog: list[dict]) -> None:
            self.catalog = catalog
            self.executes: list[tuple] = []

        def execute(self, sql, params):
            self.executes.append((sql, params))
            wanted = {_norm_rfc(w) for w in params[0] if _norm_rfc(w)}
            last_id = params[-2] if "id >" in sql else None
            page_size = int(params[-1])
            matched: list[dict] = []
            for raw in sorted(self.catalog, key=lambda r: r["id"]):
                if last_id is not None and raw["id"] <= last_id:
                    continue
                row = _light_row_from_neighbor_raw(raw)
                if _neighbor_row_matches_wanted(row, wanted):
                    matched.append(raw)
                if len(matched) >= page_size:
                    break
            return matched

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    _child = LightRow(
        evidence_id="child",
        sent_at=datetime(2009, 1, 3, tzinfo=_tz.utc),
        thread_id="",
        rfc_message_id="<peggy-child@x.test>",
        reply_ids=["<parent-b@x.test>"],
        from_addrs={"peggo417@hotmail.com"},
        addresses={"peggo417@hotmail.com"},
        peggy_authored=True,
        subject="Re: Dinner",
        skip=False,
    )
    _cat3 = [
        _neighbor_catalog_row("id-a", "<grand@x.test>"),
        _neighbor_catalog_row(
            "id-b",
            "<parent-b@x.test>",
            in_reply_to="<grand@x.test>",
        ),
    ]
    _conn3 = _NeighborPageConn(_cat3)

    def _factory3():
        return _conn3

    _hop3 = fetch_rfc_neighbor_rows([_child], connection_factory=_factory3)
    _linked3 = attach_rfc_neighbors([_child], _hop3.rows)
    _check(
        "review_neighbor_three_hop_chain_attaches_grandparent",
        {r.evidence_id for r in _linked3} == {"child", "id-b", "id-a"}
        and _hop3.neighbor_context_complete is True
        and _hop3.hops_used >= 2,
        checks,
        problems,
        detail={
            "rows": [r.evidence_id for r in _hop3.rows],
            "hops": _hop3.hops_used,
            "pages": _hop3.pages_fetched,
        },
    )

    _big_cat = [
        _neighbor_catalog_row(
            f"id-{i:04d}",
            f"<m{i}@x.test>",
            in_reply_to="<peggy-child@x.test>",
        )
        for i in range(1200)
    ]
    _conn_pages = _NeighborPageConn(_big_cat)

    def _factory_pages():
        return _conn_pages

    _page_res = fetch_rfc_neighbor_rows(
        [_child],
        connection_factory=_factory_pages,
        page_size=500,
        attach_cap=5000,
    )
    _check(
        "review_neighbor_keyset_pages_multiple_filled_pages",
        _page_res.pages_fetched >= 3
        and _page_res.attached_n == 1200
        and all("OFFSET" not in sql.upper() for sql, _ in _conn_pages.executes)
        and any("id >" in sql for sql, _ in _conn_pages.executes[1:]),
        checks,
        problems,
        detail={
            "pages": _page_res.pages_fetched,
            "attached": _page_res.attached_n,
            "executes": len(_conn_pages.executes),
        },
    )

    _cycle_a = LightRow(
        evidence_id="cyc-a",
        sent_at=datetime(2009, 1, 1, tzinfo=_tz.utc),
        thread_id="",
        rfc_message_id="<a@cycle.test>",
        reply_ids=["<b@cycle.test>"],
        from_addrs={"peggo417@hotmail.com"},
        addresses={"peggo417@hotmail.com"},
        peggy_authored=True,
        subject="Re:",
        skip=False,
    )
    _cat_cycle = [
        _neighbor_catalog_row("cyc-b", "<b@cycle.test>", in_reply_to="<a@cycle.test>"),
        _neighbor_catalog_row("cyc-a2", "<a@cycle.test>", in_reply_to="<b@cycle.test>"),
    ]
    _conn_cycle = _NeighborPageConn(_cat_cycle)

    def _factory_cycle():
        return _conn_cycle

    _cycle_res = fetch_rfc_neighbor_rows(
        [_cycle_a],
        connection_factory=_factory_cycle,
        max_hops=8,
    )
    _check(
        "review_neighbor_cycle_terminates_without_duplicate_attach",
        len(_cycle_res.rows) <= 2
        and len({r.evidence_id for r in _cycle_res.rows}) == len(_cycle_res.rows)
        and _conn_cycle.executes,
        checks,
        problems,
        detail={
            "rows": [r.evidence_id for r in _cycle_res.rows],
            "executes": len(_conn_cycle.executes),
            "complete": _cycle_res.neighbor_context_complete,
        },
    )

    _cap_res = fetch_rfc_neighbor_rows(
        [_child],
        connection_factory=_factory_pages,
        page_size=500,
        attach_cap=50,
    )
    _check(
        "review_neighbor_attach_cap_returns_incomplete_metadata",
        _cap_res.neighbor_context_complete is False
        and str(_cap_res.stopping_reason or "").startswith("attach_cap:")
        and _cap_res.attached_n == 50,
        checks,
        problems,
        detail=_cap_res.__dict__,
    )

    class _DbFailConn:
        def execute(self, *_a, **_k):
            raise RuntimeError("db_unreachable")

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def _factory_fail():
        return _DbFailConn()

    try:
        fetch_rfc_neighbor_rows([_child], connection_factory=_factory_fail)
        _db_fail = {"ok": True}
    except RuntimeError as exc:
        _db_fail = {"ok": False, "error": str(exc)}
    _check(
        "review_neighbor_db_error_propagates_for_fail_closed_prepare",
        _db_fail.get("ok") is False and "db_unreachable" in str(_db_fail.get("error")),
        checks,
        problems,
        detail=_db_fail,
    )
    _mixed_rows = extract_rfc_lookup_rows(
        {
            "rfc_message_id": "ABC@Example.TEST",
            "in_reply_to": "<Parent@x.test> <Other@x.test>",
            "in_reply_to_ids": ["<Array@x.test>"],
            "references": "<RefOne@x.test> <RefTwo@x.test>",
        }
    )
    _mixed_ids = {rfc for rfc, _role in _mixed_rows}
    _check(
        "review_rfc_lookup_extracts_mixed_case_and_multiple_parents",
        "<abc@example.test>" in _mixed_ids
        and "<parent@x.test>" in _mixed_ids
        and "<other@x.test>" in _mixed_ids
        and "<array@x.test>" in _mixed_ids
        and "<refone@x.test>" in _mixed_ids
        and ("<abc@example.test>", "own") in _mixed_rows
        and extract_rfc_lookup_rows(
            {
                "rfc_message_id": "ABC@Example.TEST",
                "in_reply_to": "<Parent@x.test> <Other@x.test>",
                "in_reply_to_ids": ["<Array@x.test>"],
                "references": "<RefOne@x.test> <RefTwo@x.test>",
            }
        )
        == _mixed_rows,
        checks,
        problems,
        detail=_mixed_rows,
    )
    _huge = "<" + ("x" * 2000) + "@example.test>"
    _html = "<div class=\"" + ("a" * 2800) + "\">"
    _skipped = extract_rfc_lookup_rows(
        {
            "rfc_message_id": _huge,
            "in_reply_to": _html,
            "references": "<ok@x.test>",
        }
    )
    _check(
        "review_rfc_lookup_skips_oversize_and_html_tokens",
        _skipped == [("<ok@x.test>", "references")]
        and _norm_rfc(_huge) == ""
        and _norm_rfc(_html) == "",
        checks,
        problems,
        detail=_skipped,
    )

    class _LookupMem:
        def __init__(self) -> None:
            self.rows: list[tuple] = []

        def execute(self, sql, params=None):
            text = str(sql)
            if "DELETE FROM communication_rfc_ids" in text:
                eid = params[0]
                self.rows = [r for r in self.rows if r[0] != eid]
            elif "INSERT INTO communication_rfc_ids" in text:
                self.rows.append(tuple(params))
            return []

    _mem = _LookupMem()
    _payload = {
        "rfc_message_id": "<Idem@x.test>",
        "in_reply_to": "<Prev@x.test>",
        "evidence_channel": "email",
    }
    replace_communication_rfc_ids("e1", _payload, conn=_mem)
    first_n = len(_mem.rows)
    replace_communication_rfc_ids("e1", _payload, conn=_mem)
    _check(
        "review_rfc_lookup_backfill_replace_is_idempotent",
        first_n == 2
        and len(_mem.rows) == 2
        and {r[1] for r in _mem.rows} == {"<idem@x.test>", "<prev@x.test>"},
        checks,
        problems,
        detail=_mem.rows,
    )
    _lookup_sqls = [sql for sql, _p in _conn3.executes]
    _check(
        "review_runtime_neighbor_walk_queries_indexed_lookup",
        _lookup_sqls
        and all("communication_rfc_ids" in sql for sql in _lookup_sqls)
        and all("regexp_split_to_array" not in sql for sql in _lookup_sqls)
        and all("jsonb_array_elements" not in sql for sql in _lookup_sqls),
        checks,
        problems,
        detail=_lookup_sqls[:2],
    )
    try:
        fetch_rfc_neighbor_rows([_child], connection_factory=_factory3, stage_deadline_s=0)
        _deadline = {"ok": True}
    except NeighborFetchError as exc:
        _deadline = {"ok": False, "code": exc.code, "detail": exc.detail}
    _check(
        "review_neighbor_stage_deadline_fails_closed",
        _deadline.get("ok") is False
        and _deadline.get("code") == "rfc_neighbor_stage_deadline"
        and "elapsed_ms" in (_deadline.get("detail") or {}),
        checks,
        problems,
        detail=_deadline,
    )
    review_src = inspect.getsource(prepare_trusted_email_review)
    _check(
        "review_neighbors_only_stops_before_packet_and_models",
        "neighbors_only" in review_src
        and "packet_built" in review_src
        and review_src.find("if neighbors_only:")
        < review_src.find("load_payloads")
        and review_src.find("if neighbors_only:")
        < review_src.find("measure_prompt_tokens")
        and review_src.find("if neighbors_only:")
        < review_src.find("render_model_paste"),
        checks,
        problems,
    )
    _comms = (
        __import__("pathlib")
        .Path(__import__("memorybox.ingest.comms_email", fromlist=["*"]).__file__)
        .read_text(encoding="utf-8")
    )
    _check(
        "review_email_ingest_maintains_rfc_lookup",
        "replace_communication_rfc_ids" in _comms
        and _comms.count("replace_communication_rfc_ids") >= 2,
        checks,
        problems,
    )
    _keep_love = PreparedMessage(
        evidence_id="keep-love",
        sent_at=datetime(2009, 1, 1, tzinfo=_tz.utc),
        in_interval=True,
        peggy_authored=True,
        body_kind="plain_text",
        authored="Love you. See you Friday.",
        quoted="",
        quote_kept=False,
        quote_uncertain=False,
        payload={"body_text": "Love you. See you Friday."},
        authorship_kind="personal",
        peggy_personal=True,
    )
    _meas_payloads = {
        "keep-love": {"body_text": "Love you. See you Friday."},
        "ex-bday": {"body_text": "Happy birthday. Hope the party was fun."},
    }
    _meas = _sanitation_measurement(
        payloads=_meas_payloads,
        need_ids=["keep-love", "ex-bday"],
        conversations=[{"messages": [_keep_love]}],
        excluded=[
            {
                "grouping": "singleton",
                "message_ids": ["ex-bday"],
                "reason": "service_only_no_personal_contribution",
            }
        ],
        paste_text="===== SYSTEM INSTRUCTIONS =====\n" + ("wrapper " * 80),
        prompt_tokens=9999,
    )
    _raw_join = "\n".join(
        classify_body_source(_meas_payloads[i])[1] for i in ["keep-love", "ex-bday"]
    )
    _after_join = "Love you. See you Friday."
    _check(
        "review_measurement_same_unit_and_scans_excluded_human",
        _meas.get("token_compare_unit") == "recovered_body_bytes_div_4"
        and _meas.get("body_tokens_before_estimate") == _estimate_tokens(_raw_join)
        and _meas.get("body_tokens_after_estimate") == _estimate_tokens(_after_join)
        and _meas.get("tokens_after") == _estimate_tokens(_after_join)
        and _meas.get("paste_tokens_reported") == 9999
        and _meas.get("paste_tokens_reported") != _meas.get("body_tokens_after_estimate")
        and _meas.get("human_evidence_loss_includes_excluded") is True
        and set(_meas.get("human_evidence_loss_scanned_ids") or [])
        == {"keep-love", "ex-bday"}
        and "ex-bday" in (_meas.get("human_evidence_ids_lost") or [])
        and "keep-love" not in (_meas.get("human_evidence_ids_lost") or [])
        and _has_independent_human_speech("Happy birthday.")
        and _has_independent_human_speech("Love you.")
        and not _has_independent_human_speech(
            "We're excited to share our seasonal collection with our members."
        )
        and _meas.get("human_evidence_loss_required_zero") is False,
        checks,
        problems,
        detail=_meas,
    )
    _keep_q = _prepare_message(
        "keep-q",
        {
            "sent_at": "2009-01-03T12:00:00Z",
            "subject": "Dinner",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "See you Friday.\n\n-----Original Message-----\n"
                "From: Sam <sam@example.test>\n\nCan you come Friday?\n"
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _omit_q = _prepare_message(
        "omit-q",
        {
            "sent_at": "2009-01-03T13:00:00Z",
            "subject": "Dinner",
            "from_parsed": [{"address": "peggo417@hotmail.com", "display_name": "Peg"}],
            "from": "peggo417@hotmail.com",
            "body_text": (
                "See you Friday.\n\n-----Original Message-----\n"
                "From: Notice <notice@example.test>\n\n" + _tmpl
            ),
        },
        trusted={"peggo417@hotmail.com"},
        in_interval=True,
        packet_texts=[],
    )
    _, _keep_user, _ = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2008-01-01", "end": "2012-12-31"},
        conversations=[
            {
                "grouping": "singleton",
                "grouping_detail": "identified_message_id_no_reply_edge",
                "messages": [_keep_q],
            }
        ],
    )
    _, _omit_user, _ = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2008-01-01", "end": "2012-12-31"},
        conversations=[
            {
                "grouping": "singleton",
                "grouping_detail": "identified_message_id_no_reply_edge",
                "messages": [_omit_q],
            }
        ],
    )
    _, _bad_user, _ = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2008-01-01", "end": "2012-12-31"},
        conversations=[
            {
                "grouping": "confirmed",
                "grouping_detail": "shared_thread_id_or_in_reply_to_match",
                "messages": [_html_svc, _thanks],
            }
        ],
    )
    _check(
        "review_paste_keeps_genuine_quotes_omits_service_template",
        "See you Friday." in _keep_user
        and "Can you come Friday?" in _keep_user
        and "See you Friday." in _omit_user
        and "Your e-card was delivered" not in _omit_user
        and any(
            d.get("action") == "omitted_service_notice" for d in _omit_q.quote_dedupe
        )
        and any(
            d.get("action") == "omitted_service_notice" for d in _thanks.quote_dedupe
        ),
        checks,
        problems,
        detail={"keep": _keep_user[-400:], "omit": _omit_user[-400:]},
    )
    _check(
        "review_paste_excludes_service_exchange_from_personal_label",
        participation_exclusion_reason([_html_svc, _thanks]) is not None
        and "personal greeting" not in _bad_user
        and "Peggy George said:" not in _bad_user,
        checks,
        problems,
        detail=_bad_user[:500],
    )
    from memorybox.providers.llm._ollama_http import ollama_chat_request_payload

    _req = ollama_chat_request_payload(
        "gemma4:26b", "sys", "user", format_json=True, num_ctx=32768
    )
    _check(
        "review_ollama_request_serializes_num_ctx",
        (_req.get("options") or {}).get("num_ctx") == 32768,
        checks,
        problems,
        detail=_req.get("options"),
    )
    import tempfile
    from pathlib import Path as _Ptmp

    def _write_bound_replay(td, *, system: str, user: str, source_map: dict) -> str:
        binding = encode_replay_binding(source_map)
        paste = (
            "===== SYSTEM INSTRUCTIONS =====\n"
            + system
            + "\n\n===== REPLAY BINDING =====\n"
            + binding
            + "\n\n===== USER QUESTION AND EVIDENCE =====\n"
            + user
            + "\n"
        )
        (td / "MODEL_PASTE.txt").write_text(paste, encoding="utf-8")
        digest = __import__("hashlib").sha256(paste.encode("utf-8")).hexdigest()
        written = dict(source_map)
        written["frozen_input_sha256"] = digest
        (td / "SOURCE_MAP.json").write_text(json.dumps(written), encoding="utf-8")
        return digest

    _td = _Ptmp(tempfile.mkdtemp())
    (_td / "MODEL_PASTE.txt").write_text(
        "===== SYSTEM INSTRUCTIONS =====\nsys\n\n"
        "===== USER QUESTION AND EVIDENCE =====\nuser\n",
        encoding="utf-8",
    )
    _unbound_hash = __import__("hashlib").sha256(
        (_td / "MODEL_PASTE.txt").read_bytes()
    ).hexdigest()
    (_td / "SOURCE_MAP.json").write_text(
        json.dumps(
            {
                "frozen_input_sha256": _unbound_hash,
                "budget": {
                    "capacity_certainty": "observed_env",
                    "proposed_request": {
                        "model": "gemma4:26b",
                        "num_ctx": 32768,
                        "output_reserve": 2048,
                    },
                    "prompt_tokens": 10,
                    "usable_input_tokens": 28000,
                },
            }
        ),
        encoding="utf-8",
    )
    _plan_missing = plan_gemma_replay(paste_dir=_td, require_hash=_unbound_hash)
    _check(
        "review_replay_plan_refuses_missing_binding",
        _plan_missing.get("ok") is False
        and "replay_binding_missing" in str(_plan_missing.get("error") or ""),
        checks,
        problems,
        detail=_plan_missing,
    )
    _paste_hash = _write_bound_replay(
        _td,
        system="sys",
        user="user",
        source_map={
            "budget": {
                "capacity_certainty": "unknown",
                "proposed_request": {
                    "model": "gemma4:26b",
                    "num_ctx": None,
                    "output_reserve": 2048,
                },
                "prompt_tokens": 10,
                "usable_input_tokens": 100,
            }
        },
    )
    _plan_bad = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _check(
        "review_replay_plan_refuses_unknown_capacity",
        _plan_bad.get("ok") is False and "unknown_capacity" in str(_plan_bad.get("error")),
        checks,
        problems,
        detail=_plan_bad,
    )
    _ok_map = {
        "budget": {
            "capacity_certainty": "observed_env",
            "proposed_request": {
                "model": "gemma4:26b",
                "provider": "ollama",
                "num_ctx": 32768,
                "temperature": 0.1,
                "output_reserve": 2048,
            },
            "prompt_tokens": 10,
            "usable_input_tokens": 28000,
        }
    }
    _paste_hash = _write_bound_replay(_td, system="sys", user="user", source_map=_ok_map)
    _plan_ok = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _req_msgs = (_plan_ok.get("request_payload") or {}).get("messages") or []
    _sys_joined = " ".join(
        str(m.get("content") or "") for m in _req_msgs if m.get("role") == "system"
    )
    _check(
        "review_replay_plan_serializes_reviewed_num_ctx",
        _plan_ok.get("ok") is True
        and ((_plan_ok.get("request_payload") or {}).get("options") or {}).get("num_ctx")
        == 32768
        and ((_plan_ok.get("request_payload") or {}).get("options") or {}).get("num_predict")
        == 2048
        and _plan_ok.get("provider") == "ollama"
        and _plan_ok.get("chunking") is False
        and "REPLAY BINDING" not in _sys_joined
        and _plan_ok.get("replay_binding") == replay_binding_payload(_ok_map),
        checks,
        problems,
        detail=_plan_ok.get("request_payload"),
    )
    _mutated = json.loads((_td / "SOURCE_MAP.json").read_text(encoding="utf-8"))
    _mutated["budget"]["proposed_request"]["num_ctx"] = 99991
    (_td / "SOURCE_MAP.json").write_text(json.dumps(_mutated), encoding="utf-8")
    _plan_mut = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _check(
        "review_replay_binding_refuses_mutated_sidecar_settings",
        _plan_mut.get("ok") is False
        and "source_map_replay_binding_mismatch" in str(_plan_mut.get("error") or ""),
        checks,
        problems,
        detail=_plan_mut,
    )
    _paste_hash = _write_bound_replay(_td, system="sys", user="user", source_map=_ok_map)
    (_td / "SOURCE_MAP.json").write_text(
        json.dumps(
            {
                "frozen_input_sha256": "deadbeef" * 8,
                "budget": _ok_map["budget"],
            }
        ),
        encoding="utf-8",
    )
    _plan_side = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _check(
        "review_replay_plan_refuses_unbound_source_map",
        _plan_side.get("ok") is False
        and "source_map_hash_mismatch" in str(_plan_side.get("error") or ""),
        checks,
        problems,
        detail=_plan_side,
    )
    _paste_hash = _write_bound_replay(
        _td,
        system="sys",
        user="user",
        source_map={
            "budget": {
                "capacity_certainty": "advertised_only",
                "proposed_request": {
                    "model": "gemma4:26b",
                    "num_ctx": 99991,
                    "output_reserve": 2048,
                },
                "prompt_tokens": 10,
                "usable_input_tokens": 28000,
            }
        },
    )
    _plan_adv = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _check(
        "review_replay_plan_refuses_advertised_only_without_env",
        _plan_adv.get("ok") is False
        and "advertised_only" in str(_plan_adv.get("error") or ""),
        checks,
        problems,
        detail=_plan_adv,
    )
    _paste_hash = _write_bound_replay(
        _td,
        system="sys",
        user="user",
        source_map={
            "budget": {
                "capacity_certainty": "observed_env",
                "proposed_request": {
                    "model": "gemma4:26b",
                    "num_ctx": 8192,
                    "output_reserve": 2048,
                },
                "prompt_tokens": 20000,
                "usable_input_tokens": 4000,
            }
        },
    )
    _plan_big = plan_gemma_replay(paste_dir=_td, require_hash=_paste_hash)
    _check(
        "review_replay_plan_refuses_oversize_without_truncate",
        _plan_big.get("ok") is False
        and "oversize" in str(_plan_big.get("error") or ""),
        checks,
        problems,
        detail=_plan_big,
    )
    _sys, _user, _cites = render_model_paste(
        ask="tell me what you know about this person",
        person_name="Peggy George",
        trusted={"peggo417@hotmail.com"},
        interval={"start": "2008-01-01", "end": "2012-12-31"},
        conversations=[
            {
                "grouping": "confirmed",
                "grouping_detail": "rfc_thread_or_in_reply_to",
                "messages": [
                    PreparedMessage(
                        evidence_id="ev-1",
                        sent_at=datetime(2009, 1, 1, tzinfo=_tz.utc),
                        in_interval=True,
                        peggy_authored=True,
                        body_kind="html_recovered",
                        authored="See you Friday.",
                        quoted="",
                        quote_kept=False,
                        quote_uncertain=False,
                        payload={
                            "sent_at": "2009-01-01T12:00:00Z",
                            "subject": "Dinner",
                            "from_parsed": [
                                {
                                    "display_name": "Peg",
                                    "address": "peggo417@hotmail.com",
                                }
                            ],
                            "from": "peggo417@hotmail.com",
                        },
                        authorship_kind="personal",
                        peggy_personal=True,
                    ),
                    PreparedMessage(
                        evidence_id="ev-2",
                        sent_at=datetime(2007, 12, 31, tzinfo=_tz.utc),
                        in_interval=False,
                        peggy_authored=False,
                        body_kind="plain_text",
                        authored="Can you come?",
                        quoted="",
                        quote_kept=False,
                        quote_uncertain=False,
                        payload={
                            "sent_at": "2007-12-31T12:00:00Z",
                            "subject": "Dinner",
                            "from_parsed": [
                                {"display_name": "Rick", "address": "rick@x.test"}
                            ],
                            "from": "Rick <rick@x.test>",
                        },
                        authorship_kind="quoted_or_other",
                        peggy_personal=False,
                    ),
                ],
            }
        ],
    )
    _check(
        "review_paste_is_dated_speaker_conversations_with_linked_context",
        "BEGIN CONVERSATION:" in _user
        and "Peggy George said: [email_1]" in _user
        and "Rick said:" in _user
        and "linked context; outside the candidate interval" in _user
        and "See you Friday." in _user
        and "people:" not in _user.lower()
        and "family historian" in _sys
        and "narrator field must be readable" in _sys
        and "ASK:" in _user,
        checks,
        problems,
        detail=_user[:500],
    )
    _refused = run_trusted_email_review_gemma(
        paste_dir="/tmp/missing-review-dir",
        require_hash="abc",
    )
    _check(
        "review_gemma_replay_refuses_missing_paste_or_hash",
        _refused.get("ok") is False
        and "model_paste_missing" in str(_refused.get("error") or ""),
        checks,
        problems,
        detail=_refused,
    )
    review_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_email_review",
            fromlist=["prepare_trusted_email_review"],
        ).prepare_trusted_email_review
    )
    replay_src = inspect.getsource(run_trusted_email_review_gemma)
    plan_src = inspect.getsource(plan_gemma_replay)
    replay_all = replay_src + "\n" + plan_src
    _check(
        "review_prepare_has_no_model_and_no_sample_cap",
        "models_called" in review_src
        and "SINGLE_PASS_EMAIL_RETRIEVE_CAP" not in review_src
        and "SINGLE_PASS_EMAIL_BODY_CHARS" not in review_src
        and "fe8a128c" in review_src
        and "run_trusted_evidence_pipeline" not in review_src,
        checks,
        problems,
    )
    _check(
        "review_prepare_fail_closed_on_neighbor_fetch",
        "rfc_neighbor_fetch_failed" in review_src
        and "fail_closed" in review_src
        and "extras = []" not in review_src
        and "neighbor_context_complete" in review_src
        and "encode_replay_binding" in review_src
        and "_REPLAY_BIND_MARK" in review_src,
        checks,
        problems,
    )
    _check(
        "review_replay_is_ollama_only_no_pipeline_no_refreeze",
        '"provider": "ollama"' in replay_all
        and "run_trusted_evidence_pipeline" not in replay_all
        and "chunking" in replay_all
        and "hash_mismatch" in replay_all
        and "num_ctx" in replay_all
        and "HistorianCloud" not in replay_all
        and "_CloudOpenAICompatChat" not in replay_all,
        checks,
        problems,
    )
    main_txt = (
        __import__("pathlib").Path(__file__).resolve().parents[1] / "__main__.py"
    ).read_text(encoding="utf-8")
    gi_txt = (
        __import__("pathlib").Path(__file__).resolve().parents[2] / ".gitignore"
    ).read_text(encoding="utf-8")
    prep_cmd = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "tools"
        / "flightsim-prepare-trusted-email-review.cmd"
    ).read_text(encoding="utf-8", errors="replace")
    _check(
        "review_cli_and_gitignore_keep_paste_off_github",
        "prepare-trusted-email-review" in main_txt
        and "prepare-trusted-email-review-chunks" in main_txt
        and "run-trusted-email-review-gemma" in main_txt
        and "run-trusted-email-review-chunk-gemma" in main_txt
        and "trusted-email-review/**" in gi_txt,
        checks,
        problems,
    )
    from memorybox.ask.i11a.trusted_email_review_chunks import (
        prepare_trusted_email_review_chunks,
        plan_trusted_email_review_chunk_gemma,
    )

    def _write_review_parent(td: _Ptmp, *, conversations, cites_extra=None) -> tuple[str, dict]:
        system, user, cites = render_model_paste(
            ask="tell me what you know about this person",
            person_name="Peggy George",
            trusted={"peggo417@hotmail.com"},
            interval={"start": "2008-01-01", "end": "2012-12-31"},
            conversations=conversations,
        )
        budget = {
            "capacity_certainty": "advertised_only",
            "proposed_request": {
                "model": "gemma4:26b",
                "provider": "ollama",
                "num_ctx": 262144,
                "num_predict": 4096,
                "output_reserve": 4096,
                "temperature": 0.1,
            },
            "prompt_tokens": 500000,
            "usable_input_tokens": 255808,
        }
        smap = {
            "budget": budget,
            "citations": cites,
            "conversations": cites_extra or [],
            "person_name": "Peggy George",
        }
        digest = _write_bound_replay(td, system=system, user=user, source_map=smap)
        smap["frozen_input_sha256"] = digest
        smap["conversations"] = [
            {
                "grouping": c.get("grouping"),
                "message_ids": [m.evidence_id for m in c["messages"]],
            }
            for c in conversations
        ]
        (td / "SOURCE_MAP.json").write_text(json.dumps(smap), encoding="utf-8")
        return digest, smap

    def _msg(eid: str, when: str, body: str) -> PreparedMessage:
        return PreparedMessage(
            evidence_id=eid,
            sent_at=_parse_sent_at(when),
            in_interval=True,
            peggy_authored=True,
            body_kind="plain_text",
            authored=body,
            quoted="",
            quote_kept=False,
            quote_uncertain=False,
            payload={
                "sent_at": when,
                "body_text": body,
                "from_parsed": [{"normalized": "peggo417@hotmail.com"}],
            },
            authorship_kind="personal",
            peggy_personal=True,
        )

    _chunk_td = _Ptmp(tempfile.mkdtemp())
    _early = _msg("e-2009", "2009-03-01T12:00:00Z", "Early note. " + ("a" * 4000))
    _mid = _msg("e-2010", "2010-06-01T12:00:00Z", "Middle note. " + ("b" * 4000))
    _late = _msg("e-2011", "2011-09-01T12:00:00Z", "Late note. " + ("c" * 4000))
    _parent_hash, _ = _write_review_parent(
        _chunk_td,
        conversations=[
            {
                "grouping": "singleton",
                "messages": [_late],
            },
            {
                "grouping": "singleton",
                "messages": [_early],
            },
            {
                "grouping": "singleton",
                "messages": [_mid],
            },
        ],
    )
    _chunk_a = prepare_trusted_email_review_chunks(
        paste_dir=_chunk_td,
        require_hash=_parent_hash,
        target_estimated_tokens=2500,
    )
    _chunk_b = prepare_trusted_email_review_chunks(
        paste_dir=_chunk_td,
        require_hash=_parent_hash,
        target_estimated_tokens=2500,
    )
    _manifest_a = json.loads((_chunk_td / "CHUNK_MANIFEST.json").read_text(encoding="utf-8"))
    _manifest_b = json.loads((_chunk_td / "CHUNK_MANIFEST.json").read_text(encoding="utf-8"))
    _first_dates = [
        (c.get("date_range") or {}).get("start") for c in (_manifest_a.get("chunks") or [])
    ]
    _expected_dates = ["2009-03-01", "2010-06-01", "2011-09-01"]
    _check(
        "review_chunks_order_conversations_chronologically",
        _chunk_a.get("ok") is True
        and int(_chunk_a.get("chunk_count") or 0) >= 2
        and _first_dates == sorted(_first_dates)
        and _first_dates == _expected_dates
        and _manifest_a["evidence_id_audit"]["ok"] is True,
        checks,
        problems,
        detail={"dates": _first_dates, "chunks": _chunk_a.get("chunk_count")},
    )
    _within_target = all(
        int(c.get("estimated_input_tokens") or 0) <= 2500
        or bool(c.get("unavoidable_oversize"))
        for c in (_manifest_a.get("chunks") or [])
    )
    _intact = all(
        int(c.get("conversation_count") or 0) == 1 and int(c.get("message_count") or 0) == 1
        for c in (_manifest_a.get("chunks") or [])
    )
    _check(
        "review_chunks_keep_intact_conversations_when_fitting",
        _intact and not (_manifest_a.get("conversation_splits") or []),
        checks,
        problems,
        detail=_manifest_a.get("chunks"),
    )
    _check(
        "review_chunks_respect_token_target_unless_unavoidable",
        _within_target,
        checks,
        problems,
        detail=[c.get("estimated_input_tokens") for c in (_manifest_a.get("chunks") or [])],
    )
    _check(
        "review_chunks_evidence_ids_complete_no_dupes",
        _manifest_a["evidence_id_audit"]["ok"] is True
        and not _manifest_a["evidence_id_audit"]["missing_cite_as"]
        and not _manifest_a["evidence_id_audit"]["duplicate_cite_as"],
        checks,
        problems,
        detail=_manifest_a.get("evidence_id_audit"),
    )
    _check(
        "review_chunks_are_deterministic",
        _chunk_b.get("ok") is True
        and _manifest_a.get("chunks") == _manifest_b.get("chunks"),
        checks,
        problems,
    )
    _chunk1_text = (_chunk_td / "CHUNK_001_MODEL_PASTE.txt").read_text(encoding="utf-8")
    _check(
        "review_chunk_prompt_warns_partial_evidence",
        "chunk 1 of" in _chunk1_text.lower()
        and "partial evidence" in _chunk1_text.lower()
        and "incomplete by design" in _chunk1_text.lower()
        and "No chunking" not in _chunk1_text.split("===== USER QUESTION AND EVIDENCE =====", 1)[0],
        checks,
        problems,
    )
    _bad_parent = prepare_trusted_email_review_chunks(
        paste_dir=_chunk_td,
        require_hash="0" * 64,
        target_estimated_tokens=2500,
    )
    _check(
        "review_chunks_fail_closed_on_parent_hash_mismatch",
        _bad_parent.get("ok") is False
        and "parent_hash_mismatch" in str(_bad_parent.get("error") or ""),
        checks,
        problems,
        detail=_bad_parent,
    )
    _chunk1_sha = _manifest_a["chunks"][0]["chunk_sha256"]
    _plan_ctx = plan_trusted_email_review_chunk_gemma(
        paste_dir=_chunk_td,
        require_parent_hash=_parent_hash,
        chunk_index=1,
        require_chunk_hash=_chunk1_sha,
    )
    _check(
        "review_chunk_runner_requires_fev2_num_ctx",
        _plan_ctx.get("ok") is False
        and "fev2_num_ctx_required" in str(_plan_ctx.get("error") or ""),
        checks,
        problems,
        detail=_plan_ctx,
    )
    _check(
        "review_chunk_prepare_never_calls_models",
        _chunk_a.get("models_called") is False and "models_called" in _manifest_a,
        checks,
        problems,
    )
    _smap_td = _Ptmp(tempfile.mkdtemp())
    _smap_hash, _ = _write_review_parent(
        _smap_td,
        conversations=[
            {"grouping": "singleton", "messages": [_early]},
        ],
    )
    _smap_bad = json.loads((_smap_td / "SOURCE_MAP.json").read_text(encoding="utf-8"))
    _smap_bad["frozen_input_sha256"] = "0" * 64
    (_smap_td / "SOURCE_MAP.json").write_text(json.dumps(_smap_bad), encoding="utf-8")
    _bad_smap = prepare_trusted_email_review_chunks(
        paste_dir=_smap_td,
        require_hash=_smap_hash,
        target_estimated_tokens=2500,
    )
    _check(
        "review_chunks_fail_closed_on_source_map_hash_mismatch",
        _bad_smap.get("ok") is False
        and "source_map_hash_mismatch" in str(_bad_smap.get("error") or ""),
        checks,
        problems,
        detail=_bad_smap,
    )
    _split_td = _Ptmp(tempfile.mkdtemp())
    _big_turns = [
        _msg(f"big-{i}", f"2012-0{(i % 9) + 1}-01T12:00:00Z", "X" * 5000)
        for i in range(8)
    ]
    _split_hash, _ = _write_review_parent(
        _split_td,
        conversations=[
            {
                "grouping": "confirmed",
                "grouping_detail": "shared_thread_id_or_in_reply_to_match",
                "messages": _big_turns,
            }
        ],
    )
    _split_res = prepare_trusted_email_review_chunks(
        paste_dir=_split_td,
        require_hash=_split_hash,
        target_estimated_tokens=6000,
    )
    _split_manifest = json.loads((_split_td / "CHUNK_MANIFEST.json").read_text(encoding="utf-8"))
    _check(
        "review_chunks_split_oversized_conversation_at_turns",
        _split_res.get("ok") is True
        and int(_split_res.get("chunk_count") or 0) >= 2
        and (_split_manifest.get("conversation_splits") or [])
        and (
            "CONTINUATION" in (_split_td / "CHUNK_001_MODEL_PASTE.txt").read_text(encoding="utf-8")
            or "CONTINUATION"
            in (_split_td / "CHUNK_002_MODEL_PASTE.txt").read_text(encoding="utf-8")
        ),
        checks,
        problems,
        detail=_split_manifest.get("conversation_splits"),
    )
    _check(
        "review_prepare_cmd_refuses_unrelated_merge_and_rebase_fallback",
        "GIT_MERGE_AUTOEDIT=no" in prep_cmd
        and "core.editor=true" in prep_cmd
        and "--no-edit" in prep_cmd
        and "GIT_EDITOR=true" in prep_cmd
        and "abbrev-ref" in prep_cmd
        and "Will not finish a merge or prepare on the wrong branch." in prep_cmd
        and "working tree is dirty" in prep_cmd
        and "Will not commit --continue" in prep_cmd
        and "Will not pull, abort that rebase, or prepare." in prep_cmd
        and "Will not abort, merge, or prepare" in prep_cmd
        and "git rebase --abort" not in prep_cmd
        and 'commit --no-edit -m "sync(flightsim):' not in prep_cmd
        and 'merge --no-edit -m "sync(flightsim):' not in prep_cmd,
        checks,
        problems,
    )
    _check(
        "review_gate_does_not_auto_prepare_or_run_models",
        "prepare-trusted-email-review" not in gate_txt
        and "-Step Chunks" not in gate_txt
        and "Phase 3 is not authorized" in gate_txt,
        checks,
        problems,
    )

    try:
        from memorybox.person.trusted_identity_e2e import run_trusted_identity_db_e2e

        db_e2e = run_trusted_identity_db_e2e()
        _check(
            "local_db_trusted_retrieve_scope",
            bool(db_e2e.get("ok")),
            checks,
            problems,
            detail=db_e2e.get("problems") or db_e2e,
        )
    except Exception as exc:  # noqa: BLE001
        _check(
            "local_db_trusted_retrieve_scope",
            False,
            checks,
            problems,
            detail=f"{type(exc).__name__}:{exc}",
        )

    payload = _phase1_gate_envelope(
        flightsim_requested=bool(flightsim),
        flightsim_report=flightsim_report,
        checks=checks,
        problems=problems,
    )
    payload["ok"] = not problems
    if flightsim:
        try:
            payload["gate_path"] = _write_phase1_gate_files(payload)
        except Exception:  # noqa: BLE001
            pass
    return payload


def _trusted_identity_runtime(*, flightsim_requested: bool) -> dict[str, Any]:
    import os
    import socket

    def _truthy(name: str) -> bool:
        return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}

    allow_dev = _truthy("MEMORYBOX_ALLOW_DEV_DEFAULTS")
    p1 = _truthy("MEMORYBOX_P1_RUNTIME_HOST")
    return {
        "hostname": socket.gethostname(),
        "p1_runtime_host": p1,
        "allow_dev_defaults": allow_dev,
        "database_url_set": bool((os.environ.get("MEMORYBOX_DATABASE_URL") or "").strip()),
        "flightsim": bool(flightsim_requested) and p1 and not allow_dev,
    }
