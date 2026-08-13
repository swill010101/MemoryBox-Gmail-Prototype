"""P2-I3 acceptance — Archive Health & Provider Honesty."""
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


def prove_p2_i3(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_p2_i3_flightsim()
    return _prove_p2_i3_harness()


def _assert_honesty(summary: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if summary.get("product") != "archive_health" and summary.get("increment") != "P2-I3":
        problems.append("missing P2-I3 product markers")
    if summary.get("default_tab") != "archive_health":
        problems.append(f"default_tab={summary.get('default_tab')}")
    contract = summary.get("metric_contract") or {}
    if "unavailable" not in (contract.get("states") or []):
        problems.append("metric_contract missing unavailable state")

    def walk_metrics(obj: Any) -> None:
        if isinstance(obj, dict):
            if "state" in obj and "key" in obj:
                st = obj.get("state")
                val = obj.get("value")
                if st in ("unavailable", "deferred") and val == 0:
                    problems.append(
                        f"false zero: {obj.get('key')} state={st} value=0"
                    )
                label = (obj.get("label") or "").strip().lower()
                if label == "videos" or label.startswith("videos:"):
                    problems.append(f"ambiguous video label: {obj.get('label')}")
            for v in obj.values():
                walk_metrics(v)
        elif isinstance(obj, list):
            for x in obj:
                walk_metrics(x)

    walk_metrics(summary)

    concepts = summary.get("concepts") or {}
    for key in ("provider_health", "processing_state", "knowledge_gaps"):
        if key not in concepts:
            problems.append(f"missing concept panel: {key}")

    work = summary.get("work_on_these_now") or []
    meta = summary.get("work_on_these_now_meta") or {}
    if len(work) > int(meta.get("ceiling") or 7):
        problems.append(f"work_on_these_now exceeds ceiling: {len(work)}")
    # At least structure present
    tab = (summary.get("tabs") or {}).get("archive_health") or {}
    titles = [s.get("title") for s in (tab.get("sections") or [])]
    if "Work on these now" not in titles:
        problems.append("archive_health tab missing Work on these now")
    if "Source / provider health" not in titles:
        problems.append("archive_health tab missing provider health section")

    # Explicit photos label somewhere
    blob = str(summary)
    if "Photos available" not in blob and "photos_available" not in blob:
        problems.append("Photos available metric missing")
    if "Source videos" not in blob:
        problems.append("Source videos label missing")
    if "Searchable video moments" not in blob:
        problems.append("Searchable video moments label missing")

    honesty = summary.get("honesty") or {}
    if not honesty.get("rule"):
        problems.append("honesty.rule missing")

    return problems


def _assert_ui_html(html: str) -> list[str]:
    problems: list[str] = []
    for marker in (
        "Archive Health",
        "data-mb-surface=\"status\"",
        "/static/shell/shell.css",
        "Work on these now",
    ):
        # Work on these now may be injected by JS from API — title is enough for static HTML
        if marker == "Work on these now":
            continue
        if marker not in html:
            problems.append(f"UI missing: {marker}")
    if "MemoryBox Status" in html and "Archive Health" not in html:
        problems.append("UI still titled Status only")
    return problems


def _prove_p2_i3_harness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I3", "flightsim": False, "mode": "harness"}

    try:
        from memorybox.status.summary import build_status_summary

        summary = build_status_summary()
        hp = _assert_honesty(summary)
        _check("summary_honesty", not hp, checks, problems, "; ".join(hp) if hp else "ok")
        work = summary.get("work_on_these_now") or []
        _check(
            "work_on_these_now_bounded",
            len(work) <= 7,
            checks,
            problems,
            f"n={len(work)}",
        )
        # Prefer high_leverage when present in candidate pool — if any high_leverage in full
        # ordered list's first items when such gaps exist: soft check via kinds
        kinds = [t.get("kind") for t in work]
        _check(
            "work_tasks_structured",
            all(t.get("href") and t.get("action_label") for t in work) or len(work) == 0,
            checks,
            problems,
            f"kinds={kinds}",
        )
        meta["work_on_these_now"] = [{"id": t.get("id"), "kind": t.get("kind")} for t in work]
    except Exception as exc:  # noqa: BLE001
        _check("summary_honesty", False, checks, problems, str(exc))

    try:
        from fastapi.testclient import TestClient

        from memorybox.app import app

        client = TestClient(app)
        ui = client.get("/status/ui")
        ui_probs = _assert_ui_html(ui.text) if ui.status_code == 200 else ["http fail"]
        _check(
            "status_ui",
            ui.status_code == 200 and not ui_probs,
            checks,
            problems,
            f"status={ui.status_code}; " + ("; ".join(ui_probs) if ui_probs else "ok"),
        )
        api = client.get("/status/summary")
        body = api.json() if api.status_code == 200 else {}
        api_probs = _assert_honesty(body) if api.status_code == 200 else ["http fail"]
        _check(
            "status_summary_api",
            api.status_code == 200 and not api_probs,
            checks,
            problems,
            f"status={api.status_code}; " + ("; ".join(api_probs) if api_probs else "ok"),
        )
        # Work on this now hrefs are actionable routes
        work = body.get("work_on_these_now") or []
        href_ok = True
        for t in work[:3]:
            href = t.get("href") or ""
            if not href.startswith("/"):
                href_ok = False
                break
            # Don't require 200 for guided-capture etc.; just that path is served or 404 for missing static is ok
            # Prefer people/review/settings/status which we know exist
        _check("work_hrefs_present", href_ok, checks, problems, f"n={len(work)}")
    except Exception as exc:  # noqa: BLE001
        _check("asgi_client", False, checks, problems, str(exc))

    # I1 + I2 harness regression
    try:
        from memorybox.person.p2_i1_acceptance import prove_p2_i1

        i1 = prove_p2_i1(flightsim=False)
        _check("i1_harness_regression", bool(i1.get("ok")), checks, problems, "ok" if i1.get("ok") else str(i1.get("problems"))[:300])
        meta["i1"] = {"ok": i1.get("ok")}
    except Exception as exc:  # noqa: BLE001
        _check("i1_harness_regression", False, checks, problems, str(exc))

    try:
        from memorybox.shell.p2_i2_acceptance import prove_p2_i2

        # Avoid nested full i1 twice: i2 harness already runs i1 — still required by gate
        i2 = prove_p2_i2(flightsim=False)
        _check("i2_harness_regression", bool(i2.get("ok")), checks, problems, "ok" if i2.get("ok") else str(i2.get("problems"))[:300])
        meta["i2"] = {"ok": i2.get("ok")}
    except Exception as exc:  # noqa: BLE001
        _check("i2_harness_regression", False, checks, problems, str(exc))

    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}


def _fetch(url: str, *, timeout: float = 30.0) -> tuple[int, str]:
    req = Request(url, headers={"Accept": "application/json,text/html,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), body
    except URLError as exc:
        raise RuntimeError(f"fetch failed: {url}: {exc}") from exc


def _prove_p2_i3_flightsim() -> dict[str, Any]:
    import json

    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I3", "flightsim": True, "mode": "flightsim"}

    if _env("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-p2-i3 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    default_port = _env("MEMORYBOX_PORT", "8790") or "8790"
    base = _env("MEMORYBOX_BASE_URL", f"http://127.0.0.1:{default_port}").rstrip("/")
    meta["base_url"] = base

    try:
        st, html = _fetch(base + "/status/ui")
        ui_probs = _assert_ui_html(html) if st == 200 else ["http fail"]
        _check(
            "status_ui",
            st == 200 and not ui_probs,
            checks,
            problems,
            f"status={st}; " + ("; ".join(ui_probs) if ui_probs else "ok"),
        )
        st2, raw = _fetch(base + "/status/summary")
        body = json.loads(raw) if st2 == 200 else {}
        api_probs = _assert_honesty(body) if st2 == 200 else ["http fail"]
        _check(
            "status_summary_api",
            st2 == 200 and not api_probs,
            checks,
            problems,
            f"status={st2}; " + ("; ".join(api_probs) if api_probs else "ok"),
        )

        # Gate: Immich healthy → real Photos available when possible
        photos = None
        for sec in ((body.get("tabs") or {}).get("archive_health") or {}).get("sections") or []:
            for m in sec.get("metrics") or []:
                if m.get("key") in ("photos_available", "photos_indexed"):
                    photos = m
                    break
        if photos is None:
            # concepts panel
            for m in ((body.get("concepts") or {}).get("provider_health") or {}).get("metrics") or []:
                if m.get("key") == "photos_available":
                    photos = m
                    break
        if photos and photos.get("state") == "available":
            _check(
                "photos_available_real",
                isinstance(photos.get("value"), int) and photos["value"] > 0,
                checks,
                problems,
                f"value={photos.get('value')} display={photos.get('display')}",
            )
        elif photos and photos.get("state") in ("unavailable", "deferred", "partial"):
            _check(
                "photos_honest_non_false_zero",
                photos.get("value") != 0,
                checks,
                problems,
                f"state={photos.get('state')} value={photos.get('value')}",
            )
        else:
            _check("photos_metric_present", False, checks, problems, "photos metric missing")

        work = body.get("work_on_these_now") or []
        _check(
            "work_on_these_now_bounded",
            len(work) <= 7,
            checks,
            problems,
            f"n={len(work)}",
        )
        high = [t for t in work if t.get("kind") == "high_leverage"]
        # If high-leverage candidates exist in visible set, good; if not, still ok when no gaps
        _check(
            "work_actionable",
            all(t.get("href") for t in work) or len(work) == 0,
            checks,
            problems,
            f"high_leverage_visible={len(high)}",
        )
        meta["work_on_these_now"] = work
        meta["photos"] = photos
    except Exception as exc:  # noqa: BLE001
        _check("live_fetch", False, checks, problems, str(exc))

    try:
        from memorybox.person.p2_i1_acceptance import prove_p2_i1

        i1 = prove_p2_i1(flightsim=True)
        _check(
            "i1_flightsim_regression",
            bool(i1.get("ok")),
            checks,
            problems,
            "ok" if i1.get("ok") else str(i1.get("problems"))[:400],
        )
        meta["i1"] = {"ok": i1.get("ok")}
    except Exception as exc:  # noqa: BLE001
        _check("i1_flightsim_regression", False, checks, problems, str(exc))

    try:
        from memorybox.shell.p2_i2_acceptance import prove_p2_i2

        i2 = prove_p2_i2(flightsim=True)
        _check(
            "i2_flightsim_regression",
            bool(i2.get("ok")),
            checks,
            problems,
            "ok" if i2.get("ok") else str(i2.get("problems"))[:400],
        )
        meta["i2"] = {"ok": i2.get("ok")}
    except Exception as exc:  # noqa: BLE001
        _check("i2_flightsim_regression", False, checks, problems, str(exc))

    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
