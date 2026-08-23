"""Increment 9 — Artifact service (conceptual object ≠ representation file)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.story import StoryServiceError, create_story

ARTIFACT_KINDS = (
    "keepsake_object",
    "letter",
    "document",
    "recipe_card",
    "clipping",
    "photograph_of_object",
    "other",
)

KIND_GROUPS = {
    "objects": ("keepsake_object", "photograph_of_object"),
    "documents": ("letter", "document", "clipping"),
    "recipes": ("recipe_card",),
    "other": ("other",),
}

DATE_PRECISIONS = ("day", "month", "year", "approximate", "unknown")
VISIBILITIES = ("private", "shared_with_family")
VIEW_KINDS = ("front", "back", "detail", "engraving", "document", "other")
MEMORY_KINDS = (
    "photo",
    "video",
    "email_thread",
    "sms_conversation",
    "calendar_event",
    "journal",
    "audio",
)

# I10B accepted new-upload MIME (preview vs download is a UI concern).
ACCEPTED_REP_MIME = {
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "image/heic": "image",
    "image/heif": "image",
    "application/pdf": "document",
    "text/plain": "document",
}
ACCEPTED_REP_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}

REL_ABOUT_PERSON = "about_person"
REL_CITES_EVIDENCE = "cites_evidence"
REL_ABOUT_ARTIFACT = "about_artifact"  # story → artifact
REL_ABOUT_PLACE = "about_place"
REL_ABOUT_EVENT = "about_event"


class ArtifactServiceError(Exception):
    pass


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise ArtifactServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ArtifactServiceError(f"{field} must be a UUID") from exc


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def artifact_media_root() -> Path:
    """Durable SoT for MB-managed representation originals (D7 config-only).

    FlightSim PostgreSQL holds Artifact domain knowledge and URI/hash refs.
    Binary originals live on media-server under MEMORYBOX_ARTIFACT_MEDIA_ROOT
    (P1 ops: MemoryBox\\Artifacts under the established photos\\MemoryBox tree —
    see docs/ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md). Never hard-code UNC here.
    """
    raw = (os.environ.get("MEMORYBOX_ARTIFACT_MEDIA_ROOT") or "").strip()
    if raw:
        return Path(raw)
    if (os.environ.get("MEMORYBOX_ALLOW_DEV_DEFAULTS") or "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        # Desktop/prove only — never the FlightSim archive SoT.
        p = Path(os.environ.get("TEMP") or ".") / "memorybox_artifact_media"
        p.mkdir(parents=True, exist_ok=True)
        return p
    raise ArtifactServiceError(
        "MEMORYBOX_ARTIFACT_MEDIA_ROOT is required for MB-managed Artifact uploads "
        "(media-server durable path under MemoryBox tree; not FlightSim local disk "
        "as archive SoT; see docs/ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md)"
    )


def _safe_filename(name: str) -> str:
    base = Path(name or "upload.bin").name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "upload.bin"
    return base[:180]


@dataclass
class ArtifactRepresentationView:
    id: str
    artifact_id: str
    representation_kind: str
    evidence_id: str | None = None
    media_object_id: str | None = None
    uri: str | None = None
    content_hash: str | None = None
    mime_type: str | None = None
    original_filename: str | None = None
    byte_size: int | None = None
    sort_order: int = 0
    label: str | None = None
    view_kind: str = "other"
    caption: str | None = None
    status: str = "active"
    created_at: str | None = None
    download_url: str | None = None
    presentation: str = "download"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactView:
    id: str
    kind: str
    label: str
    description: str | None
    status: str
    current_metadata_revision: int
    unresolved_context: dict[str, Any]
    visibility: str = "private"
    described_start_date: str | None = None
    described_precision: str = "unknown"
    place_id: str | None = None
    place_label: str | None = None
    person_ids: list[str] = field(default_factory=list)
    people: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    story_ids: list[str] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    representations: list[ArtifactRepresentationView] = field(default_factory=list)
    needs_representation: bool = False
    needs_context: bool = False
    added_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    link_memory_id: str | None = None
    cover_thumb_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["representations"] = [r.to_dict() for r in self.representations]
        return d


def _rep_from_row(r: dict[str, Any]) -> ArtifactRepresentationView:
    rid = str(r["id"])
    aid = str(r["artifact_id"])
    kind = str(r["representation_kind"])
    download = None
    mime = (r.get("mime_type") or "").split(";")[0].strip().lower()
    if kind == "mb_managed" and str(r.get("status") or "active") == "active":
        download = f"/artifact/{aid}/representations/{rid}/bytes"
    preview = mime in {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    return ArtifactRepresentationView(
        id=rid,
        artifact_id=aid,
        representation_kind=kind,
        evidence_id=str(r["evidence_id"]) if r.get("evidence_id") else None,
        media_object_id=str(r["media_object_id"]) if r.get("media_object_id") else None,
        uri=r.get("uri"),
        content_hash=r.get("content_hash"),
        mime_type=r.get("mime_type"),
        original_filename=r.get("original_filename"),
        byte_size=int(r["byte_size"]) if r.get("byte_size") is not None else None,
        sort_order=int(r.get("sort_order") or 0),
        label=r.get("label"),
        view_kind=str(r.get("view_kind") or "other"),
        caption=r.get("caption"),
        status=str(r.get("status") or "active"),
        created_at=_iso(r.get("created_at")),
        download_url=download,
        presentation="preview" if preview else "download",
    )


def _load_reps(conn, artifact_id: UUID) -> list[ArtifactRepresentationView]:
    rows = conn.execute(
        """
        SELECT * FROM artifact_representations
        WHERE artifact_id = %s AND COALESCE(status, 'active') = 'active'
        ORDER BY sort_order ASC, created_at ASC
        """,
        (artifact_id,),
    ).fetchall()
    return [_rep_from_row(dict(r)) for r in rows]


def _load_links(conn, artifact_id: UUID) -> tuple[list[str], list[str], list[str]]:
    people: list[str] = []
    evidence: list[str] = []
    stories: list[str] = []
    rows = conn.execute(
        """
        SELECT relationship_kind, from_type, from_id, to_type, to_id, status
        FROM relationships
        WHERE status IN ('candidate', 'confirmed')
          AND (
            (from_type = 'artifact' AND from_id = %s)
            OR (to_type = 'artifact' AND to_id = %s)
          )
        """,
        (artifact_id, artifact_id),
    ).fetchall()
    for r in rows:
        if r["from_type"] == "artifact" and r["to_type"] == "person":
            people.append(str(r["to_id"]))
        elif r["from_type"] == "artifact" and r["to_type"] == "evidence":
            evidence.append(str(r["to_id"]))
        elif r["from_type"] == "story" and r["to_type"] == "artifact":
            stories.append(str(r["from_id"]))
        elif r["from_type"] == "artifact" and r["to_type"] == "story":
            stories.append(str(r["to_id"]))
    mem_stories = conn.execute(
        """
        SELECT DISTINCT s.id::text AS id
        FROM stories s
        JOIN story_versions sv
          ON sv.id IN (s.working_version_id, s.current_saved_version_id)
        JOIN story_version_memories m ON m.version_id = sv.id
        WHERE s.status = 'active'
          AND m.source_kind = 'artifact'
          AND m.source_id = %s
        """,
        (str(artifact_id),),
    ).fetchall()
    for r in mem_stories:
        stories.append(str(r["id"]))
    return (
        list(dict.fromkeys(people)),
        list(dict.fromkeys(evidence)),
        list(dict.fromkeys(stories)),
    )


def _needs_context(
    unresolved: dict[str, Any],
    people: list[str],
    place_id: str | None,
    needs_rep: bool,
) -> bool:
    if needs_rep:
        return True
    if unresolved.get("person") and not people:
        return True
    if unresolved.get("place") and not place_id:
        return True
    if unresolved.get("event"):
        return True
    return False


@lru_cache(maxsize=1)
def _added_by_name() -> str | None:
    try:
        from memorybox.profile.owner import get_owner_person_id

        pid = get_owner_person_id()
        if not pid:
            return None
        from memorybox.person import get_person

        person = get_person(pid)
        return getattr(person, "display_name", None) if person else None
    except Exception:  # noqa: BLE001
        return None


def _hydrate_people(conn, person_ids: list[str]) -> list[dict[str, Any]]:
    if not person_ids:
        return []
    rows = conn.execute(
        """
        SELECT id::text AS id, display_name
        FROM people
        WHERE id = ANY(%s::uuid[]) AND status <> 'merged_away'
        """,
        (person_ids,),
    ).fetchall()
    by_id = {str(r["id"]): r for r in rows}
    out = []
    for pid in person_ids:
        r = by_id.get(pid)
        if not r:
            continue
        out.append(
            {
                "id": pid,
                "display_name": r.get("display_name") or "Person",
                "portrait_url": f"/people/{pid}/portrait",
            }
        )
    return out


def _hydrate_stories(story_ids: list[str]) -> list[dict[str, Any]]:
    if not story_ids:
        return []
    out = []
    try:
        from memorybox.story import get_story
    except Exception:  # noqa: BLE001
        return [{"id": sid} for sid in story_ids]
    for sid in story_ids:
        try:
            view = get_story(sid)
        except Exception:  # noqa: BLE001
            view = None
        if not view:
            continue
        d = view.to_dict(include_body=False) if hasattr(view, "to_dict") else {}
        out.append(
            {
                "id": sid,
                "title": d.get("title") or "Story",
                "narrator_display_name": d.get("narrator_display_name"),
                "ask_available": d.get("ask_available"),
                "has_working_draft": d.get("has_working_draft"),
                "lifecycle": d.get("lifecycle"),
            }
        )
    return out


def _load_memories(conn, artifact_id: UUID) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT * FROM artifact_memories
            WHERE artifact_id = %s AND status = 'active'
            ORDER BY position ASC, created_at ASC
            """,
            (artifact_id,),
        ).fetchall()
    except Exception:  # noqa: BLE001 — pre-I10B schema
        return []
    out = []
    for r in rows:
        kind = str(r["source_kind"])
        sid = str(r["source_id"])
        thumb = r.get("thumb_url")
        if not thumb and kind == "photo":
            thumb = f"/library/media/photo/{sid}"
        out.append(
            {
                "id": str(r["id"]),
                "source_kind": kind,
                "source_id": sid,
                "label_snapshot": r.get("label_snapshot"),
                "occurred_on": _iso(r.get("occurred_on")),
                "thumb_url": thumb,
                "position": int(r.get("position") or 0),
                "status": "active",
            }
        )
    return out


