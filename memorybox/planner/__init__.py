"""Query Planner v0 — intent-oriented Ask with typed context slots (I4 corrective).

Semantic rules (locked corrective acceptance):
  A. Current utterance > inherited context
  B. Inherit only missing slots
  C. Typed slots: person ≠ place ≠ event ≠ trip
  D. Supersede incompatible context on subject change
  E. Resolve references (then/there/that trip/the other trip) before retrieval
  F. Ambiguity must be disclosed
  G. Context-constrained retrieval (constraints on plan)
  H. Displayed context must match effective retrieval context

Generalized: no hard-coded demo people/places/events.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from memorybox.context import AskContext

VisualScope = Literal["none", "broad", "still_only", "video_only"]

STILL_ONLY_RE = re.compile(r"(?i)\b(photos?|stills?)\b")
VIDEO_ONLY_RE = re.compile(
    r"(?i)\b(videos?|video\s+clips?|clips?|footage|home\s*movies?)\b"
)
BROAD_VISUAL_RE = re.compile(
    r"(?i)\b(pictures?|images?|snapshots?|gallery|album|visuals?)\b"
)
SHOW_ME_RE = re.compile(r"(?i)\bshow\s+me\b")
EXPLORATORY_RE = re.compile(
    r"(?i)\b(?:"
    r"what\s+do\s+(?:you|i|we)\s+know\s+about|"
    r"tell\s+me\s+about|"
    r"what\s+do\s+(?:i|we)\s+have\s+(?:about|from|on)"
    r")\b"
)
SAID_ABOUT_RE = re.compile(
    r"(?i)\b(?:"
    r"what\s+did\b[\w\s,'-]{0,40}\bsay\b|"
    r"\bsaid\s+about\b|"
    r"\btell\s+me\s+what\b[\w\s,'-]{0,40}\bsaid\b"
    r")\b"
)
ABOUT_SUBJECT_RE = re.compile(
    r"(?i)\b(?:(?:what\s+do\s+(?:you|i|we)\s+know\s+about)|(?:tell\s+me\s+about)|"
    r"(?:what\s+do\s+(?:i|we)\s+have\s+(?:about|on))|\babout)\s+"
    r"(?:(?:our|my|the|a|an)\s+)?"
    r"(?!pictures?\b|photos?\b|images?\b|videos?\b|emails?\b|mail\b|stills?\b)"
    r"([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*)?)"
    r"(?!\s+trip\b)"
)
EMAIL_RE = re.compile(
    r"(?i)\b(emails?|e-mails?|mail|messages?|inbox|correspondence|wrote|signed\s+off)\b"
)
JOURNAL_INTENT_RE = re.compile(
    r"(?i)^\s*(?:i\s+(?:want|need)\s+to\s+journal|let\s+me\s+journal|"
    r"start\s+(?:a\s+)?journal|journal\s+now|open\s+journal|^journal)\s*[.!]?\s*$"
)
JOURNAL_ASK_RE = re.compile(
    r"(?i)\b(journals?|journal\s+entr(?:y|ies)|my\s+journal|what\s+did\s+i\s+journal)\b"
)
CALENDAR_RE = re.compile(
    r"(?i)\b(calendar|appointment|schedule|event|meeting|ics)\b"
)
RELATIONSHIP_RE = re.compile(r"(?i)\brelationship\b|\bbetween\b.+\band\b")
FOLLOWUP_RE = re.compile(
    r"(?i)^\s*("
    r"just\s+the\s+ones?\b|"
    r"only\s+(?:the\s+)?(?:ones?|those)\b|"
    r"what\s+happened\s+(?:right\s+)?after\b|"
    r"what\s+(?:was|is)\s+happening\b|"
    r"what\s+else\b|"
    r"and\s+(?:then|after)\b|"
    r"narrow\s+(?:to|that)\b|"
    r"filter\b|"
    r"same\s+(?:trip|place|person|time)\b|"
    r"no,?\s+i\s+meant\b|"
    r"(?:the\s+)?other\s+trip\b|"
    r"around\s+then\b|"
    r"at\s+that\s+time\b"
    r")"
)
AFTER_RE = re.compile(
    r"(?i)\b(?:right\s+)?after\s+(?:that|this|it)\b|\bwhat\s+happened\s+after\b"
)
ELSE_RE = re.compile(
    r"(?i)\bwhat\s+else\b|\banything\s+else\b|\bother\s+(?:emails?|photos?|events?)\b"
)
AROUND_THEN_RE = re.compile(
    r"(?i)\b("
    r"around\s+then|at\s+that\s+time|back\s+then|"
    r"what\s+(?:was|is)\s+happening\s+(?:around\s+)?then|"
    r"what\s+was\s+happening"
    r")\b"
)
OTHER_TRIP_RE = re.compile(
    r"(?i)\b("
    r"(?:the\s+)?other\s+trip|"
    r"(?:a\s+)?different\s+trip|"
    r"another\s+trip|"
    r"no,?\s+i\s+meant\s+(?:the\s+)?other"
    r")\b"
)
THAT_TRIP_RE = re.compile(r"(?i)\b(?:that|this|the)\s+trip\b|\bfrom\s+that\s+trip\b")
THERE_RE = re.compile(r"(?i)\b(?:there|from\s+there|at\s+that\s+place)\b")
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# Typed person extractors (not places).
# Name capture is case-insensitive — owners often type "dan will"; _clean_entity title-cases.
_PERSON_NAME = r"([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*)?)"
PERSON_WITH_RE = re.compile(
    rf"(?i)\b(?:with|featuring|including)\s+{_PERSON_NAME}\b"
)
PERSON_OF_RE = re.compile(
    rf"(?i)\b(?:pictures?|photos?|images?|videos?)\s+of\s+"
    rf"(?:(?:our|my|the|a|an)\s+)?{_PERSON_NAME}\b"
)
PERSON_EMAIL_FROM_RE = re.compile(
    rf"(?i)\b(?:emails?|e-mails?|mail|messages?)\s+from\s+{_PERSON_NAME}\b"
)
PERSON_SAID_RE = re.compile(
    rf"(?i)\bwhat\s+did\s+{_PERSON_NAME}\s+say\b"
)
PERSON_POSSESSIVE_RE = re.compile(r"(?-i:\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s)\b")
SHOW_ME_PERSON_RE = re.compile(
    r"(?i)\bshow\s+me\s+"
    r"(?!pictures?\b|photos?\b|images?\b|videos?\b|emails?\b|mail\b|stills?\b)"
    rf"{_PERSON_NAME}\b"
)

# Places: geographic/locative — never "from <Person>" for email.
PLACE_IN_AT_RE = re.compile(
    r"(?i)\b(?:in|at|near|around|to)\s+"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b"
)
PLACE_TRIP_RE = re.compile(
    r"(?i)\b(?:our|the|a|an|my|your)?\s*"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\s+trip\b"
)
TRIP_TO_RE = re.compile(
    r"(?i)\btrip\s+(?:to|in|around)\s+"
    r"(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b"
)

KNOWN_EVENT_WORDS = (
    "Christmas",
    "Thanksgiving",
    "Hanukkah",
    "Easter",
    "Birthday",
    "Wedding",
    "Graduation",
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
        "happening",
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
        "know",
        "about",
        "relationship",
        "other",
        "meant",
        "then",
        "there",
        "around",
        "was",
        "were",
        "being",
    }
)


@dataclass(frozen=True)
class QueryPlan:
    original_ask: str
    effective_ask: str
    is_followup: bool
    want_photo: bool
    want_communication: bool
    want_calendar: bool
    want_story: bool = False
    want_journal: bool = False
    journal_capture_intent: bool = False
    visual_scope: VisualScope = "none"
    want_visual: bool = False
    want_still: bool = False
    want_video: bool = False
    person_names: tuple[str, ...] = ()
    place_names: tuple[str, ...] = ()
    event_labels: tuple[str, ...] = ()
    trip_labels: tuple[str, ...] = ()
    time_start: str | None = None
    time_end: str | None = None
    inherit_from_context: bool = False
    notes: tuple[str, ...] = ()
    temporal_after: bool = False
    broaden_same_context: bool = False
    # Corrective fields
    requires_clarification: bool = False
    ambiguity_message: str | None = None
    reference_resolved: bool = False
    subject_changed: bool = False
    retrieval_constraints: tuple[str, ...] = ()
    """Opaque constraint tokens actually applied to retrieval (rule H)."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def modalities(self) -> tuple[str, ...]:
        out: list[str] = []
        if self.want_visual or self.want_still or self.want_video:
            out.append("visual")
        if self.want_still:
            out.append("still")
            out.append("photo")
        if self.want_video:
            out.append("video")
        if self.want_communication:
            out.append("communication")
        if self.want_calendar:
            out.append("calendar_event")
        if self.want_story:
            out.append("story")
        if self.want_journal:
            out.append("journal")
        return tuple(out)


