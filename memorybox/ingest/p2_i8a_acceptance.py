"""P2-I8A Unified Communications Gallery & Timeline Precision — structural + logic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.mbql.verbs import VERB_IDS


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = _root()
    find_py = (root / "explore" / "find.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    retrieve = (root / "ask" / "retrieve.py").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    verbs = (root / "mbql" / "verbs.py").read_text(encoding="utf-8")
    compile_py = (root / "mbql" / "compile.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")
    planner = (root / "planner" / "__init__.py").read_text(encoding="utf-8")

    _check(
        "i8a_q3_hidden_defaults",
        "explicit_email_gallery" in find_py
        and "explicit_calendar_gallery" in find_py
        and "gallery_show_email" in find_py
        and "gallery_show_calendar" in find_py
        and "_attach_calendar" in find_py,
        checks,
        problems,
        "Q3: email/SMS/calendar presentation flags",
    )
    _check(
        "i8a_filters_mbql",
        "add_communications" in verbs
        and "add_calendar" in verbs
        and "attachments_only" in verbs
        and "show_memory" in verbs
        and "gallery_show_email" in compile_py
        and all(v in explore_js for v in VERB_IDS),
        checks,
        problems,
        "Communications/Calendar/Memory/Attachments MBQL verbs synced",
    )
    _check(
        "i8a_drilldown_screens",
        "openDayStack" in explore_js
        and "DAY_PREVIEW_DELAY_MS" in explore_js
        and "threadCards" in explore_js
        and "yearFairTake" in explore_js
        and "presentWithoutRewritingAsk" in explore_js
        and "mb-day-prev" in explore_html
        and "mb-day-stack" in explore_html
        and "mb-comms-filter" in explore_html
        and "mb-cal-filter" in explore_html
        and "Communications filter" in explore_html,
        checks,
        problems,
        "Day stack + Communications/Calendar filter chrome",
    )
    _check(
        "i8a_no_mail_send",
        "Reply all" not in explore_js
        and "Reply All" not in explore_js
        and "Forward" not in explore_html.split("mb-day-stack")[-1],
        checks,
        problems,
        "No Reply/Forward implementation chrome",
    )
    _check(
        "i8a_person_lock",
        "p2_bl_i8_02" in orch
        and "allow_first_token" in retrieve
        and "resolved_person_ids_for_comms" in orch,
        checks,
        problems,
        "P2-BL-I8-02 unique Person before email/SMS retrieve",
    )
    _check(
        "i8a_calendar_retrieve",
        "search_calendar_events" in retrieve
        and "want_calendar_modality" in planner
        and 'type_ = "calendar"' in find_py
        and "inspect_calendar_state" in (root / "ingest" / "comms_calendar.py").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        "calendar_event retrieve + Explore type + inspect",
    )
    _check(
        "i8a_cli",
        "prove-p2-i8a" in main and "inspect-calendar" in main,
        checks,
        problems,
        "prove-p2-i8a + inspect-calendar CLI",
    )
    _check(
        "i8a_no_draft_badge",
        "NOT YET FOR CURSOR" not in explore_html
        and "NOT YET FOR CURSOR" not in explore_js,
        checks,
        problems,
        "Do not ship stale DRAFT badges",
    )
    close_fn = explore_js.split("function closeDayStack(")[1].split("function renderDayStack(")[0]
    matches_fn = explore_js.split("function matchesType(")[1].split("function resultSetItems(")[0]
    _check(
        "i8a_close_day_keeps_gallery",
        "restoreExplore" not in close_fn,
        checks,
        problems,
        "Close day stack must not restoreExplore (wipes live find)",
    )
    _check(
        "i8a_comms_filter_respects_text",
        "if (!includeTexts) return false;" in matches_fn
        and "applyPresentFlags" in explore_js
        and "mb-day-row-date" in explore_js
        and "explore.js?v=i8a4" in explore_html,
        checks,
        problems,
        "Communications filter + list dates + cache bust",
    )


def _logic(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.context import AskContext
    from memorybox.explore.find import (
        explicit_calendar_gallery,
        explicit_email_gallery,
        explicit_text_gallery,
        items_from_ask_result,
    )
    from memorybox.mbql import compile_ask
    from memorybox.planner import plan_ask

    ctx = AskContext(session_id="prove-i8a")
    broad = items_from_ask_result(
        {
            "evidence_hits": [
                {
                    "evidence_id": "00000000-0000-0000-0000-000000000001",
                    "evidence_kind": "communication",
                    "summary": "mail",
                    "channel": "email",
                    "sent_at": "2001-12-23T10:00:00",
                    "people": ["Peggy George"],
                },
                {
                    "evidence_id": "00000000-0000-0000-0000-000000000002",
                    "evidence_kind": "communication",
                    "summary": "sms",
                    "source": "sms_export",
                    "channel": "sms",
                    "sent_at": "2001-12-23T11:00:00",
                    "people": ["Peggy George"],
                },
                {
                    "evidence_id": "00000000-0000-0000-0000-000000000003",
                    "evidence_kind": "calendar_event",
                    "summary": "Dinner",
                    "channel": "calendar",
                    "sent_at": "2001-12-23T18:00:00",
                    "people": ["Peggy George"],
                },
            ],
            "plan": {"notes": (), "original_ask": "Show me Peggy"},
        }
    )
    _check(
        "i8a_broad_all_hidden",
        all(i.get("gallery_default_hidden") for i in broad)
        and {i["type"] for i in broad} >= {"email", "sms", "calendar"}
        and not explicit_text_gallery({"plan": {"notes": ()}}, "Show me Peggy")
        and not explicit_email_gallery({"plan": {"notes": ()}}, "Show me Peggy")
        and not explicit_calendar_gallery({"plan": {"notes": ()}}, "Show me Peggy"),
        checks,
        problems,
        f"types={[i.get('type') for i in broad]} hidden={[i.get('gallery_default_hidden') for i in broad]}",
    )
    sms_ask = items_from_ask_result(
        {
            "evidence_hits": [
                {
                    "evidence_id": "00000000-0000-0000-0000-000000000002",
                    "evidence_kind": "communication",
                    "summary": "sms",
                    "source": "sms_export",
                    "channel": "sms",
                    "sent_at": "2001-12-23T11:00:00",
                    "people": ["Peggy"],
                }
            ],
            "plan": {
                "notes": ("want_sms_modality",),
                "original_ask": "Show me all my text messages with Peggy",
            },
        }
    )
    _check(
        "i8a_explicit_sms_visible",
        sms_ask and sms_ask[0].get("type") == "sms" and not sms_ask[0].get("gallery_default_hidden"),
        checks,
        problems,
        str(sms_ask[:1]),
    )
    p_add = compile_ask("Add communications.", ctx, allow_model=False)
    p_cal = compile_ask("Add calendar.", ctx, allow_model=False)
    p_mem = compile_ask("Memory.", ctx, allow_model=False)
    _check(
        "i8a_mbql_presentation",
        p_add.gallery_show_sms is True
        and p_add.gallery_show_email is True
        and p_cal.gallery_show_calendar is True
        and p_mem.memory_presentation is True,
        checks,
        problems,
        f"add={p_add.refine_verb} cal={p_cal.gallery_show_calendar} mem={p_mem.memory_presentation}",
    )
    plan_mail = plan_ask("how many times did I send an email to Peggy George?", ctx)
    _check(
        "i8a_email_count_plans_comms",
        plan_mail.want_communication and any("peggy" in n.lower() for n in plan_mail.person_names),
        checks,
        problems,
        f"people={plan_mail.person_names} comm={plan_mail.want_communication}",
    )


def _inspect(checks: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    from memorybox.ingest.comms_calendar import inspect_calendar_state

    inspect = inspect_calendar_state()
    n = inspect.get("calendar_event")
    staged = inspect.get("staged_ics_files")
    _check(
        "i8a_calendar_inspect",
        bool(inspect.get("ok")),
        checks,
        problems,
        (
            f"calendar_event={n} staged_ics={staged} "
            f"archive_health.calendar={n} "
            f"coverage={inspect.get('coverage')} "
            f"needs_ingest={inspect.get('needs_ingest')} "
            f"ingest_recommended={inspect.get('ingest_recommended')}"
        ),
    )
    return inspect


def run_p2_i8a_acceptance(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    _structural(checks, problems)
    try:
        _logic(checks, problems)
    except Exception as exc:  # noqa: BLE001
        _check(
            "i8a_logic_suite",
            False,
            checks,
            problems,
            f"{type(exc).__name__}: {exc}",
        )
    try:
        inspect = _inspect(checks, problems)
    except Exception as exc:  # noqa: BLE001
        inspect = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        _check(
            "i8a_calendar_inspect",
            False,
            checks,
            problems,
            str(inspect.get("error")),
        )
    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "ok": overall,
        "checks": checks,
        "problems": problems,
        "inspect": inspect,
        "meta": {
            "increment": "P2-I8A",
            "mode": "flightsim" if flightsim else "harness",
            "build_authorized": True,
            "note": (
                "i8a_calendar_inspect + inspect.* are live FlightSim/PG facts. "
                "Other checks stay structural+logic. §11 ACCEPTED is still a manual owner pass."
            ),
        },
    }