def _sniff_mime(data: bytes) -> str | None:
    if not data:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"%PDF":
        return "application/pdf"
    brand = data[8:24].lower() if len(data) >= 24 else b""
    if data[4:8] == b"ftyp" and any(x in brand for x in (b"heic", b"heif", b"mif1", b"msf1")):
        return "image/heic"
    return None


def _normalize_mime(
    filename: str | None, content_type: str | None, data: bytes | None = None
) -> str:
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw in {"image/jpg", "image/pjpeg"}:
        raw = "image/jpeg"
    if raw in {"image/x-heic", "image/x-heif"}:
        raw = "image/heic"
    if raw in {"application/octet-stream", "binary/octet-stream", "application/x-download"}:
        raw = ""
    ext = Path(filename or "").suffix.lower()
    if raw in ACCEPTED_REP_MIME:
        return raw
    if ext in ACCEPTED_REP_EXT:
        return ACCEPTED_REP_EXT[ext]
    sniffed = _sniff_mime(data or b"")
    if sniffed:
        return sniffed
    raise ArtifactServiceError(
        f"unsupported representation type {content_type or ext or 'unknown'} "
        "(I10B accepts jpeg, png, webp, gif, heic/heif, pdf, txt)"
    )


def _view(conn, row: dict[str, Any]) -> ArtifactView:
    aid = row["id"]
    unresolved = row.get("unresolved_context_json") or {}
    if isinstance(unresolved, str):
        try:
            unresolved = json.loads(unresolved)
        except (TypeError, ValueError, json.JSONDecodeError):
            unresolved = {}
    people, evidence, stories = _load_links(conn, aid)
    reps = _load_reps(conn, aid)
    memories = _load_memories(conn, aid)
    place_id = str(row["place_id"]) if row.get("place_id") else None
    place_label = None
    if place_id:
        prow = conn.execute(
            "SELECT display_name FROM places WHERE id = %s::uuid AND status <> 'removed'",
            (place_id,),
        ).fetchone()
        place_label = (prow or {}).get("display_name") if prow else None
    people_views = _hydrate_people(conn, people)
    story_views = _hydrate_stories(stories)
    needs_rep = len(reps) == 0
    needs_ctx = _needs_context(unresolved, people, place_id, needs_rep)
    cover = None
    for r in reps:
        if r.presentation == "preview" and r.download_url:
            cover = r.download_url
            break
    if not cover:
        for m in memories:
            if m.get("thumb_url"):
                cover = m["thumb_url"]
                break
            if m.get("source_kind") == "photo" and m.get("source_id"):
                cover = f"/library/media/photo/{m['source_id']}"
                break
    return ArtifactView(
        id=str(aid),
        kind=str(row["kind"]),
        label=str(row["label"] or ""),
        description=row.get("description"),
        status=str(row["status"]),
        current_metadata_revision=int(row.get("current_metadata_revision") or 1),
        unresolved_context=dict(unresolved),
        visibility=str(row.get("visibility") or "private"),
        described_start_date=_iso(row.get("described_start_date")),
        described_precision=str(row.get("described_precision") or "unknown"),
        place_id=place_id,
        place_label=place_label,
        person_ids=people,
        people=people_views,
        evidence_ids=evidence,
        story_ids=stories,
        stories=story_views,
        memories=memories,
        representations=reps,
        needs_representation=needs_rep,
        needs_context=needs_ctx,
        added_by=_added_by_name(),
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        cover_thumb_url=cover,
    )