def _clean_entity(name: str) -> str | None:
    n = (name or "").strip()
    if not n or n.lower() in _ENTITY_STOP:
        return None
    if len(n) < 2:
        return None
    # Normalize casing for display / Immich name match (owner often types lowercase)
    if n.islower() or n.isupper():
        n = n.title()
    return n


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for i in items:
        k = i.lower()
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def _extract_people(text: str, *, want_email: bool) -> list[str]:
    found: list[str] = []
    patterns = [
        PERSON_WITH_RE,
        PERSON_OF_RE,
        PERSON_POSSESSIVE_RE,
        SHOW_ME_PERSON_RE,
        PERSON_EMAIL_FROM_RE,
        PERSON_SAID_RE,
    ]
    if want_email:
        # "from <Name>" in an email ask is a person, never a place
        patterns.append(
            re.compile(rf"(?i)\bfrom\s+{_PERSON_NAME}\b")
        )
    for rx in patterns:
        for m in rx.finditer(text or ""):
            ent = _clean_entity(m.group(1))
            if ent and ent not in found:
                found.append(ent)
    return found


def _extract_places_and_trips(text: str, *, want_email: bool) -> tuple[list[str], list[str]]:
    places: list[str] = []
    trips: list[str] = []
    q = text or ""

    for m in PLACE_TRIP_RE.finditer(q):
        ent = _clean_entity(m.group(1))
        if ent:
            trips.append(ent)
            places.append(ent)
    for m in TRIP_TO_RE.finditer(q):
        ent = _clean_entity(m.group(1))
        if ent:
            trips.append(ent)
            places.append(ent)
    for m in PLACE_IN_AT_RE.finditer(q):
        ent = _clean_entity(m.group(1))
        # "at Christmas" is an event, not a place
        if ent and ent.lower() in {e.lower() for e in KNOWN_EVENT_WORDS}:
            continue
        if ent:
            places.append(ent)

    # Do NOT treat bare "from X" as place when email intent (person).
    if not want_email:
        # Geographic "from Cascadia" without email/mail cue may be place
        if not re.search(r"(?i)\b(emails?|mail|messages?)\b", q):
            for m in re.finditer(
                r"(?i)\bfrom\s+(?-i:([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b", q
            ):
                ent = _clean_entity(m.group(1))
                if ent:
                    places.append(ent)

    return _dedupe(places), _dedupe(trips)


