"""P2-I7A AI Model Trace — structural + T1–T10 harness. Increment ACCEPTED 2026-08-15."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memorybox.explore.p2_i4_acceptance import _check


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = _root()
    app_py = (root / "app.py").read_text(encoding="utf-8")
    shell_js = (root / "shell" / "static" / "shell.js").read_text(encoding="utf-8")
    wrapper = (root / "ai_trace" / "wrapper.py").read_text(encoding="utf-8")
    store = (root / "ai_trace" / "store.py").read_text(encoding="utf-8")
    html = (root / "ai_trace" / "static" / "ai-trace.html").read_text(encoding="utf-8")
    js = (root / "ai_trace" / "static" / "ai-trace.js").read_text(encoding="utf-8")
    ui = html + js
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    deps = (root / "ask" / "deps.py").read_text(encoding="utf-8")
    rebuild = (root / "ingest" / "rebuild_index.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")
    mig = (root / "migrations" / "009_p2_i7a_ai_trace.sql").read_text(encoding="utf-8")
    mig10 = (root / "migrations" / "010_p2_i7a_ai_trace_ensure.sql").read_text(encoding="utf-8")

    _check(
        "route_dev_ai_trace",
        '@app.get("/dev/ai-trace")' in app_py and "/dev/api/ai-trace" in app_py,
        checks,
        problems,
        "Canonical /dev/ai-trace + JSON API",
    )
    _check(
        "not_in_family_nav",
        "ai-trace" not in shell_js and "/dev/ai-trace" not in shell_js,
        checks,
        problems,
        "Must not appear in family primary or system nav",
    )
    _check(
        "no_shell_inject_on_dev_page",
        "No shell inject" in app_py or "no shell inject" in app_py.lower(),
        checks,
        problems,
        "Standalone developer page",
    )
    _check(
        "provider_neutral_wrap",
        "class TracedLlmProvider" in wrapper
        and "def chat(" in wrapper
        and "def embed(" in wrapper
        and "trace_llm" in deps
        and "trace_llm" in rebuild,
        checks,
        problems,
        "Shared chat+embed wrap, not Ollama-only",
    )
    _check(
        "no_vector_by_default",
        "vector_persisted" in wrapper and "len(result.vector)" in wrapper,
        checks,
        problems,
        "Embeddings store dimensions, not the vector",
    )
    _check(
        "redact_before_write",
        "_json(value: Any)" in store and "redact(value)" in store,
        checks,
        problems,
        "Redaction on persist path",
    )
    _check(
        "fail_open_store",
        "never fail" in (root / "ai_trace" / "store.py").read_text(encoding="utf-8").lower()
        or "Fail-open" in store,
        checks,
        problems,
        "Store errors are swallowed",
    )
    _check(
        "ask_always_traced",
        "tracing_ask" in orch and "note_planner" in orch,
        checks,
        problems,
        "Deterministic Ask still emits end-to-end trace",
    )
    _check(
        "polling_not_sse",
        "750" in js and "EventSource" not in js and "WebSocket" not in js,
        checks,
        problems,
        "P2 live update is HTTP poll",
    )
    _check(
        "ui_distinguishes_context_vs_payload",
        "Assembled MemoryBox context" in ui and "Exact provider payload" in ui,
        checks,
        problems,
        "UI panes split assembled context from payload",
    )
    _check(
        "retention_defaults",
        "500" in mig
        and "7" in mig
        and "ai_trace_max_traces" in mig
        and "CREATE TABLE IF NOT EXISTS ai_traces" in mig10,
        checks,
        problems,
        "500 traces or 7 days",
    )
    _check(
        "cli_prove",
        "prove-p2-i7a" in main,
        checks,
        problems,
        "prove-p2-i7a CLI",
    )
    _check(
        "no_mbql",
        "mbql" not in (root / "ai_trace").name.lower()
        and "class Mbql" not in app_py
        and "MBQL" not in wrapper,
        checks,
        problems,
        "No MBQL implementation in I7A",
    )
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    _check(
        "explore_js_parses",
        "<ul>${atts}" not in explore_js
        and "mbExploreApplyAsk" in explore_js
        and "sms-attachment" in explore_js,
        checks,
        problems,
        "Nested backticks in SMS attach HTML must not kill the whole Explore script",
    )
    _check(
        "explore_chrome_before_find",
        "Bind Ask chrome before any find" in explore_js
        and "chromeBound" in explore_js
        and "hydrateExploreHistory" in explore_js,
        checks,
        problems,
        "Explore binds Enter/history before the first find returns",
    )
    _check(
        "empty_find_skips_orchestrator",
        "orch = None if not str(q" in app_py,
        checks,
        problems,
        "Empty Explore find must not construct AskOrchestrator",
    )


def _redact_checks(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ai_trace.redact import redact

    cleaned = redact(
        {
            "Authorization": "Bearer super-secret-token-value",
            "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
            "host": "http://user:hunter2@127.0.0.1:11434",
            "messages": [{"role": "user", "content": "hello"}],
        }
    )
    blob = json.dumps(cleaned)
    _check(
        "t10_redact_unit",
        "super-secret-token-value" not in blob
        and "sk-abcdefghijklmnopqrstuvwxyz" not in blob
        and "hunter2" not in blob
        and "[REDACTED]" in blob
        and "hello" in blob,
        checks,
        problems,
        blob[:200],
    )


def _fail_open(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ai_trace import store as ai_store
    from memorybox.ask.orchestrator import AskOrchestrator
    from memorybox.providers.llm.fake import FakeLlmProvider
    from memorybox.providers.photo.fake import FakePhotoProvider
    from memorybox.providers.video.fake import FakeVideoProvider

    orig = ai_store.connection

    def boom(*_a, **_k):
        raise RuntimeError("forced store down")

    ai_store.connection = boom  # type: ignore[assignment]
    try:
        orch = AskOrchestrator(
            llm=FakeLlmProvider(),
            photo=FakePhotoProvider(),
            video=FakeVideoProvider(),
        )
        result = orch.ask("How many text messages did I send?")
        _check(
            "store_down_does_not_fail_ask",
            bool(result.answer_kind) and bool(result.answer_text or result.plan),
            checks,
            problems,
            f"kind={result.answer_kind}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("store_down_does_not_fail_ask", False, checks, problems, str(exc))
    finally:
        ai_store.connection = orig  # type: ignore[assignment]


def _scenarios(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ai_trace import store as ai_store
    from memorybox.ai_trace.scenarios import run_scenario
    from memorybox.ai_trace.wrapper import trace_llm
    from memorybox.providers.llm.fake import FakeLlmProvider

    results = {}
    for name in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"):
        results[name] = run_scenario(name)
        _check(
            f"scenario_{name.lower()}_ran",
            bool(results[name].get("ok")),
            checks,
            problems,
            json.dumps(results[name], default=str)[:240],
        )

    t3 = results["T3"]
    t3_id = t3.get("trace_id")
    t3_row = ai_store.get_trace(t3_id) if t3_id else None
    model_ops = [
        s.get("operation")
        for s in (t3_row or {}).get("spans") or []
        if s.get("operation") in ("chat", "embed")
    ]
    stages = [s.get("stage") for s in (t3_row or {}).get("spans") or []]
    _check(
        "t3_zero_model_spans",
        t3_row is not None and model_ops == [],
        checks,
        problems,
        f"ops={model_ops} stages={stages}",
    )
    _check(
        "t3_end_to_end_stages",
        t3_row is not None
        and "initiation" in stages
        and "planner" in stages
        and "disposition" in stages
        and "final_result" in stages,
        checks,
        problems,
        f"stages={stages}",
    )

    t2 = ai_store.get_trace(results["T2"].get("trace_id") or "")
    t4 = ai_store.get_trace(results["T4"].get("trace_id") or "")
    _check(
        "t2_vs_t4_distinct_classes",
        (t2 or {}).get("error_class") == "ORCHESTRATION"
        and (t4 or {}).get("error_class") == "MODEL_OUTPUT",
        checks,
        problems,
        f"t2={ (t2 or {}).get('error_class') } t4={ (t4 or {}).get('error_class') }",
    )

    t8 = ai_store.get_trace(results["T8"].get("trace_id") or "")
    chats = [
        s
        for s in (t8 or {}).get("spans") or []
        if s.get("operation") == "chat"
    ]
    _check(
        "t8_multi_call_one_parent",
        len(chats) >= 2 and (t8 or {}).get("model_call_count", 0) >= 2,
        checks,
        problems,
        f"chats={len(chats)} count={(t8 or {}).get('model_call_count')}",
    )

    t5 = ai_store.get_trace(results["T5"].get("trace_id") or "")
    _check(
        "t5_provider_transport",
        (t5 or {}).get("error_class") == "PROVIDER_TRANSPORT",
        checks,
        problems,
        f"class={(t5 or {}).get('error_class')}",
    )

    t10 = ai_store.get_trace(results["T10"].get("trace_id") or "")
    blob = json.dumps(t10 or {}, default=str)
    _check(
        "t10_secrets_absent_from_store",
        t10 is not None
        and "super-secret-token-value" not in blob
        and "hunter2" not in blob,
        checks,
        problems,
        "persisted blob must not contain secrets",
    )

    from memorybox.ai_trace.request import tracing_harness

    llm = trace_llm(FakeLlmProvider())
    with tracing_harness("embed-meta") as tr:
        emb = llm.embed("peggy christmas", purpose="query")
        tr.complete(disposition={"dimensions": len(emb.vector)})
    erow = ai_store.get_trace(tr.trace_id) or {}
    raws = [s.get("raw_response") or {} for s in erow.get("spans") or [] if s.get("operation") == "embed"]
    persisted_vec = any(isinstance(r.get("vector"), (list, tuple)) for r in raws)
    _check(
        "embed_metadata_without_vector",
        raws
        and raws[0].get("vector_persisted") is False
        and raws[0].get("dimensions")
        and not persisted_vec,
        checks,
        problems,
        json.dumps(raws[:1], default=str),
    )


def _http(checks: dict[str, Any], problems: list[str]) -> None:
    try:
        from fastapi.testclient import TestClient

        from memorybox.app import app

        client = TestClient(app)
        page = client.get("/dev/ai-trace")
        _check(
            "http_dev_ai_trace",
            page.status_code == 200 and "AI Trace" in page.text and "Live Follow" in page.text,
            checks,
            problems,
            f"status={page.status_code}",
        )
        listing = client.get("/dev/api/ai-trace")
        _check(
            "http_list",
            listing.status_code == 200 and listing.json().get("ok") is True,
            checks,
            problems,
            f"status={listing.status_code}",
        )
        ask_page = client.get("/ask/ui")
        _check(
            "ask_nav_unchanged",
            ask_page.status_code == 200 and "/dev/ai-trace" not in ask_page.text,
            checks,
            problems,
            "Ask page must not promote AI Trace into family chrome",
        )
    except Exception as exc:  # noqa: BLE001
        _check("http_dev_ai_trace", False, checks, problems, str(exc))


def prove_p2_i7a(*, flightsim: bool = False) -> dict[str, Any]:
    from memorybox import migrate as migrate_mod

    checks: dict[str, Any] = {}
    problems: list[str] = []
    from memorybox.ai_trace import store as ai_store

    try:
        applied = migrate_mod.migrate()
        ensured = ai_store.ensure_schema()
        have_tables = ai_store.tables_exist()
    except Exception as exc:  # noqa: BLE001
        applied = []
        ensured = False
        have_tables = False
        _check("migrate", False, checks, problems, str(exc))
    else:
        _check(
            "migrate",
            bool(have_tables and ensured),
            checks,
            problems,
            f"applied={applied} tables={have_tables}",
        )

    _structural(checks, problems)
    _redact_checks(checks, problems)
    _fail_open(checks, problems)
    _scenarios(checks, problems)
    _http(checks, problems)

    overall = not problems
    return {
        "ok": overall,
        "overall_ok": overall,
        "increment": "P2-I7A",
        "flightsim": bool(flightsim),
        "note": (
            "P2-I7A ACCEPTED 2026-08-15 (Tom FlightSim owner pass). "
            "prove-p2-i7a remains a regression harness."
        ),
        "checks": checks,
        "problems": problems,
    }