def _view_list_batch(conn, rows: list[dict[str, Any]]) -> list[ArtifactView]:
    """Panel cards: no per-row get_story / owner lookup."""
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    owner = _added_by_name()
    preview_mimes = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    covers: dict[str, str] = {}
    rep_counts: dict[str, int] = {}
    try:
        reps = conn.execute(
            """
            SELECT artifact_id, id, mime_type
            FROM artifact_representations
            WHERE artifact_id = ANY(%s)
              AND COALESCE(status, 'active') = 'active'
            ORDER BY sort_order ASC, created_at ASC
            """,
            (ids,),
        ).fetchall()
    except Exception:  # noqa: BLE001
        reps = []
    for r in reps:
        aid = str(r["artifact_id"])
        rep_counts[aid] = rep_counts.get(aid, 0) + 1
        mime = (r.get("mime_type") or "").split(";")[0].strip().lower()
        if aid not in covers and mime in preview_mimes:
            covers[aid] = f"/artifact/{aid}/representations/{r['id']}/bytes"
    people_by: dict[str, list[dict[str, Any]]] = {str(i): [] for i in ids}
    try:
        prow = conn.execute(
            """
            SELECT r.from_id::text AS artifact_id, p.id::text AS id, p.display_name
            FROM relationships r
            JOIN people p ON p.id = r.to_id
            WHERE r.from_type = 'artifact'
              AND r.from_id = ANY(%s)
              AND r.to_type = 'person'
              AND r.relationship_kind = %s
              AND r.status IN ('candidate', 'confirmed')
              AND p.status <> 'merged_away'
            """,
            (ids, REL_ABOUT_PERSON),
        ).fetchall()
        for r in prow:
            people_by.setdefault(r["artifact_id"], []).append(
                {
                    "id": r["id"],
                    "display_name": r.get("display_name") or "Person",
                    "portrait_url": f"/people/{r['id']}/portrait",
                }
            )
    except Exception:  # noqa: BLE001
        pass
    mem_counts: dict[str, int] = {}
    mem_thumbs: dict[str, str] = {}
    try:
        mrows = conn.execute(
            """
            SELECT artifact_id::text AS artifact_id, source_kind, source_id, thumb_url
            FROM artifact_memories
            WHERE artifact_id = ANY(%s) AND status = 'active'
            ORDER BY position ASC, created_at ASC
            """,
            (ids,),
        ).fetchall()
        for r in mrows:
            aid = r["artifact_id"]
            mem_counts[aid] = mem_counts.get(aid, 0) + 1
            if aid in mem_thumbs:
                continue
            thumb = r.get("thumb_url")
            if not thumb and r.get("source_kind") == "photo" and r.get("source_id"):
                thumb = f"/library/media/photo/{r['source_id']}"
            if thumb:
                mem_thumbs[aid] = thumb
    except Exception:  # noqa: BLE001
        pass
    story_ids_by: dict[str, list[str]] = {str(i): [] for i in ids}
    try:
        srows = conn.execute(
            """
            SELECT DISTINCT m.source_id AS artifact_id, s.id::text AS story_id
            FROM story_version_memories m
            JOIN story_versions sv ON sv.id = m.version_id
            JOIN stories s ON s.id = sv.story_id
              AND s.status = 'active'
              AND sv.id IN (s.working_version_id, s.current_saved_version_id)
            WHERE m.source_kind = 'artifact'
              AND m.source_id = ANY(%s)
            """,
            ([str(i) for i in ids],),
        ).fetchall()
        for r in srows:
            story_ids_by.setdefault(str(r["artifact_id"]), []).append(r["story_id"])
    except Exception:  # noqa: BLE001
        pass
    place_ids = [r["place_id"] for r in rows if r.get("place_id")]
    places: dict[str, str] = {}
    if place_ids:
        for pr in conn.execute(
            "SELECT id::text AS id, display_name FROM places WHERE id = ANY(%s) AND status <> 'removed'",
            (place_ids,),
        ).fetchall():
            places[pr["id"]] = pr.get("display_name") or ""
    views = []
    for row in rows:
        aid = str(row["id"])
        unresolved = row.get("unresolved_context_json") or {}
        if isinstance(unresolved, str):
            try:
                unresolved = json.loads(unresolved)
            except (TypeError, ValueError, json.JSONDecodeError):
                unresolved = {}
        people = people_by.get(aid) or []
        place_id = str(row["place_id"]) if row.get("place_id") else None
        needs_rep = rep_counts.get(aid, 0) == 0
        needs_ctx = _needs_context(unresolved, [p["id"] for p in people], place_id, needs_rep)
        cover = covers.get(aid) or mem_thumbs.get(aid)
        n_mem = mem_counts.get(aid, 0)
        sids = story_ids_by.get(aid) or []
        views.append(
            ArtifactView(
                id=aid,
                kind=str(row["kind"]),
                label=str(row["label"] or ""),
                description=row.get("description"),
                status=str(row["status"]),
                current_metadata_revision=int(row.get("current_metadata_revision") or 1),
                unresolved_context=dict(unresolved),
                visibility=str(row.get("visibility") or "private"),
                described_start_date=_iso(row.get("described_start_date")),
                described_precision=str(row.get("described_precision") or "unknown"),
                place_id=place_id,
                place_label=places.get(place_id) if place_id else None,
                person_ids=[p["id"] for p in people],
                people=people,
                story_ids=sids,
                stories=[{"id": sid} for sid in sids],
                memories=[{"id": str(i)} for i in range(n_mem)],
                needs_representation=needs_rep,
                needs_context=needs_ctx,
                added_by=owner,
                created_at=_iso(row.get("created_at")),
                updated_at=_iso(row.get("updated_at")),
                cover_thumb_url=cover,
            )
        )
    return views


