"""Owner voice Learn from a transcript span — existing Choose Person + Learn, not a speaker product."""
from __future__ import annotations

from typing import Any

from memorybox.speech.constants import PRIORITY_CURRENT, VOICE_MODEL
from memorybox.speech.embeddings import embed_video_span
from memorybox.speech.media import resolve_speech_media_path
from memorybox.speech.process import persist_transcript
from memorybox.speech.queue import enqueue_interactive_owner_learn
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
    from memorybox.processing.scope import require_interactive_source
    admission = require_interactive_source(
        "voice",
        video_provider_key or getattr(video_provider, "provider_key", None) or "hvrt",
        video_external_id,
        person_id,
    )
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
    queued_follow_on = enqueue_interactive_owner_learn(
        admission=admission,
        person_id=person_id,
        video_provider_key=vpk,
        video_external_id=video_external_id,
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
        "queued_follow_on": queued_follow_on,
        "follow_on_policy": "async_queue_current_source_only",
        "person": {"id": person_id, "display_name": display_name},
        "span": {"t_start": float(t_start), "t_end": float(t_end)},
    }
