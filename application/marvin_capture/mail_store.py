"""Preserve raw emails and attachments exactly as received."""
from __future__ import annotations

import email
import email.policy
import re
from email.message import EmailMessage, Message
from pathlib import Path
from typing import Any

from .reply_extract import extract_reply_text, html_to_text


SAFE_FILENAME_RE = re.compile(r"[^\w.\- ()[\]]+", re.UNICODE)


def safe_filename(name: str, fallback: str = "attachment.bin") -> str:
    name = (name or "").strip() or fallback
    name = name.replace("/", "_").replace("\\", "_")
    name = SAFE_FILENAME_RE.sub("_", name)
    return name[:180] or fallback


def parse_raw_email(raw: bytes) -> Message:
    return email.message_from_bytes(raw, policy=email.policy.default)


def message_subject(msg: Message) -> str:
    return str(msg.get("Subject") or "")


def message_date(msg: Message) -> str | None:
    return msg.get("Date")


def walk_body_parts(msg: Message) -> tuple[str, bool]:
    """Return (body_text_or_html, is_html) preferring plain text."""
    if msg.is_multipart():
        plain = None
        html = None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            if ctype == "text/plain" and plain is None:
                try:
                    plain = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ctype == "text/html" and html is None:
                try:
                    html = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if plain is not None:
            return str(plain), False
        if html is not None:
            return str(html), True
        return "", False

    ctype = msg.get_content_type()
    try:
        content = msg.get_content()
    except Exception:
        payload = msg.get_payload(decode=True) or b""
        content = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    if ctype == "text/html":
        return str(content), True
    return str(content), False


def extract_attachments(msg: Message) -> list[dict[str, Any]]:
    """Collect attachment payloads (filename, mime_type, data)."""
    found: list[dict[str, Any]] = []
    if not msg.is_multipart():
        return found

    for idx, part in enumerate(msg.walk()):
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        disp = str(part.get("Content-Disposition") or "")
        is_attachment = bool(filename) or "attachment" in disp.lower()
        # skip body text parts without filename
        if not is_attachment:
            continue
        try:
            data = part.get_payload(decode=True) or b""
        except Exception:
            data = b""
        mime_type = part.get_content_type()
        found.append(
            {
                "filename": safe_filename(filename or f"part-{idx}.bin"),
                "mime_type": mime_type,
                "data": data,
            }
        )
    return found


def save_raw_email(raw: bytes, dest_dir: Path, message_id: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{safe_filename(message_id, 'message')}.eml"
    path.write_bytes(raw)
    return path


def save_attachments(
    attachments: list[dict[str, Any]],
    dest_dir: Path,
) -> list[dict[str, Any]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    used: set[str] = set()
    for att in attachments:
        name = att["filename"]
        base = name
        n = 1
        while name.lower() in used or (dest_dir / name).exists():
            stem = Path(base).stem
            suffix = Path(base).suffix
            name = f"{stem}_{n}{suffix}"
            n += 1
        used.add(name.lower())
        path = dest_dir / name
        path.write_bytes(att["data"])
        saved.append(
            {
                "filename": name,
                "mime_type": att.get("mime_type"),
                "storage_path": str(path),
            }
        )
    return saved


def derive_reply_text(msg: Message) -> str:
    body, is_html = walk_body_parts(msg)
    return extract_reply_text(body, is_html=is_html)
