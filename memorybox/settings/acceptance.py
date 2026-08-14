"""Thin Settings + video-source acceptance (harness, no FlightSim required)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from memorybox.settings.video_root import (
    ENV_VIDEO_DERIVED_DIR,
    ENV_VIDEO_MEDIA_ROOT,
    describe_video_media_root,
    resolve_video_media_root,
    set_video_media_root,
    sidecar_path,
)

SETTINGS_HTML = Path(__file__).resolve().parent / "static" / "settings.html"


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_settings_thin() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    prev_env = os.environ.get(ENV_VIDEO_MEDIA_ROOT)
    prev_derived = os.environ.get(ENV_VIDEO_DERIVED_DIR)
    try:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            os.environ[ENV_VIDEO_DERIVED_DIR] = tmp
            os.environ.pop(ENV_VIDEO_MEDIA_ROOT, None)

            from memorybox.settings import video_root as vr

            orig_write = vr._write_db
            orig_read = vr._read_db
            vr._write_db = lambda value, *, actor_key="owner": True
            vr._read_db = lambda: ""
            try:
                sp = sidecar_path()
                if sp.is_file():
                    sp.unlink()

                _check(
                    "unset_without_env_or_sidecar",
                    resolve_video_media_root() is None,
                    checks,
                    problems,
                    f"got={resolve_video_media_root()!r}",
                )

                os.environ[ENV_VIDEO_MEDIA_ROOT] = str(Path(tmp) / "from-env")
                _check(
                    "env_bootstrap_when_no_settings",
                    resolve_video_media_root() == os.environ[ENV_VIDEO_MEDIA_ROOT],
                    checks,
                    problems,
                    f"got={resolve_video_media_root()!r}",
                )

                saved = set_video_media_root(str(Path(tmp) / "from-settings"), actor_key="harness")
                _check(
                    "settings_overrides_env",
                    resolve_video_media_root() == str(Path(tmp) / "from-settings")
                    and saved.get("source") == "settings_sidecar"
                    and saved.get("settings_overrides_env") is True,
                    checks,
                    problems,
                    f"resolved={resolve_video_media_root()!r} src={saved.get('source')}",
                )

                cleared = set_video_media_root("", actor_key="harness")
                _check(
                    "clear_falls_back_to_env",
                    resolve_video_media_root() == os.environ[ENV_VIDEO_MEDIA_ROOT]
                    and cleared.get("source") == "env",
                    checks,
                    problems,
                    f"resolved={resolve_video_media_root()!r} src={cleared.get('source')}",
                )

                desc = describe_video_media_root()
                _check(
                    "describe_has_effective",
                    desc.get("ok") is True and bool(desc.get("effective_root")),
                    checks,
                    problems,
                    str(desc)[:240],
                )
            finally:
                vr._write_db = orig_write
                vr._read_db = orig_read
    finally:
        if prev_env is None:
            os.environ.pop(ENV_VIDEO_MEDIA_ROOT, None)
        else:
            os.environ[ENV_VIDEO_MEDIA_ROOT] = prev_env
        if prev_derived is None:
            os.environ.pop(ENV_VIDEO_DERIVED_DIR, None)
        else:
            os.environ[ENV_VIDEO_DERIVED_DIR] = prev_derived

    from memorybox.providers.photo.http_range import apply_http_range

    st, chunk, hdrs = apply_http_range(b"abcdefghij", "bytes=2-5")
    _check(
        "http_range_slice",
        st == 206 and chunk == b"cdef" and "bytes 2-5/10" in str(hdrs.get("Content-Range")),
        checks,
        problems,
        f"st={st} chunk={chunk!r}",
    )
    html = SETTINGS_HTML.read_text(encoding="utf-8") if SETTINGS_HTML.is_file() else ""
    for marker in (
        'data-mb-surface="settings"',
        "Home Videos library path",
        "mb-set-video-root",
        "Mature Settings increment",
    ):
        _check(
            f"html_{marker[:24].replace(' ', '_')}",
            marker in html,
            checks,
            problems,
            "missing" if marker not in html else "ok",
        )

    js = (Path(__file__).resolve().parent / "static" / "settings.js").read_text(encoding="utf-8")
    _check(
        "settings_js_save",
        "POST" in js and "/settings/video-media-root" in js,
        checks,
        problems,
        "save path present" if "POST" in js else "missing POST",
    )

    try:
        from fastapi.testclient import TestClient

        from memorybox.app import app

        client = TestClient(app)
        page = client.get("/settings/ui")
        _check(
            "settings_ui_http",
            page.status_code == 200 and "mb-set-video-root" in page.text,
            checks,
            problems,
            f"status={page.status_code}",
        )
        got = client.get("/settings/video-media-root")
        body = got.json() if got.status_code == 200 else {}
        _check(
            "settings_get_api",
            got.status_code == 200 and body.get("ok") is True and "effective_root" in body,
            checks,
            problems,
            f"status={got.status_code} keys={list(body)[:8]}",
        )
        css = client.get("/static/settings/settings.css")
        _check(
            "settings_css_mount",
            css.status_code == 200,
            checks,
            problems,
            f"status={css.status_code}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("settings_http", False, checks, problems, str(exc))

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems}
