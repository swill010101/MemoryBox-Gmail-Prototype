"""Streaming mbox parse helpers (no SQLite — DTO path only)."""
from __future__ import annotations

import email
import email.policy
import hashlib
from email.utils import parsedate_to_datetime
from pathlib import Path


def content_hash(
    message_id: str | None, date: str | None, subject: str | None, body: str
) -> str:
    raw = f"{message_id or ''}|{date or ''}|{subject or ''}|{body[:2000]}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def iter_mbox_bytes(path: Path):
    buf = bytearray()
    with path.open("rb") as f:
        for line in f:
            if line.startswith(b"From ") and buf:
                yield bytes(buf)
                buf = bytearray()
            buf.extend(line)
        if buf:
            yield bytes(buf)


def extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not body_text:
                try:
                    content = part.get_content()
                    body_text = content if isinstance(content, str) else ""
                except Exception:  # noqa: BLE001
                    body_text = ""
            elif ctype == "text/html" and not body_html:
                try:
                    content = part.get_content()
                    body_html = content if isinstance(content, str) else ""
                except Exception:  # noqa: BLE001
                    body_html = ""
    else:
        try:
            content = msg.get_content()
            if isinstance(content, str):
                if msg.get_content_type() == "text/html":
                    body_html = content
                else:
                    body_text = content
        except Exception:  # noqa: BLE001
            pass
    return body_text, body_html


def parse_date(msg: email.message.Message):
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:  # noqa: BLE001
        return None