def _extract_events(text: str) -> list[str]:
    found: list[str] = []
    for hol in KNOWN_EVENT_WORDS:
        if re.search(rf"(?i)\b{re.escape(hol)}\b", text or ""):
            found.append(hol)
    return found


def _extract_years(text: str) -> tuple[str | None, str | None]:
    years = YEAR_RE.findall(text or "")
    if not years:
        return None, None
    if len(years) == 1:
        y = years[0]
        return f"{y}-01-01", f"{y}-12-31"
    return f"{years[0]}-01-01", f"{years[-1]}-12-31"


def _ctx_trips(ctx: AskContext) -> list[str]:
    out: list[str] = []
    for e in ctx.event_labels:
        if e.lower().startswith("trip:"):
            out.append(e.split(":", 1)[1])
        elif e.lower().startswith("trip"):
            out.append(e)
    return out


def _ctx_events_non_trip(ctx: AskContext) -> list[str]:
    return [e for e in ctx.event_labels if not e.lower().startswith("trip:")]


def _resolve_visual_scope(
    q: str,
    *,
    want_email: bool,
    want_cal: bool,
    want_relationship: bool,
    people: list[str],
) -> tuple[VisualScope, list[str]]:
    notes: list[str] = []
    if want_email or want_cal or want_relationship:
        return "none", notes
    video_only = bool(VIDEO_ONLY_RE.search(q))
    still_only = bool(STILL_ONLY_RE.search(q))
    broad_word = bool(BROAD_VISUAL_RE.search(q))
    show_me = bool(SHOW_ME_RE.search(q))
    if video_only and not still_only and not broad_word:
        return "video_only", ["visual_scope=video_only"]
    if video_only and (still_only or broad_word):
        return "broad", ["visual_scope=broad_mixed_wording"]
    if still_only and not broad_word:
        return "still_only", ["visual_scope=still_only"]
    if broad_word:
        return "broad", ["visual_scope=broad"]
    if show_me and people:
        return "broad", ["visual_scope=broad_show_me_person"]
    return "none", notes


