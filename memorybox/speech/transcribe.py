from __future__ import annotations

import logging
from typing import Any

from memorybox.speech.constants import DIARIZE_PAUSE_GAP_SEC, VIDEO_MEDIA_EXTS

log = logging.getLogger("memorybox.speech.transcribe")


def _pause_gap_turns(words: list[dict[str, Any]], *, gap_sec: float | None = None) -> list[dict[str, Any]]:
    """Anonymous turn groups from word timestamps. Provenance: pause_gap_local, not pyannote."""
    gap = float(gap_sec if gap_sec is not None else DIARIZE_PAUSE_GAP_SEC)
    if not words:
        return []
    turns: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    last_end = float(words[0].get("t_start") or words[0].get("start_sec") or 0)
    speaker_n = 0
    for w in words:
        st = float(w.get("t_start") if w.get("t_start") is not None else w.get("start_sec") or 0)
        en = float(w.get("t_end") if w.get("t_end") is not None else w.get("end_sec") or st)
        if cur and st - last_end >= gap:
            turns.append(_turn_from_words(cur, speaker_n))
            speaker_n += 1
            cur = []
        cur.append(w)
        last_end = en
    if cur:
        turns.append(_turn_from_words(cur, speaker_n))
    return turns


def _norm_word(w: dict[str, Any]) -> dict[str, Any]:
    st = float(w.get("t_start") if w.get("t_start") is not None else w.get("start_sec") or 0)
    en = float(w.get("t_end") if w.get("t_end") is not None else w.get("end_sec") or st)
    return {
        "token": str(w.get("token") or "").strip(),
        "t_start": st,
        "t_end": en,
        "confidence": w.get("confidence"),
    }


def _turn_from_words(words: list[dict[str, Any]], speaker_n: int) -> dict[str, Any]:
    nw = [_norm_word(w) for w in words]
    text = " ".join(w["token"] for w in nw if w["token"]).strip()
    return {
        "t_start": nw[0]["t_start"],
        "t_end": nw[-1]["t_end"],
        "text": text,
        "anonymous_speaker_key": f"speaker-{speaker_n}",
        "person_id": None,
        "status": "anonymous",
        "confidence": None,
        "diarization_model": "pause_gap_local",
        "words": nw,
    }


def _try_pyannote_turns(path: str, words: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Local pyannote if installed. Never pretend pyannote when unused."""
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except ImportError:
        return None
    try:
        pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        diar = pipe(path)
    except Exception as e:
        log.info("pyannote unavailable for %s: %s", path, e)
        return None
    turns: list[dict[str, Any]] = []
    n = 0
    for turn, _, speaker in diar.itertracks(yield_label=True):
        st = float(turn.start)
        en = float(turn.end)
        span = [w for w in words if float(w["t_start"]) < en and float(w["t_end"]) > st]
        text = " ".join(w["token"] for w in span).strip()
        if not text:
            continue
        turns.append(
            {
                "t_start": st,
                "t_end": en,
                "text": text,
                "anonymous_speaker_key": str(speaker or f"speaker-{n}"),
                "person_id": None,
                "status": "anonymous",
                "confidence": None,
                "diarization_model": "pyannote_local",
                "words": span,
            }
        )
        n += 1
    return turns or None


def transcribe_local_file(path: str) -> dict[str, Any]:
    """Word-timestamp transcript via faster-whisper if installed."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        log.info("faster-whisper not installed; skip local transcribe for %s", path)
        return {"words": [], "full_text": "", "engine": "unavailable"}
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(path, word_timestamps=True)
        words: list[dict[str, Any]] = []
        parts: list[str] = []
        for seg in segments:
            parts.append(seg.text or "")
            for w in getattr(seg, "words", None) or []:
                tok = (getattr(w, "word", None) or "").strip()
                if not tok:
                    continue
                words.append(
                    {
                        "token": tok,
                        "t_start": float(getattr(w, "start", 0) or 0),
                        "t_end": float(getattr(w, "end", 0) or 0),
                        "confidence": float(getattr(w, "probability", 0) or 0) or None,
                    }
                )
        return {
            "words": words,
            "full_text": " ".join(p.strip() for p in parts).strip(),
            "engine": "faster_whisper",
        }
    except Exception as e:
        log.warning("faster-whisper failed for %s: %s", path, e)
        return {"words": [], "full_text": "", "engine": "error", "error": str(e)}


def transcribe_video_id(video_id: str, *, video_provider: Any | None = None) -> dict[str, Any]:
    """Transcribe one video. FakeVideo.i9_scan_transcript wins for harness."""
    fn = getattr(video_provider, "i9_scan_transcript", None) if video_provider is not None else None
    if callable(fn):
        inj = fn(video_id)
        if isinstance(inj, dict) and inj.get("words"):
            words = [_norm_word(w) for w in inj["words"]]
            raw_turns = inj.get("turns")
            if raw_turns:
                turns = []
                for i, t in enumerate(raw_turns):
                    turns.append(
                        {
                            "t_start": float(t.get("t_start") if t.get("t_start") is not None else t.get("start_sec") or 0),
                            "t_end": float(t.get("t_end") if t.get("t_end") is not None else t.get("end_sec") or 0),
                            "text": str(t.get("text") or ""),
                            "anonymous_speaker_key": str(t.get("anonymous_speaker_key") or f"speaker-{i}"),
                            "person_id": t.get("person_id"),
                            "status": str(t.get("status") or "anonymous"),
                            "confidence": t.get("confidence"),
                            "diarization_model": str(t.get("diarization_model") or "pause_gap_local"),
                            "embedding": t.get("embedding"),
                        }
                    )
            else:
                turns = _pause_gap_turns(words)
            full = inj.get("full_text") or " ".join(w["token"] for w in words)
            return {
                "ok": True,
                "video_id": video_id,
                "words": words,
                "turns": turns,
                "full_text": full,
                "engine": "fakevideo_inject",
                "diarization_provenance": turns[0]["diarization_model"] if turns else "pause_gap_local",
            }

    path = ""
    if video_provider is not None:
        getter = getattr(video_provider, "local_path_for", None)
        if callable(getter):
            path = str(getter(video_id) or "")
    if not path:
        try:
            from memorybox.video_worker import path_for_video_id

            path = str(path_for_video_id(video_id) or "")
        except Exception:
            path = ""
    if not path:
        return {"ok": False, "error": "no_local_path", "video_id": video_id}

    raw = transcribe_local_file(path)
    words = [_norm_word(w) for w in (raw.get("words") or [])]
    py_turns = _try_pyannote_turns(path, words) if words else None
    turns = py_turns or _pause_gap_turns(words)
    prov = (turns[0]["diarization_model"] if turns else "pause_gap_local")
    return {
        "ok": True,
        "video_id": video_id,
        "words": words,
        "turns": turns,
        "full_text": raw.get("full_text") or "",
        "engine": raw.get("engine") or "faster_whisper",
        "diarization_provenance": prov,
        "error": raw.get("error"),
    }


def looks_like_video_filename(name: str) -> bool:
    n = (name or "").lower()
    return any(n.endswith(ext) for ext in VIDEO_MEDIA_EXTS)
