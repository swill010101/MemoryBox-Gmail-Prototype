"""Streaming mbox / Maildir parse helpers (no SQLite — DTO path only)."""
from __future__ import annotations

import email
import email.policy
import hashlib
import re
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterator

from memorybox.providers.email_read.dto import EmailAddressDto, EmailPartDto
from memorybox.ingest.sources_paths import PREFERRED_MBOX_NAME, email_source_candidates

PARSER_VERSION = "i8-email-1"

_HEADER_KEEP = (
    "Message-ID",
    "Date",
    "From",
    "To",
    "Cc",
    "Bcc",
    "Subject",
    "In-Reply-To",
    "References",
    "MIME-Version",
    "Content-Type",
    "Content-Transfer-Encoding",
    "Delivered-To",
    "Return-Path",
    "X-GM-THRID",
    "X-GM-MSGID",
    "X-Gmail-Labels",
    "X-GM-LABELS",
    "Thread-Index",
    "Thread-Topic",
)

_ID_RE = re.compile(r"<[^<>]+>")


def content_hash(
    message_id: str | None, date: str | None, subject: str | None, body: str
) -> str:
    raw = f"{message_id or ''}|{date or ''}|{subject or ''}|{body[:2000]}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def iter_rfc822_bytes(path: Path) -> Iterator[bytes]:
    """Yield RFC 822 messages from a file (mbox) or directory (Maildir / .eml)."""
    if path.is_file():
        yield from iter_mbox_bytes(path)
        return
    if not path.is_dir():
        return
    cur, new = path / "cur", path / "new"
    if cur.is_dir() or new.is_dir():
        for folder in (new, cur):
            if not folder.is_dir():
                continue
            try:
                kids = sorted(folder.iterdir(), key=lambda p: p.name)
            except OSError:
                continue
            for child in kids:
                try:
                    if child.is_file() and not child.name.startswith("."):
                        yield child.read_bytes()
                except OSError:
                    continue
        return
    try:
        files = sorted(path.rglob("*"), key=lambda p: str(p).lower())
    except OSError:
        return
    for child in files:
        try:
            if not child.is_file():
                continue
        except OSError:
            continue
        suffix = child.suffix.lower()
        if suffix in {".eml", ".msg"}:
            try:
                yield child.read_bytes()
            except OSError:
                continue
        elif suffix in {".mbox", ".mbx"} or child.name.lower().endswith(".mbox"):
            yield from iter_mbox_bytes(child)


def pick_mbox_in_dir(path: Path) -> Path | None:
    """Prefer the Takeout -002 mbox; match names case-insensitively."""
    try:
        kids = [
            p
            for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in {".mbox", ".mbx"}
        ]
    except OSError:
        return None
    if not kids:
        return None
    by_fold = {p.name.casefold(): p for p in kids}
    if PREFERRED_MBOX_NAME in by_fold:
        return by_fold[PREFERRED_MBOX_NAME]
    for name, p in by_fold.items():
        if name.endswith("-002.mbox") and "spam" in name and "trash" in name:
            return p
    for name, p in by_fold.items():
        if "spam" in name and "trash" in name:
            return p
    dash002 = [p for p in kids if p.stem.casefold().endswith("-002")]
    if dash002:
        return max(dash002, key=lambda p: p.stat().st_size)
    return max(kids, key=lambda p: p.stat().st_size)


def default_email_source_path() -> Path | None:
    for path in email_source_candidates():
        try:
            if path.is_file():
                return path
            if not path.is_dir():
                continue
            hit = pick_mbox_in_dir(path)
            if hit is not None:
                return hit
            if (path / "cur").is_dir() or (path / "new").is_dir():
                return path
        except OSError:
            continue
    return None


def detect_format(path: Path) -> str:
    if path.is_file():
        return "mbox"
    if path.is_dir() and ((path / "cur").is_dir() or (path / "new").is_dir()):
        return "maildir"
    if path.is_dir():
        return "directory"
    return "missing"


def parse_message_ids(raw: str | None) -> tuple[str, ...]:
    text = (raw or "").strip()
    if not text:
        return ()
    found = tuple(_ID_RE.findall(text))
    if found:
        return found
    return (text,)


def addr_records(*header_values: str | None) -> tuple[EmailAddressDto, ...]:
    values = [v for v in header_values if v]
    if not values:
        return ()
    out: list[EmailAddressDto] = []
    seen: set[str] = set()
    for name, addr in getaddresses(values):
        addr = (addr or "").strip()
        if not addr or "@" not in addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        display = (name or "").strip()
        raw = f"{display} <{addr}>".strip() if display else addr
        out.append(
            EmailAddressDto(
                raw=raw,
                display_name=display,
                address=addr,
                normalized=key,
            )
        )
    return tuple(out)


