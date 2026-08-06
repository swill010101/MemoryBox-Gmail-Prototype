"""Marvin Capture review UI + worker endpoints.

  python scripts/run_marvin_capture.py
  http://127.0.0.1:8790
"""
from __future__ import annotations

import logging
import mimetypes
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.service import get_gmail_client, poll_once, send_daily_journal_if_due, send_prompt  # noqa: E402
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402

log = logging.getLogger("marvin.app")

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Marvin Capture", version="0.1.0")
_cfg = cfgmod.ensure_runtime_dirs()
_db = store.init_db(_cfg["sqlite_path"])

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SendPromptIn(BaseModel):
    prompt_type: str = "MEM"
    token: str
    headline: str
    body: str
    to: str | None = None


class ReviewIn(BaseModel):
    reviewed: bool = True


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "marvin-capture",
        "version": "0.1.0",
        "sqlite": _cfg["sqlite_path"],
        "attachment_storage": _cfg["attachment_storage"],
        "whisper_endpoint": _cfg["whisper"].get("endpoint"),
        "principle": "never lose information in an attempt to be intelligent",
    }


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    return {
        "polling_interval_seconds": _cfg["polling_interval_seconds"],
        "processed_label": _cfg["gmail"].get("processed_label"),
        "whisper_endpoint": _cfg["whisper"].get("endpoint"),
        "schedule": _cfg.get("schedule"),
        "user_email_set": bool(_cfg["gmail"].get("user_email")),
    }


@app.get("/api/responses")
def api_list_responses(
    reviewed: bool | None = Query(default=None),
) -> dict[str, Any]:
    items = store.list_responses(_db, reviewed=reviewed)
    return {"count": len(items), "responses": items}


@app.get("/api/responses/{response_id}")
def api_get_response(response_id: int) -> dict[str, Any]:
    detail = store.get_response_detail(_db, response_id)
    if not detail:
        raise HTTPException(404, "response not found")
    return detail


@app.post("/api/responses/{response_id}/review")
def api_review(response_id: int, body: ReviewIn) -> dict[str, Any]:
    detail = store.mark_reviewed(_db, response_id, reviewed=body.reviewed)
    _db.commit()
    if not detail:
        raise HTTPException(404, "response not found")
    return {"ok": True, "response": detail}


@app.get("/api/attachments/{attachment_id}/file")
def api_attachment_file(attachment_id: int) -> FileResponse:
    row = _db.execute("SELECT * FROM attachment WHERE id = ?", (attachment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "attachment not found")
    path = Path(row["storage_path"])
    if not path.is_file():
        raise HTTPException(404, "file missing on disk")
    media = row["mime_type"] or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, filename=row["filename"])


@app.post("/api/poll")
def api_poll(fake: bool = False) -> dict[str, Any]:
    if fake:
        _cfg["use_fake_gmail"] = True
    client = get_gmail_client(_cfg, fake=fake or bool(_cfg.get("use_fake_gmail")))
    results = poll_once(_db, client, _cfg)
    tx = process_pending_transcriptions(_db, _cfg["whisper"])
    _db.commit()
    return {"ok": True, "processed": results, "transcriptions": tx}


@app.post("/api/transcribe")
def api_transcribe() -> dict[str, Any]:
    tx = process_pending_transcriptions(_db, _cfg["whisper"])
    _db.commit()
    return {"ok": True, "transcriptions": tx}


@app.post("/api/send")
def api_send(body: SendPromptIn, fake: bool = False) -> dict[str, Any]:
    if fake:
        _cfg["use_fake_gmail"] = True
    client = get_gmail_client(_cfg, fake=fake or bool(_cfg.get("use_fake_gmail")))
    result = send_prompt(
        _db,
        client,
        _cfg,
        prompt_type=body.prompt_type,
        token=body.token,
        headline=body.headline,
        body=body.body,
        to=body.to,
    )
    _db.commit()
    return {"ok": True, **result}


@app.post("/api/send-journal")
def api_send_journal(force: bool = True, fake: bool = False) -> dict[str, Any]:
    if fake:
        _cfg["use_fake_gmail"] = True
    client = get_gmail_client(_cfg, fake=fake or bool(_cfg.get("use_fake_gmail")))
    result = send_daily_journal_if_due(_db, client, _cfg, force=force)
    _db.commit()
    return {"ok": True, "sent": result}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "review.html"
    if not index_path.is_file():
        return HTMLResponse("<h1>Marvin Capture</h1><p>static/review.html missing</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
