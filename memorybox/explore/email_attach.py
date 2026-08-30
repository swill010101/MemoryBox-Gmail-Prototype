"""Serve email MIME attachments and copy them into MemoryBox Artifacts (not Immich)."""
from __future__ import annotations

import json
import mimetypes
import re
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


_SUBJECT_AS_PERSON = re.compile(r"(?i)^(re|fw|fwd)\s*:")


def split_quoted_email(text: str) -> list[dict[str, str | None]]:
    """Split one MIME body into quoted turns. Does not invent RFC thread members."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return []
    splitter = re.compile(
        r"(?im)^("
        r"On .{8,400}? wrote:"
        r"|-{2,}\s*Original Message\s*-{2,}"
        r"|-{2,}\s*Forwarded message\s*-{2,}"
        r"|Begin forwarded message:"
        r"|_{8,}"
        r")\s*$"
    )
    parts = splitter.split(raw)
    turns: list[dict[str, str | None]] = []
    lead = (parts[0] or "").strip()
    if lead:
        turns.append({"header": None, "from": None, "body": lead})
    i = 1
    while i < len(parts):
        header = (parts[i] or "").strip()
        body = (parts[i + 1] if i + 1 < len(parts) else "") or ""
        turns.append(
            {
                "header": header,
                "from": _speaker_from_quote_header(header),
                "body": body.strip(),
            }
        )
        i += 2
    return turns or [{"header": None, "from": None, "body": raw}]


def _speaker_from_quote_header(header: str) -> str | None:
    if not header:
        return None
    if header.startswith("-----"):
        return "Earlier message"
    addr_m = re.search(r"<([^>]+@[^>]+)>", header)
    addr = (addr_m.group(1) if addr_m else "").strip()
    name = ""
    name_m = re.search(r"(?i)\b(?:AM|PM),?\s+([^<]+?)\s*<", header)
    if name_m:
        name = name_m.group(1).strip().strip(",")
        if re.match(r"^\d", name):
            name = ""
    if not name:
        names = re.findall(r",\s*([^,<\n]+)\s*<", header)
        if names:
            name = names[-1].strip()
    if name and addr:
        return f"{name} <{addr}>"
    return name or addr or header[:120]


def _plain_body(payload: dict[str, Any]) -> tuple[str, bool]:
    text = str(payload.get("body_text") or "").strip()
    html = str(payload.get("body_html") or "").strip()
    html_only = bool(payload.get("html_only")) or (bool(html) and not text)
    if text:
        return text[:40000], html_only
    if not html:
        return "", html_only
    import html as htmlmod

    t = re.sub(r"(?i)<br\s*/?>", "\n", html)
    t = re.sub(r"(?i)</p>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmlmod.unescape(re.sub(r"[ \t]+\n", "\n", t))
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:40000], True


def _rail_people(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for rec in (
        list(payload.get("from_parsed") or [])
        + list(payload.get("to_parsed") or [])
        + list(payload.get("cc_parsed") or [])
    ):
        if not isinstance(rec, dict):
            continue
        label = str(rec.get("display_name") or rec.get("address") or "").strip()
        if not label or _SUBJECT_AS_PERSON.match(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def load_email_view(evidence_id: str) -> dict[str, Any]:
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
    body, html_only = _plain_body(payload)
    turns = split_quoted_email(body)
    people = _rail_people(payload)
    return {
        "ok": True,
        "evidence_id": str(eid),
        "subject": str(payload.get("subject") or row.get("summary") or ""),
        "from": payload.get("from") or payload.get("from_raw"),
        "to": payload.get("to") or [],
        "sent_at": payload.get("sent_at"),
        "direction": payload.get("direction"),
        "html_only": html_only,
        "thread_id": payload.get("thread_id"),
        "thread_status": payload.get("thread_status"),
        "thread_completeness": payload.get("thread_completeness"),
        "people": people,
        "turns": turns,
        "quoted_history_in_body": len(turns) > 1,
        "note": (
            "Turns are quoted history inside this MIME message. "
            "RFC/vendor thread membership is separate and is not invented here."
        ),
        "attachments": _attachments(payload),
        "identity_mapped": (payload.get("identity_resolution") or {}).get("mapped")
        or [],
    }
