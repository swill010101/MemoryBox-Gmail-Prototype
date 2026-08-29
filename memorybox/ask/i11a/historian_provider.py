"""Historian fixture model providers — local Ollama now; cloud opt-in later.

Cloud runs must be explicit (--provider cloud). The fixture bytes sent to any
provider are identical: same system message and user JSON payload. Transport
formatting may differ; semantic prompt content must not be rewritten.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from memorybox.providers.base import ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto

HistorianProviderKind = Literal["ollama", "cloud"]


class HistorianProviderError(Exception):
    """Fixture runner provider configuration or call error."""


class HistorianModelMismatch(HistorianProviderError):
    """Requested model does not match configured provider model."""


class HistorianCloudNotAvailable(HistorianProviderError):
    """Cloud provider selected but not implemented or not configured."""


@dataclass(frozen=True)
class HistorianProviderSpec:
    """Explicit provider choice for a fixture run."""

    provider: HistorianProviderKind
    model: str
    timeout_seconds: int


def normalize_provider_kind(raw: str | None) -> HistorianProviderKind:
    token = (raw or "ollama").strip().lower()
    if token in {"ollama", "local"}:
        return "ollama"
    if token == "cloud":
        return "cloud"
    raise HistorianProviderError(
        f"Unknown historian provider {raw!r}; use ollama (local) or cloud."
    )


def assert_model_matches(provider: Any, requested_model: str) -> str:
    """Abort before any LLM request if configured model != requested model."""
    inner = getattr(provider, "inner", provider)
    actual = (
        getattr(inner, "chat_model", None)
        or getattr(provider, "chat_model", None)
        or getattr(inner, "model", None)
        or getattr(provider, "model", None)
    )
    requested = (requested_model or "").strip()
    if not actual or str(actual).strip() != requested:
        raise HistorianModelMismatch(
            f"requested model {requested!r} != provider chat_model {actual!r}; aborting before LLM call"
        )
    return str(actual)


def sanitize_model_for_filename(model: str) -> str:
    return (
        (model or "unknown")
        .replace(":", "-")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
    )


class _TimeoutOllamaChat:
    """Ollama provider with explicit model + timeout for fixture runs (no env ambiguity)."""

    provider_key = "ollama"

    def __init__(self, *, base_url: str, chat_model: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.timeout_seconds = int(timeout_seconds)

    def health(self) -> Any:
        from memorybox.providers.llm.ollama import OllamaLlmProvider

        return OllamaLlmProvider(
            base_url=self.base_url,
            chat_model=self.chat_model,
        ).health()

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        from memorybox.providers.llm import _ollama_http as oh

        system = "\n".join(m.content for m in messages if m.role == "system") or ""
        user_parts = [m.content for m in messages if m.role == "user"]
        if not user_parts:
            raise ProviderUnavailable("chat requires at least one user message")
        user = "\n".join(user_parts)
        try:
            content, usage = oh.ollama_chat(
                self.base_url,
                self.chat_model,
                system,
                user,
                format_json=json_mode,
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderUnavailable(f"timed out after {self.timeout_seconds}s") from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "timed out" in msg or "timeout" in msg:
                raise ProviderUnavailable(f"timed out after {self.timeout_seconds}s") from exc
            raise ProviderUnavailable(str(exc)) from exc
        usage = dict(usage or {})
        usage["timeout_seconds"] = self.timeout_seconds
        usage["model"] = self.chat_model
        usage["provider_key"] = self.provider_key
        return ChatResultDto(model=self.chat_model, content=content, usage=usage)


class _CloudHistorianStub:
    """Placeholder — cloud benchmark requires explicit --provider cloud."""

    provider_key = "cloud"

    def __init__(self, *, chat_model: str, timeout_seconds: int) -> None:
        self.chat_model = chat_model
        self.timeout_seconds = int(timeout_seconds)

    def health(self) -> Any:
        from memorybox.providers.base import ProviderHealth

        return ProviderHealth(
            provider_key=self.provider_key,
            ok=False,
            detail="cloud historian provider not implemented",
        )

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        raise HistorianCloudNotAvailable(
            "Cloud historian provider is not implemented yet. "
            "Use --provider ollama for local Ollama runs. "
            "When implemented, cloud calls will be stateless single-request only "
            "(no ChatGPT history, MemoryBox memory, or profile context)."
        )


def build_historian_provider(spec: HistorianProviderSpec) -> Any:
    """Construct provider from explicit spec. Never defaults to cloud."""
    model = (spec.model or "").strip()
    if not model:
        raise HistorianProviderError("--model is required for historian-fixture-run")
    if spec.provider == "cloud":
        return _CloudHistorianStub(chat_model=model, timeout_seconds=spec.timeout_seconds)
    from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
    from memorybox.providers.llm._ollama_http import ollama_reachable

    base = (settings.ollama_base_url or "").strip()
    if not base:
        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                base = url
                break
    if not base:
        raise HistorianProviderError(
            "No Ollama base URL configured and daemon not reachable for --provider ollama"
        )
    return _TimeoutOllamaChat(
        base_url=base,
        chat_model=model,
        timeout_seconds=spec.timeout_seconds,
    )


def historian_chat_json(
    provider: Any,
    *,
    system: str,
    user_payload: dict[str, Any] | None = None,
    user_message: str | None = None,
    json_mode: bool = True,
    requested_model: str,
) -> tuple[str, dict[str, Any], int]:
    """Stateless chat: system + user JSON only. Returns (raw, usage, wall_ms).

    Prefer user_message when provided (exact frozen request bytes). Otherwise
    dump user_payload with the same sort_keys=True contract as fixture prepare.
    """
    assert_model_matches(provider, requested_model)
    if user_message is None:
        user_message = json.dumps(user_payload or {}, default=str, sort_keys=True)
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user_message),
    ]
    t0 = time.perf_counter()
    result = provider.chat(messages, json_mode=json_mode)
    wall_ms = int((time.perf_counter() - t0) * 1000)
    usage = dict(getattr(result, "usage", None) or {})
    usage.setdefault("model", getattr(result, "model", None) or requested_model)
    usage.setdefault(
        "provider_key",
        getattr(provider, "provider_key", None),
    )
    return str(getattr(result, "content", "") or ""), usage, wall_ms


def historian_chat_text(
    provider: Any,
    *,
    system: str,
    user_text: str,
    json_mode: bool = False,
    requested_model: str,
) -> tuple[str, dict[str, Any], int]:
    assert_model_matches(provider, requested_model)
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user_text),
    ]
    t0 = time.perf_counter()
    result = provider.chat(messages, json_mode=json_mode)
    wall_ms = int((time.perf_counter() - t0) * 1000)
    usage = dict(getattr(result, "usage", None) or {})
    usage.setdefault("model", getattr(result, "model", None) or requested_model)
    usage.setdefault("provider_key", getattr(provider, "provider_key", None))
    return str(getattr(result, "content", "") or ""), usage, wall_ms
