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
from memorybox.planner.temporal import (
    ANNIVERSARY_RE,
    BIRTHDAY_RE,
    TemporalParse,
    holiday_window,
    parse_temporal,
    season_window,
    HOLIDAY_LABELS,
)

VisualScope = Literal["none", "broad", "still_only", "video_only"]
MbqlAct = Literal["find", "refine", "navigate", "clarify"]
MbqlProvenance = Literal["deterministic", "model_fill", "mixed"]
OutputMode = Literal["show", "play", "tell"]

STILL_ONLY_RE = re.compile(r"(?i)\b(photos?|stills?)\b")
STORY_ASK_RE = re.compile(r"(?i)\bstor(?:y|ies|ied|iest)\b")
_TOPIC_STOP = frozenset(
    {
        "what",
        "you",
        "know",
        "about",
        "tell",
        "have",
        "from",
        "our",
        "the",
        "and",
        "show",
        "me",
        "my",
        "please",
        "some",
        "any",
        "all",
        "that",
        "this",
        "with",
        "for",
        "email",
        "emails",
        "photos",
        "photo",
        "pictures",
        "story",
        "stories",
        "storiest",
        "dad",
        "daddy",
        "father",
        "mom",
        "mum",
        "mother",
        "grandma",
        "grandpa",
        "grandmother",
        "grandfather",
    }
)


