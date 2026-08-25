"""P2-I11 Narrative & Summaries — Ask output_mode tell on existing curator."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.episode_semantics import public_episode_dump
from memorybox.ask.evidence_prep import prepare_narrative_pack
from memorybox.ask.narrative import (
    SYSTEM_PROMPT,
    coverage_incomplete_line,
    memories_from_citations,
    missing_modality_lines,
    pack_for_narrator,
    persistable_view,
    tell_from_hits,
)
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.ask.retrieve import (
    EvidenceHit,
    PhotoHit,
    _sms_ask,
    _tell_pack_comms,
    filter_hits_by_constraints,
    search_photos,
    visual_library_person_ids,
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
from memorybox.providers.llm.dto import ChatMessage
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
        and "Collecting photos" in explore_js
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
    jan_ctx = AskContext(
        session_id="i11-peggy-after-jan",
        time_start="2026-01-01",
        time_end="2026-01-31",
    )
    peggy_after_jan = plan_ask("Tell me what you know about Peggy", jan_ctx)
    know_after_jan = plan_ask("what do you know about Peggy", jan_ctx)
    jan_tell = plan_ask("write a narrative about my January of 2026", AskContext(session_id="i11-jan"))
    _check(
        "c02b_peggy_know_does_not_inherit_january",
        any(n.lower() == "peggy" for n in (peggy_after_jan.person_names or ()))
        and peggy_after_jan.output_mode == "show"
        and peggy_after_jan.subject_changed
        and peggy_after_jan.time_start is None
        and peggy_after_jan.time_end is None
        and not peggy_after_jan.temporal_windows
        and "inherited_missing_slots_only" not in (peggy_after_jan.notes or ())
        and any(n.lower() == "peggy" for n in (know_after_jan.person_names or ()))
        and know_after_jan.time_start is None
        and know_after_jan.subject_changed
        and jan_tell.output_mode == "tell"
        and jan_tell.time_start == "2026-01-01"
        and jan_tell.time_end == "2026-01-31",
        checks,
        problems,
        detail=(
            f"peggy={peggy_after_jan.person_names} t={peggy_after_jan.time_start} "
            f"win={peggy_after_jan.temporal_windows} notes={peggy_after_jan.notes} "
            f"jan_tell={jan_tell.time_start}..{jan_tell.time_end}"
        ),
    )
    mixed_show = curator_answer_text(
        {
            "answer_kind": "mixed",
            "answer_text": "January 2026 essay that must not stay on screen.",
            "plan": {"output_mode": "show"},
        }
    )
    _check(
        "c02c_mixed_show_drops_tell_essay",
        mixed_show is None,
        checks,
        problems,
        detail=repr(mixed_show),
    )
    _check(
        "c02d_explore_clears_tell_on_new_show_ask",
        "Do not keep the previous tell essay" in explore_js
        and "never restore a leftover tell essay" in explore_js
        and 'outputMode = isTellAsk(askText) ? "tell" : "show"' in explore_js
        and 'outputMode: nextOutputMode === "tell" ? "tell" : "show"' in explore_js,
        checks,
        problems,
        detail="showSearching and applyPayloadToState replace curator on a new show Ask",
    )
    _jan_lib, jan_requestor = visual_library_person_ids(jan_tell)
    peggy_lib, peggy_requestor = visual_library_person_ids(peggy_after_jan)
    _check(
        "c02e_period_tell_does_not_name_owner_as_subject",
        not (jan_tell.person_names or ())
        and not (jan_tell.person_ids or ())
        and any(n.lower() == "peggy" for n in (peggy_after_jan.person_names or ()))
        and peggy_requestor is None
        and not (peggy_lib),
        checks,
        problems,
        detail=(
            f"jan_names={jan_tell.person_names} jan_ids={jan_tell.person_ids} "
            f"jan_req={jan_requestor} peggy_names={peggy_after_jan.person_names} "
            f"peggy_req={peggy_requestor}"
        ),
    )
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import patch

    from memorybox.providers.photo.dto import PhotoAssetDto, PhotoPersonRef

    req_pid = str(uuid4())
    immich_ext = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    jan_asset = PhotoAssetDto(
        provider_key="fake_photo",
        external_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        original_filename="january_trip.jpg",
        taken_at=datetime(2026, 1, 14, 16, 0, tzinfo=timezone.utc),
        people=(
            PhotoPersonRef(
                provider_key="fake_photo",
                external_id=immich_ext,
                display_name="Requestor",
            ),
        ),
    )
    req_photo = FakePhotoProvider(extra_assets=[jan_asset])
    req_person = SimpleNamespace(
        id=req_pid,
        display_name="Requestor",
        identity_authority="confirmed",
        provider_mappings=(
            {
                "provider_key": "fake_photo",
                "external_id": immich_ext,
                "identity_authority": "confirmed",
            },
        ),
    )
    with (
        patch(
            "memorybox.profile.owner.get_requestor_person_id",
            return_value=req_pid,
        ),
        patch("memorybox.person.get_person", return_value=req_person),
        patch(
            "memorybox.person.list_provider_external_ids_for_person",
            return_value=[immich_ext],
        ),
        patch(
            "memorybox.person.resolve_immich_external_ids_for_person",
            return_value=[],
        ),
    ):
        photo_hits, photo_status = search_photos(jan_tell, req_photo, limit=0)
        peggy_photo_hits, peggy_photo_status = search_photos(
            peggy_after_jan, req_photo, limit=0
        )
    _check(
        "c02e_period_tell_searches_requestor_photo_library",
        bool(photo_hits)
        and photo_status.get("requestor_library") is True
        and photo_status.get("requestor_person_id") == req_pid
        and any(
            (h.taken_at or "").startswith("2026-01")
            for h in photo_hits
        )
        and not (jan_tell.person_names or ())
        and peggy_photo_status.get("requestor_library") is not True,
        checks,
        problems,
        detail=str(
            {
                "n": len(photo_hits),
                "status": {
                    k: photo_status.get(k)
                    for k in (
                        "requestor_library",
                        "requestor_person_id",
                        "detail",
                        "after_temporal_filter",
                    )
                },
                "peggy_req": peggy_photo_status.get("requestor_library"),
                "peggy_n": len(peggy_photo_hits),
            }
        ),
    )
    _check(
        "c02e_empty_requestor_photos_are_python_truth",
        "No photos were found for this period."
        == missing_modality_lines(
            {
                "coverage": {"missing": ["photos"]},
                "scope": {"requestor_library": True},
            }
        )
        and missing_modality_lines(
            {
                "coverage": {"missing": ["photos"]},
                "scope": {"requestor_library": False, "people": ["Peggy"]},
            }
        )
        == "",
        checks,
        problems,
        detail="period tell with a searched empty photo library; named subject Ask is unchanged",
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
        and "turn the essay into family truth" not in show_text
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
        "c22_evidence_used_considered_units",
        int((pack.get("evidence_used") or {}).get("emails") or 0) >= 1
        and int((pack.get("evidence_used") or {}).get("travel") or 0) >= 1
        and int((pack.get("evidence_used") or {}).get("photos") or 0) >= 1
        and int((pack.get("volume") or {}).get("eligible_n") or 0)
        == int((pack.get("volume") or {}).get("processed_n") or -1)
        and int((pack.get("volume") or {}).get("narrator_input_n") or 0)
        == len(pack.get("narrator_episodes") or []),
        checks,
        problems,
        detail=str({"used": pack.get("evidence_used"), "volume": pack.get("volume")}),
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
    sms_hits = [
        EvidenceHit(
            evidence_id=f"e-sms-{i}",
            evidence_kind="communication",
            summary=f"SMS {i}",
            score=1.0,
            excerpt="on my way",
            source="sms_export",
            sent_at=f"2025-01-{(i % 20) + 1:02d}T18:00:00",
            channel="sms",
            thread_id=f"sms-thread-{i}",
        )
        for i in range(30)
    ]
    mail_hits = [
        EvidenceHit(
            evidence_id=f"e-mail-{i}",
            evidence_kind="communication",
            summary=f"Lunch {i}",
            score=1.0,
            excerpt="see you tuesday",
            source="email_mbox",
            sent_at=f"2025-01-{(i % 20) + 1:02d}T12:00:00",
            channel="email",
            thread_id=f"mail-thread-{i}",
        )
        for i in range(40)
    ]
    sms_pack = prepare_narrative_pack(jan_plan, evidence=sms_hits + mail_hits)
    _check(
        "january_tell_not_full_sms_export",
        not _sms_ask(jan_plan)
        and _tell_pack_comms(jan_plan)
        and filter_hits_by_constraints([year_hit], ["2025"]) == [year_hit],
        checks,
        problems,
        detail=f"sms_ask={_sms_ask(jan_plan)} tell_pack={_tell_pack_comms(jan_plan)}",
    )
    _check(
        "january_tell_pack_includes_sms",
        int((sms_pack.get("evidence_used") or {}).get("sms") or 0) >= 1
        and int((sms_pack.get("evidence_used") or {}).get("emails") or 0) >= 1,
        checks,
        problems,
        detail=str(sms_pack.get("evidence_used")),
    )
    year_plan = plan_ask("Tell me about my 2017", ctx)
    year_pack = prepare_narrative_pack(year_plan, evidence=many)
    _check(
        "c16_c21_hierarchical_not_first_n",
        (year_pack.get("volume") or {}).get("reduction")
        in {"hierarchical_summary", "hierarchical_episode", "organize"}
        and (year_pack.get("derived_summaries") or [])
        and int((year_pack.get("volume") or {}).get("retrieved_n") or 0) == 50
        and int((year_pack.get("volume") or {}).get("eligible_n") or 0) == 50
        and int((year_pack.get("volume") or {}).get("processed_n") or 0) == 50
        and int((year_pack.get("volume") or {}).get("narrator_input_n") or 0) < 50
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
        mixed_kinds.count("communication") >= 1
        and mixed_kinds.count("travel") >= 1
        and mixed_kinds.count("travel") >= 1
        and int((mixed_pack.get("volume") or {}).get("eligible_n") or 0)
        == int((mixed_pack.get("volume") or {}).get("processed_n") or -1)
        and int((mixed_pack.get("volume") or {}).get("narrator_input_n") or 0) <= 24
        and (not mixed_ids or max(mixed_ids) <= 12)
        and "unit_ids" not in slim_blob
        and isinstance(slim.get("evidence_considered") or slim.get("evidence_used"), dict),
        checks,
        problems,
        detail=str(
            {
                "kinds": {k: mixed_kinds.count(k) for k in set(mixed_kinds)},
                "narrator": (mixed_pack.get("volume") or {}).get("narrator_input_n"),
                "eligible": (mixed_pack.get("volume") or {}).get("eligible_n"),
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
        "wrote:" not in dump_text.lower()
        and "mcook@" not in dump_text.lower()
        and "evidence item" not in dump_text.lower()
        and dump_meta.get("ok") is True
        and ("garden" in dump_text.lower() or "pt at noon" in dump_text.lower() or "january" in dump_text.lower()),
        checks,
        problems,
        detail=dump_text[:280],
    )

    shuffled = list(reversed(sms_hits + mail_hits))
    period_text, period_pack, _ = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=shuffled
    )
    period_l = period_text.lower()
    vol = period_pack.get("volume") or {}
    _check(
        "bounded_period_processes_all_eligible",
        int(vol.get("eligible_n") or 0) == int(vol.get("processed_n") or -1)
        and int((period_pack.get("evidence_considered") or {}).get("sms") or 0) == 30
        and int((period_pack.get("evidence_considered") or {}).get("emails") or 0) == 40
        and int(vol.get("narrator_input_n") or 0) <= 24
        and int(vol.get("eligible_n") or 0) > int(vol.get("narrator_input_n") or 0)
        and "year-fair" not in period_l
        and "ingested sms" not in period_l
        and "n=530" not in period_l
        and "evidence item" not in period_l
        and "2025-w01:" not in period_l
        and "\n\n" in period_text,
        checks,
        problems,
        detail=str({"volume": vol, "used": period_pack.get("evidence_considered"), "prose": period_text[:220]}),
    )

    four_week_hits = []
    for w, day in enumerate(("2025-01-06", "2025-01-13", "2025-01-20", "2025-01-27")):
        for i in range(20):
            four_week_hits.append(
                EvidenceHit(
                    evidence_id=f"e-w{w}-{i}",
                    evidence_kind="communication",
                    summary=f"note week {w} item {i}",
                    score=1.0,
                    excerpt=f"planning item {i}",
                    source="email_mbox" if i % 2 == 0 else "sms_export",
                    sent_at=f"{day}T{8 + (i % 10):02d}:00:00",
                    channel="email" if i % 2 == 0 else "sms",
                    thread_id=f"t-w{w}-{i}",
                )
            )
    large_pack = prepare_narrative_pack(jan_plan, evidence=four_week_hits)
    large_weeks = {
        str(s.get("period"))
        for s in (large_pack.get("derived_summaries") or [])
        if int(s.get("unit_n") or 0) > 0
    }
    _check(
        "large_set_weeks_all_covered",
        len(four_week_hits) >= 80
        and int((large_pack.get("volume") or {}).get("eligible_n") or 0) == 80
        and int((large_pack.get("volume") or {}).get("processed_n") or 0) == 80
        and int((large_pack.get("volume") or {}).get("narrator_input_n") or 0) <= 24
        and int((large_pack.get("volume") or {}).get("eligible_n") or 0)
        > int((large_pack.get("volume") or {}).get("narrator_input_n") or 0)
        and len(large_weeks) >= 4,
        checks,
        problems,
        detail=str({"volume": large_pack.get("volume"), "weeks": sorted(large_weeks)}),
    )

    later_first = [
        EvidenceHit(
            evidence_id="e-late",
            evidence_kind="communication",
            summary="Late January note",
            score=9.0,
            excerpt="PT at noon; closing the month after physical therapy",
            source="email_mbox",
            sent_at="2025-01-28T12:00:00",
            channel="email",
            thread_id="t-late",
        ),
        EvidenceHit(
            evidence_id="e-early",
            evidence_kind="communication",
            summary="Early January note",
            score=1.0,
            excerpt="harbor dinner to open the month",
            source="sms_export",
            sent_at="2025-01-03T12:00:00",
            channel="sms",
            thread_id="t-early",
        ),
    ]
    chrono_text, chrono_pack, _ = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=later_first
    )
    chrono_l = chrono_text.lower()
    early_at = chrono_l.find("2025-01-03")
    late_at = chrono_l.find("2025-01-28")
    if early_at < 0:
        early_at = chrono_l.find("early january")
    if late_at < 0:
        late_at = chrono_l.find("late january")
    ep_days = [
        str((e.get("time") or {}).get("value") or "")[:10]
        for e in (chrono_pack.get("episodes") or [])
    ]
    _check(
        "period_narrative_is_chronological",
        ep_days == sorted(ep_days)
        and early_at != -1
        and late_at != -1
        and early_at < late_at,
        checks,
        problems,
        detail=str({"ep_days": ep_days, "early": early_at, "late": late_at, "prose": chrono_text[:240]}),
    )

    same_day = "2025-01-15T10:00:00"
    cross_hits = [
        EvidenceHit(
            evidence_id="e-cross-mail",
            evidence_kind="communication",
            summary="Harbor dinner plans",
            score=1.0,
            excerpt="Harbor dinner at 7",
            source="email_mbox",
            sent_at=same_day,
            channel="email",
            people=["Alex"],
            thread_id="t-harbor-dinner",
        ),
        EvidenceHit(
            evidence_id="e-cross-sms",
            evidence_kind="communication",
            summary="Harbor dinner",
            score=1.0,
            excerpt="see you at harbor dinner",
            source="sms_export",
            sent_at="2025-01-15T10:05:00",
            channel="sms",
            people=["Alex"],
            thread_id="t-harbor-sms",
        ),
        EvidenceHit(
            evidence_id="e-cross-cal",
            evidence_kind="calendar_event",
            summary="Harbor dinner",
            score=1.0,
            excerpt="Harbor",
            source="ics",
            sent_at="2025-01-15T19:00:00",
            channel="calendar",
            people=["Alex"],
        ),
    ]
    cross_photo = PhotoHit(
        provider_key="fake",
        external_id="p-harbor-dinner",
        taken_at="2025-01-15T19:30:00",
        people=["Alex"],
        location="Harbor",
        thumb_url=None,
        web_url=None,
        latitude=None,
        longitude=None,
        identity_trust="confirmed",
    )
    cross_pack = prepare_narrative_pack(jan_plan, evidence=cross_hits, photos=[cross_photo])
    harbor_eps = [
        e
        for e in (cross_pack.get("episodes") or [])
        if "harbor" in str(e.get("content") or "").lower()
        or "harbor" in str(e.get("place") or "").lower()
    ]
    _check(
        "cross_source_same_event_one_episode",
        len(harbor_eps) == 1
        and int((harbor_eps[0] or {}).get("member_n") or 0) >= 3,
        checks,
        problems,
        detail=str(
            {
                "episode_n": len(cross_pack.get("episodes") or []),
                "harbor": [
                    {"n": e.get("member_n"), "content": (e.get("content") or "")[:120]}
                    for e in harbor_eps
                ],
            }
        ),
    )

    motive_text, motive_pack, _ = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=later_first
    )
    html_note = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    _check(
        "trust_no_invented_motive_save_story_not_truth",
        "felt heartbroken" not in motive_text.lower()
        and "because they wanted" not in motive_text.lower()
        and "does not turn the essay into family truth" in html_note.lower()
        and "not family truth until you save story" not in html_note.lower()
        and not (motive_pack.get("coverage") or {}).get("incomplete"),
        checks,
        problems,
        detail=motive_text[:240],
    )

    txn_hits = [
        EvidenceHit(
            evidence_id="e-ship-1",
            evidence_kind="communication",
            summary="Your package is out for delivery",
            score=1.0,
            excerpt="FedEx tracking shipment notice. Your order is out for delivery.",
            source="email_mbox",
            sent_at="2025-01-06T09:00:00",
            channel="email",
            thread_id="t-ship-1",
        ),
        EvidenceHit(
            evidence_id="e-survey-1",
            evidence_kind="communication",
            summary="Survey invitation",
            score=1.0,
            excerpt="Tell us how we did. This is an automated survey invitation.",
            source="email_mbox",
            sent_at="2025-01-07T09:00:00",
            channel="email",
            thread_id="t-survey-1",
        ),
        EvidenceHit(
            evidence_id="e-life-1",
            evidence_kind="communication",
            summary="Sunday dinner at the harbor",
            score=1.0,
            excerpt="come to Sunday dinner at the harbor",
            source="sms_export",
            sent_at="2025-01-12T18:00:00",
            channel="sms",
            people=["Alex"],
            thread_id="t-dinner-1",
        ),
    ]
    txn_text, txn_pack, _ = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=txn_hits
    )
    txn_l = txn_text.lower()
    sig_n = int((txn_pack.get("volume") or {}).get("significant_episode_n") or 0)
    _check(
        "narrative_is_life_not_evidence_volume",
        int((txn_pack.get("evidence_considered") or {}).get("emails") or 0) == 2
        and int((txn_pack.get("evidence_considered") or {}).get("sms") or 0) == 1
        and sig_n >= 1
        and "harbor" in txn_l
        and "evidence item" not in txn_l
        and "2025-w01:" not in txn_l
        and "fedex" not in txn_l
        and "survey invitation" not in txn_l
        and "out for delivery" not in txn_l,
        checks,
        problems,
        detail=str(
            {
                "volume": txn_pack.get("volume"),
                "sig": [e.get("title") for e in (txn_pack.get("significant_episodes") or [])],
                "prose": txn_text[:280],
            }
        ),
    )
    nar = pack_for_narrator(txn_pack)
    nar_blob = json.dumps(nar, default=str)
    nar_eps = [e for e in (nar.get("episodes") or []) if isinstance(e, dict)]
    _check(
        "narrator_input_is_semantic_life_outline",
        "evidence_considered" not in nar
        and "derived_summaries" not in nar
        and "volume" not in nar
        and "2025-W" not in nar_blob
        and "evidence item" not in nar_blob.lower()
        and isinstance(nar.get("background"), dict)
        and isinstance(nar.get("uncertainty"), dict)
        and bool(nar_eps)
        and all(
            e.get("claims")
            and e.get("evidence_ids")
            and isinstance(e.get("date_span"), dict)
            and e.get("significance")
            for e in nar_eps
        )
        and "harbor" in nar_blob.lower()
        and "fedex" not in nar_blob.lower(),
        checks,
        problems,
        detail=str({"keys": sorted(nar.keys()), "episodes": nar_eps[:3], "blob": nar_blob[:400]}),
    )
    prompt_l = SYSTEM_PROMPT.lower()
    _check(
        "c26_narrator_payload_does_not_instruct_system_truth",
        "incomplete_coverage" not in prompt_l
        and "say coverage is incomplete" not in prompt_l
        and "family evidence considered" not in prompt_l
        and "eligible items" not in prompt_l
        and "incomplete_coverage" not in nar
        and "incomplete_coverage" not in nar_blob
        and "evidence_considered" not in nar
        and "truncation_disclosure" not in nar_blob
        and "coverage is incomplete" not in nar_blob.lower()
        and "family evidence considered" not in nar_blob.lower()
        and "eligible_n" not in nar_blob
        and isinstance(nar.get("uncertainty"), dict)
        and         "incomplete_coverage" not in (nar.get("uncertainty") or {}),
        checks,
        problems,
        detail=str({"prompt_snip": SYSTEM_PROMPT[:220], "unc": nar.get("uncertainty"), "keys": sorted(nar.keys())}),
    )
    _check(
        "c26_missing_photos_line_is_python_not_narrator",
        "no photos were found" not in nar_blob.lower()
        and "requestor_library" not in nar_blob
        and "missing_modality" not in SYSTEM_PROMPT.lower(),
        checks,
        problems,
        detail=str({"keys": sorted(nar.keys())}),
    )

    trunc_hits = [
        EvidenceHit(
            evidence_id="e-trunc-1",
            evidence_kind="communication",
            summary="Sunday dinner at the harbor",
            score=1.0,
            excerpt="come to Sunday dinner at the harbor",
            source="sms_export",
            sent_at="2025-01-12T18:00:00",
            channel="sms",
            people=["Alex"],
            thread_id="t-dinner-trunc",
            truncated=True,
            count_scope="retrieve truncated",
        ),
    ]
    inc_text, inc_pack, _ = tell_from_hits(
        jan_plan, llm=FakeLlmProvider(), evidence=trunc_hits
    )
    inc_nar = pack_for_narrator(inc_pack)
    inc_nar_blob = json.dumps(inc_nar, default=str)
    fake_only = FakeLlmProvider().chat(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=inc_nar_blob),
        ]
    )
    fake_body = str(getattr(fake_only, "content", "") or "")
    py_cov = coverage_incomplete_line(inc_pack)
    _check(
        "c26_python_renders_coverage_and_evidence_footer",
        bool((inc_pack.get("coverage") or {}).get("incomplete"))
        and bool(py_cov)
        and "coverage is incomplete" in py_cov.lower()
        and "coverage is incomplete" in inc_text.lower()
        and "family evidence considered" in inc_text.lower()
        and "incomplete_coverage" not in inc_nar
        and "incomplete_coverage" not in inc_nar_blob
        and "coverage is incomplete" not in fake_body.lower()
        and "family evidence considered" not in fake_body.lower(),
        checks,
        problems,
        detail=str(
            {
                "py_cov": py_cov,
                "prose_tail": inc_text[-280:],
                "fake": fake_body[:280],
                "unc": inc_nar.get("uncertainty"),
            }
        ),
    )

    mixed_life = [
        EvidenceHit(
            evidence_id="e-msft",
            evidence_kind="communication",
            summary="Your Microsoft order #4949347936 has been processed",
            score=1.0,
            excerpt=(
                "Your Microsoft order #4949347936 has been processed. "
                "Knee surgery was scheduled for 1/15. Recovery and PT start after."
            ),
            source="email_mbox",
            sent_at="2025-01-08T09:00:00",
            channel="email",
            thread_id="t-msft",
        ),
        EvidenceHit(
            evidence_id="e-nike",
            evidence_kind="communication",
            summary="Nike Boys Kawa Slide refund",
            score=1.0,
            excerpt="Your refund for Nike Boys Kawa Slide is being processed.",
            source="email_mbox",
            sent_at="2025-01-09T10:00:00",
            channel="email",
            thread_id="t-nike",
        ),
        EvidenceHit(
            evidence_id="e-wifi",
            evidence_kind="communication",
            summary="Wi-Fi outage follow-up",
            score=1.0,
            excerpt="The home Wi-Fi router is still dropping. Internet service ticket 88.",
            source="email_mbox",
            sent_at="2025-01-09T11:00:00",
            channel="email",
            thread_id="t-wifi",
        ),
        EvidenceHit(
            evidence_id="e-drewes",
            evidence_kind="communication",
            summary="Ted Drewes this week only",
            score=1.0,
            excerpt="Use code CUSTARD for 20% off. Unsubscribe. Limited time shop now.",
            source="email_mbox",
            sent_at="2025-01-10T12:00:00",
            channel="email",
            thread_id="t-drewes",
        ),
        EvidenceHit(
            evidence_id="e-1099",
            evidence_kind="communication",
            summary="Your 1099-R is ready",
            score=1.0,
            excerpt="Your 1099-R tax document is available. Form W-2 also posted.",
            source="email_mbox",
            sent_at="2025-01-11T12:00:00",
            channel="email",
            thread_id="t-1099",
        ),
        EvidenceHit(
            evidence_id="e-1098",
            evidence_kind="communication",
            summary="1098 mortgage interest",
            score=1.0,
            excerpt="Your 1098 tax document is ready at irs.gov related portal.",
            source="email_mbox",
            sent_at="2025-01-11T13:00:00",
            channel="email",
            thread_id="t-1098",
        ),
        EvidenceHit(
            evidence_id="e-lll",
            evidence_kind="communication",
            summary="lll",
            score=1.0,
            excerpt="lll",
            source="email_mbox",
            sent_at="2025-01-12T08:00:00",
            channel="email",
            thread_id="t-lll",
        ),
        EvidenceHit(
            evidence_id="e-sponsors",
            evidence_kind="communication",
            summary="Re: Sponsors",
            score=1.0,
            excerpt="Trivia Night planning and fundraising. Need sponsors for the event.",
            source="email_mbox",
            sent_at="2025-01-14T09:00:00",
            channel="email",
            thread_id="t-sponsors",
        ),
        EvidenceHit(
            evidence_id="e-reflect",
            evidence_kind="communication",
            summary="Latest info",
            score=1.0,
            excerpt="Day of Reflection on Saturday. Music planning for the liturgy.",
            source="email_mbox",
            sent_at="2025-01-16T09:00:00",
            channel="email",
            thread_id="t-reflect",
        ),
    ]
    life_pack = prepare_narrative_pack(jan_plan, evidence=mixed_life)
    dump = public_episode_dump(life_pack)
    sel_titles = " | ".join(str(x.get("title") or "").lower() for x in dump.get("selected") or [])
    rej_titles = " | ".join(str(t or "").lower() for t in dump.get("rejected_titles") or [])
    nike_wifi_split = True
    families = [str(e.get("primary_family") or "") for e in (life_pack.get("episodes") or [])]
    _check(
        "episodes_are_grounded_life_events",
        "knee surgery" in sel_titles
        and "microsoft order" not in sel_titles
        and "trivia night" in sel_titles
        and "day of reflection" in sel_titles
        and "wi-fi" in sel_titles
        and "kawa slide" not in sel_titles
        and "ted drewes" in rej_titles
        and "1099" in rej_titles
        and "1098" in rej_titles
        and (any(str(t).lower() == "lll" or "untitled" in str(t).lower() for t in dump.get("rejected_titles") or []))
        and "commerce" in families
        and "household_project" in families
        and nike_wifi_split,
        checks,
        problems,
        detail=json.dumps(dump, default=str)[:1200],
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
        or "Family evidence considered" in (told.answer_text or "")
        or "Family evidence used" in (told.answer_text or ""),
        checks,
        problems,
        detail=(told.answer_text or "")[:240],
    )

    if flightsim:
        print(
            "prove-i11 --flightsim: POST live /explore/api/find "
            "(needs Ask/serve; live January tell can take several minutes)...",
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
        live_timeout = 900
        raw_to = (os.environ.get("MEMORYBOX_I11_LIVE_TIMEOUT") or "").strip()
        if raw_to.isdigit() and int(raw_to) >= 30:
            live_timeout = int(raw_to)
        with urllib.request.urlopen(req, timeout=live_timeout) as resp:
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
        and int(used.get("travel") or 0) >= 0
        and authored >= 1
        and "year-fair" not in prose.lower()
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
