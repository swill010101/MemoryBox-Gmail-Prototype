"""FastAPI entry for MemoryBox monolith (Increment 4: Ask + health)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from memorybox import __version__
from memorybox import migrate as migrate_mod
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.config import settings
from memorybox.context import ContextPatch, default_context_store
from memorybox.db import ping

# Domain tables created by 001_domain_v0.sql — listed for health/inventory (no provider schemas).
DOMAIN_V0_TABLES = (
    "sources",
    "media_objects",
    "media_refs",
    "evidence",
    "people",
    "provider_identities",
    "assertions",
    "assertion_evidence",
    "relationships",
    "stories",
    "story_versions",
    "journal_entries",
    "jobs",
    "processing_states",
)

ASK_STATIC = Path(__file__).resolve().parent / "ask" / "static" / "ask.html"

app = FastAPI(
    title="MemoryBox",
    version=__version__,
    description="MemoryBox modular monolith (MBBS-001). Increment 4: Evidence-backed Ask.",
)

_orchestrator: AskOrchestrator | None = None


def get_orchestrator() -> AskOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AskOrchestrator(store=default_context_store)
    return _orchestrator


class AskRequest(BaseModel):
    ask: str = Field(..., min_length=1)
    session_id: str | None = None


class ContextChangeRequest(BaseModel):
    person_names: list[str] | None = None
    place_names: list[str] | None = None
    event_labels: list[str] | None = None
    time_start: str | None = None
    time_end: str | None = None
    clear_time: bool = False


@app.get("/health")
def health() -> dict[str, Any]:
    db: dict[str, Any]
    try:
        db = {"status": "ok", **ping()}
    except Exception as exc:  # noqa: BLE001 — surface connection errors in health
        db = {"status": "error", "error": str(exc)}

    migrations: dict[str, Any]
    try:
        applied = migrate_mod.applied_versions()
        pending = migrate_mod.pending()
        migrations = {
            "status": "ok",
            "applied": [
                {
                    "version": r["version"],
                    "filename": r["filename"],
                    "applied_at": r["applied_at"].isoformat()
                    if hasattr(r["applied_at"], "isoformat")
                    else str(r["applied_at"]),
                }
                for r in applied
            ],
            "pending": pending,
        }
    except Exception as exc:  # noqa: BLE001
        migrations = {"status": "error", "error": str(exc)}

    tables_ok = False
    missing: list[str] = []
    if db.get("status") == "ok":
        try:
            from memorybox.db import connection

            with connection() as conn:
                rows = conn.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """
                ).fetchall()
            present = {r["table_name"] for r in rows}
            missing = [t for t in DOMAIN_V0_TABLES if t not in present]
            provider_leaks = sorted(
                n
                for n in present
                if n.startswith("immich") or n.startswith("hvrt_") or n == "face_appearances"
            )
            tables_ok = not missing and not provider_leaks
            table_info = {
                "domain_v0_complete": not missing,
                "missing": missing,
                "provider_schema_leaks": provider_leaks,
            }
        except Exception as exc:  # noqa: BLE001
            table_info = {"error": str(exc)}
            provider_leaks = []
    else:
        table_info = {"skipped": True}
        provider_leaks = []

    ok = (
        db.get("status") == "ok"
        and migrations.get("status") == "ok"
        and not migrations.get("pending")
        and tables_ok
    )
    return {
        "ok": ok,
        "service": "memorybox",
        "increment": 4,
        "version": __version__,
        "database": db,
        "migrations": migrations,
        "domain_tables": table_info,
        "host": settings.host,
        "port": settings.port,
        "ask": "/ask/ui",
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "memorybox",
        "increment": 4,
        "version": __version__,
        "health": "/health",
        "ask_ui": "/ask/ui",
        "ask": "POST /ask",
    }


@app.get("/ask/ui")
def ask_ui() -> FileResponse:
    if not ASK_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Ask UI missing")
    return FileResponse(ASK_STATIC, media_type="text/html")


@app.post("/ask")
def ask_endpoint(body: AskRequest) -> dict[str, Any]:
    result = get_orchestrator().ask(body.ask, session_id=body.session_id)
    return result.to_dict()


@app.get("/ask/context/{session_id}")
def get_context(session_id: str) -> dict[str, Any]:
    ctx = get_orchestrator().get_context(session_id)
    return {"ok": True, "context": ctx.to_dict()}


@app.delete("/ask/context/{session_id}")
def clear_context(session_id: str) -> dict[str, Any]:
    ctx = get_orchestrator().clear_context(session_id)
    return {"ok": True, "context": ctx.to_dict()}


@app.patch("/ask/context/{session_id}")
def change_context(session_id: str, body: ContextChangeRequest) -> dict[str, Any]:
    patch = ContextPatch()
    if body.person_names is not None:
        patch.person_names = tuple(body.person_names)
    if body.place_names is not None:
        patch.place_names = tuple(body.place_names)
    if body.event_labels is not None:
        patch.event_labels = tuple(body.event_labels)
    if body.clear_time:
        patch.time_start = None
        patch.time_end = None
    else:
        if body.time_start is not None:
            patch.time_start = body.time_start
        if body.time_end is not None:
            patch.time_end = body.time_end
    ctx = get_orchestrator().change_context(session_id, patch)
    return {"ok": True, "context": ctx.to_dict()}