def header_provenance(msg: email.message.Message) -> tuple[tuple[str, str], ...]:
    keep = {k.lower() for k in _HEADER_KEEP}
    out: list[tuple[str, str]] = []
    for key, value in msg.items():
        if key.lower() not in keep:
            continue
        text = str(value).strip()
        if text:
            out.append((key, text[:4000]))
    return tuple(out)


def parse_gmail_labels(msg: email.message.Message) -> tuple[str, ...]:
    raw = str(msg.get("X-Gmail-Labels") or msg.get("X-GM-LABELS") or "").strip()
    if not raw:
        return ()
    parts: list[str] = []
    seen: set[str] = set()
    for piece in raw.split(","):
        label = piece.strip().lstrip("\\").strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(label)
    return tuple(parts)


def mailbox_skip_reason(labels: tuple[str, ...] | list[str]) -> str | None:
    """Spam/Trash from Gmail Takeout labels. Inbox+Spam still counts as spam."""
    spam = False
    trash = False
    for label in labels:
        token = str(label).casefold().replace("\\", "/").rsplit("/", 1)[-1]
        if token in {"spam", "junk"}:
            spam = True
        elif token in {"trash", "bin", "deleted"}:
            trash = True
    if spam:
        return "spam"
    if trash:
        return "trash"
    return None


def vendor_thread_id(msg: email.message.Message) -> str | None:
    for key in ("X-GM-THRID", "X-GM-THRID".lower(), "Thread-Index"):
        raw = msg.get(key)
        if raw and str(raw).strip():
            return str(raw).strip()
    return None


def thread_fields(
    *,
    rfc_message_id: str | None,
    in_reply_to_ids: tuple[str, ...],
    reference_ids: tuple[str, ...],
    vendor: str | None,
) -> tuple[str | None, str]:
    """Return (thread_id, thread_status). Never invent membership from subject."""
    if vendor and (in_reply_to_ids or reference_ids):
        return vendor, "vendor+rfc"
    if vendor:
        return vendor, "vendor"
    refs = reference_ids or in_reply_to_ids
    if in_reply_to_ids or reference_ids:
        # Cluster key is evidence from this message's RFC headers (root of References).
        root = refs[0] if refs else (rfc_message_id or None)
        return root, "rfc"
    return None, "unthreaded"


def extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get_content_disposition() or "").lower()
            filename = part.get_filename()
            if disp == "attachment" or filename:
                continue
            if ctype == "text/plain" and not body_text:
                body_text = _part_text(part)
            elif ctype == "text/html" and not body_html:
                body_html = _part_text(part)
    else:
        try:
            content = msg.get_content()
            if isinstance(content, str):
                if msg.get_content_type() == "text/html":
                    body_html = content
                else:
                    body_text = content
        except Exception:  # noqa: BLE001
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = text
                else:
                    body_text = text
    return body_text, body_html


def _part_text(part: email.message.Message) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else ""
    except Exception:  # noqa: BLE001
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = part.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")
            except LookupError:
                return payload.decode("utf-8", errors="replace")
        return ""


def _decode_bytes(part: email.message.Message) -> bytes:
    try:
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload
    except Exception:  # noqa: BLE001
        return b""
    return b""


def extract_attachments(
    msg: email.message.Message, *, include_bytes: bool
) -> tuple[EmailPartDto, ...] | list[dict[str, Any]]:
    """MIME parts that are not the primary body. include_bytes=False skips payload decode."""
    parts: list[EmailPartDto] = []
    meta: list[dict[str, Any]] = []
    index = 0
    walker = msg.walk() if msg.is_multipart() else iter([msg])
    for part in walker:
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or "application/octet-stream").lower()
        disp = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        cid_raw = str(part.get("Content-ID") or "").strip() or None
        cid = cid_raw.strip("<>") if cid_raw else None
        is_body = ctype in {"text/plain", "text/html"} and disp != "attachment" and not filename
        if is_body:
            continue
        if not msg.is_multipart() and is_body:
            continue
        if not filename and not disp and not cid and ctype.startswith("text/"):
            continue
        kind = "inline" if (disp == "inline" or cid) and disp != "attachment" else "attachment"
        if disp == "attachment":
            kind = "attachment"
        elif disp == "inline" or cid:
            kind = "inline"
        name = filename or (f"inline-{cid}.bin" if cid else f"part-{index}.bin")
        index += 1
        data = _decode_bytes(part) if include_bytes else b""
        rec = {
            "filename": str(name),
            "mime_type": ctype,
            "disposition": disp or ("inline" if kind == "inline" else "attachment"),
            "content_id": cid,
            "kind": kind,
            "byte_size": len(data) if include_bytes else None,
            "content_hash": sha256_bytes(data) if include_bytes and data else None,
        }
        if not include_bytes:
            meta.append(rec)
            continue
        parts.append(
            EmailPartDto(
                filename=str(name),
                mime_type=ctype,
                byte_size=len(data),
                content_hash=sha256_bytes(data) if data else "",
                disposition=str(rec["disposition"]),
                content_id=cid,
                kind=kind,
                data=data,
            )
        )
    return tuple(parts) if include_bytes else meta


