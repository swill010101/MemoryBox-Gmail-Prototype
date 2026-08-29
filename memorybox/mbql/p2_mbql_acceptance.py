"""P2-MBQL-001 acceptance — structural + phrase compile.

Increment ACCEPTED 2026-08-18 (Tom). This harness remains structural assist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.mbql import VERB_IDS, compile_ask
from memorybox.mbql.residual import needs_residual
from memorybox.providers.llm.dto import ChatMessage, ChatResultDto


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


class _FillPeggy:
    provider_key = "stub_mbql"

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        return ChatResultDto(
            model="stub-mbql",
            content='{"person_names":["Peggy George"],"clarify":false}',
        )


class _BoomLlm:
    provider_key = "boom"

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        raise RuntimeError("forced residual model down")


class _OkOnlyLlm:
    provider_key = "ok_only"

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        return ChatResultDto(model="stub-ok", content='{"ok":true}')


class _ExtraSlotsLlm:
    provider_key = "extra"

    def chat(self, messages: list[ChatMessage], *, json_mode: bool = False) -> ChatResultDto:
        return ChatResultDto(
            model="stub-extra",
            content=(
                '{"person_names":["Peggy George","Tom Will"],'
                '"time_start":"2015-01-01","time_end":"2015-12-31"}'
            ),
        )


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = _root()
    app_py = (root / "app.py").read_text(encoding="utf-8")
    shell_js = (root / "shell" / "static" / "shell.js").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    planner = (root / "planner" / "__init__.py").read_text(encoding="utf-8")
    compile_py = (root / "mbql" / "compile.py").read_text(encoding="utf-8")
    verbs_py = (root / "mbql" / "verbs.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")

    _check(
        "queryplan_extended",
        "act:" in planner
        and "compile_provenance" in planner
        and "refine_verb" in planner
        and "gallery_show_sms" in planner,
        checks,
        problems,
        "QueryPlan carries MBQL act/provenance (no second dataclass)",
    )
    _check(
        "one_compile_entry",
        "def compile_ask" in compile_py and "compile_ask" in orch,
        checks,
        problems,
        "Ask orchestrator uses compile_ask",
    )
    _check(
        "shared_verbs",
        all(v in explore_js for v in VERB_IDS) and "MBQL_VERBS" in explore_js,
        checks,
        problems,
        "Explore MBQL_VERBS matches server VERB_IDS",
    )
    _check(
        "new_find_resets_include_texts",
        "const includeTexts = galleryShowSms" in explore_js
        and "not leak SMS" in explore_js,
        checks,
        problems,
        "New find does not inherit includeTexts; Photos pill hides SMS",
    )
    _check(
        "compile_api",
        "/ask/api/compile" in app_py and "/ask/api/mbql-verbs" in app_py,
        checks,
        problems,
        "STT-ready compile HTTP API",
    )
    _check(
        "not_in_family_nav",
        "mbql" not in shell_js.lower() and "/dev/ai-trace" not in shell_js,
        checks,
        problems,
        "MBQL is not a family nav surface",
    )
    _check(
        "no_i9_product",
        "Do not build speech" in (root / "mbql" / "__init__.py").read_text(encoding="utf-8"),
        checks,
        problems,
        "I9 stays after I8.5 — contract only",
    )
    _check(
        "cli_prove",
        "prove-p2-mbql-001" in main or "prove-mbql-001" in main,
        checks,
        problems,
        "prove-mbql-001 CLI",
    )
    _check(
        "residual_q1",
        "needs_residual" in (root / "mbql" / "residual.py").read_text(encoding="utf-8")
        and "try_residual_fill" in verbs_py + (root / "mbql" / "residual.py").read_text(encoding="utf-8"),
        checks,
        problems,
        "Residual fill is a separate path",
    )
    _check(
        "q4_fail_back_in_orchestrator",
        "compile_ask" in orch and "plan_ask" in orch and "Q4" in orch,
        checks,
        problems,
        "Ask fails back to plan_ask if compile_ask raises",
    )


def _phrases(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.context import AskContext

    ctx = AskContext(session_id="prove-mbql")

    p1 = compile_ask("show me text messages from Peggy George", ctx, llm=_BoomLlm())
    _check(
        "phrase_peggy_texts",
        p1.act == "find"
        and p1.compile_provenance == "deterministic"
        and p1.want_communication
        and any("peggy" in n.lower() for n in p1.person_names),
        checks,
        problems,
        f"act={p1.act} prov={p1.compile_provenance} people={p1.person_names} comm={p1.want_communication}",
    )
    _check(
        "phrase_peggy_texts_zero_model",
        not needs_residual(p1, "show me text messages from Peggy George"),
        checks,
        problems,
        "Complete SMS+person compile must not call the model",
    )

    p2 = compile_ask("Show me Peggy", ctx, llm=None)
    _check(
        "phrase_show_peggy",
        p2.act == "find"
        and p2.compile_provenance == "deterministic"
        and any("peggy" in n.lower() for n in p2.person_names),
        checks,
        problems,
        f"act={p2.act} people={p2.person_names}",
    )

    ctx_alias = AskContext(session_id="prove-mbql-alias", person_names=("Peggy",))
    p_alias = compile_ask("Show me Peggy George", ctx_alias, llm=None)
    alias_names = [n.lower() for n in p_alias.person_names]
    _check(
        "phrase_no_second_peggy_alias",
        p_alias.act == "find"
        and any("peggy george" in n for n in alias_names)
        and "peggy" not in alias_names,
        checks,
        problems,
        f"people={p_alias.person_names}",
    )
    ctx_upgrade = AskContext(session_id="prove-mbql-up", person_names=("Peggy George",))
    p_up = compile_ask("Show me Peggy", ctx_upgrade, llm=None)
    _check(
        "phrase_upgrade_peggy_to_full",
        p_up.person_names == ("Peggy George",),
        checks,
        problems,
        f"people={p_up.person_names}",
    )

    p3 = compile_ask("Show me Peggy Christmas", ctx, llm=None)
    ev = " ".join(p3.event_labels).lower()
    _check(
        "phrase_peggy_christmas",
        p3.act == "find"
        and "christmas" in ev
        and any("peggy" in n.lower() for n in p3.person_names)
        and (
            "holiday_all_years" in " ".join(p3.notes)
            or len(p3.temporal_windows) > 1
        ),
        checks,
        problems,
        f"events={p3.event_labels} people={p3.person_names} windows={p3.temporal_windows}",
    )

    p4 = compile_ask("Only photos.", ctx, llm=_BoomLlm())
    _check(
        "phrase_only_photos",
        p4.act == "refine" and p4.refine_verb == "only_photos" and p4.compile_provenance == "deterministic",
        checks,
        problems,
        f"act={p4.act} verb={p4.refine_verb}",
    )

    p5 = compile_ask("Add texts.", ctx, llm=None)
    _check(
        "phrase_add_texts",
        p5.act == "refine" and p5.refine_verb == "add_texts" and p5.gallery_show_sms is True,
        checks,
        problems,
        f"act={p5.act} verb={p5.refine_verb} sms={p5.gallery_show_sms}",
    )

    p6 = compile_ask("Clear filters.", ctx, llm=None)
    _check(
        "phrase_clear_filters",
        p6.act == "refine" and p6.refine_verb == "clear_filters",
        checks,
        problems,
        f"act={p6.act} verb={p6.refine_verb}",
    )

    p7 = compile_ask("Go to Tom instead.", ctx, llm=None)
    _check(
        "phrase_go_to_tom",
        p7.act == "navigate"
        and p7.refine_verb is None
        and (p7.navigate_target or "").lower().startswith("tom"),
        checks,
        problems,
        f"act={p7.act} target={p7.navigate_target}",
    )


def _residual(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.context import AskContext

    ctx = AskContext(session_id="prove-mbql-res")
    q = "what did she say"
    base = compile_ask(q, ctx, llm=None, allow_model=False)
    _check(
        "residual_detected",
        needs_residual(base, q) and not any(
            n.lower() not in {"she", "he", "they", "her", "him"} for n in base.person_names
        ),
        checks,
        problems,
        f"needs={needs_residual(base, q)} people={base.person_names}",
    )

    filled = compile_ask(q, ctx, llm=_FillPeggy())
    _check(
        "residual_fill_person",
        filled.compile_provenance in ("model_fill", "mixed")
        and any("peggy" in n.lower() for n in filled.person_names)
        and filled.act == "find",
        checks,
        problems,
        f"prov={filled.compile_provenance} people={filled.person_names} act={filled.act}",
    )

    fallback = compile_ask(q, ctx, llm=_BoomLlm())
    _check(
        "residual_fail_back",
        fallback.compile_provenance == "deterministic" and fallback.original_ask.lower().startswith("what did she"),
        checks,
        problems,
        f"prov={fallback.compile_provenance} act={fallback.act}",
    )

    ok_only = compile_ask(q, ctx, llm=_OkOnlyLlm())
    _check(
        "residual_ok_true_fail_back",
        ok_only.compile_provenance == "deterministic" and not any("peggy" in n.lower() for n in ok_only.person_names),
        checks,
        problems,
        f"prov={ok_only.compile_provenance} people={ok_only.person_names}",
    )

    extra = compile_ask(q, ctx, llm=_ExtraSlotsLlm())
    _check(
        "residual_extra_slots_ignored",
        any("peggy" in n.lower() for n in extra.person_names)
        and not any("tom" in n.lower() for n in extra.person_names)
        and extra.time_start is None,
        checks,
        problems,
        f"people={extra.person_names} time={extra.time_start}",
    )


def _http(checks: dict[str, Any], problems: list[str]) -> None:
    from fastapi.testclient import TestClient

    from memorybox.app import app

    client = TestClient(app)
    r = client.post("/ask/api/compile", json={"ask": "Only photos."})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    plan = (body or {}).get("plan") or {}
    _check(
        "http_compile_only_photos",
        r.status_code == 200 and plan.get("act") == "refine" and plan.get("refine_verb") == "only_photos",
        checks,
        problems,
        f"status={r.status_code} act={plan.get('act')} verb={plan.get('refine_verb')}",
    )
    v = client.get("/ask/api/mbql-verbs")
    verbs = (v.json() or {}).get("verbs") or []
    _check(
        "http_verbs",
        v.status_code == 200 and "only_photos" in verbs and "go_to_person" in verbs,
        checks,
        problems,
        f"status={v.status_code} n={len(verbs)}",
    )


def prove_p2_mbql_001(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    _structural(checks, problems)
    _phrases(checks, problems)
    _residual(checks, problems)
    _http(checks, problems)
    overall = not problems
    return {
        "ok": overall,
        "overall_ok": overall,
        "increment": "MBQL-001",
        "flightsim": bool(flightsim),
        "note": (
            "MBQL-001 ACCEPTED 2026-08-18 (Tom: 'MBQL is accepted'). "
            "This harness is structural assist. Q1 residual; I9 not in this increment."
        ),
        "checks": checks,
        "problems": problems,
    }
