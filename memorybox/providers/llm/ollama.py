"""Ollama LlmProvider adapter — in-package HTTP helpers (config-driven base_url)."""
from __future__ import annotations

import os
from typing import Literal

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto
from memorybox.providers.llm import _ollama_http as oh


def ollama_chat_timeout_seconds() -> int:
    timeout = 90
    raw_to = (os.environ.get("MEMORYBOX_OLLAMA_CHAT_TIMEOUT") or "").strip()
    if raw_to.isdigit() and int(raw_to) >= 15:
        timeout = int(raw_to)
    return timeout


class OllamaLlmProvider:
    provider_key = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str = "llama3.2",
        embed_model: str = "nomic-embed-text",
    ) -> None:
        if not base_url:
            raise ProviderUnavailable("Ollama base_url is required via configuration")
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    def health(self) -> ProviderHealth:
        try:
            tags = oh.ollama_tags(self.base_url)
            models = tags.get("models") if isinstance(tags, dict) else None
            return ProviderHealth(
                provider_key=self.provider_key,
                ok=True,
                detail="tags ok",
                meta={"model_count": len(models or [])},
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(
                provider_key=self.provider_key, ok=False, detail=str(exc)
            )

    def embed(
        self, text: str, *, purpose: Literal["query", "document"] = "document"
    ) -> EmbeddingDto:
        try:
            vec = oh.ollama_embed(
                self.base_url,
                self.embed_model,
                text,
                query=(purpose == "query"),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailable(str(exc)) from exc
        return EmbeddingDto(
            model=self.embed_model, vector=tuple(float(x) for x in vec), purpose=purpose
        )

    def chat(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> ChatResultDto:
        system = "\n".join(m.content for m in messages if m.role == "system") or ""
        user_parts = [m.content for m in messages if m.role == "user"]
        if not user_parts:
            raise ProviderError("chat requires at least one user message")
        user = "\n".join(user_parts)
        timeout = ollama_chat_timeout_seconds()
        try:
            content, usage = oh.ollama_chat(
                self.base_url,
                self.chat_model,
                system,
                user,
                format_json=json_mode,
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise ProviderUnavailable(f"timed out after {timeout}s") from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "timed out" in msg or "timeout" in msg:
                raise ProviderUnavailable(f"timed out after {timeout}s") from exc
            raise ProviderUnavailable(str(exc)) from exc
        return ChatResultDto(model=self.chat_model, content=content, usage=usage)
