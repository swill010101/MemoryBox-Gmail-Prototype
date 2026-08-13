"""FastAPI entry for MemoryBox monolith (Increment 12: MV Export)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from html import escape as html_escape

from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from memorybox import __version__
from memorybox import migrate as migrate_mod
from memorybox.shell.inject import inject_shell, read_and_inject
from memorybox.artifact import (
    ARTIFACT_KINDS,
    ArtifactServiceError,
    add_evidence_ref_representation,
    add_mb_managed_representation,
    associate_person as artifact_associate_person,
    associate_person_from_provider as artifact_associate_person_from_provider,
    associate_story as artifact_associate_story,
    create_artifact,
    create_story_for_artifact,
    get_artifact,
    list_artifacts,
    read_representation_bytes,
    revise_metadata,
)
from memorybox.ask.deps import build_photo, build_video
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.config import settings
from memorybox.context import ContextPatch, default_context_store
from memorybox.db import ping
from memorybox.export import ExportError, get_export_job, resolve_export_parent, start_export_job
from memorybox.status import build_status_summary
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
    "artifacts",
    "artifact_metadata_revisions",
    "artifact_representations",

    "person_aliases",
    "person_facts",
    "person_contact_points",
    "person_relationship_assertions",
    "shared_life_events",
    "shared_life_event_participants",
    "memorybox_runtime_settings",
    "guided_capture_contacts",
    "guided_capture_campaigns",
    "guided_capture_questions",
    "guided_capture_deliveries",
    "guided_capture_responses",
)

ASK_STATIC = Path(__file__).resolve().parent / "ask" / "static" / "ask.html"
STORY_STATIC = Path(__file__).resolve().parent / "story" / "static" / "story.html"
JOURNAL_STATIC = Path(__file__).resolve().parent / "journal" / "static" / "journal.html"
PEOPLE_STATIC = Path(__file__).resolve().parent / "person" / "static" / "people.html"
REVIEW_STATIC = Path(__file__).resolve().parent / "review" / "static" / "review.html"
LIBRARY_STATIC = Path(__file__).resolve().parent / "library" / "static" / "library.html"
ARTIFACT_STATIC = Path(__file__).resolve().parent / "artifact" / "static" / "artifact.html"
GC_STATIC = Path(__file__).resolve().parent / "guided_capture" / "static" / "guided_capture.html"
EXPORT_STATIC = Path(__file__).resolve().parent / "export" / "static" / "export.html"
STATUS_STATIC = Path(__file__).resolve().parent / "status" / "static" / "status.html"
SETTINGS_STATIC = Path(__file__).resolve().parent / "settings" / "static" / "settings.html"
SHELL_STATIC_DIR = Path(__file__).resolve().parent / "shell" / "static"

app = FastAPI(
    title="MemoryBox",
    version=__version__,
    description="MemoryBox modular monolith (MBBS-001). P2-I2 Product Shell.",
)

if SHELL_STATIC_DIR.is_dir():
    app.mount("/static/shell", StaticFiles(directory=str(SHELL_STATIC_DIR)), name="shell_static")


def _html_ui(path: Path, *, surface: str, missing: str) -> HTMLResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail=missing)
    return HTMLResponse(
        read_and_inject(path, surface=surface),
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
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


class ReconcileIdentityRequest(BaseModel):
    """I10: map a new provider external id onto an existing MB Person after reprocess."""

    provider_key: str = Field(..., min_length=1)
    new_external_id: str = Field(..., min_length=1)
    previous_external_id: str | None = None
    label: str | None = None


class ReviewFaceRequest(BaseModel):
    video_external_id: str = Field(..., min_length=1)
    t_sec: float = 0.0
    label: str | None = None
    bbox: dict[str, Any] | None = None


class ReviewFaceBoxRequest(BaseModel):
    bbox: dict[str, Any]
    label: str | None = None
    crop_jpeg_base64: str | None = None


class ArtifactCreateRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str | None = None
    person_ids: list[str] = Field(default_factory=list)


class ArtifactReviseRequest(BaseModel):
    kind: str | None = None
    label: str | None = None
    description: str | None = None
    note: str | None = None


class ArtifactEvidenceRefRequest(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    label: str | None = None


class ArtifactStoryCreateRequest(BaseModel):
    title: str | None = None
    body_text: str = Field(..., min_length=1)
    narrator_display_name: str | None = None
    narrator_person_id: str | None = None
    narrator_provider_key: str | None = "immich"
    narrator_external_id: str | None = None


class ArtifactPersonFromProviderRequest(BaseModel):
    """Lazy Immich (trusted provider) name → MB Person → Artifact association."""

    display_name: str = Field(..., min_length=2)
    provider_key: str = "immich"
    external_id: str = Field(..., min_length=1)
    label: str | None = None


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
        "increment": "12",
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
        "artifact": "/artifact/ui",
        "guided_capture": "/guided-capture/ui",
        "export": "/export/ui",
        "status": "/status/ui",
        "settings": "/settings/ui",
    }


@app.get("/")
def root() -> RedirectResponse:
    """P2-I2: Ask/Home is the product front door."""
    return RedirectResponse(url="/ask/ui", status_code=307)


@app.get("/ask/ui")
def ask_ui() -> HTMLResponse:
    return _html_ui(ASK_STATIC, surface="ask", missing="Ask UI missing")


@app.get("/story/ui")
def story_ui() -> HTMLResponse:
    return _html_ui(STORY_STATIC, surface="story", missing="Story UI missing")


@app.get("/journal/ui")
def journal_ui() -> HTMLResponse:
    return _html_ui(JOURNAL_STATIC, surface="journal", missing="Journal UI missing")


@app.get("/people/ui")
def people_ui() -> HTMLResponse:
    return _html_ui(PEOPLE_STATIC, surface="people", missing="People UI missing")


@app.get("/review/ui")
def review_ui() -> HTMLResponse:
    return _html_ui(REVIEW_STATIC, surface="review", missing="Review UI missing")


@app.get("/library/ui")
def library_ui() -> HTMLResponse:
    """Library UI with MB Person options embedded (no client fetch required)."""
    if not LIBRARY_STATIC.is_file():
        raise HTTPException(status_code=404, detail="Library UI missing")
    html = LIBRARY_STATIC.read_text(encoding="utf-8")
    people_err: str | None = None
    try:
        rows = list_people(limit=200)
    except Exception as exc:  # noqa: BLE001
        rows = []
        people_err = str(exc)
    options = ['<option value="">(select a person)</option>']
    for p in rows:
        pid = html_escape(str(p.get("id") or ""))
        name = p.get("display_name") or "(unnamed)"
        st = p.get("status") or "?"
        label_raw = f"{name} · {st}" + (f" · {pid[:8]}" if pid else "")
        label = html_escape(label_raw)
        options.append(f'<option value="{pid}">{label}</option>')
    html = html.replace(
        '<select id="personSel"><option value="">(select a person)</option></select>',
        "<select id=\"personSel\">" + "".join(options) + "</select>",
        1,
    )
    if people_err:
        status = f"People embed failed: {people_err}"
        status_cls = "warn"
    elif not rows:
        status = "No MB People in database (embed)."
        status_cls = "warn"
    else:
        status = f"Loaded {len(rows)} people (embedded; video worker not required)."
        status_cls = "muted"
    html = html.replace(
        '<p id="peopleStatus" class="muted"></p>',
        f'<p id="peopleStatus" class="{status_cls}">{html_escape(status)}</p>',
        1,
    )
    return HTMLResponse(
        content=inject_shell(html, surface="library"),
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@app.get("/artifact/ui")
def artifact_ui() -> HTMLResponse:
    return _html_ui(ARTIFACT_STATIC, surface="artifact", missing="Artifact UI missing")


@app.get("/guided-capture/ui")
def guided_capture_ui() -> HTMLResponse:
    return _html_ui(GC_STATIC, surface="guided_capture", missing="Guided Capture UI missing")


@app.get("/export/ui")
def export_ui() -> HTMLResponse:
    return _html_ui(EXPORT_STATIC, surface="export", missing="Export UI missing")


class ExportStartRequest(BaseModel):
    destination: str | None = None
    make_zip: bool = False


@app.get("/export/config")
def export_config() -> dict[str, Any]:
    raw = (os.environ.get("MEMORYBOX_EXPORT_DIR") or "").strip()
    allow_dev = bool(getattr(settings, "allow_dev_defaults", False))
    configured = bool(raw)
    warning = None
    try:
        resolved = str(resolve_export_parent())
        if raw and Path(raw).expanduser().resolve() != Path(resolved).resolve():
            warning = (
                f"Configured MEMORYBOX_EXPORT_DIR ({raw}) is not usable on this host; "
                f"using {resolved}"
            )
    except ExportError:
        resolved = None
    return {
        "export_dir_configured": configured,
        "export_dir": resolved or raw,
        "export_dir_env": raw or None,
        "allow_dev_defaults": allow_dev,
        "memorybox_export_format": 1,
        "warning": warning,
    }


@app.post("/export/start")
def export_start(body: ExportStartRequest) -> dict[str, Any]:
    try:
        resolve_export_parent(body.destination)
        return start_export_job(destination=body.destination, make_zip=bool(body.make_zip))
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/export/jobs/{job_id}")
def export_job_status(job_id: str) -> dict[str, Any]:
    try:
        return get_export_job(job_id)
    except ExportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/status/ui")
def status_ui() -> HTMLResponse:
    """Archive Health entry (owner/system) under Product Shell — content remains I3."""
    return _html_ui(STATUS_STATIC, surface="status", missing="Status UI missing")


@app.get("/settings/ui")
def settings_ui() -> HTMLResponse:
    """Settings stub entry (owner/system) — mature Settings deferred to I14."""
    return _html_ui(SETTINGS_STATIC, surface="settings", missing="Settings UI missing")


@app.get("/status/summary")
def status_summary() -> dict[str, Any]:
    try:
        return build_status_summary()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"status summary failed: {exc}") from exc


@app.get("/library/person-options")
def library_person_options(limit: int = Query(200, ge=1, le=500)) -> dict[str, Any]:
    """MB Person options for Library filter — same I6 list as GET /people.

    Separate path so browser extensions that block `/people` do not empty the dropdown.
    """
    try:
        rows = list_people(limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"library person-options failed (check MEMORYBOX_DATABASE_URL): {exc}",
        ) from exc
    return {"ok": True, "count": len(rows), "people": rows}


@app.get("/library/cards")
def library_cards(
    person_id: str | None = Query(None),
    bucket: str = Query("timeline"),
    modalities: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(24, ge=1, le=50),
) -> dict[str, Any]:
    """Unified Library read API.

    Person filter required for Person-centric browse (I8).
    Artifact-only browse may omit person_id (I9).
    """
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
    person_id: str | None = Query(None),
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


@app.get("/library/media/photo/{external_id}")
def library_photo_thumb(external_id: str) -> Response:
    """Authenticated Immich (or fake) preview for Library cards — browser-safe."""
    photo = build_photo()
    try:
        preview = photo.fetch_preview(external_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404, detail=f"photo thumb unavailable: {exc}"
        ) from exc
    return Response(
        content=preview.data,
        media_type=preview.content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.get("/library/media/video-poster")
def library_video_poster(
    video: str = Query(..., min_length=1),
    t: float = Query(0.0),
) -> Response:
    """Poster frame for a video segment via the sibling video worker."""
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="MEMORYBOX_VIDEO_WORKER_URL required for video posters",
        )
    q = urllib.parse.urlencode(
        {"video_external_id": video, "t": f"{max(0.0, float(t)):.3f}"}
    )
    url = f"{base}/poster?{q}"
    try:
        with urllib.request.urlopen(url, timeout=45) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type") or "image/jpeg"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=exc.code, detail=detail or "poster failed"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503, detail=f"video poster unavailable: {exc}"
        ) from exc
    if not data:
        raise HTTPException(status_code=404, detail="empty poster")
    return Response(
        content=data,
        media_type=ctype,
        headers={"Cache-Control": "private, max-age=600"},
    )


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


@app.get("/artifact")
def artifact_list(
    limit: int = Query(50, ge=1, le=200),
    kind: str | None = Query(None),
    person_id: str | None = Query(None),
    q: str | None = Query(None),
) -> dict[str, Any]:
    try:
        rows = list_artifacts(limit=limit, kind=kind, person_id=person_id, query=q)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "kinds": list(ARTIFACT_KINDS),
        "artifacts": [a.to_dict() for a in rows],
    }


@app.post("/artifact")
def artifact_create(body: ArtifactCreateRequest) -> dict[str, Any]:
    try:
        view = create_artifact(
            kind=body.kind,
            label=body.label,
            description=body.description,
            person_ids=body.person_ids,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.get("/artifact/{artifact_id}")
def artifact_get(artifact_id: str) -> dict[str, Any]:
    view = get_artifact(artifact_id)
    if not view:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"ok": True, "artifact": view.to_dict()}


@app.post("/artifact/{artifact_id}/revise")
def artifact_revise(artifact_id: str, body: ArtifactReviseRequest) -> dict[str, Any]:
    try:
        view = revise_metadata(
            artifact_id,
            kind=body.kind,
            label=body.label,
            description=body.description,
            note=body.note,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.post("/artifact/{artifact_id}/representations")
async def artifact_add_representation(
    artifact_id: str,
    file: UploadFile = File(...),
    label: str | None = Form(None),
) -> dict[str, Any]:
    data = await file.read()
    try:
        view = add_mb_managed_representation(
            artifact_id,
            data=data,
            filename=file.filename,
            content_type=file.content_type,
            label=label,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.post("/artifact/{artifact_id}/evidence-ref")
def artifact_add_evidence_ref(
    artifact_id: str, body: ArtifactEvidenceRefRequest
) -> dict[str, Any]:
    try:
        view = add_evidence_ref_representation(
            artifact_id, evidence_id=body.evidence_id, label=body.label
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.get("/artifact/{artifact_id}/representations/{representation_id}/bytes")
def artifact_representation_bytes(
    artifact_id: str, representation_id: str
) -> Response:
    try:
        data, mime, name = read_representation_bytes(artifact_id, representation_id)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    safe = name.replace('"', "")
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{safe}"'},
    )


@app.post("/artifact/{artifact_id}/persons/from-provider")
def artifact_add_person_from_provider(
    artifact_id: str, body: ArtifactPersonFromProviderRequest
) -> dict[str, Any]:
    """Teach/map Immich person name into MB Person (I6/I7), then associate Artifact."""
    try:
        linked = artifact_associate_person_from_provider(
            artifact_id,
            display_name=body.display_name,
            provider_key=body.provider_key,
            external_id=body.external_id,
            label=body.label,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **linked}


@app.post("/artifact/{artifact_id}/persons/{person_id}")
def artifact_add_person(artifact_id: str, person_id: str) -> dict[str, Any]:
    try:
        view = artifact_associate_person(artifact_id, person_id)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.post("/artifact/{artifact_id}/stories/{story_id}")
def artifact_add_story(artifact_id: str, story_id: str) -> dict[str, Any]:
    try:
        view = artifact_associate_story(artifact_id, story_id)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "artifact": view.to_dict()}


@app.post("/artifact/{artifact_id}/story")
def artifact_create_story(
    artifact_id: str, body: ArtifactStoryCreateRequest
) -> dict[str, Any]:
    try:
        linked = create_story_for_artifact(
            artifact_id,
            title=body.title,
            body_text=body.body_text,
            narrator_display_name=body.narrator_display_name,
            narrator_person_id=body.narrator_person_id,
            narrator_provider_key=body.narrator_provider_key,
            narrator_external_id=body.narrator_external_id,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **linked}


@app.get("/people")
def people_list(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    try:
        rows = list_people(limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"people list failed (check MEMORYBOX_DATABASE_URL): {exc}",
        ) from exc
    return {"ok": True, "count": len(rows), "people": rows}


@app.post("/people/sync/immich")
def people_sync_immich(trigger: str = Query("sync_now")) -> dict[str, Any]:
    """P2-I1: Sync/Poll now — Immich named people → MB Person + recognition enqueue."""
    from memorybox.person.immich_sync import sync_immich_people

    photo = build_photo()
    video = build_video()

    def list_videos() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if hasattr(video, "eligible_video_rows"):
            return list(video.eligible_video_rows())
        try:
            for v in video.list_videos(limit=5000):
                rows.append(
                    {
                        "video_provider_key": getattr(video, "provider_key", "hvrt"),
                        "video_external_id": v.external_id,
                        "eligible": True,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"video inventory failed: {exc}") from exc
        return rows

    def list_faces(pref: Any) -> list[dict[str, Any]]:
        if not hasattr(photo, "list_face_assets"):
            return []
        try:
            assets = photo.list_face_assets(person_external_id=pref.external_id, limit=50)
        except Exception:  # noqa: BLE001
            return []
        out = []
        for a in assets:
            out.append(
                {
                    "id": getattr(a, "external_face_id", None),
                    "external_face_id": getattr(a, "external_face_id", None),
                    "source_asset_id": getattr(a, "source_asset_id", None),
                    "bbox": getattr(a, "bbox", None),
                    "confidence": getattr(a, "confidence", None),
                }
            )
        return out

    trig = (trigger or "sync_now").strip() or "sync_now"
    if trig not in {"sync_now", "nightly", "harness"}:
        trig = "sync_now"
    result = sync_immich_people(
        photo_provider=photo,
        list_eligible_videos=list_videos,
        trigger=trig,
        ingest_faces=True,
        list_face_assets=list_faces,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "sync failed")
    return result


@app.get("/people/sync/immich/latest")
def people_sync_immich_latest() -> dict[str, Any]:
    from memorybox.person.immich_sync import latest_sync_run

    run = latest_sync_run("immich") or latest_sync_run("fake_photo")
    return {"ok": True, "run": run}


@app.get("/recognition/queue")
def recognition_queue_get(
    person_id: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    from memorybox.recognition.queue import list_queue_items, queue_summary

    return {
        "ok": True,
        "summary": queue_summary(person_id),
        "items": list_queue_items(person_id=person_id, status=status, limit=limit),
    }


@app.post("/recognition/queue/process")
def recognition_queue_process(
    person_id: str | None = None,
    max_items: int = Query(25, ge=1, le=500),
) -> dict[str, Any]:
    from memorybox.recognition.process import process_queue

    video = build_video()
    return {"ok": True, **process_queue(video_provider=video, person_id=person_id, max_items=max_items)}


class AppearanceCorrectRequest(BaseModel):
    person_id: str
    video_provider_key: str = "hvrt"
    video_external_id: str
    start_sec: float
    end_sec: float | None = None
    face_external_id: str | None = None


@app.post("/recognition/appearances/correct")
def recognition_appearance_correct(body: AppearanceCorrectRequest) -> dict[str, Any]:
    from memorybox.recognition.process import owner_correct_appearance

    try:
        return {
            "ok": True,
            **owner_correct_appearance(
                person_id=body.person_id,
                video_provider_key=body.video_provider_key,
                video_external_id=body.video_external_id,
                start_sec=body.start_sec,
                end_sec=body.end_sec,
                face_external_id=body.face_external_id,
            ),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/people/{person_id}/face-evidence")
def people_face_evidence(person_id: str) -> dict[str, Any]:
    from memorybox.person.face_evidence import list_face_evidence

    return {"ok": True, "person_id": person_id, "evidence": list_face_evidence(person_id)}


@app.get("/people/{person_id}/appearances")
def people_appearances(person_id: str, limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    from memorybox.recognition.process import list_appearance_moments

    return {
        "ok": True,
        "person_id": person_id,
        "moments": list_appearance_moments(person_id, limit=limit),
    }


@app.get("/people/owner")
def people_owner() -> dict[str, Any]:
    from memorybox.profile import get_current_person_id, owner_config_status

    status = owner_config_status()
    return {
        "ok": True,
        **status,
        "current_person_id": get_current_person_id(),
    }


class OwnerSetBody(BaseModel):
    person_id: str = Field(..., min_length=1)


@app.post("/people/owner")
def people_set_owner(body: OwnerSetBody) -> dict[str, Any]:
    """Set canonical “I am this person” owner for my-father / my-mother relativity."""
    from memorybox.profile import ProfileServiceError, set_owner_person_id

    try:
        status = set_owner_person_id(body.person_id)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **status}


@app.get("/people/picker-options")
def people_picker_options(limit: int = Query(300, ge=1, le=1000)) -> dict[str, Any]:
    """Unified person list for UI: one name once (MB preferred over Immich-only).

    Each option is either an existing MB Person or an Immich identity that will be
    taught into MB on use via POST /people/ensure.
    """
    from memorybox.ask.deps import build_photo
    from memorybox.person import get_person
    from urllib.parse import quote

    mb_rows = list_people(limit=limit)
    mapped_ext: set[str] = set()
    by_name: dict[str, dict[str, Any]] = {}
    options: list[dict[str, Any]] = []

    for row in mb_rows:
        pid = row["id"]
        view = get_person(pid)
        name = (row.get("display_name") or "").strip() or "(unnamed)"
        key = name.lower()
        immich_ids: list[str] = []
        if view:
            for m in view.provider_mappings or []:
                if m.get("provider_key") == "immich" and m.get("external_id"):
                    eid = str(m["external_id"])
                    immich_ids.append(eid)
                    mapped_ext.add(eid)
        entry = {
            "key": f"mb:{pid}",
            "label": name,
            "person_id": pid,
            "display_name": name,
            "source": "memorybox",
            "status": row.get("status"),
            "immich_external_ids": immich_ids,
        }
        # Prefer first MB for a name; later same-name MB still listed with disambiguation
        if key in by_name and by_name[key].get("person_id") != pid:
            entry["label"] = f"{name} (MB · {str(pid)[:8]}…)"
            options.append(entry)
        else:
            by_name[key] = entry
            options.append(entry)

    immich_err: str | None = None
    immich_count = 0
    try:
        photo = build_photo()
        h = photo.health()
        if not h.ok:
            immich_err = h.detail or "Immich unavailable"
        else:
            refs = photo.list_people(limit=limit) or []
            for r in refs:
                eid = str(getattr(r, "external_id", "") or "").strip()
                name = (getattr(r, "display_name", None) or "").strip()
                if not eid or len(name) < 2:
                    continue
                immich_count += 1
                if eid in mapped_ext:
                    continue  # already represented via MB mapping
                key = name.lower()
                if key in by_name:
                    continue  # same display name already in MB — show once
                options.append(
                    {
                        "key": f"immich:{quote(eid, safe='')}:{quote(name, safe='')}",
                        "label": name,
                        "person_id": None,
                        "display_name": name,
                        "source": "immich",
                        "external_id": eid,
                        "status": "immich_only",
                        "immich_external_ids": [eid],
                    }
                )
    except Exception as exc:  # noqa: BLE001
        immich_err = str(exc)

    options.sort(key=lambda o: str(o.get("label") or "").lower())
    return {
        "ok": True,
        "count": len(options),
        "options": options,
        "immich_named_count": immich_count,
        "immich_error": immich_err,
    }


class EnsurePersonBody(BaseModel):
    """Resolve picker selection to an MB Person (lazy-teach Immich when needed)."""

    person_id: str | None = None
    provider_key: str = "immich"
    external_id: str | None = None
    display_name: str | None = None


@app.post("/people/ensure")
def people_ensure(body: EnsurePersonBody) -> dict[str, Any]:
    from memorybox.ask.deps import build_photo
    from memorybox.person import AmbiguousIdentityError

    if body.person_id:
        view = get_person(body.person_id)
        if not view:
            raise HTTPException(status_code=404, detail="person not found")
        return {"ok": True, "created": False, "person": view.to_dict()}
    ext = (body.external_id or "").strip()
    name = (body.display_name or "").strip()
    if not ext or len(name) < 2:
        raise HTTPException(
            status_code=400,
            detail="person_id or (external_id + display_name) required",
        )
    try:
        view = teach_provider_person(
            display_name=name,
            provider_key=body.provider_key or "immich",
            external_id=ext,
            label=name,
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
    return {"ok": True, "created": True, "person": view.to_dict()}


class ContactSupersedeBody(BaseModel):
    value_text: str = Field(..., min_length=2)
    note: str | None = None


@app.post("/people/contacts/{contact_id}/supersede")
def people_supersede_contact(contact_id: str, body: ContactSupersedeBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, supersede_contact

    try:
        contact = supersede_contact(
            contact_id, value_text=body.value_text, note=body.note
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "contact": contact.to_dict()}


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


@app.get("/people/{person_id}/profile")
def people_profile(person_id: str) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, get_person_profile

    try:
        profile = get_person_profile(person_id)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "profile": profile}


class ProfileFactBody(BaseModel):
    fact_kind: str
    value_date: str | None = None
    value_text: str | None = None
    note: str | None = None


class ProfileAliasBody(BaseModel):
    alias_kind: str
    alias_text: str
    note: str | None = None


class ProfileContactBody(BaseModel):
    contact_kind: str
    value_text: str
    note: str | None = None


class ProfileRelationshipBody(BaseModel):
    from_person_id: str
    to_person_id: str
    role_kind: str
    note: str | None = None


class ProfileSupersedeRelBody(BaseModel):
    from_person_id: str
    to_person_id: str
    role_kind: str
    note: str | None = None


class ProfileMarriageBody(BaseModel):
    person_a_id: str
    person_b_id: str
    event_date: str | None = None
    label: str | None = None
    note: str | None = None


@app.post("/people/{person_id}/facts")
def people_add_fact(person_id: str, body: ProfileFactBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, add_fact

    try:
        fact = add_fact(
            person_id,
            fact_kind=body.fact_kind,
            value_date=body.value_date,
            value_text=body.value_text,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "fact": fact.to_dict()}


@app.post("/people/{person_id}/aliases")
def people_add_alias(person_id: str, body: ProfileAliasBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, add_alias

    try:
        alias = add_alias(
            person_id,
            alias_kind=body.alias_kind,
            alias_text=body.alias_text,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "alias": alias.to_dict()}


@app.post("/people/{person_id}/contacts")
def people_add_contact(person_id: str, body: ProfileContactBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, add_contact

    try:
        contact = add_contact(
            person_id,
            contact_kind=body.contact_kind,
            value_text=body.value_text,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "contact": contact.to_dict()}


@app.post("/people/relationships")
def people_assert_relationship(body: ProfileRelationshipBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, assert_relationship

    try:
        rel = assert_relationship(
            from_person_id=body.from_person_id,
            to_person_id=body.to_person_id,
            role_kind=body.role_kind,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "relationship": rel.to_dict()}


@app.post("/people/relationships/{assertion_id}/withdraw")
def people_withdraw_relationship(assertion_id: str, note: str | None = None) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, withdraw_relationship

    try:
        rel = withdraw_relationship(assertion_id, note=note)
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "relationship": rel.to_dict()}


@app.post("/people/relationships/{assertion_id}/supersede")
def people_supersede_relationship(
    assertion_id: str, body: ProfileSupersedeRelBody
) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, supersede_relationship

    try:
        rel = supersede_relationship(
            assertion_id,
            from_person_id=body.from_person_id,
            to_person_id=body.to_person_id,
            role_kind=body.role_kind,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "relationship": rel.to_dict()}


@app.post("/people/life-events/marriage")
def people_create_marriage(body: ProfileMarriageBody) -> dict[str, Any]:
    from memorybox.profile import ProfileServiceError, create_marriage_event

    try:
        ev = create_marriage_event(
            person_a_id=body.person_a_id,
            person_b_id=body.person_b_id,
            event_date=body.event_date,
            label=body.label,
            note=body.note,
        )
    except ProfileServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "life_event": ev.to_dict()}


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
                "candidates": getattr(exc, "candidates", None) or [],
                "hint": (
                    "Do not recreate the human per provider. "
                    "Pick the correct MB Person and POST /people/{person_id}/map "
                    "with this provider_key + external_id (Review: Attach to existing Person)."
                ),
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
    """Attach a provider identity onto an explicit MB Person (cross-provider teach)."""
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


@app.post("/people/{person_id}/reconcile")
def people_reconcile(person_id: str, body: ReconcileIdentityRequest) -> dict[str, Any]:
    """I10: reconcile a new provider external id onto an existing Person after reprocess."""
    from memorybox.person import reconcile_provider_identity

    try:
        view = reconcile_provider_identity(
            person_id=person_id,
            provider_key=body.provider_key,
            new_external_id=body.new_external_id,
            previous_external_id=body.previous_external_id,
            label=body.label,
        )
    except PersonServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "person": view.to_dict(), "archive_updated": True}


@app.get("/people/{person_id}/provider-projection")
def people_provider_projection(person_id: str) -> dict[str, Any]:
    """Rebuildable Person↔provider mapping projection (I10 — PG is SoT)."""
    from memorybox.person import provider_mappings_projection

    try:
        proj = provider_mappings_projection(person_id)
    except PersonServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, **proj}


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


# --- Increment 11 Guided Capture ------------------------------------------------


class GcCampaignCreateBody(BaseModel):
    display_name: str
    email: str
    title: str | None = None
    cadence_seconds: int | None = None
    cadence_days: float | None = None
    start_at: str | None = None
    questions: list[str] = Field(default_factory=list)
    people_id: str | None = None
    owner_person_id: str | None = None


class GcCredibilityBody(BaseModel):
    credibility: str
    actor_key: str = "owner"


class GcTranscriptBody(BaseModel):
    text: str
    actor_key: str = "owner"


class GcLinkPersonBody(BaseModel):
    people_id: str | None = None


def _cadence_seconds_from_body(body: GcCampaignCreateBody) -> int:
    if body.cadence_seconds is not None and int(body.cadence_seconds) >= 1:
        return int(body.cadence_seconds)
    days = body.cadence_days if body.cadence_days is not None else 7.0
    if float(days) <= 0:
        raise HTTPException(status_code=400, detail="cadence_days must be > 0")
    return max(1, int(round(float(days) * 86400)))


@app.get("/guided-capture/email-status")
def gc_email_status() -> dict[str, Any]:
    from memorybox.guided_capture import email_adapter_status

    return email_adapter_status()


@app.get("/guided-capture/respondent-options")
def gc_respondent_options(limit: int = Query(200, ge=1, le=500)) -> dict[str, Any]:
    from memorybox.guided_capture import respondent_options

    return {"options": respondent_options(limit=limit)}


@app.get("/guided-capture/new-count")
def gc_new_count() -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, new_response_count

    try:
        return {"count": new_response_count()}
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/guided-capture/starter-questions")
def gc_starter_questions(limit: int = Query(12, ge=1, le=50)) -> dict[str, Any]:
    from memorybox.guided_capture import starter_questions

    return {"questions": starter_questions(limit=limit)}


@app.get("/guided-capture/contacts")
def gc_list_contacts(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    from memorybox.guided_capture import list_contacts

    return {"contacts": list_contacts(limit=limit)}


@app.post("/guided-capture/contacts")
def gc_upsert_contact(body: dict[str, Any]) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, upsert_contact

    try:
        return upsert_contact(
            display_name=str(body.get("display_name") or ""),
            email=str(body.get("email") or ""),
            people_id=body.get("people_id"),
        )
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/contacts/{contact_id}/link-person")
def gc_link_person(contact_id: str, body: GcLinkPersonBody) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, link_contact_person

    try:
        return link_contact_person(contact_id, body.people_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/guided-capture/campaigns")
def gc_list_campaigns(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    from memorybox.guided_capture import list_campaigns

    return {"campaigns": list_campaigns(limit=limit)}


@app.post("/guided-capture/campaigns")
def gc_create_campaign(body: GcCampaignCreateBody) -> dict[str, Any]:
    from memorybox.guided_capture import (
        GuidedCaptureError,
        create_campaign,
        upsert_contact,
    )

    try:
        contact = upsert_contact(
            display_name=body.display_name,
            email=body.email,
            people_id=body.people_id,
        )
        return create_campaign(
            respondent_contact_id=contact["id"],
            title=body.title,
            owner_person_id=body.owner_person_id,
            cadence_seconds=_cadence_seconds_from_body(body),
            start_at=body.start_at,
            questions=body.questions,
        )
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/guided-capture/campaigns/{campaign_id}")
def gc_get_campaign(campaign_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, get_campaign

    try:
        return get_campaign(campaign_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/guided-capture/campaigns/{campaign_id}/start")
def gc_start(campaign_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, start_campaign

    try:
        return start_campaign(campaign_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/campaigns/{campaign_id}/pause")
def gc_pause(campaign_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, pause_campaign

    try:
        return pause_campaign(campaign_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/campaigns/{campaign_id}/resume")
def gc_resume(campaign_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, resume_campaign

    try:
        return resume_campaign(campaign_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/campaigns/{campaign_id}/stop")
def gc_stop(campaign_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, stop_campaign

    try:
        return stop_campaign(campaign_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/questions/{question_id}/skip")
def gc_skip(question_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, skip_question

    try:
        return skip_question(question_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/tick")
def gc_tick() -> dict[str, Any]:
    from memorybox.guided_capture import tick_scheduler

    return tick_scheduler()


@app.post("/guided-capture/poll")
def gc_poll() -> dict[str, Any]:
    from memorybox.guided_capture import poll_and_ingest

    return poll_and_ingest()


@app.get("/guided-capture/responses")
def gc_list_responses(
    review_status: str | None = None,
    campaign_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, list_responses

    try:
        return {
            "responses": list_responses(
                review_status=review_status,
                campaign_id=campaign_id,
                limit=limit,
            )
        }
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/guided-capture/responses/{response_id}")
def gc_get_response(response_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, get_response

    try:
        return get_response(response_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/guided-capture/responses/{response_id}/credibility")
def gc_set_cred(response_id: str, body: GcCredibilityBody) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, set_credibility

    try:
        return set_credibility(
            response_id, body.credibility, actor_key=body.actor_key
        )
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/responses/{response_id}/reviewed")
def gc_mark_reviewed(response_id: str) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, mark_reviewed

    try:
        return mark_reviewed(response_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/guided-capture/responses/{response_id}/transcript")
def gc_correct_tx(response_id: str, body: GcTranscriptBody) -> dict[str, Any]:
    from memorybox.guided_capture import GuidedCaptureError, correct_transcript

    try:
        return correct_transcript(
            response_id, body.text, actor_key=body.actor_key
        )
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/guided-capture/responses/{response_id}/audio")
def gc_audio(response_id: str) -> Response:
    from pathlib import Path
    from urllib.parse import unquote, urlparse

    from memorybox.guided_capture import GuidedCaptureError, get_response

    try:
        r = get_response(response_id)
    except GuidedCaptureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    uri = r.get("audio_uri")
    if not uri:
        raise HTTPException(status_code=404, detail="no audio")
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise HTTPException(status_code=400, detail="audio not local file")
    raw = unquote(parsed.path or "")
    # Windows file:///C:/path → urlparse path "/C:/path" (leading slash before drive)
    if os.name == "nt":
        if raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
            raw = raw[1:]
        elif parsed.netloc and len(parsed.netloc) >= 2 and parsed.netloc[1] == ":":
            raw = f"{parsed.netloc}{raw}"
    path = Path(raw)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"audio file missing on this host: {path}",
        )
    # Synthetic harness clips are tiny non-media bytes — still serve for download
    media = "audio/webm"
    suffix = path.suffix.lower()
    if suffix == ".wav":
        media = "audio/wav"
    elif suffix == ".mp3":
        media = "audio/mpeg"
    elif suffix in (".m4a", ".mp4"):
        media = "audio/mp4"
    elif suffix == ".ogg":
        media = "audio/ogg"
    return FileResponse(path, media_type=media)
