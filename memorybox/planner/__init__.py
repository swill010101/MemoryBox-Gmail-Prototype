"""Query Planner v0 — generalized ask + session context → retrieval plan.

Intent-oriented (I4 semantic rule): "show me" is a presentation verb, not a
media-type identifier. Broad visual asks request relevant visual memories
(stills + video when available). I4 executes only currently wired providers;
video/HVRT is planned on the contract, not implemented in I4.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from memorybox.context import AskContext

VisualScope = Literal["none", "broad", "still_only", "video_only"]

# Explicit still-only narrowing (not "pictures"/"images").
STILL_ONLY_RE = re.compile(r"(?i)\b(photos?|stills?)\b")
# Explicit video-only.
VIDEO_ONLY_RE = re.compile(
    r"(?i)\b(videos?|video\s+clips?|clips?|footage|home\s*movies?)\b"
)
# Broad visual wording — NOT permanently PhotoProvider-only.
BROAD_VISUAL_RE = re.compile(
    r"(?i)\b(pictures?|images?|snapshots?|gallery|album|visuals?)\b"
)
SHOW_ME_RE = re.compile(r"(?i)\bshow\s+me\b")
EMAIL_RE = re.compile(
    r"(?i)\b("
    r"emails?|e-mails?|mail|messages?|inbox|correspondence|wrote|signed\s+off"
    r")\b"
)
CALENDAR_RE = re.compile(
    r"(?i)\b("
    r"calendar|appointment|schedule|event|meeting|ics"
    r")\b"
)
RELATIONSHIP_RE = re.compile(r"(?i)\brelationship\b|\bbetween\b.+\band\b")
FOLLOWUP_RE = re.compile(
    r"(?i)^\s*("
    r"just\s+the\s+ones?\b|"
    r"only\s+(?:the\s+)?(?:ones?|those)\b|"
    r"what\s+happened\s+(?:right\s+)?after\b|"
    r"what\s+else\b|"
    r"and\s+(?:then|after)\b|"
    r"narrow\s+(?:to|that)\b|"
    r"filter\b|"
    r"same\s+(?:trip|place|person|time)\b"
    r")"
)
AFTER_RE = re.compile(
    r"(?i)\b(?:right\s+)?after\s+(?:that|this|it)\b|\bwhat\s+happened\s+after\b"
)
ELSE_RE = re.compile(
    r"(?i)\bwhat\s+else\b|\banything\s+else\b|\bother\s+(?:emails?|photos?|events?)\b"
)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
PERSON_WITH_RE = re.compile(
    r"(?i)\b(?:with|of|featuring|including)\s+"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b"
)
PERSON_POSSESSIVE_RE = re.compile(
    r"(?-i:\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s)\b"
)
# "Show me NAME" — case-sensitive name token so "pictures" is never a person under (?i).
SHOW_ME_PERSON_RE = re.compile(
    r"(?i)\bshow\s+me\s+"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b"
)
PLACE_FROM_RE = re.compile(
    r"(?i)\b(?:from|in|at|near|around)\s+"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b"
)
_ENTITY_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "our",
        "your",
        "this",
        "that",
        "those",
        "these",
        "me",
        "myself",
        "christmas",
        "thanksgiving",
        "pictures",
        "picture",
        "photos",
        "photo",
        "images",
        "image",
        "videos",
        "video",
        "emails",
        "email",
        "ones",
        "one",
        "trip",
        "year",
        "years",
        "last",
        "past",
        "just",
        "only",
        "what",
        "happened",
        "right",
        "after",
        "else",
        "have",
        "from",
        "with",
        "show",
        "find",
        "get",
        "see",
        "relationship",
    }
)


@dataclass(frozen=True)
class QueryPlan:
    original_ask: str
    effective_ask: str
    is_followup: bool
    want_photo: bool
    """I4 compat: True when still/visual retrieval should run on available still provider."""
    want_communication: bool
    want_calendar: bool
    visual_scope: VisualScope = "none"
    """none | broad (stills+video intent) | still_only | video_only."""
    want_visual: bool = False
    want_still: bool = False
    want_video: bool = False
    """Video intent for later providers; I4 does not wire HVRT/video retrieval."""
    person_names: tuple[str, ...] = ()
    place_names: tuple[str, ...] = ()
    event_labels: tuple[str, ...] = ()
    time_start: str | None = None
    time_end: str | None = None
    inherit_from_context: bool = False
    notes: tuple[str, ...] = ()
    temporal_after: bool = False
    broaden_same_context: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def modalities(self) -> tuple[str, ...]:
        out: list[str] = []
        if self.want_visual or self.want_still or self.want_video:
            out.append("visual")
        if self.want_still:
            out.append("still")
            out.append("photo")  # legacy context key for I4 inheritance
        if self.want_video:
            out.append("video")
        if self.want_communication:
            out.append("communication")
        if self.want_calendar:
            out.append("calendar_event")
        return tuple(out)


def _clean_entity(name: str) -> str | None:
    n = (name or "").strip()
    if not n or n.lower() in _ENTITY_STOP:
        return None
    if len(n) < 2:
        return None
    return n


def _extract_people(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for rx in (PERSON_WITH_RE, PERSON_POSSESSIVE_RE, SHOW_ME_PERSON_RE):
        for m in rx.finditer(text or ""):
            ent = _clean_entity(m.group(1))
            if ent and ent not in found:
                found.append(ent)
    return tuple(found)


def _extract_places(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for m in PLACE_FROM_RE.finditer(text or ""):
        ent = _clean_entity(m.group(1))
        if ent and ent not in found:
            found.append(ent)
    return tuple(found)


def _extract_years(text: str) -> tuple[str | None, str | None]:
    years = YEAR_RE.findall(text or "")
    if not years:
        return None, None
    if len(years) == 1:
        y = years[0]
        return f"{y}-01-01", f"{y}-12-31"
    return f"{years[0]}-01-01", f"{years[-1]}-12-31"


def _resolve_visual_scope(
    q: str,
    *,
    want_email: bool,
    want_cal: bool,
    want_relationship: bool,
    people: list[str],
) -> tuple[VisualScope, list[str]]:
    """Map NL to visual_scope. 'show me' alone is never a media type."""
    notes: list[str] = []
    if want_email or want_cal or want_relationship:
        return "none", notes

    video_only = bool(VIDEO_ONLY_RE.search(q))
    still_only = bool(STILL_ONLY_RE.search(q))
    broad_word = bool(BROAD_VISUAL_RE.search(q))
    show_me = bool(SHOW_ME_RE.search(q))

    if video_only and not still_only and not broad_word:
        notes.append("visual_scope=video_only")
        return "video_only", notes

    if video_only and (still_only or broad_word):
        # Mixed wording → broad visual memories
        notes.append("visual_scope=broad_mixed_wording")
        return "broad", notes

    if still_only and not broad_word:
        notes.append("visual_scope=still_only")
        return "still_only", notes

    if broad_word:
        notes.append("visual_scope=broad")
        return "broad", notes

    # "Show me <Person>…" without email/relationship → broad visual memories
    if show_me and people:
        notes.append("visual_scope=broad_show_me_person")
        return "broad", notes

    return "none", notes


def plan_ask(ask: str, ctx: AskContext) -> QueryPlan:
    """Build a retrieval plan from the ask and inherited session context.

    Generalized: does not hard-code demo people, places, phrases, dates, or IDs.
    Intent-oriented: modalities follow user intent, not internal object jargon.
    """
    q = (ask or "").strip()
    notes: list[str] = []
    is_followup = bool(FOLLOWUP_RE.search(q)) or (
        len(q.split()) <= 8
        and not ctx.is_empty()
        and bool(re.search(r"(?i)\b(just|only|those|that|this|after|else)\b", q))
    )

    people = list(_extract_people(q))
    places = list(_extract_places(q))
    t0, t1 = _extract_years(q)
    temporal_after = bool(AFTER_RE.search(q))
    broaden = bool(ELSE_RE.search(q))

    want_email = bool(EMAIL_RE.search(q))
    want_cal = bool(CALENDAR_RE.search(q))
    want_relationship = bool(RELATIONSHIP_RE.search(q))
    if want_relationship:
        notes.append("intent_domain_relationship")

    visual_scope, vnotes = _resolve_visual_scope(
        q,
        want_email=want_email,
        want_cal=want_cal,
        want_relationship=want_relationship,
        people=people,
    )
    notes.extend(vnotes)

    want_still = visual_scope in ("broad", "still_only")
    want_video = visual_scope in ("broad", "video_only")
    want_visual = want_still or want_video
    # I4 retrieval: stills via PhotoProvider when still intent is active.
    want_photo = want_still

    inherit = False
    visual_ctx = any(
        m in (ctx.modalities_active or ())
        for m in ("visual", "photo", "still", "video")
    )
    if is_followup or (
        not want_visual
        and not want_email
        and not want_cal
        and not want_relationship
        and not ctx.is_empty()
    ):
        inherit = True
        notes.append("inherited_session_context")
        for p in ctx.person_names:
            if p not in people:
                people.append(p)
        for p in ctx.place_names:
            if p not in places:
                places.append(p)
        if t0 is None and ctx.time_start:
            t0 = ctx.time_start
        if t1 is None and ctx.time_end:
            t1 = ctx.time_end
        if not want_visual and not want_email and not want_cal:
            want_email = "communication" in ctx.modalities_active
            want_cal = "calendar_event" in ctx.modalities_active
            if visual_ctx:
                visual_scope = "broad"
                want_still = True
                want_video = True
                want_visual = True
                want_photo = True
                notes.append("inherited_visual_context_as_broad")

    if is_followup and people and visual_ctx:
        visual_scope = visual_scope if visual_scope != "none" else "broad"
        want_still = True
        want_video = visual_scope != "still_only"
        want_visual = True
        want_photo = True

    if temporal_after or broaden:
        want_email = True
        want_cal = True
        notes.append("temporal_or_broaden_followup")

    if want_relationship and not want_visual:
        # Domain/relationship asks: Evidence-backed when available; not a visual default.
        want_email = True
        want_cal = True
        notes.append("relationship_uses_evidence_modalities")

    if not want_visual and not want_email and not want_cal:
        want_email = True
        want_cal = True
        notes.append("default_comms_calendar")

    parts = [q]
    if inherit:
        if people:
            parts.append("people:" + ",".join(people))
        if places:
            parts.append("places:" + ",".join(places))
        if t0 or t1:
            parts.append(f"time:{t0 or ''}..{t1 or ''}")
    if visual_scope != "none":
        parts.append(f"visual_scope:{visual_scope}")
    effective = " | ".join(parts)

    event_labels = list(ctx.event_labels) if inherit else []
    if places and "trip" in q.lower():
        label = f"trip:{places[0]}"
        if label not in event_labels:
            event_labels.append(label)
    # Holiday-ish tokens as event labels when present (generic, not demo-locked)
    for hol in ("Christmas", "Thanksgiving", "Hanukkah", "Easter"):
        if re.search(rf"(?i)\b{hol}\b", q) and hol not in event_labels:
            event_labels.append(hol)

    if want_video and not want_still:
        notes.append("video_intent_no_i4_provider")

    return QueryPlan(
        original_ask=q,
        effective_ask=effective,
        is_followup=is_followup,
        want_photo=want_photo,
        want_communication=want_email,
        want_calendar=want_cal,
        visual_scope=visual_scope,
        want_visual=want_visual,
        want_still=want_still,
        want_video=want_video,
        person_names=tuple(people),
        place_names=tuple(places),
        event_labels=tuple(event_labels),
        time_start=t0,
        time_end=t1,
        inherit_from_context=inherit,
        notes=tuple(notes),
        temporal_after=temporal_after,
        broaden_same_context=broaden,
    )
