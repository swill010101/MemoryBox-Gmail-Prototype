"""Acceptance for trusted-for-retrieval identity (Phase 1)."""
from __future__ import annotations

from typing import Any

from memorybox.person.comm_identity import _header_records, corroborate_email_candidate
from memorybox.person.trusted_identity import classify_contact_trust


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


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
    _check(
        "unknown_provenance_fail_closed",
        unknown.get("retrieval_trust") == "untrusted",
        checks,
        problems,
        detail=unknown,
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

    import inspect

    from memorybox.ask import retrieve as retrieve_mod
    from memorybox.person import comm_identity as ci

    keep_src = inspect.getsource(retrieve_mod.search_email_messages)
    header_src = inspect.getsource(ci._header_records)
    expand_src = inspect.getsource(ci.expand_emails_for_retrieve)
    sql_src = inspect.getsource(retrieve_mod._sql_confirmed_email_addrs)
    _check(
        "retrieve_keep_does_not_use_name_blob_when_person_ids",
        "if person_ids:" in keep_src and "_email_person_blob" not in keep_src.split("if person_ids:")[1][:800],
        checks,
        problems,
    )
    _check(
        "header_records_do_not_assign_from_people",
        "from_people" not in header_src,
        checks,
        problems,
    )
    _check(
        "expand_retrieve_is_trusted_only",
        "trusted_emails_for_people" in expand_src and "trusted_only" in expand_src,
        checks,
        problems,
    )
    _check(
        "retrieve_sql_omits_people_array",
        "people" not in sql_src,
        checks,
        problems,
        detail=sql_src,
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

    from memorybox.ask.i11a.trusted_full_evidence_v2 import (
        fev2_input_sha256,
        score_email_grounding,
        select_single_pass_items,
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
    freeze_src = inspect.getsource(
        __import__(
            "memorybox.ask.i11a.trusted_full_evidence_v2",
            fromlist=["freeze_trusted_full_evidence_v2"],
        ).freeze_trusted_full_evidence_v2
    )
    _check(
        "freeze_pins_person_id_not_peggy_resolver",
        "resolve_peggy_plan" not in freeze_src and "person_ids=(str(person_id),)" in freeze_src,
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

    from memorybox.ask.i11a.trusted_full_evidence_v2 import validate_fev2_document

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
    _check(
        "chunk_merge_dedupes_claims",
        merged.get("ok") and len((merged.get("document") or {}).get("claims") or []) == 1,
        checks,
        problems,
        detail=merged,
    )

    return {
        "ok": not problems,
        "prove": "trusted_identity_retrieval",
        "flightsim": bool(flightsim),
        "checks": checks,
        "problems": problems,
        "flightsim_report": flightsim_report,
        "phase": 1,
        "stop": "phase_1_trusted_identity — no Gemma/Sol/chunking",
    }