def _add_rel(
    conn,
    *,
    kind: str,
    from_type: str,
    from_id: UUID,
    to_type: str,
    to_id: UUID,
    label: str,
) -> None:
    exists = conn.execute(
        """
        SELECT 1 FROM relationships
        WHERE from_type=%s AND from_id=%s AND to_type=%s AND to_id=%s
          AND relationship_kind=%s
        LIMIT 1
        """,
        (from_type, from_id, to_type, to_id, kind),
    ).fetchone()
    if exists:
        return
    conn.execute(
        """
        INSERT INTO relationships (
            id, relationship_kind, from_type, from_id, to_type, to_id,
            label, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'confirmed')
        """,
        (uuid4(), kind, from_type, from_id, to_type, to_id, label),
    )


def create_artifact(
    *,
    kind: str,
    label: str,
    description: str | None = None,
    unresolved_context: dict[str, Any] | None = None,
    person_ids: list[str] | None = None,
    actor_key: str = "owner",
    visibility: str | None = None,
    described_start_date: str | None = None,
    described_precision: str | None = None,
    place_id: str | None = None,
) -> ArtifactView:
    k = (kind or "").strip()
    if k not in ARTIFACT_KINDS:
        raise ArtifactServiceError(
            f"kind must be one of: {', '.join(ARTIFACT_KINDS)}"
        )
    lab = (label or "").strip()
    if not lab:
        raise ArtifactServiceError("label is required")
    desc = (description or "").strip() or None
    unresolved = unresolved_context or {"person": True, "place": True, "event": True}
    vis = (visibility or "private").strip() or "private"
    if vis not in VISIBILITIES:
        raise ArtifactServiceError("visibility must be private or shared_with_family")
    prec = (described_precision or "unknown").strip() or "unknown"
    if prec not in DATE_PRECISIONS:
        raise ArtifactServiceError("invalid described_precision")
    dstart = (described_start_date or "").strip() or None
    if prec == "unknown":
        dstart = None
    pid_place = None
    if place_id and str(place_id).strip():
        pid_place = _parse_uuid(str(place_id), field="place_id")
        unresolved = dict(unresolved)
        unresolved["place"] = False
    aid = uuid4()
    with connection() as conn:
        if pid_place:
            pl = conn.execute(
                "SELECT id FROM places WHERE id = %s AND status <> 'removed'",
                (pid_place,),
            ).fetchone()
            if not pl:
                raise ArtifactServiceError("place not found")
        conn.execute(
            """
            INSERT INTO artifacts (
                id, kind, label, description, status, current_metadata_revision,
                unresolved_context_json, visibility, described_start_date,
                described_precision, place_id
            )
            VALUES (%s, %s, %s, %s, 'active', 1, %s::jsonb, %s, %s, %s, %s)
            """,
            (aid, k, lab, desc, json.dumps(unresolved), vis, dstart, prec, pid_place),
        )
        conn.execute(
            """
            INSERT INTO artifact_metadata_revisions (
                id, artifact_id, revision, kind, label, description,
                unresolved_context_json, actor_key, note,
                visibility, described_start_date, described_precision, place_id
            )
            VALUES (%s, %s, 1, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                aid,
                k,
                lab,
                desc,
                json.dumps(unresolved),
                actor_key or "owner",
                "create",
                vis,
                dstart,
                prec,
                pid_place,
            ),
        )
        for pid in person_ids or []:
            if not str(pid).strip():
                continue
            _add_rel(
                conn,
                kind=REL_ABOUT_PERSON,
                from_type="artifact",
                from_id=aid,
                to_type="person",
                to_id=_parse_uuid(str(pid), field="person_id"),
                label="Artifact about person",
            )
            # Person known → clear person unresolved flag
            unresolved = dict(unresolved)
            unresolved["person"] = False
            conn.execute(
                """
                UPDATE artifacts
                SET unresolved_context_json = %s::jsonb, updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(unresolved), aid),
            )
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert row
        return _view(conn, dict(row))


