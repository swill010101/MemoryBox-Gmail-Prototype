"""Transcribe one open tape now — not people × files, not the overnight batch."""
from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_in_flight: set[str] = set()


def whisper_installed() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _provider_key(video_external_id: str, video_provider: Any) -> str:
    raw = (video_external_id or "").strip()
    if len(raw) == 36 and raw.count("-") == 4:
        return "immich"
    return str(getattr(video_provider, "provider_key", None) or "hvrt")


def start_transcribe_now(
    *,
    video_external_id: str,
    video_provider: Any,
    video_provider_key: str | None = None,
) -> dict[str, Any]:
    veid = (video_external_id or "").strip()
    if not veid:
        return {"ok": False, "error": "missing_video_id"}
    vpk = (video_provider_key or "").strip() or _provider_key(veid, video_provider)
    inject = getattr(video_provider, "i9_scan_transcript", None)
    can_inject = False
    if callable(inject):
        raw = inject(veid)
        can_inject = isinstance(raw, dict) and bool(raw.get("words"))
    whisper = whisper_installed()
    if not can_inject and not whisper:
        return {
            "ok": False,
            "error": "faster_whisper_unavailable",
            "detail": "Install faster-whisper on FlightSim, then restart Serve.",
            "whisper": False,
        }
    with _lock:
        already = veid in _in_flight
        _in_flight.add(veid)

    def _run() -> None:
        try:
            from memorybox.speech.process import transcribe_this_video_now

            transcribe_this_video_now(
                video_provider_key=vpk,
                video_external_id=veid,
                video_provider=video_provider,
            )
        finally:
            with _lock:
                _in_flight.discard(veid)

    if not already:
        threading.Thread(target=_run, name="mb-transcribe-now", daemon=True).start()
    return {
        "ok": True,
        "started": True,
        "already": already,
        "video_external_id": veid,
        "video_provider_key": vpk,
        "whisper": whisper,
        "inject": can_inject,
        "cartesian": False,
    }
