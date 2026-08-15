"""Harness-only forced-model scenarios (T1–T10). Not MBQL. Not production Ask."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from memorybox.ai_trace import store
from memorybox.ai_trace.request import tracing_ask, tracing_harness
from memorybox.ai_trace.wrapper import trace_llm
from memorybox.providers.base import ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto, EmbeddingDto
from memorybox.providers.llm.fake import FakeLlmProvider


class _ScriptedChat:
    provider_key = "harness_llm"
    chat_model = "harness-chat"
    embed_model = "harness-embed"

    def __init__(self, replies: list[str] | None = None, *, fail: Exception | None = None) -> None:
        self._replies = list(replies or [])
        self._fail = fail
        self.calls = 0

    def health(self):
        from memorybox.providers.base import ProviderHealth

        return ProviderHealth(provider_key=self.provider_key, ok=self._fail is None, detail="harness")

    def embed(self, text: str, *, purpose: str = "document") -> EmbeddingDto:
        return EmbeddingDto(model=self.embed_model, vector=(0.1, 0.2, 0.3), purpose=purpose)  # type: ignore[arg-type]

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        self.calls += 1
        if self._fail is not None:
            raise self._fail
        if self._replies:
            content = self._replies.pop(0)
        else:
            content = '{"ok":true,"intent":"sms"}' if json_mode else "ok"
        return ChatResultDto(model=self.chat_model, content=content)


def _messages(*parts: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=p) for p in parts]


def _parse_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "PARSE_SCHEMA"
    if not isinstance(data, dict):
        return None, "PARSE_SCHEMA"
    return data, None


def run_scenario(name: str) -> dict[str, Any]:
    key = (name or "").strip().upper()
    fn = {
        "T1": _t1,
        "T2": _t2,
        "T3": _t3,
        "T4": _t4,
        "T5": _t5,
        "T6": _t6,
        "T7": _t7,
        "T8": _t8,
        "T9": _t9,
        "T10": _t10,
    }.get(key)
    if fn is None:
        return {"ok": False, "error": f"unknown scenario {name}"}
    return fn()


def _t1() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(['{"ok":true,"intent":"sms"}']))
    with tracing_harness("T1") as tr:
        assembled = {
            "task": "interpret_ask",
            "person_names": ["Peggy"],
            "channel": "sms",
            "evidence_refs": ["ev-demo-1"],
        }
        tr.set_assembled(assembled)
        tr.note_planner(
            {
                "original_ask": "T1 normal model call",
                "person_names": ["Peggy"],
                "want_communication": True,
            }
        )
        result = llm.chat(_messages("Classify this Ask as sms or email"), json_mode=True)
        parsed, err = _parse_json(result.content)
        tr.note_parse(raw=result.content, parsed=parsed, validation={"ok": err is None})
        tr.complete(
            disposition={
                "accepted": parsed,
                "answer_kind": "harness_model",
                "intent": (parsed or {}).get("intent"),
            }
        )
    return {"ok": True, "scenario": "T1", "trace_id": tr.trace_id, "error_class": None}


def _t2() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(['{"ok":true}']))
    with tracing_harness("T2") as tr:
        wrong = {
            "task": "interpret_ask",
            "person_ids": ["WRONG-PERSON"],
            "person_names": ["Not Peggy"],
            "note": "forced wrong normalized context",
        }
        tr.set_assembled(wrong)
        tr.note_planner({"person_ids": ["WRONG-PERSON"], "defect": "wrong_person"})
        llm.chat(_messages("Who is this about?"), json_mode=True)
        tr.complete(
            disposition={"accepted": False, "reason": "wrong pre-model context"},
            status="error",
            error_class="ORCHESTRATION",
            error={"class": "ORCHESTRATION", "message": "Planner selected the wrong Person ID"},
        )
    return {"ok": True, "scenario": "T2", "trace_id": tr.trace_id, "error_class": "ORCHESTRATION"}


def _t3() -> dict[str, Any]:
    from memorybox.ask.orchestrator import AskOrchestrator
    from memorybox.providers.photo.fake import FakePhotoProvider
    from memorybox.providers.video.fake import FakeVideoProvider

    orch = AskOrchestrator(
        llm=FakeLlmProvider(),
        photo=FakePhotoProvider(),
        video=FakeVideoProvider(),
    )
    result = orch.ask("How many text messages did I send?")
    return {
        "ok": True,
        "scenario": "T3",
        "trace_id": getattr(result, "trace_id", None),
        "answer_kind": result.answer_kind,
        "model_calls_expected": 0,
    }


def _t4() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(["this is not json and claims the user meant email"]))
    with tracing_harness("T4") as tr:
        tr.set_assembled({"task": "interpret_ask", "expected_schema": {"intent": "sms|email"}})
        tr.note_planner({"original_ask": "show my texts with Peggy"})
        result = llm.chat(_messages("Return JSON intent"), json_mode=True)
        parsed, err = _parse_json(result.content)
        klass = "MODEL_OUTPUT" if err else "MODEL_OUTPUT"
        tr.note_parse(
            raw=result.content,
            parsed=parsed,
            validation={"ok": False, "reason": "malformed or wrong intent"},
            error_class=klass,
            status="error",
        )
        tr.complete(
            disposition={"accepted": False},
            status="error",
            error_class=klass,
        )
    return {"ok": True, "scenario": "T4", "trace_id": tr.trace_id, "error_class": "MODEL_OUTPUT"}


def _t5() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(fail=ProviderUnavailable("ollama unreachable (harness)")))
    with tracing_harness("T5") as tr:
        tr.set_assembled({"task": "interpret_ask"})
        tr.note_planner({"original_ask": "T5 provider down"})
        try:
            llm.chat(_messages("hello"), json_mode=True)
            status = "ok"
            klass = None
        except ProviderUnavailable as exc:
            status = "error"
            klass = "PROVIDER_TRANSPORT"
            tr.fail(klass, exc)
    return {"ok": True, "scenario": "T5", "trace_id": tr.trace_id, "error_class": klass, "status": status}


def _t6() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(['{"ok":true,"intent":"sms"}']))
    with tracing_harness("T6") as tr:
        tr.set_assembled({"task": "interpret_ask", "required_fields": ["intent", "confidence"]})
        result = llm.chat(_messages("Return JSON"), json_mode=True)
        parsed, _ = _parse_json(result.content)
        # Valid model JSON; harness parser requires confidence (forced defect).
        missing = [f for f in ("intent", "confidence") if f not in (parsed or {})]
        tr.note_parse(
            raw=result.content,
            parsed=parsed,
            validation={"ok": False, "missing": missing},
            error_class="PARSE_SCHEMA",
            status="error",
        )
        tr.complete(
            disposition={"accepted": False, "raw_preserved": True},
            status="error",
            error_class="PARSE_SCHEMA",
        )
    return {"ok": True, "scenario": "T6", "trace_id": tr.trace_id, "error_class": "PARSE_SCHEMA"}


def _t7() -> dict[str, Any]:
    llm = trace_llm(
        _ScriptedChat(['{"assertion":"Peggy lived on Mars in 2019","supported_by_evidence":false}'])
    )
    with tracing_harness("T7") as tr:
        tr.set_assembled({"task": "trust_check", "evidence_refs": []})
        result = llm.chat(_messages("Extract a fact"), json_mode=True)
        parsed, _ = _parse_json(result.content)
        rejected = not (parsed or {}).get("supported_by_evidence")
        tr.note_parse(
            raw=result.content,
            parsed=parsed,
            validation={"ok": False, "rejected": rejected, "reason": "unsupported assertion"},
            error_class="TRUST_VALIDATION",
            status="error",
        )
        tr.complete(
            disposition={"accepted": False, "promoted_to_fact": False},
            status="error",
            error_class="TRUST_VALIDATION",
        )
    return {"ok": True, "scenario": "T7", "trace_id": tr.trace_id, "error_class": "TRUST_VALIDATION"}


def _t8() -> dict[str, Any]:
    llm = trace_llm(_ScriptedChat(['{"step":"plan"}', '{"step":"narrative"}']))
    with tracing_harness("T8") as tr:
        tr.set_assembled({"task": "multi_call"})
        tr.note_planner({"steps": ["plan", "narrative"]})
        llm.chat(_messages("plan"), json_mode=True)
        llm.chat(_messages("narrative"), json_mode=True)
        tr.complete(disposition={"calls": 2, "answer_kind": "harness_multi"})
    return {"ok": True, "scenario": "T8", "trace_id": tr.trace_id, "error_class": None}


def _t9() -> dict[str, Any]:
    old_id = str(uuid4())
    keep_id = str(uuid4())
    store.insert_trace(
        trace_id=old_id,
        request_kind="harness",
        originating_ask="T9 aged",
        purpose="T9",
    )
    store.insert_trace(
        trace_id=keep_id,
        request_kind="harness",
        originating_ask="T9 recent",
        purpose="T9",
    )
    try:
        from memorybox.db import connection

        aged = datetime.now(timezone.utc) - timedelta(days=30)
        with connection() as conn:
            conn.execute(
                "UPDATE ai_traces SET created_at = %s, updated_at = %s WHERE trace_id = %s",
                (aged, aged, old_id),
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "scenario": "T9", "error": str(exc)}
    cleaned = store.cleanup()
    still_old = store.get_trace(old_id)
    still_new = store.get_trace(keep_id)
    return {
        "ok": still_old is None and still_new is not None,
        "scenario": "T9",
        "deleted_old": still_old is None,
        "kept_recent": still_new is not None,
        "cleanup": cleaned,
        "old_id": old_id,
        "keep_id": keep_id,
    }


def _t10() -> dict[str, Any]:
    llm = trace_llm(FakeLlmProvider())
    secret_payload = {
        "Authorization": "Bearer super-secret-token-value",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
        "messages": [{"role": "user", "content": "hello"}],
        "host": "http://user:hunter2@127.0.0.1:11434",
    }
    with tracing_harness("T10") as tr:
        tr.set_assembled({"task": "secret_scrub"})
        store.insert_span(
            trace_id=tr.trace_id,
            stage="prompt_build",
            component="harness",
            operation="prompt_build",
            assembled_context={"note": "auth present on provider request config"},
            provider_payload=secret_payload,
            meta={"authorization": "Bearer should-not-land"},
        )
        llm.chat(_messages("ping"))
        tr.complete(disposition={"accepted": True, "secrets_should_be_absent": True})
    saved = store.get_trace(tr.trace_id) or {}
    blob = json.dumps(saved, default=str)
    leaked = any(
        token in blob
        for token in (
            "super-secret-token-value",
            "sk-abcdefghijklmnopqrstuvwxyz",
            "hunter2",
            "Bearer should-not-land",
        )
    )
    return {
        "ok": not leaked,
        "scenario": "T10",
        "trace_id": tr.trace_id,
        "leaked": leaked,
    }


def run_all() -> dict[str, Any]:
    results = {name: run_scenario(name) for name in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10")}
    return {"ok": all(bool(v.get("ok")) for v in results.values()), "scenarios": results}
