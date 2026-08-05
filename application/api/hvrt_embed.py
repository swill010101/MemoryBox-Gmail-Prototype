"""Embed HVRT review console inside the demonstrator (same origin)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from api import config

ROOT = Path(__file__).resolve().parents[2]
HVRT_ROOT = ROOT / "hvrt"
REVIEW_HTML = HVRT_ROOT / "hvrt" / "static" / "review.html"

_hvrt_mounted = False
_hvrt_error: str | None = None


def hvrt_status() -> dict[str, Any]:
    return {
        "mounted": _hvrt_mounted,
        "error": _hvrt_error,
        "review_embed": "/review-embed",
        "db": str(config.HVRT_DB),
        "db_present": config.HVRT_DB.is_file(),
    }


def mount_hvrt(app: FastAPI) -> bool:
    """Mount HVRT FastAPI app at /hvrt so Review works without a second process."""
    global _hvrt_mounted, _hvrt_error
    if _hvrt_mounted:
        return True
    if not (HVRT_ROOT / "scripts" / "review_app.py").is_file():
        _hvrt_error = f"HVRT package missing at {HVRT_ROOT}"
        return False
    try:
        # Prefer demonstrator-configured DB path
        if config.HVRT_DB.is_file():
            import os
            os.environ.setdefault("HVRT_DB", str(config.HVRT_DB))

        sys.path.insert(0, str(HVRT_ROOT))
        from scripts import review_app as ra  # noqa: WPS433

        # Point HVRT at the real POC database when present
        if config.HVRT_DB.is_file():
            ra.app.state.db_path = config.HVRT_DB
            # gallery next to db: .../hvrt/gallery or repo/hvrt/gallery
            gallery = HVRT_ROOT / "gallery"
            working = HVRT_ROOT / "working"
            sample = HVRT_ROOT / "sample"
            ra.app.state.working_dir = working
            ra.app.state.sample_dir = sample
            ra.app.state.gallery_dirs = [gallery, working / "exemplars" / "people"]
            try:
                from hvrt.learning import LearningManager
                from hvrt.process_jobs import ProcessJobManager
                from hvrt.browser_proxy import BrowserProxyManager
                from hvrt.schema_r2 import init_r2_schema
                from hvrt.annotations import sync_people_from_gallery

                init_r2_schema(config.HVRT_DB)
                ra.app.state.learner = LearningManager(
                    config.HVRT_DB, working, gallery_dirs=ra.app.state.gallery_dirs
                )
                ra.app.state.processor = ProcessJobManager(
                    db_path=config.HVRT_DB, root=HVRT_ROOT, sample_dir=sample
                )
                ra.app.state.proxies = BrowserProxyManager(working)
                gallery.mkdir(parents=True, exist_ok=True)
                sync_people_from_gallery(ra.conn(), ra.app.state.gallery_dirs)
            except Exception as e:  # noqa: BLE001
                # App still mounts; some features may init on first request
                _hvrt_error = f"HVRT partial init: {e}"

        app.mount("/hvrt", ra.app)
        _hvrt_mounted = True
        if not _hvrt_error:
            _hvrt_error = None
        return True
    except Exception as e:  # noqa: BLE001
        _hvrt_error = str(e)
        _hvrt_mounted = False
        return False


def patched_review_html(*, person_id: str | None = None, person_name: str | None = None) -> str:
    """Rewrite absolute /api paths to /hvrt/api so the embed talks to the mounted app."""
    if not REVIEW_HTML.is_file():
        return "<p>HVRT review.html missing</p>"
    html = REVIEW_HTML.read_text(encoding="utf-8")
    # Prefix API calls for embed under demonstrator
    html = html.replace("fetch('/api/", "fetch('/hvrt/api/")
    html = html.replace('fetch("/api/', 'fetch("/hvrt/api/')
    html = html.replace("fetch(`/api/", "fetch(`/hvrt/api/")
    html = html.replace("'/api/", "'/hvrt/api/")
    html = html.replace('"/api/', '"/hvrt/api/')
    html = html.replace("`/api/", "`/hvrt/api/")
    html = html.replace("xhr.open('POST', '/api/", "xhr.open('POST', '/hvrt/api/")
    # Quiet brand line so it sits under MemoryBox chrome
    html = html.replace(
        "build multipart-lifespan",
        "build mbd-review-embed",
    )
    html = html.replace(
        "build face-merge-transcript-c",
        "build mbd-review-embed",
    )
    html = html.replace(
        "build db-busy-load-hits",
        "build mbd-review-embed",
    )
    # Deep-link: select person + load face hits when opened from Ask/People
    boot = ""
    if person_id or person_name:
        pid_js = json_dumps(person_id)
        name_js = json_dumps(person_name)
        boot = f"""
<script>
(function(){{
  const wantId = {pid_js};
  const wantName = {name_js};
  function bootPerson(){{
    const mode = document.getElementById('mode');
    if (mode) {{ mode.value = 'faces'; mode.dispatchEvent(new Event('change')); }}
    const qs = document.getElementById('querySelect');
    if (qs && wantId) {{
      const opt = [...qs.options].find(o => String(o.value) === String(wantId));
      if (opt) qs.value = String(wantId);
    }} else if (qs && wantName) {{
      const opt = [...qs.options].find(o => (o.textContent||'').toLowerCase().includes(String(wantName).toLowerCase()));
      if (opt) qs.value = opt.value;
    }}
    const loadBtn = document.getElementById('loadBtn');
    if (loadBtn) loadBtn.click();
  }}
  window.addEventListener('load', () => setTimeout(bootPerson, 600));
}})();
</script>
"""
    if "</body>" in html:
        html = html.replace("</body>", boot + "</body>")
    else:
        html += boot
    return html


def json_dumps(v: Any) -> str:
    import json
    return json.dumps(v)
