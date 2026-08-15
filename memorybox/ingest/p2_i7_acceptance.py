"""P2-I7 SMS/Text Evidence — structural + fixture logic acceptance."""
from __future__ import annotations

import json
import os
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
    app_py = (root / "app.py").read_text(encoding="utf-8")
    shell_js = (root / "shell" / "static" / "shell.js").read_text(encoding="utf-8")
    shell_css = (root / "shell" / "static" / "shell.css").read_text(encoding="utf-8")
    sms_attach = (root / "explore" / "sms_attach.py").read_text(encoding="utf-8")
    ask_hist = (root / "ask" / "history.py").read_text(encoding="utf-8")
    attach_cache = (root / "ingest" / "sms_attach_cache.py").read_text(encoding="utf-8")
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")

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
        "i7_person_ask_photo_fallback",
        "face_asset_fallback" in retrieve
        and "_search_person_assets" in retrieve
        and "photos_empty_person_resolved" in retrieve
        and "resolved_person_ids_for_visual" in orch
        and "supersede_person_subject_change" in planner
        and "URLError" in (root / "providers" / "photo" / "_immich_http.py").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        "Show-me-person retries Immich RST and does not wipe photos/videos",
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
        and "setTypeFilter(\"all\")" not in explore_js.split("liveFind(text)")[-1][:400]
        and "maybeMergePersonVisuals" in explore_js
        and "gallery_default_hidden && !includeTexts" in explore_js
        and "keepTexts" in explore_js,
        checks,
        problems,
        "Explicit text ask selects Email/Text; All keeps texts and can join photos",
    )
    _check(
        "i7_dark_readable_explore",
        "--mb-page: #0f141c" in explore_css
        and ".mb-card-textbody" in explore_css
        and "#e8edf5" in explore_css
        and 'html[data-mb-surface="explore"] .mb-explore-filters button' in explore_css
        and 'background: #f8fafc' not in explore_css.split(".mb-card-media[data-type=\"sms\"]")[1][:200]
        and 'html[data-mb-surface="explore"]' in shell_css
        and "section:not([class*=\"mb-explore\"])" in shell_css
        and "body.mb-shell .mb-explore-filters button" in shell_css,
        checks,
        problems,
        "Explore dark theme; SMS card text is light on dark",
    )
    _check(
        "i7_hover_and_attach_indicator",
        "mb-qp-textbody" in explore_js
        and "mb-card-attach" in explore_js
        and "sms-attachment" in explore_js
        and "to-library" in explore_js
        and "immich" in explore_js.lower(),
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
        "i7_ask_history_100",
        "bindAskHistory" in shell_js
        and "slice(0, 100)" in shell_js
        and "ArrowUp" in shell_js
        and "localStorage" in shell_js
        and "hydrateAskHistory" in shell_js
        and "/ask/api/history" in shell_js
        and "HISTORY_MAX = 100" in ask_hist
        and "/ask/api/history" in app_py
        and "applyHistory" in shell_js
        and "ArrowDown" in shell_js
        and "histIndex" in shell_js
        and "parents[2]" in ask_hist
        and "bindExploreAskHistory" in explore_js
        and "histIndex" in explore_js
        and "mb-explore-ask-hist" not in explore_html
        and "mb-explore-ask-hist" not in explore_js,
        checks,
        problems,
        "Last 100 asks persist; empty Ask + Up/Down cycles one command in the box (no dropdown)",
    )
    _check(
        "i7_sms_attach_mb_library",
        "sms-attachment" in app_py
        and "to-library" in app_py
        and "add_sms_attachment_to_mb_library" in sms_attach
        and "add_mb_managed_representation" in sms_attach
        and "Never writes Immich" in sms_attach
        and "_dir_candidates" in sms_attach
        and "first-class" in explore_js
        and "_build_attach_index" in sms_attach
        and "ATTACH_PREVIEW_DELAY_MS" in explore_js
        and "cache_get" in attach_cache
        and "cache_put" in sms_attach
        and "sms-attachment/{evidence_id}/meta" in app_py
        and "_name_forms" in sms_attach
        and "put_media_object" in attach_cache
        and "bytes_ingested" in comms
        and "media_object_id" in comms
        and "inventory_export_attachments" in attach_cache
        and "sms_folder_has_attachment_bytes" in attach_cache
        and "_find_in_zips" in sms_attach,
        checks,
        problems,
        "SMS attachment is first-class on the message; optional Artifact copy; no Immich write",
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
        inv.get("ok")
        and inv.get("original_untouched")
        and before == after_inspect
        and inv.get("attachment_files_on_disk") == 1
        and "photo.jpg" in str(inv.get("sms_folder_listing") or ""),
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
            int(result.get("inserted") or 0) + int(result.get("skipped") or 0) >= 10
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
    peggy_eid = next(
        eid
        for eid in eids
        if "3D printing this weekend"
        in str((_payload(store.get_evidence(eid) or {})).get("body_text") or "")
    )
    from memorybox.explore.sms_attach import load_sms_attachment

    ingested = load_sms_attachment(str(peggy_eid), 0)
    _check(
        "i7_attachment_not_promoted",
        attach_p
        and attach_p[0].get("promoted_to_immich") is False
        and attach_p[0].get("standalone_explore_media") is False,
        checks,
        problems,
        "Attachment linked, not Immich/Explore-promoted",
    )
    _check(
        "i7_attachment_bytes_in_media_objects",
        bool(attach_p[0].get("media_object_id"))
        and attach_p[0].get("bytes_ingested") is True
        and bool(ingested.get("bytes_present")),
        checks,
        problems,
        "SMS attachment bytes stored on the message (media_objects), not export-path-only",
    )
    from memorybox.explore.sms_attach import _name_forms, resolve_attachment_file
    from memorybox.ingest.sms_attach_cache import cache_get, cache_put

    prev_cache = os.environ.get("MEMORYBOX_SMS_ATTACH_CACHE")
    tmp_cache = Path(os.environ.get("TMPDIR") or "/tmp") / f"mb-sms-attach-{token}"
    tmp_cache.mkdir(parents=True, exist_ok=True)
    os.environ["MEMORYBOX_SMS_ATTACH_CACHE"] = str(tmp_cache)
    cache_ok = False
    try:
        ima_name = "78715179111__AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG"
        cached = cache_put(ATTACHMENT, ima_name)
        forms = _name_forms(ima_name)
        resolved = resolve_attachment_file({"filename": ima_name, "source_ref": ima_name})
        cache_ok = (
            cached is not None
            and cache_get(ima_name) is not None
            and cache_get("AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG") is not None
            and "AF89223C-3F6A-417B-A3C2-485DF14A8835.JPG" in forms
            and resolved is not None
            and resolved.is_file()
        )
    finally:
        if prev_cache is None:
            os.environ.pop("MEMORYBOX_SMS_ATTACH_CACHE", None)
        else:
            os.environ["MEMORYBOX_SMS_ATTACH_CACHE"] = prev_cache
    _check(
        "i7_sms_attach_cache_and_uuid_names",
        cache_ok,
        checks,
        problems,
        "Local SMS attach cache + iMazing UUID filename forms",
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

    plan_from_to = plan_ask(
        "show me all the text messages from and to Peggy George", ctx
    )
    plan_short = plan_ask("show me Peggy George text messages", ctx)
    hits_from_to = search_sms_messages(plan_from_to, limit=5000)
    hits_short = search_sms_messages(plan_short, limit=5000)
    _check(
        "i7_ask_from_and_to_same_as_person_texts",
        "want_sms_modality" in plan_from_to.notes
        and any("peggy" in n.lower() for n in plan_from_to.person_names)
        and not any(n.lower() == "and" for n in plan_from_to.person_names)
        and {h.evidence_id for h in hits_from_to} == {h.evidence_id for h in hits_short}
        and len(hits_from_to) >= 3,
        checks,
        problems,
        f"from_to people={plan_from_to.person_names} n={len(hits_from_to)} short={len(hits_short)}",
    )

    plan_between = plan_ask(
        "Show me the last 100 messages between Peggy George and myself", ctx
    )
    hits_between = search_sms_messages(plan_between, limit=5000)
    _check(
        "i7_ask_last_n_between",
        "want_sms_modality" in plan_between.notes
        and any("peggy" in n.lower() for n in plan_between.person_names)
        and "last_100_newest" in (hits_between[0].count_scope or "")
        and len(hits_between) >= 3
        and len(hits_between) <= 100,
        checks,
        problems,
        f"between people={plan_between.person_names} n={len(hits_between)} scope={hits_between[0].count_scope if hits_between else None}",
    )

    plan_narr = plan_ask(
        "write a narrative about the last 100 text messages between me and Peggy George",
        ctx,
    )
    _check(
        "i7_ask_narrative_is_retrieve_not_i11",
        "want_sms_modality" in plan_narr.notes
        and any("peggy" in n.lower() for n in plan_narr.person_names)
        and bool(__import__("memorybox.ask.retrieve", fromlist=["SMS_NARRATIVE_RE"]).SMS_NARRATIVE_RE.search(plan_narr.original_ask)),
        checks,
        problems,
        f"narrative people={plan_narr.person_names} notes={plan_narr.notes}",
    )

    plan_in = plan_ask("how many text messages did Peggy George send to me?", ctx)
    hits_in = search_sms_messages(plan_in, limit=5000)
    _check(
        "i7_ask_inbound_count",
        "want_sms_modality" in plan_in.notes
        and hits_in
        and "inbound_only" in (hits_in[0].count_scope or "")
        and int(hits_in[0].match_total or 0) >= 1
        and not any("how" in n.lower() for n in plan_in.person_names)
        and all((h.direction or "").lower() == "incoming" for h in hits_in),
        checks,
        problems,
        f"inbound n={len(hits_in)} total={hits_in[0].match_total if hits_in else None} scope={hits_in[0].count_scope if hits_in else None}",
    )

    plan_heart = plan_ask("how many hear emoji's did Peggy George send me?", ctx)
    hits_heart = search_sms_messages(plan_heart, limit=5000)
    _check(
        "i7_ask_heart_emoji_count",
        "want_sms_modality" in plan_heart.notes
        and any("peggy" in n.lower() for n in plan_heart.person_names)
        and hits_heart
        and "heart_emoji_or_loved_tapback" in (hits_heart[0].count_scope or "")
        and int(hits_heart[0].match_total or 0) >= 1,
        checks,
        problems,
        f"heart people={plan_heart.person_names} n={len(hits_heart)} scope={hits_heart[0].count_scope if hits_heart else None}",
    )

    from memorybox.planner.temporal import parse_temporal

    xmas_time = parse_temporal("at christmas time in 2017")
    xmas_season = parse_temporal("christmas season 2017")
    plan_xmas = plan_ask(
        "how many times did Peggy and I text each other at christmas time in 2017",
        ctx,
    )
    hits_xmas = search_sms_messages(plan_xmas, limit=5000)
    xmas_scope = hits_xmas[0].count_scope if hits_xmas else ""
    _check(
        "i7_ask_christmas_time_window",
        xmas_time.windows == (("2017-12-04", "2018-01-01"),)
        and xmas_season.windows == (("2017-12-04", "2018-01-01"),)
        and plan_xmas.temporal_windows == (("2017-12-04", "2018-01-01"),)
        and any("peggy" in n.lower() for n in plan_xmas.person_names)
        and "keyword=christmas" not in xmas_scope
        and "christmas_window=minus_21d_through_nyd" in " ".join(plan_xmas.notes),
        checks,
        problems,
        f"windows={plan_xmas.temporal_windows} people={plan_xmas.person_names} scope={xmas_scope} notes={plan_xmas.notes}",
    )

    plan_att = plan_ask("show me Peggy George text messages with attachments", ctx)
    hits_att = search_sms_messages(plan_att, limit=5000)
    _check(
        "i7_ask_attachments_only",
        any("peggy" in n.lower() for n in plan_att.person_names)
        and not any("attach" in n.lower() for n in plan_att.person_names)
        and hits_att
        and "attachments_only" in (hits_att[0].count_scope or "")
        and all(h.attachments for h in hits_att),
        checks,
        problems,
        f"attach people={plan_att.person_names} n={len(hits_att)}",
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

    from memorybox.ask import history as ask_history

    hist_path = FIXTURE.parent / "ask_history_test.json"
    prev = os.environ.get("MEMORYBOX_ASK_HISTORY_PATH")
    os.environ["MEMORYBOX_ASK_HISTORY_PATH"] = str(hist_path)
    try:
        if hist_path.exists():
            hist_path.unlink()
        ask_history.remember_ask("show me texts with Peggy")
        ask_history.remember_ask("show me Peggy George")
        stored = ask_history.read_asks()
        _check(
            "i7_ask_history_persist",
            stored[:2] == ["show me Peggy George", "show me texts with Peggy"]
            and hist_path.is_file(),
            checks,
            problems,
            f"asks={stored}",
        )
    finally:
        if prev is None:
            os.environ.pop("MEMORYBOX_ASK_HISTORY_PATH", None)
        else:
            os.environ["MEMORYBOX_ASK_HISTORY_PATH"] = prev
        if hist_path.exists():
            hist_path.unlink()



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
