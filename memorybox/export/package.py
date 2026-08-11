"""Build MemoryBox export format 1 packages (folder = source of truth)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox import __version__ as app_version
from memorybox.config import settings
from memorybox.db import connection
from memorybox.export.paths import guess_media_type, uri_or_path_to_file

EXPORT_FORMAT_VERSION = 1


class ExportError(RuntimeError):
    pass


@dataclass
class FileEntry:
    relative_path: str
    byte_size: int
    sha256: str
    media_type: str
    related_entity_id: str | None = None
    related_entity_type: str | None = None
    bytes_status: str = "INCLUDED"  # INCLUDED | catalog-only


@dataclass
class ExportResult:
    export_root: Path
    zip_path: Path | None
    created_at: str
    counts: dict[str, int]
    files: list[dict[str, Any]] = field(default_factory=list)
    job_message: str = ""


def resolve_export_parent(explicit: str | Path | None = None) -> Path:
    """Destination parent directory — config/env or owner-provided path (D7)."""
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip()).expanduser()
    raw = (os.environ.get("MEMORYBOX_EXPORT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    if settings.allow_dev_defaults:
        return Path(tempfile.gettempdir()) / "memorybox_exports"
    raise ExportError(
        "MEMORYBOX_EXPORT_DIR is required "
        "(or pass destination; or MEMORYBOX_ALLOW_DEV_DEFAULTS=1 for desktop prove only)"
    )


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    # date / time without importing separately — duck-type isoformat
    iso = getattr(obj, "isoformat", None)
    if callable(iso):
        try:
            return iso()
        except Exception:
            pass
    raise TypeError(f"not JSON serializable: {type(obj)!r}")


def _row_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
        elif hasattr(v, "isoformat") and not isinstance(v, (str, bytes)):
            try:
                out[k] = v.isoformat()
            except Exception:
                out[k] = str(v)
        else:
            out[k] = v
    return out


def _sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_bytes(
    root: Path,
    rel: str,
    data: bytes,
    *,
    related_entity_id: str | None = None,
    related_entity_type: str | None = None,
    media_type: str | None = None,
) -> FileEntry:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    digest = _sha256_bytes(data)
    return FileEntry(
        relative_path=rel.replace("\\", "/"),
        byte_size=len(data),
        sha256=digest,
        media_type=media_type or guess_media_type(path),
        related_entity_id=related_entity_id,
        related_entity_type=related_entity_type,
    )


def _write_text(
    root: Path,
    rel: str,
    text: str,
    *,
    related_entity_id: str | None = None,
    related_entity_type: str | None = None,
    media_type: str | None = None,
) -> FileEntry:
    return _write_bytes(
        root,
        rel,
        text.encode("utf-8"),
        related_entity_id=related_entity_id,
        related_entity_type=related_entity_type,
        media_type=media_type,
    )


def _write_jsonl(
    root: Path,
    rel: str,
    rows: list[dict[str, Any]],
    *,
    related_entity_type: str | None = None,
) -> FileEntry:
    buf = io.StringIO()
    for row in rows:
        buf.write(json.dumps(row, default=_json_default, ensure_ascii=False))
        buf.write("\n")
    return _write_text(
        root,
        rel,
        buf.getvalue(),
        related_entity_type=related_entity_type,
        media_type="application/x-ndjson",
    )


def _write_csv(
    root: Path,
    rel: str,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> FileEntry:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat = {}
        for k in fieldnames:
            v = row.get(k)
            if isinstance(v, (dict, list)):
                flat[k] = json.dumps(v, default=_json_default, ensure_ascii=False)
            elif v is None:
                flat[k] = ""
            else:
                flat[k] = v
        writer.writerow(flat)
    return _write_text(root, rel, buf.getvalue(), media_type="text/csv")


def _copy_original(
    root: Path,
    src: Path,
    rel: str,
    *,
    related_entity_id: str | None,
    related_entity_type: str | None,
) -> FileEntry | None:
    if not src.is_file():
        return None
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    digest, size = _sha256_file(dest)
    return FileEntry(
        relative_path=rel.replace("\\", "/"),
        byte_size=size,
        sha256=digest,
        media_type=guess_media_type(dest),
        related_entity_id=related_entity_id,
        related_entity_type=related_entity_type,
    )


def _fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    rows = conn.execute(sql, params).fetchall()
    return [_row_dict(r) or {} for r in rows]


def _build_stories(conn: Any) -> list[dict[str, Any]]:
    stories = _fetch_all(
        conn,
        """
        SELECT s.*, p.display_name AS narrator_display_name
        FROM stories s
        LEFT JOIN people p ON p.id = s.narrator_person_id
        ORDER BY s.created_at
        """,
    )
    versions = _fetch_all(
        conn,
        """
        SELECT * FROM story_versions
        ORDER BY story_id, version
        """,
    )
    by_story: dict[str, list[dict[str, Any]]] = {}
    for v in versions:
        by_story.setdefault(str(v["story_id"]), []).append(v)
    out: list[dict[str, Any]] = []
    for s in stories:
        sid = str(s["id"])
        current = int(s.get("current_version") or 0)
        vers = []
        for v in by_story.get(sid, []):
            ver_num = int(v["version"])
            vers.append(
                {
                    **v,
                    "version_id": v["id"],
                    "version_number": ver_num,
                    "status": "current" if ver_num == current else "superseded",
                    "is_current": ver_num == current,
                    "narrator_person_id": s.get("narrator_person_id"),
                    "narrator_display_name": s.get("narrator_display_name"),
                    "provenance": {
                        "actor_key": v.get("actor_key"),
                        "note": v.get("note"),
                        "confidence_at_save": v.get("confidence_at_save"),
                        "kind": "owner_narrator_recollection",
                    },
                }
            )
        current_body = next((x for x in vers if x["is_current"]), None)
        out.append(
            {
                "story_id": sid,
                "title": s.get("title"),
                "status": s.get("status"),
                "narrator_person_id": s.get("narrator_person_id"),
                "narrator_display_name": s.get("narrator_display_name"),
                "current_version": current,
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
                "current": current_body,
                "versions": vers,
            }
        )
    return out


def _build_journals(conn: Any) -> list[dict[str, Any]]:
    journals = _fetch_all(
        conn,
        """
        SELECT j.*, p.display_name AS author_display_name
        FROM journal_entries j
        LEFT JOIN people p ON p.id = j.author_person_id
        ORDER BY j.created_at
        """,
    )
    versions = _fetch_all(
        conn,
        "SELECT * FROM journal_versions ORDER BY journal_id, version",
    )
    by_j: dict[str, list[dict[str, Any]]] = {}
    for v in versions:
        by_j.setdefault(str(v["journal_id"]), []).append(v)
    out: list[dict[str, Any]] = []
    for j in journals:
        jid = str(j["id"])
        current = int(j.get("current_version") or 0)
        vers = []
        for v in by_j.get(jid, []):
            ver_num = int(v["version"])
            vers.append(
                {
                    **v,
                    "version_id": v["id"],
                    "version_number": ver_num,
                    "status": "current" if ver_num == current else "superseded",
                    "is_current": ver_num == current,
                    "author_person_id": j.get("author_person_id"),
                    "author_display_name": j.get("author_display_name"),
                    "provenance": {
                        "actor_key": v.get("actor_key"),
                        "note": v.get("note"),
                        "kind": "owner_journal",
                    },
                }
            )
        current_body = next((x for x in vers if x["is_current"]), None)
        out.append(
            {
                "journal_id": jid,
                "title": j.get("title"),
                "status": j.get("status"),
                "author_person_id": j.get("author_person_id"),
                "author_display_name": j.get("author_display_name"),
                "current_version": current,
                "channel": j.get("channel"),
                "recorded_at": j.get("recorded_at"),
                "captured_at": j.get("captured_at"),
                "created_at": j.get("created_at"),
                "updated_at": j.get("updated_at"),
                "current": current_body,
                "versions": vers,
            }
        )
    return out


def _build_gc_responses(conn: Any) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT
            r.*,
            c.title AS campaign_title,
            c.status AS campaign_status,
            c.owner_person_id,
            q.body_text AS question_body,
            q.sort_order AS question_sort_order,
            ct.display_name AS respondent_display_name,
            ct.email AS respondent_email,
            ct.people_id AS respondent_people_id,
            d.correlation_token AS delivery_correlation_token,
            d.outbound_message_id AS delivery_outbound_message_id,
            d.sent_at AS delivery_sent_at,
            d.status AS delivery_status,
            d.channel AS delivery_channel
        FROM guided_capture_responses r
        JOIN guided_capture_campaigns c ON c.id = r.campaign_id
        JOIN guided_capture_questions q ON q.id = r.question_id
        JOIN guided_capture_contacts ct ON ct.id = r.respondent_contact_id
        LEFT JOIN guided_capture_deliveries d ON d.id = r.delivery_id
        ORDER BY r.received_at
        """,
    )


