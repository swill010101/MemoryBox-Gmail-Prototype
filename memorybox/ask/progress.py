"""In-memory Ask progress for the Explore curator ticker (one line at a time)."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

import threading
import time
from typing import Any

_request_id = ContextVar("ask_progress_request", default=None)

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def _key(session_id: str | None, request_id: str | None = None) -> str:
    if request_id:
        return "request:" + request_id
    return str(session_id or "").strip() or "_default"


@contextmanager
def ask_progress_request(request_id: str | None):
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        if request_id:
            with _lock:
                _state.pop(_key(None, request_id), None)
        _request_id.reset(token)


def note_ask_progress(session_id: str | None, line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    with _lock:
        _state[_key(session_id, _request_id.get())] = {"line": text, "updated_at": time.time()}


def get_ask_progress(session_id: str | None, request_id: str | None = None) -> dict[str, Any]:
    with _lock:
        row = dict(_state.get(_key(session_id, request_id)) or {})
    return {"ok": True, "line": row.get("line") or "", "updated_at": row.get("updated_at")}


def clear_ask_progress(session_id: str | None) -> None:
    with _lock:
        _state.pop(_key(session_id, _request_id.get()), None)
