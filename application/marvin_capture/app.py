"""Marvin Capture review UI + worker endpoints.

  python scripts/run_marvin_capture.py
  http://127.0.0.1:8790
"""
from __future__ import annotations

import logging
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.mem_bank import (  # noqa: E402
    ensure_questions_file,
    export_mem_bank,
    open_questions_file_in_editor,
    tick_mem_bank,
)
from marvin_capture.service import (  # noqa: E402
    get_gmail_client,
    poll_once,
    reextract_all_responses,
    send_daily_journal_if_due,
    send_prompt,
)
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402

log = logging.getLogger("marvin.app")

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Marvin Capture", version="0.1.1")
_cfg = cfgmod.ensure_runtime_dirs()
_db = store.init_db(_cfg["sqlite_path"])
# Refresh derived reply text from preserved raw mail (soft-wrap / signature cleanup)
try:
    n = reextract_all_responses(_db)
    _db.commit()
    if n:
        log.info("reextracted %s response(s) from raw email", n)
except Exception:  # noqa: BLE001
    log.exception("startup reextract skipped")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SendPromptIn(BaseModel):
    prompt_type: str = "MEM"
    token: str = ""
    headline: str = ""
    body: str
    to: str | None = None


class ReviewIn(BaseModel):
    reviewed: bool = True


class EvsExtractIn(BaseModel):
    filename: str = Field(default="evs_export.txt", min_length=1, max_length=180)


def _safe_download_name(name: str) -> str:
    name = Path(name).name.strip() or "evs_export.txt"
    name = re.sub(r"[^\w.\- ()[\]]+", "_", name)
    if not name.lower().endswith(".txt"):
        name += ".txt"
    return name[:180]


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "marvin-capture",
        "version": "0.1.1",
        "sqlite": _cfg["sqlite_path"],
        "attachment_storage": _cfg["attachment_storage"],
        "whisper_endpoint": _cfg["whisper"].get("endpoint"),
        "principle": "never lose information in an attempt to be intelligent",
        "subject_keys": ["[MB-JRN]", "[MB-MEM]", "[MB-EVS]"],
    }


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    return {
        "polling_interval_seconds": _cfg["polling_interval_seconds"],
        "processed_label": _cfg["gmail"].get("processed_label"),
        "whisper_endpoint": _cfg["whisper"].get("endpoint"),
        "schedule": _cfg.get("schedule"),
        "user_email_set": bool(_cfg["gmail"].get("user_email")),
        "subject_keys": {
            "JRN": "[MB-JRN] optional headline",
            "MEM": "[MB-MEM] optional headline",
            "EVS": "[MB-EVS] optional headline",
        },
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
        token=body.token or "",
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


@app.post("/api/evs/extract")
def api_evs_extract(body: EvsExtractIn) -> Response:
    items = store.list_responses_by_type(_db, "EVS")
    text = store.format_evs_export(items)
    filename = _safe_download_name(body.filename)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
        },
    )


@app.post("/api/evs/remove")
def api_evs_remove() -> dict[str, Any]:
    result = store.delete_responses_by_type(_db, "EVS")
    _db.commit()
    return {"ok": True, **result}


@app.post("/api/mem/extract")
def api_mem_extract() -> dict[str, Any]:
    result = export_mem_bank(_db, _cfg)
    return {"ok": True, **result}


@app.post("/api/mem/tick")
def api_mem_tick(force: bool = True, fake: bool = False) -> dict[str, Any]:
    """Manual / test trigger for the MEM bank scheduler."""
    if fake:
        _cfg["use_fake_gmail"] = True
    client = get_gmail_client(_cfg, fake=fake or bool(_cfg.get("use_fake_gmail")))
    result = tick_mem_bank(_db, client, _cfg, force=force)
    _db.commit()
    return {"ok": True, **result}


@app.get("/api/mem/status")
def api_mem_status() -> dict[str, Any]:
    bank = _cfg.get("mem_bank") or {}
    state = store.get_mem_bank_state(_db)
    qpath = bank.get("questions_file")
    return {
        "enabled": bool(bank.get("enabled")),
        "questions_file": qpath,
        "questions_file_exists": bool(qpath and Path(qpath).is_file()),
        "hour": bank.get("hour"),
        "minute": bank.get("minute"),
        "state": state,
        "id_rule": "Questions must be numbered contiguously 1..N",
    }


@app.post("/api/mem/questions/open")
def api_mem_questions_open() -> dict[str, Any]:
    """Open config/mem_questions.json in the desktop default editor."""
    bank = _cfg.get("mem_bank") or {}
    qpath = bank.get("questions_file")
    if not qpath:
        raise HTTPException(400, "mem_bank.questions_file is not configured")
    example = str(ROOT / "config" / "mem_questions.example.json")
    path = ensure_questions_file(qpath, example=example)
    try:
        opened = open_questions_file_in_editor(path)
    except OSError as exc:
        raise HTTPException(500, f"could not open editor: {exc}") from exc
    return {
        "ok": True,
        "path": opened,
        "hint": "Number questions contiguously as id 1..N. Save the file, then restart is not required — next tick reloads JSON.",
    }


@app.post("/api/reextract")
def api_reextract() -> dict[str, Any]:
    n = reextract_all_responses(_db)
    _db.commit()
    return {"ok": True, "updated": n}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "review.html"
    if not index_path.is_file():
        return HTMLResponse("<h1>Marvin Capture</h1><p>static/review.html missing</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
