"""In-memory Ask progress for the Explore curator ticker (one line at a time)."""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def _key(session_id: str | None) -> str:
    return str(session_id or "").strip() or "_default"


def note_ask_progress(session_id: str | None, line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    with _lock:
        _state[_key(session_id)] = {"line": text, "updated_at": time.time()}


def get_ask_progress(session_id: str | None) -> dict[str, Any]:
    with _lock:
        row = dict(_state.get(_key(session_id)) or {})
    return {"ok": True, "line": row.get("line") or "", "updated_at": row.get("updated_at")}


def clear_ask_progress(session_id: str | None) -> None:
    with _lock:
        _state.pop(_key(session_id), None)