def _enforce_typed_slots(
    people: list[str], places: list[str], trips: list[str], events: list[str]
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Rule C: a Person must not occupy Place/Trip/Event slots."""
    notes: list[str] = []
    people_l = {p.lower() for p in people}
    # Remove people names from place/trip
    places2 = [p for p in places if p.lower() not in people_l]
    trips2 = [t for t in trips if t.lower() not in people_l]
    if len(places2) != len(places) or len(trips2) != len(trips):
        notes.append("typed_slots_removed_person_from_place_trip")
    # Events that equal a person name are invalid
    events2 = [e for e in events if e.lower() not in people_l]
    return people, places2, trips2, events2, notes


def plan_ask(ask: str, ctx: AskContext) -> QueryPlan:
    q = (ask or "").strip()
    notes: list[str] = []

    want_email = bool(EMAIL_RE.search(q))
    want_cal = bool(CALENDAR_RE.search(q))
    want_relationship = bool(RELATIONSHIP_RE.search(q))

    # --- Utterance extractions (authoritative for present slots) ---
    u_people = _extract_people(q, want_email=want_email)
    u_places, u_trips = _extract_places_and_trips(q, want_email=want_email)
    u_events = _extract_events(q)
    u_t0, u_t1 = _extract_years(q)

    about_trip = bool(PLACE_TRIP_RE.search(q) or TRIP_TO_RE.search(q) or re.search(r"(?i)\btrip\b", q))
    exploratory = bool(EXPLORATORY_RE.search(q))
    said_about = bool(SAID_ABOUT_RE.search(q))
    # Explicit modality narrowing always wins over exploratory multimodal.
    narrowed_comms = bool(want_email or want_relationship or said_about)
    narrowed_visual = bool(STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q) or BROAD_VISUAL_RE.search(q))

    visual_scope, vnotes = _resolve_visual_scope(
        q,
        want_email=want_email or said_about,
        want_cal=want_cal,
        want_relationship=want_relationship,
        people=u_people,
    )
    notes.extend(vnotes)

    # Bare "tell me about <Subject>" / "know about <Subject>" (not "... trip")
    if exploratory and not u_people and not u_places and not u_trips and not u_events:
        for m in ABOUT_SUBJECT_RE.finditer(q):
            ent = _clean_entity(m.group(1))
            if not ent:
                continue
            if ent.lower() in {e.lower() for e in KNOWN_EVENT_WORDS}:
                u_events.append(ent)
            else:
                # Family-archive default: bare proper noun after about → person slot;
                # Immich text search still receives the token via person_names.
                u_people.append(ent)
            notes.append("exploratory_about_subject")
            break

    want_still = visual_scope in ("broad", "still_only")
    want_video = visual_scope in ("broad", "video_only")
    want_visual = want_still or want_video
    want_photo = want_still

    # Exploratory / know-about: always multimodal across I4-available modalities.
    # Not photo-fallback — stills + email/calendar even when communications hit.
    if (
        exploratory
        and not narrowed_comms
        and not narrowed_visual
        and visual_scope == "none"
        and not SHOW_ME_RE.search(q)
    ):
        want_email = True
        want_cal = True
        visual_scope = "broad"
        want_still = True
        want_video = True
        want_visual = True
        want_photo = True
        notes.append("exploratory_multimodal_i4")

    if said_about and not narrowed_visual:
        want_email = True
        want_cal = True
        visual_scope = "none"
        want_still = False
        want_video = False
        want_visual = False
        want_photo = False
        notes.append("said_about_communication_focus")

    show_me = bool(SHOW_ME_RE.search(q))
    # "show me <person>" (or show me + session person) → broad visual when no
    # explicit media word already set scope (photos→still_only, videos→video_only).
    if (
        show_me
        and visual_scope == "none"
        and not want_email
        and not want_cal
        and not want_relationship
        and not about_trip
        and not exploratory
    ):
        if not u_people and ctx.person_names:
            u_people = list(ctx.person_names)
            notes.append("show_me_inherited_person_for_visual")
        if u_people or ctx.person_names:
            visual_scope = "broad"
            want_still = True
            want_video = True
            want_visual = True
            want_photo = True
            notes.append("show_me_person_forces_broad_visual")

    ref_then = bool(AROUND_THEN_RE.search(q))
    ref_other_trip = bool(OTHER_TRIP_RE.search(q))
    ref_that_trip = bool(THAT_TRIP_RE.search(q))
    ref_there = bool(THERE_RE.search(q))
    temporal_after = bool(AFTER_RE.search(q))
    broaden = bool(ELSE_RE.search(q))

    is_followup = bool(FOLLOWUP_RE.search(q)) or ref_then or ref_other_trip or ref_that_trip or ref_there
    if not is_followup and len(q.split()) <= 10 and not ctx.is_empty():
        if re.search(r"(?i)\b(just|only|those|that|this|after|else|then|there|other)\b", q):
            is_followup = True

    # --- Subject-change / supersede (Rule D) ---
    subject_changed = False
    ctx_trips = _ctx_trips(ctx)
    ctx_events = _ctx_events_non_trip(ctx)
    if u_trips and ctx_trips and not any(t.lower() in {c.lower() for c in ctx_trips} for t in u_trips):
        subject_changed = True
        notes.append("supersede_trip_subject_change")
    if u_places and ctx.place_names and not any(
        p.lower() in {c.lower() for c in ctx.place_names} for p in u_places
    ):
        # New place vs old place
        if not (u_trips and any(p.lower() in {t.lower() for t in u_trips} for p in u_places)):
            # place change often accompanies trip change
            pass
        subject_changed = True
        notes.append("supersede_place_subject_change")
    if u_events and ctx_events and not any(
        e.lower() in {c.lower() for c in ctx_events} for e in u_events
    ):
        subject_changed = True
        notes.append("supersede_event_subject_change")
    if u_trips or (u_places and about_trip):
        # Explicit new trip/place trip ask clears incompatible holiday events
        if ctx_events and not u_events:
            subject_changed = True
            notes.append("supersede_clear_prior_events_for_new_trip")

    # --- Merge slots (Rules A, B, D) ---
    # A: utterance present → use utterance; B: else inherit if followup/missing
    inherit = False
    people = list(u_people)
    places = list(u_places)
    trips = list(u_trips)
    events = list(u_events)
    t0, t1 = u_t0, u_t1

    should_inherit_missing = is_followup or (
        not want_visual
        and not want_email
        and not want_cal
        and not want_relationship
        and not about_trip
        and not ctx.is_empty()
        and not (u_people or u_places or u_trips or u_events)
    )

    if subject_changed:
        # D: do not inherit incompatible place/event/trip from prior subject
        if not people and ctx.person_names:
            people = list(ctx.person_names)
            inherit = True
            notes.append("inherit_person_only_after_subject_change")
        notes.append("rule_D_no_inherit_incompatible_place_event_trip")
    elif should_inherit_missing or is_followup or (show_me and not people and ctx.person_names):
        inherit = True
        notes.append("inherited_missing_slots_only")
        if not people:
            people = list(ctx.person_names)
        if not places and not show_me:
            places = list(ctx.place_names)
        if not trips and not show_me:
            trips = list(ctx_trips)
        if not events and not show_me:
            events = list(ctx_events)
        if t0 is None and not show_me:
            t0 = ctx.time_start
        if t1 is None and not show_me:
            t1 = ctx.time_end
    # show me + partial name: keep context people that contain the uttered token
    if show_me and u_people and ctx.person_names:
        merged = list(u_people)
        for cp in ctx.person_names:
            if any(u.lower() in cp.lower() or cp.lower() in u.lower() for u in u_people):
                if cp not in merged:
                    merged.append(cp)
        people = merged
        notes.append("show_me_merged_context_person_names")

    # Reference resolution (Rule E) — before retrieval
    reference_resolved = False
    requires_clarification = False
    ambiguity_message: str | None = None

    if ref_other_trip:
        # F: need a uniquely identifiable alternate trip
        known = _dedupe(list(ctx_trips) + list(ctx.place_names) + trips)
        if len(known) < 2:
            requires_clarification = True
            ambiguity_message = (
                "Ambiguous reference: “the other trip” cannot be uniquely resolved "
                "from the current session context. Please name the trip or place."
            )
            notes.append("rule_F_other_trip_ambiguous")
        else:
            # Prefer a place/trip not equal to the primary (first) one
            primary = (trips or ctx_trips or places or ctx.place_names or [None])[0]
            alts = [k for k in known if primary is None or k.lower() != str(primary).lower()]
            if not alts:
                requires_clarification = True
                ambiguity_message = (
                    "Ambiguous reference: no alternate trip is available in context. "
                    "Please name the trip you mean."
                )
            else:
                trips = [alts[0]]
                places = [alts[0]]
                reference_resolved = True
                notes.append("rule_E_resolved_other_trip")

    if ref_that_trip and not requires_clarification:
        if trips or ctx_trips or places or ctx.place_names:
            if not trips:
                trips = list(ctx_trips) or list(ctx.place_names)[:1]
            if not places and trips:
                places = list(trips)
            reference_resolved = True
            notes.append("rule_E_resolved_that_trip")
        else:
            requires_clarification = True
            ambiguity_message = (
                "Ambiguous reference: “that trip” has no trip/place in session context."
            )

    if ref_there and not requires_clarification:
        if places or ctx.place_names:
            if not places:
                places = list(ctx.place_names)
            reference_resolved = True
            notes.append("rule_E_resolved_there")
        else:
            requires_clarification = True
            ambiguity_message = (
                "Ambiguous reference: “there” has no place in session context."
            )

    if ref_then and not requires_clarification:
        # Resolve "then" to active time/event/trip/place constraints
        if not (t0 or t1 or events or trips or places or ctx.time_start or ctx.event_labels or ctx.place_names):
            requires_clarification = True
            ambiguity_message = (
                "Ambiguous reference: “then” has no temporal/event/trip context to resolve against."
            )
            notes.append("rule_E_then_unresolved")
        else:
            if not events:
                events = list(ctx_events) if not subject_changed else events
            if not trips:
                trips = list(ctx_trips) if not subject_changed else trips
            if not places:
                places = list(ctx.place_names) if not subject_changed else places
            if t0 is None:
                t0 = ctx.time_start
            if t1 is None:
                t1 = ctx.time_end
            reference_resolved = True
            want_email = True
            want_cal = True
            notes.append("rule_E_resolved_then_to_context")

    people, places, trips, events, type_notes = _enforce_typed_slots(
        people, places, trips, events
    )
    notes.extend(type_notes)

    # Modality inheritance for pure follow-ups without modality cue
    visual_ctx = any(
        m in (ctx.modalities_active or ()) for m in ("visual", "photo", "still", "video")
    )
    if is_followup and not want_visual and not want_email and not want_cal and not about_trip:
        if visual_ctx and not ref_then:
            visual_scope = "broad"
            want_still = True
            want_video = True
            want_visual = True
            want_photo = True
            notes.append("inherited_visual_modality")
        elif "communication" in (ctx.modalities_active or ()) or "calendar_event" in (
            ctx.modalities_active or ()
        ):
            want_email = "communication" in (ctx.modalities_active or ()) or want_email
            want_cal = "calendar_event" in (ctx.modalities_active or ()) or want_cal

    if temporal_after or broaden:
        want_email = True
        want_cal = True
        notes.append("temporal_or_broaden_followup")

    if want_relationship and not want_visual:
        want_email = True
        want_cal = True

    if not want_visual and not want_email and not want_cal and not requires_clarification:
        want_email = True
        want_cal = True
        notes.append("default_comms_calendar")

    # Rule G: retrieval constraints from resolved context
    constraints: list[str] = []
    constraints.extend(people)
    constraints.extend(places)
    constraints.extend(trips)
    constraints.extend(events)
    if t0:
        constraints.append(t0[:4] if len(t0) >= 4 else t0)
    constraints = _dedupe(constraints)

    # Build event_labels for storage: trips as trip:X, events as names
    event_labels: list[str] = list(events)
    for t in trips:
        label = f"trip:{t}"
        if label not in event_labels:
            event_labels.append(label)

    parts = [q]
    if people:
        parts.append("people:" + ",".join(people))
    if places:
        parts.append("places:" + ",".join(places))
    if trips:
        parts.append("trips:" + ",".join(trips))
    if events:
        parts.append("events:" + ",".join(events))
    if t0 or t1:
        parts.append(f"time:{t0 or ''}..{t1 or ''}")
    if constraints:
        parts.append("constraints:" + ",".join(constraints))
    if visual_scope != "none":
        parts.append(f"visual_scope:{visual_scope}")
    effective = " | ".join(parts)

    if want_video and not want_still:
        notes.append("video_intent_no_i4_provider")

    # Story modality (I5): exploratory + default archive asks; not email/photo/video-only or said-about
    want_story = False
    if not requires_clarification:
        if "exploratory_multimodal_i4" in notes or "default_comms_calendar" in notes:
            want_story = True
        if narrowed_comms and EMAIL_RE.search(q) and not exploratory:
            want_story = False
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_story = False
        if said_about:
            want_story = False
        if want_story:
            notes.append("want_story_modality")

    # Journal modality (I5A): capture intent OR retrieval (exploratory / journal ask)
    journal_capture_intent = bool(JOURNAL_INTENT_RE.search(q))
    want_journal = False
    if journal_capture_intent:
        notes.append("journal_capture_intent")
    elif not requires_clarification:
        if JOURNAL_ASK_RE.search(q):
            want_journal = True
        if "exploratory_multimodal_i4" in notes or "default_comms_calendar" in notes:
            want_journal = True
        if narrowed_comms and EMAIL_RE.search(q) and not exploratory:
            want_journal = False
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_journal = False
        if said_about:
            want_journal = False
        if want_journal:
            notes.append("want_journal_modality")

    return QueryPlan(
        original_ask=q,
        effective_ask=effective if not journal_capture_intent else "journal_capture",
        is_followup=is_followup,
        want_photo=want_photo and not journal_capture_intent,
        want_communication=want_email and not requires_clarification and not journal_capture_intent,
        want_calendar=want_cal and not requires_clarification and not journal_capture_intent,
        want_story=want_story and not journal_capture_intent,
        want_journal=want_journal and not journal_capture_intent,
        journal_capture_intent=journal_capture_intent,
        visual_scope=visual_scope if not requires_clarification and not journal_capture_intent else "none",
        want_visual=want_visual and not requires_clarification and not journal_capture_intent,
        want_still=want_still and not requires_clarification and not journal_capture_intent,
        want_video=want_video and not requires_clarification and not journal_capture_intent,
        person_names=tuple(people),
        place_names=tuple(places),
        event_labels=tuple(event_labels),
        trip_labels=tuple(trips),
        time_start=t0,
        time_end=t1,
        inherit_from_context=inherit,
        notes=tuple(notes),
        temporal_after=temporal_after or ref_then,
        broaden_same_context=broaden,
        requires_clarification=requires_clarification,
        ambiguity_message=ambiguity_message,
        reference_resolved=reference_resolved,
        subject_changed=subject_changed,
        retrieval_constraints=tuple(constraints),
    )
