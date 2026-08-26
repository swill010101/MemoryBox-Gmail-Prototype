"""LLM provider DTOs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class EmbeddingDto:
    model: str
    vector: tuple[float, ...]
    purpose: Literal["query", "document"]


@dataclass(frozen=True)
class ChatResultDto:
    model: str
    content: str
    usage: dict[str, Any] | None = None
