"""Thin Experience Orchestrator — Evidence First Ask + Story (I5) + Journal (I5A)."""
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
    story_hits: list[dict[str, Any]]
    journal_hits: list[dict[str, Any]]
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
            "story_hits": self.story_hits,
            "journal_hits": self.journal_hits,
            "missing_disclosure": self.missing_disclosure,
            "provider_status": self.provider_status,
            "inventing": self.inventing,
        }


def _update_context_from_plan(
    ctx: AskContext,
    plan: QueryPlan,
    evidence_ids: list[str],
    photo_ids: list[str],
    story_ids: list[str],
    journal_ids: list[str],
) -> AskContext:
    """Rule H: persisted context mirrors effective plan slots (not stale merge)."""
    selection = tuple(
        evidence_ids[:8] + photo_ids[:8] + story_ids[:8] + journal_ids[:8]
    )
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
    stories: list[R.StoryHit],
    journals: list[R.JournalHit],
    photo_status: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    citations: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []

    if getattr(plan, "journal_capture_intent", False):
        msg = (
            "Journal capture is ready. Open /journal/ui to type or speak, review any "
            "transcript draft, then explicitly Save. MemoryBox will not invent a Journal entry."
        )
        return "journal_capture", msg, [], [], None

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
                "provenance_kind": "archive_evidence",
            }
        )
        statements.append(
            {
                "text": h.summary or h.excerpt[:160],
                "label": "Fact",
                "evidence_ids": [h.evidence_id],
                "photo_external_ids": [],
                "story_ids": [],
                "journal_ids": [],
                "provenance_kind": "archive_evidence",
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
                "identity_trust": getattr(p, "identity_trust", "confirmed"),
                "mb_person_id": getattr(p, "mb_person_id", None),
                "mb_person_name": getattr(p, "mb_person_name", None),
                "attribution": getattr(p, "attribution", None),
                "provenance_kind": (
                    "archive_evidence"
                    if getattr(p, "identity_trust", "confirmed") == "confirmed"
                    else "provider_candidate"
                ),
            }
        )
        who = ", ".join(p.people) if p.people else "people not labeled"
        where = p.location or "location not labeled"
        trust = getattr(p, "identity_trust", "confirmed")
        label = "Fact" if trust == "confirmed" else "Candidate"
        prefix = ""
        if trust == "candidate":
            prefix = "Unconfirmed Immich name candidate — "
        statements.append(
            {
                "text": f"{prefix}Photo asset from provider ({who}; {where}).",
                "label": label,
                "evidence_ids": [],
                "photo_external_ids": [p.external_id],
                "story_ids": [],
                "journal_ids": [],
                "provenance_kind": (
                    "archive_evidence" if trust == "confirmed" else "provider_candidate"
                ),
                "attribution": getattr(p, "attribution", None),
            }
        )

    for s in stories:
        citations.append(
            {
                "kind": "story",
                "story_id": s.story_id,
                "version": s.version,
                "title": s.title,
                "narrator_person_id": s.narrator_person_id,
                "narrator_display_name": s.narrator_display_name,
                "provenance_kind": s.provenance_kind,
                "attribution": s.attribution,
            }
        )
        statements.append(
            {
                "text": f"{s.attribution}: {s.excerpt}",
                "label": "Recollection",
                "evidence_ids": [],
                "photo_external_ids": [],
                "story_ids": [s.story_id],
                "journal_ids": [],
                "provenance_kind": s.provenance_kind,
                "attribution": s.attribution,
            }
        )

    for j in journals:
        citations.append(
            {
                "kind": "journal",
                "journal_id": j.journal_id,
                "version": j.version,
                "title": j.title,
                "author_person_id": j.author_person_id,
                "author_display_name": j.author_display_name,
                "captured_at": j.captured_at,
                "described_start_date": j.described_start_date,
                "described_end_date": j.described_end_date,
                "described_precision": j.described_precision,
                "provenance_kind": j.provenance_kind,
                "attribution": j.attribution,
            }
        )
        statements.append(
            {
                "text": f"{j.attribution}: {j.excerpt}",
                "label": "Journal",
                "evidence_ids": [],
                "photo_external_ids": [],
                "story_ids": [],
                "journal_ids": [j.journal_id],
                "provenance_kind": j.provenance_kind,
                "attribution": j.attribution,
            }
        )

    photo_unavail = bool(
        (plan.want_still or plan.want_photo) and photo_status.get("unavailable")
    )
    video_only_no_provider = bool(
        plan.want_video and not plan.want_still and plan.visual_scope == "video_only"
    )

    if video_only_no_provider and not evidence and not stories and not journals:
        missing = (
            "Video modality is not available in this Increment 4 runtime "
            "(no video/HVRT provider wired). MemoryBox will not invent video results."
        )
        return "insufficient", missing, statements, citations, missing

    if photo_unavail and not evidence and not stories and not journals:
        text = (
            "Photo/still provider is unavailable, so MemoryBox cannot search the "
            "visual library right now. This is not the same as finding no photos. "
            "No other Evidence modalities returned hits for this ask."
        )
        return "provider_unavailable", text, statements, citations, None

    if photo_unavail and (evidence or stories or journals):
        text = (
            "Photo provider is unavailable (not 'no photos'). "
            f"Found {len(evidence)} Evidence, {len(stories)} Story, "
            f"{len(journals)} Journal hit(s). "
            "Family-history claims below are limited to cited items with provenance."
        )
        return "mixed", text, statements, citations, None

    if (
        (plan.want_photo or plan.want_still or getattr(plan, "want_story", False)
         or getattr(plan, "want_journal", False))
        and not photos
        and not evidence
        and not stories
        and not journals
        and photo_status.get("ok", True)
    ):
        missing = (
            "Insufficient Evidence: no matching photos, Stories, Journals, or "
            "email/calendar Evidence were found for this ask. MemoryBox will not invent a family fact."
        )
        return "insufficient", missing, statements, citations, missing

    if not evidence and not photos and not stories and not journals:
        missing = (
            "Insufficient Evidence for this ask. Available archive Evidence does not "
            "support a factual family-history answer. MemoryBox will not invent one."
        )
        return "insufficient", missing, statements, citations, missing

    parts = []
    if journals:
        parts.append(
            f"Found {len(journals)} owner Journal entr(y/ies) "
            "(provenance: owner journal — distinct from Story recollection)."
        )
    if stories:
        parts.append(
            f"Found {len(stories)} owner Story recollection(s) "
            "(provenance: narrator testimony — not independently corroborated unless also cited)."
        )
    if photos:
        confirmed_n = sum(
            1 for p in photos if getattr(p, "identity_trust", "confirmed") == "confirmed"
        )
        candidate_n = len(photos) - confirmed_n
        if confirmed_n and not candidate_n:
            parts.append(
                f"Found {confirmed_n} photo hit(s) via confirmed MB Person→Immich mapping."
            )
        elif candidate_n and not confirmed_n:
            parts.append(
                f"Found {candidate_n} unconfirmed Immich name-candidate photo hit(s) "
                "(not MB-confirmed identity)."
            )
        else:
            parts.append(
                f"Found {confirmed_n} confirmed-mapping photo hit(s) and "
                f"{candidate_n} unconfirmed candidate hit(s)."
            )
        if photo_status.get("disclosure"):
            parts.append(str(photo_status["disclosure"]))
    if evidence:
        parts.append(f"Found {len(evidence)} Evidence hit(s) (email/calendar).")
    if plan.retrieval_constraints:
        parts.append(
            "Retrieval used context constraints: "
            + ", ".join(plan.retrieval_constraints)
            + "."
        )
    parts.append("Factual claims are limited to the citations listed.")
    modalities_hit = sum(
        1 for x in (bool(journals), bool(stories), bool(photos), bool(evidence)) if x
    )
    if modalities_hit > 1:
        kind = "mixed"
    elif journals:
        kind = "journal_backed"
    elif stories:
        kind = "story_backed"
    elif photos and not evidence:
        kind = "photo_backed"
    elif photos and evidence:
        kind = "mixed"
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
        stories: list[R.StoryHit] = []
        journals: list[R.JournalHit] = []

        if not plan.requires_clarification and not plan.journal_capture_intent:
            if plan.want_communication or plan.want_calendar:
                pg_hits = R.search_evidence_pg(plan)
                qd_hits, qdrant_status = R.search_evidence_qdrant(plan)
                evidence = R.merge_evidence_hits(pg_hits, qd_hits)
                if plan.retrieval_constraints:
                    evidence = R.filter_hits_by_constraints(
                        evidence, plan.retrieval_constraints
                    )
            if plan.want_still or plan.want_photo:
                photos, photo_status = R.search_photos(plan, self.photo)

            if getattr(plan, "want_story", False):
                stories = R.search_stories(plan)
            if getattr(plan, "want_journal", False):
                journals = R.search_journals(plan)

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
            plan, evidence, photos, stories, journals, photo_status
        )

        new_ctx = _update_context_from_plan(
            ctx,
            plan,
            [h.evidence_id for h in evidence],
            [p.external_id for p in photos],
            [s.story_id for s in stories],
            [j.journal_id for j in journals],
        )
        new_ctx = self.store.save(new_ctx)

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
        providers["story_search"] = {
            "ok": True,
            "detail": f"hits={len(stories)}" if plan.want_story else "not_requested",
        }
        providers["journal_search"] = {
            "ok": True,
            "detail": (
                f"hits={len(journals)}"
                if plan.want_journal
                else ("capture_intent" if plan.journal_capture_intent else "not_requested")
            ),
        }

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
            story_hits=[s.to_dict() for s in stories],
            journal_hits=[j.to_dict() for j in journals],
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
