"""Thin Experience Orchestrator — Evidence First Ask (Increment 4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memorybox.ask import retrieve as R
from memorybox.ask.deps import build_llm, build_photo, provider_snapshot
from memorybox.context import (
    AskContext,
    ContextPatch,
    ContextStore,
    apply_patch,
    default_context_store,
)
from memorybox.planner import QueryPlan, plan_ask
from memorybox.providers.llm.protocol import LlmProvider
from memorybox.providers.photo.protocol import PhotoProvider


@dataclass
class AskResult:
    session_id: str
    ask: str
    plan: dict[str, Any]
    context: dict[str, Any]
    answer_kind: str
    answer_text: str
    statements: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    evidence_hits: list[dict[str, Any]]
    photo_hits: list[dict[str, Any]]
    missing_disclosure: str | None
    provider_status: dict[str, Any]
    inventing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "ask": self.ask,
            "plan": self.plan,
            "context": self.context,
            "answer_kind": self.answer_kind,
            "answer_text": self.answer_text,
            "statements": self.statements,
            "citations": self.citations,
            "evidence_hits": self.evidence_hits,
            "photo_hits": self.photo_hits,
            "missing_disclosure": self.missing_disclosure,
            "provider_status": self.provider_status,
            "inventing": self.inventing,
        }


def _update_context_from_plan(
    ctx: AskContext, plan: QueryPlan, evidence_ids: list[str], photo_ids: list[str]
) -> AskContext:
    """Rule H: persisted context mirrors effective plan slots (not stale merge)."""
    selection = tuple(evidence_ids[:12] + photo_ids[:12])
    patch = ContextPatch(
        person_names=plan.person_names,
        place_names=plan.place_names,
        event_labels=plan.event_labels,
        result_selection=selection,
        modalities_active=plan.modalities,
        last_ask=plan.original_ask,
        time_start=plan.time_start,
        time_end=plan.time_end,
    )
    return apply_patch(ctx, patch)


def _build_answer(
    plan: QueryPlan,
    evidence: list[R.EvidenceHit],
    photos: list[R.PhotoHit],
    photo_status: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    citations: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []

    if plan.requires_clarification:
        msg = plan.ambiguity_message or (
            "Ambiguous ask: please clarify before MemoryBox retrieves Evidence."
        )
        return "clarification", msg, [], [], msg

    for h in evidence:
        citations.append(
            {
                "kind": "evidence",
                "evidence_id": h.evidence_id,
                "evidence_kind": h.evidence_kind,
                "summary": h.summary,
                "source": h.source,
            }
        )
        statements.append(
            {
                "text": h.summary or h.excerpt[:160],
                "label": "Fact",
                "evidence_ids": [h.evidence_id],
                "photo_external_ids": [],
            }
        )

    for p in photos:
        citations.append(
            {
                "kind": "photo",
                "provider_key": p.provider_key,
                "external_id": p.external_id,
                "taken_at": p.taken_at,
                "people": p.people,
                "location": p.location,
                "thumb_url": p.thumb_url,
                "web_url": p.web_url,
            }
        )
        who = ", ".join(p.people) if p.people else "people not labeled"
        where = p.location or "location not labeled"
        statements.append(
            {
                "text": f"Photo asset from provider ({who}; {where}).",
                "label": "Fact",
                "evidence_ids": [],
                "photo_external_ids": [p.external_id],
            }
        )

    photo_unavail = bool(
        (plan.want_still or plan.want_photo) and photo_status.get("unavailable")
    )
    video_only_no_provider = bool(
        plan.want_video and not plan.want_still and plan.visual_scope == "video_only"
    )

    if video_only_no_provider:
        missing = (
            "Video modality is not available in this Increment 4 runtime "
            "(no video/HVRT provider wired). MemoryBox will not invent video results."
        )
        return "insufficient", missing, statements, citations, missing

    if photo_unavail and not evidence:
        text = (
            "Photo/still provider is unavailable, so MemoryBox cannot search the "
            "visual library right now. This is not the same as finding no photos. "
            "No other Evidence modalities returned hits for this ask."
        )
        return "provider_unavailable", text, statements, citations, None

    if photo_unavail and evidence:
        text = (
            "Photo provider is unavailable (not 'no photos'). "
            f"Found {len(evidence)} Evidence hit(s) from email/calendar. "
            "Family-history claims below are limited to cited Evidence."
        )
        return "mixed", text, statements, citations, None

    if plan.want_photo and not photos and not evidence and photo_status.get("ok"):
        missing = (
            "Insufficient Evidence: no matching photos or email/calendar Evidence "
            "were found for this ask. MemoryBox will not invent a family fact."
        )
        return "insufficient", missing, statements, citations, missing

    if not evidence and not photos:
        missing = (
            "Insufficient Evidence for this ask. Available archive Evidence does not "
            "support a factual family-history answer. MemoryBox will not invent one."
        )
        return "insufficient", missing, statements, citations, missing

    parts = []
    if photos:
        parts.append(f"Found {len(photos)} photo hit(s) via the photo provider.")
    if evidence:
        parts.append(f"Found {len(evidence)} Evidence hit(s) (email/calendar).")
    if plan.retrieval_constraints:
        parts.append(
            "Retrieval used context constraints: "
            + ", ".join(plan.retrieval_constraints)
            + "."
        )
    parts.append("Factual claims are limited to the citations listed.")
    if photos and evidence:
        kind = "mixed"
    elif photos and not evidence:
        kind = "photo_backed"
    else:
        kind = "evidence_backed"
    return kind, " ".join(parts), statements, citations, None


class AskOrchestrator:
    def __init__(
        self,
        *,
        store: ContextStore | None = None,
        photo: PhotoProvider | None = None,
        llm: LlmProvider | None = None,
    ) -> None:
        self.store = store or default_context_store
        self.photo = photo if photo is not None else build_photo()
        self.llm = llm if llm is not None else build_llm()

    def ask(self, text: str, *, session_id: str | None = None) -> AskResult:
        ctx = self.store.get_or_create(session_id)
        plan = plan_ask(text, ctx)

        evidence: list[R.EvidenceHit] = []
        qdrant_status: dict[str, Any] = {"ok": False, "detail": "skipped"}
        photos: list[R.PhotoHit] = []
        photo_status: dict[str, Any] = {"ok": True, "detail": "not_requested"}

        if not plan.requires_clarification:
            if plan.want_communication or plan.want_calendar:
                pg_hits = R.search_evidence_pg(plan)
                qd_hits, qdrant_status = R.search_evidence_qdrant(plan)
                evidence = R.merge_evidence_hits(pg_hits, qd_hits)
                # Rule G: when constraints exist, drop hits that match none
                if plan.retrieval_constraints:
                    evidence = R.filter_hits_by_constraints(
                        evidence, plan.retrieval_constraints
                    )
            if plan.want_still or plan.want_photo:
                photos, photo_status = R.search_photos(plan, self.photo)

            if plan.want_video and plan.visual_scope in ("broad", "video_only"):
                photo_status = dict(photo_status)
                photo_status.setdefault(
                    "video_modality",
                    {
                        "requested": True,
                        "available_in_i4": False,
                        "detail": "video/HVRT not wired in Increment 4",
                    },
                )

        answer_kind, answer_text, statements, citations, missing = _build_answer(
            plan, evidence, photos, photo_status
        )

        new_ctx = _update_context_from_plan(
            ctx,
            plan,
            [h.evidence_id for h in evidence],
            [p.external_id for p in photos],
        )
        new_ctx = self.store.save(new_ctx)

        # Rule H: expose effective retrieval context on the response context dict
        ctx_dict = new_ctx.to_dict()
        ctx_dict["effective_retrieval_constraints"] = list(plan.retrieval_constraints)
        ctx_dict["plan_slots"] = {
            "person": list(plan.person_names),
            "place": list(plan.place_names),
            "trip": list(plan.trip_labels),
            "event": [e for e in plan.event_labels if not e.lower().startswith("trip:")],
            "modality": list(plan.modalities),
        }

        providers = provider_snapshot(self.photo, self.llm)
        providers["qdrant"] = qdrant_status
        providers["photo_search"] = photo_status

        return AskResult(
            session_id=new_ctx.session_id,
            ask=text,
            plan=plan.to_dict(),
            context=ctx_dict,
            answer_kind=answer_kind,
            answer_text=answer_text,
            statements=statements,
            citations=citations,
            evidence_hits=[h.to_dict() for h in evidence],
            photo_hits=[p.to_dict() for p in photos],
            missing_disclosure=missing,
            provider_status=providers,
            inventing=False,
        )

    def get_context(self, session_id: str) -> AskContext:
        return self.store.get_or_create(session_id)

    def clear_context(self, session_id: str) -> AskContext:
        return self.store.clear(session_id)

    def change_context(self, session_id: str, patch: ContextPatch) -> AskContext:
        return self.store.patch(session_id, patch)
