"""Request-scoped trace binding (contextvars). Fail-open callers ignore misses."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_trace_id: ContextVar[str | None] = ContextVar("mb_ai_trace_id", default=None)
_assembled: ContextVar[dict[str, Any] | None] = ContextVar(
    "mb_ai_trace_assembled", default=None
)
_purpose: ContextVar[str | None] = ContextVar("mb_ai_trace_purpose", default=None)


def current_trace_id() -> str | None:
    return _trace_id.get()


def set_current_trace_id(trace_id: str | None):
    return _trace_id.set(trace_id)


def reset_current_trace_id(token) -> None:
    _trace_id.reset(token)


def current_assembled_context() -> dict[str, Any] | None:
    return _assembled.get()


def set_assembled_context(payload: dict[str, Any] | None):
    return _assembled.set(payload)


def reset_assembled_context(token) -> None:
    _assembled.reset(token)


def current_purpose() -> str | None:
    return _purpose.get()


def set_purpose(purpose: str | None):
    return _purpose.set(purpose)


def reset_purpose(token) -> None:
    _purpose.reset(token)
