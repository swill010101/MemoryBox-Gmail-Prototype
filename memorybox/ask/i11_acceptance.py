"""P2-I11 Narrative & Summaries — Ask output_mode tell on existing curator."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.evidence_prep import prepare_narrative_pack
from memorybox.ask.narrative import memories_from_citations, persistable_view, tell_from_hits
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.ask.retrieve import (
    EvidenceHit,
    PhotoHit,
    _sms_ask,
    _tell_pack_comms,
    filter_hits_by_constraints,
)
from memorybox.context import AskContext, InMemoryContextStore
from memorybox.explore.find import (
    client_narrative_pack,
    curator_answer_text,
    explicit_calendar_gallery,
    explicit_email_gallery,
    explicit_text_gallery,
)
from memorybox.planner import compile_output_mode, plan_ask
from memorybox.planner.temporal import parse_temporal
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def run_prove_i11(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I11", "p1_runtime_final": flightsim}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-i11 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    print("prove-i11: checks running (JSON prints when finished)", flush=True)

    from memorybox.migrate import migrate

    meta["migrations_applied"] = migrate()

    root = Path(__file__).resolve().parents[1]
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    app_py = (root / "app.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    _check(
        "c05_c10_no_narration_screen",
        "/narration" not in app_py
        and 'id="mb-explore-copy"' in explore_html
        and 'id="mb-explore-save-story"' in explore_html
        and "Save as Story" in explore_html
        and "/story/drafts" in explore_js
        and "composed_by_model: true" in explore_js
        and "narrativeText" in explore_js
        and "Writing the narrative" in explore_js
        and 'method: "POST"' in explore_js
        and "tellOut !== \"tell\"" in explore_js,
        checks,
        problems,
        detail="Copy/Save as Story on Explore; no narration route",
    )

    ctx = AskContext(session_id="i11-prove")
    tell_plan = plan_ask("Tell me about Peggy", ctx)
    know_plan = plan_ask("what do you know about Peggy", ctx)
    show_plan = plan_ask("Show me Peggy", ctx)
    said_plan = plan_ask("what did Peggy say", ctx)
    have_plan = plan_ask("what do I have about Peggy", ctx)
    _check(
        "c01_tell_compiles",
        tell_plan.output_mode == "tell"
        and know_plan.output_mode == "tell"
        and compile_output_mode("Summarize our Alaska trip") == "tell"
        and tell_plan.act == "find"
        and tell_plan.gallery_show_sms is not True,
        checks,
        problems,
        detail=f"tell={tell_plan.output_mode} act={tell_plan.act} sms_gallery={tell_plan.gallery_show_sms}",
    )
    _check(
        "c02_show_not_essay",
        show_plan.output_mode == "show"
        and have_plan.output_mode == "show"
        and said_plan.output_mode == "show",
        checks,
        problems,
        detail=f"show={show_plan.output_mode} have={have_plan.output_mode} said={said_plan.output_mode}",
    )
    _check(
        "c09_said_about_not_tell",
        said_plan.output_mode == "show"
        and not said_plan.want_story
        and said_plan.want_communication,
        checks,
        problems,
        detail=f"story={said_plan.want_story} comms={said_plan.want_communication}",
    )

    tell_pack = curator_answer_text(
        {
            "answer_kind": "mixed",
            "answer_text": "Owner journal: harbor walk. Communications: packing list email.",
            "plan": {"output_mode": "tell"},
        }
    )
    show_pack = curator_answer_text(
        {
            "answer_kind": "photo_backed",
            "answer_text": "Found 12 photo hit(s).",
            "plan": {"output_mode": "show"},
        }
    )
    _check(
        "c04_tell_passes_answer_text",
        tell_pack is not None
        and "harbor walk" in tell_pack
        and show_pack is None,
        checks,
        problems,
        detail=f"tell={tell_pack!r} show={show_pack!r}",
    )

    tag = f"I11-{uuid4().hex[:8]}"
    from memorybox.journal.i10c import save_draft as save_journal_draft, save_journal

    draft_j = save_journal_draft(
        title="",
        body_text=f"Owner journal about {tag} harbor walk with a hidden-comms check phrase.",
        described_start_date=date.today(),
        described_precision="day",
        actor_key="owner",
    )
    saved = save_journal(
        draft_j["id"],
        title="",
        body_text=f"Owner journal about {tag} harbor walk with a hidden-comms check phrase.",
        described_start_date=date.today(),
        described_precision="day",
        actor_key="owner",
    )
    meta["synthetic_journal_id"] = saved.get("id")
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
    )
    print("prove-i11: AskOrchestrator tell (may take a bit on a full archive)...", flush=True)
    told = orch.ask(f"Tell me about {tag} harbor")
    journal_in_tell = tag.lower() in (told.answer_text or "").lower() or any(
        tag.lower() in str((s.get("text") or "")).lower()
        for s in (told.statements or [])
    )
    _check(
        "c03_tell_uses_journal_pack",
        (told.plan or {}).get("output_mode") == "tell"
        and journal_in_tell
        and saved.get("ask_available")
        and "evidence-backed account" not in (told.answer_text or "").lower(),
        checks,
        problems,
        detail=(told.answer_text or "")[:240],
    )
    shown = orch.ask("Show me Peggy")
    show_text = shown.answer_text or ""
    _check(
        "c02_show_answer_is_result_set",
        (shown.plan or {}).get("output_mode") == "show"
        and "evidence-backed account" not in show_text.lower()
        and "not family truth until you Save Story" not in show_text
        and "narration unavailable" not in show_text.lower(),
        checks,
        problems,
        detail=show_text[:200],
    )

    hidden_sms = {
        "answer_kind": "mixed",
        "answer_text": "Communications in the archive: packing list for Alaska.",
        "plan": {"output_mode": "tell"},
        "citations": [{"kind": "evidence", "evidence_id": "e1", "source": "sms_export", "summary": "packing list"}],
    }
    _check(
        "c03_hidden_comms_in_tell_prose",
        "packing list" in (curator_answer_text(hidden_sms) or ""),
        checks,
        problems,
        detail=str(curator_answer_text(hidden_sms)),
    )

    sms_plan = plan_ask("Tell me about Alaska packing", ctx)
    sms_text, sms_pack, _sms_meta = tell_from_hits(
        sms_plan,
        llm=FakeLlmProvider(),
        evidence=[
            EvidenceHit(
                evidence_id="e1",
                evidence_kind="communication",
                summary="SMS: see you in Alaska",
                score=1.0,
                excerpt="see you in Alaska packing list",
                source="sms_export",
                sent_at="2017-01-02T12:00:00",
                channel="sms",
            )
        ],
    )
    _check(
        "c03_pack_includes_hidden_style_comms",
        "Alaska" in sms_text
        and any(u.get("kind") == "communication" for u in (sms_pack.get("units") or [])),
        checks,
        problems,
        detail=sms_text[:180],
    )

    view = persistable_view(
        original_ask="Tell me about Peggy",
        plan=tell_plan.to_dict(),
        presentation={"gallery_show_sms": False},
    )
    _check(
        "c08_living_view_json",
        view.get("schema_version") == 1
        and view.get("output_mode") == "tell"
        and view.get("original_ask") == "Tell me about Peggy"
        and isinstance(view.get("plan"), dict)
        and view.get("presentation", {}).get("gallery_show_sms") is False,
        checks,
        problems,
        detail=str(sorted(view.keys())),
    )

    mems = memories_from_citations(
        [{"kind": "journal", "journal_id": saved.get("id"), "title": "j"}]
    )
    _check(
        "c07_memories_from_citations",
        mems and mems[0]["source_kind"] == "journal" and mems[0]["source_id"] == saved.get("id"),
        checks,
        problems,
        detail=str(mems),
    )

    from memorybox.story import StoryServiceError, get_story, save_draft, save_story

    draft = save_draft(
        title=f"I11 {tag}",
        body_text=told.answer_text or "proposed",
        composed_by_model=True,
    )
    freeze_rejected = False
    try:
        save_story(
            draft.id,
            title=f"I11 {tag}",
            body_text="proposed",
            composed_by_model=True,
        )
    except StoryServiceError:
        freeze_rejected = True
    again = get_story(draft.id)
    _check(
        "c06_c07_copy_noop_save_as_story_draft",
        (not draft.ask_available)
        and freeze_rejected
        and again is not None
        and not again.ask_available,
        checks,
        problems,
        detail=f"ask_available={draft.ask_available} freeze_rejected={freeze_rejected}",
    )

    from memorybox.ask.semantic import (
        register_interpretation,
        reset_interpretations,
        resolve_semantic_constraints,
    )
    from memorybox.ask.travel import extract_travel
    from memorybox.providers.base import ProviderUnavailable

    person_html = (root / "person" / "static" / "person-explore.html").read_text(encoding="utf-8")
    _check(
        "c05_shared_curator_not_unhide",
        'id="mb-explore-copy"' in person_html
        and "Save as Story" in person_html
        and "mb-person-hide-curator" in person_html
        and 'id="mb-explore-curator" hidden' in person_html,
        checks,
        problems,
        detail="Person Explorer uses the same curator actions, still hidden until tell",
    )

    authored_sample = (
        "Packing list for Maui.\n\nOn Tue, Jan 1, 2017 Alice wrote:\nQuoted older thread"
    )
    from memorybox.ask.authored import authored_email_text, sms_location_assertions

    authored, aflags = authored_email_text(authored_sample)
    _check(
        "c12_authored_email_pack_time",
        "Packing list" in authored and "Quoted older" not in authored,
        checks,
        problems,
        detail=authored[:120],
    )

    loc = sms_location_assertions("See you tomorrow", attachments=None)
    _check(
        "c19_sms_timestamp_not_location",
        loc == [],
        checks,
        problems,
        detail=str(loc),
    )
    loc2 = sms_location_assertions("I'm at the Maui airport")
    _check(
        "c19_sms_authored_place_basis",
        loc2 and loc2[0].get("basis") == "authored_text",
        checks,
        problems,
        detail=str(loc2),
    )

    delta_body = (
        "Delta Air Lines itinerary confirmation ABC12X\n"
        "Flight DL123 STL → OGG March 12, 2017\n"
        "Passengers: Tom Will"
    )
    hotel_body = (
        "Marriott hotel reservation confirmation HTL99A\n"
        "Check-in March 12, 2017 check-out March 18, 2017 Maui"
    )
    flight = extract_travel(
        subject="Delta itinerary confirmation",
        body=delta_body,
        source_unit_id="u-comm-1",
        source_evidence_id="e-delta",
    )
    lodging = extract_travel(
        subject="Marriott reservation",
        body=hotel_body,
        source_unit_id="u-comm-2",
        source_evidence_id="e-hotel",
    )
    checkout_only = extract_travel(
        subject="Thanks for staying",
        body="Checkout 2025-01-08. We hope you enjoyed your stay.",
        source_unit_id="u-comm-co",
        source_evidence_id="e-checkout",
    )
    car_date_only = extract_travel(
        subject="Weekend note",
        body="car 2025-01-03",
        source_unit_id="u-comm-car",
        source_evidence_id="e-car",
    )
    _check(
        "c24_dual_travel_extract",
        bool(flight)
        and flight.get("travel_kind") == "flight"
        and flight.get("origin") == "STL"
        and flight.get("destination") == "OGG"
        and flight.get("derived_from", {}).get("evidence_id") == "e-delta"
        and bool(lodging)
        and lodging.get("travel_kind") == "lodging"
        and checkout_only is None
        and car_date_only is None,
        checks,
        problems,
        detail=str(flight)[:240],
    )

    email_hit = EvidenceHit(
        evidence_id="e-delta",
        evidence_kind="communication",
        summary="Delta itinerary confirmation",
        score=1.0,
        excerpt=delta_body,
        source="email_mbox",
        sent_at="2017-03-01T12:00:00",
        channel="email",
    )
    cal_unrelated = EvidenceHit(
        evidence_id="e-cal-dentist",
        evidence_kind="calendar_event",
        summary="Dentist 2017",
        score=1.0,
        excerpt="cleaning",
        source="postgres_keyword",
        sent_at="2017-06-01T09:00:00",
        channel="calendar",
    )
    photo = PhotoHit(
        provider_key="fake",
        external_id="p-maui",
        taken_at="2017-03-14T10:00:00",
        people=["Tom"],
        location="Maui",
        thumb_url=None,
        web_url=None,
        latitude=20.8,
        longitude=-156.3,
        mb_person_id="person-tom",
        identity_trust="confirmed",
        original_filename="IMG_0001.JPG",
    )
    hawaii_plan = plan_ask("Tell me about my Hawaii trip in 2017", ctx)
    pack = prepare_narrative_pack(
        hawaii_plan,
        evidence=[email_hit, cal_unrelated],
        photos=[photo],
    )
    kinds = [u.get("kind") for u in pack.get("units") or []]
    travel_u = next((u for u in pack["units"] if u.get("kind") == "travel"), None)
    comm_u = next((u for u in pack["units"] if u.get("kind") == "communication"), None)
    media_u = next((u for u in pack["units"] if u.get("kind") == "media_observation"), None)
    _check(
        "c18_c24_pack_keeps_communication_and_travel",
        "communication" in kinds
        and "travel" in kinds
        and "calendar" not in kinds
        and travel_u is not None
        and comm_u is not None
        and travel_u.get("derived_from", {}).get("evidence_id") == "e-delta"
        and travel_u.get("provenance", {}).get("never_replaces_original") is True,
        checks,
        problems,
        detail=str(kinds),
    )
    presence = (media_u or {}).get("claims") or []
    _check(
        "c17_presence_not_photographer",
        any(c.get("type") == "presence" for c in presence)
        and (media_u or {}).get("flags", {}).get("filename_is_not_photographer") is True
        and not any(c.get("type") == "photographer" for c in presence),
        checks,
        problems,
        detail=str(presence),
    )
    _check(
        "c11_spam_excluded_constant",
        "spam" in (pack.get("coverage") or {}).get("excluded", []),
        checks,
        problems,
        detail=str((pack.get("coverage") or {}).get("excluded")),
    )
    _check(
        "c22_evidence_used_supplied_units",
        int((pack.get("evidence_used") or {}).get("emails") or 0) >= 1
        and int((pack.get("evidence_used") or {}).get("travel") or 0) >= 1
        and int((pack.get("evidence_used") or {}).get("photos") or 0) >= 1
        and int((pack.get("volume") or {}).get("supplied_to_model_n") or 0)
        == len(pack.get("units") or []),
        checks,
        problems,
        detail=str(pack.get("evidence_used")),
    )

    xmas_plan = plan_ask(
        "Tell me about what Peggy and I discussed around Christmas in 2017",
        ctx,
    )
    xmas_pack = prepare_narrative_pack(
        xmas_plan,
        evidence=[
            EvidenceHit(
                evidence_id="e-sms-1",
                evidence_kind="communication",
                summary="Peggy: packing gifts",
                score=1.0,
                excerpt="packing gifts",
                source="sms_export",
                sent_at="2017-12-20T12:00:00",
                channel="sms",
                people=["Peggy", "Tom"],
            ),
            cal_unrelated,
        ],
    )
    xmas_kinds = [u.get("kind") for u in xmas_pack.get("units") or []]
    _check(
        "c14_c20_narrow_calendar_not_year_dump",
        "calendar" not in xmas_kinds and "communication" in xmas_kinds,
        checks,
        problems,
        detail=str(xmas_kinds),
    )

    many = [
        EvidenceHit(
            evidence_id=f"e-{i}",
            evidence_kind="communication",
            summary=f"note {i} 2017 harbor",
            score=1.0,
            excerpt=f"day {i} harbor walk",
            source="email_mbox",
            sent_at=f"2017-{(i % 12) + 1:02d}-10T12:00:00",
            channel="email",
        )
        for i in range(50)
    ]
    jan_parse = parse_temporal("write a narrative about my January of 2025")
    comma_parse = parse_temporal("January, 2025")
    year_parse = parse_temporal("Tell me about my 2017")
    _check(
        "january_of_year_not_year_range",
        jan_parse.time_start == "2025-01-01"
        and jan_parse.time_end == "2025-01-31"
        and "temporal=month_year" in (jan_parse.notes or ())
        and comma_parse.time_start == "2025-01-01"
        and comma_parse.time_end == "2025-01-31"
        and year_parse.time_start == "2017-01-01"
        and year_parse.time_end == "2017-12-31"
        and "temporal=year_range" in (year_parse.notes or ()),
        checks,
        problems,
        detail=str(jan_parse.to_dict()),
    )
    jan_plan = plan_ask("write a narrative about my January of 2025", ctx)
    jan_pack = prepare_narrative_pack(
        jan_plan,
        evidence=[
            EvidenceHit(
                evidence_id="e-cal-jan",
                evidence_kind="calendar_event",
                summary="KofC Trivia Knight January",
                score=1.0,
                excerpt="planning",
                source="postgres_keyword",
                sent_at="2025-01-04T14:30:00+00:00",
                channel="calendar",
            ),
            EvidenceHit(
                evidence_id="e-cal-apr",
                evidence_kind="calendar_event",
                summary="Links to La Salle Golf Classic 2025",
                score=1.0,
                excerpt="golf",
                source="postgres_keyword",
                sent_at="2025-04-14T16:30:00+00:00",
                channel="calendar",
            ),
        ],
        journals=[
            {
                "journal_id": "j-aug",
                "excerpt": "On this day memory from last year.",
                "described_start_date": "2025-08-24",
            }
        ],
    )
    jan_days = sorted(
        {
            str((u.get("time") or {}).get("value") or "")[:10]
            for u in (jan_pack.get("units") or [])
        }
    )
    _check(
        "january_pack_drops_out_of_window",
        jan_plan.output_mode == "tell"
        and jan_plan.time_start == "2025-01-01"
        and jan_plan.time_end == "2025-01-31"
        and jan_days == ["2025-01-04"]
        and int((jan_pack.get("evidence_used") or {}).get("calendar_events") or 0) == 1
        and int((jan_pack.get("evidence_used") or {}).get("journal_entries") or 0) == 0,
        checks,
        problems,
        detail=str({"days": jan_days, "plan": jan_plan.time_start, "used": jan_pack.get("evidence_used")}),
    )
    jan_find = {"plan": jan_plan.to_dict(), "ask": jan_plan.original_ask}
    _check(
        "c03_tell_hides_gallery_comms",
        not explicit_text_gallery(jan_find, jan_plan.original_ask)
        and not explicit_email_gallery(jan_find, jan_plan.original_ask)
        and not explicit_calendar_gallery(jan_find, jan_plan.original_ask)
        and "want_sms_modality" in (jan_plan.notes or ()),
        checks,
        problems,
        detail=str(
            {
                "sms": explicit_text_gallery(jan_find, jan_plan.original_ask),
                "email": explicit_email_gallery(jan_find, jan_plan.original_ask),
                "cal": explicit_calendar_gallery(jan_find, jan_plan.original_ask),
            }
        ),
    )
    year_hit = EvidenceHit(
        evidence_id="e-jan-mail",
        evidence_kind="communication",
        summary="Lunch plans",
        score=1.0,
        excerpt="see you tuesday",
        source="email_mbox",
        sent_at="2025-01-12T12:00:00",
        channel="email",
    )
    _check(
        "january_tell_not_full_sms_export",
        not _sms_ask(jan_plan)
        and _tell_pack_comms(jan_plan)
        and filter_hits_by_constraints([year_hit], ["2025"]) == [year_hit],
        checks,
        problems,
        detail=f"sms_ask={_sms_ask(jan_plan)} tell_pack={_tell_pack_comms(jan_plan)}",
    )
    year_plan = plan_ask("Tell me about my 2017", ctx)
    year_pack = prepare_narrative_pack(year_plan, evidence=many)
    _check(
        "c16_c21_hierarchical_not_first_n",
        (year_pack.get("volume") or {}).get("reduction") in {"hierarchical_summary", "organize"}
        and (year_pack.get("derived_summaries") or [])
        and int((year_pack.get("volume") or {}).get("retrieved_n") or 0) == 50
        and int((year_pack.get("volume") or {}).get("supplied_to_model_n") or 0) < 50,
        checks,
        problems,
        detail=str(year_pack.get("volume")),
    )
    mixed_hits = [
        EvidenceHit(
            evidence_id=f"e-tr-{i}",
            evidence_kind="communication",
            summary="Marriott reservation confirmation HTL99A",
            score=1.0,
            excerpt=(
                "Marriott hotel reservation confirmation HTL99A "
                f"Check-in 2025-01-{(i % 20) + 1:02d} Maui"
            ),
            source="email_mbox",
            sent_at=f"2025-01-{(i % 20) + 1:02d}T12:00:00",
            channel="email",
        )
        for i in range(40)
    ] + [
        EvidenceHit(
            evidence_id=f"e-lunch-{i}",
            evidence_kind="communication",
            summary="Lunch plans",
            score=1.0,
            excerpt="see you tuesday",
            source="email_mbox",
            sent_at=f"2025-01-{(i % 20) + 1:02d}T13:00:00",
            channel="email",
        )
        for i in range(20)
    ]
    mixed_pack = prepare_narrative_pack(jan_plan, evidence=mixed_hits)
    mixed_kinds = [u.get("kind") for u in mixed_pack.get("units") or []]
    mixed_ids = [
        len(s.get("unit_ids") or []) for s in (mixed_pack.get("derived_summaries") or [])
    ]
    slim = client_narrative_pack(mixed_pack) or {}
    slim_blob = str(slim)
    _check(
        "hierarchy_keeps_authored_not_all_travel",
        mixed_kinds.count("travel") <= 6
        and mixed_kinds.count("communication") >= 1
        and int((mixed_pack.get("volume") or {}).get("supplied_to_model_n") or 0) <= 24
        and (not mixed_ids or max(mixed_ids) <= 12)
        and "unit_ids" not in slim_blob
        and isinstance(slim.get("evidence_used"), dict),
        checks,
        problems,
        detail=str(
            {
                "kinds": {k: mixed_kinds.count(k) for k in set(mixed_kinds)},
                "supplied": (mixed_pack.get("volume") or {}).get("supplied_to_model_n"),
                "unit_id_lens": mixed_ids,
            }
        ),
    )
    quoted_hit = EvidenceHit(
        evidence_id="e-quoted-jan",
        evidence_kind="communication",
        summary="Re: Garden",
        score=1.0,
        excerpt=(
            "OK, PT at noon on the 28th.\n"
            "On Wed, Jan 22, 2025 at 10:48 AM Michelle Cook "
            "<mcook@lasalleretreat.org> wrote:\nHow about Wednesday"
        ),
        source="email_mbox",
        sent_at="2025-01-22T08:33:00",
        channel="email",
        thread_id="t-garden",
    )
    dump_text, _dump_pack, dump_meta = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=[quoted_hit]
    )
    _check(
        "fake_tell_is_prose_not_email_dump",
        "here is a short account" in dump_text.lower()
        and "without pasting" in dump_text.lower()
        and "wrote:" not in dump_text.lower()
        and "mcook@" not in dump_text.lower()
        and dump_meta.get("ok") is True,
        checks,
        problems,
        detail=dump_text[:280],
    )

    class _DownLlm:
        provider_key = "down"

        def health(self):
            from memorybox.providers.base import ProviderHealth

            return ProviderHealth(provider_key="down", ok=False, detail="down")

        def chat(self, messages, *, json_mode=False):
            raise ProviderUnavailable("model down")

    down_text, down_pack, down_meta = tell_from_hits(
        hawaii_plan,
        llm=_DownLlm(),
        evidence=[email_hit],
        photos=[photo],
    )
    _check(
        "c23_fail_closed_no_stitch",
        down_meta.get("fail_closed") is True
        and "narration unavailable" in down_text.lower()
        and "evidence-backed account" not in down_text.lower()
        and (down_pack.get("units") or []),
        checks,
        problems,
        detail=down_text[:240],
    )

    planner_src = (root / "planner" / "__init__.py").read_text(encoding="utf-8")
    semantic_src = (root / "ask" / "semantic.py").read_text(encoding="utf-8")
    reset_interpretations()
    unresolved = resolve_semantic_constraints("Tell me about when Dad was young")
    _check(
        "c25_no_hardcoded_young_range",
        unresolved
        and unresolved[0].constraint_kind == "age_band"
        and unresolved[0].age_band is None
        and not unresolved[0].resolved
        and "when_he_was_young" not in planner_src
        and "age_band=(10, 25)" not in semantic_src
        and "age_band: [10, 25]" not in semantic_src
        and "age_band: [10,25]" not in planner_src,
        checks,
        problems,
        detail=str(unresolved[0].to_dict()),
    )
    register_interpretation("relative_youth", version="owner.v1", age_band=(16, 24))
    resolved_band = resolve_semantic_constraints("when Dad was young")
    _check(
        "c25_generic_fields_not_phrase_column",
        resolved_band
        and resolved_band[0].age_band == (16, 24)
        and resolved_band[0].interpretation_id == "relative_youth"
        and resolved_band[0].interpretation_version == "owner.v1"
        and "when_he_was_young" not in resolved_band[0].to_dict(),
        checks,
        problems,
        detail=str(resolved_band[0].to_dict()),
    )
    reset_interpretations()
    young_ask = orch.ask("Tell me about when Dad was young")
    _check(
        "c25_ask_rather_than_guess",
        (young_ask.answer_kind == "clarification")
        or (
            "guess" in (young_ask.answer_text or "").lower()
            or "age" in (young_ask.answer_text or "").lower()
            or "young" in (young_ask.answer_text or "").lower()
        ),
        checks,
        problems,
        detail=(young_ask.answer_text or "")[:240],
    )

    view2 = persistable_view(
        original_ask="Show me Dad when he was young",
        plan={
            "output_mode": "tell",
            "semantic_constraints": [unresolved[0].to_dict()],
        },
        presentation={"gallery_show_sms": False},
    )
    _check(
        "c08_semantic_constraints_on_plan",
        view2["plan"].get("semantic_constraints")
        and "when_he_was_young" not in str(view2)
        and view2.get("output_mode") == "tell",
        checks,
        problems,
        detail=str(view2["plan"].get("semantic_constraints")),
    )

    _check(
        "c15_fake_llm_synthesizes_from_pack",
        "harbor" in (told.answer_text or "").lower()
        or "Family evidence used" in (told.answer_text or ""),
        checks,
        problems,
        detail=(told.answer_text or "")[:240],
    )

    if flightsim:
        print(
            "prove-i11 --flightsim: POST live /explore/api/find "
            "(needs Ask/serve; can take a couple of minutes)...",
            flush=True,
        )
        _prove_i11_flightsim_live(checks, problems, meta)

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}


def _prove_i11_flightsim_live(
    checks: dict[str, Any], problems: list[str], meta: dict[str, Any]
) -> None:
    import json
    import urllib.error
    import urllib.request

    port = os.environ.get("MEMORYBOX_PORT") or "8790"
    base = (os.environ.get("MEMORYBOX_BASE_URL") or f"http://127.0.0.1:{port}").rstrip("/")
    meta["base_url"] = base
    ask = "write a narrative about my January of 2025"
    req = urllib.request.Request(
        base + "/explore/api/find",
        data=json.dumps({"ask": ask, "session_id": "i11-flightsim"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)
            st = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            err_body = ""
        _check(
            "flightsim_live_january_tell",
            False,
            checks,
            problems,
            detail=f"{base}/explore/api/find failed: {exc} {err_body}",
        )
        return
    except Exception as exc:  # noqa: BLE001
        _check(
            "flightsim_live_january_tell",
            False,
            checks,
            problems,
            detail=f"{base}/explore/api/find failed: {exc}",
        )
        return
    plan = body.get("plan") or {}
    est = body.get("explore_state") or {}
    pack = body.get("narrative_pack") or {}
    used = pack.get("evidence_used") or {}
    prose = str(body.get("narrative_text") or body.get("summary") or "").strip()
    mode = body.get("output_mode") or plan.get("output_mode")
    slim_ok = "unit_ids" not in json.dumps(pack)
    authored = int(used.get("emails") or 0) + int(used.get("sms") or 0) + int(
        used.get("calendar_events") or 0
    )
    _check(
        "flightsim_live_january_tell",
        st == 200
        and mode == "tell"
        and str(plan.get("time_start") or "")[:10] == "2025-01-01"
        and str(plan.get("time_end") or "")[:10] == "2025-01-31"
        and not est.get("gallery_show_sms")
        and not est.get("gallery_show_email")
        and len(prose) > 20
        and slim_ok
        and int(used.get("travel") or 0) <= 6
        and authored >= 1
        and prose.lower().count("wrote:") < 3
        and "mcook@" not in prose.lower(),
        checks,
        problems,
        detail=str(
            {
                "status": st,
                "mode": mode,
                "time": [plan.get("time_start"), plan.get("time_end")],
                "gallery_sms": est.get("gallery_show_sms"),
                "gallery_email": est.get("gallery_show_email"),
                "items": len(body.get("items") or []),
                "used": used,
                "slim": slim_ok,
                "prose": prose[:180],
            }
        ),
    )
