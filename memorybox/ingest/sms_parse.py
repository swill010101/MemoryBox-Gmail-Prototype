"""Header-driven SMS / iMessage / MMS export reader.

Does not assume a vendor schema. Known header aliases fill normalized
fields; every source column is kept in source_metadata. Originals are
never rewritten.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PARSER_VERSION = "i7-sms-1"

_SMS_CHANNELS = frozenset({"sms", "text", "imessage", "i-message", "mms", "rcs"})


def _norm_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


# Normalized field -> acceptable header aliases (already _norm_header'd)
_ALIASES: dict[str, tuple[str, ...]] = {
    "thread_id": (
        "chatsession",
        "chat",
        "conversation",
        "conversationid",
        "thread",
        "threadid",
        "chatid",
    ),
    "group_name": ("groupname", "group", "chatname"),
    "sent_at": (
        "messagedate",
        "date",
        "timestamp",
        "sentdate",
        "sentat",
        "datetime",
        "imessagedate",
    ),
    "delivered_at": ("delivereddate", "deliveredat", "delivered"),
    "read_at": ("readdate", "readat", "read"),
    "edited_at": ("editeddate", "editedat", "edited"),
    "service": ("service", "channel", "messagetype", "protocol"),
    "direction": ("type", "direction", "inout", "sentreceived"),
    "sender_handle": ("senderid", "sender", "from", "fromid", "handle", "phone"),
    "sender_name": ("sendername", "fromname", "contact", "contactname"),
    "recipients": ("recipient", "recipients", "to", "toid"),
    "status": ("status",),
    "reply_to": ("replyingto", "replyto", "inreplyto", "reply"),
    "subject": ("subject",),
    "body_text": ("text", "message", "body", "messagetext", "content"),
    "attachment": ("attachment", "attachments", "filename", "file"),
    "attachment_type": ("attachmenttype", "atttype", "mimetype"),
    "message_id": ("messageid", "guid", "rowid", "id"),
    "tapback": ("tapback", "reaction", "reactions"),
    "unsend": ("unsend", "unsent", "deleted"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lng", "lon"),
    "shared_location": ("sharedlocation", "location", "place", "address"),
}


@dataclass
class SmsMessage:
    source_row: int
    headers: list[str]
    raw: dict[str, str]
    source_metadata: dict[str, str]
    thread_id: str = ""
    group_name: str = ""
    sent_at: str | None = None
    delivered_at: str | None = None
    read_at: str | None = None
    edited_at: str | None = None
    service: str = "text"
    direction: str = ""
    sender_handle: str = ""
    sender_name: str = ""
    recipients: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    status: str = ""
    reply_to: str = ""
    subject: str = ""
    body_text: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)
    message_id: str = ""
    tapback: str = ""
    unsend: str = ""
    latitude: str = ""
    longitude: str = ""
    shared_location: str = ""
    content_hash: str = ""

    @property
    def from_owner(self) -> bool:
        d = (self.direction or "").strip().lower()
        return d in {"outgoing", "outbound", "sent", "out", "1"}


def sniff_dialect(sample: str) -> csv.Dialect:
    """Prefer comma CSV. Only sniff when the header is clearly tab/semicolon."""
    header = (sample.splitlines() or [""])[0]
    if header.count("\t") > header.count(",") and header.count("\t") >= 2:
        return csv.excel_tab
    if header.count(";") > header.count(",") and header.count(";") >= 2:
        class _Semi(csv.excel):
            delimiter = ";"

        return _Semi()
    return csv.excel


def _looks_like_filename(raw: str) -> bool:
    name = Path(raw or "").name.strip()
    return bool(name) and bool(re.search(r"\.[A-Za-z0-9]{2,5}$", name))


def _coord(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        val = float(text)
    except ValueError:
        return ""
    if not (-180.0 <= val <= 180.0):
        return ""
    return text


def _pick(raw_norm: dict[str, str], field: str) -> str:
    for alias in _ALIASES.get(field, ()):
        if alias in raw_norm and raw_norm[alias].strip():
            return raw_norm[alias].strip()
    return ""


def _parse_when(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return text


def _split_handles(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[;|,]", raw)
    return [p.strip() for p in parts if p.strip()]


def _channel(service: str, attachment: str, attachment_type: str) -> str:
    s = (service or "").strip().lower()
    if s in {"imessage", "i-message", "imessage"}:
        return "imessage"
    if s in {"mms"}:
        return "mms"
    if s in {"rcs"}:
        return "rcs"
    if s in {"sms", "text", "sms/text"}:
        return "sms" if s != "text" else "sms"
    if attachment or (attachment_type or "").lower() in {"image", "video", "audio"}:
        if s in {"", "type", "incoming", "outgoing"}:
            return "mms"
    if s in {"incoming", "outgoing", "sent", "received"}:
        return "text"
    return s or "text"


def _direction(raw: str, service_field: str) -> str:
    d = (raw or service_field or "").strip().lower()
    if d in {"outgoing", "outbound", "sent", "out", "1"}:
        return "outgoing"
    if d in {"incoming", "inbound", "received", "in", "0"}:
        return "incoming"
    return (raw or "").strip()


def resolve_attachment_paths(
    names: Iterable[str], *, export_path: Path
) -> list[dict[str, Any]]:
    parent = export_path.parent
    stems = [parent, parent / "attachments", parent / "Attachments"]
    out: list[dict[str, Any]] = []
    for name in names:
        raw = (name or "").strip()
        if not raw:
            continue
        found: str | None = None
        candidate = Path(raw)
        if candidate.is_file():
            found = str(candidate)
        else:
            for root in stems:
                hit = root / Path(raw).name
                if hit.is_file():
                    found = str(hit)
                    break
        out.append(
            {
                "filename": Path(raw).name,
                "source_ref": raw,
                "resolved_path": found,
                "bytes_present": bool(found),
                "promoted_to_immich": False,
                "standalone_explore_media": False,
            }
        )
    return out


def iter_sms_rows(
    path: Path, *, limit: int | None = None
) -> tuple[list[str], list[SmsMessage]]:
    """Read export read-only. Returns (headers, messages)."""
    data = path.read_bytes()
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    dialect = sniff_dialect(sample)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = list(reader.fieldnames or [])
    messages: list[SmsMessage] = []
    for i, row in enumerate(reader, start=2):
        if limit is not None and len(messages) >= limit:
            break
        raw = {str(k or ""): "" if v is None else str(v) for k, v in (row or {}).items()}
        raw_norm = {_norm_header(k): (v or "").strip() for k, v in raw.items()}
        # Prefer dedicated direction column; if Type is Incoming/Outgoing use it
        # and do not treat it as service.
        type_val = raw_norm.get("type") or ""
        service_val = _pick(raw_norm, "service")
        if _norm_header(service_val) in {"incoming", "outgoing", "sent", "received"}:
            direction = _direction(service_val, "")
            if _norm_header(type_val) in _SMS_CHANNELS or service_val == type_val:
                service_val = type_val if _norm_header(type_val) in _SMS_CHANNELS else ""
        else:
            direction = _direction(_pick(raw_norm, "direction") or type_val, "")
        attach_raw = _pick(raw_norm, "attachment")
        if attach_raw and not _looks_like_filename(attach_raw):
            attach_raw = ""
        attach_type = _pick(raw_norm, "attachment_type")
        thread = _pick(raw_norm, "thread_id")
        sender_handle = _pick(raw_norm, "sender_handle")
        sender_name = _pick(raw_norm, "sender_name")
        recipients = _split_handles(_pick(raw_norm, "recipients"))
        participants: list[str] = []
        for part in [sender_name, sender_handle, thread, *recipients]:
            if part and part not in participants:
                participants.append(part)
        body = _pick(raw_norm, "body_text")
        sent = _parse_when(_pick(raw_norm, "sent_at"))
        mid = _pick(raw_norm, "message_id") or f"{thread}|{sent or ''}|{body[:48]}|{i}"
        blob = "\n".join(f"{k}={raw[k]}" for k in headers)
        digest = hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()
        attachments = resolve_attachment_paths(
            _split_handles(attach_raw) or ([attach_raw] if attach_raw else []),
            export_path=path,
        )
        if attach_type and attachments:
            attachments[0]["attachment_type"] = attach_type
        msg = SmsMessage(
            source_row=i,
            headers=headers,
            raw=raw,
            source_metadata=dict(raw),
            thread_id=thread,
            group_name=_pick(raw_norm, "group_name") or "",
            sent_at=sent,
            delivered_at=_parse_when(_pick(raw_norm, "delivered_at")),
            read_at=_parse_when(_pick(raw_norm, "read_at")),
            edited_at=_parse_when(_pick(raw_norm, "edited_at")),
            service=_channel(service_val, attach_raw, attach_type),
            direction=direction,
            sender_handle=sender_handle,
            sender_name=sender_name,
            recipients=recipients,
            participants=participants,
            status=_pick(raw_norm, "status"),
            reply_to=_pick(raw_norm, "reply_to"),
            subject=_pick(raw_norm, "subject"),
            body_text=body,
            attachments=attachments,
            message_id=mid,
            tapback=_pick(raw_norm, "tapback"),
            unsend=_pick(raw_norm, "unsend"),
            latitude=_coord(_pick(raw_norm, "latitude")),
            longitude=_coord(_pick(raw_norm, "longitude")),
            shared_location=_pick(raw_norm, "shared_location"),
            content_hash=digest,
        )
        messages.append(msg)
    return headers, messages


def inspect_sms_export(path: Path, *, sample_rows: int = 0) -> dict[str, Any]:
    """Read-only inventory. Does not ingest. Does not rewrite."""
    before = path.stat()
    headers, rows = iter_sms_rows(path, limit=None)
    after = path.stat()
    dates = [m.sent_at for m in rows if m.sent_at]
    services = sorted({m.service for m in rows if m.service})
    threads = sorted({m.thread_id for m in rows if m.thread_id})
    return {
        "ok": True,
        "path": str(path),
        "bytes": before.st_size,
        "original_untouched": before.st_mtime_ns == after.st_mtime_ns
        and before.st_size == after.st_size,
        "headers": headers,
        "row_count": len(rows),
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "services": services,
        "thread_count": len(threads),
        "threads_sample": threads[:12],
        "attachment_rows": sum(1 for m in rows if m.attachments),
        "location_rows": sum(
            1 for m in rows if m.latitude or m.longitude or m.shared_location
        ),
        "parser_version": PARSER_VERSION,
        "sample": [
            {
                "row": m.source_row,
                "thread_id": m.thread_id,
                "sent_at": m.sent_at,
                "direction": m.direction,
                "service": m.service,
                "body_text": (m.body_text or "")[:80],
            }
            for m in rows[: max(0, int(sample_rows))]
        ],
    }
