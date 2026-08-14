"""P2-I7 SMS/Text Evidence — structural + fixture logic acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.ingest.sms_parse import PARSER_VERSION, inspect_sms_export, iter_sms_rows


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "providers"
    / "_fixtures"
    / "i7_sms_chat_sessions.csv"
)
ATTACHMENT = FIXTURE.parent / "photo.jpg"


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    sms_parse = (root / "ingest" / "sms_parse.py").read_text(encoding="utf-8")
    comms = (root / "ingest" / "comms_sms.py").read_text(encoding="utf-8")
    phone = (root / "person" / "phone_map.py").read_text(encoding="utf-8")
    retrieve = (root / "ask" / "retrieve.py").read_text(encoding="utf-8")
    planner = (root / "planner" / "__init__.py").read_text(encoding="utf-8")
    find_py = (root / "explore" / "find.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    summary = (root / "status" / "summary.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")

    _check(
        "i7_parser_header_driven",
        "PARSER_VERSION" in sms_parse
        and "_ALIASES" in sms_parse
        and "source_metadata" in sms_parse
        and "iMazing" not in sms_parse,
        checks,
        problems,
        "Header-driven parser; no locked vendor schema",
    )
    _check(
        "i7_one_evidence_model",
        "evidence_kind=\"communication\"" in comms.replace("'", '"')
        or 'evidence_kind="communication"' in comms
        or "evidence_kind='communication'" in comms,
        checks,
        problems,
        "SMS uses communication Evidence",
    )
    _check(
        "i7_no_sms_table",
        "CREATE TABLE sms" not in comms
        and "sms_messages" not in comms.replace("iter_sms_messages", ""),
        checks,
        problems,
        "No parallel sms_messages SoT",
    )
    _check(
        "i7_identity_rules",
        "auto_mapped" in phone and "unmapped" in phone and "review" in phone,
        checks,
        problems,
        "Unique auto-map / ambiguous review / unmapped retained",
    )
    _check(
        "i7_ask_sms_path",
        "search_sms_messages" in retrieve
        and "SMS_ASK_RE" in planner
        and "want_sms_modality" in planner
        and "skipped_for_sms_ask" in orch,
        checks,
        problems,
        "Ask planner + retrieve SMS path",
    )
    _check(
        "i7_explore_reuse",
        'type_ = "sms"' in find_py
        and 'filter === "email"' in explore_js
        and "id: \"sms\"" not in explore_js
        and all(x not in explore_js for x in ('label: "SMS"', "label: 'SMS'")),
        checks,
        problems,
        "Explore reuses Email/Text; no SMS app nav",
    )
    _check(
        "i7_gallery_default_hidden",
        "gallery_default_hidden" in find_py
        and "includeTexts" in explore_js
        and "galleryShowSms" in explore_js
        and "Add texts" in explore_js
        and "MBQL" not in find_py
        and "mbql" not in explore_js.lower(),
        checks,
        problems,
        "Default Gallery hides texts; Add/Only texts; no MBQL-001",
    )
    _check(
        "i7_archive_health",
        "_sms_ingested_metric" in summary
        and "ingest deferred" not in summary.lower()
        and "Missing source is not zero" in summary,
        checks,
        problems,
        "Archive Health staged vs ingested vs unavailable",
    )
    _check(
        "i7_cli",
        '"ingest-sms"' in main
        and '"inspect-sms"' in main
        and '"repair-sms-identities"' in main
        and '"prove-p2-i7"' in main
        and "prove-video" in main,
        checks,
        problems,
        "CLI ingest/inspect/prove-p2-i7 (P1 prove-video unchanged)",
    )
    explore_css = (root / "explore" / "static" / "explore.css").read_text(encoding="utf-8")
    _check(
        "i7_no_silent_5000_oldest",
        "SMS_RETRIEVE_CAP" in retrieve
        and "_year_fair_slice" in retrieve
        and "limit=max(limit, 5000)" not in retrieve
        and "hits[: max(1, int(limit))]" not in retrieve,
        checks,
        problems,
        "SMS retrieve is not a silent 5000 oldest-first cap",
    )
    _check(
        "i7_filter_sync_email_text",
        'nextType = "email"' in explore_js
        and "gallery_show_sms" in explore_js
        and "setTypeFilter(\"all\")" not in explore_js.split("liveFind(text)")[-1][:400],
        checks,
        problems,
        "Explicit text ask selects Email/Text filter",
    )
    _check(
        "i7_dark_readable_explore",
        "--mb-page: #0f141c" in explore_css
        and ".mb-card-textbody" in explore_css
        and "#e8edf5" in explore_css
        and 'background: #f8fafc' not in explore_css.split(".mb-card-media[data-type=\"sms\"]")[1][:200],
        checks,
        problems,
        "Explore dark theme; SMS card text is light on dark",
    )
    _check(
        "i7_hover_and_attach_indicator",
        "mb-qp-textbody" in explore_js
        and "mb-card-attach" in explore_js
        and "linked to this message" in explore_js,
        checks,
        problems,
        "Hover expands text; paperclip marks attachments",
    )
    _check(
        "i7_people_confirmed_phone",
        "ensure_confirmed_phone_contact" in phone
        and "repair_sms_identity_contacts" in phone
        and "Confirmed phone" in (root / "person" / "static" / "person-explore.js").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        "Unique SMS phone writes confirmed People contact",
    )
    _check(
        "i7_ask_keeps_person_context",
        "setActiveAsk" in explore_js
        and "setActivePerson" in (root / "ask" / "static" / "ask.html").read_text(encoding="utf-8")
        and 'PERSON.memoryMode = "all"' in explore_js,
        checks,
        problems,
        "Ask → People keeps person + query; Person opens All Memories",
    )
    _check(
        "i7_no_i8_email_product",
        "thread-as-email" not in comms
        and "richer email" not in comms.lower()
        and "mbox" not in comms,
        checks,
        problems,
        "I8 richer email not pulled in",
    )
    _check(
        "i7_no_i10_i11_narrative",
        "alaska trip" not in retrieve.lower()
        and "infer" not in comms.lower()
        and "narrative" not in comms.lower(),
        checks,
        problems,
        "No I10/I11 trip/narrative inference",
    )
    _check(
        "i7_fixture_present",
        FIXTURE.is_file() and ATTACHMENT.is_file() and "Export Notes" in FIXTURE.read_text(),
        checks,
        problems,
        "In-repo fixture + unused column + sibling attachment",
    )
    _check(
        "i7_parser_version",
        PARSER_VERSION.startswith("i7-sms"),
        checks,
        problems,
        f"parser {PARSER_VERSION}",
    )


def _logic(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ask.retrieve import EvidenceHit, _year_fair_slice, search_sms_messages
    from memorybox.context import AskContext
    from memorybox.explore.find import explicit_text_gallery, items_from_ask_result
    from memorybox.ingest import store as store
    from memorybox.ingest.comms_sms import ingest_sms
    from memorybox.person import resolve_person_by_name
    from memorybox.person.phone_map import resolve_handles
    from memorybox.planner import plan_ask
    from memorybox.profile.facts import add_contact
    from memorybox.status.summary import _sms_ingested_metric

    before = FIXTURE.read_bytes()
    headers, rows = iter_sms_rows(FIXTURE)
    _check(
        "i7_parse_rows",
        len(rows) == 10 and "Export Notes" in headers and "Chat Session" in headers,
        checks,
        problems,
        f"rows={len(rows)} headers={len(headers)}",
    )
    first = next(m for m in rows if "3D printing this weekend" in (m.body_text or ""))
    _check(
        "i7_fidelity_parse",
        first.direction == "outgoing"
        and first.service == "imessage"
        and first.thread_id == "Peggy"
        and first.sent_at
        and first.sent_at.startswith("2020-03-15")
        and first.source_metadata.get("Export Notes") == "keep-me"
        and first.attachments
        and first.attachments[0].get("filename") == "photo.jpg"
        and first.attachments[0].get("bytes_present") is True
        and first.attachments[0].get("promoted_to_immich") is False
        and first.attachments[0].get("standalone_explore_media") is False,
        checks,
        problems,
        "Parsed Peggy 2020 row preserves text/date/direction/thread/attachment/unused col",
    )
    group = next(m for m in rows if m.thread_id == "Core 4")
    _check(
        "i7_group_preserved",
        group.thread_id == "Core 4" and len(group.recipients) >= 2,
        checks,
        problems,
        "Group thread Core 4 kept (not a domain object)",
    )
    alaska = next(m for m in rows if "Alaska" in (m.body_text or ""))
    _check(
        "i7_correlation_metadata",
        alaska.latitude == "61.2181"
        and alaska.longitude == "-149.9003"
        and alaska.shared_location == "Anchorage"
        and alaska.source_metadata.get("Shared Location") == "Anchorage",
        checks,
        problems,
        "Explicit location fields preserved (no trip inference)",
    )
    inv = inspect_sms_export(FIXTURE, sample_rows=0)
    after_inspect = FIXTURE.read_bytes()
    _check(
        "i7_inspect_untouched",
        inv.get("ok") and inv.get("original_untouched") and before == after_inspect,
        checks,
        problems,
        "inspect-sms does not rewrite the export",
    )

    token = uuid4().hex[:6]
    peggy = resolve_person_by_name(f"I7 Peggy {token}", create_if_missing=True, confirm=True)
    denny = resolve_person_by_name(f"I7 Denny {token}", create_if_missing=True, confirm=True)
    amb_a = resolve_person_by_name(f"I7 PatA {token}", create_if_missing=True, confirm=True)
    amb_b = resolve_person_by_name(f"I7 PatB {token}", create_if_missing=True, confirm=True)
    add_contact(peggy.person_id, contact_kind="phone", value_text="555-010-1001")
    unique_phone = f"+15550{token}"
    add_contact(peggy.person_id, contact_kind="phone", value_text=unique_phone)
    add_contact(denny.person_id, contact_kind="phone", value_text="+1 (555) 020-2002")
    add_contact(amb_a.person_id, contact_kind="phone", value_text="555-030-3003")
    add_contact(amb_b.person_id, contact_kind="phone", value_text="+15550303003")

    result = ingest_sms(str(FIXTURE), label=f"i7-fixture-{token}")
    after_ingest = FIXTURE.read_bytes()
    _check(
        "i7_ingest_ok",
        bool(result.get("ok"))
        and (
            int(result.get("inserted") or 0) >= 10
            or int(result.get("skipped") or 0) >= 10
        ),
        checks,
        problems,
        f"ingest inserted={result.get('inserted')} skipped={result.get('skipped')}",
    )
    _check(
        "i7_original_untouched",
        bool(result.get("original_untouched")) and before == after_ingest,
        checks,
        problems,
        "ingest does not rewrite the CSV",
    )
    again = ingest_sms(str(FIXTURE), label=f"i7-fixture-{token}")
    _check(
        "i7_hash_skip",
        bool(again.get("ok")) and int(again.get("inserted") or 0) == 0,
        checks,
        problems,
        f"second ingest skipped={again.get('skipped')}",
    )

    eids = [UUID(x) for x in (result.get("evidence_ids") or [])]
    payloads = [_payload(store.get_evidence(eid) or {}) for eid in eids]
    peggy_2020 = next(
        p for p in payloads if "3D printing this weekend" in str(p.get("body_text") or "")
    )
    mapped_ids = {m.get("person_id") for m in (peggy_2020.get("identity_resolution") or {}).get("mapped") or []}
    live_map = resolve_handles([unique_phone])
    live_ids = {m.get("person_id") for m in live_map.get("mapped") or []}
    _check(
        "i7_unique_phone_automap",
        live_ids == {peggy.person_id}
        or peggy.person_id in mapped_ids
        or peggy.person_id in (peggy_2020.get("person_ids") or []),
        checks,
        problems,
        f"mapped={mapped_ids} live={live_map}",
    )
    unknown = next(p for p in payloads if "unmapped number" in str(p.get("body_text") or ""))
    unmapped_handles = {
        u.get("normalized")
        for u in (unknown.get("identity_resolution") or {}).get("unmapped") or []
    }
    _check(
        "i7_unmapped_retained",
        "+15559999099" in unmapped_handles
        and not (unknown.get("identity_resolution") or {}).get("mapped"),
        checks,
        problems,
        f"unmapped={unmapped_handles}",
    )
    shared = next(p for p in payloads if "Shared number hello" in str(p.get("body_text") or ""))
    amb = (shared.get("identity_resolution") or {}).get("ambiguous") or []
    _check(
        "i7_ambiguous_review",
        bool(amb) and amb[0].get("status") == "review" and len(amb[0].get("person_ids") or []) >= 2,
        checks,
        problems,
        f"ambiguous={amb}",
    )
    alaska_p = next(p for p in payloads if "Landed in Alaska" in str(p.get("body_text") or ""))
    _check(
        "i7_no_alaska_inference",
        alaska_p.get("latitude") == "61.2181"
        and not alaska_p.get("trip_id")
        and not alaska_p.get("place_id")
        and not alaska_p.get("inferred_trip")
        and (alaska_p.get("source_metadata") or {}).get("Export Notes") == "keep-me",
        checks,
        problems,
        "Alaska GPS/text preserved; no Place/Event/Trip invented",
    )
    attach_p = peggy_2020.get("attachments") or []
    _check(
        "i7_attachment_not_promoted",
        attach_p
        and attach_p[0].get("promoted_to_immich") is False
        and attach_p[0].get("standalone_explore_media") is False,
        checks,
        problems,
        "Attachment linked, not Immich/Explore-promoted",
    )

    ctx = AskContext(session_id=f"i7-{token}")
    plan_all = plan_ask("Show me all my text messages with Peggy", ctx)
    _check(
        "i7_plan_retrieve",
        plan_all.want_communication
        and plan_all.visual_scope == "none"
        and "want_sms_modality" in plan_all.notes
        and any(n.lower() == "peggy" for n in plan_all.person_names),
        checks,
        problems,
        f"plan notes={plan_all.notes} people={plan_all.person_names} scope={plan_all.visual_scope}",
    )
    fake_span = [
        EvidenceHit(
            evidence_id=f"y{year}-{i}",
            evidence_kind="communication",
            summary="x",
            score=1.0,
            excerpt="x",
            source="sms_export",
            sent_at=f"{year}-06-01T12:00:00",
        )
        for year in range(2008, 2026)
        for i in range(400)
    ]
    sliced, truncated = _year_fair_slice(fake_span, 5000)
    years_kept = { (h.sent_at or "")[:4] for h in sliced }
    _check(
        "i7_year_fair_keeps_recent",
        truncated
        and len(sliced) == 5000
        and "2008" in years_kept
        and "2019" in years_kept
        and "2025" in years_kept,
        checks,
        problems,
        f"year-fair years={sorted(years_kept)} n={len(sliced)}",
    )
    hits_peggy = search_sms_messages(plan_all, limit=5000)
    _check(
        "i7_ask_peggy",
        len(hits_peggy) >= 3
        and all((h.sent_at or "") >= "2020" for h in hits_peggy)
        and hits_peggy[0].sent_at <= hits_peggy[-1].sent_at,
        checks,
        problems,
        f"peggy hits={len(hits_peggy)}",
    )
    plan_2020 = plan_ask("Show me text messages with Peggy in 2020", ctx)
    hits_2020 = search_sms_messages(plan_2020, limit=5000)
    _check(
        "i7_ask_year",
        len(hits_2020) >= 2 and all((h.sent_at or "").startswith("2020") for h in hits_2020),
        checks,
        problems,
        f"2020 hits={len(hits_2020)} dates={[h.sent_at for h in hits_2020]}",
    )
    plan_kw = plan_ask("Show me text messages with Denny about 3D printing", ctx)
    hits_kw = search_sms_messages(plan_kw, limit=5000)
    _check(
        "i7_ask_keyword",
        any("3D printing" in (h.excerpt or h.summary or "") for h in hits_kw),
        checks,
        problems,
        f"keyword hits={len(hits_kw)}",
    )
    plan_out = plan_ask("How many text messages did I send in 2024?", ctx)
    hits_out = search_sms_messages(plan_out, limit=5000)
    _check(
        "i7_ask_outbound_count",
        len(hits_out) >= 1
        and hits_out[0].count_scope
        and "outbound_only" in (hits_out[0].count_scope or "")
        and str(len(hits_out)) in (hits_out[0].summary or ""),
        checks,
        problems,
        f"outbound n={len(hits_out)} scope={hits_out[0].count_scope if hits_out else None}",
    )
    plan_bi = plan_ask("How many times did Peggy and I text each other?", ctx)
    hits_bi = search_sms_messages(plan_bi, limit=5000)
    _check(
        "i7_ask_bidirectional",
        len(hits_bi) >= 3
        and any(n.lower() == "peggy" for n in plan_bi.person_names)
        and hits_bi[0].count_scope,
        checks,
        problems,
        f"bidirectional n={len(hits_bi)} people={plan_bi.person_names}",
    )

    fake_ask = {
        "evidence_hits": [h.to_dict() for h in hits_peggy],
        "plan": {"person_names": ["Peggy"]},
    }
    items = items_from_ask_result(fake_ask)
    dated_sms = [i for i in items if i.get("type") == "sms" and not i.get("undated")]
    _check(
        "i7_explore_dated_sms",
        len(dated_sms) >= 3 and all(i.get("date", "").startswith("20") for i in dated_sms),
        checks,
        problems,
        f"explore sms dated={len(dated_sms)}",
    )
    hidden = items_from_ask_result(
        {"evidence_hits": [h.to_dict() for h in hits_peggy], "plan": {"notes": ()}}
    )
    shown = items_from_ask_result(
        {
            "evidence_hits": [h.to_dict() for h in hits_peggy],
            "plan": {"notes": ("want_sms_modality",), "original_ask": "Show me all my texts with Peggy"},
        }
    )
    _check(
        "i7_gallery_visibility_rules",
        hidden
        and all(i.get("gallery_default_hidden") for i in hidden if i.get("type") == "sms")
        and shown
        and all(not i.get("gallery_default_hidden") for i in shown if i.get("type") == "sms")
        and not explicit_text_gallery({"plan": {"notes": ()}}, "Show me Peggy")
        and explicit_text_gallery(
            {"plan": {"notes": ("want_sms_modality",)}},
            "Show me all my texts with Peggy",
        ),
        checks,
        problems,
        "Broad memory ask hides Text cards; explicit text ask shows them",
    )

    metric = _sms_ingested_metric(
        count=len(payloads),
        unmapped_rows=1,
        date_min="2019-08-12",
        date_max="2024-06-01",
        staged=True,
        calculated_at="2026-08-14T00:00:00+00:00",
        pg="postgresql",
    )
    missing = _sms_ingested_metric(
        count=0,
        unmapped_rows=0,
        date_min=None,
        date_max=None,
        staged=False,
        calculated_at="2026-08-14T00:00:00+00:00",
        pg="postgresql",
    )
    _check(
        "i7_health_honesty",
        metric.get("state") == "available"
        and metric.get("value") == len(payloads)
        and missing.get("state") == "unavailable"
        and missing.get("value") is None,
        checks,
        problems,
        "ingested has a count; unavailable is not 0",
    )


def run_p2_i7_acceptance(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    _structural(checks, problems)
    try:
        _logic(checks, problems)
    except Exception as exc:  # noqa: BLE001
        _check(
            "i7_logic_suite",
            False,
            checks,
            problems,
            f"logic suite error: {type(exc).__name__}: {exc}",
        )

    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {
            "increment": "P2-I7",
            "mode": "flightsim" if flightsim else "harness",
            "fixture": str(FIXTURE),
        },
        "evs_status": {
            "EVS-223": "harness retrieve (Peggy fixture); FlightSim maps real Person after inspect-sms",
            "EVS-220": "harness bidirectional count + scope",
            "EVS-221": "harness outbound 2024 + scope",
            "EVS-222": "harness outbound count path (scope disclosed)",
            "EVS-224": "cited extract via evidence hits; messages reachable",
            "EVS-065": "harness 2020 window",
            "EVS-118": "harness Denny + 3D printing keyword",
            "EVS-106": "earn-in / disclose on real corpus — not invented here",
        },
        "note": (
            "Structural + fixture harness. ACCEPTED requires FlightSim owner pass of "
            "definition §8 against the real staged export. Q1 file bytes were not opened "
            "in this cloud environment; run inspect-sms on FlightSim before treating the "
            "1085-session CSV as fully understood. prove-p2-i7 is not P1 prove-video."
        ),
    }


def main() -> None:
    print(json.dumps(run_p2_i7_acceptance(), indent=2))


if __name__ == "__main__":
    main()
