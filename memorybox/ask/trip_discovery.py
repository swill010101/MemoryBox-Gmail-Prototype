"""Resolve named-trip Asks from evidence windows — before I11A inference.

Possessive/place compilation yields a semantic hint (Alaska), not an album title.
Broad retrieve uses person + time; this module scores place/travel evidence,
clusters candidate trip windows, then keeps eligible rows for the resolved trip.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from memorybox.ask.place_match import filter_photo_hits_to_places
from memorybox.ask.retrieve import (
    EvidenceHit,
    JournalHit,
    PhotoHit,
    StoryHit,
    VideoHit,
    _place_trip_keywords,
    trip_discovery_pending,
)
from memorybox.planner import QueryPlan
from memorybox.planner.temporal import date_in_windows

_GAP_DAYS = 14


def _day(raw: Any) -> str | None:
    s = str(raw or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            date.fromisoformat(s[:10])
            return s[:10]
        except ValueError:
            return None
    return None


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _place_tokens(plan: QueryPlan) -> list[str]:
    return _place_trip_keywords(plan)


def _text_matches_place(blob: str, tokens: list[str]) -> bool:
    if not tokens:
        return False
    low = blob.lower()
    for tok in tokens:
        t = (tok or "").lower().strip()
        if not t:
            continue
        if len(t) <= 3:
            if re.search(rf"\b{re.escape(t)}\b", low):
                return True
        elif t in low:
            return True
    return False


def _cluster_days(days: list[str], *, gap: int = _GAP_DAYS) -> list[tuple[str, str, int]]:
    uniq = sorted({d for d in days if d})
    if not uniq:
        return []
    clusters: list[tuple[str, str, int]] = []
    start = prev = uniq[0]
    n = 1
    for day in uniq[1:]:
        a = date.fromisoformat(prev)
        b = date.fromisoformat(day)
        if (b - a).days <= gap:
            n += 1
            prev = day
            continue
        clusters.append((start, prev, n))
        start = prev = day
        n = 1
    clusters.append((start, prev, n))
    return clusters


@dataclass
class ModalityResolution:
    provider: str
    initial_candidate_count: int
    person_constraints: list[str]
    time_constraints: dict[str, Any]
    semantic_constraint: str | None
    constraint_applied: str
    post_filter_count: int
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "initial_candidate_count": self.initial_candidate_count,
            "person_constraints": self.person_constraints,
            "time_constraints": self.time_constraints,
            "semantic_constraint": self.semantic_constraint,
            "constraint_applied": self.constraint_applied,
            "post_filter_count": self.post_filter_count,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class TripDiscoveryResult:
    plan: QueryPlan
    evidence: list[EvidenceHit]
    photos: list[PhotoHit]
    videos: list[VideoHit]
    stories: list[StoryHit]
    journals: list[JournalHit]
    artifacts: list[dict[str, Any]]
    modalities: list[ModalityResolution] = field(default_factory=list)
    windows: list[tuple[str, str, int]] = field(default_factory=list)
    resolved: bool = False
    ambiguous: bool = False
    clarification: str | None = None
    comm_pipeline: list[dict[str, Any]] = field(default_factory=list)

    def span_payload(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "ambiguous": self.ambiguous,
            "clarification": self.clarification,
            "candidate_windows": [
                {"start": a, "end": b, "day_count": n} for a, b, n in self.windows
            ],
            "modalities": [m.to_dict() for m in self.modalities],
            "trip_labels": list(getattr(self.plan, "trip_labels", ()) or ()),
            "place_names": list(getattr(self.plan, "place_names", ()) or ()),
            "comm_pipeline": self.comm_pipeline[:80],
        }


def emit_retrieval_resolution_span(result: TripDiscoveryResult) -> None:
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store

        tid = ai_ctx.current_trace_id()
        if not tid:
            return
        store.insert_span(
            trace_id=tid,
            stage="retrieval_resolution",
            component="retrieve",
            operation="retrieval_resolution",
            status="ok" if not result.ambiguous else "error",
            error_class="ORCHESTRATION" if result.ambiguous else None,
            assembled_context=result.span_payload(),
            parsed={"modalities": [m.to_dict() for m in result.modalities]},
            disposition={
                "resolved": result.resolved,
                "eligible_photos": len(result.photos),
                "eligible_evidence": len(result.evidence),
                "comm_selected": sum(
                    1 for r in result.comm_pipeline if r.get("selected")
                ),
                "comm_skipped": sum(
                    1 for r in result.comm_pipeline if not r.get("selected")
                ),
            },
        )
    except Exception:  # noqa: BLE001
        return


def _time_constraints(plan: QueryPlan) -> dict[str, Any]:
    return {
        "time_start": getattr(plan, "time_start", None),
        "time_end": getattr(plan, "time_end", None),
        "temporal_windows": [list(w) for w in (getattr(plan, "temporal_windows", ()) or ())],
        "temporal_label": getattr(plan, "temporal_label", None),
    }


def _person_constraints(plan: QueryPlan, photo_status: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    st = photo_status or {}
    if st.get("requestor_person_id"):
        out.append(str(st["requestor_person_id"]))
    for n in getattr(plan, "person_names", ()) or ():
        if n:
            out.append(str(n))
    for p in getattr(plan, "person_ids", ()) or ():
        if p:
            out.append(str(p))
    return list(dict.fromkeys(out))


def _photo_modality(
    plan: QueryPlan,
    photos: list[PhotoHit],
    photo_status: dict[str, Any] | None,
    *,
    matched: list[PhotoHit],
    tokens: list[str],
) -> ModalityResolution:
    st = photo_status or {}
    initial = int(st.get("after_temporal_filter") or st.get("before_place_filter") or len(photos))
    if st.get("before_temporal_filter") is not None and not st.get("after_temporal_filter"):
        initial = int(st.get("before_temporal_filter") or initial)
    if trip_discovery_pending(plan):
        initial = int(st.get("after_temporal_filter") or st.get("before_place_filter") or len(photos))
    label = (list(getattr(plan, "place_names", ()) or ()) or [None])[0]
    exclusive = st.get("constraint_mode") == "exclusive_place_filter"
    if exclusive:
        post = int(st.get("after_place_filter") or len(photos))
        dropped = initial - post
        reason = None
        if dropped > 0 and post == 0 and label:
            reason = (
                f"{initial} Person-library photos became 0 because the literal "
                f"{label!r} location constraint was applied"
            )
        elif dropped > 0:
            reason = st.get("disclosure") or f"{dropped} photos dropped by exclusive place filter"
        return ModalityResolution(
            provider=str(st.get("provider_key") or "immich"),
            initial_candidate_count=initial,
            person_constraints=_person_constraints(plan, st),
            time_constraints=_time_constraints(plan),
            semantic_constraint=str(label) if label else None,
            constraint_applied="exclusive_place_filter",
            post_filter_count=post,
            skipped_reason=reason,
        )
    post = len(matched)
    reason = None
    if tokens and initial and post == 0:
        reason = (
            f"{initial} Person-library photos became 0: place hint "
            f"{(label or tokens[0])!r} matched none (no EXIF/GPS/text/album location)"
        )
    elif not photos and st.get("unavailable"):
        reason = str(st.get("detail") or "photo provider unavailable")
    elif not photos and st.get("detail") == "not_requested":
        reason = "not_requested"
    return ModalityResolution(
        provider=str(st.get("provider_key") or "immich"),
        initial_candidate_count=initial,
        person_constraints=_person_constraints(plan, st),
        time_constraints=_time_constraints(plan),
        semantic_constraint=str(label) if label else None,
        constraint_applied="hint_score" if tokens else "person_time_only",
        post_filter_count=post,
        skipped_reason=reason,
    )


def _comm_modality(
    *,
    provider: str,
    initial: int,
    matched: int,
    plan: QueryPlan,
    tokens: list[str],
    channel: str,
) -> ModalityResolution:
    label = (list(getattr(plan, "place_names", ()) or ()) or [None])[0]
    reason = None
    if tokens and initial and matched == 0:
        reason = f"{initial} {channel} candidate(s) had no {label or tokens[0]!r} text/travel match"
    return ModalityResolution(
        provider=provider,
        initial_candidate_count=initial,
        person_constraints=_person_constraints(plan, None),
        time_constraints=_time_constraints(plan),
        semantic_constraint=str(label) if label else None,
        constraint_applied="hint_score" if tokens else "person_time_only",
        post_filter_count=matched,
        skipped_reason=reason,
    )


def resolve_trip(
    plan: QueryPlan,
    *,
    evidence: list[EvidenceHit],
    photos: list[PhotoHit],
    videos: list[VideoHit] | None = None,
    stories: list[StoryHit] | None = None,
    journals: list[JournalHit] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    photo_status: dict[str, Any] | None = None,
    video_status: dict[str, Any] | None = None,
) -> TripDiscoveryResult:
    videos = list(videos or [])
    stories = list(stories or [])
    journals = list(journals or [])
    artifacts = list(artifacts or [])
    evidence = list(evidence)
    photos = list(photos)
    tokens = _place_tokens(plan)
    pending = trip_discovery_pending(plan)

    matched_photos = (
        filter_photo_hits_to_places(photos, plan.place_names) if tokens else list(photos)
    )
    matched_ev = []
    comm_pipeline: list[dict[str, Any]] = []
    for h in evidence:
        blob = _blob(h.summary, h.excerpt, " ".join(h.people or []), h.channel, h.evidence_kind)
        channel = str(h.channel or h.evidence_kind or "").lower()
        place_ok = (not tokens) or _text_matches_place(blob, tokens)
        travel_ok = False
        if not place_ok and str(channel) in {"email", "communication", ""}:
            try:
                from memorybox.ask.travel import extract_travel

                travel_ok = bool(
                    extract_travel(
                        subject=str(h.summary or ""),
                        body=str(h.excerpt or ""),
                        source_unit_id=str(h.evidence_id or ""),
                        source_evidence_id=str(h.evidence_id or ""),
                    )
                )
            except Exception:  # noqa: BLE001
                travel_ok = False
        selected = place_ok or travel_ok
        skip = None
        if tokens and not selected:
            skip = "no_place_hint_or_travel_match"
        comm_pipeline.append(
            {
                "evidence_id": h.evidence_id,
                "title": h.summary,
                "channel": channel,
                "day": _day(h.sent_at),
                "retrieved": True,
                "selected": selected,
                "skip_reason": skip,
                "place_hint_match": place_ok,
                "travel_extracted": travel_ok,
            }
        )
        if selected:
            matched_ev.append(h)
            if not travel_ok:
                try:
                    from memorybox.ask.travel import extract_travel as _et2

                    extra = _et2(
                        subject=str(h.summary or ""),
                        body=str(h.excerpt or ""),
                        source_unit_id=str(h.evidence_id or ""),
                        source_evidence_id=str(h.evidence_id or ""),
                    )
                    if extra:
                        comm_pipeline[-1]["travel_extracted"] = True
                except Exception:  # noqa: BLE001
                    pass

    matched_stories = [
        h
        for h in stories
        if not tokens or _text_matches_place(_blob(h.title, h.excerpt), tokens)
    ]
    matched_journals = [
        h
        for h in journals
        if not tokens or _text_matches_place(_blob(h.title, h.excerpt), tokens)
    ]
    matched_arts = [
        a
        for a in artifacts
        if not tokens
        or _text_matches_place(_blob(a.get("title"), a.get("summary"), a.get("excerpt")), tokens)
    ]
    matched_videos = list(videos)

    days: list[str] = []
    for h in matched_photos:
        d = _day(h.taken_at)
        if d:
            days.append(d)
    for h in matched_ev:
        d = _day(h.sent_at)
        if d:
            days.append(d)
        try:
            from memorybox.ask.travel import extract_travel as _et_days

            facts = _et_days(
                subject=str(h.summary or ""),
                body=str(h.excerpt or ""),
                source_unit_id=str(h.evidence_id or ""),
                source_evidence_id=str(h.evidence_id or ""),
            )
            if facts:
                for key in ("start", "end"):
                    dd = _day(facts.get(key))
                    if dd:
                        days.append(dd)
        except Exception:  # noqa: BLE001
            pass
    for h in matched_stories:
        d = _day(h.taken_at)
        if d:
            days.append(d)
    for h in matched_journals:
        d = _day(h.described_start_date) or _day(h.captured_at)
        if d:
            days.append(d)

    windows = _cluster_days(days)
    modalities = [
        _photo_modality(plan, photos, photo_status, matched=matched_photos, tokens=tokens),
        _comm_modality(
            provider="postgres",
            initial=len(evidence),
            matched=len(matched_ev),
            plan=plan,
            tokens=tokens,
            channel="communications/calendar",
        ),
        _comm_modality(
            provider=str((video_status or {}).get("provider_key") or "video"),
            initial=len(videos),
            matched=len(matched_videos),
            plan=plan,
            tokens=tokens,
            channel="video",
        ),
        _comm_modality(
            provider="postgres",
            initial=len(stories),
            matched=len(matched_stories),
            plan=plan,
            tokens=tokens,
            channel="stories",
        ),
        _comm_modality(
            provider="postgres",
            initial=len(journals),
            matched=len(matched_journals),
            plan=plan,
            tokens=tokens,
            channel="journals",
        ),
        _comm_modality(
            provider="postgres",
            initial=len(artifacts),
            matched=len(matched_arts),
            plan=plan,
            tokens=tokens,
            channel="artifacts",
        ),
    ]

    result = TripDiscoveryResult(
        plan=plan,
        evidence=evidence,
        photos=photos,
        videos=videos,
        stories=stories,
        journals=journals,
        artifacts=artifacts,
        modalities=modalities,
        windows=windows,
        comm_pipeline=comm_pipeline,
    )

    if not pending:
        return result

    ranked = sorted(windows, key=lambda w: w[2], reverse=True)
    if len(ranked) >= 2 and ranked[0][2] > 0 and ranked[1][2] >= max(2, ranked[0][2] // 2):
        label = (list(plan.place_names or ()) or ["that place"])[0]
        spans = "; ".join(f"{a}–{b}" for a, b, _n in ranked[:4])
        result.ambiguous = True
        result.clarification = (
            f"More than one {label} trip window in this period ({spans}). "
            "Which trip should MemoryBox use?"
        )
        result.plan = replace(
            plan,
            requires_clarification=True,
            ambiguity_message=result.clarification,
            notes=tuple(list(plan.notes) + ["trip_windows_ambiguous"]),
        )
        result.evidence = []
        result.photos = []
        result.videos = []
        result.stories = []
        result.journals = []
        result.artifacts = []
        return result

    if not ranked:
        # No place-matching evidence: do not dump the whole year into I11A.
        result.photos = []
        result.evidence = []
        result.videos = []
        result.stories = []
        result.journals = []
        result.artifacts = []
        result.plan = replace(
            plan,
            notes=tuple(
                [n for n in plan.notes if n != "trip_window_unresolved"]
                + ["trip_window_unresolved", "trip_discovery_no_place_match"]
            ),
        )
        return result

    start, end, _n = ranked[0]
    win = ((start, end),)
    notes = [n for n in plan.notes if n != "trip_window_unresolved"]
    notes.append("trip_window_resolved")
    result.plan = replace(
        plan,
        time_start=start,
        time_end=end,
        temporal_windows=win,
        temporal_label=f"{start}–{end}",
        notes=tuple(notes),
    )
    result.resolved = True

    def _in_win(raw: Any) -> bool:
        d = _day(raw)
        if not d:
            return False
        return date_in_windows(d, win)

    result.photos = [h for h in photos if not h.taken_at or _in_win(h.taken_at)]
    result.evidence = [h for h in matched_ev if not h.sent_at or _in_win(h.sent_at)]
    result.videos = [h for h in videos if not h.taken_at or _in_win(h.taken_at)]
    result.stories = [h for h in matched_stories if not h.taken_at or _in_win(h.taken_at)]
    result.journals = [
        h
        for h in matched_journals
        if _in_win(h.described_start_date)
        or _in_win(h.described_end_date)
        or _in_win(h.captured_at)
    ]
    result.artifacts = matched_arts
    kept_ids = {str(h.evidence_id) for h in result.evidence}
    for row in result.comm_pipeline:
        eid = str(row.get("evidence_id") or "")
        if row.get("selected") and eid not in kept_ids:
            row["selected"] = False
            row["skip_reason"] = row.get("skip_reason") or "outside_resolved_trip_window"
    if result.modalities:
        m0 = result.modalities[0]
        result.modalities[0] = replace(
            m0,
            post_filter_count=len(result.photos),
            constraint_applied="hint_score_then_window",
        )
    return result
