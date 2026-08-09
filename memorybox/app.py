"""FastAPI entry for MemoryBox monolith (Increment 5A: Ask + Story + Journal)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from memorybox import __version__
from memorybox import migrate as migrate_mod
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.config import settings
from memorybox.context import ContextPatch, default_context_store
from memorybox.db import ping
from memorybox.journal import (
    JournalServiceError,
    create_journal,
    get_journal,
    list_journals,
    save_new_version,
)
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.capture import build_capture_stt
from memorybox.story import (
    StoryServiceError,
    associate_evidence,
    associate_person,
    create_story,
    get_story,
    list_stories,
    save_new_version as save_story_version,
)

# Domain tables created by migrations — listed for health/inventory (no provider schemas).
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
    "journal_versions",
    "jobs",
    "processing_states",
)

ASK_STATIC = Path(__file__).resolve().parent / "ask" / "static" / "ask.html"
STORY_STATIC = Path(__file__).resolve().parent / "story" / "static" / "story.html"
JOURNAL_STATIC = Path(__file__).resolve().parent / "journal" / "static" / "journal.html"

app = FastAPI(
    title="MemoryBox",
    version=__version__,
    description="MemoryBox modular monolith (MBBS-001). Increment 5A: Journal + Capture/STT + Ask.",
)

_orchestrator: AskOrchestrator | None = None
_capture_stt = None


def get_orchestrator() -> AskOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AskOrchestrator(store=default_context_store)
    return _orchestrator


def get_capture_stt():
    global _capture_stt
    if _capture_stt is None:
        _capture_stt = build_capture_stt()
    return _capture_stt


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


class StoryCreateRequest(BaseModel):
    title: str | None = None
    body_text: str = Field(..., min_length=1)
    narrator_display_name: str | None = None
    narrator_person_id: str | None = None
    person_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class StoryVersionRequest(BaseModel):
    body_text: str = Field(..., min_length=1)
    title: str | None = None
    note: str | None = None


class JournalCreateRequest(BaseModel):
    title: str | None = None
    body_text: str = Field(..., min_length=1)
    author_display_name: str | None = None
    author_person_id: str | None = None
    channel: str | None = None
    audio_uri: str | None = None
    described_start_date: str | None = None
    described_end_date: str | None = None
    described_precision: str = "unknown"
    person_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class JournalVersionRequest(BaseModel):
    body_text: str = Field(..., min_length=1)
    title: str | None = None
    audio_uri: str | None = None
    described_start_date: str | None = None
    described_end_date: str | None = None
    described_precision: str | None = None
    note: str | None = None


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

    stt_info: dict[str, Any]
    try:
        stt = get_capture_stt()
        h = stt.health()
        stt_info = {
            "provider_key": h.provider_key,
            "ok": h.ok,
            "detail": h.detail,
        }
    except Exception as exc:  # noqa: BLE001
        stt_info = {"ok": False, "error": str(exc)}

    ok = (
        db.get("status") == "ok"
        and migrations.get("status") == "ok"
        and not migrations.get("pending")
        and tables_ok
    )
    return {
        "ok": ok,
        "service": "memorybox",
        "increment": "5A",
        "version": __version__,
        "database": db,
        "migrations": migrations,
        "domain_tables": table_info,
        "capture_stt": stt_info,
        "host": settings.host,
        "port": settings.port,
        "ask": "/ask/ui",
        "story": "/story/ui",
        "journal": "/journal/ui",
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "memorybox",
        "increment": "5A",
        "version": __version__,
        "health": "/health",
        "ask_ui": "/ask/ui",
        "ask": "POST /ask",
        "story_ui": "/story/ui",
        "story": "/story",
        "journal_ui": "/journal/ui",
        "journal": "/journal",
        "capture_transcribe": "POST /capture/transcribe",
    }


@app.get("/ask/ui")
def ask_ui() -> FileResponse:
    if not ASK_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Ask UI missing")
    return FileResponse(ASK_STATIC, media_type="text/html")


@app.get("/story/ui")
def story_ui() -> FileResponse:
    if not STORY_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Story UI missing")
    return FileResponse(STORY_STATIC, media_type="text/html")


@app.get("/journal/ui")
def journal_ui() -> FileResponse:
    if not JOURNAL_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Journal UI missing")
    return FileResponse(JOURNAL_STATIC, media_type="text/html")


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


@app.post("/capture/transcribe")
async def capture_transcribe(file: UploadFile = File(...)) -> dict[str, Any]:
    """Preserve audio + STT draft. Does not create a Journal entry."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio upload")
    stt = get_capture_stt()
    try:
        draft = stt.preserve_and_transcribe(
            data,
            filename=file.filename or "clip.webm",
            content_type=file.content_type,
        )
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"STT unavailable: {exc}. Typed Journal path still works.",
        ) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "draft": draft.to_dict(),
        "persisted_as_journal": False,
        "hint": "Review/edit transcript in /journal/ui, then explicit Save.",
    }


