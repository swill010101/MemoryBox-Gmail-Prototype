"""Resolve the original video file used for transcription and voice Learn."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_speech_media_path(video_provider: Any, video_id: str) -> str:
    """Same file lookup for transcribe and owner voice Learn.

    HVRT may expose local_path_for / path_hint. FlightSim Immich tapes are UUIDs
    and are found via encoded-video / originalPath (same as I8B frames).
    """
    vid = (video_id or "").strip()
    if not vid:
        return ""
    getter = getattr(video_provider, "local_path_for", None)
    if callable(getter):
        try:
            path = getter(vid)
        except Exception:
            path = None
        if path:
            return str(path)
    getv = getattr(video_provider, "get_video", None)
    if callable(getv):
        try:
            asset = getv(vid)
        except Exception:
            asset = None
        hint = getattr(asset, "path_hint", None) if asset is not None else None
        if hint:
            hp = Path(str(hint))
            if hp.is_file():
                return str(hp)
    try:
        from memorybox.recognition.frames import (
            resolve_immich_video_path,
            resolve_local_video_path,
        )

        found = resolve_local_video_path(video_provider, vid) or resolve_immich_video_path(
            vid
        )
        if found is not None:
            return str(found)
    except Exception:
        pass
    return ""
