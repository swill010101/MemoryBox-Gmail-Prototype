"""Resolve named-trip Asks from evidence windows — before I11A inference.

Possessive/place compilation yields a semantic hint (Alaska), not an album title.
Broad retrieve uses person + time; this module scores place/travel evidence,
clusters candidate trip windows, then keeps eligible rows for the resolved trip.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

from memorybox.ask.place_match import filter_photo_hits_to_places
from memorybox.ask.retrieve import (
    EvidenceHit,
    JournalHit,
    PhotoHit,
    StoryHit,
    VideoHit,
    _place_trip_keywords,
    hit_who_blob,
    trip_discovery_pending,
)
from memorybox.planner import QueryPlan
from memorybox.planner.temporal import date_in_windows

_GAP_DAYS = 14
_HIGH_GAP_DAYS = 7
_TRIP_PAD_DAYS = 3
_WEAK_PLACE_TOKENS = frozenset({"las", "the", "and", "our", "for"})
_VEGAS_CONTEXT = (
    "las vegas",
    "vegas",
    "sphere",
    "eagles",
    "paradise",
    "harry reid",
    "nevada",
    "flight",
    "airport",
    "itinerary",
    "calendar",
    "concert",
    "hotel",
)


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


def _hit_who_blob(h: EvidenceHit) -> str:
    """Email: structured From/To. Never people[] (Takeout co-occurrence)."""
    return hit_who_blob(h)


def _place_tokens(plan: QueryPlan) -> list[str]:
    return _place_trip_keywords(plan)


def _text_matches_place(blob: str, tokens: list[str]) -> bool:
    reason = _place_match_reason(blob, tokens)
    return reason is not None


def _place_match_reason(blob: str, tokens: list[str]) -> str | None:
    """Distinctive place/travel clues only. Never treat standalone 'las' as Vegas."""
    if not tokens:
        return None
    low = blob.lower()
    joined = " ".join(t.lower() for t in tokens)
    vegas_ask = any(t in {"las vegas", "vegas"} or "las vegas" in t for t in tokens) or (
        "las vegas" in joined
    )
    if vegas_ask:
        if "las vegas" in low:
            return "phrase:las vegas"
        if re.search(r"\bvegas\b", low) and any(ctx in low for ctx in _VEGAS_CONTEXT if ctx != "vegas"):
            return "vegas_with_travel_or_event_context"
        if any(p in low for p in ("eagles", "sphere", "paradise", "harry reid")):
            return "vegas_event_or_locality_alias"
        return None
    for tok in tokens:
        t = (tok or "").lower().strip()
        if not t or t in _WEAK_PLACE_TOKENS or t == "las":
            continue
        if len(t) <= 3:
            if re.search(rf"\b{re.escape(t)}\b", low):
                return f"short_token:{t}"
        elif t in low:
            return f"token:{t}"
    return None


def _vegas_gps(lat: Any, lon: Any) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    return 35.85 <= lat_f <= 36.45 and -115.45 <= lon_f <= -114.85


def _pad_span(start: str, end: str, *, days: int = _TRIP_PAD_DAYS) -> tuple[str, str]:
    a = date.fromisoformat(start) - timedelta(days=days)
    b = date.fromisoformat(end) + timedelta(days=days)
    return a.isoformat(), b.isoformat()


def _windows_cover(inner: tuple[str, str], outer: tuple[tuple[str, str], ...]) -> bool:
    """True when every day of inner falls in the discovery Ask windows."""
    if not outer:
        return False
    cur = date.fromisoformat(inner[0])
    last = date.fromisoformat(inner[1])
    while cur <= last:
        if not date_in_windows(cur.isoformat(), outer):
            return False
        cur += timedelta(days=1)
    return True


def _comm_anchor(match_reason: str | None, channel: str) -> tuple[str, str] | None:
    """Strength and source class for trip-window anchors. Weak mail is not an anchor."""
    ch = str(channel or "").lower()
    reason = str(match_reason or "")
    if ch == "calendar" and reason:
        return "high", "calendar"
    if reason.startswith("travel"):
        return "high", "travel"
    if reason in {
        "phrase:las vegas",
        "vegas_event_or_locality_alias",
        "vegas_with_travel_or_event_context",
    }:
        return "medium", "communication"
    if reason.startswith("token:") or reason.startswith("short_token:"):
        return "medium", "communication"
    return None


def _cross_source_ok(sources: set[str]) -> bool:
    if "calendar" in sources and "media" in sources:
        return True
    if "travel" in sources and "media" in sources:
        return True
    if "calendar" in sources and "travel" in sources:
        return True
    if "media" in sources and "communication" in sources:
        return True
    if "calendar" in sources and "communication" in sources:
        return True
    return False


def _span_equals_discovery(start: str, end: str, disc: tuple[tuple[str, str], ...]) -> bool:
    if len(disc) != 1:
        return False
    return str(disc[0][0])[:10] == start and str(disc[0][1])[:10] == end


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
    person_library_unwindowed_n: int | None = None
    person_assets_in_window_n: int | None = None
    year_fair_applied: bool | None = None
    stills_in_window_n: int | None = None
    videos_in_window_n: int | None = None

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
            "person_library_unwindowed_n": self.person_library_unwindowed_n,
            "person_assets_in_window_n": self.person_assets_in_window_n,
            "year_fair_applied": self.year_fair_applied,
            "stills_in_window_n": self.stills_in_window_n,
            "videos_in_window_n": self.videos_in_window_n,
            "gallery_display_is_presentation_only": True,
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
    needs_refetch: bool = False
    discovery_windows: tuple[tuple[str, str], ...] = ()
    resolved_window: tuple[str, str] | None = None

    def span_payload(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "ambiguous": self.ambiguous,
            "clarification": self.clarification,
            "needs_refetch": self.needs_refetch,
            "discovery_windows": [list(w) for w in self.discovery_windows],
            "resolved_trip_window": list(self.resolved_window) if self.resolved_window else None,
            "needs_refetch": self.needs_refetch,
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
        payload = result.span_payload()
        extra = getattr(result, "span_extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        store.insert_span(
            trace_id=tid,
            stage="retrieval_resolution",
            component="retrieve",
            operation="retrieval_resolution",
            status="ok" if not result.ambiguous else "error",
            error_class="ORCHESTRATION" if result.ambiguous else None,
            assembled_context=payload,
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
    window_n = st.get("person_assets_in_window_n")
    if window_n is not None:
        initial = int(window_n)
    else:
        initial = int(st.get("after_temporal_filter") or st.get("before_place_filter") or len(photos))
        if st.get("before_temporal_filter") is not None and not st.get("after_temporal_filter"):
            initial = int(st.get("before_temporal_filter") or initial)
        if trip_discovery_pending(plan):
            initial = int(st.get("after_temporal_filter") or st.get("before_place_filter") or len(photos))
    extra = dict(
        person_library_unwindowed_n=(
            int(st["person_library_unwindowed_n"])
            if st.get("person_library_unwindowed_n") is not None
            else None
        ),
        person_assets_in_window_n=int(window_n) if window_n is not None else initial,
        year_fair_applied=bool(st.get("year_fair_applied")) if st.get("year_fair_applied") is not None else False,
        stills_in_window_n=(
            int(st["person_stills_in_window_n"])
            if st.get("person_stills_in_window_n") is not None
            else None
        ),
        videos_in_window_n=(
            int(st["person_videos_in_window_n"])
            if st.get("person_videos_in_window_n") is not None
            else None
        ),
    )
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
            **extra,
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
        **extra,
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

    matched_photos = []
    for h in photos:
        loc_blob = _blob(
            h.location,
            h.place,
            h.city,
            h.state,
            h.country,
            h.original_filename,
        )
        if (
            not tokens
            or filter_photo_hits_to_places([h], plan.place_names)
            or _vegas_gps(h.latitude, h.longitude)
            or _place_match_reason(loc_blob, tokens)
        ):
            matched_photos.append(h)
    matched_ev = []
    comm_pipeline: list[dict[str, Any]] = []
    for h in evidence:
        blob = _blob(h.summary, h.excerpt, _hit_who_blob(h), h.channel, h.evidence_kind)
        channel = str(h.channel or h.evidence_kind or "").lower()
        match_reason = None if tokens else "no_place_tokens"
        if tokens:
            match_reason = _place_match_reason(blob, tokens)
        travel_ok = False
        travel_dest = None
        if not match_reason:
            try:
                from memorybox.ask.travel import extract_travel

                facts = extract_travel(
                    subject=str(h.summary or ""),
                    body=str(h.excerpt or ""),
                    source_unit_id=str(h.evidence_id or ""),
                    source_evidence_id=str(h.evidence_id or ""),
                )
                if facts:
                    travel_ok = True
                    dest = str(facts.get("destination") or facts.get("place") or "").lower()
                    travel_dest = dest or True
                    if not tokens:
                        match_reason = "travel_extracted"
                    elif _place_match_reason(dest + " " + blob, tokens) or (
                        any("vegas" in t or "alaska" in t or "florida" in t for t in tokens)
                        and dest
                    ):
                        match_reason = "travel_extracted:" + (dest or "itinerary")
                    elif travel_ok and tokens:
                        # Generic itinerary without the asked place is not an anchor.
                        travel_ok = False
            except Exception:  # noqa: BLE001
                travel_ok = False
        selected = bool(match_reason)
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
                "match_reason": match_reason,
                "place_hint_match": bool(match_reason) and not str(match_reason).startswith("travel"),
                "travel_extracted": bool(travel_ok or (match_reason and str(match_reason).startswith("travel"))),
            }
        )
        if selected:
            matched_ev.append(h)
            anc = _comm_anchor(match_reason, channel)
            if anc:
                comm_pipeline[-1]["anchor_strength"] = anc[0]
                comm_pipeline[-1]["anchor_source"] = anc[1]

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
    matched_videos = []
    for h in videos:
        blob = _blob(h.label, h.place, h.city, h.state, h.original_filename)
        if (
            not tokens
            or _place_match_reason(blob, tokens)
            or _vegas_gps(h.latitude, h.longitude)
        ):
            matched_videos.append(h)

    high_by_day: dict[str, set[str]] = {}
    medium_by_day: dict[str, set[str]] = {}

    def _mark(day: str | None, source: str, strength: str) -> None:
        if not day:
            return
        bucket = high_by_day if strength == "high" else medium_by_day
        bucket.setdefault(day, set()).add(source)

    for h in matched_photos:
        _mark(_day(h.taken_at), "media", "high")
    for h in matched_videos:
        _mark(_day(h.taken_at), "media", "high")
    for row in comm_pipeline:
        if not row.get("selected"):
            continue
        strength = str(row.get("anchor_strength") or "")
        src = str(row.get("anchor_source") or "")
        if strength == "high":
            _mark(row.get("day"), src or "calendar", "high")
        elif strength == "medium":
            _mark(row.get("day"), src or "communication", "medium")

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
    for h in matched_videos:
        d = _day(h.taken_at)
        if d:
            days.append(d)

    windows = _cluster_days(days)
    high_windows = _cluster_days(list(high_by_day), gap=_HIGH_GAP_DAYS)
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

    disc = tuple(getattr(plan, "temporal_windows", ()) or ())
    if not disc and getattr(plan, "time_start", None) and getattr(plan, "time_end", None):
        disc = ((str(plan.time_start)[:10], str(plan.time_end)[:10]),)

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
        discovery_windows=disc,
    )

    if not pending:
        return result

    def _sources_near(start: str, end: str) -> set[str]:
        lo = date.fromisoformat(start) - timedelta(days=_GAP_DAYS)
        hi = date.fromisoformat(end) + timedelta(days=_GAP_DAYS)
        found: set[str] = set()
        for bucket in (high_by_day, medium_by_day):
            for day, srcs in bucket.items():
                dd = date.fromisoformat(str(day)[:10])
                if lo <= dd <= hi:
                    found |= srcs
        return found

    def _bounds_with_nearby(start: str, end: str) -> tuple[str, str]:
        lo = date.fromisoformat(start) - timedelta(days=_GAP_DAYS)
        hi = date.fromisoformat(end) + timedelta(days=_GAP_DAYS)
        days_keep = [start, end]
        for day in medium_by_day:
            dd = date.fromisoformat(str(day)[:10])
            if lo <= dd <= hi:
                days_keep.append(day)
        for day in high_by_day:
            dd = date.fromisoformat(str(day)[:10])
            if lo <= dd <= hi:
                days_keep.append(day)
        return min(days_keep), max(days_keep)

    converged = []
    for a, b, n in high_windows:
        srcs = _sources_near(a, b)
        if _cross_source_ok(srcs):
            converged.append((a, b, n, srcs))
    ranked = sorted(converged, key=lambda w: w[2], reverse=True)
    if len(ranked) >= 2 and ranked[0][2] > 0 and ranked[1][2] >= max(2, ranked[0][2] // 2):
        label = (list(plan.place_names or ()) or ["that place"])[0]
        spans = "; ".join(f"{a}–{b}" for a, b, _n, _s in ranked[:4])
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
        # Anchors exist but do not yet converge across sources — do not invent a month-long trip.
        result.photos = list(matched_photos)
        result.evidence = list(matched_ev)
        result.videos = list(matched_videos)
        result.stories = list(matched_stories)
        result.journals = list(matched_journals)
        result.artifacts = list(matched_arts)
        result.plan = replace(
            plan,
            notes=tuple(
                [n for n in plan.notes if n != "trip_window_unresolved"]
                + [
                    "trip_window_unresolved",
                    "trip_discovery_no_cross_source"
                    if (high_windows or matched_ev or matched_photos)
                    else "trip_discovery_no_place_match",
                ]
            ),
        )
        return result

    start, end, _n, srcs = ranked[0]
    start, end = _bounds_with_nearby(start, end)
    start, end = _pad_span(start, end)
    win = ((start, end),)
    needs_refetch = not _span_equals_discovery(start, end, disc)
    notes = [n for n in plan.notes if n != "trip_window_unresolved"]
    notes.append("trip_window_resolved")
    notes.append(f"discovery_window={disc[0][0]}/{disc[0][1]}" if disc else "discovery_window=")
    notes.append(f"resolved_trip_window={start}/{end}")
    notes.append("convergence=" + ",".join(sorted(srcs)))
    if needs_refetch:
        notes.append("trip_window_extends_discovery")
    result.plan = replace(
        plan,
        time_start=start,
        time_end=end,
        temporal_windows=win,
        temporal_label=f"{start}–{end}",
        notes=tuple(notes),
    )
    result.resolved = True
    result.needs_refetch = needs_refetch
    result.resolved_window = (start, end)

    def _in_win(raw: Any) -> bool:
        d = _day(raw)
        if not d:
            return False
        return date_in_windows(d, win)

    # Media in the resolved span is eligible. Communications are trip-relevant
    # only with an independent match — not mere window membership.
    result.photos = [h for h in photos if not h.taken_at or _in_win(h.taken_at)]
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
    inference_ev: list[EvidenceHit] = []
    matched_ids = {str(h.evidence_id) for h in matched_ev}
    for h in evidence:
        d = _day(h.sent_at)
        in_span = bool(d and date_in_windows(d, win)) or (not h.sent_at)
        channel = str(h.channel or h.evidence_kind or "").lower()
        if channel in {"calendar", "calendar_event"} and in_span:
            inference_ev.append(h)
            continue
        if str(h.evidence_id) in matched_ids and (in_span or not d):
            inference_ev.append(h)
    result.evidence = inference_ev
    kept_ids = {str(h.evidence_id) for h in result.evidence}
    for row in result.comm_pipeline:
        eid = str(row.get("evidence_id") or "")
        day = row.get("day")
        in_span = bool(day and date_in_windows(str(day), win))
        row["in_resolved_window"] = in_span
        row["eligible_for_consideration"] = in_span
        if row.get("selected") and eid not in kept_ids and not in_span:
            row["selected"] = False
            row["skip_reason"] = row.get("skip_reason") or "outside_resolved_trip_window"
        if in_span and not row.get("match_reason"):
            row["skip_reason"] = row.get("skip_reason") or "window_membership_not_trip_relevance"
        if channel := str(row.get("channel") or ""):
            if channel == "calendar" and in_span and eid in kept_ids and not row.get("match_reason"):
                row["selected"] = True
                row["match_reason"] = "calendar_in_resolved_window"
                row["skip_reason"] = None
    if result.modalities:
        m0 = result.modalities[0]
        result.modalities[0] = replace(
            m0,
            post_filter_count=len(result.photos),
            constraint_applied="cross_source_anchors_then_resolved_window",
        )
    return result


def apply_plan_windows(
    plan: QueryPlan,
    *,
    evidence: list[EvidenceHit],
    photos: list[PhotoHit],
    videos: list[VideoHit] | None = None,
    stories: list[StoryHit] | None = None,
    journals: list[JournalHit] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Keep retrieved rows in the resolved trip span after a refetch."""
    win = tuple(getattr(plan, "temporal_windows", ()) or ())
    if not win and getattr(plan, "time_start", None) and getattr(plan, "time_end", None):
        win = ((str(plan.time_start)[:10], str(plan.time_end)[:10]),)

    def _in_win(raw: Any) -> bool:
        d = _day(raw)
        if not d:
            return False
        return date_in_windows(d, win)

    videos = list(videos or [])
    stories = list(stories or [])
    journals = list(journals or [])
    artifacts = list(artifacts or [])
    tokens = _place_tokens(plan)
    kept_ev: list[EvidenceHit] = []
    for h in evidence:
        d = _day(h.sent_at)
        in_span = (not d) or _in_win(h.sent_at)
        if not in_span:
            continue
        channel = str(h.channel or h.evidence_kind or "").lower()
        if channel in {"calendar", "calendar_event"}:
            kept_ev.append(h)
            continue
        blob = _blob(h.summary, h.excerpt, _hit_who_blob(h), h.channel, h.evidence_kind)
        if (not tokens) or _place_match_reason(blob, tokens):
            kept_ev.append(h)
            continue
        try:
            from memorybox.ask.travel import extract_travel

            facts = extract_travel(
                subject=str(h.summary or ""),
                body=str(h.excerpt or ""),
                source_unit_id=str(h.evidence_id or ""),
                source_evidence_id=str(h.evidence_id or ""),
            )
            dest = str((facts or {}).get("destination") or "")
            if facts and _place_match_reason(dest + " " + blob, tokens):
                kept_ev.append(h)
        except Exception:  # noqa: BLE001
            pass
    return {
        "evidence": kept_ev,
        "photos": [h for h in photos if not h.taken_at or _in_win(h.taken_at)],
        "videos": [h for h in videos if not h.taken_at or _in_win(h.taken_at)],
        "stories": [h for h in stories if not h.taken_at or _in_win(h.taken_at)],
        "journals": [
            h
            for h in journals
            if _in_win(h.described_start_date)
            or _in_win(h.described_end_date)
            or _in_win(h.captured_at)
        ],
        "artifacts": artifacts,
    }
