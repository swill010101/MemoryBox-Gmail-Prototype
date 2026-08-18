"""Staged Sources locations (read-only originals). Env wins; local P: before leftover UNC."""
from __future__ import annotations

import os
from pathlib import Path

# USB layout after Sources left the NAS. Env always wins.
# Owner path: P:\photos\memorybox\sources\email\<takeout mbox>
_LOCAL_SOURCES = Path(r"P:\photos\memorybox\sources")
_LOCAL_SOURCES_ALT = Path(r"P:\MemoryBox\Sources")
_LEGACY_UNC = Path(r"\\media-server\photos\MemoryBox\Sources")
_LEGACY_UNC_ALT = Path(r"\\media-server\photos\memorybox\sources")
PREFERRED_MBOX_NAME = "all mail including spam and trash-002.mbox"


def sources_root_candidates() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    raw = (os.environ.get("MEMORYBOX_SOURCES_ROOT") or "").strip()
    ordered = []
    if raw:
        ordered.append(Path(raw))
    ordered.extend([_LOCAL_SOURCES, _LOCAL_SOURCES_ALT, _LEGACY_UNC, _LEGACY_UNC_ALT])
    for p in ordered:
        key = str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def default_sources_root() -> Path | None:
    for p in sources_root_candidates():
        try:
            if p.is_dir():
                return p
        except OSError:
            continue
    return None


def email_source_candidates() -> list[Path]:
    """Folders/files inspect-mbox / ingest-email will try, in order."""
    out: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        key = str(p).casefold()
        if key in seen:
            return
        seen.add(key)
        out.append(p)

    env = (
        os.environ.get("MEMORYBOX_MBOX_URI")
        or os.environ.get("MEMORYBOX_SMOKE_MBOX_URI")
        or ""
    ).strip()
    if env:
        _add(Path(env))
    for root in sources_root_candidates():
        email_dir = root / "email"
        _add(email_dir / PREFERRED_MBOX_NAME)
        _add(email_dir)
    return out


def sms_source_dir_candidates() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    env = (
        os.environ.get("MEMORYBOX_SMS_URI")
        or os.environ.get("MEMORYBOX_SMOKE_SMS_URI")
        or ""
    ).strip()
    if env:
        p = Path(env)
        out.append(p.parent if p.suffix.lower() == ".csv" else p)
        seen.add(str(out[0]).casefold())
    for root in sources_root_candidates():
        d = root / "sms"
        key = str(d).casefold()
        if key not in seen:
            seen.add(key)
            out.append(d)
        att = root / "sms-attachments"
        akey = str(att).casefold()
        if akey not in seen:
            seen.add(akey)
            out.append(att)
    return out
