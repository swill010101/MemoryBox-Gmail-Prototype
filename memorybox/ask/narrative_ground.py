"""Post-narration evidence gate: displayed prose vs semantic-pack IDs.

Does not change I11A inference. Unsupported place/date/weather/activity/
companion/transition claims are stripped before display.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"'])")
_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_GEO_SUFFIX = (
    r"Sea|Ocean|River|Bay|Island|Islands|Mountains?|Strait|Gulf|Peninsula|"
    r"Harbor|Harbour|City|County|Province|State|Lake|Beach|Inlet|Sound|"
    r"Pass|Glacier|Fjord|Range|Reef|Channel|Cape|Point|Valley|Forest|"
    r"Desert|Plateau|Archipelago|Atoll"
)
_GEO_PHRASE = re.compile(
    rf"\b((?:[A-Z][a-z]+(?:\s+|\-)){{0,3}}(?:{_GEO_SUFFIX}))\b"
)
_PREP_PLACE = re.compile(
    r"\b(?:in|at|near|from|to|across|over|off|aboard|toward|towards)\s+"
    r"((?:the\s+)?[A-Z][a-z]+(?:[\s\-][A-Z][a-z]+){0,3})\b"
)
_MONTH = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december"
)
_DATE_ATOM = rf"(?:(?:{_MONTH})\s+\d{{1,2}}(?:\,\s*\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})"
_DATE_TOKEN = re.compile(rf"\b({_DATE_ATOM})\b", re.I)
_DATE_RANGE = re.compile(
    rf"\b(?:from\s+)?({_DATE_ATOM})\s+(?:through|to|until|–|-)\s+({_DATE_ATOM})\b",
    re.I,
)
_WEATHER = re.compile(
    r"(?i)\b("
    r"storm|stormy|fog|foggy|rain|rainy|snow|snowy|sleet|hail|"
    r"wind|windy|gale|sunny|overcast|weather|chill|cold front|"
    r"clear skies|rough seas|whitecaps|blizzard|drizzle|humid|"
    r"heatwave|thunder|lightning|mist"
    r")\b"
)
_EXPERIENTIAL = re.compile(
    r"(?i)\b("
    r"excited|excitement|concern|concerned|disappointed|disappointment|"
    r"beauty|beautiful|atmosphere|dramatic|awe|awesome|worried|"
    r"thrilled|heartwarming|breathtaking|majestic|solemn|tense|"
    r"anxious|delight|delighted|fear|afraid|wonderstruck|nostalgic|"
    r"mood|felt|feeling|emotion|emotional|"
    r"grateful|gratitude|profound|much-needed|milestone|"
    r"beautiful scenery|important milestone"
    r")\b"
)
_OCCURRED = re.compile(
    r"(?i)\b("
    r"spent|traveled|travelled|flew|drove|sailed|stayed|visited|"
    r"were in|was in|crossed|toured|journeyed|cruised"
    r")\b"
)
_HEDGE = re.compile(
    r"(?i)\b("
    r"the calendar showed|calendar (?:listed|recorded|had)|"
    r"scheduled|planned|planning|"
    r"travel records indicate|photos place|messages suggest|"
    r"itinerary listed|records (?:show|indicate)|"
    r"not proof|not shown as occurred"
    r")\b"
)
_TRANSITION = re.compile(
    r"(?i)\b("
    r"as (?:they|he|she) (?:left|departed|sailed|drove|watched)|"
    r"the weather (?:turned|changed|broke)|"
    r"as dawn broke|as night fell|"
    r"on the way home|after leaving|once they arrived|"
    r"excitement (?:grew|filled)|the air was"
    r")\b"
)
_COMPANION = re.compile(
    r"(?i)\b(?:with|alongside|joined by|accompanied by|together with)\s+"
    r"((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){0,2})\b"
)
_ACTIVITY = re.compile(
    r"(?i)\b(?:went|go(?:ing)?|did|doing|watched|fishing|hiking|"
    r"whale watching|sightseeing|camping|kayaking|hunting)\b"
)
_FRAMING = frozenset(
    {
        "during",
        "family",
        "records",
        "record",
        "messages",
        "message",
        "photos",
        "photo",
        "travel",
        "calendar",
        "this",
        "that",
        "these",
        "those",
        "nothing",
        "memorybox",
        "ask",
        "on",
        "in",
        "at",
        "from",
        "for",
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "as",
        "it",
        "its",
        "they",
        "them",
        "their",
        "there",
        "then",
        "than",
        "when",
        "where",
        "what",
        "who",
        "how",
        "after",
        "before",
        "about",
        "into",
        "over",
        "under",
        "with",
        "without",
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "spring",
        "summer",
        "autumn",
        "fall",
        "winter",
        "period",
        "account",
        "chronological",
        "following",
        "outline",
        "episode",
        "episodes",
        "theme",
        "themes",
        "claim",
        "claims",
        "evidence",
        "archive",
        "original",
        "correspondence",
        "ordinary",
        "standout",
        "shape",
        "life",
        "asked",
        "window",
        "windows",
        "planning",
        "scheduled",
        "observed",
        "actual",
        "showed",
        "indicate",
        "suggest",
        "place",
        "places",
        "people",
        "person",
        "harbor",  # common common-noun; proper "X Harbor" still uses geo phrase
        "dinner",
        "trip",
        "home",
        "city",
        "state",
        "county",
        "island",
        "sea",
        "ocean",
        "river",
        "bay",
        "lake",
        "beach",
    }
)
_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _lower(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _parse_iso(raw: str) -> date | None:
    text = str(raw or "").strip()[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_date_token(raw: str, *, year_hint: int | None) -> date | None:
    text = str(raw or "").strip()
    iso = _parse_iso(text)
    if iso:
        return iso
    m = re.match(rf"(?i)({_MONTH})\s+(\d{{1,2}})(?:\,\s*(\d{{4}}))?", text)
    if not m:
        return None
    month = _MONTH_NAMES.get(m.group(1).lower())
    day_n = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else year_hint
    if not month or not year:
        return None
    try:
        return date(year, month, day_n)
    except ValueError:
        return None


def _claim_text(claim: Any) -> str:
    if isinstance(claim, dict):
        return str(claim.get("text") or "")
    return str(claim or "")


def _iter_units(pack: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for u in pack.get("units") or []:
        if isinstance(u, dict):
            out.append(u)
    return out


def _iter_episodes(pack: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    outline = pack.get("life_period_outline") if isinstance(pack.get("life_period_outline"), dict) else {}
    for ep in outline.get("episodes") or []:
        if isinstance(ep, dict):
            out.append(ep)
    inf = pack.get("validated_inference") if isinstance(pack.get("validated_inference"), dict) else {}
    for ep in inf.get("episodes") or []:
        if isinstance(ep, dict):
            out.append(ep)
    return out


def grounding_index(pack: dict[str, Any]) -> dict[str, Any]:
    """Lexicon of places/people/dates/weather/activities licensed by evidence IDs."""
    blobs: list[str] = []
    places: set[str] = set()
    people: set[str] = set()
    explicit_dates: set[str] = set()
    observed_spans: list[tuple[date, date]] = []
    recorded_spans: list[tuple[date, date]] = []
    derived_spans: list[tuple[date, date]] = []
    ids: set[str] = set()
    year_hint: int | None = None
    place_ids: dict[str, list[str]] = {}
    date_ids: dict[str, list[str]] = {}

    def _bind(eid: str, place: Any, day: Any) -> None:
        if not eid:
            return
        p = _lower(place)
        if p and p not in {"none", "null", "unknown"}:
            bucket = place_ids.setdefault(p, [])
            if eid not in bucket:
                bucket.append(eid)
        if isinstance(day, dict):
            day = day.get("value") or day.get("start")
        d = _parse_iso(str(day or ""))
        if d:
            bucket = date_ids.setdefault(d.isoformat(), [])
            if eid not in bucket:
                bucket.append(eid)

    def add_blob(text: Any) -> None:
        t = _lower(text)
        if t:
            blobs.append(t)

    def add_place(text: Any) -> None:
        t = _lower(text)
        if t and t not in {"none", "null", "unknown"}:
            places.add(t)

    def add_person(text: Any) -> None:
        t = _lower(text)
        if t:
            people.add(t)
            add_blob(t)

    def add_date(raw: Any) -> None:
        d = _parse_iso(str(raw or ""))
        if d:
            explicit_dates.add(d.isoformat())
            nonlocal year_hint
            year_hint = d.year

    for u in _iter_units(pack):
        eid = str(u.get("evidence_id") or u.get("unit_id") or "").strip()
        if eid:
            ids.add(eid)
        add_place(u.get("place"))
        add_blob(u.get("content"))
        add_blob(u.get("title"))
        add_blob(u.get("place"))
        add_date(u.get("time") or u.get("capture_time"))
        _bind(eid, u.get("place"), u.get("time") or u.get("capture_time"))
        for p in u.get("people") or []:
            if isinstance(p, dict):
                add_person(p.get("name") or p.get("person_id"))
            else:
                add_person(p)
        kind = str(u.get("kind") or u.get("source_type") or "").lower()
        start = _parse_iso(str(u.get("time") or ""))
        end = _parse_iso(str(u.get("date_end") or u.get("time") or ""))
        if start and end:
            if kind in {"calendar", "calendar_event"}:
                recorded_spans.append((start, end))
            elif kind in {"photo", "video", "media_observation", "spoken_moment", "journal", "story"}:
                observed_spans.append((start, end))
            elif kind == "travel":
                derived_spans.append((start, end))

    for ep in _iter_episodes(pack):
        for pl in ep.get("places") or []:
            add_place(pl)
        if ep.get("place"):
            add_place(ep.get("place"))
        for p in ep.get("people") or []:
            if isinstance(p, dict):
                add_person(p.get("name") or p.get("person_id"))
            else:
                add_person(p)
        for eid in ep.get("evidence_ids") or ep.get("supporting_evidence_ids") or []:
            if str(eid).strip():
                ids.add(str(eid).strip())
                for pl in list(ep.get("places") or []) + [ep.get("place")]:
                    _bind(str(eid).strip(), pl, (ep.get("date_span") or {}).get("start") if isinstance(ep.get("date_span"), dict) else None)
        span = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
        add_date(span.get("start"))
        add_date(span.get("end"))
        d0 = _parse_iso(str(span.get("start") or ""))
        d1 = _parse_iso(str(span.get("end") or span.get("start") or ""))
        types: set[str] = set()
        for cl in ep.get("claims") or []:
            add_blob(_claim_text(cl))
            if isinstance(cl, dict):
                ct = str(cl.get("claim_type") or "")
                if ct:
                    types.add(ct)
                for eid in cl.get("supporting_evidence_ids") or []:
                    if str(eid).strip():
                        ids.add(str(eid).strip())
        add_blob(ep.get("theme_or_episode") or ep.get("label") or ep.get("title"))
        unc = ep.get("uncertainty") if isinstance(ep.get("uncertainty"), dict) else {}
        def _absorb_win(win: Any, dest: list[tuple[date, date]]) -> None:
            if not isinstance(win, dict):
                return
            a = _parse_iso(win.get("start"))
            b = _parse_iso(win.get("end") or win.get("start"))
            add_date(win.get("start"))
            add_date(win.get("end"))
            if a and b:
                dest.append((a, b))

        _absorb_win(ep.get("observed_window"), observed_spans)
        _absorb_win(ep.get("scheduled_window"), recorded_spans)
        _absorb_win(ep.get("derived_window"), derived_spans)
        if d0 and d1 and not (ep.get("observed_window") or ep.get("scheduled_window") or ep.get("derived_window")):
            if (
                "recorded" in types
                or unc.get("occurrence_not_established_by_calendar_alone")
                or unc.get("calendar_scheduled_not_occurred")
            ):
                recorded_spans.append((d0, d1))
            elif "derived" in types:
                derived_spans.append((d0, d1))
            else:
                observed_spans.append((d0, d1))

    outline = pack.get("life_period_outline") if isinstance(pack.get("life_period_outline"), dict) else {}

    def _absorb_pack_win(win: Any, dest: list[tuple[date, date]]) -> None:
        if not isinstance(win, dict):
            return
        a = _parse_iso(win.get("start"))
        b = _parse_iso(win.get("end") or win.get("start"))
        add_date(win.get("start"))
        add_date(win.get("end"))
        if a and b:
            dest.append((a, b))

    _absorb_pack_win(pack.get("observed_window") or outline.get("observed_window"), observed_spans)
    _absorb_pack_win(pack.get("scheduled_window") or outline.get("scheduled_window"), recorded_spans)
    _absorb_pack_win(pack.get("derived_window") or outline.get("derived_window"), derived_spans)

    blob = " \n ".join(blobs)
    weather_ok = {m.group(1).lower() for m in _WEATHER.finditer(blob)}
    experiential_ok = {m.group(1).lower() for m in _EXPERIENTIAL.finditer(blob)}
    return {
        "blob": blob,
        "places": places,
        "people": people,
        "explicit_dates": explicit_dates,
        "observed_spans": observed_spans,
        "recorded_spans": recorded_spans,
        "derived_spans": derived_spans,
        "weather_ok": weather_ok,
        "experiential_ok": experiential_ok,
        "ids": ids,
        "year_hint": year_hint,
        "period": _lower(outline.get("period") or ""),
        "place_ids": place_ids,
        "date_ids": date_ids,
    }


def _in_blob(phrase: str, blob: str) -> bool:
    p = _lower(phrase)
    if not p:
        return True
    if p in blob:
        return True
    # drop leading the
    if p.startswith("the ") and p[4:] in blob:
        return True
    return False


def _place_grounded(phrase: str, index: dict[str, Any]) -> bool:
    p = _lower(phrase)
    if not p or p in _FRAMING:
        return True
    if p in index["places"] or _in_blob(p, index["blob"]):
        return True
    if p.startswith("the ") and (p[4:] in index["places"] or _in_blob(p[4:], index["blob"])):
        return True
    return False


def _person_grounded(phrase: str, index: dict[str, Any]) -> bool:
    p = _lower(phrase)
    if not p or p in _FRAMING:
        return True
    if p in index["people"] or _in_blob(p, index["blob"]):
        return True
    return False


def _date_grounded(token: str, index: dict[str, Any]) -> bool:
    d = _parse_date_token(token, year_hint=index.get("year_hint"))
    if d and d.isoformat() in index["explicit_dates"]:
        return True
    if _in_blob(token, index["blob"]):
        return True
    # month-only mentions that match the asked period label
    if _lower(token).split()[0] in _MONTH_NAMES and _lower(token) in (index.get("period") or ""):
        return True
    return False


def _span_covered(start: date, end: date, spans: list[tuple[date, date]]) -> bool:
    for a, b in spans:
        if a <= start and end <= b and (b - a).days <= 21:
            return True
        if a == start and b == end:
            return True
    return False


def sentence_violations(sentence: str, index: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not str(sentence or "").strip():
        return reasons
    hedge = bool(_HEDGE.search(sentence))

    for m in _GEO_PHRASE.finditer(sentence):
        if not _place_grounded(m.group(1), index):
            reasons.append(f"place:{m.group(1)}")
    for m in _PREP_PLACE.finditer(sentence):
        phrase = m.group(1)
        core = re.sub(r"(?i)^the\s+", "", phrase).strip()
        first = (_lower(core).split() or [""])[0]
        if first in _FRAMING or first in _MONTH_NAMES:
            continue
        if _person_grounded(core, index):
            continue
        if not _place_grounded(core, index):
            reasons.append(f"place:{phrase}")

    for m in _WEATHER.finditer(sentence):
        tok = m.group(1).lower()
        if tok not in index["weather_ok"] and not _in_blob(tok, index["blob"]):
            reasons.append(f"weather:{tok}")
    for m in _EXPERIENTIAL.finditer(sentence):
        tok = m.group(1).lower()
        if tok not in index["experiential_ok"] and not _in_blob(tok, index["blob"]):
            reasons.append(f"experiential:{tok}")
    if _TRANSITION.search(sentence) and not hedge:
        # Transitions may stand if every content word is in the blob; otherwise reject.
        if not any(_in_blob(m.group(0), index["blob"]) for m in _TRANSITION.finditer(sentence)):
            reasons.append("transition:unsupported")

    for m in _COMPANION.finditer(sentence):
        if not _person_grounded(m.group(1), index):
            reasons.append(f"companion:{m.group(1)}")

    for m in _ACTIVITY.finditer(sentence):
        tok = m.group(0).lower()
        if tok in {"did", "doing", "go", "going", "went", "watched"}:
            continue
        if not _in_blob(tok, index["blob"]):
            reasons.append(f"activity:{tok}")

    for m in _DATE_TOKEN.finditer(sentence):
        token = m.group(1)
        if not _date_grounded(token, index):
            # ISO/month-day not licensed by an evidence ID
            reasons.append(f"date:{token}")

    occurred = bool(_OCCURRED.search(sentence))
    if occurred and not hedge:
        for m in _DATE_RANGE.finditer(sentence):
            a = _parse_date_token(m.group(1), year_hint=index.get("year_hint"))
            b = _parse_date_token(m.group(2), year_hint=index.get("year_hint"))
            if a and b:
                if _span_covered(a, b, index["observed_spans"]):
                    continue
                if _span_covered(a, b, index.get("derived_spans") or []):
                    reasons.append("derived_span_as_actual")
                    continue
                if _span_covered(a, b, index["recorded_spans"]):
                    reasons.append("calendar_span_as_actual")
                    continue
                reasons.append("date_span:unobserved")
        # “spent the entire/whole …” treats a scheduled window as occurred
        if re.search(r"(?i)\b(spent|were|was|stayed)\b.{0,40}\b(entire|whole|throughout)\b", sentence):
            if index["recorded_spans"] and not _span_covered(
                index["recorded_spans"][0][0],
                index["recorded_spans"][0][1],
                index["observed_spans"],
            ):
                reasons.append("calendar_span_as_actual")

    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _evidence_ids_for_sentence(sentence: str, index: dict[str, Any]) -> list[str]:
    """Map place/date mentions in a kept sentence to supporting evidence IDs."""
    found: list[str] = []
    seen: set[str] = set()

    def add_all(ids: list[str] | None) -> None:
        for i in ids or []:
            if i and i not in seen:
                seen.add(i)
                found.append(i)

    for m in _GEO_PHRASE.finditer(sentence):
        add_all((index.get("place_ids") or {}).get(_lower(m.group(1))))
    for m in _PREP_PLACE.finditer(sentence):
        add_all((index.get("place_ids") or {}).get(_lower(m.group(1))))
        core = re.sub(r"(?i)^the\s+", "", m.group(1)).strip()
        add_all((index.get("place_ids") or {}).get(_lower(core)))
    for m in _DATE_TOKEN.finditer(sentence):
        d = _parse_date_token(m.group(1), year_hint=index.get("year_hint"))
        if d:
            add_all((index.get("date_ids") or {}).get(d.isoformat()))
    return found


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for para in re.split(r"\n{2,}", text or ""):
        para = para.strip()
        if not para:
            continue
        bits = [s.strip() for s in _SENT_SPLIT.split(para) if s.strip()]
        parts.extend(bits or [para])
    return parts


def enforce_narrative_grounding(
    text: str,
    pack: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Strip unsupported sentences. Fail closed if nothing grounded remains."""
    meta: dict[str, Any] = {"ok": True, "fail_closed": False, "rejected": []}
    raw = str(text or "").strip()
    if not raw:
        meta["ok"] = False
        meta["fail_closed"] = True
        return "", meta
    index = grounding_index(pack or {})
    kept: list[str] = []
    sentence_evidence: list[dict[str, Any]] = []
    for sent in split_sentences(raw):
        reasons = sentence_violations(sent, index)
        if reasons:
            meta["rejected"].append({"sentence": sent, "reasons": reasons})
            continue
        kept.append(sent)
        eids = _evidence_ids_for_sentence(sent, index)
        if eids:
            sentence_evidence.append({"sentence": sent, "evidence_ids": eids})
    if not kept:
        meta["ok"] = False
        meta["fail_closed"] = True
        return "", meta
    # Re-join: single sentences stay one paragraph; original multi-sentence
    # paragraphs are flattened into readable prose blocks of ~3 sentences.
    paras: list[str] = []
    buf: list[str] = []
    for sent in kept:
        buf.append(sent if sent.endswith((".", "!", "?")) else sent + ".")
        if len(buf) >= 3:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    meta["kept_n"] = len(kept)
    meta["redacted_n"] = len(meta["rejected"])
    meta["sentence_evidence"] = sentence_evidence
    return "\n\n".join(paras), meta


def ground_narrative(
    text: str,
    pack: dict[str, Any] | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Return (displayable prose, rejected sentence records). Empty prose = fail closed."""
    cleaned, meta = enforce_narrative_grounding(text, pack)
    return cleaned, list(meta.get("rejected") or [])