@app.get("/journal")
def journal_list() -> dict[str, Any]:
    return {"ok": True, "journals": list_journals()}


@app.post("/journal")
def journal_create(body: JournalCreateRequest) -> dict[str, Any]:
    try:
        view = create_journal(
            title=body.title,
            body_text=body.body_text,
            author_display_name=body.author_display_name,
            author_person_id=body.author_person_id,
            channel=body.channel,
            audio_uri=body.audio_uri,
            described_start_date=body.described_start_date,
            described_end_date=body.described_end_date,
            described_precision=body.described_precision,
            person_ids=body.person_ids,
            evidence_ids=body.evidence_ids,
            note=body.note,
            actor_key="owner",
        )
    except JournalServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "journal": view.to_dict()}


@app.get("/journal/{journal_id}")
def journal_get(
    journal_id: str, version: int | None = Query(default=None)
) -> dict[str, Any]:
    view = get_journal(journal_id, version=version)
    if not view:
        raise HTTPException(status_code=404, detail="journal not found")
    return {"ok": True, "journal": view.to_dict()}


@app.post("/journal/{journal_id}/versions")
def journal_new_version(journal_id: str, body: JournalVersionRequest) -> dict[str, Any]:
    try:
        view = save_new_version(
            journal_id,
            body_text=body.body_text,
            title=body.title,
            audio_uri=body.audio_uri,
            described_start_date=body.described_start_date,
            described_end_date=body.described_end_date,
            described_precision=body.described_precision,
            note=body.note,
            actor_key="owner",
        )
    except JournalServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "journal": view.to_dict()}


@app.get("/story")
def story_list() -> dict[str, Any]:
    return {"ok": True, "stories": list_stories()}


@app.post("/story")
def story_create(body: StoryCreateRequest) -> dict[str, Any]:
    try:
        view = create_story(
            title=body.title,
            body_text=body.body_text,
            narrator_display_name=body.narrator_display_name,
            narrator_person_id=body.narrator_person_id,
            person_ids=body.person_ids,
            evidence_ids=body.evidence_ids,
            note=body.note,
            actor_key="owner",
        )
    except StoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "story": view.to_dict()}


@app.get("/story/{story_id}")
def story_get(
    story_id: str, version: int | None = Query(default=None)
) -> dict[str, Any]:
    view = get_story(story_id, version=version)
    if not view:
        raise HTTPException(status_code=404, detail="story not found")
    return {"ok": True, "story": view.to_dict()}


@app.post("/story/{story_id}/versions")
def story_new_version(story_id: str, body: StoryVersionRequest) -> dict[str, Any]:
    try:
        view = save_story_version(
            story_id,
            body_text=body.body_text,
            title=body.title,
            note=body.note,
            actor_key="owner",
        )
    except StoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "story": view.to_dict()}


@app.post("/story/{story_id}/persons/{person_id}")
def story_add_person(story_id: str, person_id: str) -> dict[str, Any]:
    try:
        view = associate_person(story_id, person_id)
    except StoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "story": view.to_dict()}


@app.post("/story/{story_id}/evidence/{evidence_id}")
def story_add_evidence(story_id: str, evidence_id: str) -> dict[str, Any]:
    try:
        view = associate_evidence(story_id, evidence_id)
    except StoryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "story": view.to_dict()}
