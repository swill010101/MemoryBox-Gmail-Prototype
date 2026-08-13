"""P2-I2 acceptance — Product Shell & Context Maturation.

Desktop harness (no --flightsim): in-process ASGI checks + inject unit checks.
FlightSim (--flightsim): same shell checks against live serve + I1 regression.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pathlib import Path

from memorybox.shell.inject import inject_shell

SHELL_STATIC = Path(__file__).resolve().parent / "static"


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def prove_p2_i2(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_p2_i2_flightsim()
    return _prove_p2_i2_harness()


def _assert_shell_html(html: str, *, surface: str, invitation: bool = False) -> list[str]:
    """Return list of problem strings (empty = pass)."""
    problems: list[str] = []
    if "/static/shell/shell.css" not in html:
        problems.append("missing shell.css link")
    if "/static/shell/shell.js" not in html:
        problems.append("missing shell.js script")
    if f'data-mb-surface="{surface}"' not in html:
        problems.append(f'missing data-mb-surface="{surface}"')
    if invitation:
        for marker in (
            "mb-invite-title",
            "What would you like to explore today?",
            "mb-journey",
            "Show me Peggy George",
            'id="providers"',
        ):
            if marker not in html:
                problems.append(f"invitation home missing marker: {marker}")
        # Progressive disclosure: provider status behind details
        if "<details" not in html or "Provider status" not in html:
            problems.append("provider status not progressive (details)")
    return problems


def _assert_shell_assets() -> list[str]:
    problems: list[str] = []
    css = SHELL_STATIC / "shell.css"
    js = SHELL_STATIC / "shell.js"
    if not css.is_file():
        problems.append("shell.css missing")
    else:
        text = css.read_text(encoding="utf-8")
        for token in ("--mb-forest", "--mb-font-display", ".mb-nav-family", ".mb-nav-system", "mb-global-ask"):
            if token not in text:
                problems.append(f"shell.css missing token: {token}")
    if not js.is_file():
        problems.append("shell.js missing")
    else:
        text = js.read_text(encoding="utf-8")
        for token in (
            "mb-global-ask",
            "mb_shell_context_stack",
            "mb-nav-family",
            "Archive Health",
            "Settings",
            "pushContext",
            "mb_return",
        ):
            if token not in text:
                problems.append(f"shell.js missing token: {token}")
        # Family nav must not list Settings/Archive Health as family destinations
        # (they appear in SYSTEM array). Soft check: SYSTEM block present.
        if "const SYSTEM" not in text and "SYSTEM =" not in text:
            problems.append("shell.js missing SYSTEM destinations block")
    return problems


def _prove_p2_i2_harness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I2", "flightsim": False, "mode": "harness"}

    asset_probs = _assert_shell_assets()
    _check(
        "shell_assets",
        not asset_probs,
        checks,
        problems,
        "; ".join(asset_probs) if asset_probs else "ok",
    )

    sample = (
        "<!DOCTYPE html><html lang='en'><head><title>t</title></head>"
        "<body><main>hi</main></body></html>"
    )
    injected = inject_shell(sample, surface="library")
    inj_probs = _assert_shell_html(injected, surface="library")
    _check(
        "inject_shell",
        not inj_probs,
        checks,
        problems,
        "; ".join(inj_probs) if inj_probs else "ok",
    )
    # Idempotent
    again = inject_shell(injected, surface="library")
    _check(
        "inject_idempotent",
        again.count("/static/shell/shell.css") == 1,
        checks,
        problems,
        f"css count={again.count('/static/shell/shell.css')}",
    )

    try:
        from fastapi.testclient import TestClient

        from memorybox.app import app

        client = TestClient(app)
        r = client.get("/", follow_redirects=False)
        _check(
            "root_redirect",
            r.status_code in (307, 302) and "/ask/ui" in (r.headers.get("location") or ""),
            checks,
            problems,
            f"status={r.status_code} loc={r.headers.get('location')}",
        )

        surfaces = {
            "ask": ("/ask/ui", True),
            "library": ("/library/ui", False),
            "people": ("/people/ui", False),
            "review": ("/review/ui", False),
            "status": ("/status/ui", False),
            "settings": ("/settings/ui", False),
        }
        for surface, (path, invitation) in surfaces.items():
            resp = client.get(path)
            ok_http = resp.status_code == 200
            html = resp.text if ok_http else ""
            html_probs = _assert_shell_html(html, surface=surface, invitation=invitation) if ok_http else ["http fail"]
            _check(
                f"surface_{surface}",
                ok_http and not html_probs,
                checks,
                problems,
                f"status={resp.status_code}; " + ("; ".join(html_probs) if html_probs else "ok"),
            )

        # Static assets mount
        css_r = client.get("/static/shell/shell.css")
        js_r = client.get("/static/shell/shell.js")
        _check(
            "static_mount",
            css_r.status_code == 200 and js_r.status_code == 200,
            checks,
            problems,
            f"css={css_r.status_code} js={js_r.status_code}",
        )

        # Health advertises settings
        health = client.get("/health")
        body = health.json() if health.status_code == 200 else {}
        _check(
            "health_settings_entry",
            body.get("settings") == "/settings/ui",
            checks,
            problems,
            f"settings={body.get('settings')}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("asgi_client", False, checks, problems, str(exc))

    # I1 harness regression (synthetic) — optional soft fail only if import/run breaks
    try:
        from memorybox.person.p2_i1_acceptance import prove_p2_i1

        i1 = prove_p2_i1(flightsim=False)
        _check(
            "i1_harness_regression",
            bool(i1.get("ok")),
            checks,
            problems,
            "ok" if i1.get("ok") else str(i1.get("problems") or i1)[:400],
        )
        meta["i1"] = {"ok": i1.get("ok"), "mode": "harness"}
    except Exception as exc:  # noqa: BLE001
        _check("i1_harness_regression", False, checks, problems, str(exc))

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}


def _fetch(url: str, *, timeout: float = 20.0) -> tuple[int, str, dict[str, str]]:
    req = Request(url, headers={"Accept": "text/html,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), resp.read().decode("utf-8", errors="replace"), headers
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), body, {}
    except URLError as exc:
        raise RuntimeError(f"fetch failed: {url}: {exc}") from exc


def _prove_p2_i2_flightsim() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I2", "flightsim": True, "mode": "flightsim"}

    if _env("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-p2-i2 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    base = _env("MEMORYBOX_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    meta["base_url"] = base

    asset_probs = _assert_shell_assets()
    _check(
        "shell_assets",
        not asset_probs,
        checks,
        problems,
        "; ".join(asset_probs) if asset_probs else "ok",
    )

    try:
        # Root redirect
        status, _, headers = _fetch(base + "/")
        loc = headers.get("location") or ""
        # Some stacks follow; accept 200 ask page or redirect
        if status in (301, 302, 303, 307, 308):
            _check(
                "root_redirect",
                "/ask/ui" in loc,
                checks,
                problems,
                f"status={status} loc={loc}",
            )
        else:
            # Follow manually
            st2, html2, _ = _fetch(base + "/ask/ui")
            _check(
                "root_redirect",
                st2 == 200 and "mb-invite-title" in html2,
                checks,
                problems,
                f"no redirect status={status}; ask={st2}",
            )

        surfaces = {
            "ask": ("/ask/ui", True),
            "library": ("/library/ui", False),
            "people": ("/people/ui", False),
            "review": ("/review/ui", False),
            "status": ("/status/ui", False),
            "settings": ("/settings/ui", False),
        }
        for surface, (path, invitation) in surfaces.items():
            st, html, _ = _fetch(base + path)
            html_probs = _assert_shell_html(html, surface=surface, invitation=invitation) if st == 200 else ["http fail"]
            _check(
                f"surface_{surface}",
                st == 200 and not html_probs,
                checks,
                problems,
                f"status={st}; " + ("; ".join(html_probs) if html_probs else "ok"),
            )

        st_css, _, _ = _fetch(base + "/static/shell/shell.css")
        st_js, _, _ = _fetch(base + "/static/shell/shell.js")
        _check(
            "static_mount",
            st_css == 200 and st_js == 200,
            checks,
            problems,
            f"css={st_css} js={st_js}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("live_fetch", False, checks, problems, str(exc))

    # I1 FlightSim regression required for ACCEPTED gate
    try:
        from memorybox.person.p2_i1_acceptance import prove_p2_i1

        i1 = prove_p2_i1(flightsim=True)
        _check(
            "i1_flightsim_regression",
            bool(i1.get("ok")),
            checks,
            problems,
            "ok" if i1.get("ok") else str(i1.get("problems") or i1)[:500],
        )
        meta["i1"] = {"ok": i1.get("ok"), "mode": "flightsim"}
    except Exception as exc:  # noqa: BLE001
        _check("i1_flightsim_regression", False, checks, problems, str(exc))

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
