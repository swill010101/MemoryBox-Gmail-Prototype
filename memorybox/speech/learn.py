"""Owner voice Learn from a transcript span — existing Choose Person + Learn, not a speaker product."""
from __future__ import annotations

from typing import Any

from memorybox.speech.constants import PRIORITY_CURRENT, PRIORITY_OTHER, VOICE_MODEL
from memorybox.speech.embeddings import embed_video_span
from memorybox.speech.media import resolve_speech_media_path
from memorybox.speech.process import persist_transcript, recognize_person_on_video
from memorybox.speech.queue import enqueue_videos
from memorybox.speech.store import assign_turn_person, persist_voice_exemplar

_LEARN_FAIL_DETAIL = {
    "no_source_audio": (
        "MemoryBox could not open the original video file for this clip, "
        "so it cannot Learn a voice from the highlighted words. "
        "The transcript is text, not a voiceprint."
    ),
    "ffmpeg_extract_failed": (
        "MemoryBox found the video but could not extract audio for the highlighted span."
    ),
    "ecapa_unavailable": (
        "Voice encoding is not available on this machine (SpeechBrain ECAPA). "
        "Install speechbrain, torch, and torchaudio to Learn a voice from a transcript span."
    ),
}


def owner_learn_voice(
    *,
    person_id: str,
    video_external_id: str,
    t_start: float,
    t_end: float,
    video_provider: Any,
    video_provider_key: str | None = None,
    embedding: list[float] | None = None,
    other_videos: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    vpk = video_provider_key or getattr(video_provider, "provider_key", None) or "hvrt"
    path = resolve_speech_media_path(video_provider, video_external_id) or None
    injected = embedding
    inj_fn = getattr(video_provider, "i9_voice_vec_for_span", None)
    if injected is None and callable(inj_fn):
        injected = inj_fn(video_external_id, float(t_start), float(t_end))
    vec, model = embed_video_span(path, float(t_start), float(t_end), injected=injected)
    if not vec:
        reason = model or "no_source_audio"
        return {
            "ok": False,
            "reason": reason,
            "detail": _LEARN_FAIL_DETAIL.get(reason)
            or (
                "Could not Learn a voice from this highlighted span "
                f"({reason}). The transcript is text, not a voiceprint."
            ),
        }
    saved = persist_voice_exemplar(
        person_id=person_id,
        video_provider_key=vpk,
        video_external_id=video_external_id,
        t_start=float(t_start),
        t_end=float(t_end),
        embedding=vec,
        embedding_model=model or VOICE_MODEL,
        meta={"provenance": "owner_review_learn", "lineage": "mb_native_i9"},
    )
    from memorybox.speech.store import has_transcript, list_transcript

    if not has_transcript(video_external_id):
        persist_transcript(
            video_provider_key=vpk,
            video_external_id=video_external_id,
            video_provider=video_provider,
            trigger="owner_learn",
        )
    tr = list_transcript(video_external_id)
    for turn in tr.get("turns") or []:
        a = float(turn.get("t_start") or 0)
        b = float(turn.get("t_end") or a)
        if b < float(t_start) or a > float(t_end):
            continue
        if turn.get("id"):
            assign_turn_person(str(turn["id"]), person_id, status="owner_confirmed", confidence=1.0)
    current = recognize_person_on_video(
        person_id=person_id,
        video_provider_key=vpk,
        video_external_id=video_external_id,
        video_provider=video_provider,
    )
    others = list(other_videos or [])
    if not others:
        rows_fn = getattr(video_provider, "eligible_video_rows", None)
        if callable(rows_fn):
            others = [r for r in (rows_fn() or []) if r.get("eligible") is not False]
    rest = [
        r
        for r in others
        if str(r.get("video_external_id") or "") not in {"", video_external_id}
    ]
    enqueue_videos(
        videos=[
            {
                "video_provider_key": str(r.get("video_provider_key") or vpk),
                "video_external_id": str(r.get("video_external_id")),
                "priority": PRIORITY_OTHER,
            }
            for r in rest
        ],
        enqueue_reason="owner_learn",
        person_id=person_id,
        priority=PRIORITY_OTHER,
    )
    enqueue_videos(
        videos=[
            {
                "video_provider_key": vpk,
                "video_external_id": video_external_id,
                "priority": PRIORITY_CURRENT,
            }
        ],
        enqueue_reason="owner_learn",
        person_id=person_id,
        priority=PRIORITY_CURRENT,
    )
    display_name = person_id
    try:
        from memorybox.person import get_person

        view = get_person(person_id)
        if view and view.display_name:
            display_name = view.display_name
    except Exception:
        pass
    return {
        "ok": True,
        "exemplar": saved,
        "current_video": current,
        "queued_other_videos": len(rest),
        "person": {"id": person_id, "display_name": display_name},
        "span": {"t_start": float(t_start), "t_end": float(t_end)},
    }
