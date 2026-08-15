"""Serve SMS/iMessage attachments and copy them into MemoryBox (not Immich)."""
from __future__ import annotations

import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ingest.comms_sms import default_sms_export_path
from memorybox.ingest.store import get_evidence

_UUID_IN_NAME = re.compile(
    r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})"
)


class SmsAttachError(Exception):
    pass


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
    if atts:
        return atts
    meta = payload.get("source_metadata") or {}
    if not isinstance(meta, dict):
        return []
    raw = str(meta.get("Attachment") or meta.get("attachment") or "").strip()
    if not raw:
        return []
    kind = str(meta.get("Attachment type") or meta.get("attachment_type") or "").strip()
    return [
        {
            "filename": Path(raw).name,
            "source_ref": raw,
            "attachment_type": kind or None,
        }
    ]


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    extra = (os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR") or "").strip()
    if extra:
        roots.append(Path(extra))
    export = default_sms_export_path()
    if export is not None:
        roots.append(export.parent)
    src = (os.environ.get("MEMORYBOX_SOURCES_ROOT") or "").strip()
    if src:
        roots.append(Path(src) / "sms")
    roots.append(Path(r"\\media-server\photos\MemoryBox\Sources\sms"))
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _dir_candidates(root: Path, name: str) -> list[Path]:
    hits = [
        root / name,
        root / "attachments" / name,
        root / "Attachments" / name,
        root / "SMS Attachments" / name,
        root / "iMessage Attachments" / name,
    ]
    try:
        if not root.is_dir():
            return hits
        for child in root.iterdir():
            if not child.is_dir():
                continue
            hits.append(child / name)
            hits.append(child / "attachments" / name)
            hits.append(child / "Attachments" / name)
            try:
                for grand in child.iterdir():
                    if grand.is_dir():
                        hits.append(grand / name)
                        hits.append(grand / "attachments" / name)
                        hits.append(grand / "Attachments" / name)
            except OSError:
                continue
    except OSError:
        return hits
    return hits


def _name_matches(found: str, wanted: str, uuid: str | None) -> bool:
    a = found.casefold()
    b = wanted.casefold()
    if a == b:
        return True
    if a.endswith(b) or b.endswith(a):
        return True
    if uuid and uuid.casefold() in a:
        return True
    return False


def _walk_match(root: Path, name: str, uuid: str | None, *, depth: int = 3) -> Path | None:
    """Bounded directory walk — do not recurse a whole NAS share."""
    try:
        if not root.is_dir():
            return None
    except OSError:
        return None
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        cur, level = stack.pop()
        try:
            children = list(cur.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                if child.is_file() and _name_matches(child.name, name, uuid):
                    return child
                if child.is_dir() and level < depth:
                    stack.append((child, level + 1))
            except OSError:
                continue
    return None


def resolve_attachment_file(att: dict[str, Any]) -> Path | None:
    for key in ("resolved_path", "source_ref", "filename"):
        raw = str(att.get(key) or "").strip()
        if not raw:
            continue
        p = Path(raw)
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    name = Path(str(att.get("filename") or att.get("source_ref") or "")).name
    if not name:
        return None
    uuid_m = _UUID_IN_NAME.search(name)
    uuid = uuid_m.group(1) if uuid_m else None
    for root in _search_roots():
        try:
            if not root.exists():
                continue
        except OSError:
            continue
        for hit in _dir_candidates(root, name):
            try:
                if hit.is_file():
                    return hit
            except OSError:
                continue
        found = _walk_match(root, name, uuid, depth=3)
        if found is not None:
            return found
    return None


def load_sms_attachment(evidence_id: str, index: int = 0) -> dict[str, Any]:
    try:
        eid = UUID(str(evidence_id).strip())
    except (ValueError, TypeError, AttributeError) as exc:
        raise SmsAttachError("evidence_id must be a UUID") from exc
    row = get_evidence(eid)
    if not row:
        raise SmsAttachError("evidence not found")
    payload = _payload(row)
    atts = _attachments(payload)
    if index < 0 or index >= len(atts):
        raise SmsAttachError("attachment index out of range")
    att = atts[index]
    path = resolve_attachment_file(att)
    filename = str(att.get("filename") or (path.name if path else "attachment"))
    mime = (
        mimetypes.guess_type(filename)[0]
        or str(att.get("mime_type") or "")
        or "application/octet-stream"
    )
    kind = str(att.get("attachment_type") or "").lower()
    if kind in {"image", "jpeg", "jpg", "png", "gif", "heic"} and not mime.startswith("image/"):
        mime = "image/jpeg"
    return {
        "evidence_id": str(eid),
        "index": index,
        "filename": filename,
        "mime_type": mime,
        "path": str(path) if path else None,
        "bytes_present": bool(path and path.is_file()),
        "attachment": att,
        "person_ids": [str(p) for p in (payload.get("person_ids") or []) if p],
        "payload": payload,
    }


def read_sms_attachment_bytes(evidence_id: str, index: int = 0) -> tuple[bytes, str, str]:
    info = load_sms_attachment(evidence_id, index)
    if not info["bytes_present"] or not info["path"]:
        raise SmsAttachError(
            f"Attachment file not found next to the SMS export: {info['filename']}"
        )
    data = Path(info["path"]).read_bytes()
    if not data:
        raise SmsAttachError("attachment file is empty")
    return data, str(info["mime_type"]), str(info["filename"])


def add_sms_attachment_to_mb_library(evidence_id: str, index: int = 0) -> dict[str, Any]:
    """Copy attachment bytes into MemoryBox Artifact storage. Never writes Immich."""
    from memorybox.artifact import (
        ArtifactServiceError,
        add_evidence_ref_representation,
        add_mb_managed_representation,
        create_artifact,
    )

    info = load_sms_attachment(evidence_id, index)
    data, mime, filename = read_sms_attachment_bytes(evidence_id, index)
    kind = "photograph_of_object" if mime.startswith("image/") else "other"
    try:
        art = create_artifact(
            kind=kind,
            label=filename,
            description=f"SMS attachment from evidence {info['evidence_id']}",
            person_ids=info.get("person_ids") or None,
            actor_key="sms_to_mb_library",
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
        raise SmsAttachError(str(exc)) from exc
    return {
        "ok": True,
        "immich_write": False,
        "artifact_id": art.id,
        "href": f"/artifact/ui?id={art.id}",
        "filename": filename,
        "mime_type": mime,
    }
