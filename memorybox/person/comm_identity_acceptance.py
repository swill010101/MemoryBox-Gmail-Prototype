"""Acceptance for Person communication-identity expansion (email)."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from memorybox.ask.retrieve import _person_scoped_comm_where, _sql_confirmed_email_addrs
from memorybox.person.comm_identity import (
    _display_matches_person,
    attach_known_email_if_corroborated,
    corroborate_email_candidate,
    expand_person_communication_identities,
)


def _check(name: str, ok: bool, checks: list[str], problems: list[str], *, detail: Any = None) -> None:
    checks.append(name)
    if not ok:
        problems.append(f"{name}: {detail}")


def run_prove_person_email_identity(*, flightsim: bool = False) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    # Display-name matching policy
    forms = ["peggy george", "margaret george"]
    _check(
        "full_name_matches",
        _display_matches_person("Peggy George", forms) in {"full", "alias_full"},
        checks,
        problems,
    )
    _check(
        "alias_full_matches",
        _display_matches_person("Margaret George", forms) is not None,
        checks,
        problems,
    )
    _check(
        "first_name_only_rejected",
        _display_matches_person("Peggy", forms) is None,
        checks,
        problems,
    )
    _check(
        "peg_legg_alias_matches",
        _display_matches_person("Peg Legg", forms + ["peg legg"]) == "alias_full",
        checks,
        problems,
    )
    _check(
        "peg_legg_not_matched_without_alias",
        _display_matches_person("Peg Legg", forms) is None,
        checks,
        problems,
    )
    _check(
        "unrelated_name_rejected",
        _display_matches_person("Tom Will", forms) is None,
        checks,
        problems,
    )

    # SQL scope includes confirmed emails (common retrieve path)
    sql, params = _sql_confirmed_email_addrs({"peggo417@hotmail.com"})
    _check("email_addr_sql_not_false", sql != "FALSE", checks, problems, detail=sql)
    _check(
        "email_addr_sql_header_only",
        "from" in sql and "body_text" not in sql,
        checks,
        problems,
        detail=sql,
    )
    _check(
        "email_addr_sql_handles_to_json_array",
        "payload_json->'to')::text" in sql.replace(" ", "")
        or "(payload_json->'to')::text" in sql,
        checks,
        problems,
        detail=sql,
    )
    _check(
        "email_addr_sql_not_broken_to_arrow",
        "payload_json->>'to'" not in sql,
        checks,
        problems,
        detail=sql,
    )
    where, wparams, scope = _person_scoped_comm_where(
        channel_sql="true",
        win_sql="true",
        win_params=[],
        person_names=[],
        person_ids={"person-peggy"},
        header_fallback=False,
        confirmed_emails={"peggo417@hotmail.com"},
    )
    _check("where_not_none_with_email", where is not None, checks, problems, detail=scope)
    _check(
        "scope_includes_confirmed_email_headers",
        "confirmed_email_headers" in scope,
        checks,
        problems,
        detail=scope,
    )
    _check(
        "scope_includes_person_ids_gin",
        "person_ids_gin" in scope,
        checks,
        problems,
        detail=scope,
    )

    # Empty identity probe still fail-closed without ids/emails
    where_empty, _, scope_empty = _person_scoped_comm_where(
        channel_sql="true",
        win_sql="true",
        win_params=[],
        person_names=["peggy"],
        person_ids=set(),
        header_fallback=False,
        confirmed_emails=None,
    )
    _check(
        "email_without_ids_or_addrs_skips_scan",
        where_empty is None and scope_empty == "identity_probe_empty",
        checks,
        problems,
        detail=scope_empty,
    )

    # Corroboration: peggo417 with full display name, unclaimed
    cand = {
        "address": "peggo417@hotmail.com",
        "display_names": {"Peggy George": 3},
        "occurrences": 3,
        "evidence_ids": ["e1", "e2", "e3"],
        "header_fields": ["from"],
        "match_strength": "full",
    }
    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_identity._people_sharing_first_name",
        return_value=["person-peggy"],
    ), patch(
        "memorybox.person.comm_identity.connection"
    ) as conn_ctx:
        # full display name unique
        conn = conn_ctx.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.return_value = [
            {"id": "person-peggy", "display_name": "Peggy George"}
        ]
        decision = corroborate_email_candidate("person-peggy", cand)
    _check(
        "peggo417_accepted_with_full_name",
        bool(decision.get("accepted")),
        checks,
        problems,
        detail=decision,
    )
    _check(
        "peggo417_reason_corroborated",
        decision.get("reason") == "corroborated_header_identity",
        checks,
        problems,
        detail=decision,
    )

    # Ambiguous: address claimed by another person
    with patch(
        "memorybox.person.comm_identity._address_claimed_by",
        return_value=["person-other"],
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
        },
    ):
        rejected = corroborate_email_candidate("person-peggy", cand)
    _check(
        "claimed_address_rejected",
        not rejected.get("accepted")
        and rejected.get("reason") == "address_claimed_by_other_person",
        checks,
        problems,
        detail=rejected,
    )

    # First-name-only candidate rejected even if occurrences high
    weak = {
        "address": "someone@example.com",
        "display_names": {"Peggy": 10},
        "occurrences": 10,
        "evidence_ids": ["e9"],
        "header_fields": ["from"],
    }
    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
        },
    ):
        weak_dec = corroborate_email_candidate("person-peggy", weak)
    _check(
        "first_name_header_not_enough",
        not weak_dec.get("accepted"),
        checks,
        problems,
        detail=weak_dec,
    )

    # Stable reuse: when confirmed emails exist, no archive rediscovery
    with patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [
                {
                    "contact_kind": "email",
                    "value_text": "peggo417@hotmail.com",
                    "status": "confirmed",
                }
            ],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_identity.discover_email_candidates_from_archive"
    ) as discover:
        report = expand_person_communication_identities(
            ["person-peggy"], persist=False, backfill=False, discover=True
        )
        _check(
            "no_rediscovery_when_confirmed_present",
            discover.call_count == 0,
            checks,
            problems,
            detail=report.get("rounds"),
        )
        _check(
            "emails_returned_from_confirmed",
            "peggo417@hotmail.com" in (report.get("emails_by_person") or {}).get(
                "person-peggy", []
            ),
            checks,
            problems,
            detail=report.get("emails_by_person"),
        )

    # Body-name matching must not be the retrieve mechanism (header SQL only)
    _check(
        "retrieve_sql_helper_avoids_body_text",
        "body_text" not in sql and "payload_json->>'body" not in sql,
        checks,
        problems,
    )

    # Operator-attested attach: bare/first-name headers still attach when --address
    # is explicit; auto path remains fail-closed.
    bare_payload = {
        "evidence_channel": "email",
        "from": "peggo417@hotmail.com",
        "to": ["owner@example.com"],
        "cc": [],
        "from_parsed": [
            {
                "display_name": "Peggy",
                "address": "peggo417@hotmail.com",
                "normalized": "peggo417@hotmail.com",
            }
        ],
        "to_parsed": [
            {
                "display_name": "",
                "address": "owner@example.com",
                "normalized": "owner@example.com",
            }
        ],
        "cc_parsed": [],
        "people": ["Peggy", "owner@example.com"],
    }
    snap_peggy = {
        "person_id": "person-peggy",
        "display_name": "Peggy George",
        "known_name_forms": ["peggy george"],
        "emails": [],
        "aliases": [],
    }

    class _FakeConn:
        def execute(self, *_a, **_k):
            class _R:
                def fetchall(self_inner):
                    return [{"id": "ev-1", "payload_json": bare_payload}]

            return _R()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value=snap_peggy,
    ), patch(
        "memorybox.person.comm_identity.connection",
        return_value=_FakeConn(),
    ), patch(
        "memorybox.person.comm_identity.corroborate_email_candidate",
        wraps=corroborate_email_candidate,
    ):
        auto = attach_known_email_if_corroborated(
            "person-peggy",
            "peggo417@hotmail.com",
            persist=False,
            backfill=False,
            operator_attested=False,
        )
        op = attach_known_email_if_corroborated(
            "person-peggy",
            "peggo417@hotmail.com",
            persist=False,
            backfill=False,
            operator_attested=True,
        )
    _check(
        "auto_rejects_bare_or_first_name_headers",
        not auto.get("accepted"),
        checks,
        problems,
        detail=auto,
    )
    _check(
        "operator_attested_accepts_address_in_headers",
        bool(op.get("accepted"))
        and (op.get("decision") or {}).get("reason")
        == "operator_attested_address_in_headers",
        checks,
        problems,
        detail=op,
    )
    _check(
        "operator_attested_reports_rows",
        int(op.get("rows_with_address") or 0) >= 1,
        checks,
        problems,
        detail=op.get("rows_with_address"),
    )

    return {
        "ok": not problems,
        "prove": "person_email_identity",
        "flightsim": bool(flightsim),
        "checks": checks,
        "problems": problems,
        "peggo417_decision_fixture": decision,
        "root_cause": (
            "Email Person retrieve was GIN person_ids-only; Peggy had no confirmed "
            "email contact so payloads never stamped and SQL returned zero. SMS "
            "succeeds via phone contacts + sender_name fallback. After To/CC JSON "
            "fix, auto expand can still miss Hotmail bare/first-name headers — "
            "use repair --person-id --address for operator attestation."
        ),
    }
