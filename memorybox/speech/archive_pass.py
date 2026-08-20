"""Incremental speech archive pass: transcribe new videos only (never people × files)."""
from __future__ import annotations

from typing import Any

from memorybox.recognition.archive_pass import combined_eligible_videos
from memorybox.speech.queue import already_done_video_ids, enqueue_videos, queue_summary


def enqueue_new_videos_for_transcribe(
    *,
    video_provider: Any,
    photo_provider: Any | None = None,
    limit: int = 5000,
    video_ids: list[str] | None = None,
) -> dict[str, Any]:
    rows = combined_eligible_videos(video_provider=video_provider, photo_provider=photo_provider)
    want = {str(v).strip() for v in (video_ids or []) if str(v).strip()}
    done = already_done_video_ids(enqueue_reason="transcribe")
    new_rows = []
    for r in rows:
        veid = str(r.get("video_external_id") or "")
        if not veid or veid in done:
            continue
        if want and veid not in want:
            continue
        if r.get("eligible") is False:
            continue
        new_rows.append(
            {
                "video_provider_key": str(r.get("video_provider_key") or "hvrt"),
                "video_external_id": veid,
                "priority": 100,
            }
        )
        if len(new_rows) >= int(limit):
            break
    queued = enqueue_videos(videos=new_rows, enqueue_reason="transcribe", person_id=None, priority=100)
    return {
        "ok": True,
        "inventory": len(rows),
        "already_done": len(done),
        "new_videos": len(new_rows),
        "enqueue": queued,
        "queue": queue_summary(),
        "cartesian": False,
        "note": "per-video transcribe only; Learn for a Person is a separate owner_learn queue",
    }
