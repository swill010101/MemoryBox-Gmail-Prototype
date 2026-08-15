"""Single MBQL compile entry — Ask, Explore, later STT."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from memorybox.context import AskContext
from memorybox.mbql.residual import needs_residual, try_residual_fill
from memorybox.mbql.verbs import match_command, navigate_target
from memorybox.planner import QueryPlan, plan_ask


def _empty_ctx() -> AskContext:
    return AskContext(session_id="mbql")


def _command_plan(text: str, spec: Any) -> QueryPlan:
    q = (text or "").strip()
    visual = spec.visual_scope or "none"
    want_still = visual in ("still_only", "broad")
    want_video = visual in ("video_only", "broad")
    want_comms = spec.verb in ("add_texts", "only_texts")
    target = navigate_target(q, spec)
    return QueryPlan(
        original_ask=q,
        effective_ask="mbql:" + spec.verb + (f":{target}" if target else ""),
        is_followup=spec.act == "refine",
        want_photo=want_still,
        want_communication=want_comms,
        want_calendar=False,
        visual_scope=visual if visual != "none" else "none",
        want_visual=want_still or want_video,
        want_still=want_still,
        want_video=want_video,
        act=spec.act,
        compile_provenance="deterministic",
        refine_verb=spec.verb if spec.act == "refine" else None,
        navigate_target=target,
        gallery_show_sms=spec.gallery_show_sms,
        notes=("mbql_command", spec.verb),
    )


def compile_ask(
    text: str,
    ctx: AskContext | None = None,
    *,
    llm: Any | None = None,
    allow_model: bool = True,
) -> QueryPlan:
    """Deterministic first. Residual model fill only when needed. Fail back (Q4)."""
    q = (text or "").strip()
    spec = match_command(q)
    if spec:
        return _command_plan(q, spec)

    plan = plan_ask(q, ctx or _empty_ctx())
    if plan.act not in ("find", "refine", "navigate", "clarify"):
        plan = replace(plan, act="clarify" if plan.requires_clarification else "find")
    if plan.compile_provenance != "deterministic":
        plan = replace(plan, compile_provenance="deterministic")

    if allow_model and llm is not None and needs_residual(plan, q):
        try:
            filled = try_residual_fill(plan, q, llm)
        except Exception:  # noqa: BLE001
            filled = None
        if filled is not None:
            return filled
    return plan
