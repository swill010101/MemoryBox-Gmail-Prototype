"""Local first-class SMS attachment bytes (not Immich, not Artifacts)."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

_UUID_IN_NAME = re.compile(
    r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})"
)


def cache_root() -> Path:
    raw = (os.environ.get("MEMORYBOX_SMS_ATTACH_CACHE") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "working" / "sms-attachments"


def cache_get(filename: str) -> Path | None:
    name = Path(filename or "").name
    if not name:
        return None
    root = cache_root()
    direct = root / name
    try:
        if direct.is_file() and direct.stat().st_size:
            return direct
    except OSError:
        pass
    uuid_m = _UUID_IN_NAME.search(name)
    uuid = uuid_m.group(1) if uuid_m else ""
    suffix = name.split("__", 1)[-1] if "__" in name else ""
    try:
        if not root.is_dir():
            return None
        for child in root.iterdir():
            if not child.is_file():
                continue
            n = child.name.casefold()
            if n == name.casefold():
                return child
            if suffix and n.endswith(suffix.casefold()):
                return child
            if uuid and uuid.casefold() in n:
                return child
    except OSError:
        return None
    return None


def cache_put(src: Path, filename: str) -> Path | None:
    name = Path(filename or src.name).name
    if not name:
        return None
    try:
        if not src.is_file() or not src.stat().st_size:
            return None
    except OSError:
        return None
    dest = cache_root() / name
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest.stat().st_size:
            return dest
        shutil.copy2(src, dest)
        return dest if dest.is_file() else None
    except OSError:
        return None


def _safe_filename(name: str) -> str:
    base = Path(name or "attachment.bin").name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "attachment.bin"
    return base[:180]


def _media_kind(filename: str, mime: str) -> str:
    ext = Path(filename).suffix.lower()
    if mime.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}:
        return "photo"
    if mime.startswith("video/") or ext in {".mp4", ".mov", ".m4v", ".avi"}:
        return "video"
    if mime.startswith("audio/") or ext in {".m4a", ".mp3", ".wav", ".aac", ".caf"}:
        return "audio"
    return "document"


def media_object_path(media_object_id: str, *, conn: Any | None = None) -> Path | None:
    """Return the MB-managed file for an ingested SMS attachment, if present."""
    try:
        mid = UUID(str(media_object_id).strip())
    except (ValueError, TypeError, AttributeError):
        return None

    def _run(c: Any) -> Path | None:
        row = c.execute(
            "SELECT uri FROM media_objects WHERE id = %s",
            (mid,),
        ).fetchone()
        if not row or not row.get("uri"):
            return None
        p = Path(str(row["uri"]))
        try:
            if p.is_file() and p.stat().st_size:
                return p
        except OSError:
            return None
        return None

    if conn is not None:
        return _run(conn)
    from memorybox.db import connection

    with connection() as c:
        return _run(c)


def put_media_object(
    data: bytes,
    filename: str,
    *,
    source_id: UUID,
    conn: Any,
    mime_type: str | None = None,
) -> dict[str, Any] | None:
    """Write attachment bytes into MB-managed store + media_objects. Not Immich."""
    if not data:
        return None
    name = _safe_filename(filename)
    digest = hashlib.sha256(data).hexdigest()
    mime = (mime_type or mimetypes.guess_type(name)[0] or "application/octet-stream")
    dest = cache_root() / digest[:2] / f"{digest}_{name}"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            tmp = dest.with_name(f".tmp_{digest[:12]}_{name}")
            tmp.write_bytes(data)
            tmp.replace(dest)
    except OSError:
        return None
    existing = conn.execute(
        """
        SELECT id, uri, content_hash, mime_type
        FROM media_objects
        WHERE source_id = %s AND content_hash = %s
        LIMIT 1
        """,
        (source_id, digest),
    ).fetchone()
    if existing:
        return {
            "media_object_id": str(existing["id"]),
            "uri": str(existing.get("uri") or dest),
            "content_hash": digest,
            "byte_size": len(data),
            "mime_type": str(existing.get("mime_type") or mime),
        }
    mid = uuid4()
    conn.execute(
        """
        INSERT INTO media_objects (
            id, source_id, media_kind, storage_mode, uri, content_hash, mime_type,
            metadata_json
        )
        VALUES (%s, %s, %s, 'memorybox_managed', %s, %s, %s, %s::jsonb)
        """,
        (
            mid,
            source_id,
            _media_kind(name, mime),
            str(dest),
            digest,
            mime,
            json.dumps({"origin": "sms_ingest", "promoted_to_immich": False}),
        ),
    )
    return {
        "media_object_id": str(mid),
        "uri": str(dest),
        "content_hash": digest,
        "byte_size": len(data),
        "mime_type": mime,
    }


def inventory_export_attachments(export_path: Path, filenames: list[str]) -> dict[str, Any]:
    """What is actually next to the SMS CSV (names only; no message bodies)."""
    parent = export_path.parent
    listing: list[dict[str, str]] = []
    unlistable: str | None = None
    try:
        kids = sorted(parent.iterdir(), key=lambda p: p.name.casefold())
        for child in kids[:80]:
            kind = "unknown"
            try:
                kind = "dir" if child.is_dir() else "file"
            except OSError:
                pass
            listing.append({"name": child.name, "kind": kind})
    except OSError as exc:
        unlistable = str(exc)
    uniq: list[str] = []
    seen: set[str] = set()
    for raw in filenames:
        name = Path(raw or "").name
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        uniq.append(name)
    on_disk: set[str] = set()
    stack: list[tuple[Path, int]] = [(parent, 0)]
    while stack:
        cur, level = stack.pop()
        try:
            children = list(cur.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                if child.is_file():
                    on_disk.add(child.name.casefold())
                elif child.is_dir() and level < 4:
                    stack.append((child, level + 1))
            except OSError:
                continue
    present = 0
    missing_sample: list[str] = []
    for name in uniq:
        stem = Path(name).stem
        suffix = Path(name).suffix
        forms = {name.casefold()}
        if "__" in stem:
            forms.add((stem.split("__", 1)[1] + suffix).casefold())
        if any(f in on_disk for f in forms):
            present += 1
        elif len(missing_sample) < 8:
            missing_sample.append(name)
    hint = None
    if uniq and present == 0:
        hint = (
            "CSV-only export: attachment names are in the spreadsheet, but no image/video "
            "files are next to it. Export the message attachments into this folder "
            "(or set MEMORYBOX_SMS_ATTACHMENTS_DIR) and run ingest-sms."
        )
    return {
        "sms_folder": str(parent),
        "sms_folder_listing": listing,
        "sms_folder_unlistable": unlistable,
        "attachment_names_unique": len(uniq),
        "attachment_files_on_disk": present,
        "attachment_files_missing": max(0, len(uniq) - present),
        "attachment_missing_sample": missing_sample,
        "attachment_hint": hint,
    }


def sms_folder_has_attachment_bytes(export_path: Path) -> bool:
    """True when a sibling file/folder or env dir might hold attachment bytes."""
    extra = (os.environ.get("MEMORYBOX_SMS_ATTACHMENTS_DIR") or "").strip()
    if extra:
        p = Path(extra).expanduser()
        try:
            if p.is_dir() and any(p.iterdir()):
                return True
            if p.is_file():
                return True
        except OSError:
            pass
    try:
        for child in export_path.parent.iterdir():
            if child.name == export_path.name:
                continue
            return True
    except OSError:
        pass
    try:
        root = cache_root()
        if root.is_dir() and any(root.iterdir()):
            return True
    except OSError:
        pass
    return False
