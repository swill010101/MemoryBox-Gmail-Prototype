"""Eligible-video inventory for I8B queue (HVRT has list_videos, not a dedicated helper)."""
from __future__ import annotations

from typing import Any


def list_owned_folder_video_rows(*, limit: int = 100000) -> list[dict[str, Any]]:
    """MB-owned home movies under MEMORYBOX_VIDEO_MEDIA_ROOT, including new subfolder files.

    These are not Immich ingest. IDs are the same vid-* hashes the video worker uses.
    """
    from memorybox.video_worker import list_owned_folder_videos

    rows: list[dict[str, Any]] = []
    for v in list_owned_folder_videos(limit=limit) or []:
        veid = str(v.get("external_id") or "").strip()
        if not veid:
            continue
        rows.append(
            {
                "video_provider_key": "hvrt",
                "video_external_id": veid,
                "eligible": True,
                "path_hint": v.get("path_hint"),
                "duration_sec": v.get("duration_sec"),
                "title": v.get("title"),
                "source": "mb_owned_folder",
            }
        )
    return rows


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
