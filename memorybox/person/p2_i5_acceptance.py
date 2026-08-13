"""P2-I5 Universal Person Surfaces — structural acceptance harness."""
from __future__ import annotations

from pathlib import Path

from memorybox.explore.p2_i4_acceptance import _check


def run_p2_i5_acceptance() -> dict:
    checks: dict = {}
    problems: list[str] = []

    person_html = (
        Path(__file__).resolve().parent / "static" / "person-explore.html"
    ).read_text(encoding="utf-8")
    person_css = (
        Path(__file__).resolve().parent / "static" / "person-explore.css"
    ).read_text(encoding="utf-8")
    person_js = (
        Path(__file__).resolve().parent / "static" / "person-explore.js"
    ).read_text(encoding="utf-8")
    explore_js = (
        Path(__file__).resolve().parents[1]
        / "explore"
        / "static"
        / "explore.js"
    ).read_text(encoding="utf-8")
    app_py = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    _check(
        "i5_person_explore_html",
        "mb-person-header" in person_html
        and "Ask about" in person_html
        and "mb-person-footer" in person_html
        and "MB_PERSON_SURFACE" in person_html
        and 'data-mode="highlights"' in person_html
        and "/static/explore/explore.js" in person_html,
        checks,
        problems,
        "person-explore.html shell",
    )
    _check(
        "i5_person_dark_theme",
        "mb-person-surface" in person_css and "#0f141c" in person_css,
        checks,
        problems,
        "dark theme CSS",
    )
    _check(
        "i5_explore_person_mode",
        "PERSON_MODE" in explore_js
        and "personScopedAsk" in explore_js
        and "rankHighlights" in explore_js
        and "ensureLockedPersonChip" in explore_js
        and "clear everything except" in explore_js
        and 'id: "audio"' in explore_js
        and 'id: "location"' in explore_js
        and "has GPS/Place" in explore_js,
        checks,
        problems,
        "explore.js person mode hooks",
    )
    _check(
        "i5_people_ui_route",
        "PERSON_EXPLORE_STATIC" in app_py
        and "Person Explorer" in app_py
        and 'person: str | None' in app_py,
        checks,
        problems,
        "/people/ui?person= route",
    )
    _check(
        "i5_person_panels_js",
        "loadProfile" in person_js
        and "mb-person-learn-stats" in person_js
        and "mb-person-ready" in person_js
        and "renderAboutDrawer" in person_js
        and "renderFamilyDrawer" in person_js
        and "renderLearnDrawer" in person_js
        and "/review/ui" in person_js,
        checks,
        problems,
        "About/Family/Learn drawers + Review deep link",
    )
    _check(
        "i5_person_drawer_shell",
        "mb-person-drawer" in person_html
        and "Open full profile editor" in person_html
        and "locationFilterMode" in person_html,
        checks,
        problems,
        "secondary drawer + Location=D boot config",
    )
    _check(
        "i5_ask_person_commands",
        "go to" in explore_js
        and "instead" in explore_js
        and "stays locked" in explore_js
        and "person_name=" in explore_js,
        checks,
        problems,
        "Go to … instead + locked-person Ask guards",
    )
    _check(
        "i5_reuse_not_iframe",
        "iframe" not in person_html.lower()
        and "explore.js" in person_html,
        checks,
        problems,
        "reuses explore.js (no iframe)",
    )

    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {"increment": "P2-I5", "mode": "harness"},
        "note": (
            "Harness is structural. ACCEPTED requires FlightSim manual pass "
            "of I5 directive §31 cases 1–13."
        ),
    }


def main() -> None:
    import json

    print(json.dumps(run_p2_i5_acceptance(), indent=2))


if __name__ == "__main__":
    main()
