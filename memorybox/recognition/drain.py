"""Background drain of recognition_queue — one video at a time."""
from __future__ import annotations

import os
import threading
import time

_started = False


def recognition_drain_enabled() -> bool:
    explicit = (os.environ.get("MEMORYBOX_RECOGNITION_DRAIN") or "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip() in {"1", "true", "yes"}


def start_recognition_drain() -> None:
    global _started
    if _started or not recognition_drain_enabled():
        return
    _started = True

    def _loop() -> None:
        from memorybox.ask.deps import build_video
        from memorybox.recognition.process import process_one

        while True:
            try:
                video = build_video()
                result = process_one(video_provider=video)
                time.sleep(0.4 if result else 6.0)
            except Exception:
                time.sleep(10.0)

    threading.Thread(target=_loop, name="mb-recognition-drain", daemon=True).start()
