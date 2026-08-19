"""Origin video date/filename/thumb for Explore appearance cards."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


def looks_like_uuid(value: str) -> bool:
    raw = (value or "").strip()
    return len(raw) == 36 and raw.count("-") == 4


def origin_thumb_url(video_external_id: str, *, t_sec: float = 0.0) -> str:
    vid = (video_external_id or "").strip()
    if not vid or vid.startswith(("video-peggy-", "video-library-")):
        return ""
    if looks_like_uuid(vid):
        return f"/library/media/photo/{vid}"
    return f"/library/media/video-poster?video={vid}&t={max(0.0, float(t_sec)):.3f}"


@lru_cache(maxsize=512)
def origin_asset_meta(video_external_id: str) -> tuple[str, str]:
    """(taken_at iso, original_filename) from Immich when the id is an asset UUID."""
    vid = (video_external_id or "").strip()
    if not looks_like_uuid(vid):
        return "", ""
    try:
        from memorybox.ask.deps import build_photo

        photo = build_photo()
        client = getattr(photo, "_client", None)
        getter = getattr(client, "get_asset", None)
        raw = getter(vid) if callable(getter) else None
    except Exception:
        return "", ""
    if not isinstance(raw, dict):
        return "", ""
    name = str(raw.get("originalFileName") or raw.get("originalPath") or "").strip()
    if name:
        name = Path(name.replace("\\", "/")).name
    taken = ""
    from memorybox.recognition.seed import _capture_at

    dt = _capture_at(raw)
    if dt is not None:
        taken = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    return taken, name


def origin_card_fields(video_external_id: str, *, t_sec: float = 0.0) -> dict[str, Any]:
    taken, filename = origin_asset_meta(video_external_id)
    return {
        "taken_at": taken or None,
        "original_filename": filename or None,
        "thumb_url": origin_thumb_url(video_external_id, t_sec=t_sec),
    }
