"""
MBD-001 MemoryBox Demonstrator — curator shell gateway.

  python scripts/run_demonstrator.py
  http://127.0.0.1:8780
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "application"))

from api import config  # noqa: E402
from api import memories as mem  # noqa: E402

app = FastAPI(title="MemoryBox Demonstrator", version="0.1.0")
_db = mem.init_db(config.DEMONSTRATOR_DB)


class MemoryCreateIn(BaseModel):
    kind: str = "voice_note"
    body_text: str = Field(..., min_length=1)
    title: str | None = None
    asset_ref: str | None = None


class MemoryEditIn(BaseModel):
    body_text: str = Field(..., min_length=1)
    title: str | None = None
    note: str | None = None


class AskIn(BaseModel):
    question: str = Field(..., min_length=1)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "mbd-001",
        "hvrt_origin": config.HVRT_ORIGIN,
        "ask_origin": config.ASK_ORIGIN or None,
        "demonstrator_db": str(config.DEMONSTRATOR_DB),
        "archive_updated": True,
        "edit_memory": "text_versions",
    }


@app.get("/api/config")
def client_config() -> dict[str, Any]:
    return {
        "hvrt_origin": config.HVRT_ORIGIN,
        "ask_proxy": bool(config.ASK_ORIGIN),
        "brand": "MemoryBox",
        "build": "mbd-001-shell-v1",
    }


@app.get("/api/memories")
def api_list_memories(q: str | None = None) -> dict[str, Any]:
    items = mem.search_memories(_db, q or "") if q else mem.list_memories(_db)
    return {"count": len(items), "memories": items}


@app.post("/api/memories")
def api_create_memory(body: MemoryCreateIn) -> dict[str, Any]:
    try:
        item = mem.create_memory(
            _db,
            kind=body.kind,
            body_text=body.body_text,
            title=body.title,
            asset_ref=body.asset_ref,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "archive_updated": True, "memory": item}


@app.get("/api/memories/{memory_id}")
def api_get_memory(memory_id: int) -> dict[str, Any]:
    item = mem.get_memory(_db, memory_id)
    if not item:
        raise HTTPException(404, "memory not found")
    return item


@app.get("/api/memories/{memory_id}/versions/{version}")
def api_get_version(memory_id: int, version: int) -> dict[str, Any]:
    item = mem.get_version(_db, memory_id, version)
    if not item:
        raise HTTPException(404, "version not found")
    return item


@app.post("/api/memories/{memory_id}/edit")
def api_edit_memory(memory_id: int, body: MemoryEditIn) -> dict[str, Any]:
    """Edit Memory — new version from text; prior retained; latest searchable."""
    try:
        item = mem.edit_memory_text(
            _db,
            memory_id,
            body.body_text,
            note=body.note,
            title=body.title,
        )
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "archive_updated": True, "memory": item}


@app.post("/api/ask")
async def api_ask(body: AskIn) -> dict[str, Any]:
    """Ask: proxy historian when configured; always include local memory hits."""
    q = body.question.strip()
    local = mem.search_memories(_db, q, limit=12)
    evidence = [
        {
            "type": "memory",
            "id": m["id"],
            "title": m.get("title") or m["kind"],
            "snippet": (m.get("body_text") or "")[:280],
            "version": m.get("current_version"),
            "updated_at": m.get("updated_at"),
            "kind": m.get("kind"),
        }
        for m in local
    ]

    remote: dict[str, Any] | None = None
    if config.ASK_ORIGIN:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    f"{config.ASK_ORIGIN}/api/ask",
                    json={"question": q},
                )
                if r.status_code < 400:
                    remote = r.json()
                else:
                    remote = {"error": f"Ask upstream {r.status_code}", "detail": r.text[:300]}
        except httpx.HTTPError as e:
            remote = {"error": "Ask upstream unreachable", "detail": str(e)}

    if remote and not remote.get("error"):
        answer = remote.get("answer") or remote.get("narrative") or remote.get("text")
        up_ev = remote.get("evidence") or remote.get("sources") or []
        return {
            "question": q,
            "answer": answer,
            "evidence": list(up_ev) + evidence,
            "local_memories": evidence,
            "upstream": True,
            "archive_note": "Local versioned memories appended when they match.",
        }

    # Local-only narrative for demonstrator until Ask tree is imported
    if evidence:
        lines = [f"I found {len(evidence)} memory(ies) in your archive that relate to that:"]
        for e in evidence[:5]:
            lines.append(f"• {e['title']} (v{e['version']}): {e['snippet'][:120]}")
        answer = "\n".join(lines)
    else:
        answer = (
            "No matching memories in the demonstrator archive yet. "
            "Teach a voice note or artifact label, or connect the email/text Ask service "
            f"({config.ASK_ORIGIN or 'set MBD_ASK_ORIGIN'})."
        )
        if remote and remote.get("error"):
            answer += f"\n\n(Ask upstream: {remote.get('error')})"

    return {
        "question": q,
        "answer": answer,
        "evidence": evidence,
        "local_memories": evidence,
        "upstream": False,
        "upstream_status": remote,
    }


@app.get("/api/library")
def api_library(q: str | None = None) -> dict[str, Any]:
    """Browseable timeline/library — local memories first; email/SMS when Ask imported."""
    items = mem.search_memories(_db, q or "") if q else mem.list_memories(_db)
    timeline = [
        {
            "id": f"memory:{m['id']}",
            "modality": m["kind"],
            "title": m.get("title") or m["kind"],
            "snippet": (m.get("body_text") or "")[:220],
            "when": m.get("updated_at") or m.get("created_at"),
            "version": m.get("current_version"),
            "memory_id": m["id"],
        }
        for m in items
    ]
    return {
        "count": len(timeline),
        "items": timeline,
        "note": "Email/SMS/Immich rows join here once Ask POC is imported and proxied.",
    }


if config.UI_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(config.UI_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    path = config.UI_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(404, "UI missing")
    return FileResponse(
        path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        },
    )
