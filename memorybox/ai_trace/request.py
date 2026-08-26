"""Ask / job request traces — including deterministic zero-model paths."""
from __future__ import annotations

import time
import traceback
from types import TracebackType
from typing import Any
from uuid import uuid4

from memorybox.ai_trace import context as ctx
from memorybox.ai_trace import store


class RequestTrace:
    def __init__(
        self,
        *,
        request_kind: str,
        originating_ask: str,
        session_id: str | None = None,
        purpose: str | None = None,
        initiator: dict[str, Any] | None = None,
    ) -> None:
        self.trace_id = str(uuid4())
        self.request_kind = request_kind
        self.originating_ask = originating_ask
        self.session_id = session_id
        self.purpose = purpose or request_kind
        self.initiator = initiator or {}
        self._t0 = time.perf_counter()
        self._token = None
        self._t0_token = None
        self._purpose_token = None
        self._assembled_token = None
        self._closed = False
        self._planner_noted = False
        self._retrieve_line: str | None = None

    def __enter__(self) -> "RequestTrace":
        store.insert_trace(
            trace_id=self.trace_id,
            request_kind=self.request_kind,
            originating_ask=self.originating_ask,
            session_id=self.session_id,
            purpose=self.purpose,
            initiator=self.initiator,
        )
        self._token = ctx.set_current_trace_id(self.trace_id)
        self._t0_token = ctx.set_current_trace_t0(self._t0)
        self._purpose_token = ctx.set_purpose(self.purpose)
        store.insert_span(
            trace_id=self.trace_id,
            stage="initiation",
            component="orchestrator",
            operation="request",
            assembled_context={
                "ask": self.originating_ask,
                "session_id": self.session_id,
                "request_kind": self.request_kind,
            },
            meta=self.initiator,
        )
        return self

    def set_assembled(self, assembled: dict[str, Any] | None) -> None:
        if self._assembled_token is not None:
            ctx.reset_assembled_context(self._assembled_token)
            self._assembled_token = None
        if assembled is not None:
            self._assembled_token = ctx.set_assembled_context(assembled)
            store.update_trace(self.trace_id, assembled_context=assembled)

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def heartbeat(self, *, extra: dict[str, Any] | None = None) -> None:
        """Bump updated_at + live duration so retrieve is not mistaken for a dead Ask."""
        del extra
        store.update_trace(self.trace_id, duration_ms=self.elapsed_ms())

    def note_retrieve(self, line: str, extra: dict[str, Any] | None = None) -> None:
        self.heartbeat(extra={"line": line, **(extra or {})})
        if line == self._retrieve_line:
            return
        self._retrieve_line = line
        store.insert_span(
            trace_id=self.trace_id,
            stage="retrieve",
            component="orchestrator",
            operation="retrieve_progress",
            status="running",
            assembled_context={
                "line": line,
                "elapsed_ms": self.elapsed_ms(),
                **(extra or {}),
            },
        )

    def note_planner(self, plan: dict[str, Any]) -> None:
        if self._planner_noted:
            self.heartbeat(extra={"planner_refresh": True})
            return
        self._planner_noted = True
        self.set_assembled({"plan": plan})
        store.insert_span(
            trace_id=self.trace_id,
            stage="planner",
            component="planner",
            operation="plan_ask",
            assembled_context={"plan": plan},
            disposition={
                "requires_clarification": plan.get("requires_clarification"),
                "want_communication": plan.get("want_communication"),
                "want_visual": plan.get("want_visual"),
                "person_names": plan.get("person_names"),
                "act": plan.get("act"),
                "compile_provenance": plan.get("compile_provenance"),
            },
        )

    def note_parse(
        self,
        *,
        raw: Any,
        parsed: Any,
        validation: dict[str, Any] | None = None,
        error_class: str | None = None,
        status: str = "ok",
    ) -> None:
        store.insert_span(
            trace_id=self.trace_id,
            stage="parse_validate",
            component="harness" if self.request_kind == "harness" else "orchestrator",
            operation="parse_validate",
            status=status,
            error_class=error_class,
            raw_response={"raw": raw} if not isinstance(raw, dict) else raw,
            parsed=parsed if isinstance(parsed, dict) else {"value": parsed},
            validation=validation,
        )

    def complete(
        self,
        *,
        disposition: dict[str, Any],
        status: str = "ok",
        error_class: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        if self._closed:
            return
        ms = int((time.perf_counter() - self._t0) * 1000)
        store.insert_span(
            trace_id=self.trace_id,
            stage="disposition",
            component="orchestrator",
            operation="disposition",
            status=status,
            error_class=error_class,
            disposition=disposition,
            error=error,
        )
        store.insert_span(
            trace_id=self.trace_id,
            stage="final_result",
            component="orchestrator",
            operation="final_result",
            status=status,
            error_class=error_class,
            disposition=disposition,
        )
        store.update_trace(
            self.trace_id,
            status=status,
            error_class=error_class,
            final_disposition=disposition,
            error=error,
            duration_ms=ms,
        )
        self._closed = True

    def fail(self, error_class: str, exc: BaseException) -> None:
        self.complete(
            disposition={"ok": False, "error_class": error_class},
            status="error",
            error_class=error_class,
            error={
                "class": error_class,
                "type": type(exc).__name__,
                "message": str(exc),
                "stack": traceback.format_exc(),
            },
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc is not None and not self._closed:
                self.fail("ORCHESTRATION", exc)
            elif not self._closed:
                self.complete(disposition={"ok": True, "note": "closed_without_explicit_complete"})
        finally:
            if self._assembled_token is not None:
                ctx.reset_assembled_context(self._assembled_token)
            if self._purpose_token is not None:
                ctx.reset_purpose(self._purpose_token)
            if self._t0_token is not None:
                ctx.reset_current_trace_t0(self._t0_token)
            if self._token is not None:
                ctx.reset_current_trace_id(self._token)


_HB_LAST = 0.0
_HB_MIN_SEC = 2.0


def heartbeat_retrieve(
    *, offset: int | None = None, line: str | None = None, span: bool = False
) -> None:
    """Fail-open retrieve heartbeat; throttled so paging does not hammer Postgres."""
    global _HB_LAST
    tid = ctx.current_trace_id()
    if not tid:
        return
    now = time.monotonic()
    if now - _HB_LAST < _HB_MIN_SEC and offset is None and not span:
        return
    _HB_LAST = now
    t0 = ctx.current_trace_t0()
    elapsed = int((time.perf_counter() - t0) * 1000) if t0 is not None else None
    store.update_trace(tid, duration_ms=elapsed)
    if span and line:
        store.insert_span(
            trace_id=tid,
            stage="retrieve",
            component="retrieve",
            operation="retrieve_progress",
            status="running",
            assembled_context={
                "line": line,
                "offset": offset,
                "elapsed_ms": elapsed,
            },
        )


def tracing_ask(text: str, session_id: str | None = None) -> RequestTrace:
    return RequestTrace(
        request_kind="ask",
        originating_ask=text,
        session_id=session_id,
        purpose="ask",
        initiator={"kind": "ask", "ask": text, "session_id": session_id},
    )


def tracing_job(name: str, **meta: Any) -> RequestTrace:
    return RequestTrace(
        request_kind="job",
        originating_ask=name,
        purpose=name,
        initiator={"kind": "job", "name": name, **meta},
    )


def tracing_harness(name: str, **meta: Any) -> RequestTrace:
    return RequestTrace(
        request_kind="harness",
        originating_ask=name,
        purpose=name,
        initiator={"kind": "harness", "scenario": name, **meta},
    )
