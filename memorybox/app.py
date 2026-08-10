"""FastAPI entry for MemoryBox monolith (Increment 8: Library + Video/Review/Ask/Story/Journal/People)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from memorybox import __version__
from memorybox import migrate as migrate_mod
from memorybox.ask.deps import build_photo, build_video
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
from memorybox.library import LibraryServiceError, get_library_card, list_library_cards
from memorybox.person import (
    PersonServiceError,
    bulk_confirm_provider_identities,
    get_person,
    list_people,
    map_provider_identity,
    merge_people,
    reject_mapping,
    rename_person,
    teach_provider_person,
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
    "identity_negatives",
    "person_merges",
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
PEOPLE_STATIC = Path(__file__).resolve().parent / "person" / "static" / "people.html"
REVIEW_STATIC = Path(__file__).resolve().parent / "review" / "static" / "review.html"
LIBRARY_STATIC = Path(__file__).resolve().parent / "library" / "static" / "library.html"

app = FastAPI(
    title="MemoryBox",
    version=__version__,
    description="MemoryBox modular monolith (MBBS-001). Increment 8: Library / Timeline.",
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


class TeachRequest(BaseModel):
    display_name: str = Field(..., min_length=2)
    provider_key: str = "immich"
    external_id: str = Field(..., min_length=1)
    label: str | None = None


class BulkTeachRequest(BaseModel):
    display_name: str = Field(..., min_length=2)
    provider_key: str = "immich"
    external_ids: list[str] = Field(default_factory=list)


class RejectRequest(BaseModel):
    person_id: str
    provider_key: str = "immich"
    external_id: str
    note: str | None = None


class MergeRequest(BaseModel):
    survivor_person_id: str
    loser_person_id: str
    note: str | None = None


class RenameRequest(BaseModel):
    display_name: str = Field(..., min_length=2)


class ReviewFaceRequest(BaseModel):
    video_external_id: str = Field(..., min_length=1)
    t_sec: float = 0.0
    label: str | None = None
    bbox: dict[str, Any] | None = None


class ReviewFaceBoxRequest(BaseModel):
    bbox: dict[str, Any]
    label: str | None = None
    crop_jpeg_base64: str | None = None


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
        "increment": 8,
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
        "people": "/people/ui",
        "review": "/review/ui",
        "library": "/library/ui",
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "memorybox",
        "increment": 8,
        "version": __version__,
        "health": "/health",
        "ask_ui": "/ask/ui",
        "ask": "POST /ask",
        "story_ui": "/story/ui",
        "story": "/story",
        "journal_ui": "/journal/ui",
        "journal": "/journal",
        "people_ui": "/people/ui",
        "people": "/people",
        "review_ui": "/review/ui",
        "library_ui": "/library/ui",
        "library_cards": "GET /library/cards",
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


@app.get("/people/ui")
def people_ui() -> FileResponse:
    if not PEOPLE_STATIC.is_file():
        raise HTTPException(status_code=404, detail="People UI missing")
    return FileResponse(PEOPLE_STATIC, media_type="text/html")


@app.get("/review/ui")
def review_ui() -> FileResponse:
    if not REVIEW_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Review UI missing")
    return FileResponse(REVIEW_STATIC, media_type="text/html")


@app.get("/library/ui")
def library_ui() -> FileResponse:
    if not LIBRARY_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Library UI missing")
    return FileResponse(LIBRARY_STATIC, media_type="text/html")


@app.get("/library/cards")
def library_cards(
    person_id: str = Query(..., min_length=1),
    bucket: str = Query("timeline"),
    modalities: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(24, ge=1, le=50),
) -> dict[str, Any]:
    """Unified Library read API — Person filter required; Timeline/Gallery same cards."""
    mods = None
    if modalities:
        mods = [m.strip() for m in modalities.split(",") if m.strip()]
    try:
        return list_library_cards(
            person_id=person_id,
            modalities=mods,
            bucket=bucket,
            date_from=date_from,
            date_to=date_to,
            cursor=cursor,
            limit=limit,
            photo=build_photo(),
            video=build_video(),
        )
    except LibraryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/library/cards/{card_id:path}")
def library_card_detail(
    card_id: str,
    person_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    try:
        card = get_library_card(
            card_id,
            person_id=person_id,
            photo=build_photo(),
            video=build_video(),
        )
    except LibraryServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    return {"ok": True, "card": card.to_dict()}


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
    """Preserve audio + STT draft. Does not create a Journal entry.

    Audio is always preserved first. If STT fails, returns 422 with audio handle
    so the owner can type a body and still Save a voice Journal.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio upload")
    stt = get_capture_stt()
    filename = file.filename or "clip.webm"
    try:
        handle = stt.preserve_audio(
            data, filename=filename, content_type=file.content_type
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        draft = stt.transcribe(handle.audio_id)
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"STT unavailable: {exc}. Typed Journal path still works.",
                "audio": handle.to_dict(),
                "persisted_as_journal": False,
            },
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "audio": handle.to_dict(),
                "persisted_as_journal": False,
                "hint": "Audio preserved. Type/edit Body, then Save Journal (channel=voice).",
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "audio": handle.to_dict(),
                "persisted_as_journal": False,
            },
        ) from exc
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


