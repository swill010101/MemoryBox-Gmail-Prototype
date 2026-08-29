"""Acceptance for Person communication-identity expansion (email)."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from memorybox.ask.retrieve import (
    _payload_email_addresses,
    _person_scoped_comm_where,
    _sql_confirmed_email_addrs,
)
from memorybox.person.comm_address_index import _quoted_body_address_displays
from memorybox.person.comm_identity import (
    _display_matches_person,
    _header_records,
    attach_known_email_if_corroborated,
    corroborate_email_candidate,
    expand_person_communication_identities,
)
from memorybox.person.phone_map import normalize_handle


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
        "normalize_extracts_angle_addr",
        normalize_handle("Peg Legg <peggo01417@hotmail.com>") == "peggo01417@hotmail.com",
        checks,
        problems,
    )
    _check(
        "normalize_bare_email",
        normalize_handle("peggo01417@hotmail.com") == "peggo01417@hotmail.com",
        checks,
        problems,
    )
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
        "peg_legg_nickname_matches_peggy_george",
        _display_matches_person("Peg Legg", forms) == "nickname_full",
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
    sql, params = _sql_confirmed_email_addrs({"peggo01417@hotmail.com"})
    _check("email_addr_sql_not_false", sql != "FALSE", checks, problems, detail=sql)
    _check(
        "email_addr_sql_header_only",
        "from" in sql and "body_text" not in sql,
        checks,
        problems,
        detail=sql,
    )
    _check(
        "email_addr_sql_from_exact_before_broad_like",
        "->>'from'" in sql and "= ANY(%s)" in sql and sql.find("= ANY(%s)") < sql.find("LIKE ANY(%s)"),
        checks,
        problems,
        detail=sql,
    )
    _check(
        "email_addr_sql_from_params_exact_then_shaped_then_broad",
        isinstance(params, list)
        and len(params) >= 3
        and params[0] == ["peggo01417@hotmail.com"]
        and any("%<peggo01417@hotmail.com>%" in str(p) for p in params[1])
        and any(str(p).startswith("%peggo01417") for p in params[2]),
        checks,
        problems,
        detail=params[:3] if isinstance(params, list) else params,
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
    _check(
        "email_addr_sql_parsed_as_text_not_unnest",
        "from_parsed" in sql
        and "jsonb_array_elements" not in sql
        and "(payload_json->'from_parsed')::text" in sql.replace(" ", ""),
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
        confirmed_emails={"peggo01417@hotmail.com"},
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
        "scope_excludes_person_ids_gin_when_trusted_emails",
        "person_ids_gin" not in scope,
        checks,
        problems,
        detail=scope,
    )
    raw_only = _payload_email_addresses(
        {
            "from": "Peg Legg <peggo01417@hotmail.com>",
            "to": ["owner@example.com"],
            "from_parsed": [],
            "to_parsed": [],
            "cc_parsed": [],
        }
    )
    _check(
        "payload_addrs_from_raw_headers",
        "peggo01417@hotmail.com" in raw_only,
        checks,
        problems,
        detail=raw_only,
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

    # Nickname header Peg Legg + structured same-address full name (not quoted body).
    nick_cand = {
        "address": "peggo417@hotmail.com",
        "display_names": {"Peg Legg": 4},
        "occurrences": 4,
        "evidence_ids": ["e10", "e11"],
        "header_fields": ["from"],
        "inventory": {
            "structured_header": {
                "distinct_display_names": [
                    {"display_name": "Peggy George", "count": 2}
                ]
            }
        },
    }
    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy-george",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_identity.connection"
    ) as conn_ctx:
        conn = conn_ctx.return_value.__enter__.return_value
        # first call: sibling rows for nickname family; later: full display unique
        conn.execute.return_value.fetchall.side_effect = [
            [
                {"id": "person-peggy-stub", "display_name": "Peggy"},
                {"id": "person-peggy-george", "display_name": "Peggy George"},
            ],
            [{"id": "person-peggy-george", "display_name": "Peg Legg"}],
        ]
        nick_dec = corroborate_email_candidate("person-peggy-george", nick_cand)
    _check(
        "peg_legg_nickname_accepted_for_peggy_george",
        bool(nick_dec.get("accepted")),
        checks,
        problems,
        detail=nick_dec,
    )
    _check(
        "peg_legg_match_strength_nickname",
        nick_dec.get("match_strength") == "nickname_full",
        checks,
        problems,
        detail=nick_dec,
    )

    # Multiple Peggy* siblings: still accept when target is the unique form match.
    multi_sib_rows = [
        {"id": "person-peggy-george", "display_name": "Peggy George"},
        {"id": "person-peggy-smith", "display_name": "Peggy Smith"},
        {"id": "person-peggy-jones", "display_name": "Peggy Jones"},
    ]
    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy-george",
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
            list(multi_sib_rows),
            [{"id": "person-peggy-george", "display_name": "Peg Legg"}],
            list(multi_sib_rows),
            [{"id": "person-peggy-smith", "display_name": "Peg Legg"}],
        ]
        multi_ok = corroborate_email_candidate("person-peggy-george", nick_cand)
        multi_wrong = corroborate_email_candidate("person-peggy-smith", nick_cand)
    _check(
        "peg_legg_accepted_when_george_unique_among_peggy_siblings",
        bool(multi_ok.get("accepted"))
        and any(
            "nickname_unique_form_match" in str(c)
            for c in (multi_ok.get("corroboration") or [])
        ),
        checks,
        problems,
        detail=multi_ok,
    )
    _check(
        "peg_legg_rejected_for_unrelated_peggy_sibling",
        not multi_wrong.get("accepted")
        and multi_wrong.get("reason") == "ambiguous_nickname_among_people",
        checks,
        problems,
        detail=multi_wrong,
    )

    # Unrelated "Peg *" mailbox must NOT attach via nickname_full alone.
    noise_cand = {
        "address": "noise99@example.com",
        "display_names": {"Peg Noise99": 12},
        "occurrences": 12,
        "evidence_ids": ["n1"],
        "header_fields": ["from"],
        "inventory": {
            "structured_header": {
                "distinct_display_names": [
                    {"display_name": "Peg Noise99", "count": 12}
                ]
            }
        },
    }
    with patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy-george",
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
            [
                {"id": "person-peggy-stub", "display_name": "Peggy"},
                {"id": "person-peggy-george", "display_name": "Peggy George"},
            ],
            [{"id": "person-peggy-george", "display_name": "Peg Noise99"}],
        ]
        noise_dec = corroborate_email_candidate("person-peggy-george", noise_cand)
    _check(
        "unrelated_peg_noise_mailbox_rejected",
        not noise_dec.get("accepted")
        and noise_dec.get("reason") == "nickname_needs_same_address_full_name_or_alias",
        checks,
        problems,
        detail=noise_dec,
    )

    # Bare From + people[]=["Peg Legg"] (Hotmail/Takeout shape)
    bare_payload = {
        "from": "peggo417@hotmail.com",
        "from_parsed": [
            {"display_name": "", "address": "peggo417@hotmail.com", "normalized": "peggo417@hotmail.com"}
        ],
        "to": ["Tom Will <swill01@gmail.com>"],
        "to_parsed": [
            {
                "display_name": "Tom Will",
                "address": "swill01@gmail.com",
                "normalized": "swill01@gmail.com",
            }
        ],
        "cc": [],
        "bcc": [],
        "people": ["Peg Legg", "Tom Will"],
        "body_text": "hi",
    }
    bare_recs = _header_records(bare_payload)
    peg_from = [
        r
        for r in bare_recs
        if r.get("address") == "peggo417@hotmail.com"
        and (r.get("display_name") or "").lower() == "peg legg"
    ]
    tom_not_legg = [
        r
        for r in bare_recs
        if r.get("address") == "swill01@gmail.com"
        and (r.get("display_name") or "").lower() == "peg legg"
    ]
    _check(
        "bare_from_people_does_not_fill_from_display",
        not peg_from,
        checks,
        problems,
        detail=bare_recs,
    )
    _check(
        "bare_from_people_does_not_paint_to_address",
        not tom_not_legg,
        checks,
        problems,
        detail=bare_recs,
    )

    # Quoted-body header extraction (lower confidence; not identity alone)
    body = (
        "Thanks!\n\n"
        "-----Original Message-----\n"
        "From: Peg Legg <peggo417@hotmail.com>\n"
        "Cc: Peggy George <peggo417@hotmail.com>\n"
        "Subject: hi\n"
    )
    qhits = _quoted_body_address_displays(body, "peggo417@hotmail.com")
    q_names = {_norm for _norm in (
        (h.get("display_name") or "").strip().lower() for h in qhits
    )}
    _check(
        "quoted_body_finds_peg_legg",
        any("peg legg" == (h.get("display_name") or "").strip().lower() for h in qhits),
        checks,
        problems,
        detail=qhits,
    )
    _check(
        "quoted_body_finds_peggy_george",
        any(
            "peggy george" == (h.get("display_name") or "").strip().lower() for h in qhits
        ),
        checks,
        problems,
        detail=qhits,
    )
    # Common reply-prefix forms ("> From:") must still extract display names.
    body_gt = (
        "On Mon wrote:\n"
        "> From: Peg Legg <peggo417@hotmail.com>\n"
        "> Cc: Peggy George <peggo417@hotmail.com>\n"
    )
    qhits_gt = _quoted_body_address_displays(body_gt, "peggo417@hotmail.com")
    _check(
        "quoted_body_gt_prefix_finds_peggy_george",
        any(
            "peggy george" == (h.get("display_name") or "").strip().lower()
            for h in qhits_gt
        ),
        checks,
        problems,
        detail=qhits_gt,
    )
    # Outlook / Hotmail: Name [mailto:addr] must still yield the display name.
    body_mailto = (
        "-----Original Message-----\n"
        "From: Peggy George [mailto:peggo417@hotmail.com]\n"
        "Sent: Monday\n"
    )
    qhits_mailto = _quoted_body_address_displays(body_mailto, "peggo417@hotmail.com")
    _check(
        "quoted_body_mailto_finds_peggy_george",
        any(
            "peggy george" == (h.get("display_name") or "").strip().lower()
            for h in qhits_mailto
        ),
        checks,
        problems,
        detail=qhits_mailto,
    )
    from memorybox.person.comm_identity import _header_records as _hr_mailto

    struct_mailto = _hr_mailto(
        {"from": "Peggy George [mailto:peggo417@hotmail.com]", "to": [], "cc": []}
    )
    _check(
        "structured_mailto_from_finds_peggy_george",
        any(
            (r.get("address") or "") == "peggo417@hotmail.com"
            and (r.get("display_name") or "").strip().lower() == "peggy george"
            for r in struct_mailto
        ),
        checks,
        problems,
        detail=struct_mailto,
    )
    retrieve_src = open("memorybox/ask/retrieve.py", encoding="utf-8").read()
    _check(
        "retrieve_has_no_peggo_hardcode",
        "peggo417" not in retrieve_src and "peggo01417" not in retrieve_src,
        checks,
        problems,
    )
    from memorybox.person import comm_identity as ci

    _check(
        "expand_hook_is_trusted_retrieve",
        "trusted" in (ci.expand_emails_for_retrieve.__doc__ or "").lower()
        and "retrieve" in (ci.expand_emails_for_retrieve.__doc__ or "").lower(),
        checks,
        problems,
        detail=ci.expand_emails_for_retrieve.__doc__,
    )

    # End-to-end offline: Peg Legg structured + Peggy George quoted on peggo417
    # → nickname discover → corroborate → confirmed-email SQL would retrieve.
    from memorybox.person.comm_address_index import find_addresses_for_person_forms

    archive_payload = {
        "evidence_channel": "email",
        "from": "Peg Legg <peggo417@hotmail.com>",
        "to": ["Tom Will <swill01@gmail.com>"],
        "cc": [],
        "from_parsed": [
            {
                "display_name": "Peg Legg",
                "address": "peggo417@hotmail.com",
                "normalized": "peggo417@hotmail.com",
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
        "body_text": (
            "Thanks\n-----Original Message-----\n"
            "From: someone\n"
            "Cc: Peggy George <peggo417@hotmail.com>\n"
        ),
    }
    recs = _header_records(archive_payload)
    _check(
        "structured_header_has_peg_legg_not_body",
        any(
            r["address"] == "peggo417@hotmail.com"
            and (r.get("display_name") or "").lower() == "peg legg"
            for r in recs
        )
        and not any(
            (r.get("display_name") or "").lower() == "peggy george" for r in recs
        ),
        checks,
        problems,
        detail=recs,
    )
    q_only = _quoted_body_address_displays(
        str(archive_payload["body_text"]), "peggo417@hotmail.com"
    )
    _check(
        "peggy_george_only_in_quoted_body_for_fixture",
        any(
            (h.get("display_name") or "").strip().lower() == "peggy george"
            for h in q_only
        ),
        checks,
        problems,
        detail=q_only,
    )

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class _Conn:
        def execute(self, sql, params=None):
            # discover SQL
            if "LIKE ANY" in str(sql) or "like any" in str(sql).lower():
                return _Rows([{"id": "ev-peg", "payload_json": archive_payload}])
            # sibling / uniqueness queries
            if "split_part" in str(sql):
                return _Rows(
                    [
                        {"id": "person-peggy-stub", "display_name": "Peggy"},
                        {"id": "person-peggy-george", "display_name": "Peggy George"},
                    ]
                )
            if "lower(display_name)" in str(sql):
                return _Rows(
                    [{"id": "person-peggy-george", "display_name": "Peggy George"}]
                )
            return _Rows([])

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    with patch(
        "memorybox.person.comm_address_index.connection", return_value=_Conn()
    ), patch(
        "memorybox.person.comm_identity.connection", return_value=_Conn()
    ), patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy-george",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
            "aliases": [],
        },
    ):
        found = find_addresses_for_person_forms(["peggy george"])
        peg_addrs = [c for c in found if c.get("address") == "peggo417@hotmail.com"]
        _check(
            "discover_finds_peggo417_via_peg_legg_structured",
            bool(peg_addrs),
            checks,
            problems,
            detail=found,
        )
        if peg_addrs:
            peg_cand = dict(peg_addrs[0])
            peg_cand["inventory"] = {
                "quoted_body_headers_only": {
                    "distinct_display_names": [
                        {"display_name": "Peggy George", "count": 1}
                    ]
                }
            }
            dec = corroborate_email_candidate(
                "person-peggy-george", peg_cand, known_forms=["peggy george"]
            )
            _check(
                "quoted_body_full_name_does_not_confirm_ownership",
                not bool(dec.get("accepted")),
                checks,
                problems,
                detail=dec,
            )
            sql, _params = _sql_confirmed_email_addrs({"peggo417@hotmail.com"})
            _check(
                "retrieve_sql_matches_address_not_display_name",
                "peggo417" not in sql  # patterns are params
                and "from" in sql
                and "bcc" in sql
                and "body_text" not in sql,
                checks,
                problems,
                detail=sql,
            )
            # Closure: Peg Legg–labeled mail is included because address matches
            keep_addrs = {
                r["address"]
                for r in _header_records(archive_payload)
                if r["address"] == "peggo417@hotmail.com"
            }
            _check(
                "identity_closure_includes_peg_legg_labeled_mail",
                "peggo417@hotmail.com" in keep_addrs,
                checks,
                problems,
                detail=keep_addrs,
            )

    # Ledger-first discover: probe inventory already stored peggo417 + Peg Legg
    from memorybox.person.comm_address_index import (
        find_ledger_addresses_for_person_forms,
        resolve_and_attach_addresses_for_person,
    )

    class _LedgerConn:
        def execute(self, sql, params=None):
            s = str(sql).lower()
            if "from communication_identities" in s and "observed_display_names" in s:

                class _R:
                    def fetchall(self_inner):
                        return [
                            {
                                "address_normalized": "peggo417@hotmail.com",
                                "observed_display_names": {
                                    "peg legg": {
                                        "display_name": "Peg Legg",
                                        "header_count": 5,
                                        "quoted_body_count": 0,
                                        "header_fields": ["from"],
                                    },
                                    "peggy george": {
                                        "display_name": "Peggy George",
                                        "header_count": 0,
                                        "quoted_body_count": 2,
                                        "header_fields": ["quoted_cc"],
                                    },
                                },
                                "header_occurrence_count": 5,
                                "quoted_body_occurrence_count": 2,
                                "evidence_ids_sample": ["ev-1"],
                                "resolution_status": "observed",
                                "resolved_person_id": None,
                            }
                        ]

                return _R()
            if "like any" in s:
                class _Empty:
                    def fetchall(self_inner):
                        return []

                return _Empty()
            if "split_part" in s:
                class _Sib:
                    def fetchall(self_inner):
                        return [
                            {"id": "person-peggy-stub", "display_name": "Peggy"},
                            {
                                "id": "person-peggy-george",
                                "display_name": "Peggy George",
                            },
                        ]

                return _Sib()
            if "lower(display_name)" in s:
                class _Full:
                    def fetchall(self_inner):
                        return [
                            {
                                "id": "person-peggy-george",
                                "display_name": "Peggy George",
                            }
                        ]

                return _Full()

            class _Empty2:
                def fetchall(self_inner):
                    return []

                def fetchone(self_inner):
                    return None

            return _Empty2()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    with patch(
        "memorybox.person.comm_address_index.connection", return_value=_LedgerConn()
    ), patch(
        "memorybox.person.comm_identity.connection", return_value=_LedgerConn()
    ), patch(
        "memorybox.person.comm_identity._address_claimed_by", return_value=[]
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy-george",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_address_index.inventory_email_address",
        return_value={
            "ok": True,
            "address": "peggo417@hotmail.com",
            "rows_scanned": 5,
            "structured_header": {
                "occurrence_count": 5,
                "has_peggy_george": False,
                "has_peg_legg": True,
                "distinct_display_names": [
                    {"normalized_display": "peg legg", "display_name": "Peg Legg", "count": 5}
                ],
                "evidence_ids_sample": ["ev-1"],
            },
            "quoted_body_headers_only": {
                "occurrence_count": 2,
                "has_peggy_george": True,
                "has_peg_legg": False,
                "distinct_display_names": [
                    {
                        "normalized_display": "peggy george",
                        "display_name": "Peggy George",
                        "count": 2,
                    }
                ],
            },
        },
    ), patch(
        "memorybox.person.comm_address_index.upsert_communication_identity_from_inventory",
        return_value={"upserted": True, "address": "peggo417@hotmail.com"},
    ), patch(
        "memorybox.person.comm_identity.ensure_confirmed_email_contact",
        return_value={"upserted": True},
    ), patch(
        "memorybox.person.comm_identity._seed_header_display_aliases",
        return_value=[],
    ), patch(
        "memorybox.person.comm_identity.backfill_email_person_ids",
        return_value={"updated": 5},
    ), patch(
        "memorybox.person.comm_address_index.find_addresses_for_person_forms",
        return_value=[],
    ):
        ledger_hits = find_ledger_addresses_for_person_forms(["peggy george"])
        _check(
            "ledger_discover_finds_peggo417_via_peg_legg",
            any(c.get("address") == "peggo417@hotmail.com" for c in ledger_hits),
            checks,
            problems,
            detail=ledger_hits,
        )
        resolve_report = resolve_and_attach_addresses_for_person(
            "person-peggy-george", persist=True, backfill=True
        )
        _check(
            "ledger_resolve_does_not_confirm_via_quoted_full_name",
            not any(
                (e.get("candidate") or {}).get("address") == "peggo417@hotmail.com"
                for e in (resolve_report.get("accepted") or [])
            ),
            checks,
            problems,
            detail=resolve_report,
        )

    # Confirmed People emails: reuse + still discover additional header identities
    with patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value={
            "person_id": "person-peggy",
            "display_name": "Peggy George",
            "known_name_forms": ["peggy george"],
            "emails": [
                {
                    "contact_kind": "email",
                    "value_text": "peggo01417@hotmail.com",
                    "status": "confirmed",
                }
            ],
            "aliases": [],
        },
    ), patch(
        "memorybox.person.comm_identity.discover_email_candidates_from_archive",
        return_value=[],
    ) as discover, patch(
        "memorybox.person.comm_identity.backfill_email_person_ids",
        return_value={"updated": 12, "scanned": 12},
    ) as backfill:
        report = expand_person_communication_identities(
            ["person-peggy"], persist=False, backfill=True, discover=True
        )
        _check(
            "discovery_still_runs_with_confirmed_present",
            discover.call_count >= 1,
            checks,
            problems,
            detail=report.get("rounds"),
        )
        _check(
            "emails_returned_from_people_contacts",
            "peggo01417@hotmail.com" in (report.get("emails_by_person") or {}).get(
                "person-peggy", []
            ),
            checks,
            problems,
            detail=report.get("emails_by_person"),
        )
        _check(
            "backfill_runs_when_confirmed_present",
            backfill.call_count >= 1,
            checks,
            problems,
            detail=report.get("rounds"),
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

    # Operator repair may reclaim an address wrongly confirmed on another Person.
    claim_calls = {"n": 0}

    def _claim_side_effect(_addr: str) -> list[str]:
        claim_calls["n"] += 1
        # First check: claimed by other; after revoke: unclaimed.
        return ["person-wrong"] if claim_calls["n"] == 1 else []

    with patch(
        "memorybox.person.comm_identity._address_claimed_by",
        side_effect=_claim_side_effect,
    ), patch(
        "memorybox.person.comm_identity._revoke_confirmed_email_contact",
        return_value={"revoked": True, "person_id": "person-wrong"},
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value=snap_peggy,
    ), patch(
        "memorybox.person.comm_identity.connection",
        return_value=_FakeConn(),
    ):
        reclaim = attach_known_email_if_corroborated(
            "person-peggy",
            "peggo417@hotmail.com",
            persist=False,
            backfill=False,
            operator_attested=True,
        )
        auto_blocked = attach_known_email_if_corroborated(
            "person-peggy",
            "peggo417@hotmail.com",
            persist=False,
            backfill=False,
            operator_attested=False,
        )
    _check(
        "operator_attested_reclaims_from_other_person",
        bool(reclaim.get("accepted"))
        and "person-wrong" in (reclaim.get("reclaimed_from") or []),
        checks,
        problems,
        detail=reclaim,
    )
    # Reset claim counter path: auto must still fail-closed when claimed.
    with patch(
        "memorybox.person.comm_identity._address_claimed_by",
        return_value=["person-wrong"],
    ), patch(
        "memorybox.person.comm_identity.person_identity_snapshot",
        return_value=snap_peggy,
    ):
        auto_blocked = attach_known_email_if_corroborated(
            "person-peggy",
            "peggo417@hotmail.com",
            persist=False,
            backfill=False,
            operator_attested=False,
        )
    _check(
        "auto_still_fail_closed_when_claimed",
        not auto_blocked.get("accepted")
        and auto_blocked.get("reason") == "address_claimed_by_other_person",
        checks,
        problems,
        detail=auto_blocked,
    )

    # People status filter must use domain statuses (not stories' 'active').
    import inspect

    from memorybox.person import (
        find_ask_person_by_name,
        list_people_by_alias,
        list_people_by_nickname_family,
    )
    from memorybox.person import comm_identity as ci_mod
    from memorybox.person import comm_address_index as cai

    src_ci = inspect.getsource(ci_mod)
    _check(
        "people_status_filter_not_active",
        "status = 'active'" not in src_ci
        and "status IN ('confirmed', 'unresolved')" in src_ci,
        checks,
        problems,
    )
    upsert_src = inspect.getsource(cai.upsert_communication_identity_from_inventory)
    _check(
        "ledger_upsert_never_downgrades_confirmed",
        "resolution_status = 'confirmed'" in upsert_src
        and "IS DISTINCT FROM 'confirmed'" in upsert_src,
        checks,
        problems,
    )

    class _PersonRow:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class _PersonConn:
        def execute(self, sql, params=None):
            s = str(sql).lower()
            if "person_aliases" in s:
                return _PersonRow(
                    [
                        {
                            "id": "person-peggy-george",
                            "display_name": "Peggy George",
                            "status": "confirmed",
                            "merged_into_id": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "split_part" in s:
                return _PersonRow(
                    [
                        {
                            "id": "person-peggy-stub",
                            "display_name": "Peggy",
                            "status": "unresolved",
                            "merged_into_id": None,
                            "created_at": None,
                            "updated_at": None,
                        },
                        {
                            "id": "person-peggy-george",
                            "display_name": "Peggy George",
                            "status": "confirmed",
                            "merged_into_id": None,
                            "created_at": None,
                            "updated_at": None,
                        },
                    ]
                )
            return _PersonRow([])

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _fake_view(_conn, row):
        from memorybox.person import PersonView

        return PersonView(
            id=str(row["id"]),
            display_name=row.get("display_name"),
            status=row.get("status") or "unresolved",
            merged_into_id=None,
            created_at=None,
            updated_at=None,
            provider_mappings=[],
            identity_authority=None,
        )

    with patch("memorybox.person.connection", return_value=_PersonConn()), patch(
        "memorybox.person._view", side_effect=_fake_view
    ), patch(
        "memorybox.person.find_confirmed_person_by_name", return_value=None
    ), patch(
        "memorybox.person.list_people_by_exact_name", return_value=[]
    ):
        nick_hits = list_people_by_nickname_family("Peg Legg")
        multi = [p for p in nick_hits if " " in (p.display_name or "")]
        _check(
            "ask_nickname_family_finds_peggy_george",
            any(p.display_name == "Peggy George" for p in multi),
            checks,
            problems,
            detail=[p.display_name for p in nick_hits],
        )
        resolved = find_ask_person_by_name("Peg Legg", photo=None, lazy_seed=False)
        _check(
            "ask_resolves_peg_legg_to_peggy_george",
            resolved is not None and resolved.display_name == "Peggy George",
            checks,
            problems,
            detail=getattr(resolved, "display_name", None),
        )
        alias_hits = list_people_by_alias("Peg Legg")
    _check(
        "ask_alias_lookup_finds_person",
        any(p.display_name == "Peggy George" for p in alias_hits),
        checks,
        problems,
        detail=[p.display_name for p in alias_hits],
    )

    # Ambiguous short Ask: prefer unique multi-token over stub; prefer unique email.
    from memorybox.person import (
        AmbiguousIdentityError as _Amb,
        PersonView as _PV,
        _pick_unique_ask_person as _pick,
        _person_has_confirmed_email as _has_email,
    )

    stub = _PV(
        id="pick-stub",
        display_name="Peggy",
        status="confirmed",
        identity_authority="owner_confirmed",
    )
    george = _PV(
        id="pick-george",
        display_name="Peggy George",
        status="confirmed",
        identity_authority="owner_confirmed",
    )
    smith = _PV(
        id="pick-smith",
        display_name="Peggy Smith",
        status="confirmed",
        identity_authority="owner_confirmed",
    )
    preferred = _pick([stub, george])
    _check(
        "ask_pick_prefers_unique_multi_token",
        preferred is not None and preferred.id == "pick-george",
        checks,
        problems,
        detail=getattr(preferred, "display_name", None),
    )
    try:
        _pick([george, smith])
        _check(
            "ask_pick_still_ambiguous_two_multi_token",
            False,
            checks,
            problems,
            detail="expected AmbiguousIdentityError",
        )
    except _Amb as exc:
        _check(
            "ask_pick_still_ambiguous_two_multi_token",
            "Peggy George" in str(exc) and "Peggy Smith" in str(exc),
            checks,
            problems,
            detail=str(exc),
        )
    _check(
        "ask_pick_email_helper_callable",
        callable(_has_email) and _has_email("nonexistent-person-id") is False,
        checks,
        problems,
    )

    # Person-complete email retrieve must not keyword-filter narrative Ask verbs.
    import inspect as _inspect

    from memorybox.ask import retrieve as retrieve_mod
    from memorybox.person import comm_address_index as addr_idx

    email_src = _inspect.getsource(retrieve_mod.search_email_messages)
    complete_src = _inspect.getsource(retrieve_mod._complete_comm_retrieve)
    expand_src = _inspect.getsource(ci.expand_emails_for_retrieve)
    _check(
        "complete_person_email_clears_narrative_keywords",
        "keywords = []" in email_src
        and (
            "gallery_email_eligible" in email_src
            or "_complete_comm_retrieve(plan)" in email_src
        ),
        checks,
        problems,
    )
    _check(
        "gallery_email_attach_is_bounded_not_complete",
        "gallery_email_eligible" in complete_src and "return False" in complete_src,
        checks,
        problems,
    )
    _check(
        "expand_retrieve_skips_archive_when_confirmed_cached",
        "skipped_archive_discover" in expand_src
        and "cache_hit" in expand_src
        and "force_rediscover" in expand_src,
        checks,
        problems,
    )
    discover_src = _inspect.getsource(addr_idx.find_addresses_for_person_forms)
    inventory_src = _inspect.getsource(addr_idx.inventory_email_address)
    enrich_src = _inspect.getsource(addr_idx._enrich_candidate_from_inventory)
    resolve_src = _inspect.getsource(addr_idx.resolve_and_attach_addresses_for_person)
    _check(
        "discover_prefers_structured_parsed_before_limit",
        "ORDER BY CASE" in discover_src and "from_parsed" in discover_src,
        checks,
        problems,
    )
    _check(
        "discover_pass1_structured_parsed_only",
        ("Pass 1a" in discover_src or "Pass 1:" in discover_src or "Pass 1b" in discover_src)
        and "from_parsed" in discover_src
        and "jsonb_array_elements" not in discover_src
        and "people" in discover_src,
        checks,
        problems,
    )
    _check(
        "discover_pass1b_prefers_multi_token_before_limit",
        "Pass 1b" in discover_src
        and "Prefer multi-token" in discover_src
        and discover_src.count("ORDER BY CASE") >= 2,
        checks,
        problems,
    )
    _check(
        "resolve_caps_nickname_only_candidates",
        "nickname_candidates_kept" in resolve_src and "48" in resolve_src,
        checks,
        problems,
    )
    _check(
        "inventory_prefers_structured_address_before_limit",
        "ORDER BY CASE" in inventory_src
        and "from_parsed" in inventory_src
        and "jsonb_array_elements" not in inventory_src,
        checks,
        problems,
    )
    _check(
        "inventory_sql_avoids_body_text_prefilter",
        "body_text" not in inventory_src
        or (
            "NEVER prefilter on body_text" in inventory_src
            and "payload_json->>'body_text'" not in inventory_src
        ),
        checks,
        problems,
    )
    _check(
        "inventory_from_exact_before_broad_like",
        "->>'from', '')) = %s" in inventory_src.replace(" ", "")
        or ("->>'from'" in inventory_src and "= %s" in inventory_src),
        checks,
        problems,
    )
    _check(
        "inventory_and_discover_skip_spam_trash",
        "mailbox_skip" in inventory_src
        and "spam" in inventory_src
        and "mailbox_skip" in discover_src
        and "spam" in discover_src,
        checks,
        problems,
    )
    identity_mod_src = open(ci.__file__, encoding="utf-8").read()
    _check(
        "comm_identity_no_jsonb_array_elements",
        "jsonb_array_elements" not in identity_mod_src
        and "(payload_json->'from_parsed')::text" in identity_mod_src.replace(" ", ""),
        checks,
        problems,
    )
    attach_src = _inspect.getsource(ci.attach_known_email_if_corroborated)
    _check(
        "attest_scan_skips_spam_trash_and_orders_structured",
        "mailbox_skip" in attach_src
        and "spam" in attach_src
        and "ORDER BY CASE" in attach_src
        and "payload_json->>'body_text'" not in attach_src,
        checks,
        problems,
    )
    _check(
        "resolve_enriches_candidate_from_inventory",
        "_enrich_candidate_from_inventory" in resolve_src
        and "distinct_display_names" in enrich_src,
        checks,
        problems,
    )

    enriched = addr_idx._enrich_candidate_from_inventory(
        {
            "address": "peggo417@hotmail.com",
            "display_names": {},
            "match_strengths": {},
            "occurrences": 0,
            "evidence_ids": [],
        },
        {
            "structured_header": {
                "occurrence_count": 4,
                "distinct_display_names": [
                    {"display_name": "Peg Legg", "count": 4, "normalized_display": "peg legg"}
                ],
                "evidence_ids_sample": ["e1"],
            }
        },
        ["peggy george"],
    )
    _check(
        "enrich_pulls_peg_legg_into_empty_candidate",
        "Peg Legg" in (enriched.get("display_names") or {})
        and int(enriched.get("occurrences") or 0) >= 4
        and (enriched.get("match_strengths") or {}).get("Peg Legg") == "nickname_full",
        checks,
        problems,
        detail=enriched,
    )

    # FlightSim Immich stub rename must not require Peggy George observation when
    # structured Peg Legg on peggo417 is present (thin quoted Takeout inventory).
    from memorybox.person import address_centric_e2e as _ace

    ace_src = open(_ace.__file__, encoding="utf-8").read()
    _check(
        "flightsim_upgrade_allows_peg_legg_structured_alone",
        "archive_lacks_peg_legg_structured" in ace_src
        and "has_legg and struct_n > 0" in ace_src,
        checks,
        problems,
    )
    # Structural: upgrade early-exit no longer requires both names for Immich rename.
    _check(
        "flightsim_upgrade_no_longer_requires_george_for_rename",
        "archive_lacks_peg_legg_and_peggy_george_corroboration" not in ace_src,
        checks,
        problems,
    )
    _check(
        "flightsim_cold_create_from_peg_legg_structured",
        "flightsim_created_peggy_george_from_peg_legg_structured" in ace_src
        and "_archive_has_legg() and struct_n > 0" in ace_src,
        checks,
        problems,
    )
    _check(
        "bootstrap_operator_attests_probe_before_peg_star_discover",
        "bootstrap_operator_attested_probe" in ace_src
        and "attach_known_email_if_corroborated" in ace_src
        and "operator_attested=True" in ace_src,
        checks,
        problems,
    )
    # Attest success must force peggo417 into addrs so we never fall through to
    # archive-wide resolve_and_attach (Peg* nickname scan / Takeout hang).
    _check(
        "bootstrap_attest_forces_probe_addr_before_peg_star",
        "addrs.add(_PROBE_ADDR)" in ace_src
        and "bootstrap_operator_attested_probe_retry" in ace_src
        and ace_src.find("addrs.add(_PROBE_ADDR)")
        < ace_src.find("resolve_and_attach_addresses_for_person("),
        checks,
        problems,
    )
    # Structured bootstrap: after attest/retry/final, fail closed — never Peg* scan.
    _check(
        "bootstrap_fail_closed_skips_peg_star_after_attest",
        "bootstrap_fail_closed_skip_peg_star_scan" in ace_src
        and "bootstrap_operator_attested_probe_final" in ace_src
        and "skipped archive-wide Peg* discover" in ace_src,
        checks,
        problems,
    )
    _check(
        "e2e_ledger_promote_retry_when_observed",
        "address_centric_e2e_ledger_retry" in ace_src
        and "ensure_confirmed_email_contact" in ace_src,
        checks,
        problems,
    )
    _check(
        "e2e_multi_exact_george_prefers_peggo_claimant",
        "Multiple exact \"Peggy George\"" in ace_src
        or "Multiple exact 'Peggy George'" in ace_src
        or "unique peggo417 contact claimant" in ace_src,
        checks,
        problems,
    )

    gate_cmd = open("tools/flightsim-address-centric-gate.cmd", encoding="utf-8").read()
    _check(
        "gate_cmd_sets_result_branch_before_pushd",
        gate_cmd.find("set RESULT_BRANCH=")
        < gate_cmd.find('pushd "%REPO_ROOT%"'),
        checks,
        problems,
    )
    _check(
        "gate_cmd_aborts_mid_merge_before_checkout",
        "git merge --abort" in gate_cmd
        and "MERGE_HEAD" in gate_cmd
        and "git reset --hard origin/%BRANCH%" in gate_cmd,
        checks,
        problems,
    )
    _check(
        "gate_cmd_checkout_fail_avoids_echo_dot_in_parens",
        "goto :checkout_failed" in gate_cmd
        and ":checkout_failed" in gate_cmd
        and "echo.\n  echo CHECKOUT FAILED" not in gate_cmd.replace("\r\n", "\n"),
        checks,
        problems,
    )
    reset_cmd = open(
        "tools/flightsim-address-centric-reset.cmd", encoding="utf-8"
    ).read()
    _check(
        "reset_cmd_hard_resets_feature_tip",
        "git reset --hard origin/%BRANCH%" in reset_cmd
        and "git merge --abort" in reset_cmd
        and "cursor/p2-i11a-address-centric-email-49da" in reset_cmd,
        checks,
        problems,
    )
    _check(
        "gate_cmd_watchdog_timeout_gates",
        "gate_cmd_startmb_watchdog_timeout" in gate_cmd
        and "gate_cmd_prove_watchdog_timeout" in gate_cmd
        and '"waiting": false' in gate_cmd
        and "flightsim-address-centric-watchdog.ps1" in gate_cmd,
        checks,
        problems,
    )
    wd_ps1_bytes = open(
        "tools/flightsim-address-centric-watchdog.ps1", "rb"
    ).read()
    _check(
        "watchdog_ps1_is_ascii",
        all(b < 128 for b in wd_ps1_bytes),
        checks,
        problems,
    )
    wd_ps1 = wd_ps1_bytes.decode("ascii")
    _check(
        "watchdog_ps1_taskkill_tree",
        "taskkill /F /T /PID" in wd_ps1
        and "ValidateSet(\"startmb\", \"prove\")" in wd_ps1,
        checks,
        problems,
    )
    prove_ps1_bytes = open("tools/flightsim-address-centric-prove.ps1", "rb").read()
    _check(
        "prove_ps1_is_ascii",
        all(b < 128 for b in prove_ps1_bytes),
        checks,
        problems,
    )
    prove_ps1 = prove_ps1_bytes.decode("ascii")
    _check(
        "prove_ps1_failure_gate_utf8_no_bom",
        "UTF8Encoding $false" in prove_ps1 and "waiting = $false" in prove_ps1,
        checks,
        problems,
    )
    _check(
        "prove_ps1_matches_startmb_default_dsn",
        "postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox" in prove_ps1
        and "missing_memorybox_app_env" not in prove_ps1,
        checks,
        problems,
    )
    _check(
        "prove_ps1_runs_goal_complete_verifier",
        "verify-address-centric-gate.py" in prove_ps1
        and "GOAL_COMPLETE=" in prove_ps1,
        checks,
        problems,
    )
    _check(
        "prove_ps1_writes_gate_even_when_python_exit_0",
        "prove_exit_ok_but_gate_missing" in prove_ps1
        and "Start-Process -FilePath $Python" in prove_ps1
        and "MEMORYBOX_ADDRESS_CENTRIC_OUT" in prove_ps1,
        checks,
        problems,
    )
    _check(
        "prove_ps1_writes_started_sentinel",
        "ADDRESS_CENTRIC_PROVE_STARTED.txt" in prove_ps1
        and "PROVE_PS1_STARTED" in prove_ps1
        and "WindowsApps" in prove_ps1,
        checks,
        problems,
    )
    wd_src = open(
        "tools/flightsim-address-centric-watchdog.ps1", encoding="utf-8"
    ).read()
    _check(
        "watchdog_prove_uses_system32_powershell",
        "WATCHDOG_PROVE_ENTER" in wd_src
        and "& $provePs1" in wd_src
        and "in-process" in wd_src,
        checks,
        problems,
    )
    _check(
        "gate_cmd_detects_prove_ps1_never_started",
        "prove_ps1_never_started" in gate_cmd
        and "ADDRESS_CENTRIC_PROVE_STARTED.txt" in gate_cmd
        and "WindowsPowerShell\\v1.0\\powershell.exe" in gate_cmd,
        checks,
        problems,
    )
    ace_write = open("memorybox/person/address_centric_e2e.py", encoding="utf-8").read()
    _check(
        "e2e_gate_out_dir_is_repo_absolute",
        "def _gate_out_dir" in ace_write
        and "parents[2]" in ace_write
        and 'Path("docs/test-output/historian-full-evidence/peggy-v2")' not in ace_write,
        checks,
        problems,
    )
    verify_src = open("tools/verify-address-centric-gate.py", encoding="utf-8").read()
    _check(
        "verifier_rejects_allow_dev_fake_flightsim",
        "C2a" in verify_src
        and "allow_dev_defaults" in verify_src
        and "C2c" in verify_src,
        checks,
        problems,
    )
    ace_claim_src = open("memorybox/person/address_centric_e2e.py", encoding="utf-8").read()
    _check(
        "e2e_demotes_flightsim_claim_under_allow_dev",
        "claim_flightsim_archive" in ace_claim_src
        and "flightsim_claim_demoted_allow_dev_defaults" in ace_claim_src,
        checks,
        problems,
    )
    _check(
        "e2e_soft_ok_distinct_immich_peg_legg",
        "ask_peg_legg_distinct_immich_soft_ok" in ace_claim_src
        and "legg_holds_peggo417" in ace_claim_src,
        checks,
        problems,
    )
    _check(
        "e2e_rename_fallback_respects_immich_uniqueness",
        "immich_peggy_not_unique" in ace_claim_src
        and "_unsafe_skip" in ace_claim_src
        and "not _unsafe_skip" in ace_claim_src,
        checks,
        problems,
    )
    _check(
        "gate_cmd_pushes_audit_json",
        "ADDRESS_CENTRIC_AUDIT.json" in gate_cmd,
        checks,
        problems,
    )

    # Full-Evidence AmbiguousIdentity recovery prefers exact George/Legg from
    # the candidate list before another Ask round-trip.
    from memorybox.ask.i11a import full_evidence_diagnostic as _fed

    fed_src = open(_fed.__file__, encoding="utf-8").read()
    _check(
        "full_evidence_ambig_prefers_candidate_display_name",
        "prefer_l = prefer.lower()" in fed_src and "== prefer_l" in fed_src,
        checks,
        problems,
    )
    _check(
        "full_evidence_ambig_exact_name_last_resort",
        "list_people_by_exact_name" in fed_src
        and (
            "Last resort: unique exact Peggy George" in fed_src
            or "_pick_exact_peggy_george" in fed_src
        ),
        checks,
        problems,
    )
    _check(
        "full_evidence_ambig_prefers_peggo_claimant_on_dup_george",
        "_pick_exact_peggy_george" in fed_src
        and "peggo417@hotmail.com" in fed_src,
        checks,
        problems,
    )

    e2e_src = open(
        __import__("memorybox.person.address_centric_e2e", fromlist=["x"]).__file__,
        encoding="utf-8",
    ).read()
    _check(
        "e2e_alias_seed_soft_when_ask_resolves",
        "peg_legg_alias_seed_soft_ok_ask_resolves" in e2e_src
        and "plan_or_ask_ok" in e2e_src,
        checks,
        problems,
    )

    return {
        "ok": not problems,
        "prove": "person_email_identity",
        "flightsim": bool(flightsim),
        "checks": checks,
        "problems": problems,
        "peggo417_decision_fixture": decision,
        "root_cause": (
            "Email Person retrieve uses confirmed People contacts + header SQL. "
            "Archive-first address ledger (discover→resolve→retrieve). "
            "Ask resolves aliases and nickname forms (Peg Legg → Peggy George). "
            "No Peggy-specific address hardcoding."
        ),
    }
