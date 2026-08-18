"""Serve email MIME attachments and copy them into MemoryBox Artifacts (not Immich)."""
from __future__ import annotations

import json
import mimetypes
from typing import Any
from uuid import UUID

from memorybox.ingest.sms_attach_cache import media_object_path
from memorybox.ingest.store import get_evidence


class EmailAttachError(Exception):
    pass


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]


def load_email_attachment(evidence_id: str, index: int = 0) -> dict[str, Any]:
    try:
        eid = UUID(str(evidence_id).strip())
    except (ValueError, TypeError, AttributeError) as exc:
        raise EmailAttachError("invalid evidence id") from exc
    row = get_evidence(eid)
    if not row:
        raise EmailAttachError("evidence not found")
    payload = _payload(row)
    if str(payload.get("evidence_channel") or "").lower() != "email":
        raise EmailAttachError("not an email evidence row")
    atts = _attachments(payload)
    if index < 0 or index >= len(atts):
        raise EmailAttachError("attachment index out of range")
    att = atts[index]
    mid = str(att.get("media_object_id") or "").strip()
    path = media_object_path(mid) if mid else None
    filename = str(att.get("filename") or "attachment.bin")
    mime = str(att.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream")
    return {
        "evidence_id": str(eid),
        "index": index,
        "filename": filename,
        "mime_type": mime,
        "kind": att.get("kind"),
        "disposition": att.get("disposition"),
        "content_id": att.get("content_id"),
        "byte_size": att.get("byte_size"),
        "content_hash": att.get("content_hash"),
        "media_object_id": mid or None,
        "bytes_present": bool(path),
        "bytes_ingested": bool(att.get("bytes_ingested")),
        "promoted_to_immich": False,
        "is_artifact": False,
        "person_ids": list(payload.get("person_ids") or []),
        "import_path": (payload.get("source_coverage") or {}).get("import_path")
        or payload.get("source_locator"),
    }


def read_email_attachment_bytes(evidence_id: str, index: int = 0) -> tuple[bytes, str, str]:
    info = load_email_attachment(evidence_id, index)
    mid = info.get("media_object_id")
    path = media_object_path(str(mid)) if mid else None
    if path is None:
        raise EmailAttachError(
            "Attachment metadata is on the message, but bytes were not stored at ingest."
        )
    return path.read_bytes(), str(info.get("mime_type") or "application/octet-stream"), str(
        info.get("filename") or "attachment.bin"
    )


def add_email_attachment_to_mb_library(evidence_id: str, index: int = 0) -> dict[str, Any]:
    """Explicit Artifact copy only. Never writes Immich. Not automatic."""
    from memorybox.artifact import (
        ArtifactServiceError,
        add_evidence_ref_representation,
        add_mb_managed_representation,
        create_artifact,
    )

    info = load_email_attachment(evidence_id, index)
    data, mime, filename = read_email_attachment_bytes(evidence_id, index)
    kind = "photograph_of_object" if mime.startswith("image/") else "other"
    try:
        art = create_artifact(
            kind=kind,
            label=filename,
            description=f"Email attachment from evidence {info['evidence_id']}",
            person_ids=info.get("person_ids") or None,
            actor_key="email_to_mb_library",
        )
        add_mb_managed_representation(
            art.id,
            data=data,
            filename=filename,
            content_type=mime,
            label=filename,
        )
        add_evidence_ref_representation(
            art.id, evidence_id=info["evidence_id"], label=filename
        )
    except ArtifactServiceError as exc:
        raise EmailAttachError(str(exc)) from exc
    return {
        "ok": True,
        "immich_write": False,
        "automatic_artifact": False,
        "artifact_id": art.id,
        "href": f"/artifact/ui?id={art.id}",
        "filename": filename,
        "mime_type": mime,
    }
