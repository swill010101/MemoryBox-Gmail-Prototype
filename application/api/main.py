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
from api import evidence as ev  # noqa: E402

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
    sources = ev.source_status()
    return {
        "ok": True,
        "service": "mbd-001",
        "hvrt_origin": config.HVRT_ORIGIN,
        "ask_origin": config.ASK_ORIGIN or None,
        "demonstrator_db": str(config.DEMONSTRATOR_DB),
        "sources": sources,
        "archive_updated": True,
        "edit_memory": "text_versions",
    }


@app.get("/api/config")
def client_config() -> dict[str, Any]:
    sources = ev.source_status()
    return {
        "hvrt_origin": config.HVRT_ORIGIN,
        "ask_proxy": bool(config.ASK_ORIGIN),
        "brand": "MemoryBox",
        "build": "mbd-001-poc-ask-v2",
        "sources": sources,
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
    """Ask across HVRT + memorybox POC DBs, Immich, versioned memories; optional Ask proxy."""
    q = body.question.strip()
    sources = ev.source_status()

    poc = ev.search_all(q, limit=36)
    local = mem.search_memories(_db, q, limit=12)
    local_ev = [
        {
            "type": "memory",
            "id": m["id"],
            "title": m.get("title") or m["kind"],
            "snippet": (m.get("body_text") or "")[:280],
            "version": m.get("current_version"),
            "updated_at": m.get("updated_at"),
            "kind": m.get("kind"),
            "modality": "memory",
            "source": "mbd_demonstrator",
        }
        for m in local
    ]
    evidence = poc + local_ev

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
            "sources": sources,
            "upstream": True,
        }

    answer = ev.compose_answer(q, evidence, sources)
    if remote and remote.get("error"):
        answer += f"\n\n(Ask upstream: {remote.get('error')})"

    return {
        "question": q,
        "answer": answer,
        "evidence": evidence,
        "sources": sources,
        "upstream": False,
        "upstream_status": remote,
    }


@app.get("/api/library")
def api_library(q: str | None = None) -> dict[str, Any]:
    """Browseable timeline across POC DBs + versioned memories."""
    sources = ev.source_status()
    timeline: list[dict[str, Any]] = []

    if q and q.strip():
        for e in ev.search_all(q.strip(), limit=50):
            timeline.append({
                "id": f"{e.get('type')}:{e.get('id')}",
                "modality": e.get("modality") or e.get("type"),
                "title": e.get("title"),
                "snippet": e.get("snippet"),
                "when": e.get("when"),
                "source": e.get("source"),
                "memory_id": e.get("id") if e.get("type") == "memory" else None,
                "raw": e,
            })
        for m in mem.search_memories(_db, q.strip(), limit=30):
            timeline.append({
                "id": f"memory:{m['id']}",
                "modality": m["kind"],
                "title": m.get("title") or m["kind"],
                "snippet": (m.get("body_text") or "")[:220],
                "when": m.get("updated_at") or m.get("created_at"),
                "version": m.get("current_version"),
                "memory_id": m["id"],
                "source": "mbd_demonstrator",
            })
    else:
        for m in mem.list_memories(_db, limit=40):
            timeline.append({
                "id": f"memory:{m['id']}",
                "modality": m["kind"],
                "title": m.get("title") or m["kind"],
                "snippet": (m.get("body_text") or "")[:220],
                "when": m.get("updated_at") or m.get("created_at"),
                "version": m.get("current_version"),
                "memory_id": m["id"],
                "source": "mbd_demonstrator",
            })
        for e in ev.list_hvrt_people(limit=40):
            timeline.append({
                "id": f"hvrt_person:{e['id']}",
                "modality": "video_face",
                "title": e["title"],
                "snippet": e.get("snippet"),
                "source": e.get("source"),
                "raw": e,
            })

    return {
        "count": len(timeline),
        "items": timeline,
        "sources": sources,
        "note": "Searches memorybox.db + hvrt.sqlite (+ Immich when configured).",
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