@app.get("/people")
def people_list(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    return {"ok": True, "people": list_people(limit=limit)}


@app.get("/people/provider/immich")
def people_immich_list() -> dict[str, Any]:
    photo = build_photo()
    status: dict[str, Any]
    try:
        h = photo.health()
        status = {
            "provider_key": h.provider_key,
            "ok": h.ok,
            "detail": h.detail,
        }
        if not h.ok:
            return {
                "ok": False,
                "people": [],
                "provider_status": status,
                "unavailable": True,
            }
        refs = photo.list_people(limit=200)
        return {
            "ok": True,
            "people": [
                {
                    "provider_key": r.provider_key,
                    "external_id": r.external_id,
                    "display_name": r.display_name,
                }
                for r in refs
            ],
            "provider_status": status,
        }
    except ProviderUnavailable as exc:
        return {
            "ok": False,
            "people": [],
            "unavailable": True,
            "provider_status": {"ok": False, "detail": str(exc)},
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/people/{person_id}")
def people_get(person_id: str) -> dict[str, Any]:
    view = get_person(person_id)
    if not view:
        raise HTTPException(status_code=404, detail="person not found")
    return {"ok": True, "person": view.to_dict()}


@app.post("/people/teach")
def people_teach(body: TeachRequest) -> dict[str, Any]:
    """I7 Review / I6 People teach — lazy Immich bootstrap via shared Person service."""
    try:
        from memorybox.ask.deps import build_photo
        from memorybox.person import AmbiguousIdentityError

        view = teach_provider_person(
            display_name=body.display_name,
            provider_key=body.provider_key,
            external_id=body.external_id,
            label=body.label,
            photo=build_photo(),
        )
    except AmbiguousIdentityError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "ambiguous_identity",
                "message": str(exc),
                "resolution": "owner_required",
            },
        ) from exc
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "person": view.to_dict(),
        "archive_updated": True,
        "identity_authority": view.identity_authority,
    }


@app.post("/people/bulk-teach")
def people_bulk_teach(body: BulkTeachRequest) -> dict[str, Any]:
    try:
        view = bulk_confirm_provider_identities(
            display_name=body.display_name,
            provider_key=body.provider_key,
            external_ids=body.external_ids,
        )
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "person": view.to_dict(), "archive_updated": True}


@app.post("/people/reject")
def people_reject(body: RejectRequest) -> dict[str, Any]:
    try:
        result = reject_mapping(
            person_id=body.person_id,
            provider_key=body.provider_key,
            external_id=body.external_id,
            note=body.note,
        )
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/people/merge")
def people_merge(body: MergeRequest) -> dict[str, Any]:
    try:
        view = merge_people(
            survivor_person_id=body.survivor_person_id,
            loser_person_id=body.loser_person_id,
            note=body.note,
        )
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "person": view.to_dict(), "archive_updated": True}