def _build_evidence_refs(conn: Any) -> list[dict[str, Any]]:
    rows = _fetch_all(
        conn,
        """
        SELECT
            e.id AS evidence_id,
            e.evidence_kind,
            e.summary,
            e.span_start,
            e.span_end,
            e.payload_json,
            e.created_at,
            s.id AS source_id,
            s.source_kind,
            s.label AS source_label,
            s.uri AS source_uri,
            s.content_hash AS source_content_hash,
            s.authoritative_original_mode,
            m.id AS media_object_id,
            m.media_kind,
            m.storage_mode,
            m.uri AS media_uri,
            m.content_hash AS media_content_hash,
            m.mime_type,
            m.captured_at AS media_captured_at,
            m.metadata_json AS media_metadata_json,
            mr.provider_key,
            mr.external_id,
            mr.metadata_json AS media_ref_metadata_json
        FROM evidence e
        LEFT JOIN sources s ON s.id = e.source_id
        LEFT JOIN media_objects m ON m.id = e.media_object_id
        LEFT JOIN media_refs mr ON mr.media_object_id = m.id
        ORDER BY e.created_at
        """,
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        storage = (r.get("storage_mode") or "").strip()
        mode = (r.get("authoritative_original_mode") or "").strip()
        included = storage == "memorybox_managed" or mode == "memorybox_managed"
        meta = r.get("media_ref_metadata_json") or {}
        if not isinstance(meta, dict):
            meta = {}
        media_meta = r.get("media_metadata_json") or {}
        if not isinstance(media_meta, dict):
            media_meta = {}
        original_filename = (
            meta.get("original_filename")
            or meta.get("originalFileName")
            or media_meta.get("original_filename")
            or media_meta.get("originalFileName")
        )
        out.append(
            {
                "evidence_id": r.get("evidence_id"),
                "evidence_kind": r.get("evidence_kind"),
                "summary": r.get("summary"),
                "provider_source_type": r.get("provider_key") or r.get("source_kind"),
                "provider_external_id": r.get("external_id"),
                "original_filename": original_filename,
                "original_uri_or_path": r.get("media_uri") or r.get("source_uri"),
                "date_time": r.get("media_captured_at") or r.get("created_at"),
                "related_mb_entities": {
                    "evidence_id": r.get("evidence_id"),
                    "source_id": r.get("source_id"),
                    "media_object_id": r.get("media_object_id"),
                },
                "bytes_status": "INCLUDED" if included else "EXTERNALLY_REFERENCED",
                "mime_type": r.get("mime_type"),
                "span_start": r.get("span_start"),
                "span_end": r.get("span_end"),
                "payload_json": r.get("payload_json"),
                "source_label": r.get("source_label"),
                "content_hash": r.get("media_content_hash") or r.get("source_content_hash"),
            }
        )
    # Artifact evidence_ref representations (metadata-only links)
    art_refs = _fetch_all(
        conn,
        """
        SELECT ar.*, a.label AS artifact_label
        FROM artifact_representations ar
        JOIN artifacts a ON a.id = ar.artifact_id
        WHERE ar.representation_kind = 'evidence_ref'
        ORDER BY ar.created_at
        """,
    )
    for ar in art_refs:
        out.append(
            {
                "evidence_id": ar.get("evidence_id"),
                "evidence_kind": "artifact_evidence_ref",
                "summary": f"Artifact evidence ref: {ar.get('artifact_label')}",
                "provider_source_type": "artifact_evidence_ref",
                "provider_external_id": ar.get("evidence_id"),
                "original_filename": ar.get("original_filename"),
                "original_uri_or_path": ar.get("uri"),
                "date_time": ar.get("created_at"),
                "related_mb_entities": {
                    "artifact_id": ar.get("artifact_id"),
                    "representation_id": ar.get("id"),
                    "evidence_id": ar.get("evidence_id"),
                },
                "bytes_status": "EXTERNALLY_REFERENCED",
                "mime_type": ar.get("mime_type"),
            }
        )
    return out


def _readme_text(*, created_at: str, counts: dict[str, int]) -> str:
    return f"""# MemoryBox export package

**memorybox_export_format:** {EXPORT_FORMAT_VERSION}  
**Export timestamp:** {created_at}  
**MemoryBox application version:** {app_version}

## What this is

This is a **minimum viable exit package** of MemoryBox-created knowledge and
MemoryBox-managed original files. It is designed so a family can leave with
their own data without a vendor subscription or portal.

## Layout

- `README.md` — this file
- `MANIFEST.json` — format version, inventories, SHA-256 integrity for packaged files
- `tables/` — machine-readable knowledge (JSONL/CSV), including retained version history
- `originals/` — bytes MemoryBox stores (audio, MB-managed artifact files). **Not** a full Immich/HVRT library

## Limitations (read carefully)

- Externally managed photo/video libraries (Immich, HVRT, Takeout, etc.) are **not**
  bulk-copied. See `tables/evidence_refs.jsonl` where `bytes_status` is
  `EXTERNALLY_REFERENCED`. Those originals may be absent from this package.
- This package does **not** claim round-trip import/restore into MemoryBox
  (import-back is later portability work).
- Open the folder directly; an optional `.zip` (if present) is only a transport copy of this folder.

## Integrity

Every packaged content file listed under `MANIFEST.json` → `files` has:

- relative path
- byte size
- SHA-256
- media/type
- related MemoryBox entity id when applicable

Verify a file:

```
# example (PowerShell)
Get-FileHash -Algorithm SHA256 .\\originals\\audio\\example.webm
```

Compare to the matching `sha256` in `MANIFEST.json`.

## Counts at export

{json.dumps(counts, indent=2)}

## Opening files

- JSONL: one JSON object per line (Stories/Journals include `current` + `versions`)
- CSV: People and graph tables (include superseded rows when MemoryBox retained them)
- Guided Capture responses include campaign, question, respondent, and delivery context
  so testimony is understandable outside MemoryBox
"""


def build_export_package(
    *,
    destination_parent: str | Path | None = None,
    make_zip: bool = False,
    progress: Any | None = None,
) -> ExportResult:
    """
    Build export format 1 under destination_parent / memorybox_export_<stamp>_<id>/.

    Does not require Immich/HVRT to be available.
    """
    parent = resolve_export_parent(destination_parent)
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError(f"cannot create export destination: {parent}: {exc}") from exc

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_id = uuid4().hex[:8]
    root = parent / f"memorybox_export_{stamp}_{export_id}"
    try:
        root.mkdir(parents=False, exist_ok=False)
    except OSError as exc:
        raise ExportError(f"cannot create export root {root}: {exc}") from exc

    def _prog(msg: str, pct: float | None = None) -> None:
        if progress is not None:
            progress(msg, pct)

    created_at = datetime.now(timezone.utc).isoformat()
    entries: list[FileEntry] = []
    counts: dict[str, int] = {}

    try:
        _prog("Reading domain knowledge", 5.0)
        with connection() as conn:
            stories = _build_stories(conn)
            journals = _build_journals(conn)
            people = _fetch_all(conn, "SELECT * FROM people ORDER BY created_at")
            provider_identities = _fetch_all(
                conn, "SELECT * FROM provider_identities ORDER BY created_at"
            )
            aliases = _fetch_all(conn, "SELECT * FROM person_aliases ORDER BY created_at")
            facts = _fetch_all(conn, "SELECT * FROM person_facts ORDER BY created_at")
            contacts = _fetch_all(
                conn, "SELECT * FROM person_contact_points ORDER BY created_at"
            )
            rel_assertions = _fetch_all(
                conn,
                "SELECT * FROM person_relationship_assertions ORDER BY created_at",
            )
            assertions = _fetch_all(conn, "SELECT * FROM assertions ORDER BY created_at")
            relationships = _fetch_all(
                conn, "SELECT * FROM relationships ORDER BY created_at"
            )
            shared_events = _fetch_all(
                conn, "SELECT * FROM shared_life_events ORDER BY created_at"
            )
            gc_contacts = _fetch_all(
                conn, "SELECT * FROM guided_capture_contacts ORDER BY created_at"
            )
            gc_campaigns = _fetch_all(
                conn, "SELECT * FROM guided_capture_campaigns ORDER BY created_at"
            )
            gc_questions = _fetch_all(
                conn,
                "SELECT * FROM guided_capture_questions ORDER BY campaign_id, sort_order",
            )
            gc_deliveries = _fetch_all(
                conn, "SELECT * FROM guided_capture_deliveries ORDER BY created_at"
            )
            gc_responses = _build_gc_responses(conn)
            artifacts = _fetch_all(conn, "SELECT * FROM artifacts ORDER BY created_at")
            artifact_reps = _fetch_all(
                conn, "SELECT * FROM artifact_representations ORDER BY created_at"
            )
            artifact_meta = _fetch_all(
                conn,
                "SELECT * FROM artifact_metadata_revisions ORDER BY artifact_id, revision",
            )
            evidence_refs = _build_evidence_refs(conn)

        counts = {
            "stories": len(stories),
            "story_versions": sum(len(s.get("versions") or []) for s in stories),
            "journals": len(journals),
            "journal_versions": sum(len(j.get("versions") or []) for j in journals),
            "people": len(people),
            "person_relationship_assertions": len(rel_assertions),
            "assertions": len(assertions),
            "guided_capture_responses": len(gc_responses),
            "guided_capture_campaigns": len(gc_campaigns),
            "artifacts": len(artifacts),
            "evidence_refs": len(evidence_refs),
        }

        _prog("Writing tables", 25.0)
        entries.append(
            _write_jsonl(root, "tables/stories.jsonl", stories, related_entity_type="story")
        )
        entries.append(
            _write_jsonl(
                root, "tables/journals.jsonl", journals, related_entity_type="journal"
            )
        )
        entries.append(
            _write_csv(
                root,
                "tables/people.csv",
                people,
                [
                    "id",
                    "display_name",
                    "status",
                    "merged_into_id",
                    "notes",
                    "attributes_json",
                    "created_at",
                    "updated_at",
                ],
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/provider_identities.jsonl",
                provider_identities,
                related_entity_type="provider_identity",
            )
        )
        entries.append(
            _write_jsonl(
                root, "tables/person_aliases.jsonl", aliases, related_entity_type="person_alias"
            )
        )
        entries.append(
            _write_jsonl(
                root, "tables/person_facts.jsonl", facts, related_entity_type="person_fact"
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/person_contact_points.jsonl",
                contacts,
                related_entity_type="person_contact",
            )
        )
        # Retained history lives as superseded rows in these tables (no invented history table).
        entries.append(
            _write_csv(
                root,
                "tables/relationships.csv",
                relationships,
                [
                    "id",
                    "relationship_kind",
                    "from_type",
                    "from_id",
                    "to_type",
                    "to_id",
                    "label",
                    "status",
                    "attributes_json",
                    "created_at",
                    "updated_at",
                ],
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/person_relationship_assertions.jsonl",
                rel_assertions,
                related_entity_type="person_relationship_assertion",
            )
        )
        entries.append(
            _write_csv(
                root,
                "tables/assertions.csv",
                assertions,
                [
                    "id",
                    "assertion_kind",
                    "subject_type",
                    "subject_id",
                    "predicate",
                    "object_type",
                    "object_id",
                    "statement",
                    "status",
                    "confidence",
                    "authority",
                    "provenance_json",
                    "created_at",
                    "updated_at",
                ],
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/shared_life_events.jsonl",
                shared_events,
                related_entity_type="shared_life_event",
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/guided_capture_contacts.jsonl",
                gc_contacts,
                related_entity_type="guided_capture_contact",
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/guided_capture_campaigns.jsonl",
                gc_campaigns,
                related_entity_type="guided_capture_campaign",
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/guided_capture_questions.jsonl",
                gc_questions,
                related_entity_type="guided_capture_question",
            )
        )
        # Delivery references only — not a second Gmail archive.
        delivery_export = []
        for d in gc_deliveries:
            delivery_export.append(
                {
                    "id": d.get("id"),
                    "campaign_id": d.get("campaign_id"),
                    "question_id": d.get("question_id"),
                    "respondent_contact_id": d.get("respondent_contact_id"),
                    "channel": d.get("channel"),
                    "scheduled_for": d.get("scheduled_for"),
                    "sent_at": d.get("sent_at"),
                    "status": d.get("status"),
                    "correlation_token": d.get("correlation_token"),
                    "outbound_message_id": d.get("outbound_message_id"),
                    "thread_id": d.get("thread_id"),
                    "fail_detail": d.get("fail_detail"),
                    "preserved_raw_uri": d.get("preserved_raw_uri"),
                    "provenance_json": d.get("provenance_json"),
                    "created_at": d.get("created_at"),
                    "note": "Transport/source reference only — not a full email archive",
                }
            )
        entries.append(
            _write_jsonl(
                root,
                "tables/guided_capture_deliveries.jsonl",
                delivery_export,
                related_entity_type="guided_capture_delivery",
            )
        )
        # First-class GC responses with context fields already joined.
        response_export = []
        for r in gc_responses:
            response_export.append(
                {
                    "response_id": r.get("id"),
                    "campaign_id": r.get("campaign_id"),
                    "campaign_title": r.get("campaign_title"),
                    "campaign_status": r.get("campaign_status"),
                    "question_id": r.get("question_id"),
                    "question_body": r.get("question_body"),
                    "question_sort_order": r.get("question_sort_order"),
                    "delivery_id": r.get("delivery_id"),
                    "outbound_delivery_reference": {
                        "delivery_id": r.get("delivery_id"),
                        "correlation_token": r.get("delivery_correlation_token"),
                        "outbound_message_id": r.get("delivery_outbound_message_id"),
                        "sent_at": r.get("delivery_sent_at"),
                        "status": r.get("delivery_status"),
                        "channel": r.get("delivery_channel"),
                    },
                    "respondent_contact_id": r.get("respondent_contact_id"),
                    "respondent_display_name": r.get("respondent_display_name"),
                    "respondent_email": r.get("respondent_email"),
                    "respondent_people_id": r.get("respondent_people_id"),
                    "received_at": r.get("received_at"),
                    "channel": r.get("channel"),
                    "extracted_text": r.get("extracted_text"),
                    "transcript_text": r.get("transcript_text"),
                    "transcript_versions": r.get("transcript_versions"),
                    "stt_status": r.get("stt_status"),
                    "credibility": r.get("credibility"),
                    "credibility_set_at": r.get("credibility_set_at"),
                    "credibility_set_by": r.get("credibility_set_by"),
                    "credibility_history": r.get("credibility_history"),
                    "review_status": r.get("review_status"),
                    "audio_uri_source": r.get("audio_uri"),
                    "resulting_knowledge_json": r.get("resulting_knowledge_json"),
                    "inbound_message_id": r.get("inbound_message_id"),
                    "preserved_raw_uri": r.get("preserved_raw_uri"),
                    "provenance_json": r.get("provenance_json"),
                    "created_at": r.get("created_at"),
                    "updated_at": r.get("updated_at"),
                }
            )
        entries.append(
            _write_jsonl(
                root,
                "tables/guided_capture_responses.jsonl",
                response_export,
                related_entity_type="guided_capture_response",
            )
        )
        entries.append(
            _write_csv(
                root,
                "tables/artifacts.csv",
                artifacts,
                [
                    "id",
                    "kind",
                    "label",
                    "description",
                    "status",
                    "current_metadata_revision",
                    "unresolved_context_json",
                    "created_at",
                    "updated_at",
                ],
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/artifact_representations.jsonl",
                artifact_reps,
                related_entity_type="artifact_representation",
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/artifact_metadata_revisions.jsonl",
                artifact_meta,
                related_entity_type="artifact_metadata_revision",
            )
        )
        entries.append(
            _write_jsonl(
                root,
                "tables/evidence_refs.jsonl",
                evidence_refs,
                related_entity_type="evidence",
            )
        )

        _prog("Copying MB-managed originals", 55.0)
        originals_copied = 0
        # Story / journal version audio
        for s in stories:
            for v in s.get("versions") or []:
                src = uri_or_path_to_file(v.get("audio_uri"))
                if not src:
                    continue
                rel = f"originals/audio/story_{s['story_id']}_v{v['version_number']}{src.suffix}"
                ent = _copy_original(
                    root,
                    src,
                    rel,
                    related_entity_id=str(v.get("version_id") or s["story_id"]),
                    related_entity_type="story_version",
                )
                if ent:
                    entries.append(ent)
                    originals_copied += 1
        for j in journals:
            for v in j.get("versions") or []:
                src = uri_or_path_to_file(v.get("audio_uri"))
                if not src:
                    continue
                rel = f"originals/audio/journal_{j['journal_id']}_v{v['version_number']}{src.suffix}"
                ent = _copy_original(
                    root,
                    src,
                    rel,
                    related_entity_id=str(v.get("version_id") or j["journal_id"]),
                    related_entity_type="journal_version",
                )
                if ent:
                    entries.append(ent)
                    originals_copied += 1

        for r in gc_responses:
            rid = str(r.get("id"))
            src = uri_or_path_to_file(r.get("audio_uri"))
            if src:
                rel = f"originals/audio/gc_response_{rid}{src.suffix}"
                ent = _copy_original(
                    root,
                    src,
                    rel,
                    related_entity_id=rid,
                    related_entity_type="guided_capture_response",
                )
                if ent:
                    entries.append(ent)
                    originals_copied += 1

        for ar in artifact_reps:
            if (ar.get("representation_kind") or "") == "evidence_ref":
                continue
            uri = ar.get("uri")
            src = uri_or_path_to_file(uri) if uri else None
            if src is None and uri:
                p = Path(str(uri))
                src = p if p.is_file() else None
            if not src:
                continue
            aid = str(ar.get("artifact_id"))
            rid = str(ar.get("id"))
            safe = Path(ar.get("original_filename") or src.name).name
            rel = f"originals/artifacts/{aid}/{rid}_{safe}"
            ent = _copy_original(
                root,
                src,
                rel,
                related_entity_id=rid,
                related_entity_type="artifact_representation",
            )
            if ent:
                entries.append(ent)
                originals_copied += 1

        counts["mb_managed_originals_copied"] = originals_copied

        _prog("Writing README", 80.0)
        entries.append(
            _write_text(
                root,
                "README.md",
                _readme_text(created_at=created_at, counts=counts),
                media_type="text/markdown",
            )
        )

        _prog("Writing MANIFEST", 90.0)
        # files[] covers every packaged content file (tables, originals, README).
        # MANIFEST.json is written last; its own SHA-256 is in MANIFEST.sha256.json
        # so the catalog is not self-referential.
        file_records = [
            {
                "relative_path": e.relative_path,
                "byte_size": e.byte_size,
                "sha256": e.sha256,
                "media_type": e.media_type,
                "related_entity_id": e.related_entity_id,
                "related_entity_type": e.related_entity_type,
                "bytes_status": e.bytes_status,
            }
            for e in entries
        ]
        manifest = {
            "memorybox_export_format": EXPORT_FORMAT_VERSION,
            "export_timestamp": created_at,
            "memorybox_application_version": app_version,
            "package_limitations": [
                "Externally managed Immich/HVRT/Takeout libraries are referenced, not bulk-copied",
                "Round-trip import/restore is out of scope for this package",
                "Optional ZIP (if present) is a derivative of this folder",
            ],
            "counts": counts,
            "files": file_records,
        }
        manifest_path = root / "MANIFEST.json"
        manifest_path.write_bytes(
            json.dumps(manifest, indent=2, default=_json_default).encode("utf-8")
        )
        man_digest, man_size = _sha256_file(manifest_path)
        (root / "MANIFEST.sha256.json").write_text(
            json.dumps(
                {
                    "relative_path": "MANIFEST.json",
                    "byte_size": man_size,
                    "sha256": man_digest,
                    "media_type": "application/json",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        zip_path = None
        if make_zip:
            _prog("Creating optional ZIP", 95.0)
            zip_path = parent / f"{root.name}.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for dirpath, _, filenames in os.walk(root):
                    for name in filenames:
                        full = Path(dirpath) / name
                        arc = full.relative_to(root).as_posix()
                        zf.write(full, arcname=f"{root.name}/{arc}")

        _prog("Export complete", 100.0)
        return ExportResult(
            export_root=root,
            zip_path=zip_path,
            created_at=created_at,
            counts=counts,
            files=file_records,
            job_message=f"Export ready at {root}",
        )
    except ExportError:
        raise
    except OSError as exc:
        raise ExportError(f"export failed (disk/path): {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ExportError(f"export failed: {exc}") from exc
