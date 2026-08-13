"""Path helpers for export (D7 — no hard-coded hosts)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse


def uri_or_path_to_file(uri_or_path: str | None) -> Path | None:
    """Resolve DB uri (file:// or absolute path) to a local Path if possible."""
    if not uri_or_path:
        return None
    raw = str(uri_or_path).strip()
    if not raw:
        return None
    if raw.startswith("file:"):
        parsed = urlparse(raw)
        path_raw = unquote(parsed.path or "")
        if os.name == "nt":
            if path_raw.startswith("/") and len(path_raw) >= 3 and path_raw[2] == ":":
                path_raw = path_raw[1:]
            elif parsed.netloc and len(parsed.netloc) >= 2 and parsed.netloc[1] == ":":
                path_raw = f"{parsed.netloc}{path_raw}"
        p = Path(path_raw)
    else:
        p = Path(raw)
    try:
        return p if p.is_file() else None
    except OSError:
        return None


def guess_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
        ".eml": "message/rfc822",
        ".zip": "application/zip",
    }.get(suffix, "application/octet-stream")
