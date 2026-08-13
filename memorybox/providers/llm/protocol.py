"""LlmProvider protocol."""
from __future__ import annotations

from typing import Literal, Protocol

from memorybox.providers.base import ProviderHealth
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto


class LlmProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def embed(
        self, text: str, *, purpose: Literal["query", "document"] = "document"
    ) -> EmbeddingDto: ...

    def chat(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> ChatResultDto: ...