def leftover_topic_tokens(
    q: str,
    people: list[str] | tuple[str, ...] | None = None,
    places: list[str] | tuple[str, ...] | None = None,
    trips: list[str] | tuple[str, ...] | None = None,
    events: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Ask words that are not person/place names or stopwords (e.g. rabbits)."""
    named: set[str] = set()
    for blob in list(people or []) + list(places or []) + list(trips or []) + list(events or []):
        for w in re.findall(r"[A-Za-z][A-Za-z']{2,}", str(blob or "")):
            named.add(w.lower())
    out: list[str] = []
    for w in re.findall(r"[A-Za-z][A-Za-z']{2,}", q or ""):
        lw = w.lower()
        if lw in _TOPIC_STOP or lw in named:
            continue
        if lw not in out:
            out.append(lw)
    return out
VIDEO_ONLY_RE = re.compile(
    r"(?i)\b(videos?|video\s+clips?|clips?|footage|home\s*movies?)\b"
)
BROAD_VISUAL_RE = re.compile(
    r"(?i)\b(pictures?|images?|snapshots?|gallery|album|visuals?)\b"
)
SHOW_ME_RE = re.compile(r"(?i)\bshow\s+me\b")
EVERYTHING_ABOUT_RE = re.compile(
    r"(?i)\b(?:"
    r"show\s+me\s+everything(?:\s+(?:that\s+)?i\s+have)?\s+about|"
    r"everything\s+(?:that\s+)?(?:i\s+have\s+)?about|"
    r"what\s+do\s+i\s+have\s+about|"
    r"find\s+everything\s+about"
    r")\s+(.+)$"
)
EXPLORATORY_RE = re.compile(
    r"(?i)\b(?:"
    r"what\s+do\s+(?:you|i|we)\s+know\s+about|"
    r"tell\s+me\s+about|"
    r"what\s+do\s+(?:i|we)\s+have\s+(?:about|from|on)"
    r")\b"
)
TELL_OUTPUT_RE = re.compile(
    r"(?i)\b(?:"
    r"tell\s+me\s+about|"
    r"what\s+do\s+you\s+know|"
    r"summarize|"
    r"what\s+happened|"
    r"what\s+was\b[\w\s,'’-]{0,40}\blike\b|"
    r"what\s+were\b[\w\s,'’-]{0,40}\blike\b|"
    r"describe\b[\w\s,'’-]{0,60}\bfrom\s+what\s+we\s+have|"
    r"write\s+a\s+narrative|"
    r"write\s+a\s+story|"
    r"narrate|"
    r"narrative\s+about"
    r")\b"
)
PLAY_OUTPUT_RE = re.compile(
    r"(?i)\b(?:play|watch)\b[\w\s,'’-]{0,40}\b(?:video|clip|moment|footage|recording)\b|"
    r"\bplay\s+(?:that|this)\b"
)
SAID_ABOUT_RE = re.compile(
    r"(?i)\b(?:"
    r"what\s+did\b[\w\s,'-]{0,40}\bsay\b|"
    r"\bsaid\s+about\b|"
    r"\btell\s+me\s+what\b[\w\s,'-]{0,40}\bsaid\b"
    r")\b"
)
SAYING_PHRASE_RE = re.compile(
    r"(?i)\bsaying\s+[“\"']([^“\"']+)[”\"']|\bsaying\s+(.+)$"
)
TALKING_ABOUT_RE = re.compile(r"(?i)\btalking\s+about\s+(.+)$")
TALKING_RE = re.compile(r"(?i)\b(?:show\s+me\s+)?(?:everything\s+)?[\w'’.-]+\s+talking\b|\btalking\b")
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
SMS_ASK_RE = re.compile(
    r"(?i)\b("
    r"sms|imessage|i-?message|mms|rcs|"
    r"text(?:s|ed|ing)?(?:\s+messages?)?|"
    r"(?:text\s+)?messages?\s+(?:from|to|between|with)|"
    r"from\s+and\s+to|to\s+and\s+from|"
    r"last\s+\d+\s+(?:text\s+)?messages?|"
    r"how\s+many\s+(?:text\s+)?messages?"
    r")\b"
)
SMS_PERSON_CONVERSATION_RE = re.compile(
    r"(?i)\b("
    r"from\s+and\s+to|to\s+and\s+from|"
    r"between\s+(?:me|myself|i)|"
    r"(?:me|myself)\s+and|"
    r"last\s+\d+\s+(?:text\s+)?messages?|"
    r"how\s+many\s+(?:text\s+)?messages?|"
    r"did\s+.+\s+send|"
    r"send(?:t)?\s+to\s+me|"
    r"hear(?:t)?\s+emojis?|"
    r"emojis?\s+did|"
    r"with\s+attachments?"
    r")\b"
)
JOURNAL_INTENT_RE = re.compile(
    r"(?i)^\s*(?:i\s+(?:want|need)\s+to\s+journal|let\s+me\s+journal|"
    r"start\s+(?:a\s+)?journal|journal\s+now|open\s+journal|^journal)\s*[.!]?\s*$"
)
JOURNAL_ASK_RE = re.compile(
    r"(?i)\b(journals?|journal\s+entr(?:y|ies)|my\s+journal|what\s+did\s+i\s+journal)\b"
)
ARTIFACT_ASK_RE = re.compile(
    r"(?i)\b("
    r"artifacts?|keepsakes?|heirloom|heirlooms|"
    r"pocket\s*watch(?:es)?|recipe\s*cards?|clippings?|"
    r"belong(?:ed|s)?\s+to"
    r")\b"
)
GUIDED_CAPTURE_ASK_RE = re.compile(
    r"(?i)\b("
    r"guided\s+capture|interview\s+campaign|campaign\s+response|"
    r"what\s+did\s+\w+\s+say|said\s+about"
    r")\b"
)
CALENDAR_RE = re.compile(
    r"(?i)\b(calendar|appointment|schedule|event|meeting|ics)\b"
)
# Kinship / I6 only. SMS/text "between me and <person>" is not a relationship ask.
RELATIONSHIP_RE = re.compile(
    r"(?i)\brelationship\b|\bkinship\b|\bhow\s+(?:are|is)\s+.+\s+related\b|\brelated\s+to\b"
)
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
# Second token must not be a preposition / season / holiday ("Show me Alex in 2021").
_PERSON_NAME_STOP2 = (
    r"in|at|on|near|around|during|from|with|for|to|and|or|of|the|a|an|"
    r"only|just|through|thru|"
    r"last|first|next|recent|past|myself|my|how|many|all|"
    r"attachments?|messages?|texts?|emails?|"
    r"summer|winter|spring|fall|autumn|"
    r"christmas|xmas|easter|thanksgiving|halloween|birthday|birthdays|bday|bdays|anniversary|anniversaries|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"nye|nyd|juneteenth|memorial|labor|presidents|columbus|veterans|valentine|mlk"
)
_PERSON_NAME = (
    rf"([A-Za-z][A-Za-z'’-]*"
    rf"(?:\s+(?!{_PERSON_NAME_STOP2}\b)[A-Za-z][A-Za-z'’-]*)?)"
)
PERSON_WITH_RE = re.compile(
    rf"(?i)\b(?:with|featuring|including)\s+{_PERSON_NAME}\b"
)
SMS_PERSON_AND_I_RE = re.compile(
    rf"(?i)\b(?:(?:how\s+many\s+times\s+)?did\s+)?{_PERSON_NAME}\s+and\s+I\b"
)
PERSON_OF_RE = re.compile(
    rf"(?i)\b(?:pictures?|photos?|images?|videos?)\s+of\s+"
    rf"(?:(?:our|my|the|a|an)\s+)?{_PERSON_NAME}\b"
)
# "pictures of Tom Will and Matt Will" — same AND as "with"
PICTURES_OF_AND_PEOPLE_RE = re.compile(
    rf"(?i)\b(?:pictures?|photos?|images?|videos?)\s+of\s+"
    rf"(?:(?:our|my|the|a|an)\s+)?{_PERSON_NAME}\s+and\s+"
    rf"(?:(?:our|my|the|a|an)\s+)?{_PERSON_NAME}\b"
)
PERSON_EMAIL_FROM_RE = re.compile(
    rf"(?i)\b(?:emails?|e-mails?|mail|messages?)\s+from\s+(?!and\b){_PERSON_NAME}\b"
)
PERSON_SAID_RE = re.compile(
    rf"(?i)\bwhat\s+did\s+{_PERSON_NAME}\s+say\b"
)
SMS_FROM_AND_TO_RE = re.compile(
    rf"(?i)\b(?:from\s+and\s+to|to\s+and\s+from)\s+{_PERSON_NAME}\b"
)
SMS_BETWEEN_ME_RE = re.compile(
    rf"(?i)\bbetween\s+(?:me|myself|i)\s+and\s+{_PERSON_NAME}\b"
    rf"|\bbetween\s+{_PERSON_NAME}\s+and\s+(?:me|myself|i)\b"
)
SMS_DID_SEND_RE = re.compile(
    rf"(?i)\b(?:did|has|have)\s+{_PERSON_NAME}\s+send"
)
EMAIL_I_EMAIL_PERSON_RE = re.compile(
    rf"(?i)\b(?:(?:how\s+many\s+times\s+)?did\s+i\s+e-?mail|i\s+e-?mailed?|e-?mails?\s+to)\s+{_PERSON_NAME}\b"
)
EMAIL_PERSON_RESPOND_RE = re.compile(
    rf"(?i)\bdid\s+{_PERSON_NAME}\s+respond"
)
SMS_NAME_TEXTS_RE = re.compile(
    rf"(?i)\b(?!how\b|all\b|my\b|the\b|last\b|show\b|write\b|did\b)"
    rf"{_PERSON_NAME}\s+(?:text|sms|imessage)(?:s|ed|ing)?\b"
)
PERSON_POSSESSIVE_RE = re.compile(r"(?-i:\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s)\b")
SHOW_ME_PERSON_RE = re.compile(
    r"(?i)\bshow\s+me\s+"
    r"(?!pictures?\b|photos?\b|images?\b|videos?\b|emails?\b|mail\b|stills?\b|"
    r"texts?\b|sms\b|imessage\b|messages?\b|all\b|"
    r"stor(?:y|ies|ied|iest)\b|artifacts?\b|journals?\b|"
    r"everything\b|what\b|"
    r"the\b|last\b|first\b|next\b|recent\b|how\b|write\b|attachments?\b)"
    rf"{_PERSON_NAME}\b"
)
# "show me Tom and Sue Will at Christmas"
SHOW_ME_AND_PEOPLE_RE = re.compile(
    r"(?i)\bshow\s+me\s+"
    rf"{_PERSON_NAME}\s+and\s+{_PERSON_NAME}\b"
)
# Bare "Pat Lee and Oregon" / "tell me about Pat Lee and Oregon"
PERSON_AND_PERSON_RE = re.compile(
    rf"(?i)\b{_PERSON_NAME}\s+and\s+{_PERSON_NAME}\b"
)
# "Show Tom Will" / "Show Eugene" — owners often omit "me"; same person visual intent
SHOW_PERSON_RE = re.compile(
    r"(?i)\bshow\s+"
    r"(?!me\b|myself\b|pictures?\b|photos?\b|images?\b|videos?\b|emails?\b|mail\b|stills?\b|"
    r"texts?\b|sms\b|imessage\b|messages?\b|"
    r"stor(?:y|ies|ied|iest)\b|artifacts?\b|journals?\b|"
    r"everything\b|map\b|gallery\b|undated\b)"
    rf"{_PERSON_NAME}\b"
)
# "Tom Will 2025" / "Tom Will in Alaska" / "Tom Will summer 2025" / "Tom Will Easter 2022"
# Also "Tom Will 4th of July 2024" (lookahead must see 4th/fourth, not only "july").
PERSON_BARE_LEADING_RE = re.compile(
    rf"(?i)^\s*{_PERSON_NAME}\s+"
    rf"(?=(?:(?:19|20)\d{{2}})|in\s+|at\s+|near\s+|around\s+|during\s+|"
    rf"summer\b|fall\b|autumn\b|winter\b|spring\b|"
    rf"christmas\b|easter\b|thanksgiving\b|halloween\b|"
    rf"memorial\b|labor\b|independence\b|july\b|"
    rf"4th\b|fourth\b|nye\b|nyd\b|"
    rf"juneteenth\b|mlk\b|presidents?\b|columbus\b|veterans?\b|"
    rf"valentine\b|mother'?s?\b|father'?s?\b|"
    rf"birthday\b|birthdays\b|bday\b|bdays\b|anniversary\b|anniversaries\b|"
    rf"new\s+year)"
)
# Bare leading person must not swallow seasons / holidays as names ("summer 2024").
_PERSON_BARE_BLOCKED = frozenset(
    {
        "spring",
        "summer",
        "fall",
        "autumn",
        "winter",
        "christmas",
        "easter",
        "thanksgiving",
        "halloween",
        "memorial",
        "labor",
        "independence",
        "july",
        "nye",
        "nyd",
        "xmas",
        "juneteenth",
        "mlk",
        "presidents",
        "president",
        "columbus",
        "veterans",
        "veteran",
        "valentine",
        "valentines",
        "mother",
        "mothers",
        "father",
        "fathers",
        "birthday",
        "birthdays",
        "bday",
        "bdays",
        "anniversary",
        "anniversaries",
        "during",
        "in",
        "at",
        "near",
        "around",
    }
)

# Places: geographic/locative — never "from <Person>" for email.
# Capture is case-insensitive: owners type "in oregon", not only "in Oregon".
_PLACE_NAME = r"([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*)?)"
PLACE_IN_AT_RE = re.compile(
    rf"(?i)\b(?:in|at|near|around|to)\s+{_PLACE_NAME}\b"
)
PLACE_TRIP_RE = re.compile(
    rf"(?i)\b(?:our|the|a|an|my|your)?\s*{_PLACE_NAME}\s+trip\b"
)
TRIP_TO_RE = re.compile(
    rf"(?i)\btrip\s+(?:to|in|around)\s+{_PLACE_NAME}\b"
)
# "Pat Lee and Oregon" — second slot is a place, not a Person named Oregon.
GEO_PLACE_WORDS = frozenset(
    {
        "alabama",
        "alaska",
        "arizona",
        "arkansas",
        "california",
        "colorado",
        "connecticut",
        "delaware",
        "florida",
        "hawaii",
        "idaho",
        "illinois",
        "indiana",
        "iowa",
        "kansas",
        "kentucky",
        "louisiana",
        "maine",
        "maryland",
        "massachusetts",
        "michigan",
        "minnesota",
        "mississippi",
        "missouri",
        "montana",
        "nebraska",
        "nevada",
        "ohio",
        "oklahoma",
        "oregon",
        "pennsylvania",
        "tennessee",
        "texas",
        "utah",
        "vermont",
        "virginia",
        "wisconsin",
        "wyoming",
        "new york",
        "new jersey",
        "new mexico",
        "new hampshire",
        "north carolina",
        "south carolina",
        "north dakota",
        "south dakota",
        "rhode island",
        "west virginia",
        "washington dc",
        "washington d.c.",
        "district of columbia",
    }
)

KNOWN_EVENT_WORDS = (
    "Christmas",
    "Christmas Eve",
    "Thanksgiving",
    "Hanukkah",
    "Easter",
    "Memorial Day",
    "Labor Day",
    "Independence Day",
    "July 4",
    "Juneteenth",
    "MLK Day",
    "Presidents' Day",
    "Presidents Day",
    "Columbus Day",
    "Veterans Day",
    "New Year's Day",
    "New Year's Eve",
    "Halloween",
    "Valentine's Day",
    "Mother's Day",
    "Father's Day",
    "NYE",
    "NYD",
    "Birthday",
    "Anniversary",
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
        "and",
        "or",
        "how",
        "many",
        "all",
        "i",
        "attachments",
        "attachment",
        "messages",
        "message",
        "texts",
        "narrative",
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
        "story",
        "stories",
        "storiest",
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
    want_artifact: bool = False
    want_guided_capture: bool = False
    journal_capture_intent: bool = False
    visual_scope: VisualScope = "none"
    want_visual: bool = False
    want_still: bool = False
    want_video: bool = False
    want_spoken: bool = False
    spoken_phrase: str | None = None
    spoken_about: str | None = None
    person_names: tuple[str, ...] = ()
    person_ids: tuple[str, ...] = ()
    """MB Person ids from relational resolve (I9A) — preferred over name lookup."""
    place_names: tuple[str, ...] = ()
    event_labels: tuple[str, ...] = ()
    trip_labels: tuple[str, ...] = ()
    time_start: str | None = None
    time_end: str | None = None
    # Inclusive ISO date pairs for non-contiguous periods (recurring holidays).
    temporal_windows: tuple[tuple[str, str], ...] = ()
    temporal_label: str | None = None
    # birthday | anniversary — windows filled from MB People when facts exist
    life_event_kind: str | None = None
    life_event_years: tuple[int, ...] = ()
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
    # I9A profile-backed intents (who / birth / anniversary) — set by orchestrator
    profile_intent: str | None = None
    profile_answer: dict | None = None
    # MBQL-001 — same record, extra compile fields (defaults keep I4–I7 callers valid)
    act: MbqlAct = "find"
    compile_provenance: MbqlProvenance = "deterministic"
    refine_verb: str | None = None
    navigate_target: str | None = None
    gallery_show_sms: bool | None = None
    gallery_show_email: bool | None = None
    gallery_show_calendar: bool | None = None
    attachments_only: bool | None = None
    memory_presentation: bool | None = None
    want_cross_source: bool = False
    theme_labels: tuple[str, ...] = ()
    output_mode: OutputMode = "show"
    semantic_constraints: tuple[dict[str, Any], ...] = ()

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
        if self.want_spoken:
            out.append("spoken")
        if self.want_communication:
            out.append("communication")
        if self.want_calendar:
            out.append("calendar_event")
        if self.want_story:
            out.append("story")
        if self.want_journal:
            out.append("journal")
        if self.want_artifact:
            out.append("artifact")
        if self.want_guided_capture:
            out.append("guided_capture")
        if self.want_cross_source:
            out.append("cross_source")
        return tuple(out)


def _clean_entity(name: str) -> str | None:
    n = (name or "").strip()
    if not n or n.lower() in _ENTITY_STOP:
        return None
    tokens = [t for t in re.split(r"\s+", n.lower()) if t]
    if tokens and all(t in _ENTITY_STOP for t in tokens):
        return None
    if len(n) < 2:
        return None
    # Normalize casing for display / Immich name match (owner often types lowercase)
    if n.islower() or n.isupper():
        n = n.title()
    return n


def compile_output_mode(
    q: str,
    *,
    said_about: bool = False,
    want_spoken: bool = False,
    want_cross_source: bool = False,
) -> OutputMode:
    """SHOW vs PLAY vs TELL. Sibling of MBQL act — do not overload find/refine."""
    if said_about:
        return "show"
    if TELL_OUTPUT_RE.search(q or ""):
        return "tell"
    if PLAY_OUTPUT_RE.search(q or ""):
        return "play"
    # I10 everything-about sets want_spoken for retrieve; that is not PLAY.
    if want_spoken and not want_cross_source:
        return "play"
    return "show"


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for i in items:
        k = i.lower()
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def _theme_from_about(
    about: str,
    *,
    people: list[str],
    places: list[str],
    trips: list[str],
    events: list[str],
) -> tuple[list[str], list[str]]:
    """Possessive person + leftover theme tokens from an everything-about clause."""
    extra_people: list[str] = []
    text = (about or "").strip().strip(".,")
    poss = re.match(r"(?i)^([A-Za-z][A-Za-z'’.-]*?)(?:'s|’s)\s+(.+)$", text)
    if poss:
        who = _clean_entity(poss.group(1))
        rest = poss.group(2)
        if who and who.lower() not in {p.lower() for p in people}:
            extra_people.append(who)
        text = rest
    for name in list(people) + extra_people + list(places) + list(trips) + list(events):
        if not name:
            continue
        text = re.sub(rf"(?i)\b{re.escape(name)}(?:'s|’s)?\b", " ", text)
    text = re.sub(
        r"(?i)\b(the|a|an|our|my|his|her|their|and|or|trip|story|stories|"
        r"birthdays?|b[\-\s]?days?|bdays?|anniversar(?:y|ies))\b",
        " ",
        text,
    )
    theme = " ".join(text.split()).strip(" .")
    themes = [theme] if theme and len(theme) >= 3 else []
    return extra_people, themes


def _extract_people(text: str, *, want_email: bool) -> list[str]:
    # Relational kinship words are resolved via Profile/Relationship service (I9A),
    # never treated as display names ("mother" ≠ a Person named Mother).
    kinship_stop = {
        "father",
        "dad",
        "mother",
        "mom",
        "son",
        "daughter",
        "child",
        "parent",
        "grandfather",
        "grandmother",
        "grandparent",
        "grandpa",
        "grandma",
        "nana",
        "grammy",
        "gram",
        "grandson",
        "granddaughter",
        "grandchild",
        "uncle",
        "aunt",
        "spouse",
        "partner",
        "sibling",
        "brother",
        "sister",
        "me",
        "myself",
    }
    found: list[str] = []
    patterns = [
        PICTURES_OF_AND_PEOPLE_RE,
        SHOW_ME_AND_PEOPLE_RE,
        PERSON_AND_PERSON_RE,
        PERSON_WITH_RE,
        PERSON_OF_RE,
        PERSON_POSSESSIVE_RE,
        SHOW_ME_PERSON_RE,
        SHOW_PERSON_RE,
        PERSON_BARE_LEADING_RE,
        PERSON_EMAIL_FROM_RE,
        PERSON_SAID_RE,
        SMS_PERSON_AND_I_RE,
        SMS_FROM_AND_TO_RE,
        SMS_BETWEEN_ME_RE,
        SMS_DID_SEND_RE,
        SMS_NAME_TEXTS_RE,
        EMAIL_I_EMAIL_PERSON_RE,
        EMAIL_PERSON_RESPOND_RE,
    ]
    if want_email:
        # "from <Name>" in an email ask is a person, never a place
        patterns.append(
            re.compile(rf"(?i)\bfrom\s+(?!and\b){_PERSON_NAME}\b")
        )
    for rx in patterns:
        for m in rx.finditer(text or ""):
            raws = [g for g in m.groups() if g and str(g).strip()]
            for raw_name in raws:
                ent = _clean_entity(raw_name or "")
                if not ent:
                    continue
                # "my dad" / "our mother" are kinship, not display names
                lowered = ent.lower()
                role = lowered
                for prefix in ("my ", "our ", "the "):
                    if lowered.startswith(prefix):
                        role = lowered[len(prefix) :].strip()
                        break
                if role in kinship_stop or lowered in kinship_stop:
                    continue
                # Do not treat season/holiday tokens as Person via bare-leading pattern.
                if lowered in _PERSON_BARE_BLOCKED or role in _PERSON_BARE_BLOCKED:
                    continue
                if ent not in found:
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
        raw = m.group(0) or ""
        # "email to Alex" is a person, not Place Alex
        if want_email and re.match(r"(?i)to\s+", raw):
            continue
        ent = _clean_entity(m.group(1))
        # "at Christmas" is an event, not a place
        if ent and ent.lower() in {e.lower() for e in KNOWN_EVENT_WORDS}:
            continue
        if ent:
            places.append(ent)

    # Do NOT treat bare "from X" as place when email/SMS intent (person).
    if not want_email:
        # Geographic "from Cascadia" without email/mail/SMS cue may be place
        if not re.search(r"(?i)\b(emails?|mail|messages?|sms|texts?)\b", q):
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
    want_sms: bool = False,
) -> tuple[VisualScope, list[str]]:
    notes: list[str] = []
    if want_email or want_sms or want_cal or want_relationship:
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
    if bool(SHOW_PERSON_RE.search(q)) and people:
        return "broad", ["visual_scope=broad_show_person"]
    return "none", notes


def _person_and_geo_place(
    people: list[str], places: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Person + geo token: a US state is a Place, not a second Person.

    Only when the first name is First Last (Pat Lee / Alex Reed). Bare
    "Alex and Georgia" stays two people — Georgia is also a given name.
    """
    notes: list[str] = []
    if len(people) < 2 or len((people[0] or "").split()) < 2:
        return people, places, notes
    kept = [people[0]]
    extra_places: list[str] = []
    for p in people[1:]:
        if (p or "").strip().lower() in GEO_PLACE_WORDS:
            extra_places.append(p)
        else:
            kept.append(p)
    if extra_places:
        notes.append("typed_slots_person_and_place")
        places = _dedupe(list(places) + extra_places)
    return kept, places, notes


def _enforce_typed_slots(
    people: list[str], places: list[str], trips: list[str], events: list[str]
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Rule C: a Person must not occupy Place/Trip/Event slots."""
    notes: list[str] = []
    people, places, geo_notes = _person_and_geo_place(people, places)
    notes.extend(geo_notes)
    people_l = {p.lower() for p in people}
    # Remove people names from place/trip
    places2 = [p for p in places if p.lower() not in people_l]
    trips2 = [t for t in trips if t.lower() not in people_l]
    if len(places2) != len(places) or len(trips2) != len(trips):
        notes.append("typed_slots_removed_person_from_place_trip")
    # Events that equal a person name are invalid
    events2 = [e for e in events if e.lower() not in people_l]
    return people, places2, trips2, events2, notes



def _final_windows(temporal, t0, t1):
    """Prefer explicit multi-windows; else single contiguous range from t0/t1."""
    if temporal.windows and temporal.time_start == t0 and temporal.time_end == t1:
        return tuple(temporal.windows)
    if t0 and t1:
        return ((t0, t1),)
    return ()

def plan_ask(ask: str, ctx: AskContext) -> QueryPlan:
    q = (ask or "").strip()
    notes: list[str] = []

    want_email = bool(EMAIL_RE.search(q))
    want_sms = bool(SMS_ASK_RE.search(q))
    want_cal = bool(CALENDAR_RE.search(q))

    # --- Utterance extractions (authoritative for present slots) ---
    u_people = _extract_people(q, want_email=want_email or want_sms)
    if not want_sms and u_people and SMS_PERSON_CONVERSATION_RE.search(q):
        if not (
            re.search(r"(?i)\b(emails?|e-mails?|gmail|inbox|imap)\b", q)
            and not re.search(r"(?i)\b(text|sms|imessage|mms)\b", q)
        ):
            want_sms = True
            notes.append("sms_person_conversation")
    # SMS/text conversation "between me and X" is not I6 kinship.
    want_relationship = bool(RELATIONSHIP_RE.search(q)) and not want_sms
    u_places, u_trips = _extract_places_and_trips(q, want_email=want_email or want_sms)
    u_people, u_places, geo_notes = _person_and_geo_place(u_people, u_places)
    notes.extend(geo_notes)
    u_events = _extract_events(q)
    temporal = parse_temporal(q)
    u_t0, u_t1 = temporal.time_start, temporal.time_end
    if temporal.notes:
        notes.extend(temporal.notes)
    # Prefer holiday/season event labels from temporal when present
    if temporal.holiday:
        hol_label = temporal.label or temporal.holiday
        # Keep short holiday name in events for chips; full label via temporal_label
        short = HOLIDAY_LABELS.get(temporal.holiday, temporal.holiday)
        if short not in u_events:
            u_events.append(short)
    if temporal.life_event_kind == "birthday" and "Birthday" not in u_events:
        u_events.append("Birthday")
    if temporal.life_event_kind == "anniversary" and "Anniversary" not in u_events:
        u_events.append("Anniversary")

    about_trip = bool(PLACE_TRIP_RE.search(q) or TRIP_TO_RE.search(q) or re.search(r"(?i)\btrip\b", q))
    exploratory = bool(EXPLORATORY_RE.search(q))
    spoken_phrase = None
    spoken_about = None
    want_spoken = False
    sm = SAYING_PHRASE_RE.search(q)
    if sm:
        want_spoken = True
        spoken_phrase = (sm.group(1) or sm.group(2) or "").strip().strip(".,")
        notes.append("want_spoken_phrase")
    am = TALKING_ABOUT_RE.search(q)
    if am:
        want_spoken = True
        spoken_about = (am.group(1) or "").strip().strip(".,")
        notes.append("want_spoken_about")
    elif TALKING_RE.search(q):
        want_spoken = True
        notes.append("want_spoken_talking")
    said_about = bool(SAID_ABOUT_RE.search(q)) and not want_spoken
    everything_m = EVERYTHING_ABOUT_RE.search(q)
    want_cross_source = bool(everything_m) and not want_spoken
    theme_labels: list[str] = []
    if want_cross_source:
        extra_p, theme_labels = _theme_from_about(
            everything_m.group(1) if everything_m else "",
            people=u_people,
            places=u_places,
            trips=u_trips,
            events=u_events,
        )
        for p in extra_p:
            if p.lower() not in {x.lower() for x in u_people}:
                u_people.append(p)
        notes.append("p2_i10_cross_source")
        if theme_labels:
            notes.append("theme=" + ",".join(theme_labels))
    # Explicit modality narrowing always wins over exploratory multimodal.
    # Everything-about is an explicit all-source ask, not a narrowing.
    narrowed_comms = bool(want_email or want_sms or want_relationship or said_about)
    narrowed_visual = bool(STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q) or BROAD_VISUAL_RE.search(q))

    visual_scope, vnotes = _resolve_visual_scope(
        q,
        want_email=want_email or said_about,
        want_cal=want_cal,
        want_relationship=want_relationship,
        people=u_people,
        want_sms=want_sms,
    )
    notes.extend(vnotes)
    # Person + time/place/holiday compose → shared visual explore (Gallery path).
    if (
        visual_scope == "none"
        and not narrowed_comms
        and u_people
        and (
            u_t0
            or u_t1
            or u_places
            or u_trips
            or temporal.holiday
            or temporal.season
            or temporal.windows
            or temporal.life_event_kind
        )
    ):
        visual_scope = "broad"
        notes.append("visual_scope=broad_person_compose")

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

    if (
        TELL_OUTPUT_RE.search(q)
        and not said_about
        and not narrowed_comms
        and not narrowed_visual
        and not SHOW_ME_RE.search(q)
    ):
        want_email = True
        want_sms = True
        want_cal = True
        if visual_scope == "none":
            visual_scope = "broad"
            want_still = True
            want_video = True
            want_visual = True
            want_photo = True
        notes.append("tell_multimodal_i11")

    if want_spoken and not want_cross_source:
        visual_scope = "video_only"
        want_still = False
        want_video = True
        want_visual = True
        want_photo = False
        notes.append("want_spoken_modality")

    if want_cross_source:
        want_email = True
        want_sms = True
        want_cal = True
        visual_scope = "broad"
        want_still = True
        want_video = True
        want_visual = True
        want_photo = True
        want_spoken = True
        notes.append("p2_i10_all_modalities")

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
    show_person = bool(SHOW_PERSON_RE.search(q)) and bool(u_people)
    # Owner self: "show me myself" / "show me me" — force broad visual and do
    # NOT inherit prior session person (dad/Eugene must not stick).
    self_show = bool(
        re.search(
            r"(?i)\bshow\s+me\s+(?:myself|me)\b|\bshow\s+myself\b|"
            r"\b(?:pictures?|photos?|images?|videos?)\s+of\s+(?:me|myself)\b",
            q,
        )
    )
    if self_show and visual_scope == "none" and not want_relationship and not about_trip:
        visual_scope = "broad"
        want_still = True
        want_video = True
        want_visual = True
        want_photo = True
        notes.append("show_me_self_forces_broad_visual")
    # "show me <person>" / "show <person>" → broad visual
    elif (
        (show_me or show_person)
        and visual_scope == "none"
        and not want_email
        and not want_sms
        and not want_cal
        and not want_relationship
        and not about_trip
        and not exploratory
    ):
        if not u_people and ctx.person_names:
            u_people = list(ctx.person_names)
            notes.append("show_me_inherited_person_for_visual")
        # Kinship ("dad"/"my father") is stripped from u_people; still force
        # broad visual so I9A relational resolve can retrieve Immich/HVRT.
        kinship_show = bool(
            re.search(
                r"(?i)\b(?:my\s+)?(father|dad|mother|mom|son|daughter|"
                r"grandfather|grandmother|grandparent|grandpa|grandma|nana|grammy|gram|"
                r"uncle|aunt|spouse|partner|"
                r"brother|sister|parent|child|grandson|granddaughter|grandchild)\b",
                q,
            )
        )
        if u_people or ctx.person_names or kinship_show:
            visual_scope = "broad"
            want_still = True
            want_video = True
            want_visual = True
            want_photo = True
            notes.append(
                "show_me_kinship_forces_broad_visual"
                if kinship_show and not (u_people or ctx.person_names)
                else (
                    "show_person_forces_broad_visual"
                    if show_person and not show_me
                    else "show_me_person_forces_broad_visual"
                )
            )

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
    if u_people and ctx.person_names:
        uttered = {p.lower() for p in u_people}
        prior = {p.lower() for p in ctx.person_names}
        if uttered and prior and uttered.isdisjoint(prior):
            # "Show me Alex Reed" after a Sue/year/text session must not
            # keep that person's time/place (FlightSim: 1 leftover video).
            if not any(
                u in p or p in u for u in uttered for p in prior
            ):
                subject_changed = True
                notes.append("supersede_person_subject_change")

    # Explicit clear / remove / reset refinements (mutate shared state; do not re-inherit cleared slots).
    clear_date = bool(re.search(r"(?i)^\s*clear\s+(?:date|time|dates|timeline)\b", q))
    clear_place = bool(
        re.search(r"(?i)^\s*clear\s+(?:location|place|places|map(?:\s+selection)?)\b", q)
    )
    reset_all = bool(re.search(r"(?i)^\s*reset\.?\s*$", q))
    remove_place_m = re.match(
        r"(?i)^\s*remove\s+([a-z0-9][a-z0-9'’.\-\s]{1,40}?)\.?\s*$", q
    )

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
        and not want_sms
        and not want_cal
        and not want_relationship
        and not about_trip
        and not ctx.is_empty()
        and not (u_people or u_places or u_trips or u_events)
        and not clear_date
        and not clear_place
        and not reset_all
        and not remove_place_m
    )

    if reset_all:
        people = []
        places = []
        trips = []
        events = []
        t0, t1 = None, None
        temporal = TemporalParse()
        notes.append("reset_cleared_shared_state")
    elif clear_date or clear_place or remove_place_m:
        inherit = True
        notes.append("clear_refinement")
        if not people:
            people = list(ctx.person_names)
        if clear_place:
            places = []
            trips = []
            notes.append("cleared_place")
        elif remove_place_m:
            drop = remove_place_m.group(1).replace(".", "").strip().lower()
            places = [p for p in ctx.place_names if p.lower() != drop and drop not in p.lower()]
            trips = [t for t in ctx_trips if t.lower() != drop and drop not in t.lower()]
            notes.append(f"removed_place={drop}")
        elif not places:
            places = list(ctx.place_names)
        if not trips and not clear_place and not remove_place_m:
            trips = list(ctx_trips)
        if not events:
            events = list(ctx_events)
        if clear_date:
            t0, t1 = None, None
            temporal = TemporalParse()
            notes.append("cleared_date")
        else:
            if t0 is None:
                t0 = ctx.time_start
            if t1 is None:
                t1 = ctx.time_end
    elif subject_changed:
        # D: do not inherit incompatible place/event/trip from prior subject
        if not people and ctx.person_names and not self_show:
            people = list(ctx.person_names)
            inherit = True
            notes.append("inherit_person_only_after_subject_change")
        notes.append("rule_D_no_inherit_incompatible_place_event_trip")
    elif self_show:
        # "show me myself" — I9A owner resolve owns identity; do not keep dad/etc.
        notes.append("show_me_self_no_inherit_person")
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
    # show me + partial name: upgrade to the longer related form only.
    # Do not keep "Alex" as a second person next to "Alex Reed" — that
    # resolved two MB Person ids and searched Immich twice (FlightSim 129s).
    if show_me and u_people and ctx.person_names and not self_show:
        merged = list(u_people)
        for cp in ctx.person_names:
            for i, u in enumerate(merged):
                ul, cl = u.lower(), cp.lower()
                if ul == cl:
                    break
                if ul in cl or cl in ul:
                    if len(cp) > len(u):
                        merged[i] = cp
                    break
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

    # Season without year: fill from session when available, else ask.
    # Birthday / anniversary without a year expand to all archive observances
    # (same as holidays). A later bare year is an optional narrow, including
    # a spoken answer to a leftover year question.
    if "temporal=season_needs_year" in temporal.notes:
        year_src = None
        for cand in (t0, t1, ctx.time_start, ctx.time_end):
            if cand and len(str(cand)) >= 4 and str(cand)[:4].isdigit():
                year_src = int(str(cand)[:4])
                break
        if year_src is None:
            requires_clarification = True
            ambiguity_message = "Which year do you mean for that season?"
            notes.append("clarify_temporal_needs_year")
        else:
            m = re.search(r"(?i)\b(spring|summer|fall|autumn|winter)\b", q)
            if m:
                season = m.group(1).lower()
                if season == "autumn":
                    season = "fall"
                start, end = season_window(season, year_src)
                temporal = TemporalParse(
                    time_start=start,
                    time_end=end,
                    windows=((start, end),),
                    label=f"{season.title()} {year_src}",
                    season=season,
                    notes=(
                        "temporal=season",
                        "season_def=meteorological_nh",
                        "season_year_from_context",
                    ),
                )
                t0, t1 = start, end
                notes.append("season_year_from_context")

    # Bare "2017" / "2017." after a person Ask — voice-ready year answer.
    # Do not treat it as a new comms-only Ask; keep the prior person + event.
    year_only_m = re.match(r"^\s*((?:19|20)\d{2})\.?\s*$", q)
    if year_only_m and people:
        year_n = int(year_only_m.group(1))
        is_followup = True
        inherit = True
        blob = " ".join(
            list(events)
            + list(ctx.event_labels or ())
            + [ctx.last_ask or "", q]
        )
        if BIRTHDAY_RE.search(blob) or temporal.life_event_kind == "birthday":
            temporal = TemporalParse(
                label=f"Birthday {year_n}",
                life_event_kind="birthday",
                life_event_years=(year_n,),
                notes=("temporal=life_event_birthday", "life_event_year_followup"),
            )
            t0, t1 = None, None
            if "Birthday" not in events:
                events.append("Birthday")
            notes.append("life_event_year_followup")
        elif ANNIVERSARY_RE.search(blob) or temporal.life_event_kind == "anniversary":
            temporal = TemporalParse(
                label=f"Anniversary {year_n}",
                life_event_kind="anniversary",
                life_event_years=(year_n,),
                notes=("temporal=life_event_anniversary", "life_event_year_followup"),
            )
            t0, t1 = None, None
            if "Anniversary" not in events:
                events.append("Anniversary")
            notes.append("life_event_year_followup")
        visual_scope = "broad"
        want_still = True
        want_video = True
        want_visual = True
        want_photo = True
        notes.append("year_only_followup_visual")
        last = ctx.last_ask or ""
        if EVERYTHING_ABOUT_RE.search(last):
            want_cross_source = True
            want_email = True
            want_sms = True
            want_cal = True
            want_spoken = True
            notes.append("year_only_followup_cross_source")

    # Modality inheritance for pure follow-ups without modality cue
    visual_ctx = any(
        m in (ctx.modalities_active or ()) for m in ("visual", "photo", "still", "video")
    )
    if is_followup and not want_visual and not want_email and not want_sms and not want_cal and not about_trip:
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

    if not want_visual and not want_email and not want_sms and not want_cal and not requires_clarification:
        want_email = True
        want_cal = True
        notes.append("default_comms_calendar")

    # Rule G: retrieval constraints from resolved context
    constraints: list[str] = []
    constraints.extend(people)
    constraints.extend(places)
    constraints.extend(trips)
    constraints.extend(events)
    constraints.extend(theme_labels)
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

    # Story modality (I5): exploratory + default archive asks; not email/photo/video-only or said-about.
    # Person "Show <Name>" asks stay visual-first but still pull stories as secondary meaning
    # so Immich hangs/empties don't leave Explore at 0 (FlightSim: Tom Will stories gone).
    want_story = False
    if not requires_clarification:
        if "exploratory_multimodal_i4" in notes or "tell_multimodal_i11" in notes or "default_comms_calendar" in notes or want_cross_source:
            want_story = True
        if any(
            n in notes
            for n in (
                "visual_scope=broad_show_me_person",
                "visual_scope=broad_show_person",
                "show_me_person_forces_broad_visual",
                "show_person_forces_broad_visual",
                "show_me_kinship_forces_broad_visual",
                "show_me_self_forces_broad_visual",
            )
        ):
            want_story = True
        if narrowed_comms and EMAIL_RE.search(q) and not exploratory:
            want_story = False
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_story = False
        if said_about:
            want_story = False
        if STORY_ASK_RE.search(q) and not said_about:
            if not (STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q)):
                want_story = True
        if (
            people
            and leftover_topic_tokens(q, people, places, trips, events)
            and not said_about
            and not (STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q))
        ):
            want_story = True
            notes.append("want_story_person_plus_topic")
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
        if "exploratory_multimodal_i4" in notes or "tell_multimodal_i11" in notes or "default_comms_calendar" in notes or want_cross_source:
            want_journal = True
        if narrowed_comms and EMAIL_RE.search(q) and not exploratory:
            want_journal = False
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_journal = False
        if said_about:
            want_journal = False
        if want_journal:
            notes.append("want_journal_modality")

    # Artifact modality (I9): explicit artifact/keepsake asks + exploratory archive
    want_artifact = False
    if not requires_clarification and not journal_capture_intent:
        if ARTIFACT_ASK_RE.search(q):
            want_artifact = True
        if "exploratory_multimodal_i4" in notes or "tell_multimodal_i11" in notes or "default_comms_calendar" in notes or want_cross_source:
            want_artifact = True
        if narrowed_comms and EMAIL_RE.search(q) and not exploratory:
            want_artifact = False
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_artifact = False
        if said_about:
            want_artifact = False
        if want_artifact:
            notes.append("want_artifact_modality")

    # Guided Capture Responses: said-about / interview testimony / exploratory (not I11 narration)
    want_guided_capture = False
    if not requires_clarification and not journal_capture_intent:
        if said_about or GUIDED_CAPTURE_ASK_RE.search(q):
            want_guided_capture = True
        if "exploratory_multimodal_i4" in notes or "tell_multimodal_i11" in notes or "default_comms_calendar" in notes or want_cross_source:
            want_guided_capture = True
        if STILL_ONLY_RE.search(q) or VIDEO_ONLY_RE.search(q):
            want_guided_capture = False
        if want_guided_capture:
            notes.append("want_guided_capture_modality")

    if want_spoken and not want_cross_source:
        visual_scope = "video_only"
        want_still = False
        want_video = True
        want_visual = True
        want_photo = False
        if not EMAIL_RE.search(q) and not SMS_ASK_RE.search(q):
            want_email = False
            want_sms = False
            want_cal = False
            want_guided_capture = False
        notes.append("want_spoken_final")

    if want_sms:
        notes.append("want_sms_modality")
    if want_email:
        notes.append("want_email_modality")
    if want_cal and not requires_clarification and not journal_capture_intent:
        notes.append("want_calendar_modality")

    output_mode = compile_output_mode(
        q,
        said_about=said_about,
        want_spoken=want_spoken,
        want_cross_source=want_cross_source,
    )

    return QueryPlan(
        original_ask=q,
        effective_ask=effective if not journal_capture_intent else "journal_capture",
        is_followup=is_followup,
        want_photo=want_photo and not journal_capture_intent,
        want_communication=(want_email or want_sms)
        and not requires_clarification
        and not journal_capture_intent,
        want_calendar=want_cal and not requires_clarification and not journal_capture_intent,
        want_story=want_story and not journal_capture_intent,
        want_journal=want_journal and not journal_capture_intent,
        want_artifact=want_artifact and not journal_capture_intent,
        want_guided_capture=want_guided_capture and not journal_capture_intent,
        journal_capture_intent=journal_capture_intent,
        visual_scope=visual_scope if not requires_clarification and not journal_capture_intent else "none",
        want_visual=want_visual and not requires_clarification and not journal_capture_intent,
        want_still=want_still and not requires_clarification and not journal_capture_intent,
        want_video=want_video and not requires_clarification and not journal_capture_intent,
        want_spoken=want_spoken and not requires_clarification and not journal_capture_intent,
        spoken_phrase=spoken_phrase,
        spoken_about=spoken_about,
        person_names=tuple(people),
        place_names=tuple(places),
        event_labels=tuple(event_labels),
        trip_labels=tuple(trips),
        time_start=t0,
        time_end=t1,
        temporal_windows=_final_windows(temporal, t0, t1),
        temporal_label=(
            temporal.label
            if temporal.label
            and (
                temporal.life_event_kind
                or (temporal.time_start == t0 and temporal.time_end == t1)
            )
            else (
                f"{t0[:4]}–{t1[:4]}"
                if t0 and t1 and t0[:4] != t1[:4]
                else (t0[:4] if t0 else None)
            )
        ),
        life_event_kind=temporal.life_event_kind,
        life_event_years=tuple(temporal.life_event_years or ()),
        inherit_from_context=inherit,
        notes=tuple(notes),
        temporal_after=temporal_after or ref_then,
        broaden_same_context=broaden,
        requires_clarification=requires_clarification,
        ambiguity_message=ambiguity_message,
        reference_resolved=reference_resolved,
        subject_changed=subject_changed,
        retrieval_constraints=tuple(constraints),
        act="clarify" if requires_clarification else "find",
        compile_provenance="deterministic",
        gallery_show_sms=True if want_cross_source else None,
        gallery_show_email=True if want_cross_source else None,
        gallery_show_calendar=True if want_cross_source else None,
        want_cross_source=want_cross_source and not journal_capture_intent,
        theme_labels=tuple(theme_labels),
        output_mode=output_mode if not journal_capture_intent else "show",
    )