def get_artifact(artifact_id: str) -> ArtifactView | None:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            return None
        return _view(conn, dict(row))


def list_artifacts(
    *,
    limit: int = 50,
    kind: str | None = None,
    kind_group: str | None = None,
    person_id: str | None = None,
    query: str | None = None,
    needs_context: bool | None = None,
    visibility: str | None = None,
) -> list[ArtifactView]:
    lim = max(1, min(int(limit or 50), 200))
    clauses = ["a.status = 'active'"]
    params: list[Any] = []
    if kind:
        if kind not in ARTIFACT_KINDS:
            raise ArtifactServiceError("invalid kind filter")
        clauses.append("a.kind = %s")
        params.append(kind)
    if kind_group:
        g = (kind_group or "").strip().lower()
        if g not in KIND_GROUPS:
            raise ArtifactServiceError("invalid kind_group")
        kinds = KIND_GROUPS[g]
        clauses.append("a.kind IN (" + ", ".join(["%s"] * len(kinds)) + ")")
        params.extend(list(kinds))
    if visibility:
        vis = visibility.strip()
        if vis not in VISIBILITIES:
            raise ArtifactServiceError("invalid visibility")
        clauses.append("a.visibility = %s")
        params.append(vis)
    if person_id:
        pid = _parse_uuid(person_id, field="person_id")
        clauses.append(
            """
            EXISTS (
              SELECT 1 FROM relationships r
              WHERE r.from_type = 'artifact' AND r.from_id = a.id
                AND r.to_type = 'person' AND r.to_id = %s
                AND r.relationship_kind = %s
                AND r.status IN ('candidate', 'confirmed')
            )
            """
        )
        params.extend([pid, REL_ABOUT_PERSON])
    if query and query.strip():
        needle = f"%{query.strip()}%"
        clauses.append("(a.label ILIKE %s OR COALESCE(a.description,'') ILIKE %s)")
        params.extend([needle, needle])
    fetch_n = 200 if needs_context else lim
    params.append(fetch_n)
    sql = f"""
        SELECT a.* FROM artifacts a
        WHERE {' AND '.join(clauses)}
        ORDER BY a.updated_at DESC
        LIMIT %s
    """
    with connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        views = _view_list_batch(conn, [dict(r) for r in rows])
    if needs_context:
        views = [v for v in views if v.needs_context][:lim]
    return views


