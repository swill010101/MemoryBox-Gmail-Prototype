"""Thin Experience Orchestrator — Evidence First Ask + Story (I5) + Journal (I5A)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memorybox.ask import retrieve as R
from memorybox.ask.deps import build_llm, build_photo, build_video, provider_snapshot
from memorybox.context import (
    AskContext,
    ContextPatch,
    ContextStore,
    apply_patch,
    default_context_store,
)
from memorybox.mbql import compile_ask
from memorybox.planner import QueryPlan, plan_ask
from memorybox.providers.llm.protocol import LlmProvider
from memorybox.providers.photo.protocol import PhotoProvider
from memorybox.providers.video.protocol import VideoIntelligenceProvider


def _prefer_live_llm(llm: LlmProvider) -> LlmProvider:
    """If Ask started while Ollama was down, retry once on tell."""
    inner = getattr(llm, "inner", llm)
    if getattr(inner, "provider_key", "") != "fake_llm":
        return llm
    from memorybox.config import settings as cfg

    if not (cfg.ollama_base_url or "").strip():
        return llm
    fresh = build_llm()
    inner2 = getattr(fresh, "inner", fresh)
    if getattr(inner2, "provider_key", "") != "fake_llm":
        return fresh
    return llm


def _apply_person_life_event_windows(plan: QueryPlan) -> QueryPlan:
    """Fill birthday/anniversary temporal windows from MB People when recorded.

    Does not invent dates. Missing fact → clarification / disclosure.
    """
    from dataclasses import replace

    kind = getattr(plan, "life_event_kind", None)
    if kind not in ("birthday", "anniversary"):
        return plan

    years = list(getattr(plan, "life_event_years", ()) or ())
    notes = list(plan.notes)
    if not years:
        from memorybox.planner.temporal import holiday_years_all

        years = holiday_years_all()
        notes.append("life_event_all_years")

    person_id = (plan.person_ids[0] if plan.person_ids else None)
    display = plan.person_names[0] if plan.person_names else None

    try:
        from memorybox.person import find_ask_person_by_name, get_person
        from memorybox.planner.temporal import observance_window_md
        from memorybox.profile.facts import get_current_fact
        from memorybox.profile.life_events import list_life_events_for_person
    except Exception as exc:  # pragma: no cover
        return replace(
            plan,
            requires_clarification=True,
            ambiguity_message=f"Could not load person observance data ({exc}).",
            notes=tuple(notes + ["life_event_resolve_import_failed"]),
        )

    if not person_id and display:
        try:
            view = find_ask_person_by_name(display, lazy_seed=False)
            if view:
                person_id = view.id
                display = view.display_name or display
        except Exception:
            person_id = None

    if not person_id:
        name = display or "that person"
        return replace(
            plan,
            requires_clarification=True,
            ambiguity_message=(
                f"No MemoryBox person matched for {name}; "
                f"cannot resolve {kind} without a recorded person."
            ),
            notes=tuple(notes + ["life_event_person_missing"]),
        )

    if not display:
        try:
            pv = get_person(person_id)
            display = pv.display_name if pv else person_id
        except Exception:
            display = person_id

    md: tuple[int, int] | None = None
    source_note = None
    if kind == "birthday":
        try:
            fact = get_current_fact(person_id, "birth_date")
        except Exception:
            fact = None
        if not fact or not fact.value_date:
            msg = (
                f"No birth_date recorded for {display}. "
                "Add it on the person profile to search birthday photos."
            )
            if getattr(plan, "want_cross_source", False):
                # Everything-about still returns the mixed pack; do not empty Gallery.
                return replace(
                    plan,
                    person_ids=(person_id,),
                    person_names=(display,) if display else plan.person_names,
                    requires_clarification=False,
                    ambiguity_message=None,
                    notes=tuple(notes + ["life_event_birth_date_missing", "life_event_no_windows_cross_source"]),
                )
            return replace(
                plan,
                person_ids=(person_id,),
                person_names=(display,) if display else plan.person_names,
                requires_clarification=True,
                ambiguity_message=msg,
                notes=tuple(notes + ["life_event_birth_date_missing"]),
            )
        try:
            y, m, d = [int(x) for x in str(fact.value_date)[:10].split("-")]
            md = (m, d)
            source_note = f"birth_date={fact.value_date[:10]}"
        except Exception:
            return replace(
                plan,
                requires_clarification=True,
                ambiguity_message=f"Invalid birth_date for {display}.",
                notes=tuple(notes + ["life_event_birth_date_invalid"]),
            )
    else:
        try:
            events = [
                e
                for e in list_life_events_for_person(person_id)
                if e.event_kind == "marriage" and e.event_date
            ]
        except Exception:
            events = []
        if not events:
            msg = (
                f"No marriage/anniversary date recorded for {display}. "
                "Add a marriage life event to search anniversary photos."
            )
            if getattr(plan, "want_cross_source", False):
                return replace(
                    plan,
                    person_ids=(person_id,),
                    person_names=(display,) if display else plan.person_names,
                    requires_clarification=False,
                    ambiguity_message=None,
                    notes=tuple(notes + ["life_event_anniversary_missing", "life_event_no_windows_cross_source"]),
                )
            return replace(
                plan,
                person_ids=(person_id,),
                person_names=(display,) if display else plan.person_names,
                requires_clarification=True,
                ambiguity_message=msg,
                notes=tuple(notes + ["life_event_anniversary_missing"]),
            )
        if len(events) > 1:
            return replace(
                plan,
                person_ids=(person_id,),
                person_names=(display,) if display else plan.person_names,
                requires_clarification=True,
                ambiguity_message=(
                    f"Multiple marriage events for {display}; "
                    "clarify which anniversary."
                ),
                notes=tuple(notes + ["life_event_anniversary_ambiguous"]),
            )
        try:
            y, m, d = [int(x) for x in str(events[0].event_date)[:10].split("-")]
            md = (m, d)
            source_note = f"marriage_date={events[0].event_date[:10]}"
        except Exception:
            return replace(
                plan,
                requires_clarification=True,
                ambiguity_message=f"Invalid anniversary date for {display}.",
                notes=tuple(notes + ["life_event_anniversary_invalid"]),
            )

    assert md is not None
    windows = tuple(observance_window_md(md[0], md[1], yr) for yr in years)
    base = "Birthday" if kind == "birthday" else "Anniversary"
    if len(years) == 1:
        label = f"{base} {years[0]}"
    else:
        label = f"{base} {years[0]}–{years[-1]}"
    notes.append("life_event_windows_from_mb_people")
    if source_note:
        notes.append(source_note)
    notes.append("holiday_pad_days=2")
    return replace(
        plan,
        person_ids=(person_id,),
        person_names=(display,) if display else plan.person_names,
        time_start=min(w[0] for w in windows),
        time_end=max(w[1] for w in windows),
        temporal_windows=windows,
        temporal_label=label,
        # Explore path — do not force profile-only short-circuit
        profile_intent=None if getattr(plan, "profile_intent", None) in ("birth", "anniversary") else plan.profile_intent,
        want_photo=True,
        want_still=True,
        want_video=True,
        want_visual=True,
        visual_scope="broad" if plan.visual_scope == "none" else plan.visual_scope,
        requires_clarification=False,
        ambiguity_message=None,
        notes=tuple(notes),
    )


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
    video_hits: list[dict[str, Any]]
    artifact_hits: list[dict[str, Any]]
    guided_capture_hits: list[dict[str, Any]]
    missing_disclosure: str | None
    provider_status: dict[str, Any]
    inventing: bool = False
    trace_id: str | None = None
    coverage: dict[str, Any] | None = None
    narrative_pack: dict[str, Any] | None = None
    narration_unavailable: bool = False

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
            "video_hits": self.video_hits,
            "artifact_hits": self.artifact_hits,
            "guided_capture_hits": self.guided_capture_hits,
            "missing_disclosure": self.missing_disclosure,
            "provider_status": self.provider_status,
            "inventing": self.inventing,
            "trace_id": self.trace_id,
            "coverage": self.coverage,
            "narrative_pack": self.narrative_pack,
            "narration_unavailable": self.narration_unavailable,
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
    videos: list[R.VideoHit] | None = None,
    video_status: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    guided_capture: list[dict[str, Any]] | None = None,
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    citations: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    videos = videos or []
    video_status = video_status or {}
    artifacts = artifacts or []
    guided_capture = guided_capture or []

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
                    else (
                        "trusted_provider"
                        if getattr(p, "identity_trust", "") == "trusted_provider"
                        else "provider_candidate"
                    )
                ),
            }
        )
        who = ", ".join(p.people) if p.people else "people not labeled"
        where = p.location or "location not labeled"
        trust = getattr(p, "identity_trust", "confirmed")
        label = (
            "Fact"
            if trust == "confirmed"
            else ("Trusted provider" if trust == "trusted_provider" else "Candidate")
        )
        prefix = ""
        if trust == "candidate":
            prefix = "Unconfirmed Immich name candidate — "
        elif trust == "trusted_provider":
            prefix = "Trusted Immich/provider-seeded identity (not owner-confirmed) — "
        statements.append(
            {
                "text": f"{prefix}Photo asset from provider ({who}; {where}).",
                "label": label,
                "evidence_ids": [],
                "photo_external_ids": [p.external_id],
                "story_ids": [],
                "journal_ids": [],
                "provenance_kind": (
                    "archive_evidence"
                    if trust == "confirmed"
                    else (
                        "trusted_provider"
                        if trust == "trusted_provider"
                        else "provider_candidate"
                    )
                ),
                "attribution": getattr(p, "attribution", None),
            }
        )

    for v in videos:
        trust = getattr(v, "identity_trust", "confirmed")
        citations.append(
            {
                "kind": "video",
                "provider_key": v.provider_key,
                "external_id": v.external_id,
                "video_external_id": v.video_external_id,
                "start_sec": v.start_sec,
                "end_sec": v.end_sec,
                "face_external_id": v.face_external_id,
                "label": v.label,
                "play_url": v.play_url,
                "identity_trust": trust,
                "mb_person_id": v.mb_person_id,
                "mb_person_name": v.mb_person_name,
                "attribution": v.attribution,
                "provenance_kind": (
                    "archive_evidence"
                    if trust == "confirmed"
                    else (
                        "trusted_provider"
                        if trust == "trusted_provider"
                        else "provider_candidate"
                    )
                ),
            }
        )
        if trust == "candidate":
            prefix = "Unconfirmed video face candidate — "
        elif trust == "trusted_provider":
            prefix = "Trusted-provider-seeded identity (not owner-confirmed) — "
        else:
            prefix = ""
        spoken = getattr(v, "spoken_text", None)
        statements.append(
            {
                "text": (
                    f"{prefix}Spoken passage: {spoken}"
                    if spoken
                    else (
                        f"{prefix}Video segment {v.video_external_id} "
                        f"[{v.start_sec:.1f}s–{v.end_sec:.1f}s]."
                    )
                ),
                "label": (
                    "Fact"
                    if trust == "confirmed"
                    else (
                        "Trusted provider"
                        if trust == "trusted_provider"
                        else "Candidate"
                    )
                ),
                "evidence_ids": [],
                "photo_external_ids": [],
                "video_external_ids": [v.external_id],
                "story_ids": [],
                "journal_ids": [],
                "provenance_kind": (
                    "archive_evidence"
                    if trust == "confirmed"
                    else (
                        "trusted_provider"
                        if trust == "trusted_provider"
                        else "provider_candidate"
                    )
                ),
                "attribution": v.attribution,
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

    for a in artifacts:
        aid = a.get("artifact_id")
        label = a.get("label") or "Artifact"
        kind = a.get("kind") or "artifact"
        citations.append(
            {
                "kind": "artifact",
                "artifact_id": aid,
                "artifact_kind": kind,
                "label": label,
                "deep_link": a.get("deep_link"),
                "provenance_kind": "artifact_identity",
                "attribution": f"Artifact “{label}” ({kind})",
            }
        )
        statements.append(
            {
                "text": (
                    f"Artifact “{label}” ({kind.replace('_', ' ')}) — "
                    f"{a.get('representation_count') or 0} representation(s). "
                    "Matched by Artifact identity/metadata, not filename-as-meaning."
                ),
                "label": "Artifact",
                "evidence_ids": [],
                "photo_external_ids": [],
                "story_ids": list(a.get("story_ids") or []),
                "journal_ids": [],
                "artifact_ids": [aid] if aid else [],
                "provenance_kind": "artifact_identity",
                "attribution": f"Artifact “{label}”",
            }
        )

    for g in guided_capture:
        rid = g.get("response_id")
        cred = g.get("credibility") or "not_rated"
        citations.append(
            {
                "kind": "guided_capture",
                "response_id": rid,
                "respondent_name": g.get("respondent_name"),
                "question_body": g.get("question_body"),
                "campaign_title": g.get("campaign_title"),
                "channel": g.get("channel"),
                "credibility": cred,
                "received_at": g.get("received_at"),
                "provenance_kind": "guided_capture_response",
                "attribution": g.get("attribution"),
            }
        )
        statements.append(
            {
                "text": f"{g.get('attribution')}: {g.get('excerpt')}",
                "label": "Guided Capture",
                "evidence_ids": [],
                "photo_external_ids": [],
                "story_ids": [],
                "journal_ids": [],
                "guided_capture_ids": [rid] if rid else [],
                "provenance_kind": "guided_capture_response",
                "attribution": g.get("attribution"),
                "credibility": cred,
            }
        )

    photo_unavail = bool(
        (plan.want_still or plan.want_photo) and photo_status.get("unavailable")
    )
    video_unavail = bool(plan.want_video and video_status.get("unavailable"))
    video_only = bool(
        plan.want_video and not plan.want_still and plan.visual_scope == "video_only"
    )

    if video_only and video_unavail and not evidence and not stories and not journals and not artifacts and not guided_capture:
        text = (
            "Video intelligence provider is unavailable, so MemoryBox cannot search "
            "video presence spans right now. This is not the same as finding no videos. "
            "MemoryBox will not invent video results."
        )
        return "provider_unavailable", text, statements, citations, None

    if photo_unavail and not evidence and not stories and not journals and not videos and not artifacts and not guided_capture:
        text = (
            "Photo/still provider is unavailable, so MemoryBox cannot search the "
            "visual library right now. This is not the same as finding no photos. "
            "No other Evidence modalities returned hits for this ask."
        )
        return "provider_unavailable", text, statements, citations, None

    if photo_unavail and (evidence or stories or journals or videos or artifacts or guided_capture):
        text = (
            "Photo provider is unavailable (not 'no photos'). "
            f"Found {len(evidence)} Evidence, {len(stories)} Story, "
            f"{len(journals)} Journal, {len(videos)} video, "
            f"{len(artifacts)} Artifact, {len(guided_capture)} Guided Capture hit(s). "
            "Family-history claims below are limited to cited items with provenance."
        )
        return "mixed", text, statements, citations, None

    if (
        (plan.want_photo or plan.want_still or plan.want_video
         or getattr(plan, "want_story", False)
         or getattr(plan, "want_journal", False)
         or getattr(plan, "want_artifact", False)
         or getattr(plan, "want_guided_capture", False))
        and not photos
        and not videos
        and not evidence
        and not stories
        and not journals
        and not artifacts
        and not guided_capture
        and photo_status.get("ok", True)
        and (not plan.want_video or video_status.get("ok", True))
        and not video_unavail
    ):
        missing = (
            "Insufficient Evidence: no matching photos, videos, Stories, Journals, "
            "Artifacts, Guided Capture Responses, or email/calendar Evidence were found "
            "for this ask. "
            "MemoryBox will not invent a family fact."
        )
        return "insufficient", missing, statements, citations, missing

    if not evidence and not photos and not videos and not stories and not journals and not artifacts and not guided_capture:
        if video_unavail and plan.want_video:
            text = (
                "Video intelligence provider is unavailable (not 'no videos'). "
                "No other modalities returned hits. MemoryBox will not invent results."
            )
            return "provider_unavailable", text, statements, citations, None
        missing = (
            "Insufficient Evidence for this ask. Available archive Evidence does not "
            "support a factual family-history answer. MemoryBox will not invent one."
        )
        return "insufficient", missing, statements, citations, missing

    ask = getattr(plan, "original_ask", "") or ""
    sms_hits = [
        h
        for h in evidence
        if (getattr(h, "source", "") == "sms_export")
        or str(getattr(h, "channel", "") or "").lower()
        in {"sms", "text", "imessage", "mms", "rcs"}
    ]
    if sms_hits and R.SMS_NARRATIVE_RE.search(ask):
        if getattr(plan, "output_mode", "show") != "tell":
            who = ", ".join(
                n
                for n in (plan.person_names or ())
                if str(n).strip() and str(n).lower() not in R._SMS_FAKE_PEOPLE
            ) or "the named person"
            n = len(sms_hits)
            total = getattr(sms_hits[0], "match_total", None) or n
            scope = getattr(sms_hits[0], "count_scope", None) or "ingested SMS/iMessage export"
            text = (
                f"Retrieved the last {n} of {total} text messages between you and {who} "
                f"({scope}). Writing a narrative from those messages is I11 and is not "
                "generated here. The gallery shows the retrieved messages."
            )
            return "evidence_backed", text, statements, citations, None
    if sms_hits and R.SMS_COUNT_RE.search(ask) and getattr(plan, "output_mode", "show") != "tell":
        total = getattr(sms_hits[0], "match_total", None)
        if total is None:
            total = len(sms_hits)
        scope = getattr(sms_hits[0], "count_scope", None) or "ingested SMS/iMessage export"
        label = (
            "heart emoji / Loved tapbacks"
            if R.SMS_HEART_ASK_RE.search(ask)
            else "text messages"
        )
        text = f"{total} {label} ({scope})."
        return "evidence_backed", text, statements, citations, None
    if sms_hits and R.SMS_LAST_N_RE.search(ask) and getattr(plan, "output_mode", "show") != "tell":
        who = ", ".join(
            n
            for n in (plan.person_names or ())
            if str(n).strip() and str(n).lower() not in R._SMS_FAKE_PEOPLE
        ) or "the named person"
        n = len(sms_hits)
        total = getattr(sms_hits[0], "match_total", None) or n
        scope = getattr(sms_hits[0], "count_scope", None) or "ingested SMS/iMessage export"
        text = f"Last {n} of {total} text messages between you and {who} ({scope})."
        return "evidence_backed", text, statements, citations, None

    parts = []
    if guided_capture:
        parts.append(
            f"Found {len(guided_capture)} Guided Capture Response(s) "
            "(respondent testimony — citable without Story promotion; "
            "credibility shown when set, not used for ranking)."
        )
    if artifacts:
        parts.append(
            f"Found {len(artifacts)} Artifact hit(s) "
            "(matched by identity/metadata/relationships — not filename-as-meaning)."
        )
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
    if videos:
        confirmed_n = sum(
            1 for v in videos if getattr(v, "identity_trust", "confirmed") == "confirmed"
        )
        trusted_n = sum(
            1
            for v in videos
            if getattr(v, "identity_trust", "") == "trusted_provider"
        )
        candidate_n = len(videos) - confirmed_n - trusted_n
        bits = []
        if confirmed_n:
            bits.append(
                f"{confirmed_n} via owner-confirmed MB Person video mapping"
            )
        if trusted_n:
            bits.append(
                f"{trusted_n} via trusted-provider-seeded MB Person "
                "(not owner-confirmed)"
            )
        if candidate_n:
            bits.append(
                f"{candidate_n} unconfirmed video face-candidate "
                "(not MB-confirmed identity)"
            )
        if bits:
            parts.append("Found video segment hit(s): " + "; ".join(bits) + ".")
        if video_status.get("disclosure"):
            parts.append(str(video_status["disclosure"]))
    if photos:
        confirmed_n = sum(
            1 for p in photos if getattr(p, "identity_trust", "confirmed") == "confirmed"
        )
        trusted_n = sum(
            1
            for p in photos
            if getattr(p, "identity_trust", "") == "trusted_provider"
        )
        candidate_n = len(photos) - confirmed_n - trusted_n
        if confirmed_n and not candidate_n and not trusted_n:
            parts.append(
                f"Found {confirmed_n} photo hit(s) via owner-confirmed MB Person→Immich mapping."
            )
        elif trusted_n and not confirmed_n and not candidate_n:
            parts.append(
                f"Found {trusted_n} photo hit(s) via trusted Immich/provider-seeded "
                "MB Person (not owner-confirmed)."
            )
        elif candidate_n and not confirmed_n and not trusted_n:
            parts.append(
                f"Found {candidate_n} unconfirmed Immich name-candidate photo hit(s) "
                "(not MB-confirmed identity)."
            )
        else:
            parts.append(
                f"Found photo hit(s): {confirmed_n} owner-confirmed, "
                f"{trusted_n} trusted-provider-seeded, "
                f"{candidate_n} unconfirmed candidate."
            )
        if photo_status.get("disclosure"):
            parts.append(str(photo_status["disclosure"]))
    if evidence:
        sms_n = sum(
            1
            for h in evidence
            if (getattr(h, "source", "") == "sms_export")
            or str(getattr(h, "channel", "") or "").lower()
            in {"sms", "text", "imessage", "mms", "rcs"}
        )
        scope = next(
            (getattr(h, "count_scope", None) for h in evidence if getattr(h, "count_scope", None)),
            None,
        )
        if sms_n and sms_n == len(evidence):
            if scope:
                parts.append(f"Found {len(evidence)} text message(s) ({scope}).")
            else:
                parts.append(
                    f"Found {len(evidence)} text message(s) "
                    "(ingested SMS/iMessage/MMS export — not a complete phone history)."
                )
        else:
            parts.append(f"Found {len(evidence)} Evidence hit(s) (email/calendar).")
    if plan.retrieval_constraints:
        parts.append(
            "Retrieval used context constraints: "
            + ", ".join(plan.retrieval_constraints)
            + "."
        )
    parts.append("Factual claims are limited to the citations listed.")
    modalities_hit = sum(
        1
        for x in (
            bool(journals),
            bool(stories),
            bool(photos),
            bool(videos),
            bool(evidence),
            bool(artifacts),
            bool(guided_capture),
        )
        if x
    )
    if modalities_hit > 1:
        kind = "mixed"
    elif guided_capture:
        kind = "guided_capture_backed"
    elif artifacts:
        kind = "artifact_backed"
    elif journals:
        kind = "journal_backed"
    elif stories:
        kind = "story_backed"
    elif videos and not photos and not evidence:
        kind = "video_backed"
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
        video: VideoIntelligenceProvider | None = None,
    ) -> None:
        self.store = store or default_context_store
        self.photo = photo if photo is not None else build_photo()
        from memorybox.ai_trace.wrapper import trace_llm

        self.llm = trace_llm(llm if llm is not None else build_llm())
        self.video = video if video is not None else build_video()

    def ask(self, text: str, *, session_id: str | None = None) -> AskResult:
        from memorybox.ai_trace.request import tracing_ask

        with tracing_ask(text, session_id) as tr:
            result = self._ask_impl(text, session_id=session_id)
            plan = result.plan if isinstance(result.plan, dict) else {}
            tr.note_planner(plan)
            tr.complete(
                disposition={
                    "answer_kind": result.answer_kind,
                    "answer_text": (result.answer_text or "")[:500],
                    "inventing": result.inventing,
                    "evidence_hits": len(result.evidence_hits or []),
                    "photo_hits": len(result.photo_hits or []),
                    "missing_disclosure": result.missing_disclosure,
                }
            )
            result.trace_id = tr.trace_id
            return result

    def _ask_impl(self, text: str, *, session_id: str | None = None) -> AskResult:
        ctx = self.store.get_or_create(session_id)
        try:
            plan = compile_ask(text, ctx, llm=self.llm)
        except Exception:  # noqa: BLE001 — Q4: never fail Ask because MBQL failed
            plan = plan_ask(text, ctx)

        # I9A: owner → Relationship service → Person id (no display_name string hacks)
        from dataclasses import replace

        from memorybox.profile import resolve_relational_ask

        rel = resolve_relational_ask(text)
        if (
            rel.intent == "none"
            and plan.person_names
            and not getattr(plan, "person_ids", ())
            and (
                plan.want_visual
                or plan.want_communication
                or plan.want_calendar
                or getattr(plan, "want_spoken", False)
            )
        ):
            # Named Ask → attach MB Person id so photo/video/email/SMS share identity.
            # P2-BL-I8-02: unique Peggy → Peggy George; genuine ambiguity clarifies.
            from memorybox.person import AmbiguousIdentityError, find_ask_person_by_name

            pids: list[str] = []
            labels: list[str] = []
            ambiguous = None
            for name in sorted(plan.person_names, key=lambda n: (-len(n), n.lower())):
                nl = name.lower()
                if any(
                    nl == lab.lower() or nl in lab.lower() or lab.lower() in nl
                    for lab in labels
                ):
                    continue
                try:
                    view = find_ask_person_by_name(name, photo=self.photo, lazy_seed=True)
                except AmbiguousIdentityError as exc:
                    ambiguous = exc
                    view = None
                except Exception:  # noqa: BLE001
                    view = None
                if not view:
                    continue
                pids.append(view.id)
                labels.append(view.display_name or name)
            if ambiguous and not pids and plan.want_communication:
                plan = replace(
                    plan,
                    requires_clarification=True,
                    ambiguity_message=str(ambiguous),
                    notes=tuple(list(plan.notes) + ["p2_bl_i8_02_clarify"]),
                )
            elif pids:
                note = (
                    "resolved_person_ids_for_comms"
                    if plan.want_communication or plan.want_calendar
                    else "resolved_person_ids_for_visual"
                )
                plan = replace(
                    plan,
                    person_ids=tuple(dict.fromkeys(pids)),
                    person_names=tuple(dict.fromkeys(labels or list(plan.person_names))),
                    notes=tuple(list(plan.notes) + [note]),
                )
        if rel.intent != "none":
            notes = list(plan.notes) + ["i9a_relational_resolve"]
            if rel.ok and rel.intent in (
                "kinship_list",
                "kinship_pictures",
                "how_related",
                "kinship_in_photo",
            ):
                notes = list(notes) + ["i6_kinship_resolve"]
                hits = list(rel.kinship_hits or [])
                hit_ids = tuple(
                    dict.fromkeys(
                        str(h.get("person_id"))
                        for h in hits
                        if h.get("person_id")
                    )
                )
                hit_names = tuple(
                    str(h.get("display_name") or "")
                    for h in hits
                    if h.get("display_name")
                )
                if rel.intent == "kinship_pictures" and hit_ids:
                    plan = replace(
                        plan,
                        person_ids=hit_ids,
                        person_names=hit_names,
                        notes=tuple(notes),
                        profile_intent=rel.intent,
                        profile_answer=rel.to_dict(),
                        want_photo=True,
                        want_still=True,
                        want_video=True,
                        want_visual=True,
                        visual_scope="broad",
                    )
                else:
                    plan = replace(
                        plan,
                        person_ids=hit_ids if hit_ids else ((rel.person_id,) if rel.person_id else ()),
                        person_names=hit_names
                        if hit_names
                        else ((rel.display_name,) if rel.display_name else ()),
                        notes=tuple(notes),
                        profile_intent=rel.intent,
                        profile_answer=rel.to_dict(),
                        want_photo=False,
                        want_still=False,
                        want_video=False,
                        want_visual=False,
                        visual_scope="none",
                    )
            elif rel.ok and rel.person_id:
                # Replace context people entirely — never keep prior "father" in a
                # follow-up "mother" / relational ask (that caused Eugene-as-mother).
                names = (rel.display_name,) if rel.display_name else ()
                plan = replace(
                    plan,
                    person_ids=(rel.person_id,),
                    person_names=names,
                    notes=tuple(notes),
                    profile_intent=rel.intent,
                    profile_answer=rel.to_dict(),
                )
                # Who / birth / anniversary: profile facts, not photo modality required
                # Exception: birthday/anniversary Explore asks with years keep visual.
                life_explore = bool(
                    getattr(plan, "life_event_kind", None)
                    and (
                        getattr(plan, "life_event_years", ())
                        or "life_event_all_years" in (plan.notes or ())
                    )
                )
                if rel.intent in ("who", "birth", "anniversary") and not life_explore:
                    plan = replace(
                        plan,
                        want_photo=False,
                        want_still=False,
                        want_video=False,
                        want_visual=False,
                        visual_scope="none",
                        want_communication=False,
                        want_calendar=False,
                        want_story=False,
                        want_journal=False,
                        want_artifact=False,
                        want_guided_capture=False,
                    )
                elif rel.intent in ("pictures", "self") and not plan.want_visual:
                    # "show me dad" — planner may not have set visual before resolve
                    plan = replace(
                        plan,
                        want_photo=True,
                        want_still=True,
                        want_video=True,
                        want_visual=True,
                        visual_scope="broad",
                        notes=tuple(
                            list(plan.notes) + ["i9a_pictures_forces_broad_visual"]
                        ),
                    )
            elif not rel.ok:
                # Failed relational resolve: do not fall through to prior context person
                plan = replace(
                    plan,
                    notes=tuple(notes),
                    profile_intent=rel.intent,
                    profile_answer=rel.to_dict(),
                    person_ids=(),
                    person_names=(),
                    requires_clarification=True,
                    ambiguity_message=rel.ambiguity or rel.disclosure,
                    want_photo=False,
                    want_still=False,
                    want_video=False,
                    want_visual=False,
                    visual_scope="none",
                )

        # Birthday / anniversary Explore windows from MB People facts when present.
        plan = _apply_person_life_event_windows(plan)
        from memorybox.ask.semantic import apply_constraints_to_plan

        plan = apply_constraints_to_plan(plan)

        evidence: list[R.EvidenceHit] = []
        qdrant_status: dict[str, Any] = {"ok": False, "detail": "skipped"}
        photos: list[R.PhotoHit] = []
        photo_status: dict[str, Any] = {"ok": True, "detail": "not_requested"}
        videos: list[R.VideoHit] = []
        video_status: dict[str, Any] = {"ok": True, "detail": "not_requested"}
        stories: list[R.StoryHit] = []
        journals: list[R.JournalHit] = []
        artifacts: list[dict[str, Any]] = []
        guided_capture: list[dict[str, Any]] = []

        # Profile-backed short-circuit (who / birth / anniversary / I6 kinship explain)
        if (
            getattr(plan, "profile_intent", None)
            in ("who", "birth", "anniversary", "kinship_list", "how_related", "kinship_in_photo")
            and getattr(plan, "profile_answer", None)
            and (plan.profile_answer or {}).get("ok")
        ):
            ans = plan.profile_answer or {}
            statements: list[dict[str, Any]] = []
            citations: list[dict[str, Any]] = []
            if plan.profile_intent == "kinship_list":
                hits = ans.get("kinship_hits") or []
                role = ans.get("role_phrase") or "relative"
                if not hits:
                    text_out = ans.get("disclosure") or f"No {role}s found on the relationship graph."
                else:
                    lines = [
                        f"{h.get('display_name') or h.get('person_id')} — {h.get('label') or role}"
                        + (
                            f" (Derived: {h.get('path_summary')})"
                            if h.get("derived") and h.get("path_summary")
                            else ""
                        )
                        for h in hits
                    ]
                    text_out = (
                        f"Derived {role}s ({len(hits)}; not direct assertions):\n"
                        + "\n".join(f"• {ln}" for ln in lines)
                    )
                statements.append(
                    {
                        "text": text_out,
                        "label": "Kinship",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                    }
                )
            elif plan.profile_intent == "how_related":
                a = ans.get("display_name") or "A"
                b = ans.get("related_display_name") or "B"
                label = ans.get("role_phrase") or "related"
                path = ans.get("path_summary") or ""
                text_out = f"{a} → {b}: {label}."
                if path:
                    text_out += f" Path: {path}."
                if ans.get("derived"):
                    text_out += " (Derived — correct an underlying direct relationship if this is wrong.)"
                if ans.get("ambiguity"):
                    text_out += f" Note: {ans['ambiguity']}."
                statements.append(
                    {
                        "text": text_out,
                        "label": "Kinship path",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                    }
                )
            elif plan.profile_intent == "kinship_in_photo":
                hits = ans.get("kinship_hits") or []
                text_out = ans.get("disclosure") or (
                    f"{len(hits)} niece/nephew candidate(s) on the graph — "
                    "open a photo with recognized People to filter."
                )
                statements.append(
                    {
                        "text": text_out,
                        "label": "Kinship × photo",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                    }
                )
            elif plan.profile_intent == "who":
                name = ans.get("display_name") or ans.get("person_id")
                role = ans.get("role_phrase") or "relative"
                if role in ("self", "me"):
                    text_out = f"You are {name}."
                else:
                    text_out = f"Your {role} is {name}."
                if ans.get("inferred") and ans.get("inference_note"):
                    text_out = f"{text_out} ({ans['inference_note']}.)"
                statements.append(
                    {
                        "text": text_out,
                        "label": "Relationship",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                        "provenance_kind": (
                            "inferred_spouse_of_parent"
                            if ans.get("inferred")
                            else "owner_relationship"
                        ),
                        "attribution": (
                            ans.get("inference_note")
                            or "Owner-asserted relationship"
                        ),
                        "person_id": ans.get("person_id"),
                        "assertion_id": ans.get("assertion_id"),
                        "inferred": bool(ans.get("inferred")),
                    }
                )
            elif plan.profile_intent == "birth":
                fact = ans.get("fact") or {}
                name = ans.get("display_name") or "that person"
                bd = fact.get("value_date") or fact.get("value_text")
                text_out = f"{name} was born on {bd}."
                statements.append(
                    {
                        "text": text_out,
                        "label": "Person fact",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                        "provenance_kind": "owner_person_fact",
                        "attribution": "Owner-asserted person fact",
                        "person_id": ans.get("person_id"),
                        "fact": fact,
                    }
                )
            else:
                ev = ans.get("life_event") or {}
                bd = ev.get("event_date")
                parts = ev.get("participants") or []
                names = " and ".join(
                    p.get("display_name") or p.get("person_id") for p in parts
                )
                text_out = (
                    f"Anniversary / marriage date for {names}: {bd}."
                    if bd
                    else f"Marriage recorded for {names} (date not set)."
                )
                statements.append(
                    {
                        "text": text_out,
                        "label": "Life event",
                        "evidence_ids": [],
                        "photo_external_ids": [],
                        "story_ids": [],
                        "journal_ids": [],
                        "provenance_kind": "owner_life_event",
                        "attribution": "Owner-asserted shared life event",
                        "life_event": ev,
                    }
                )
            citations.append(
                {
                    "kind": "profile",
                    "intent": plan.profile_intent,
                    "person_id": ans.get("person_id"),
                    "assertion_id": ans.get("assertion_id"),
                    "provenance_kind": "owner_profile",
                }
            )
            new_ctx = _update_context_from_plan(ctx, plan, [], [], [], [])
            self.store.save(new_ctx)
            providers = provider_snapshot(photo=self.photo, llm=self.llm, video=self.video)
            providers["relational_resolve"] = ans
            return AskResult(
                session_id=new_ctx.session_id,
                ask=text,
                plan=plan.to_dict(),
                context=new_ctx.to_dict(),
                answer_kind="profile_backed",
                answer_text=text_out,
                statements=statements,
                citations=citations,
                evidence_hits=[],
                photo_hits=[],
                story_hits=[],
                journal_hits=[],
                video_hits=[],
                artifact_hits=[],
                guided_capture_hits=[],
                missing_disclosure=None,
                provider_status=providers,
                inventing=False,
            )

        if not plan.requires_clarification and not plan.journal_capture_intent:
            if plan.want_communication or plan.want_calendar:
                pg_hits = R.search_evidence_pg(plan)
                tell_pack = (
                    str((plan.output_mode if hasattr(plan, "output_mode") else "") or "")
                    == "tell"
                    or "tell_multimodal_i11" in (getattr(plan, "notes", ()) or ())
                )
                if (
                    ((R._sms_ask(plan) or R._email_ask(plan)) and plan.want_communication)
                    or tell_pack
                ):
                    evidence = pg_hits
                    qdrant_status = {
                        "ok": True,
                        "detail": (
                            "skipped_for_tell_pack"
                            if tell_pack
                            and not (R._sms_ask(plan) or R._email_ask(plan))
                            else (
                                "skipped_for_email_ask"
                                if R._email_ask(plan) and not R._sms_ask(plan)
                                else "skipped_for_sms_ask"
                            )
                        ),
                    }
                else:
                    qd_hits, qdrant_status = R.search_evidence_qdrant(plan)
                    evidence = R.merge_evidence_hits(pg_hits, qd_hits)
                if plan.retrieval_constraints:
                    evidence = R.filter_hits_by_constraints(
                        evidence, plan.retrieval_constraints
                    )
            # Photos first, then video. They share the Immich client for identity;
            # parallel calls RST person-library search (0 photos / 1 video).
            if plan.want_still or plan.want_photo:
                photo_limit = 0 if R._bounded_period_tell(plan) else 5000
                photos, photo_status = R.search_photos(plan, self.photo, limit=photo_limit)
            spoken_videos: list[R.VideoHit] = []
            if getattr(plan, "want_spoken", False):
                from memorybox.speech.retrieve import search_spoken_moments

                spoken_rows = search_spoken_moments(plan)
                spoken_videos = [
                    R.VideoHit(
                        provider_key=str(r.get("provider_key") or "hvrt"),
                        external_id=str(r.get("external_id") or r.get("id") or ""),
                        video_external_id=str(r.get("video_external_id") or ""),
                        start_sec=float(r.get("start_sec") or 0),
                        end_sec=float(r.get("end_sec") or 0),
                        label=str(r.get("label") or "Spoken moment"),
                        play_url=r.get("play_url"),
                        identity_trust=str(r.get("identity_trust") or "candidate"),
                        mb_person_id=r.get("mb_person_id"),
                        attribution=str(r.get("attribution") or "spoken_moment"),
                        spoken_text=r.get("spoken_text"),
                    )
                    for r in spoken_rows
                ]
                video_status = {
                    "ok": True,
                    "detail": f"spoken_moments={len(spoken_videos)}",
                    "evidence_first": True,
                }
            appearance: list[R.VideoHit] = []
            if plan.want_video and (
                not getattr(plan, "want_spoken", False)
                or getattr(plan, "want_cross_source", False)
            ):
                appearance, appear_status = R.search_videos(
                    plan,
                    self.video,
                    photo=self.photo,
                    limit=0 if R._bounded_period_tell(plan) else 48,
                )
                if not spoken_videos:
                    video_status = appear_status
                else:
                    video_status = {
                        **(video_status or {}),
                        "ok": bool((video_status or {}).get("ok", True))
                        and bool((appear_status or {}).get("ok", True)),
                        "appearance": appear_status,
                    }
            if spoken_videos and appearance:
                seen_v = {v.external_id for v in spoken_videos}
                videos = spoken_videos + [v for v in appearance if v.external_id not in seen_v]
            elif spoken_videos:
                videos = spoken_videos
            else:
                videos = appearance

            if getattr(plan, "want_story", False):
                stories = R.search_stories(
                    plan, limit=0 if R._bounded_period_tell(plan) else 12
                )
            if getattr(plan, "want_journal", False):
                journals = R.search_journals(
                    plan, limit=0 if R._bounded_period_tell(plan) else 12
                )
            if getattr(plan, "want_artifact", False):
                artifacts = R.search_artifacts(
                    plan, limit=0 if R._bounded_period_tell(plan) else 12
                )
            if getattr(plan, "want_guided_capture", False):
                guided_capture = R.search_guided_capture(plan)

        coverage: dict[str, Any] | None = None
        if getattr(plan, "want_cross_source", False) and not plan.requires_clarification:
            try:
                from memorybox.correlate.pack import apply_cross_source, propose_theme_links
                from memorybox.correlate.store import upsert_event

                themes = list(getattr(plan, "theme_labels", ()) or ())
                trips = list(plan.trip_labels or ())
                label = (themes[0] if themes else None) or (trips[0] if trips else None)
                event_id = None
                if label:
                    kind = "theme" if themes else "trip"
                    event_id = upsert_event(label, event_kind=kind)["id"]
                    propose_theme_links(
                        event_id=event_id,
                        evidence_hits=evidence,
                        theme=label,
                    )
                pack, filtered = apply_cross_source(
                    plan,
                    evidence=evidence,
                    photos=photos,
                    videos=videos,
                    stories=stories,
                    journals=journals,
                    artifacts=artifacts,
                    event_id=event_id,
                )
                evidence = filtered["evidence"]
                photos = filtered["photos"]
                videos = filtered["videos"]
                stories = filtered["stories"]
                journals = filtered["journals"]
                artifacts = filtered["artifacts"]
                coverage = {
                    **pack.coverage,
                    "missing": pack.missing,
                    "conflicts": pack.conflicts,
                    "event_id": pack.event_id,
                    "dropped_rejected": pack.dropped_rejected,
                    "hydrated_confirmed": pack.hydrated_confirmed,
                    "summary": pack.summary,
                }
            except Exception as exc:  # noqa: BLE001
                coverage = {"ok": False, "error": str(exc)}

        # First-name / person identity clarity (founder): 1→go, 0→Who is X?,
        # many→Please specify which X you would like.
        # I10A: a matching saved Story/Journal/Artifact is still an answer.
        # Do not hide owner recollection because the subject is not an MB Person.
        for st in (photo_status, video_status):
            mode = str((st or {}).get("identity_mode") or "")
            if mode in ("ambiguous_identity", "unknown_person"):
                msg = str(
                    (st or {}).get("clarify_message")
                    or (st or {}).get("disclosure")
                    or ""
                ).strip()
                if not msg:
                    names = (st or {}).get("ambiguous_person_names") or (
                        st or {}
                    ).get("unknown_person_names") or plan.person_names
                    label = (list(names)[0] if names else "this person")
                    if mode == "unknown_person":
                        msg = f"Who is {label}?"
                    else:
                        first = str(label).split()[0]
                        msg = f"Please specify which {first} you would like."
                photos = []
                videos = []
                if stories or journals or artifacts or evidence:
                    break
                plan = replace(
                    plan,
                    requires_clarification=True,
                    ambiguity_message=msg,
                )
                stories = []
                journals = []
                artifacts = []
                guided_capture = []
                evidence = []
                break

        # Disclose failed relational resolve when no other answer path
        if (
            getattr(plan, "profile_answer", None)
            and not (plan.profile_answer or {}).get("ok")
            and (plan.profile_answer or {}).get("disclosure")
            and not plan.requires_clarification
        ):
            disc = (plan.profile_answer or {}).get("disclosure")
            if not (photos or evidence or stories or journals or videos or artifacts or guided_capture):
                plan = replace(
                    plan,
                    requires_clarification=True,
                    ambiguity_message=disc,
                )

        answer_kind, answer_text, statements, citations, missing = _build_answer(
            plan,
            evidence,
            photos,
            stories,
            journals,
            photo_status,
            videos=videos,
            video_status=video_status,
            artifacts=artifacts,
            guided_capture=guided_capture,
        )
        narrative_pack: dict[str, Any] | None = None
        narration_unavailable = False
        if (
            getattr(plan, "output_mode", "show") == "tell"
            and answer_kind not in {"clarification", "journal_capture"}
        ):
            from memorybox.ask.narrative import tell_from_hits

            self.llm = _prefer_live_llm(self.llm)
            answer_text, narrative_pack, synth_meta = tell_from_hits(
                plan,
                llm=self.llm,
                evidence=evidence,
                photos=photos,
                videos=videos,
                stories=stories,
                journals=journals,
                artifacts=artifacts,
            )
            narration_unavailable = bool(synth_meta.get("fail_closed"))
            if narrative_pack and isinstance(narrative_pack.get("coverage"), dict):
                pack_cov = narrative_pack["coverage"]
                if coverage:
                    coverage = {
                        **coverage,
                        "summary": pack_cov.get("summary") or coverage.get("summary"),
                        "i11_missing": pack_cov.get("missing"),
                        "truncated": pack_cov.get("truncated"),
                    }
                else:
                    coverage = pack_cov
        if (
            coverage
            and coverage.get("summary")
            and answer_kind not in {"clarification", "journal_capture"}
            and getattr(plan, "output_mode", "show") != "tell"
        ):
            extra = str(coverage.get("summary") or "").strip()
            if extra and extra not in (answer_text or ""):
                answer_text = f"{extra} {answer_text}".strip()

        # I10: disclose cross-modality mapping gaps (Ask + Library share same Person X)
        cross: list[str] = []
        for st in (photo_status, video_status):
            disc = (st or {}).get("disclosure")
            if disc and disc not in cross:
                cross.append(str(disc))
        want_photo = bool(plan.want_still or plan.want_photo)
        want_vid = bool(getattr(plan, "want_video", False))
        if want_photo and want_vid:
            p_mode = (photo_status or {}).get("identity_mode") or ""
            v_mode = (video_status or {}).get("identity_mode") or ""
            p_unmap = (photo_status or {}).get("unmapped_person_names") or []
            v_unmap = (video_status or {}).get("unmapped_person_names") or []
            if "mapping" in p_mode and v_unmap:
                cross.append(
                    "Same MB Person has Immich/photo mapping but no HVRT/video mapping "
                    f"for {v_unmap} — attach the video face in Review to this Person."
                )
            if "mapping" in v_mode and p_unmap:
                cross.append(
                    "Same MB Person has HVRT/video mapping but no Immich/photo mapping "
                    f"for {p_unmap}."
                )
        if cross:
            extra = " ".join(cross)
            missing = f"{missing} {extra}".strip() if missing else extra

        new_ctx = _update_context_from_plan(
            ctx,
            plan,
            [h.evidence_id for h in evidence],
            [p.external_id for p in photos] + [v.external_id for v in videos],
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
            "theme": list(getattr(plan, "theme_labels", ()) or ()),
            "modality": list(plan.modalities),
            "time_label": getattr(plan, "temporal_label", None),
            "time_start": plan.time_start,
            "time_end": plan.time_end,
            "temporal_windows": [
                list(w) for w in (getattr(plan, "temporal_windows", ()) or ())
            ],
            "life_event_kind": getattr(plan, "life_event_kind", None),
            "life_event_years": list(getattr(plan, "life_event_years", ()) or ()),
        }

        providers = provider_snapshot(self.photo, self.llm, self.video)
        providers["qdrant"] = qdrant_status
        providers["photo_search"] = photo_status
        providers["video_search"] = video_status
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
        providers["artifact_search"] = {
            "ok": True,
            "detail": (
                f"hits={len(artifacts)}" if plan.want_artifact else "not_requested"
            ),
        }
        providers["guided_capture_search"] = {
            "ok": True,
            "detail": (
                f"hits={len(guided_capture)}"
                if getattr(plan, "want_guided_capture", False)
                else "not_requested"
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
            video_hits=[v.to_dict() for v in videos],
            artifact_hits=list(artifacts),
            guided_capture_hits=list(guided_capture),
            missing_disclosure=missing,
            provider_status=providers,
            inventing=False,
            coverage=coverage,
            narrative_pack=narrative_pack,
            narration_unavailable=narration_unavailable,
        )

    def get_context(self, session_id: str) -> AskContext:
        return self.store.get_or_create(session_id)

    def clear_context(self, session_id: str) -> AskContext:
        return self.store.clear(session_id)

    def change_context(self, session_id: str, patch: ContextPatch) -> AskContext:
        return self.store.patch(session_id, patch)
