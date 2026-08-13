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
        "mb-view-map",
        "mb-tl-track",
        "mb-tl-reset",
        "Reset",
        "mb-density-label",
        "mb-tl-undated",
        "mb-modal-teach",
        "/static/explore/explore.js",
        "data-mb-surface=\"explore\"",
    ):
        if marker not in html:
            problems.append(f"UI missing: {marker}")
    if "Full Range" in html or "Life Span" in html:
        problems.append("Reset control must not use Full Range / Life Span labels")
    return problems


def _assert_explore_css(css: str) -> list[str]:
    problems: list[str] = []
    if ".mb-explore-ask-row" not in css:
        problems.append("explore.css missing .mb-explore-ask-row")
    if "flex-wrap: nowrap" not in css:
        problems.append("Ask row must use flex-wrap: nowrap where width permits")
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
            "Only undated",
            "never exclude undated from gallery",
            "faceBoxHtml",
            "applyCorrectionConsequences",
            "confirmIdentityCorrection",
            "syncTimelineToEligibleDatedExtent",
            "Does NOT clear query/filters",
            "liveFind",
            "/explore/api/find",
            "No dated memories on the Timeline",
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
        _t, _s = curator_from_items("Show me Test", mapped, None)
        _check("curator_builder", bool(_s), checks, problems, (_s or "")[:80])
    except Exception as exc:  # noqa: BLE001
        _check("ask_to_explore_mapper", False, checks, problems, str(exc))

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
            {"area": "Undated", "criterion": "Matching undated discoverable unbounded; no fake date; excluded when date-bounded", "automated": "fixture+structural"},
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