@app.post("/people/{person_id}/name")
def people_rename(person_id: str, body: RenameRequest) -> dict[str, Any]:
    try:
        view = rename_person(person_id, body.display_name)
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "person": view.to_dict()}


@app.post("/people/{person_id}/map")
def people_map(person_id: str, body: TeachRequest) -> dict[str, Any]:
    try:
        view = map_provider_identity(
            person_id=person_id,
            provider_key=body.provider_key,
            external_id=body.external_id,
            label=body.label or body.display_name,
        )
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "person": view.to_dict(), "archive_updated": True}

@app.get("/review/videos")
def review_videos() -> dict[str, Any]:
    video = build_video()
    try:
        h = video.health()
        status = {"provider_key": h.provider_key, "ok": h.ok, "detail": h.detail}
        if not h.ok:
            return {"ok": False, "videos": [], "provider_status": status, "unavailable": True}
        vids = video.list_videos(limit=200)
        return {
            "ok": True,
            "videos": [
                {
                    "provider_key": v.provider_key,
                    "external_id": v.external_id,
                    "title": v.title,
                    "path_hint": v.path_hint,
                    "duration_sec": v.duration_sec,
                }
                for v in vids
            ],
            "provider_status": status,
        }
    except ProviderUnavailable as exc:
        return {
            "ok": False,
            "videos": [],
            "unavailable": True,
            "provider_status": {"ok": False, "detail": str(exc)},
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/review/faces")
def review_faces(video_external_id: str | None = None) -> dict[str, Any]:
    video = build_video()
    try:
        faces = video.list_face_candidates(video_external_id=video_external_id, limit=200)
        # Enrich from worker when available (bbox/boxed)
        enriched = []
        for f in faces:
            row = {
                "provider_key": f.provider_key,
                "external_id": f.external_id,
                "label": f.label,
                "video_external_id": f.video_external_id,
                "boxed": False,
            }
            enriched.append(row)
        worker_faces = _worker_list_faces(video_external_id)
        by_id = {r["external_id"]: r for r in worker_faces}
        for row in enriched:
            w = by_id.get(row["external_id"])
            if w:
                row["boxed"] = bool(w.get("boxed") or w.get("bbox"))
                row["bbox"] = w.get("bbox")
        # Include worker-only faces not yet on provider list
        seen = {r["external_id"] for r in enriched}
        for w in worker_faces:
            if w["external_id"] in seen:
                continue
            enriched.append(
                {
                    "provider_key": "hvrt",
                    "external_id": w["external_id"],
                    "label": w.get("label"),
                    "video_external_id": w.get("video_external_id"),
                    "boxed": bool(w.get("boxed") or w.get("bbox")),
                    "bbox": w.get("bbox"),
                }
            )
        return {
            "ok": True,
            "faces": enriched,
            "provider_key": getattr(video, "provider_key", None),
        }
    except ProviderUnavailable as exc:
        return {"ok": False, "faces": [], "unavailable": True, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/review/faces")
def review_create_face(body: ReviewFaceRequest) -> dict[str, Any]:
    video = build_video()
    create = getattr(video, "create_face_candidate", None)
    if not callable(create):
        raise HTTPException(
            status_code=400,
            detail="video provider cannot create face candidates",
        )
    try:
        face = create(
            video_external_id=body.video_external_id,
            t_sec=body.t_sec,
            label=body.label,
        )
        # If HTTP worker, also PATCH bbox when provided via worker URL
        if body.bbox is not None:
            patch = _worker_patch_face(
                face.external_id,
                bbox=body.bbox,
                label=body.label,
            )
            if patch.get("face"):
                return {
                    "ok": True,
                    "face": patch["face"],
                    "archive_note": "derived_only",
                    "needs_box": not bool(patch["face"].get("boxed")),
                }
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "face": {
            "provider_key": face.provider_key,
            "external_id": face.external_id,
            "label": face.label,
            "video_external_id": face.video_external_id,
            "boxed": False,
        },
        "archive_note": "derived_only",
        "needs_box": True,
    }


@app.patch("/review/faces/{face_external_id}")
def review_box_face(face_external_id: str, body: ReviewFaceBoxRequest) -> dict[str, Any]:
    """Save rubber-band face box onto a derived face candidate (POC-style)."""
    result = _worker_patch_face(
        face_external_id,
        bbox=body.bbox,
        label=body.label,
        crop_jpeg_base64=body.crop_jpeg_base64,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=400, detail=result.get("detail") or "box save failed"
        )
    return result


def _worker_list_faces(video_external_id: str | None) -> list[dict[str, Any]]:
    import json
    import os
    import urllib.parse
    import urllib.request

    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if not base:
        return []
    q = "limit=200"
    if video_external_id:
        q += f"&video_external_id={urllib.parse.quote(video_external_id)}"
    try:
        with urllib.request.urlopen(f"{base}/faces?{q}", timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return list(data.get("faces") or [])
    except Exception:  # noqa: BLE001
        return []


def _worker_patch_face(
    face_external_id: str,
    *,
    bbox: dict[str, Any] | None = None,
    label: str | None = None,
    crop_jpeg_base64: str | None = None,
) -> dict[str, Any]:
    import json
    import os
    import urllib.error
    import urllib.request

    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if not base:
        # Fake provider path: stash bbox in-process is not durable; report needs worker
        return {
            "ok": True,
            "face": {
                "external_id": face_external_id,
                "bbox": bbox,
                "boxed": bool(bbox),
                "label": label,
            },
            "detail": "bbox accepted (no worker URL — not persisted to derived store)",
        }
    payload: dict[str, Any] = {}
    if bbox is not None:
        payload["bbox"] = bbox
    if label is not None:
        payload["label"] = label
    if crop_jpeg_base64:
        payload["crop_jpeg_base64"] = crop_jpeg_base64
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/faces/{face_external_id}",
        data=raw,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "detail": f"HTTP {exc.code}: {detail}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)}


@app.post("/review/videos/{video_external_id}/browser-proxy")
def review_start_browser_proxy(video_external_id: str) -> dict[str, Any]:
    """Transcode source → H.264/AAC (HVRT POC fix for HEVC blank frames)."""
    return _worker_browser_proxy(video_external_id, method="POST")


@app.get("/review/videos/{video_external_id}/browser-proxy")
def review_browser_proxy_status(video_external_id: str) -> dict[str, Any]:
    return _worker_browser_proxy(video_external_id, method="GET")


def _worker_browser_proxy(video_external_id: str, *, method: str) -> dict[str, Any]:
    import json
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="MEMORYBOX_VIDEO_WORKER_URL required for browser-playable proxy",
        )
    url = f"{base}/videos/{urllib.parse.quote(video_external_id)}/browser-proxy"
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/review/media/{video_external_id}")
def review_media(
    video_external_id: str,
    request: Request,
    proxy: int = Query(0),
) -> Response:
    """Proxy read-only media from sibling worker with Range support for scrubbing."""
    import os
    import urllib.error
    import urllib.request

    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=404,
            detail="media proxy requires MEMORYBOX_VIDEO_WORKER_URL",
        )
    url = f"{base}/media/{video_external_id}"
    if int(proxy) == 1:
        url += "?proxy=1"
    headers: dict[str, str] = {}
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code == 416:
            raise HTTPException(status_code=416, detail="Invalid range") from exc
        raise HTTPException(
            status_code=502, detail=f"media proxy failed: {exc.code}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"media proxy failed: {exc}") from exc

    status = getattr(resp, "status", 200) or 200
    ctype = resp.headers.get("Content-Type") or "video/mp4"
    out_headers: dict[str, str] = {
        "Accept-Ranges": resp.headers.get("Accept-Ranges") or "bytes",
    }
    if resp.headers.get("Content-Range"):
        out_headers["Content-Range"] = resp.headers["Content-Range"]
    if resp.headers.get("Content-Length"):
        out_headers["Content-Length"] = resp.headers["Content-Length"]

    def _iter():
        try:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()

    return StreamingResponse(
        _iter(),
        status_code=status,
        media_type=ctype,
        headers=out_headers,
    )
