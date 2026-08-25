"""Provider-neutral LlmProvider wrapper — traces chat and embed only."""
from __future__ import annotations

import time
import traceback
from typing import Any, Literal
from uuid import uuid4

from memorybox.ai_trace import context as ctx
from memorybox.ai_trace import store
from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto
from memorybox.providers.llm.protocol import LlmProvider


def _host_of(inner: Any) -> str | None:
    url = getattr(inner, "base_url", None)
    if not url:
        return None
    from memorybox.ai_trace.redact import redact

    return str(redact(str(url)))


def _model_meta(inner: Any, *, capability: str, model: str | None) -> dict[str, Any]:
    return {
        "provider_key": getattr(inner, "provider_key", None),
        "model": model,
        "host": _host_of(inner),
        "capability": capability,
    }


def _classify(exc: BaseException) -> str:
    if isinstance(exc, ProviderUnavailable):
        return "PROVIDER_TRANSPORT"
    if isinstance(exc, ProviderError):
        return "MODEL_EXECUTION"
    return "MODEL_EXECUTION"


def _ensure_parent_trace(*, operation: str) -> str | None:
    existing = ctx.current_trace_id()
    if existing:
        return existing
    tid = str(uuid4())
    ok = store.insert_trace(
        trace_id=tid,
        request_kind="job",
        originating_ask=f"standalone {operation}",
        purpose=operation,
        initiator={"kind": "standalone", "operation": operation},
    )
    if not ok:
        return None
    ctx.set_current_trace_id(tid)
    return tid


class TracedLlmProvider:
    """Delegates to an inner LlmProvider; emits the same lifecycle for Fake and Ollama."""

    def __init__(self, inner: LlmProvider) -> None:
        self.inner = inner
        self.provider_key = getattr(inner, "provider_key", "unknown")

    def health(self) -> ProviderHealth:
        return self.inner.health()

    def embed(
        self, text: str, *, purpose: Literal["query", "document"] = "document"
    ) -> EmbeddingDto:
        assembled = ctx.current_assembled_context() or {
            "purpose": purpose,
            "component": "embed",
        }
        payload = {"text": text, "purpose": purpose}
        model_name = getattr(self.inner, "embed_model", None)
        t0 = time.perf_counter()
        started = store._now()
        tid = _ensure_parent_trace(operation="embed")
        try:
            result = self.inner.embed(text, purpose=purpose)
            ms = int((time.perf_counter() - t0) * 1000)
            if tid:
                store.insert_span(
                    trace_id=tid,
                    stage="provider_call",
                    component="llm_wrapper",
                    operation="embed",
                    status="ok",
                    started_at=started,
                    duration_ms=ms,
                    assembled_context=assembled,
                    provider_payload=payload,
                    raw_response={
                        "model": result.model,
                        "purpose": result.purpose,
                        "dimensions": len(result.vector),
                        "vector_persisted": False,
                    },
                    model=_model_meta(
                        self.inner, capability="embedding", model=result.model
                    ),
                    meta={"input_chars": len(text or "")},
                )
            return result
        except Exception as exc:  # noqa: BLE001
            ms = int((time.perf_counter() - t0) * 1000)
            klass = _classify(exc)
            if tid:
                store.insert_span(
                    trace_id=tid,
                    stage="provider_call",
                    component="llm_wrapper",
                    operation="embed",
                    status="error",
                    error_class=klass,
                    started_at=started,
                    duration_ms=ms,
                    assembled_context=assembled,
                    provider_payload=payload,
                    model=_model_meta(
                        self.inner, capability="embedding", model=model_name
                    ),
                    error={
                        "class": klass,
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "stack": traceback.format_exc(),
                    },
                    meta={"input_chars": len(text or "")},
                )
                store.update_trace(tid, status="error", error_class=klass)
            raise

    def chat(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> ChatResultDto:
        assembled = ctx.current_assembled_context()
        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "json_mode": bool(json_mode),
            "model": getattr(self.inner, "chat_model", None),
        }
        t0 = time.perf_counter()
        started = store._now()
        tid = _ensure_parent_trace(operation="chat")
        try:
            result = self.inner.chat(messages, json_mode=json_mode)
            ms = int((time.perf_counter() - t0) * 1000)
            if tid:
                store.insert_span(
                    trace_id=tid,
                    stage="provider_call",
                    component="llm_wrapper",
                    operation="chat",
                    status="ok",
                    started_at=started,
                    duration_ms=ms,
                    assembled_context=assembled,
                    provider_payload=payload,
                    raw_response={
                        "model": result.model,
                        "content": result.content,
                    },
                    model=_model_meta(
                        self.inner, capability="llm", model=result.model
                    ),
                )
            return result
        except Exception as exc:  # noqa: BLE001
            ms = int((time.perf_counter() - t0) * 1000)
            klass = _classify(exc)
            if tid:
                store.insert_span(
                    trace_id=tid,
                    stage="provider_call",
                    component="llm_wrapper",
                    operation="chat",
                    status="error",
                    error_class=klass,
                    started_at=started,
                    duration_ms=ms,
                    assembled_context=assembled,
                    provider_payload=payload,
                    model=_model_meta(
                        self.inner,
                        capability="llm",
                        model=getattr(self.inner, "chat_model", None),
                    ),
                    error={
                        "class": klass,
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "stack": traceback.format_exc(),
                    },
                )
            raise


def trace_llm(provider: LlmProvider) -> LlmProvider:
    if isinstance(provider, TracedLlmProvider):
        return provider
    return TracedLlmProvider(provider)