def parse_date(msg: email.message.Message):
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:  # noqa: BLE001
        return None


def inspect_mbox(path: Path, *, sample: int = 12, limit: int | None = None) -> dict[str, Any]:
    """Read-only inventory. Does not ingest. Does not rewrite. No message bodies."""
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "error": "not_found",
            "note": "Missing staged mail is not zero messages.",
        }
    before = path.stat()
    fmt = detect_format(path)
    n = 0
    with_attach = 0
    with_inline = 0
    with_vendor = 0
    with_rfc_thread = 0
    unthreaded = 0
    html_only = 0
    dates: list[str] = []
    from_sample: list[str] = []
    subject_sample: list[str] = []
    vendor_keys: set[str] = set()
    errors = 0
    labeled_spam = 0
    labeled_trash = 0
    for raw in iter_rfc822_bytes(path):
        if limit is not None and n >= limit:
            break
        try:
            msg = email.message_from_bytes(raw, policy=email.policy.compat32)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        n += 1
        dt = parse_date(msg)
        if dt is not None:
            dates.append(dt.date().isoformat())
        vendor = vendor_thread_id(msg)
        if vendor:
            with_vendor += 1
            vendor_keys.add("X-GM-THRID" if msg.get("X-GM-THRID") else "Thread-Index")
        irt = parse_message_ids(str(msg.get("In-Reply-To") or "") or None)
        refs = parse_message_ids(str(msg.get("References") or "") or None)
        if irt or refs:
            with_rfc_thread += 1
        elif not vendor:
            unthreaded += 1
        meta = extract_attachments(msg, include_bytes=False)
        if any(p.get("kind") == "attachment" for p in meta):
            with_attach += 1
        if any(p.get("kind") == "inline" for p in meta):
            with_inline += 1
        text, html = extract_bodies(msg)
        if html and not (text or "").strip():
            html_only += 1
        skip = mailbox_skip_reason(parse_gmail_labels(msg))
        if skip == "spam":
            labeled_spam += 1
        elif skip == "trash":
            labeled_trash += 1
        if len(from_sample) < sample:
            frm = str(msg.get("From") or "").strip()
            if frm:
                from_sample.append(frm[:200])
        if len(subject_sample) < sample:
            sub = str(msg.get("Subject") or "").strip()
            if sub:
                subject_sample.append(sub[:120])
    after = path.stat()
    return {
        "ok": True,
        "path": str(path),
        "format": fmt,
        "bytes": before.st_size,
        "original_untouched": before.st_mtime_ns == after.st_mtime_ns
        and before.st_size == after.st_size,
        "message_count": n,
        "parse_errors": errors,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "messages_with_attachment_parts": with_attach,
        "messages_with_inline_cid_parts": with_inline,
        "messages_with_vendor_thread_id": with_vendor,
        "messages_with_rfc_thread_headers": with_rfc_thread,
        "messages_unthreaded": unthreaded,
        "html_only_bodies": html_only,
        "labeled_spam": labeled_spam,
        "labeled_trash": labeled_trash,
        "spam_trash_skipped_on_ingest_default": labeled_spam + labeled_trash,
        "spam_trash_note": (
            "Counts come from Gmail Takeout labels (X-Gmail-Labels / X-GM-LABELS), "
            "not from the filename. inspect-mbox reports them; ingest-email skips "
            "Spam/Junk and Trash/Bin/Deleted by default. Pass "
            "--include-spam-trash to ingest those too. Originals are never rewritten."
        ),
        "vendor_thread_headers_seen": sorted(vendor_keys),
        "from_sample": from_sample,
        "subject_sample": subject_sample,
        "parser_version": PARSER_VERSION,
        "note": (
            "Header/part inventory only — bodies are not stored in this report. "
            "Q2 acceptance people/dates must be mapped from this sample (or a full "
            "owner-runtime inspect), not from a fabricated corpus."
        ),
        "limit": limit,
    }
