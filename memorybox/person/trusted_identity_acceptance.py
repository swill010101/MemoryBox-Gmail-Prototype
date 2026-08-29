"""Acceptance for trusted-for-retrieval identity (Phase 1)."""
from __future__ import annotations

import inspect
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
    _check(
        "flightsim_gate_runs_phase1_prove_before_pipeline",
        "prove-trusted-identity-retrieval --flightsim" in gate_txt
        and "errorlevel 1" in gate_txt
        and "verify-trusted-identity-gate.py" in gate_txt
        and gate_txt.find("prove-trusted-identity-retrieval")
        < gate_txt.find("verify-trusted-identity-gate.py")
        < gate_txt.find("run-trusted-evidence-pipeline")
        < gate_txt.find("verify-trusted-fev2-reports.py")
        < gate_txt.find("run-trusted-fev2-chunked-models --from-dir")
        and "evidence(flightsim): trusted-identity Phase 1 gate" in gate_txt
        and "TRUSTED_IDENTITY_GATE.json" in gate_txt
        and "git pull --rebase" in gate_txt
        and "--force" not in gate_txt,
        checks,
        problems,
    )
    _check(
        "flightsim_gate_fails_closed_on_pipeline_skip",
        "verify-trusted-fev2-reports.py" in gate_txt
        and "if errorlevel 1" in gate_txt[gate_txt.find("run-trusted-evidence-pipeline") :]
        and gate_txt.find("run-trusted-evidence-pipeline")
        < gate_txt.find("verify-trusted-fev2-reports.py"),
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
    _check(
        "app_env_loader_strips_quotes_and_cr",
        parsed_env.get("MEMORYBOX_CLOUD_LLM_MODEL") == "sol-quoted",
        checks,
        problems,
        detail=parsed_env,
    )
    _check(
        "flightsim_gate_clears_allow_dev_before_prove",
        "set MEMORYBOX_P1_RUNTIME_HOST=1" in gate_txt
        and "set MEMORYBOX_ALLOW_DEV_DEFAULTS=" in gate_txt
        and "MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333" in gate_txt
        and gate_txt.find("set MEMORYBOX_ALLOW_DEV_DEFAULTS=")
        < gate_txt.find("prove-trusted-identity-retrieval --flightsim")
        and gate_txt.find("MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333")
        < gate_txt.find("python -m memorybox migrate")
        and "export-memorybox-app-env.py" in gate_txt
        and "MEMORYBOX_OLLAMA_BASE_URL=http://127.0.0.1:11434" in gate_txt,
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
        and main_src.count("_apply_trusted_identity_flightsim_env") >= 3,
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
    _check(
        "constraint_filter_email_omits_people_array",
        "from_header" in cons_src
        and "Never people[]" in cons_src
        and 'h.people or []' in cons_src,
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
        and "format_cloud_paste" in freeze_src,
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
        and "retrieve_eligible_hits" not in freeze_src,
        checks,
        problems,
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
    _check(
        "pipeline_writes_phase2_human_summary",
        "phase2_summary" in pipe_src
        and "TRUSTED-EVIDENCE PHASE 2 SUMMARY" in phase2_sum_src,
        checks,
        problems,
    )
    _check(
        "pipeline_blocks_chunk_models_until_both_single_pass",
        "blocked_until_both_single_pass" in pipe_src,
        checks,
        problems,
    )
    _check(
        "pipeline_defers_larger_set_until_both_single_pass",
        "after_both_single_pass_reports_only" in pipe_src
        and "complete_trusted=True" not in pipe_src
        and "run_chunked_models_after_single_pass" not in pipe_src
        and "after_phase2_verifier" in pipe_src,
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
