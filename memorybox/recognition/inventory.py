"""Eligible-video inventory for I8B queue (HVRT has list_videos, not a dedicated helper)."""
from __future__ import annotations

from typing import Any


def inventory_video_rows(video: Any, *, limit: int = 5000) -> list[dict[str, Any]]:
    """Same shape as FakeVideo.eligible_video_rows / POST /people/sync/immich."""
    fn = getattr(video, "eligible_video_rows", None)
    if callable(fn):
        return list(fn() or [])
    vpk = getattr(video, "provider_key", None) or "hvrt"
    rows: list[dict[str, Any]] = []
    try:
        videos = video.list_videos(limit=limit)
    except Exception:
        return []
    for v in videos or []:
        rows.append(
            {
                "video_provider_key": vpk,
                "video_external_id": getattr(v, "external_id", None) or "",
                "eligible": True,
                "path_hint": getattr(v, "path_hint", None),
                "duration_sec": getattr(v, "duration_sec", None),
                "title": getattr(v, "title", None),
            }
        )
    return [r for r in rows if r.get("video_external_id")]
