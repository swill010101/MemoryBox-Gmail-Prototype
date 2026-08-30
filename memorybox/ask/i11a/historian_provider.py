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
    num_ctx: int | None = None


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

    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        timeout_seconds: int,
        num_ctx: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.timeout_seconds = int(timeout_seconds)
        self.num_ctx = int(num_ctx) if num_ctx else None

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
                num_ctx=self.num_ctx,
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


class _CloudOpenAICompatChat:
    """Explicit opt-in cloud control (Sol). Stateless single request only.

    Requires MEMORYBOX_CLOUD_LLM_BASE_URL and MEMORYBOX_CLOUD_LLM_API_KEY.
    Never selected unless --provider cloud.
    """

    provider_key = "cloud"

    def __init__(self, *, chat_model: str, timeout_seconds: int) -> None:
        import os

        self.chat_model = chat_model
        self.timeout_seconds = int(timeout_seconds)
        self.base_url = (os.environ.get("MEMORYBOX_CLOUD_LLM_BASE_URL") or "").rstrip("/")
        self.api_key = (os.environ.get("MEMORYBOX_CLOUD_LLM_API_KEY") or "").strip()

    def health(self) -> Any:
        from memorybox.providers.base import ProviderHealth

        ok = bool(self.base_url and self.api_key)
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=ok,
            detail=(
                "cloud OpenAI-compatible endpoint configured"
                if ok
                else "set MEMORYBOX_CLOUD_LLM_BASE_URL and MEMORYBOX_CLOUD_LLM_API_KEY"
            ),
        )

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        import json as _json
        import urllib.error
        import urllib.request

        if not self.base_url or not self.api_key:
            raise HistorianCloudNotAvailable(
                "Cloud provider requires MEMORYBOX_CLOUD_LLM_BASE_URL and "
                "MEMORYBOX_CLOUD_LLM_API_KEY. Stateless single-request only "
                "(no ChatGPT history, MemoryBox memory, or profile context)."
            )
        url = self.base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "temperature": 0,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailable(f"cloud chat failed: {exc}") from exc
        choices = body.get("choices") or []
        content = ""
        if choices:
            content = str(((choices[0] or {}).get("message") or {}).get("content") or "")
        usage = dict(body.get("usage") or {})
        usage["timeout_seconds"] = self.timeout_seconds
        usage["model"] = self.chat_model
        usage["provider_key"] = self.provider_key
        usage["stateless"] = True
        return ChatResultDto(model=self.chat_model, content=content, usage=usage)


def build_historian_provider(spec: HistorianProviderSpec) -> Any:
    """Construct provider from explicit spec. Never defaults to cloud."""
    model = (spec.model or "").strip()
    if not model:
        raise HistorianProviderError("--model is required for historian-fixture-run")
    if spec.provider == "cloud":
        return _CloudOpenAICompatChat(chat_model=model, timeout_seconds=spec.timeout_seconds)
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
        num_ctx=spec.num_ctx,
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