def revise_metadata(
    artifact_id: str,
    *,
    kind: str | None = None,
    label: str | None = None,
    description: str | None = None,
    unresolved_context: dict[str, Any] | None = None,
    actor_key: str = "owner",
    note: str | None = None,
    visibility: str | None = None,
    described_start_date: str | None = None,
    described_precision: str | None = None,
    place_id: str | None = None,
) -> ArtifactView:
    """Immutable metadata revision — does not touch representation bytes."""
    aid = _parse_uuid(artifact_id, field="artifact_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        new_kind = (kind or row["kind"]).strip()
        if new_kind not in ARTIFACT_KINDS:
            raise ArtifactServiceError("invalid kind")
        new_label = (label if label is not None else row["label"] or "").strip()
        if not new_label:
            raise ArtifactServiceError("label is required")
        if description is None:
            new_desc = row.get("description")
        else:
            new_desc = description.strip() or None
        prev_unresolved = row.get("unresolved_context_json") or {}
        if isinstance(prev_unresolved, str):
            try:
                prev_unresolved = json.loads(prev_unresolved)
            except (TypeError, ValueError, json.JSONDecodeError):
                prev_unresolved = {}
        new_unresolved = (
            unresolved_context if unresolved_context is not None else dict(prev_unresolved)
        )
        new_vis = (visibility if visibility is not None else row.get("visibility") or "private")
        new_vis = str(new_vis).strip() or "private"
        if new_vis not in VISIBILITIES:
            raise ArtifactServiceError("visibility must be private or shared_with_family")
        new_prec = (
            described_precision
            if described_precision is not None
            else row.get("described_precision") or "unknown"
        )
        new_prec = str(new_prec).strip() or "unknown"
        if new_prec not in DATE_PRECISIONS:
            raise ArtifactServiceError("invalid described_precision")
        if described_start_date is None:
            new_date = row.get("described_start_date")
        else:
            new_date = described_start_date.strip() or None
        if new_prec == "unknown":
            new_date = None
        if place_id is None:
            new_place = row.get("place_id")
        elif str(place_id).strip() == "":
            new_place = None
            new_unresolved = dict(new_unresolved)
            new_unresolved["place"] = True
        else:
            new_place = _parse_uuid(str(place_id), field="place_id")
            pl = conn.execute(
                "SELECT id FROM places WHERE id = %s AND status <> 'removed'",
                (new_place,),
            ).fetchone()
            if not pl:
                raise ArtifactServiceError("place not found")
            new_unresolved = dict(new_unresolved)
            new_unresolved["place"] = False
        rev = int(row["current_metadata_revision"] or 1) + 1
        conn.execute(
            """
            INSERT INTO artifact_metadata_revisions (
                id, artifact_id, revision, kind, label, description,
                unresolved_context_json, actor_key, note,
                visibility, described_start_date, described_precision, place_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                aid,
                rev,
                new_kind,
                new_label,
                new_desc,
                json.dumps(new_unresolved),
                actor_key or "owner",
                note,
                new_vis,
                new_date,
                new_prec,
                new_place,
            ),
        )
        conn.execute(
            """
            UPDATE artifacts
            SET kind = %s, label = %s, description = %s,
                unresolved_context_json = %s::jsonb,
                current_metadata_revision = %s,
                visibility = %s,
                described_start_date = %s,
                described_precision = %s,
                place_id = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (
                new_kind,
                new_label,
                new_desc,
                json.dumps(new_unresolved),
                rev,
                new_vis,
                new_date,
                new_prec,
                new_place,
                aid,
            ),
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def add_mb_managed_representation(
    artifact_id: str,
    *,
    data: bytes,
    filename: str | None = None,
    content_type: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
    view_kind: str | None = None,
    caption: str | None = None,
) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    if not data:
        raise ArtifactServiceError("empty upload")
    mime = _normalize_mime(filename, content_type, data)
    vk = (view_kind or "").strip() or "other"
    if vk not in VIEW_KINDS:
        raise ArtifactServiceError("invalid view_kind")
    cap = (caption or "").strip() or None
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
    digest = hashlib.sha256(data).hexdigest()
    root = artifact_media_root()
    root.mkdir(parents=True, exist_ok=True)
    art_dir = root / str(aid)
    art_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename or "upload.bin")
    # Content-addressed filename prevents silent overwrite of distinct bytes.
    dest_name = f"{digest[:16]}_{safe}"
    dest = art_dir / dest_name
    if dest.is_file():
        # Same hash already stored — reuse path; do not rewrite bytes.
        pass
    else:
        tmp = art_dir / f".tmp_{uuid4().hex}"
        tmp.write_bytes(data)
        tmp.replace(dest)

    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        # Idempotent: same artifact + hash → return existing
        existing = conn.execute(
            """
            SELECT id, status FROM artifact_representations
            WHERE artifact_id = %s AND content_hash = %s
              AND representation_kind = 'mb_managed'
            LIMIT 1
            """,
            (aid, digest),
        ).fetchone()
        if existing:
            if existing.get("status") == "removed":
                conn.execute(
                    """
                    UPDATE artifact_representations
                    SET status = 'active', view_kind = %s, caption = %s,
                        label = COALESCE(%s, label)
                    WHERE id = %s
                    """,
                    (vk, cap, (label or "").strip() or None, existing["id"]),
                )
                conn.execute(
                    "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
                )
                row = conn.execute(
                    "SELECT * FROM artifacts WHERE id = %s", (aid,)
                ).fetchone()
            return _view(conn, dict(row))

        # Domain source/media rows are optional. A unique-hash collision
        # must not block the representation itself.
        mid = None
        sid = uuid4()
        rel_uri = str(dest)
        try:
            with conn.transaction():
                mid = uuid4()
                conn.execute(
                    """
                    INSERT INTO sources (id, source_kind, label, uri, content_hash, authoritative_original_mode)
                    VALUES (%s, 'artifact_upload', %s, %s, %s, 'memorybox_managed')
                    """,
                    (sid, f"Artifact {aid}", rel_uri, digest),
                )
                conn.execute(
                    """
                    INSERT INTO media_objects (
                        id, source_id, media_kind, storage_mode, uri, content_hash, mime_type
                    )
                    VALUES (%s, %s, 'document', 'memorybox_managed', %s, %s, %s)
                    """,
                    (mid, sid, rel_uri, digest, mime),
                )
        except Exception:  # noqa: BLE001
            mid = None
        order = sort_order
        if order is None:
            mx = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM artifact_representations WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            order = int(mx["m"] if mx else -1) + 1
        conn.execute(
            """
            INSERT INTO artifact_representations (
                id, artifact_id, representation_kind, media_object_id,
                uri, content_hash, mime_type, original_filename, byte_size,
                sort_order, label, view_kind, caption, status
            )
            VALUES (%s, %s, 'mb_managed', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """,
            (
                uuid4(),
                aid,
                mid,
                rel_uri,
                digest,
                mime,
                safe,
                len(data),
                order,
                (label or "").strip() or None,
                vk,
                cap,
            ),
        )
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def add_evidence_ref_representation(
    artifact_id: str,
    *,
    evidence_id: str,
    label: str | None = None,
    sort_order: int | None = None,
) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    eid = _parse_uuid(evidence_id, field="evidence_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        ev = conn.execute("SELECT id FROM evidence WHERE id = %s", (eid,)).fetchone()
        if not ev:
            raise ArtifactServiceError("evidence not found")
        existing = conn.execute(
            """
            SELECT id FROM artifact_representations
            WHERE artifact_id = %s AND evidence_id = %s
              AND representation_kind = 'evidence_ref'
            LIMIT 1
            """,
            (aid, eid),
        ).fetchone()
        if existing:
            return _view(conn, dict(row))
        order = sort_order
        if order is None:
            mx = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM artifact_representations WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            order = int(mx["m"] if mx else -1) + 1
        conn.execute(
            """
            INSERT INTO artifact_representations (
                id, artifact_id, representation_kind, evidence_id,
                sort_order, label
            )
            VALUES (%s, %s, 'evidence_ref', %s, %s, %s)
            """,
            (uuid4(), aid, eid, order, (label or "").strip() or None),
        )
        _add_rel(
            conn,
            kind=REL_CITES_EVIDENCE,
            from_type="artifact",
            from_id=aid,
            to_type="evidence",
            to_id=eid,
            label="Artifact cites evidence representation",
        )
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def associate_person(artifact_id: str, person_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        person = conn.execute(
            "SELECT id, status FROM people WHERE id = %s", (pid,)
        ).fetchone()
        if not person or person["status"] == "merged_away":
            raise ArtifactServiceError("person not found")
        _add_rel(
            conn,
            kind=REL_ABOUT_PERSON,
            from_type="artifact",
            from_id=aid,
            to_type="person",
            to_id=pid,
            label="Artifact about person",
        )
        unresolved = row.get("unresolved_context_json") or {}
        if isinstance(unresolved, str):
            try:
                unresolved = json.loads(unresolved)
            except (TypeError, ValueError, json.JSONDecodeError):
                unresolved = {}
        unresolved = dict(unresolved)
        unresolved["person"] = False
        conn.execute(
            """
            UPDATE artifacts
            SET unresolved_context_json = %s::jsonb, updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(unresolved), aid),
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def associate_person_from_provider(
    artifact_id: str,
    *,
    display_name: str,
    provider_key: str = "immich",
    external_id: str,
    label: str | None = None,
) -> dict[str, Any]:
    """I6/I7 lazy Immich name → MB Person, then Artifact association.

    Immich already has the owner-created name; do not require a prior /people/ui
    teach step before Artifact associate.
    """
    from memorybox.ask.deps import build_photo
    from memorybox.person import AmbiguousIdentityError, PersonServiceError, teach_provider_person

    name = (display_name or "").strip()
    ext = (external_id or "").strip()
    if len(name) < 2:
        raise ArtifactServiceError("display_name required (use Immich person name)")
    if not ext:
        raise ArtifactServiceError("external_id required")
    try:
        person = teach_provider_person(
            display_name=name,
            provider_key=(provider_key or "immich").strip() or "immich",
            external_id=ext,
            label=label or name,
            photo=build_photo(),
        )
    except AmbiguousIdentityError as exc:
        raise ArtifactServiceError(
            f"ambiguous Immich→MB Person for {name!r}: {exc} "
            "(resolve in /people/ui, then retry)"
        ) from exc
    except PersonServiceError as exc:
        raise ArtifactServiceError(str(exc)) from exc
    art = associate_person(artifact_id, person.id)
    return {"artifact": art.to_dict(), "person": person.to_dict()}


def associate_story(artifact_id: str, story_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        label = (row["label"] or "").strip() or "Artifact"
        st = conn.execute(
            "SELECT id, status FROM stories WHERE id = %s", (sid,)
        ).fetchone()
        if not st or st["status"] != "active":
            raise ArtifactServiceError("story not found")
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
    from memorybox.story import StoryServiceError, add_working_memory

    try:
        add_working_memory(
            str(sid),
            source_kind="artifact",
            source_id=str(aid),
            label_snapshot=label,
        )
    except StoryServiceError as exc:
        raise ArtifactServiceError(str(exc)) from exc
    got = get_artifact(str(aid))
    if not got:
        raise ArtifactServiceError("artifact not found")
    return got


def create_story_for_artifact(
    artifact_id: str,
    *,
    title: str | None,
    body_text: str,
    narrator_display_name: str | None = None,
    narrator_person_id: str | None = None,
    narrator_provider_key: str | None = None,
    narrator_external_id: str | None = None,
) -> dict[str, Any]:
    """Story Save earn-in: narrator must resolve to an MB Person when given.

    Prefer narrator_person_id or Immich lazy-teach (external_id + display_name).
    Free-text narrator_display_name alone enrolls by exact name (typos → new Person).
    """
    view = get_artifact(artifact_id)
    if not view:
        raise ArtifactServiceError("artifact not found")

    nid = (narrator_person_id or "").strip() or None
    ndisp = (narrator_display_name or "").strip() or None
    next_id = (narrator_external_id or "").strip() or None
    npk = (narrator_provider_key or "immich").strip() or "immich"

    if next_id:
        if not ndisp or len(ndisp) < 2:
            raise ArtifactServiceError(
                "narrator Immich selection requires display_name (Immich person name)"
            )
        from memorybox.ask.deps import build_photo
        from memorybox.person import AmbiguousIdentityError, PersonServiceError, teach_provider_person

        try:
            person = teach_provider_person(
                display_name=ndisp,
                provider_key=npk,
                external_id=next_id,
                label=ndisp,
                photo=build_photo(),
            )
        except AmbiguousIdentityError as exc:
            raise ArtifactServiceError(
                f"ambiguous narrator Immich→MB Person for {ndisp!r}: {exc}"
            ) from exc
        except PersonServiceError as exc:
            raise ArtifactServiceError(str(exc)) from exc
        nid = person.id
        ndisp = None

    if not nid and not ndisp:
        raise ArtifactServiceError(
            "narrator required: select an MB/Immich Person or enroll a new exact display name"
        )

    try:
        story = create_story(
            title=title or f"About {view.label}",
            body_text=body_text,
            narrator_person_id=nid,
            narrator_display_name=ndisp if not nid else None,
            person_ids=list(view.person_ids) or None,
        )
    except StoryServiceError as exc:
        raise ArtifactServiceError(str(exc)) from exc
    associate_story(artifact_id, story.id)
    return {"artifact": get_artifact(artifact_id).to_dict(), "story": story.to_dict()}


def read_representation_bytes(
    artifact_id: str, representation_id: str
) -> tuple[bytes, str, str]:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    rid = _parse_uuid(representation_id, field="representation_id")
    with connection() as conn:
        art = conn.execute(
            "SELECT status FROM artifacts WHERE id = %s", (aid,)
        ).fetchone()
        if not art or art["status"] == "removed":
            raise ArtifactServiceError("representation not found")
        row = conn.execute(
            """
            SELECT * FROM artifact_representations
            WHERE id = %s AND artifact_id = %s
            """,
            (rid, aid),
        ).fetchone()
        if not row:
            raise ArtifactServiceError("representation not found")
        if str(row.get("status") or "active") == "removed":
            raise ArtifactServiceError("representation not found")
        if row["representation_kind"] != "mb_managed":
            raise ArtifactServiceError("only mb_managed representations are byte-served here")
        uri = row.get("uri")
        if not uri:
            raise ArtifactServiceError("representation uri missing")
        path = Path(uri)
        if not path.is_file():
            raise ArtifactServiceError("representation file missing on durable store")
        # Integrity check
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if row.get("content_hash") and digest != row["content_hash"]:
            raise ArtifactServiceError("content hash mismatch — refuse to serve")
        mime = row.get("mime_type") or "application/octet-stream"
        name = row.get("original_filename") or path.name
        return data, mime, name


def search_artifacts_for_ask(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Thin Ask earn-in: match label/description/kind — not filename-as-meaning."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    rows = list_artifacts(limit=limit, query=q)
    # Also kind token match
    low = q.lower()
    kind_hits = []
    for k in ARTIFACT_KINDS:
        token = k.replace("_", " ")
        if token in low or k in low:
            kind_hits.extend(list_artifacts(limit=limit, kind=k))
    by_id = {r.id: r for r in rows}
    for h in kind_hits:
        by_id.setdefault(h.id, h)
    out = []
    for a in by_id.values():
        out.append(
            {
                "artifact_id": a.id,
                "kind": a.kind,
                "label": a.label,
                "description": a.description,
                "person_ids": a.person_ids,
                "story_ids": a.story_ids,
                "representation_count": len(a.representations),
                "deep_link": f"/artifact/ui?id={a.id}",
                "provenance": {
                    "kind": "artifact",
                    "note": "Matched Artifact identity/metadata — not upload filename alone",
                },
            }
        )
    return out[:limit]


def remove_artifact(artifact_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        conn.execute(
            "UPDATE artifacts SET status = 'removed', updated_at = now() WHERE id = %s",
            (aid,),
        )
    gone = get_artifact(str(aid))
    if gone:
        raise ArtifactServiceError("artifact still visible after remove")
    return ArtifactView(
        id=str(aid),
        kind=str(row["kind"]),
        label=str(row["label"] or ""),
        description=row.get("description"),
        status="removed",
        current_metadata_revision=int(row.get("current_metadata_revision") or 1),
        unresolved_context={},
    )


def unlink_person(artifact_id: str, person_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        conn.execute(
            """
            UPDATE relationships
            SET status = 'superseded', updated_at = now()
            WHERE from_type = 'artifact' AND from_id = %s
              AND to_type = 'person' AND to_id = %s
              AND relationship_kind = %s
              AND status IN ('candidate', 'confirmed')
            """,
            (aid, pid, REL_ABOUT_PERSON),
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def remove_representation(artifact_id: str, representation_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    rid = _parse_uuid(representation_id, field="representation_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        rep = conn.execute(
            """
            SELECT id, uri FROM artifact_representations
            WHERE id = %s AND artifact_id = %s
            """,
            (rid, aid),
        ).fetchone()
        if not rep:
            raise ArtifactServiceError("representation not found")
        conn.execute(
            """
            UPDATE artifact_representations
            SET status = 'removed'
            WHERE id = %s
            """,
            (rid,),
        )
        conn.execute("UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,))
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def add_artifact_memory(
    artifact_id: str,
    *,
    source_kind: str,
    source_id: str,
    label_snapshot: str | None = None,
    thumb_url: str | None = None,
    occurred_on: str | None = None,
) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    kind = (source_kind or "").strip()
    if kind not in MEMORY_KINDS:
        raise ArtifactServiceError(f"unsupported source_kind {kind!r}")
    sid = (source_id or "").strip()
    if not sid:
        raise ArtifactServiceError("source_id is required")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        existing = conn.execute(
            """
            SELECT id, status FROM artifact_memories
            WHERE artifact_id = %s AND source_kind = %s AND source_id = %s
            """,
            (aid, kind, sid),
        ).fetchone()
        if existing:
            mx = conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS m FROM artifact_memories WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            conn.execute(
                """
                UPDATE artifact_memories
                SET status = 'active',
                    label_snapshot = COALESCE(%s, label_snapshot),
                    thumb_url = COALESCE(%s, thumb_url),
                    occurred_on = COALESCE(%s, occurred_on),
                    position = %s
                WHERE id = %s
                """,
                (
                    (label_snapshot or "").strip() or None,
                    thumb_url,
                    (occurred_on or "").strip() or None,
                    int(mx["m"] if mx else -1) + 1,
                    existing["id"],
                ),
            )
        else:
            mx = conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS m FROM artifact_memories WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO artifact_memories (
                    id, artifact_id, position, source_kind, source_id,
                    label_snapshot, occurred_on, thumb_url, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
                """,
                (
                    uuid4(),
                    aid,
                    int(mx["m"] if mx else -1) + 1,
                    kind,
                    sid,
                    (label_snapshot or "").strip() or None,
                    (occurred_on or "").strip() or None,
                    thumb_url,
                ),
            )
        conn.execute("UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,))
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def remove_artifact_memory(artifact_id: str, memory_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    mid = _parse_uuid(memory_id, field="memory_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        mem = conn.execute(
            "SELECT id FROM artifact_memories WHERE id = %s AND artifact_id = %s",
            (mid, aid),
        ).fetchone()
        if not mem:
            raise ArtifactServiceError("memory link not found")
        conn.execute(
            "UPDATE artifact_memories SET status = 'removed' WHERE id = %s",
            (mid,),
        )
        conn.execute("UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,))
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def artifacts_using_media(*, source_kind: str, source_id: str) -> list[ArtifactView]:
    kind = (source_kind or "").strip()
    sid = (source_id or "").strip()
    if kind not in MEMORY_KINDS or not sid:
        return []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT a.*, m.id AS link_memory_id
            FROM artifacts a
            JOIN artifact_memories m ON m.artifact_id = a.id
            WHERE a.status = 'active'
              AND m.status = 'active'
              AND m.source_kind = %s
              AND m.source_id = %s
            ORDER BY a.updated_at DESC
            """,
            (kind, sid),
        ).fetchall()
        views = []
        for r in rows:
            payload = dict(r)
            mid = payload.pop("link_memory_id", None)
            view = _view(conn, payload)
            view.link_memory_id = str(mid) if mid else None
            views.append(view)
        return views


def resolve_or_create_place(display_name: str) -> dict[str, Any]:
    from memorybox.correlate.store import upsert_place

    name = (display_name or "").strip()
    if not name:
        raise ArtifactServiceError("place display_name required")
    try:
        return upsert_place(name)
    except Exception as exc:  # noqa: BLE001
        raise ArtifactServiceError(str(exc)) from exc
