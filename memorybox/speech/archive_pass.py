"""Incremental speech archive pass: transcribe new videos only (never people × files)."""
from __future__ import annotations

from typing import Any

from memorybox.recognition.archive_pass import combined_eligible_videos
from memorybox.speech.queue import already_done_video_ids, enqueue_videos, queue_summary


def _provider_key_for_video_id(video_external_id: str) -> str:
    raw = (video_external_id or "").strip()
    if len(raw) == 36 and raw.count("-") == 4:
        return "immich"
    return "hvrt"


def enqueue_new_videos_for_transcribe(
    *, video_provider: Any, photo_provider: Any | None = None,
    limit: int = 5000, video_ids: list[str] | None = None,
) -> dict[str, Any]:
    from memorybox.processing.scope import require_admission, ScopeDenied, admit
    admission = require_admission("transcribe")
    rows = admission.videos
    if video_ids:
        if len(set(video_ids)) != len(video_ids): raise ScopeDenied("duplicate_source")
        selected=[]
        for vid in video_ids:
            matches=[v for v in rows if v["video_external_id"]==vid]
            if len(matches)!=1: raise ScopeDenied("off_manifest_or_ambiguous_source")
            selected.extend(matches)
        rows=selected
    if len(rows)>limit: raise ScopeDenied("limit_would_truncate_approved_workload")
    admit("transcribe",rows)
    queued=enqueue_videos(videos=rows,enqueue_reason="transcribe",force_requeue=bool(video_ids))
    return {"ok":True,"admission_id":admission.id,"source_count":len(rows),"enqueue":queued,"cartesian":False}
