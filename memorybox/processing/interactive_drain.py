"""Dedicated Interactive Learn worker — owner_learn follow-on only.

Runs independently of MEMORYBOX_RECOGNITION_DRAIN and MEMORYBOX_SPEECH_DRAIN.
Claims only enqueue_reason=owner_learn rows for the active bounded admission.
"""
from __future__ import annotations

import os
import threading
import time

_started = False
_worker_lock = threading.Lock()


def interactive_learn_worker_enabled() -> bool:
    explicit = (os.environ.get("MEMORYBOX_INTERACTIVE_LEARN_WORKER") or "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    try:
        from memorybox.processing.scope import load_admission

        return load_admission().interactive_learn_permitted()
    except Exception:
        return False


def recover_stale_interactive_jobs(*, admission_id: str | None = None) -> dict[str, int]:
    """Re-queue owner_learn rows stuck in running after a crash or restart."""
    from memorybox.processing.scope import ScopeDenied, load_admission
    from memorybox.db import connection

    try:
        admission = load_admission()
    except ScopeDenied:
        return {"face": 0, "voice": 0}
    if admission_id and admission.id != admission_id:
        return {"face": 0, "voice": 0}
    if not admission.interactive_learn_permitted():
        return {"face": 0, "voice": 0}
    with connection() as conn:
        face = conn.execute(
            """
            UPDATE recognition_queue_items
            SET status = 'queued', updated_at = now(), finished_at = NULL
            WHERE status = 'running'
              AND enqueue_reason = 'owner_learn'
              AND i13_admission_id = %s::uuid
            """,
            (admission.id,),
        ).rowcount
        voice = conn.execute(
            """
            UPDATE speech_queue_items
            SET status = 'queued', updated_at = now(), finished_at = NULL
            WHERE status = 'running'
              AND enqueue_reason = 'owner_learn'
              AND i13_admission_id = %s::uuid
            """,
            (admission.id,),
        ).rowcount
    return {"face": int(face or 0), "voice": int(voice or 0)}


def start_interactive_learn_worker() -> None:
    global _started
    if not interactive_learn_worker_enabled():
        return
    with _worker_lock:
        if _started:
            return
        _started = True

    recover_stale_interactive_jobs()

    def _loop() -> None:
        from memorybox.ask.deps import build_video
        from memorybox.recognition.process import process_one as process_face_one
        from memorybox.speech.process import process_one as process_speech_one

        while True:
            try:
                if not interactive_learn_worker_enabled():
                    time.sleep(6.0)
                    continue
                video = build_video()
                face = process_face_one(video_provider=video, interactive=True)
                if face:
                    time.sleep(0.4)
                    continue
                speech = process_speech_one(video_provider=video, interactive=True)
                time.sleep(0.4 if speech else 6.0)
            except Exception:
                time.sleep(10.0)

    threading.Thread(target=_loop, name="mb-interactive-learn", daemon=True).start()


def reset_interactive_learn_worker_for_tests() -> None:
    """Test-only reset of worker singleton state."""
    global _started
    with _worker_lock:
        _started = False
