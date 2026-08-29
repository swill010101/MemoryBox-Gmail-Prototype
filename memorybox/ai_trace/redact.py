"""Secret redaction before trace persistence (not display-only)."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_SECRET_KEY = re.compile(
    r"(api[_-]?key|authorization|auth|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|secret|cookie|bearer|credential|private[_-]?key)",
    re.I,
)
_SECRET_VALUE = re.compile(
    r"(?i)(\bBearer\s+\S+|\bsk-[A-Za-z0-9]{8,}|\bghp_[A-Za-z0-9]+|"
    r"\bxox[baprs]-[A-Za-z0-9-]+)"
)
_REDACTED = "[REDACTED]"


def _redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except Exception:
        return value
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = host
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return value


def redact(value: Any) -> Any:
    """Return a JSON-safe copy with secrets stripped."""
    if value is None:
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _SECRET_KEY.search(key):
                out[key] = _REDACTED
            else:
                out[key] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        text = _redact_url(value)
        return _SECRET_VALUE.sub(_REDACTED, text)
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)
