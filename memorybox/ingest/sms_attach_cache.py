"""Local first-class SMS attachment bytes (not Immich, not Artifacts)."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

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
