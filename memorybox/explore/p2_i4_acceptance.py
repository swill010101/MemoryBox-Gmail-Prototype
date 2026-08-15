"""P2-I4 acceptance — Mixed-Media Find / Explore (MBUX-001 v0.4)."""
from __future__ import annotations

import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _fetch(url: str) -> tuple[int, str, dict[str, str]]:
    req = Request(url, headers={"Accept": "*/*", "User-Agent": "memorybox-prove-p2-i4"})
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), body, headers
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), body, {}
    except URLError as exc:
        return 0, str(exc), {}


def prove_p2_i4(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_flightsim()
    return _prove_harness()


def _assert_fixture(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not payload.get("ok"):
        problems.append("fixture not ok")
    items = payload.get("items") or []
    if len(items) < 12:
        problems.append(f"fixture items < 12 ({len(items)})")
    kinds = {str(i.get("type") or i.get("kind") or "").lower() for i in items}
    for need in ("photo", "video", "email", "artifact", "story"):
        if need not in kinds:
            problems.append(f"fixture missing type: {need}")
    undated = [
        i
        for i in items
        if i.get("undated") or not (i.get("date") or "").strip()
    ]
    if not undated:
        problems.append("fixture missing undated item")
    teachable = [i for i in items if i.get("teachable") or i.get("face_box")]
    if not teachable:
        problems.append("fixture missing teachable photo/video for I1 proof")
    if "Peggy" not in str(payload.get("title") or ""):
        problems.append("fixture title missing Peggy")
    if not (payload.get("summary") or payload.get("curator")):
        problems.append("fixture missing curator summary")
    chips = payload.get("chips") or []
    labels = {str(c.get("label") or "") for c in chips}
    for need in ("Peggy", "Christmas", "Oak Street"):
        if need not in labels:
            problems.append(f"fixture chip missing: {need}")
    geo = [
        i
        for i in items
        if i.get("lat") is not None and i.get("lng") is not None
    ]
    if len(geo) < 2:
        problems.append(f"fixture geo-located items < 2 ({len(geo)})")
    return problems


def _assert_explore_html(html: str) -> list[str]:
    problems: list[str] = []
    for marker in (
        "mb-explore",
        "What would you like to see?",
        "mb-explore-ask-row",
        "mb-explore-gallery",
        "mb-explore-map",
        "mb-tl-track",
        "mb-tl-reset",
        "Reset",
        "mb-density-label",
        "mb-tl-undated",
        "mb-modal-teach",
        "mb-viewer-rail",
        "mb-rail-tabs",
        "mb-quick-preview",
        "/static/explore/explore.js",
        "data-mb-surface=\"explore\"",
    ):
        if marker not in html:
            problems.append(f"UI missing: {marker}")
    if "mb-view-map" in html or "mb-view-gallery" in html:
        problems.append("Map must be a filter-bar control, not Gallery|Map toolbar toggle")
    if "Full Range" in html or "Life Span" in html:
        problems.append("Reset control must not use Full Range / Life Span labels")
    return problems


def _assert_explore_css(css: str) -> list[str]:
    problems: list[str] = []
    if ".mb-explore-ask-row" not in css:
        problems.append("explore.css missing .mb-explore-ask-row")
    if "flex-wrap: nowrap" not in css:
        problems.append("Ask row must use flex-wrap: nowrap where width permits")
    if ".mb-viewer" not in css or ".mb-quick-preview" not in css:
        problems.append("explore.css missing Shared Evidence Viewer / quick preview styles")
    if ".mb-viewer-zoom" not in css:
        problems.append("explore.css missing photo zoom control styles")
    if ".mb-rail-tools" not in css:
        problems.append("explore.css missing rail tools styles")
    if "max-height: calc(var(--mb-row-h) * 2" not in css and "max-height: calc(var(--mb-row-h) * 2 +" not in css:
        # two-row gallery target
        if "* 2 +" not in css and "* 2)" not in css:
            problems.append("gallery CSS should target two visible rows")
    return problems


def _assert_shell_family(js: str) -> list[str]:
    problems: list[str] = []
    for label in (
        "Ask",
        "People",
        "Stories",
        "Journal",
        "Artifacts",
        "Family Night",
        "Review & Learn",
    ):
        if label not in js:
            problems.append(f"shell family missing label: {label}")
    # Archive Health must not be in FAMILY primary block as first-class family nav —
    # tolerate it in SYSTEM only.
    fam_start = js.find("const FAMILY")
    fam_end = js.find("const SYSTEM", fam_start)
    if fam_start < 0 or fam_end < 0:
        problems.append("shell FAMILY/SYSTEM blocks not found")
    else:
        fam = js[fam_start:fam_end]
        # Match href/label entries only (ignore comments).
        if 'label: "Archive Health"' in fam or 'href: "/status/ui"' in fam:
            problems.append("Archive Health still in FAMILY primary nav")
        if 'label: "Library"' in fam:
            problems.append("Library still in FAMILY primary nav")
    return problems


def _prove_harness() -> dict[str, Any]:
    from pathlib import Path

    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I4", "flightsim": False, "mode": "harness"}

    try:
        from memorybox.explore.payload import demo_payload

        payload = demo_payload("peggy-christmas")
        assert payload is not None
        fp = _assert_fixture(payload)
        _check("fixture_mixed_media", not fp, checks, problems, "; ".join(fp) if fp else "ok")
        meta["fixture_item_count"] = len(payload.get("items") or [])
    except Exception as exc:  # noqa: BLE001
        _check("fixture_mixed_media", False, checks, problems, str(exc))

    try:
        html = (Path(__file__).resolve().parent / "static" / "explore.html").read_text(
            encoding="utf-8"
        )
        from memorybox.shell.inject import inject_shell

        injected = inject_shell(html, surface="explore")
        hp = _assert_explore_html(injected)
        _check("explore_html", not hp, checks, problems, "; ".join(hp) if hp else "ok")
        css = (Path(__file__).resolve().parent / "static" / "explore.css").read_text(
            encoding="utf-8"
        )
        cp = _assert_explore_css(css)
        _check("explore_css_hierarchy", not cp, checks, problems, "; ".join(cp) if cp else "ok")
    except Exception as exc:  # noqa: BLE001
        _check("explore_html", False, checks, problems, str(exc))

    try:
        js = (Path(__file__).resolve().parent.parent / "shell" / "static" / "shell.js").read_text(
            encoding="utf-8"
        )
        sp = _assert_shell_family(js)
        _check("shell_family_nav", not sp, checks, problems, "; ".join(sp) if sp else "ok")
    except Exception as exc:  # noqa: BLE001
        _check("shell_family_nav", False, checks, problems, str(exc))

    try:
        js = (Path(__file__).resolve().parent / "static" / "explore.js").read_text(
            encoding="utf-8"
        )
        missing = []
        for marker in (
            "applyAskCommand",
            "setActiveRange",
            "snapshotExplore",
            "restoreExplore",
            "openModal",
            "closeModal",
            "only photos",
            "typeFilter",
            "density",
            "Show 2005 through 2011",
            "eligibleItems",
            "resultSetItems",
            "isDateBounded",
            "hasDatedExtent",
            "undatedEligible",
            "undatedFilter",
            "setUndatedFilter",
            "placeFilter",
            "setPlaceFilter",
            "renderMap",
            "Show map",
            "Clear location",
            "only undated",
            "never exclude undated from gallery",
            "data-map-filter",
            "mb-filter-map",
            "faceBoxHtml",
            "applyCorrectionConsequences",
            "confirmIdentityCorrection",
            "syncTimelineToEligibleDatedExtent",
            "Does NOT clear query/filters",
            "liveFind",
            "/explore/api/find",
            "No dated memories on the Timeline",
            "renderViewer",
            "renderRailPanel",
            "QUICK_PREVIEW_DELAY_MS",
            "scheduleQuickPreview",
            "renderQuickPreview",
            "bindCardPreview",
            "stepViewer",
            "mb-zoom-in",
            "mb-rail-exif-btn",
            "mb-viewer-share",
            "mb-rail-add-story",
            "enrichPhotoPeople",
            "bindPhotoPan",
            "renderRailTools",
            "Camera / EXIF",
            "smsHidden",
            "hidden in Gallery — say Add texts to show them",
            "textsPinned",
            "bindLazyThumbs",
        ):
            if marker not in js:
                missing.append(marker)
        _check(
            "explore_js_state",
            not missing,
            checks,
            problems,
            ("missing: " + ", ".join(missing)) if missing else "command/state/modal present",
        )
    except Exception as exc:  # noqa: BLE001
        _check("explore_js_state", False, checks, problems, str(exc))

    try:
        from memorybox.explore.find import items_from_ask_result, curator_from_items

        sample = {
            "photo_hits": [
                {
                    "provider_key": "immich",
                    "external_id": "x1",
                    "taken_at": "2010-12-24T12:00:00",
                    "people": ["Test"],
                    "mb_person_name": "Test",
                }
            ],
            "video_hits": [
                {
                    "provider_key": "hvrt",
                    "external_id": "seg1",
                    "video_external_id": "vid1",
                    "start_sec": 12.5,
                    "end_sec": 14.0,
                    "mb_person_name": "Test",
                    "play_url": "/review/ui?video=vid1&t=12.5",
                },
                # Near-duplicate appearance moment (same clip / seek window)
                {
                    "provider_key": "hvrt",
                    "external_id": "mom-dup",
                    "video_external_id": "vid1",
                    "start_sec": 12.8,
                    "end_sec": 14.2,
                    "label": "face-appearance-moment",
                    "mb_person_name": None,
                    "play_url": "/review/ui?video=vid1&t=12.8",
                },
            ],
            "evidence_hits": [],
            "artifact_hits": [],
            "story_hits": [],
            "context": {"plan_slots": {"person": ["Test"]}},
        }
        mapped = items_from_ask_result(sample)
        _check(
            "ask_to_explore_mapper",
            len(mapped) == 2
            and mapped[0]["type"] == "photo"
            and mapped[1]["type"] == "video"
            and mapped[1].get("undated") is True
            and bool(mapped[1].get("play_url"))
            and mapped[1].get("face_identity") == "Test"
            and "face_box" not in mapped[1],
            checks,
            problems,
            f"n={len(mapped)} titles={[m.get('title') for m in mapped]}",
        )
        peggy = items_from_ask_result(
            {
                "photo_hits": [
                    {
                        "provider_key": "immich",
                        "external_id": "peg1",
                        "taken_at": "2012-12-25T12:00:00",
                        "people": [],
                        "mb_person_name": None,
                    }
                ],
                "context": {"person_names": ["Peggy"], "plan_slots": {"person": ["Peggy"]}},
                "provider_status": {
                    "photo": {"mapped_person_names": ["Peggy George"]}
                },
            }
        )
        peggy_people = list((peggy[0].get("people") if peggy else None) or [])
        _check(
            "people_rail_ask_scoped_person",
            bool(peggy)
            and "Peggy" in peggy_people
            and "Peggy George" in peggy_people
            and peggy[0].get("face_identity") not in (None, "", "Unknown"),
            checks,
            problems,
            f"people={peggy_people} face={peggy[0].get('face_identity') if peggy else None}",
        )
        _t, _s = curator_from_items("Show me Test", mapped, None)
        _check("curator_builder", bool(_s), checks, problems, (_s or "")[:80])
        all_ask_items = (
            [{"type": "photo"} for _ in range(131)]
            + [{"type": "video"}]
            + [
                {"type": "sms", "gallery_default_hidden": True}
                for _ in range(500)
            ]
        )
        _pt, _ps = curator_from_items("Show me Peggy George", all_ask_items, None)
        _check(
            "all_ask_curator_counts_hidden_texts",
            "632" in _ps
            and "131 photo" in _ps
            and "500 text" in _ps
            and "1 video" in _ps,
            checks,
            problems,
            (_ps or "")[:160],
        )
        from memorybox.explore.find import _sms_attach_windows

        xmas_windows = _sms_attach_windows(
            {
                "temporal_windows": [
                    ["2023-12-04", "2024-01-01"],
                    ["2024-12-04", "2025-01-01"],
                ],
                "time_start": "1950-12-04",
                "time_end": "2027-01-01",
                "temporal_label": "Christmas",
            }
        )
        _check(
            "christmas_sms_uses_holiday_windows_not_lifetime",
            xmas_windows == (
                ("2023-12-04", "2024-01-01"),
                ("2024-12-04", "2025-01-01"),
            ),
            checks,
            problems,
            f"windows={xmas_windows}",
        )
        _check(
            "christmas_sms_no_lifetime_fallback",
            _sms_attach_windows(
                {
                    "temporal_label": "Christmas",
                    "time_start": "1950-01-01",
                    "time_end": "2027-12-31",
                }
            )
            == (),
            checks,
            problems,
            "holiday label without windows must not attach all-time texts",
        )
    except Exception as exc:  # noqa: BLE001
        _check("ask_to_explore_mapper", False, checks, problems, str(exc))

    try:
        from memorybox.context import AskContext
        from memorybox.planner import plan_ask
        from memorybox.planner.temporal import (
            holiday_window,
            parse_temporal,
            resolve_holiday_date,
        )

        ctx = AskContext.empty("prove-i4-compose")

        def _plan(ask: str):
            return plan_ask(ask, ctx)

        c1 = _plan("Tom Will 2025")
        _check(
            "i4_compose_case1_year",
            c1.person_names == ("Tom Will",)
            and c1.time_start == "2025-01-01"
            and c1.time_end == "2025-12-31"
            and c1.visual_scope == "broad"
            and c1.temporal_label == "2025",
            checks,
            problems,
            f"people={c1.person_names} time={c1.time_start}..{c1.time_end} vs={c1.visual_scope}",
        )

        c2 = _plan("Tom Will 2023 to 2025")
        _check(
            "i4_compose_case2_year_range",
            c2.person_names == ("Tom Will",)
            and c2.time_start == "2023-01-01"
            and c2.time_end == "2025-12-31"
            and len(c2.temporal_windows) == 1,
            checks,
            problems,
            f"time={c2.time_start}..{c2.time_end} label={c2.temporal_label}",
        )

        c3 = _plan("Tom Will summer 2025")
        _check(
            "i4_compose_case3_summer",
            c3.time_start == "2025-06-01"
            and c3.time_end == "2025-08-31"
            and c3.temporal_label == "Summer 2025",
            checks,
            problems,
            f"time={c3.time_start}..{c3.time_end} label={c3.temporal_label}",
        )

        c4 = _plan("Tom Will in Alaska")
        _check(
            "i4_compose_case4_alaska",
            c4.person_names == ("Tom Will",)
            and c4.place_names == ("Alaska",)
            and c4.visual_scope == "broad",
            checks,
            problems,
            f"people={c4.person_names} places={c4.place_names}",
        )

        c5 = _plan("Tom Will in Paris")
        _check(
            "i4_compose_case5_paris",
            c5.person_names == ("Tom Will",) and c5.place_names == ("Paris",),
            checks,
            problems,
            f"places={c5.place_names}",
        )

        easter_2022 = resolve_holiday_date("easter", 2022)
        c6 = _plan("Tom Will Easter 2022")
        w6 = holiday_window("easter", 2022)
        _check(
            "i4_compose_case6_easter_2022",
            easter_2022.isoformat() == "2022-04-17"
            and c6.temporal_windows == (w6,)
            and c6.time_start == w6[0]
            and c6.time_end == w6[1]
            and "Easter" in c6.event_labels,
            checks,
            problems,
            f"easter={easter_2022} windows={c6.temporal_windows} label={c6.temporal_label}",
        )

        c7 = _plan("Tom Will Easter 2018 through 2022")
        _check(
            "i4_compose_case7_easter_recurring",
            len(c7.temporal_windows) == 5
            and c7.temporal_windows[0] == holiday_window("easter", 2018)
            and c7.temporal_windows[-1] == holiday_window("easter", 2022)
            # Must NOT be one contiguous spring band
            and c7.temporal_windows[0][1] < c7.temporal_windows[1][0],
            checks,
            problems,
            f"n={len(c7.temporal_windows)} first={c7.temporal_windows[0]} last={c7.temporal_windows[-1]}",
        )

        c8 = _plan("Tom Will Memorial Day 2024")
        _check(
            "i4_compose_case8_memorial_day",
            resolve_holiday_date("memorial_day", 2024).isoformat() == "2024-05-27"
            and c8.temporal_windows == (holiday_window("memorial_day", 2024),),
            checks,
            problems,
            f"windows={c8.temporal_windows}",
        )

        c9 = _plan("Tom Will Labor Day 2024")
        _check(
            "i4_compose_case9_labor_day",
            resolve_holiday_date("labor_day", 2024).isoformat() == "2024-09-02"
            and c9.temporal_windows == (holiday_window("labor_day", 2024),),
            checks,
            problems,
            f"windows={c9.temporal_windows}",
        )

        c10 = _plan("Tom Will NYE 2023")
        _check(
            "i4_compose_case10_nye",
            c10.temporal_windows == (holiday_window("nye", 2023),)
            and c10.temporal_windows[0][0] == "2023-12-29",
            checks,
            problems,
            f"windows={c10.temporal_windows}",
        )

        c11 = _plan("Tom Will NYD 2024")
        _check(
            "i4_compose_case11_nyd",
            c11.temporal_windows == (holiday_window("nyd", 2024),),
            checks,
            problems,
            f"windows={c11.temporal_windows}",
        )

        c12 = _plan("Tom Will in Alaska 2026")
        _check(
            "i4_compose_case12_alaska_2026",
            c12.person_names == ("Tom Will",)
            and c12.place_names == ("Alaska",)
            and c12.time_start == "2026-01-01"
            and c12.time_end == "2026-12-31"
            and c12.visual_scope == "broad",
            checks,
            problems,
            f"people={c12.person_names} places={c12.place_names} time={c12.time_start}",
        )

        xmas = parse_temporal("Christmas 2022")
        _check(
            "i4_compose_christmas_window",
            xmas.windows == (("2022-12-04", "2023-01-01"),),
            checks,
            problems,
            f"christmas={xmas.windows}",
        )

        # US national / federal holidays (±2d; computed variable dates)
        national = {
            "MLK Day 2024": ("mlk_day", "2024-01-15"),
            "Presidents Day 2024": ("presidents_day", "2024-02-19"),
            "Juneteenth 2024": ("juneteenth", "2024-06-19"),
            "Veterans Day 2024": ("veterans_day", "2024-11-11"),
            "Columbus Day 2024": ("columbus_day", "2024-10-14"),
            "Mother's Day 2024": ("mothers_day", "2024-05-12"),
            "Father's Day 2024": ("fathers_day", "2024-06-16"),
            "Tom Will 4th of July 2024": ("july_4", "2024-07-04"),
        }
        nat_ok = True
        nat_detail = []
        for ask, (key, center) in national.items():
            p = _plan(ask) if ask.startswith("Tom") else parse_temporal(ask)
            got = (
                p.temporal_windows[0]
                if hasattr(p, "temporal_windows") and p.temporal_windows
                else (p.windows[0] if getattr(p, "windows", None) else None)
            )
            expect = holiday_window(key, 2024)
            center_ok = resolve_holiday_date(key, 2024).isoformat() == center
            win_ok = got == expect
            if not (center_ok and win_ok):
                nat_ok = False
            nat_detail.append(f"{key}:{center_ok}:{got}")
            if ask.startswith("Tom"):
                if p.person_names != ("Tom Will",):
                    nat_ok = False
                    nat_detail.append(f"people={p.person_names}")
        _check(
            "i4_compose_national_holidays",
            nat_ok,
            checks,
            problems,
            "; ".join(nat_detail),
        )

        bday = _plan("Tom Will birthday 2024")
        _check(
            "i4_compose_birthday_intent",
            bday.person_names == ("Tom Will",)
            and bday.life_event_kind == "birthday"
            and bday.life_event_years == (2024,)
            and bday.visual_scope == "broad"
            and "Birthday" in bday.event_labels,
            checks,
            problems,
            f"kind={bday.life_event_kind} years={bday.life_event_years} "
            f"people={bday.person_names} label={bday.temporal_label}",
        )
        ann = _plan("Tom Will anniversary 2018 through 2020")
        _check(
            "i4_compose_anniversary_intent",
            ann.life_event_kind == "anniversary"
            and ann.life_event_years == (2018, 2019, 2020)
            and ann.person_names == ("Tom Will",),
            checks,
            problems,
            f"kind={ann.life_event_kind} years={ann.life_event_years}",
        )
        from memorybox.planner.temporal import observance_window_md

        ow = observance_window_md(6, 11, 2024)
        _check(
            "i4_compose_observance_pad",
            ow == ("2024-06-09", "2024-06-13"),
            checks,
            problems,
            f"observance={ow}",
        )
        # Missing MB People birth_date must not invent windows (orchestrator).
        from memorybox.ask.orchestrator import _apply_person_life_event_windows

        applied = _apply_person_life_event_windows(bday)
        _check(
            "i4_compose_birthday_missing_data_no_invent",
            applied.requires_clarification is True
            and not applied.temporal_windows
            and (
                "birth_date" in (applied.ambiguity_message or "").lower()
                or "person" in (applied.ambiguity_message or "").lower()
            ),
            checks,
            problems,
            f"clarify={applied.requires_clarification} msg={applied.ambiguity_message} "
            f"windows={applied.temporal_windows}",
        )

        js = (Path(__file__).resolve().parent / "static" / "explore.js").read_text(
            encoding="utf-8"
        )
        _check(
            "i4_compose_explore_sync_markers",
            "temporalWindows" in js
            and "explore_state" in js
            and "temporal_windows" in js
            and "clear date" in js
            # Regression: "Show me <Person>" must NOT be a client place filter.
            and 'at|show)' not in js
            and "never keep a stale pin" in js,
            checks,
            problems,
            "explore.js shared temporal/place sync markers",
        )

        peggy_full = _plan("Show me Peggy George")
        _check(
            "i4_compose_show_me_peggy_george",
            peggy_full.person_names == ("Peggy George",)
            and peggy_full.place_names == ()
            and peggy_full.time_start is None
            and peggy_full.visual_scope == "broad"
            and peggy_full.want_still
            and peggy_full.want_video,
            checks,
            problems,
            f"people={peggy_full.person_names} places={peggy_full.place_names} "
            f"t={peggy_full.time_start} vs={peggy_full.visual_scope}",
        )
        sticky = AskContext(
            session_id="prove-peggy-subject",
            person_names=("Sue Will",),
            place_names=("Alaska",),
            time_start="2020-01-01",
            time_end="2020-12-31",
        )
        peggy_fresh = plan_ask("Show me Peggy George", sticky)
        _check(
            "i4_show_me_person_clears_prior_subject",
            peggy_fresh.person_names == ("Peggy George",)
            and peggy_fresh.place_names == ()
            and peggy_fresh.time_start is None
            and peggy_fresh.visual_scope == "broad"
            and "supersede_person_subject_change" in (peggy_fresh.notes or ()),
            checks,
            problems,
            f"people={peggy_fresh.person_names} places={peggy_fresh.place_names} "
            f"t={peggy_fresh.time_start} notes={peggy_fresh.notes}",
        )
        peggy_in = _plan("Show me Peggy in 2021")
        _check(
            "i4_compose_show_me_peggy_year",
            peggy_in.person_names == ("Peggy",)
            and peggy_in.place_names == ()
            and peggy_in.time_start == "2021-01-01"
            and peggy_in.visual_scope == "broad",
            checks,
            problems,
            f"people={peggy_in.person_names} places={peggy_in.place_names} "
            f"t={peggy_in.time_start} vs={peggy_in.visual_scope}",
        )
        peggy_xmas = _plan("Show me Peggy during Christmas 2021")
        _check(
            "i4_compose_show_me_peggy_christmas",
            peggy_xmas.person_names == ("Peggy",)
            and peggy_xmas.place_names == ()
            and peggy_xmas.temporal_windows == (("2021-12-04", "2022-01-01"),)
            and "Christmas" in peggy_xmas.event_labels,
            checks,
            problems,
            f"people={peggy_xmas.person_names} places={peggy_xmas.place_names} "
            f"win={peggy_xmas.temporal_windows}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("i4_compose_query_expansion", False, checks, problems, str(exc))

    try:
        from memorybox.profile.ask_resolve import _PICTURES_OF_ME_RE

        self_asks = (
            "Show me myself",
            "show me me",
            "pictures of myself",
            "Show myself",
        )
        miss = [a for a in self_asks if not _PICTURES_OF_ME_RE.search(a)]
        _check(
            "show_me_myself_regex",
            not miss,
            checks,
            problems,
            ("miss: " + ", ".join(miss)) if miss else "self patterns match",
        )
    except Exception as exc:  # noqa: BLE001
        _check("show_me_myself_regex", False, checks, problems, str(exc))

    try:
        from memorybox.context import AskContext
        from memorybox.planner import plan_ask

        ctx = AskContext(session_id="prove-self", person_names=("Eugene Will",))
        plan = plan_ask("Show me myself", ctx)
        _check(
            "show_me_myself_no_inherit_dad",
            "Eugene Will" not in (plan.person_names or ())
            and "show_me_self_no_inherit_person" in (plan.notes or ())
            and plan.want_visual is True,
            checks,
            problems,
            f"people={plan.person_names} notes={plan.notes}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("show_me_myself_no_inherit_dad", False, checks, problems, str(exc))

    try:
        from memorybox.context import AskContext
        from memorybox.planner import plan_ask

        for ask in ("Show Tom Will", "Show Anne Will", "Show Diane Scollay"):
            plan = plan_ask(ask, AskContext.empty("prove-show-person"))
            ok_plan = (
                plan.want_visual is True
                and plan.want_still is True
                and bool(plan.person_names)
            )
            if not ok_plan:
                _check(
                    "show_person_forces_visual",
                    False,
                    checks,
                    problems,
                    f"{ask}: people={plan.person_names} visual={plan.want_visual} story={plan.want_story}",
                )
                break
        else:
            _check(
                "show_person_forces_visual",
                True,
                checks,
                problems,
                "Show <Person> → broad visual (stories OK as secondary)",
            )
    except Exception as exc:  # noqa: BLE001
        _check("show_person_forces_visual", False, checks, problems, str(exc))

    try:
        from memorybox.providers.photo._immich_http import ImmichHttpClient

        class _FakeImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None
                self._calls: list[dict[str, Any]] = []

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                if method != "POST":
                    return 404, None
                assert path == "/search/metadata"
                # Prefer withExif for Map GPS; fake Immich accepts it.
                page = int((body or {}).get("page") or 1)
                order = str((body or {}).get("order") or "desc")
                size = int((body or {}).get("size") or 100)
                taken_after = (body or {}).get("takenAfter")
                self._calls.append(
                    {
                        "page": page,
                        "order": order,
                        "size": size,
                        "takenAfter": taken_after,
                        "withExif": (body or {}).get("withExif"),
                    }
                )
                # Simulate Immich bug: assets.total == page size (not library total).
                total_library = 600
                start = (page - 1) * size
                items = []
                for i in range(size):
                    idx = start + i
                    if idx >= total_library:
                        break
                    items.append(
                        {
                            "id": f"asset-{idx}",
                            "originalFileName": f"{idx}.jpg",
                            "exifInfo": {
                                "latitude": 38.597,
                                "longitude": -90.509,
                                "city": "Manchester",
                                "state": "Missouri",
                                "country": "United States of America",
                            },
                        }
                    )
                next_page = str(page + 1) if start + len(items) < total_library else None
                return 200, {
                    "assets": {
                        "items": items,
                        "total": len(items),
                        "count": len(items),
                        "nextPage": next_page,
                    }
                }

        client = _FakeImmich()
        got = client.search_by_person_ids(["person-1"], size=500)
        _check(
            "immich_person_full_page",
            len(got) >= 500 and len(client._calls) >= 2,
            checks,
            problems,
            f"n={len(got)} calls={len(client._calls)}",
        )
        _check(
            "immich_with_exif_for_map",
            any(c.get("withExif") is True for c in client._calls)
            and bool(got)
            and isinstance((got[0].get("exifInfo") or {}).get("latitude"), (int, float)),
            checks,
            problems,
            f"calls={len(client._calls)} sample_exif={got[0].get('exifInfo') if got else None}",
        )
        client2 = _FakeImmich()
        got_all = client2.search_by_person_ids(["person-1"], size=5000)
        _check(
            "immich_person_exhausts_library",
            len(got_all) >= 600,
            checks,
            problems,
            f"n={len(got_all)} calls={len(client2._calls)}",
        )
        client3 = _FakeImmich()
        got_trap = client3.search_by_person_ids(["person-1"], size=5000)
        _check(
            "immich_ignores_page_total_trap",
            len(got_trap) > 120,
            checks,
            problems,
            f"n={len(got_trap)} (must exceed fake page total)",
        )

        class _ExifTimeoutImmich(_FakeImmich):
            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                if (body or {}).get("withExif"):
                    raise TimeoutError("withExif RST")
                return super()._request(method, path, body=body, timeout=timeout, retries=retries)

        client4 = _ExifTimeoutImmich()
        got_no_exif = client4.search_by_person_ids(["person-1"], size=50)
        _check(
            "immich_person_library_survives_exif_timeout",
            len(got_no_exif) >= 25,
            checks,
            problems,
            f"n={len(got_no_exif)} calls={len(client4._calls)}",
        )
        from memorybox.providers.photo._immich_http import ImmichHttpClient as _ImmichIds

        _check(
            "immich_face_asset_id_not_path",
            _ImmichIds._immich_asset_id("uploads/thumbs/abc.jpg") is None
            and _ImmichIds._immich_asset_id("cc6eb438-86a9-405c-89aa-6c6fc43de076")
            is not None,
            checks,
            problems,
            "Face fallback must use asset UUIDs, not thumbnailPath",
        )

        class _RstMetadataFacesImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                if method == "POST":
                    raise TimeoutError("search/metadata RST")
                if method == "GET" and str(path).startswith("/people/person-1"):
                    return 200, {
                        "id": "person-1",
                        "name": "Peggy George",
                        "faceAssetId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "faces": [
                            {
                                "id": "f1",
                                "assetId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            },
                            {
                                "id": "f2",
                                "assetId": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                            },
                        ],
                    }
                return 404, None

        client5 = _RstMetadataFacesImmich()
        got_faces = client5.search_by_person_ids(["person-1"], size=50)
        _check(
            "immich_person_library_via_faces_when_metadata_rst",
            len(got_faces) >= 2
            and {
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            }.issubset({str(x.get("id")) for x in got_faces}),
            checks,
            problems,
            f"n={len(got_faces)} ids={[x.get('id') for x in got_faces]}",
        )

        class _RstMetadataTimelineImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                if method == "POST":
                    raise TimeoutError("search/metadata RST")
                p = str(path)
                if "timeline/buckets" in p:
                    return 200, [{"timeBucket": "2020-01-01", "count": 2}]
                if "timeline/bucket" in p:
                    return 200, {
                        "id": [
                            "ccccccc1-1111-2222-3333-444444444444",
                            "ccccccc2-1111-2222-3333-444444444444",
                        ],
                        "isImage": [True, True],
                        "fileCreatedAt": [
                            "2020-01-15T00:00:00.000Z",
                            "2020-01-16T00:00:00.000Z",
                        ],
                    }
                return 404, None

        client6 = _RstMetadataTimelineImmich()
        got_tl = client6.search_by_person_ids(["person-1"], size=50)
        _check(
            "immich_person_library_via_timeline_when_metadata_rst",
            len(got_tl) >= 2
            and all(str(x.get("id") or "").startswith("ccccccc") for x in got_tl),
            checks,
            problems,
            f"n={len(got_tl)} ids={[x.get('id') for x in got_tl]}",
        )

        class _FacesSubsetTimelineLibraryImmich(ImmichHttpClient):
            """Peggy bug: faces return 131; Immich person page is timeline 598."""

            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None
                self.timeline_calls = 0

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                if method == "POST":
                    raise TimeoutError("search/metadata RST")
                p = str(path)
                if method == "GET" and p.startswith("/people/person-1"):
                    faces = [
                        {
                            "id": f"f{i}",
                            "assetId": f"{i:08d}-aaaa-bbbb-cccc-dddddddddddd",
                        }
                        for i in range(131)
                    ]
                    return 200, {"id": "person-1", "name": "Peggy George", "faces": faces}
                if "timeline/buckets" in p:
                    return 200, [
                        {"timeBucket": f"{2000 + y}-01-01", "count": 20}
                        for y in range(30)
                    ]
                if "timeline/bucket" in p:
                    self.timeline_calls += 1
                    # 30 year buckets × 20 assets = 600 (Immich person page).
                    import re

                    m = re.search(r"timeBucket=(\d{4})", p)
                    year = int(m.group(1)) if m else 2000
                    yoff = year - 2000
                    return 200, [
                        {
                            "id": f"{yoff:02d}{i:02d}cccc-1111-2222-3333-444444444444",
                            "isImage": True,
                        }
                        for i in range(20)
                    ]
                return 404, None

        client_peggy = _FacesSubsetTimelineLibraryImmich()
        got_peggy = client_peggy.search_by_person_ids(["person-1"], size=5000)
        _check(
            "immich_person_library_unions_faces_and_full_timeline",
            len(got_peggy) >= 480
            and client_peggy.timeline_calls >= 20
            and client_peggy.timeline_calls <= 24
            and getattr(client_peggy, "_last_person_source", "") == "faces_or_timeline",
            checks,
            problems,
            f"n={len(got_peggy)} tl_calls={client_peggy.timeline_calls} "
            f"src={getattr(client_peggy, '_last_person_source', None)}",
        )
        tl_before = client_peggy.timeline_calls
        got_cached = client_peggy.search_by_person_ids(["person-1"], size=5000)
        _check(
            "immich_person_library_cached_on_reask",
            len(got_cached) == len(got_peggy)
            and client_peggy.timeline_calls == tl_before
            and getattr(client_peggy, "_last_person_source", "") == "cache",
            checks,
            problems,
            f"n={len(got_cached)} tl={client_peggy.timeline_calls} "
            f"src={getattr(client_peggy, '_last_person_source', None)}",
        )
        _check(
            "immich_year_buckets_newest_first",
            _ImmichIds._sort_time_buckets_newest_first(
                ["1983-01-01", "2024-01-01", "1901-01-01"]
            )[0].startswith("2024"),
            checks,
            problems,
            "Must walk 2024 before 1983 so recent person photos are not dropped",
        )

        class _TwoPersonStickyImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None
                self.paths: list[str] = []

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                p = str(path)
                self.paths.append(p)
                if method == "POST":
                    raise TimeoutError("search/metadata RST")
                if "timeline/buckets" in p:
                    return 200, [{"timeBucket": "2020-01-01", "count": 1}]
                if "timeline/bucket" in p:
                    who = "p1" if "person-1" in p else "p2"
                    return 200, [{"id": f"{who}aaaaaa-1111-2222-3333-444444444444"}]
                return 404, None

        two = _TwoPersonStickyImmich()
        a1 = two.search_by_person_ids(["person-1"], size=20)
        a2 = two.search_by_person_ids(["person-2"], size=20)
        bucket_lists = [p for p in two.paths if "timeline/buckets" in p]
        _check(
            "immich_person_timeline_not_sticky_across_people",
            any("person-1" in p for p in bucket_lists)
            and any("person-2" in p for p in bucket_lists)
            and {str(x.get("id")) for x in a1} != {str(x.get("id")) for x in a2},
            checks,
            problems,
            f"lists={bucket_lists} a1={[x.get('id') for x in a1]} a2={[x.get('id') for x in a2]}",
        )

        _check(
            "immich_name_matches_peggy_george_to_peggy",
            _ImmichIds._name_matches_person("Peggy George", "Peggy")
            and _ImmichIds._name_matches_person("Peggy", "Peggy George")
            and not _ImmichIds._name_matches_person("Ann", "Anne Will"),
            checks,
            problems,
            "Ask Peggy George must match Immich Peggy",
        )

        class _SearchPersonImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None
                self.n = 0

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                self.n += 1
                if method == "POST" and path == "/search/person":
                    return 200, [
                        {"id": "immich-peggy", "name": "Peggy"},
                    ]
                return 404, None

        client7 = _SearchPersonImmich()
        named = client7.find_people_by_name("Peggy George")
        _check(
            "immich_search_person_not_full_people_dump",
            len(named) == 1
            and named[0].get("id") == "immich-peggy"
            and client7.n <= 2,
            checks,
            problems,
            f"n={len(named)} calls={client7.n}",
        )

        class _TimeoutImmich(ImmichHttpClient):
            def __init__(self) -> None:  # noqa: D107
                self.ui_root = "http://immich.test"
                self.api_base = "http://immich.test/api"
                self._key = "test"
                self.thumbs_root = None
                self.n = 0

            def _request(self, method, path, body=None, timeout=30, retries=2):  # noqa: ANN001
                self.n += 1
                raise TimeoutError("RST")

        client8 = _TimeoutImmich()
        got_to = client8.search_by_person_ids(["person-1"], size=50)
        _check(
            "immich_person_search_fail_fast",
            got_to == []
            and client8.n <= 3
            and getattr(client8, "_last_person_source", "") == "timeout",
            checks,
            problems,
            f"n_calls={client8.n} src={getattr(client8, '_last_person_source', None)}",
        )
        n_after_fail = client8.n
        got_to2 = client8.search_by_person_ids(["person-1"], size=50)
        _check(
            "immich_circuit_stays_closed_on_reask",
            got_to2 == []
            and client8.n == n_after_fail
            and bool(getattr(client8, "_circuit_open", False)),
            checks,
            problems,
            f"n_calls={client8.n} was={n_after_fail} "
            f"src={getattr(client8, '_last_person_source', None)}",
        )
        diag_c = object.__new__(_ImmichIds)
        diag_c._call_log = [
            {
                "ts": "2026-08-15T18:00:00",
                "method": "GET",
                "path": "/server/ping",
                "status": 0,
                "ms": 8000,
                "err": "timed out",
                "circuit": True,
            }
        ]
        diag_c._circuit_open = True
        diag_c._last_person_source = "timeout"
        snap = _ImmichIds.diag_snapshot(diag_c)
        _check(
            "immich_activity_diag_snapshot",
            int(snap.get("fails") or 0) >= 1
            and snap.get("circuit") is True
            and snap.get("source") == "timeout",
            checks,
            problems,
            f"snap={snap}",
        )
        client8._circuit_open = True
        named_open = client8.find_people_by_name("Peggy George")
        _check(
            "immich_name_search_survives_mapped_circuit",
            client8._circuit_allows("/search/person")
            and not client8._circuit_allows("/people/stale-id"),
            checks,
            problems,
            f"named={named_open} allows_search={client8._circuit_allows('/search/person')}",
        )

        import tempfile
        from pathlib import Path as _Path

        local_aid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        tmp_thumbs = _Path(tempfile.mkdtemp())
        (tmp_thumbs / local_aid[:2]).mkdir()
        (tmp_thumbs / local_aid[:2] / f"{local_aid}-thumbnail.webp").write_bytes(
            b"RIFF" + b"\x00" * 40
        )
        disk_c = object.__new__(_ImmichIds)
        disk_c.thumbs_root = tmp_thumbs
        local_got = _ImmichIds._read_local_thumb(disk_c, local_aid)
        _check(
            "immich_thumb_from_local_thumbs_path",
            bool(local_got and local_got[0] and local_got[1] == "image/webp"),
            checks,
            problems,
            f"got={None if not local_got else (len(local_got[0]), local_got[1])}",
        )
        miss_c = object.__new__(_ImmichIds)
        miss_c.thumbs_root = None
        miss_c.api_base = "http://immich.test/api"
        miss_c._key = "test"
        miss_c._circuit_open = False
        miss_c._fetch_api_image = lambda *a, **k: None
        try:
            _ImmichIds.fetch_preview_bytes(miss_c, local_aid)
            thumb_err = None
        except FileNotFoundError as exc:
            thumb_err = exc
        _check(
            "immich_http_thumb_miss_does_not_open_circuit",
            thumb_err is not None and not bool(getattr(miss_c, "_circuit_open", False)),
            checks,
            problems,
            f"err={thumb_err} circuit={getattr(miss_c, '_circuit_open', None)}",
        )
        from memorybox.ask import deps as ask_deps

        p_a = ask_deps.build_photo()
        p_b = ask_deps.build_photo()
        _check(
            "photo_provider_is_process_singleton",
            p_a is p_b,
            checks,
            problems,
            f"a={type(p_a).__name__} b={type(p_b).__name__}",
        )

        from memorybox.person import _ask_named_photo_people
        from memorybox.providers.photo.dto import PhotoPersonRef

        class _ImmichNamedPeggy:
            def list_people(self, *, query=None, limit=50):  # noqa: ANN001
                return [
                    PhotoPersonRef(
                        provider_key="immich",
                        external_id="immich-peggy",
                        display_name="Peggy",
                    )
                ]

        got_ask = _ask_named_photo_people(_ImmichNamedPeggy(), "Peggy George")
        _check(
            "ask_named_photo_people_upgrades_peggy",
            len(got_ask) == 1
            and getattr(got_ask[0], "external_id", "") == "immich-peggy",
            checks,
            problems,
            f"refs={[(getattr(r, 'display_name', None), getattr(r, 'external_id', None)) for r in got_ask]}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("immich_person_full_page", False, checks, problems, str(exc))

    try:
        from memorybox.providers.photo.immich import ImmichPhotoProvider

        prov = object.__new__(ImmichPhotoProvider)
        prov._client = type(
            "C",
            (),
            {
                "thumb_url": staticmethod(lambda *a, **k: None),
                "web_url": staticmethod(lambda *a, **k: None),
            },
        )()
        mapped = ImmichPhotoProvider._map_asset(
            prov,
            {
                "id": "gps-1",
                "exifInfo": {
                    "latitude": "38.597",
                    "longitude": "-90.509",
                    "city": "Manchester",
                    "state": "Missouri",
                    "country": "United States of America",
                    "dateTimeOriginal": "2020-02-29T21:43:06",
                },
            },
        )
        _check(
            "immich_exif_gps_mapped",
            mapped.location is not None
            and abs(float(mapped.location.latitude) - 38.597) < 0.001
            and abs(float(mapped.location.longitude) - (-90.509)) < 0.001
            and mapped.location.city == "Manchester",
            checks,
            problems,
            str(mapped.location),
        )
    except Exception as exc:  # noqa: BLE001
        _check("immich_exif_gps_mapped", False, checks, problems, str(exc))

    try:
        from datetime import datetime, timezone

        from memorybox.ask import retrieve as R
        from memorybox.planner import QueryPlan
        from memorybox.providers.base import ProviderHealth
        from memorybox.providers.photo.dto import PhotoAssetDto, PhotoPersonRef, PhotoSearchQuery
        from memorybox import person as person_mod

        person = PhotoPersonRef(
            provider_key="scripted_photo",
            external_id="eugene-immich-id",
            display_name="Eugene Will",
        )
        person_assets = [
            PhotoAssetDto(
                provider_key="scripted_photo",
                external_id=f"eugene-{i}",
                taken_at=datetime(2010, 1, 1, tzinfo=timezone.utc),
                people=(person,),
            )
            for i in range(5)
        ]
        recent_library = [
            PhotoAssetDto(
                provider_key="scripted_photo",
                external_id=f"recent-{i}",
                taken_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
                people=(),
            )
            for i in range(3)
        ]

        class _CountingPhoto:
            provider_key = "scripted_photo"

            def __init__(self) -> None:
                self.calls: list[PhotoSearchQuery] = []

            def health(self) -> ProviderHealth:
                return ProviderHealth(provider_key=self.provider_key, ok=True, detail="ok")

            def list_people(self, *, query: str | None = None, limit: int = 50):
                return [person]

            def search_assets(self, query: PhotoSearchQuery):
                self.calls.append(query)
                if query.person_external_ids:
                    return list(person_assets)[: query.limit]
                return list(recent_library)[: query.limit]

        photo = _CountingPhoto()
        plan = QueryPlan(
            original_ask="Show me Eugene Will",
            effective_ask="Show me Eugene Will",
            is_followup=False,
            want_photo=True,
            want_communication=False,
            want_calendar=False,
            want_still=True,
            want_video=True,
            want_visual=True,
            visual_scope="broad",
            person_names=("Eugene Will",),
            notes=("visual_scope=broad_show_me_person",),
        )

        class _FakePerson:
            id = "mb-eugene"
            display_name = "Eugene Will"
            identity_authority = "owner_confirmed"
            provider_mappings = [
                {
                    "provider_key": "scripted_photo",
                    "external_id": "eugene-immich-id",
                    "identity_authority": "owner_confirmed",
                }
            ]

        orig = {
            "get_person": person_mod.get_person,
            "find_ask_person_by_name": person_mod.find_ask_person_by_name,
            "list_provider_external_ids_for_person": person_mod.list_provider_external_ids_for_person,
            "find_confirmed_person_by_name": person_mod.find_confirmed_person_by_name,
            "is_negative": person_mod.is_negative,
        }
        person_mod.get_person = lambda _pid: None  # type: ignore[assignment]
        person_mod.find_ask_person_by_name = (  # type: ignore[assignment]
            lambda name, photo=None, lazy_seed=True: _FakePerson()
        )
        person_mod.list_provider_external_ids_for_person = (  # type: ignore[assignment]
            lambda person_id, provider_key: ["eugene-immich-id"]
        )
        person_mod.find_confirmed_person_by_name = (  # type: ignore[assignment]
            lambda name: _FakePerson()
        )
        person_mod.is_negative = lambda **kwargs: False  # type: ignore[assignment]
        try:
            hits, st = R.search_photos(plan, photo, limit=5000)
        finally:
            for k, v in orig.items():
                setattr(person_mod, k, v)

        years = {(h.taken_at or "")[:4] for h in hits if h.taken_at}
        _check(
            "person_ask_no_library_pad",
            len(hits) == 5
            and "2026" not in years
            and bool(photo.calls)
            and all(c.person_external_ids for c in photo.calls)
            and "supplementing_via_name_search" not in str(st.get("detail") or ""),
            checks,
            problems,
            f"n={len(hits)} years={sorted(years)} calls={len(photo.calls)} detail={st.get('detail')}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("person_ask_no_library_pad", False, checks, problems, str(exc))

    try:
        from datetime import datetime, timezone

        from memorybox.ask import retrieve as R
        from memorybox.planner import QueryPlan
        from memorybox.providers.base import ProviderHealth
        from memorybox.providers.photo.dto import PhotoAssetDto, PhotoPersonRef, PhotoSearchQuery
        from memorybox import person as person_mod

        peggy_ref = PhotoPersonRef(
            provider_key="scripted_photo",
            external_id="peggy-immich",
            display_name="Peggy George",
        )
        mixed_assets = [
            PhotoAssetDto(
                provider_key="scripted_photo",
                external_id="xmas-dated",
                taken_at=datetime(2021, 12, 20, tzinfo=timezone.utc),
                people=(peggy_ref,),
            ),
            PhotoAssetDto(
                provider_key="scripted_photo",
                external_id="july-dated",
                taken_at=datetime(2021, 7, 4, tzinfo=timezone.utc),
                people=(peggy_ref,),
            ),
            PhotoAssetDto(
                provider_key="scripted_photo",
                external_id="undated-face",
                taken_at=None,
                people=(peggy_ref,),
            ),
        ]

        class _XmasPhoto:
            provider_key = "scripted_photo"

            def health(self) -> ProviderHealth:
                return ProviderHealth(provider_key=self.provider_key, ok=True, detail="ok")

            def list_people(self, *, query: str | None = None, limit: int = 50):
                return [peggy_ref]

            def search_assets(self, query: PhotoSearchQuery):
                return list(mixed_assets)

        class _XmasPerson:
            id = "mb-peggy"
            display_name = "Peggy George"
            identity_authority = "owner_confirmed"
            provider_mappings = [
                {
                    "provider_key": "scripted_photo",
                    "external_id": "peggy-immich",
                    "identity_authority": "owner_confirmed",
                }
            ]

        xmas_plan = QueryPlan(
            original_ask="show me Peggy George during Christmas time",
            effective_ask="show me Peggy George during Christmas time",
            is_followup=False,
            want_photo=True,
            want_communication=False,
            want_calendar=False,
            want_still=True,
            want_video=True,
            want_visual=True,
            visual_scope="broad",
            person_names=("Peggy George",),
            event_labels=("Christmas",),
            temporal_label="Christmas",
            temporal_windows=(("2021-12-04", "2022-01-01"),),
            time_start="2021-12-04",
            time_end="2022-01-01",
            notes=("holiday_all_years", "visual_scope=broad_show_me_person"),
        )
        orig_x = {
            "get_person": person_mod.get_person,
            "find_ask_person_by_name": person_mod.find_ask_person_by_name,
            "list_provider_external_ids_for_person": person_mod.list_provider_external_ids_for_person,
            "find_confirmed_person_by_name": person_mod.find_confirmed_person_by_name,
            "is_negative": person_mod.is_negative,
        }
        person_mod.get_person = lambda _pid: None  # type: ignore[assignment]
        person_mod.find_ask_person_by_name = (  # type: ignore[assignment]
            lambda name, photo=None, lazy_seed=True: _XmasPerson()
        )
        person_mod.list_provider_external_ids_for_person = (  # type: ignore[assignment]
            lambda person_id, provider_key: ["peggy-immich"]
        )
        person_mod.find_confirmed_person_by_name = (  # type: ignore[assignment]
            lambda name: _XmasPerson()
        )
        person_mod.is_negative = lambda **kwargs: False  # type: ignore[assignment]
        try:
            xhits, _xst = R.search_photos(xmas_plan, _XmasPhoto(), limit=50)
        finally:
            for k, v in orig_x.items():
                setattr(person_mod, k, v)
        xids = {h.external_id for h in xhits}
        _check(
            "christmas_keeps_undated_drops_off_season",
            "xmas-dated" in xids
            and "undated-face" in xids
            and "july-dated" not in xids,
            checks,
            problems,
            f"ids={sorted(xids)}",
        )
    except Exception as exc:  # noqa: BLE001
        _check(
            "christmas_keeps_undated_drops_off_season",
            False,
            checks,
            problems,
            str(exc),
        )

    try:
        from datetime import datetime, timezone

        from memorybox.ask import retrieve as R
        from memorybox.planner import QueryPlan
        from memorybox.providers.base import ProviderHealth
        from memorybox.providers.photo.dto import PhotoAssetDto, PhotoPersonRef, PhotoSearchQuery
        from memorybox import person as person_mod

        live = PhotoPersonRef(
            provider_key="scripted_photo",
            external_id="immich-live-peggy",
            display_name="Peggy",
        )
        live_asset = PhotoAssetDto(
            provider_key="scripted_photo",
            external_id="live-face-1",
            taken_at=datetime(2021, 12, 20, tzinfo=timezone.utc),
            people=(live,),
        )

        class _StaleThenName:
            provider_key = "scripted_photo"

            def __init__(self) -> None:
                self._client = type(
                    "C",
                    (),
                    {
                        "_last_person_source": "timeout",
                        "_reset_person_circuit": lambda self=None: None,
                    },
                )()

            def health(self) -> ProviderHealth:
                return ProviderHealth(provider_key=self.provider_key, ok=True, detail="ok")

            def list_people(self, *, query: str | None = None, limit: int = 50):
                return [live]

            def search_assets(self, query: PhotoSearchQuery):
                ids = list(query.person_external_ids or ())
                if ids == ["stale-mapped-id"]:
                    self._client._last_person_source = "timeout"
                    return []
                if "immich-live-peggy" in ids:
                    self._client._last_person_source = "faces_or_timeline"
                    return [live_asset]
                return []

        class _MappedStale:
            id = "mb-peggy"
            display_name = "Peggy George"
            identity_authority = "owner_confirmed"
            provider_mappings = [
                {
                    "provider_key": "scripted_photo",
                    "external_id": "stale-mapped-id",
                    "identity_authority": "owner_confirmed",
                }
            ]

        orig_s = {
            "get_person": person_mod.get_person,
            "find_ask_person_by_name": person_mod.find_ask_person_by_name,
            "list_provider_external_ids_for_person": person_mod.list_provider_external_ids_for_person,
            "find_confirmed_person_by_name": person_mod.find_confirmed_person_by_name,
            "is_negative": person_mod.is_negative,
        }
        person_mod.get_person = lambda _pid: None  # type: ignore[assignment]
        person_mod.find_ask_person_by_name = (  # type: ignore[assignment]
            lambda name, photo=None, lazy_seed=True: _MappedStale()
        )
        person_mod.list_provider_external_ids_for_person = (  # type: ignore[assignment]
            lambda person_id, provider_key: ["stale-mapped-id"]
        )
        person_mod.find_confirmed_person_by_name = (  # type: ignore[assignment]
            lambda name: _MappedStale()
        )
        person_mod.is_negative = lambda **kwargs: False  # type: ignore[assignment]
        try:
            shits, sst = R.search_photos(
                QueryPlan(
                    original_ask="show me Peggy George",
                    effective_ask="show me Peggy George",
                    is_followup=False,
                    want_photo=True,
                    want_communication=False,
                    want_calendar=False,
                    want_still=True,
                    want_visual=True,
                    visual_scope="broad",
                    person_names=("Peggy George",),
                ),
                _StaleThenName(),
                limit=50,
            )
        finally:
            for k, v in orig_s.items():
                setattr(person_mod, k, v)
        _check(
            "stale_mapped_id_falls_back_to_immich_name",
            len(shits) == 1
            and shits[0].external_id == "live-face-1"
            and sst.get("unavailable") is not True,
            checks,
            problems,
            f"n={len(shits)} ids={[h.external_id for h in shits]} detail={sst.get('detail')}",
        )
    except Exception as exc:  # noqa: BLE001
        _check(
            "stale_mapped_id_falls_back_to_immich_name",
            False,
            checks,
            problems,
            str(exc),
        )

    try:
        from memorybox.person import AmbiguousIdentityError, PersonView, _pick_unique_ask_person

        a = PersonView(
            id="a1",
            display_name="Tom Will",
            status="confirmed",
            identity_authority="owner_confirmed",
        )
        b = PersonView(
            id="a2",
            display_name="Tom Smith",
            status="confirmed",
            identity_authority="owner_confirmed",
        )
        try:
            _pick_unique_ask_person([a, b])
            _check(
                "first_name_ambiguous_clarify",
                False,
                checks,
                problems,
                "expected AmbiguousIdentityError",
            )
        except AmbiguousIdentityError as exc:
            msg = str(exc)
            _check(
                "first_name_ambiguous_clarify",
                "Please specify which Tom you would like" in msg
                and "Tom Will" in msg
                and "Tom Smith" in msg,
                checks,
                problems,
                msg,
            )
        alone = _pick_unique_ask_person([a])
        _check(
            "first_name_unique_proceeds",
            alone is not None and alone.id == "a1",
            checks,
            problems,
            f"got={alone}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("first_name_ambiguous_clarify", False, checks, problems, str(exc))

    ok = not problems
    return {
        "ok": ok,
        "checks": checks,
        "problems": problems,
        "meta": meta,
        "acceptance_gate_authority": "docs/product/MBBS-P2_INCREMENT_4_DEFINITION.md §8",
        "manual_gate_cases": [
            "A Filter + Timeline interaction",
            "B Undated evidence",
            "C Density independence",
            "D Teach and return",
            "E Ask command equivalence",
        ],
        "note": "Harness is structural. ACCEPTED requires FlightSim manual pass of every §8 row and §8.1 cases A–E.",
    }


def _prove_flightsim() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I4", "flightsim": True, "mode": "flightsim"}

    if _env("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        _check(
            "p1_runtime_host",
            False,
            checks,
            problems,
            "MEMORYBOX_P1_RUNTIME_HOST must be 1 on FlightSim",
        )
    else:
        _check("p1_runtime_host", True, checks, problems, "1")

    port = _env("MEMORYBOX_PORT", "8790")
    base = _env("MEMORYBOX_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    meta["base_url"] = base

    # Local harness assertions still required
    harness = _prove_harness()
    for k, v in (harness.get("checks") or {}).items():
        checks[f"harness_{k}"] = v
    for p in harness.get("problems") or []:
        problems.append(f"harness: {p}")

    st, html, _ = _fetch(f"{base}/explore/ui?demo=peggy-christmas")
    _check("explore_ui_http", st == 200, checks, problems, f"status={st}")
    if st == 200:
        hp = _assert_explore_html(html)
        _check("explore_ui_markers", not hp, checks, problems, "; ".join(hp) if hp else "ok")

    st2, body, _ = _fetch(f"{base}/explore/api/demo/peggy-christmas")
    _check("explore_demo_api", st2 == 200, checks, problems, f"status={st2}")
    if st2 == 200:
        import json

        try:
            payload = json.loads(body)
            fp = _assert_fixture(payload)
            _check("live_fixture", not fp, checks, problems, "; ".join(fp) if fp else "ok")
            meta["live_item_count"] = len(payload.get("items") or [])
        except Exception as exc:  # noqa: BLE001
            _check("live_fixture", False, checks, problems, str(exc))

    st_find, find_body, _ = _fetch(f"{base}/explore/api/find")
    _check("explore_find_api", st_find == 200, checks, problems, f"status={st_find}")
    if st_find == 200:
        import json

        try:
            find_payload = json.loads(find_body)
            _check(
                "explore_find_live_flag",
                find_payload.get("live") is True and find_payload.get("demo") is False,
                checks,
                problems,
                f"live={find_payload.get('live')} demo={find_payload.get('demo')}",
            )
        except Exception as exc:  # noqa: BLE001
            _check("explore_find_live_flag", False, checks, problems, str(exc))

    st3, _, _ = _fetch(f"{base}/family-night/ui")
    _check("family_night_ui", st3 == 200, checks, problems, f"status={st3}")

    ok = not problems
    return {
        "ok": ok,
        "checks": checks,
        "problems": problems,
        "meta": meta,
        "acceptance_gate_authority": "docs/product/MBBS-P2_INCREMENT_4_DEFINITION.md §8",
        "acceptance_gate": [
            {"area": "Ask", "criterion": "Prompt + entry on one line where practical; Ask remains visible but compact", "automated": "structural"},
            {"area": "Gallery", "criterion": "Mixed-media, two rows, target 12+ visible objects at 13\" class viewport", "automated": "fixture count only"},
            {"area": "Density", "criterion": "User can easily show more/smaller or fewer/larger cards", "automated": "structural"},
            {"area": "Filters", "criterion": "Lightweight, immediately applied, common state for mouse/Ask/STT", "automated": "structural"},
            {"area": "Timeline", "criterion": "One unified graphical Timeline/scrubber", "automated": "structural"},
            {"area": "Banding", "criterion": "Dragging a period narrows result and increases precision", "automated": "manual"},
            {"area": "Handles", "criterion": "Widen/narrow current temporal range", "automated": "manual"},
            {"area": "Reset", "criterion": "Restores full temporal extent of current query+context+type-filter set; does not clear filters", "automated": "structural"},
            {"area": "Undated", "criterion": "Matching undated always in Gallery when filter off; Undated control left of Timeline + filter bar; no fake date", "automated": "fixture+structural"},
            {"area": "Synchronization", "criterion": "Timeline changes immediately update Gallery", "automated": "manual"},
            {"area": "Scrub", "criterion": "Playhead continuously moves Gallery through chronological neighborhood", "automated": "structural"},
            {"area": "Detail", "criterion": "Large modal, not new screen", "automated": "structural"},
            {"area": "Return", "criterion": "Close restores prior state then applies correction consequences", "automated": "structural"},
            {"area": "Extensibility", "criterion": "Same modal shell supports mixed evidence types", "automated": "fixture types"},
            {"area": "Teach proof", "criterion": "Visible I1 identity-correction affordance in modal", "automated": "structural"},
            {"area": "Health", "criterion": "Not top-level", "automated": "shell FAMILY check"},
            {"area": "Context", "criterion": "Query/filter/date/gallery state coherent for Ask/STT", "automated": "structural"},
        ],
        "manual_gate_cases": [
            "A Filter + Timeline interaction",
            "B Undated evidence",
            "C Density independence",
            "D Teach and return",
            "E Ask command equivalence",
        ],
        "note": "prove-p2-i4 is structural assist only. ACCEPTED requires manual pass of every §8 row and §8.1 cases A–E on FlightSim.",
    }
