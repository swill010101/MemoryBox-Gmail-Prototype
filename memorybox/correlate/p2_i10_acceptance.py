"""P2-I10 Cross-Source Correlation acceptance."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.mbql.compile import compile_ask


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def prove_p2_i10(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I10", "flightsim": bool(flightsim)}
    _structural(checks, problems)
    _compile(checks, problems)
    db_ok = _db_logic(checks, problems, meta)
    meta["db_logic"] = db_ok
    if flightsim:
        src = (_root().parent / "docs" / "source" / "MBBS-P2_INCREMENT_10_DEFINITION.md").read_text(
            encoding="utf-8"
        )
        _check(
            "p2i10_definition_authorized",
            "BUILD AUTHORIZED" in src
            and "I10 is approved to build" in src
            and "I11" in src,
            checks,
            problems,
            "definition must stay authorized and keep I11 out",
        )
    return {
        "ok": not problems,
        "overall_ok": not problems,
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = _root()
    planner = (root / "planner" / "__init__.py").read_text(encoding="utf-8")
    retrieve = (root / "ask" / "retrieve.py").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    find_py = (root / "explore" / "find.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    app = (root / "app.py").read_text(encoding="utf-8")
    mig = (root / "migrations" / "014_p2_i10_correlate.sql").read_text(encoding="utf-8")
    store = (root / "correlate" / "store.py").read_text(encoding="utf-8")
    _check(
        "p2i10_schema_links_places_events",
        "CREATE TABLE IF NOT EXISTS places" in mig
        and "CREATE TABLE IF NOT EXISTS correlatable_events" in mig
        and "CREATE TABLE IF NOT EXISTS correlation_links" in mig
        and "rejected" in mig,
        checks,
        problems,
        "014 migration must define places, events, links with rejected status",
    )
    _check(
        "p2i10_reject_does_not_delete",
        "rejected" in store and "DELETE FROM correlation_links" not in store,
        checks,
        problems,
        "reject must update status, not delete the row",
    )
    _check(
        "p2i10_compile_everything_about",
        "EVERYTHING_ABOUT_RE" in planner and "want_cross_source" in planner,
        checks,
        problems,
        "planner must compile everything-about as cross-source",
    )
    _check(
        "p2i10_spoken_does_not_narrow_cross_source",
        "want_cross_source" in planner and "want_spoken and not" in planner,
        checks,
        problems,
        "I9 spoken-narrowing must skip when want_cross_source",
    )
    _check(
        "p2i10_retrieve_cross_source_flag",
        "want_cross_source" in retrieve,
        checks,
        problems,
        "SMS/email retrieve must honor want_cross_source",
    )
    _check(
        "p2i10_pack_in_orchestrator",
        "apply_cross_source" in orch and "coverage" in orch,
        checks,
        problems,
        "Ask must attach coverage pack, not a saved Story",
    )
    _check(
        "p2i10_explore_coverage_strip",
        "coverage" in find_py
        and "mb-explore-coverage" in explore_html
        and "coverage" in explore_js,
        checks,
        problems,
        "Explore curator coverage strip",
    )
    _check(
        "p2i10_confirm_reject_api",
        "/correlate/link" in app and "reject_link" in app,
        checks,
        problems,
        "confirm/reject HTTP API",
    )
    _check(
        "p2i10_unlink_api",
        "/correlate/unlink" in app
        and "unlink_subject" in app
        and "/correlate/event/{event_id}" in app
        and "Not this event" in explore_js
        and "/correlate/unlink" in explore_js
        and "unlink_subject" in store,
        checks,
        problems,
        "owner unlink API + Learn rail Not this event",
    )
    _check(
        "p2i10_place_photo_filter",
        "filter_photo_hits_to_places" in retrieve
        and "place_match" in find_py
        and "placeMatch" in explore_js
        and "need_location" in retrieve,
        checks,
        problems,
        "person+place must filter photos (aliases/GPS), not dump the person library",
    )
    _check(
        "p2i10_find_comms_only_on_cross_source",
        'plan_early.get("want_cross_source")' in find_py
        and "clarifying" in find_py,
        checks,
        problems,
        "Explore must not force SMS/email/calendar on ordinary Show-me or year-clarify",
    )
    _check(
        "p2i10_birthday_not_a_person_token",
        '"birthdays"' in planner and "life_event_all_years" in (root / "planner" / "temporal.py").read_text(encoding="utf-8"),
        checks,
        problems,
        "birthdays must not compile as a Person; no-year birthday is all observances",
    )
    _check(
        "p2i10_bare_year_followup_marker",
        "year_only_followup_visual" in planner and "life_event_year_followup" in planner,
        checks,
        problems,
        "bare 2017 must inherit person + birthday (voice path)",
    )
    _check(
        "p2i10_authorized_quote",
        "I10 is approved to build"
        in (root.parent / "docs" / "source" / "MBBS-P2_INCREMENT_10_DEFINITION.md").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        "definition must stamp Tom's I10 build authorization",
    )
    _check(
        "p2i10_not_i11_narrative_save",
        "durable Story" not in orch or "not a saved Story" in (root / "correlate" / "pack.py").read_text(
            encoding="utf-8"
        )
        or "Everything about" in (root / "correlate" / "pack.py").read_text(encoding="utf-8"),
        checks,
        problems,
        "pack summary is coverage, not narrative save",
    )


def _compile(checks: dict[str, Any], problems: list[str]) -> None:
    plan = compile_ask("Show me everything I have about Grandpa's military service")
    notes = " ".join(plan.notes or ())
    theme = " ".join(getattr(plan, "theme_labels", ()) or ()).lower()
    _check(
        "p2i10_compile_cross_source_on",
        bool(getattr(plan, "want_cross_source", False)),
        checks,
        problems,
        f"want_cross_source notes={plan.notes}",
    )
    _check(
        "p2i10_compile_theme_military",
        "military" in theme,
        checks,
        problems,
        f"theme={getattr(plan, 'theme_labels', ())}",
    )
    _check(
        "p2i10_compile_not_video_only",
        plan.visual_scope != "video_only"
        and bool(plan.want_still)
        and bool(plan.want_communication)
        and bool(plan.want_calendar),
        checks,
        problems,
        f"scope={plan.visual_scope} still={plan.want_still} comm={plan.want_communication} cal={plan.want_calendar} spoken={plan.want_spoken}",
    )
    _check(
        "p2i10_compile_presentation_on",
        plan.gallery_show_email is True
        and plan.gallery_show_sms is True
        and plan.gallery_show_calendar is True,
        checks,
        problems,
        f"email={plan.gallery_show_email} sms={plan.gallery_show_sms} cal={plan.gallery_show_calendar}",
    )
    talking = compile_ask("Peggy talking about Christmas")
    _check(
        "p2i10_i9_talking_not_cross_source",
        bool(getattr(talking, "want_spoken", False))
        and not bool(getattr(talking, "want_cross_source", False)),
        checks,
        problems,
        f"talking cross={getattr(talking, 'want_cross_source', None)} spoken={talking.want_spoken}",
    )
    show = compile_ask("Show me Peggy")
    _check(
        "p2i10_ordinary_show_me_not_everything",
        not bool(getattr(show, "want_cross_source", False)),
        checks,
        problems,
        f"show_me notes={show.notes}",
    )
    in_fl = compile_ask("show me peggy george in florida")
    _check(
        "p2i10_in_florida_lowercase_is_place",
        "Peggy" in " ".join(in_fl.person_names)
        and any(p.lower() == "florida" for p in (in_fl.place_names or ())),
        checks,
        problems,
        f"people={in_fl.person_names} places={in_fl.place_names}",
    )
    and_fl = compile_ask("show me Peggy George and florida")
    _check(
        "p2i10_and_florida_is_place_not_person",
        any("Peggy" in n for n in (and_fl.person_names or ()))
        and not any(n.lower() == "florida" for n in (and_fl.person_names or ()))
        and any(p.lower() == "florida" for p in (and_fl.place_names or ())),
        checks,
        problems,
        f"people={and_fl.person_names} places={and_fl.place_names}",
    )
    from memorybox.context import AskContext
    from memorybox.planner import plan_ask as _plan_ask

    sticky_eugene = AskContext(session_id="p2-i10-eugene", person_names=("Eugene Will",))
    tom_and_fl = _plan_ask("tom will and florida", sticky_eugene)
    _check(
        "p2i10_tom_and_florida_does_not_keep_eugene",
        any("Tom" in n for n in (tom_and_fl.person_names or ()))
        and "Eugene Will" not in (tom_and_fl.person_names or ())
        and any(p.lower() == "florida" for p in (tom_and_fl.place_names or ())),
        checks,
        problems,
        f"people={tom_and_fl.person_names} places={tom_and_fl.place_names} notes={tom_and_fl.notes}",
    )
    tell_tom = _plan_ask("tell me about tom will and florida", sticky_eugene)
    _check(
        "p2i10_tell_tom_does_not_keep_eugene",
        any("Tom" in n for n in (tell_tom.person_names or ()))
        and "Eugene Will" not in (tell_tom.person_names or ()),
        checks,
        problems,
        f"people={tell_tom.person_names} places={tell_tom.place_names} notes={tell_tom.notes}",
    )
    two_people = compile_ask("show me tom will and peggy")
    _check(
        "p2i10_person_and_person_still_two_people",
        any("Tom" in n for n in (two_people.person_names or ()))
        and any("Peggy" in n for n in (two_people.person_names or ()))
        and not two_people.place_names,
        checks,
        problems,
        f"people={two_people.person_names} places={two_people.place_names}",
    )
    bday_all = compile_ask("show me everything about peggy george and birthdays")
    bday_theme = " ".join(getattr(bday_all, "theme_labels", ()) or ()).lower()
    _check(
        "p2i10_everything_about_birthdays_not_person",
        any("Peggy" in n for n in (bday_all.person_names or ()))
        and not any(n.lower() in {"birthday", "birthdays"} for n in (bday_all.person_names or ()))
        and bday_all.life_event_kind == "birthday"
        and "Birthday" in (bday_all.event_labels or ())
        and bool(getattr(bday_all, "want_cross_source", False))
        and bool(bday_all.want_still)
        and bool(bday_all.want_communication)
        and not bday_all.requires_clarification
        and "and" not in bday_theme.split(),
        checks,
        problems,
        f"people={bday_all.person_names} events={bday_all.event_labels} "
        f"theme={getattr(bday_all, 'theme_labels', ())} still={bday_all.want_still} "
        f"cross={getattr(bday_all, 'want_cross_source', None)} "
        f"clarify={bday_all.requires_clarification} msg={bday_all.ambiguity_message} "
        f"notes={bday_all.notes}",
    )
    bday_ctx = AskContext(
        session_id="p2-i10-bday-year",
        person_names=bday_all.person_names,
        event_labels=bday_all.event_labels,
        last_ask=bday_all.original_ask,
        modalities_active=bday_all.modalities,
    )
    year_only = _plan_ask("2017", bday_ctx)
    _check(
        "p2i10_bare_2017_keeps_person_birthday_visual",
        any("Peggy" in n for n in (year_only.person_names or ()))
        and year_only.life_event_kind == "birthday"
        and year_only.life_event_years == (2017,)
        and bool(year_only.want_still)
        and year_only.visual_scope == "broad"
        and bool(getattr(year_only, "want_cross_source", False))
        and not year_only.requires_clarification
        and not any(n.lower() in {"birthday", "birthdays"} for n in (year_only.person_names or ())),
        checks,
        problems,
        f"people={year_only.person_names} kind={year_only.life_event_kind} "
        f"years={year_only.life_event_years} still={year_only.want_still} "
        f"scope={year_only.visual_scope} cross={getattr(year_only, 'want_cross_source', None)} "
        f"comm={year_only.want_communication} notes={year_only.notes}",
    )
    year_dot = _plan_ask("2017.", bday_ctx)
    _check(
        "p2i10_bare_2017_period_same",
        year_dot.life_event_kind == "birthday"
        and year_dot.life_event_years == (2017,)
        and bool(year_dot.want_still),
        checks,
        problems,
        f"kind={year_dot.life_event_kind} years={year_dot.life_event_years} notes={year_dot.notes}",
    )
    _check(
        "p2i10_compile_note",
        "p2_i10_cross_source" in notes,
        checks,
        problems,
        notes,
    )
    from memorybox.ask.place_match import (
        filter_photo_hits_to_places,
        location_matches_place,
        place_match_spec,
    )
    from memorybox.ask.retrieve import PhotoHit

    def _hit(**kwargs: Any) -> PhotoHit:
        return PhotoHit(
            provider_key="fake_photo",
            external_id=str(kwargs.pop("external_id", "ph-1")),
            taken_at=kwargs.pop("taken_at", "2018-03-01"),
            people=["Peggy George"],
            location=kwargs.pop("location", None),
            thumb_url=None,
            web_url=None,
            **kwargs,
        )

    miami = _hit(external_id="miami", city="Miami", state=None)
    fl_abbr = _hit(external_id="fl", city="Naples", state="FL")
    gps_fl = _hit(external_id="gps", latitude=26.14, longitude=-81.79)
    castle = _hit(
        external_id="nj",
        city="Hoboken",
        state="New Jersey",
        latitude=40.74,
        longitude=-74.03,
    )
    unnamed = _hit(external_id="none")
    file_fl = _hit(external_id="fn", original_filename="Florida_2016_beach.JPG")
    kept = filter_photo_hits_to_places(
        [miami, fl_abbr, gps_fl, castle, unnamed, file_fl],
        ("Florida",),
    )
    kept_ids = {h.external_id for h in kept}
    _check(
        "p2i10_place_keeps_city_abbrev_gps_filename",
        kept_ids == {"miami", "fl", "gps", "fn"},
        checks,
        problems,
        f"kept={kept_ids}",
    )
    _check(
        "p2i10_place_drops_unlocated_and_other_state",
        not location_matches_place("Florida")
        and not location_matches_place(
            "Florida", city="Hoboken", state="New Jersey", latitude=40.74, longitude=-74.03
        ),
        checks,
        problems,
        "unlocated and New Jersey must not count as Florida",
    )
    spec = place_match_spec(("Florida",))
    needles = list((spec or {}).get("needles") or [])
    bbox = (spec or {}).get("bbox")
    _check(
        "p2i10_place_match_spec_for_explore",
        spec is not None
        and "miami" in needles
        and isinstance(bbox, list)
        and len(bbox) == 4,
        checks,
        problems,
        str(spec),
    )


def _db_logic(checks: dict[str, Any], problems: list[str], meta: dict[str, Any]) -> bool:
    try:
        from memorybox.db import ping

        ping()
    except Exception as exc:  # noqa: BLE001
        _check(
            "p2i10_db_optional_skipped",
            True,
            checks,
            problems,
            f"no postgres: {exc}",
        )
        return False

    from memorybox.correlate.fixture import seed_i10_military_fixture
    from memorybox.correlate.pack import apply_cross_source
    from memorybox.correlate.store import date_conflicts, get_event, list_links, unlink_subject, upsert_link
    from memorybox.migrate import migrate
    from memorybox.planner import QueryPlan

    migrate()
    seeded = seed_i10_military_fixture()
    meta["fixture"] = {k: seeded[k] for k in ("person_id", "event_id", "noise_link_id") if k in seeded}
    event_id = seeded["event_id"]
    conflicts = date_conflicts(event_id)
    _check(
        "p2i10_date_conflict_disclosed",
        len(conflicts) >= 2,
        checks,
        problems,
        f"conflicts={conflicts}",
    )
    restored = upsert_link(
        subject_type="evidence",
        subject_id=seeded["noise_id"],
        object_type="event",
        object_id=event_id,
        predicate="about",
        evidence_id=seeded["noise_id"],
        authority="system",
        status="candidate",
        provenance={"retry": True},
    )
    _check(
        "p2i10_reject_sticks",
        restored.get("status") == "rejected" and restored.get("restored") is False,
        checks,
        problems,
        str(restored),
    )
    rejected_rows = list_links(
        object_type="event",
        object_id=event_id,
        statuses=("rejected",),
    )
    _check(
        "p2i10_rejected_row_preserved",
        any(r["id"] == seeded["noise_link_id"] for r in rejected_rows),
        checks,
        problems,
        f"rejected={rejected_rows}",
    )

    class _E:
        def __init__(self, eid: str, channel: str, summary: str, sent_at: str | None = None):
            self.evidence_id = eid
            self.channel = channel
            self.evidence_kind = "communication"
            self.summary = summary
            self.excerpt = summary
            self.sent_at = sent_at

    evidence = [
        _E(seeded["email_id"], "email", "army Fort Lewis", "1968-03-12"),
        _E(seeded["letter_1968"], "email", "discharge 1968", "1968-06-01"),
        _E(seeded["letter_1969"], "email", "discharge 1969", "1969-06-01"),
        _E(seeded["noise_id"], "email", "walnut rolls", "2012-12-01"),
    ]
    plan = QueryPlan(
        original_ask="Show me everything I have about Grandpa's military service",
        effective_ask="everything-about",
        is_followup=False,
        want_photo=True,
        want_communication=True,
        want_calendar=True,
        want_cross_source=True,
        theme_labels=("military service",),
        person_names=("Eugene Will",),
    )
    artifacts = [{"artifact_id": seeded["artifact_id"], "label": "Eugene army letter", "kind": "letter"}]
    pack, filtered = apply_cross_source(
        plan,
        evidence=evidence,
        photos=[],
        videos=[],
        stories=[],
        journals=[],
        artifacts=artifacts,
        event_id=event_id,
    )
    kept_ids = {getattr(h, "evidence_id", None) for h in filtered["evidence"]}
    _check(
        "p2i10_pack_drops_rejected_keeps_military",
        seeded["noise_id"] not in kept_ids
        and seeded["email_id"] in kept_ids
        and seeded["letter_1968"] in kept_ids
        and pack.coverage.get("email", 0) >= 2
        and pack.coverage.get("artifact", 0) >= 1
        and "journal" in pack.missing
        and pack.dropped_rejected >= 1,
        checks,
        problems,
        f"kept={kept_ids} coverage={pack.coverage} missing={pack.missing} dropped={pack.dropped_rejected}",
    )
    _check(
        "p2i10_pack_not_a_story",
        "Everything about" in pack.summary and "Missing:" in pack.summary,
        checks,
        problems,
        pack.summary,
    )
    pack_h, filtered_h = apply_cross_source(
        plan,
        evidence=[],
        photos=[],
        videos=[],
        stories=[],
        journals=[],
        artifacts=[],
        event_id=event_id,
    )
    art_ids = {
        str(a.get("artifact_id") or a.get("id") or "")
        for a in filtered_h["artifacts"]
        if isinstance(a, dict)
    }
    hyd_ev = set()
    for h in filtered_h["evidence"]:
        if isinstance(h, dict):
            hyd_ev.add(str(h.get("evidence_id") or ""))
        else:
            hyd_ev.add(str(getattr(h, "evidence_id", "") or ""))
    _check(
        "p2i10_hydrate_confirmed_missed_by_retrieve",
        seeded["artifact_id"] in art_ids
        and seeded["letter_1968"] in hyd_ev
        and seeded["noise_id"] not in hyd_ev
        and pack_h.hydrated_confirmed >= 2
        and int(pack_h.coverage.get("artifact") or 0) >= 1
        and int(pack_h.coverage.get("email") or 0) >= 1,
        checks,
        problems,
        f"arts={art_ids} ev={hyd_ev} coverage={pack_h.coverage} hydrated={pack_h.hydrated_confirmed}",
    )
    ev_row = get_event(event_id)
    _check(
        "p2i10_get_event",
        bool(ev_row) and str(ev_row.get("id")) == str(event_id),
        checks,
        problems,
        str(ev_row),
    )

    live_ok = False
    live_detail = ""
    try:
        from memorybox.ask.orchestrator import AskOrchestrator
        from memorybox.providers.llm.fake import FakeLlmProvider
        from memorybox.providers.photo.fake import FakePhotoProvider
        from memorybox.providers.video.fake import FakeVideoProvider

        orch = AskOrchestrator(
            photo=FakePhotoProvider(),
            video=FakeVideoProvider(),
            llm=FakeLlmProvider(),
        )
        live = orch.ask(
            "Show me everything I have about Eugene Will's military service",
            session_id="p2-i10-prove-live",
        )
        live_plan = live.plan if isinstance(live.plan, dict) else {}
        live_cov = live.coverage if isinstance(live.coverage, dict) else {}
        live_ev = {
            str(h.get("evidence_id") or "")
            for h in (live.evidence_hits or [])
            if isinstance(h, dict)
        }
        live_art = {
            str(h.get("artifact_id") or h.get("id") or "")
            for h in (live.artifact_hits or [])
            if isinstance(h, dict)
        }
        mixed = (
            int(live_cov.get("email") or 0) >= 1 and int(live_cov.get("artifact") or 0) >= 1
        ) or (bool(live_ev) and bool(live_art))
        live_ok = (
            bool(live_plan.get("want_cross_source"))
            and mixed
            and seeded["noise_id"] not in live_ev
            and live.answer_kind not in {"story", "narrative"}
            and "Everything about" in str(live_cov.get("summary") or live.answer_text or "")
        )
        live_detail = (
            f"kind={live.answer_kind} cross={live_plan.get('want_cross_source')} "
            f"coverage={live_cov} ev={live_ev} art={live_art} answer={(live.answer_text or '')[:240]}"
        )
    except Exception as exc:  # noqa: BLE001
        live_detail = f"live ask failed: {exc}"
    _check(
        "p2i10_live_ask_mixed_pack_not_story",
        live_ok,
        checks,
        problems,
        live_detail,
    )

    unlinked = unlink_subject(
        subject_type="evidence",
        subject_id=seeded["email_id"],
        object_type="event",
        object_id=event_id,
    )
    _check(
        "p2i10_unlink_rejects",
        str(unlinked.get("status") or "") == "rejected",
        checks,
        problems,
        str(unlinked),
    )
    restored_unlinked = upsert_link(
        subject_type="evidence",
        subject_id=seeded["email_id"],
        object_type="event",
        object_id=event_id,
        predicate="about",
        evidence_id=seeded["email_id"],
        authority="system",
        status="candidate",
        provenance={"retry": "after-unlink"},
    )
    _check(
        "p2i10_unlink_sticks",
        restored_unlinked.get("status") == "rejected"
        and restored_unlinked.get("restored") is False,
        checks,
        problems,
        str(restored_unlinked),
    )
    return True
