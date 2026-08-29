"""Shared provider errors and health."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    """Base provider failure (visible to callers — never silent empty success)."""


class ProviderUnavailable(ProviderError):
    """Provider cannot be reached or is not configured."""


@dataclass(frozen=True)
class ProviderHealth:
    provider_key: str
    ok: bool
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
