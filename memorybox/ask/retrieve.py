"""Evidence + photo retrieval for Ask (PostgreSQL / Qdrant / PhotoProvider)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from memorybox.ask.place_match import (
    filter_photo_hits_to_places,
    place_match_spec,
)
from memorybox.config import Settings, settings
from memorybox.db import connection
from memorybox.ingest import rebuild_index
from memorybox.planner import QueryPlan
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.photo.dto import PhotoAssetDto, PhotoSearchQuery
from memorybox.providers.photo.protocol import PhotoProvider


@dataclass
class EvidenceHit:
    evidence_id: str
    evidence_kind: str
    summary: str
    score: float
    excerpt: str
    source: str  # qdrant | postgres_keyword | sms_export | email_mbox
    sent_at: str | None = None
    channel: str | None = None
    people: list[str] | None = None
    thread_id: str | None = None
    direction: str | None = None
    attachments: list[dict[str, Any]] | None = None
    count_scope: str | None = None
    match_total: int | None = None
    truncated: bool = False
    identity_mapped: list[dict[str, str]] | None = None
    from_header: str | None = None
    to_header: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Hard ceiling so a 90k-row export cannot dump the whole archive into Explore.
# Year-fair sampling keeps every year on the Timeline when we must truncate.
# I7 gallery/export retrieve may year-fair-slice. Bounded tell must not.
SMS_RETRIEVE_CAP = 25000
# SQL page size only — not a semantic evidence limit.
TELL_DB_PAGE = 500

_MONTH_KEYWORD_STOP = {
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
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
}
_TELL_KEYWORD_STOP = {
    "write",
    "narrative",
    "narrate",
    "story",
    "tell",
    "know",
    "summarize",
    "summary",
    "happened",
    "like",
    "year",
    "month",
    "about",
}


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
SMS_COUNT_RE = re.compile(r"(?i)\bhow many\b|\bcount\b|\btimes did\b")
SMS_OUTBOUND_RE = re.compile(
    r"(?i)\b(i sent|have i sent|did i send|text messages did i send|total text)\b"
)
SMS_INBOUND_RE = re.compile(
    r"(?i)\b("
    r"(?:send|sent|text(?:ed|s)?)\s+to\s+me|"
    r"did\s+.+\s+send\s+(?:to\s+)?me|"
    r"how\s+many.+\s+send\s+(?:to\s+)?me|"
    r"emojis?\s+did\s+.+\s+send\s+me"
    r")\b"
)
SMS_LAST_N_RE = re.compile(r"(?i)\blast\s+(\d+)")
SMS_ATTACH_ASK_RE = re.compile(
    r"(?i)\bwith\s+attachments?\b|\bhas\s+attachments?\b|\bthat\s+have\s+attachments?\b"
)
SMS_HEART_ASK_RE = re.compile(
    r"(?i)\bhear(?:t)?\s+emojis?|\bheart\s+emojis?|❤️|❤|♥️"
)
SMS_NARRATIVE_RE = re.compile(
    r"(?i)\b(write\s+a\s+narrative|write\s+a\s+story|narrate|narrative\s+about)\b"
)
_HEART_MARK_RE = re.compile(
    r"(?i)❤️|❤|♥️|💕|💖|💗|💓|💞|💘|💝|"
    r"\b(loved|hearted|tapback\s*loved)\b"
)
_SMS_CHANNELS = frozenset({"sms", "text", "imessage", "mms", "rcs"})
_SMS_FAKE_PEOPLE = frozenset(
    {
        "attachments",
        "attachment",
        "unknown",
        "photo",
        "image",
        "messages",
        "message",
        "and",
    }
)
EMAIL_ASK_RE = re.compile(r"(?i)\b(e-?mails?|inbox|correspondence)\b")
EMAIL_COUNT_RE = re.compile(r"(?i)\bhow many\b|\bcount\b|\btimes did\b")
EMAIL_OUTBOUND_RE = re.compile(
    r"(?i)\b("
    r"did i e-?mail|have i e-?mailed|i e-?mailed|how many times did i e-?mail|"
    r"e-?mails? did i send|sent e-?mail"
    r")\b"
)
EMAIL_INBOUND_RE = re.compile(
    r"(?i)\b("
    r"respond(?:ed)?\s+to\s+any\s+of\s+my\s+e-?mails?|"
    r"replied\s+to\s+my\s+e-?mails?|"
    r"e-?mails?\s+.+\s+respond"
    r")\b"
)
EMAIL_THREAD_RE = re.compile(r"(?i)\b(thread|replies|reply chain|conversation)\b")
EMAIL_ATTACH_ASK_RE = re.compile(
    r"(?i)\bwith\s+attachments?\b|\bhas\s+attachments?\b|\binline\s+images?\b"
)
_EMAIL_FAKE_PEOPLE = frozenset(
    {
        "attachments",
        "attachment",
        "unknown",
        "email",
        "emails",
        "mail",
        "inbox",
        "and",
        "times",
    }
)

_SMS_KEYWORD_EXTRA_STOP = frozenset(
    {
        "about",
        "between",
        "myself",
        "narrative",
        "write",
        "hear",
        "heart",
        "emoji",
        "emojis",
        "attachment",
        "attachments",
        "only",
        "last",
        "involving",
        "library",
        "visible",
        "gallery",
    }
)


@dataclass
class PhotoHit:
    provider_key: str
    external_id: str
    taken_at: str | None
    people: list[str]
    location: str | None
    thumb_url: str | None
    web_url: str | None
    score: float = 1.0
    identity_trust: str = "confirmed"  # confirmed | trusted_provider | candidate
    mb_person_id: str | None = None
    mb_person_name: str | None = None
    attribution: str | None = None
    # Structured place (I4 location filter / map) — optional; never invent coords
    place: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    original_filename: str | None = None
    # Camera EXIF for Source rail — dict keys are human labels
    exif: dict[str, str] | None = None
    # Immich-named faces on the asset (+ optional boxes)
    faces: list[dict[str, Any]] | None = None
    media_type: str = "image"
    duration_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoHit:
    provider_key: str
    external_id: str
    video_external_id: str
    start_sec: float
    end_sec: float
    face_external_id: str | None = None
    label: str | None = None
    play_url: str | None = None
    identity_trust: str = "confirmed"  # confirmed | trusted_provider | candidate
    mb_person_id: str | None = None
    mb_person_name: str | None = None
    attribution: str | None = None
    taken_at: str | None = None
    original_filename: str | None = None
    thumb_url: str | None = None
    spoken_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place: str | None = None
    city: str | None = None
    state: str | None = None
    duration_sec: float | None = None
    media_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def photo_hit_is_video(hit: PhotoHit | dict[str, Any]) -> bool:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit or {})
    if str(d.get("media_type") or "").lower() == "video":
        return True
    fn = str(d.get("original_filename") or "").lower()
    return fn.endswith((".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"))


def video_assets_from_photo_hits(photos: list[PhotoHit]) -> list[VideoHit]:
    """Immich VIDEO files as evidence even when HVRT returns zero moments."""
    out: list[VideoHit] = []
    for h in photos or []:
        if not photo_hit_is_video(h):
            continue
        out.append(
            VideoHit(
                provider_key=h.provider_key,
                external_id=h.external_id,
                video_external_id=h.external_id,
                start_sec=0.0,
                end_sec=float(h.duration_sec or 0.0),
                label=h.original_filename or h.location or "Immich video",
                play_url=h.web_url,
                identity_trust=h.identity_trust,
                mb_person_id=h.mb_person_id,
                mb_person_name=h.mb_person_name,
                attribution="video_asset",
                taken_at=h.taken_at,
                original_filename=h.original_filename,
                thumb_url=h.thumb_url,
                latitude=h.latitude,
                longitude=h.longitude,
                place=h.place or h.location,
                city=h.city,
                state=h.state,
                duration_sec=h.duration_sec,
                media_type="video",
            )
        )
    return out


def _origin_on_video_hit(h: VideoHit) -> VideoHit:
    try:
        from memorybox.recognition.origin import origin_card_fields

        meta = origin_card_fields(h.video_external_id, t_sec=float(h.start_sec or 0))
    except Exception:
        return h
    if not h.taken_at:
        h.taken_at = meta.get("taken_at")
    if not h.original_filename:
        h.original_filename = meta.get("original_filename")
    h.thumb_url = meta.get("thumb_url") or h.thumb_url
    return h


@dataclass
class StoryHit:
    story_id: str
    version: int
    title: str | None
    excerpt: str
    narrator_person_id: str | None
    narrator_display_name: str | None
    provenance_kind: str
    attribution: str
    score: float = 1.0
    taken_at: str | None = None
    thumb_url: str | None = None
    source_photo_id: str | None = None
    people: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_STORY_TOKEN_STOP = {
    "what",
    "you",
    "know",
    "about",
    "tell",
    "have",
    "from",
    "our",
    "the",
    "trip",
    "show",
    "me",
    "emails",
    "photos",
    "story",
    "stories",
    "storiest",
    "grandma",
    "grandpa",
    "grandmother",
    "grandfather",
    "nana",
    "grammy",
    "gram",
    "my",
    "and",
    "please",
    "some",
    "any",
}


def story_search_tokens(plan: QueryPlan) -> list[str]:
    """Ask words plus planner constraints. Do not search only the person name.

    'Eugene Will rabbits' must keep rabbits. Constraints alone are 'Eugene Will',
    which will not match a Story tagged Tom/Anne that quotes Dad.
    """
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: str) -> None:
        t = (raw or "").strip()
        if len(t) < 3:
            return
        key = t.lower()
        if key in _STORY_TOKEN_STOP or key in seen:
            return
        seen.add(key)
        out.append(t)

    for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", getattr(plan, "original_ask", None) or ""):
        add(t)
    for c in getattr(plan, "retrieval_constraints", None) or ():
        add(str(c or ""))
        for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", str(c or "")):
            add(t)
    return out


def _payload_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _excerpt(payload: dict[str, Any], kind: str, limit: int = 280) -> str:
    if kind == "communication":
        text = payload.get("body_text") or payload.get("subject") or ""
    else:
        text = (
            payload.get("description")
            or payload.get("summary")
            or payload.get("title")
            or ""
        )
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:limit]


def _sms_ask(plan: QueryPlan) -> bool:
    if getattr(plan, "want_cross_source", False):
        return True
    ask = plan.original_ask or ""
    # tell_multimodal notes include want_sms_modality for the pack, not an I7 SMS Ask.
    if _tell_pack_comms(plan):
        return bool(
            SMS_ASK_RE.search(ask)
            or SMS_INBOUND_RE.search(ask)
            or SMS_HEART_ASK_RE.search(ask)
            or SMS_LAST_N_RE.search(ask)
            or SMS_ATTACH_ASK_RE.search(ask)
        )
    blob = f"{ask} {plan.effective_ask or ''} {' '.join(plan.notes or ())}"
    return (
        bool(SMS_ASK_RE.search(blob))
        or "want_sms_modality" in (plan.notes or ())
        or bool(SMS_INBOUND_RE.search(blob))
        or bool(SMS_HEART_ASK_RE.search(blob))
        or bool(SMS_NARRATIVE_RE.search(blob))
        or bool(SMS_LAST_N_RE.search(blob))
        or bool(SMS_ATTACH_ASK_RE.search(blob))
    )


def _email_ask(plan: QueryPlan) -> bool:
    if getattr(plan, "want_cross_source", False):
        return True
    ask = plan.original_ask or ""
    if _tell_pack_comms(plan):
        return bool(EMAIL_ASK_RE.search(ask))
    blob = f"{ask} {plan.effective_ask or ''} {' '.join(plan.notes or ())}"
    return bool(EMAIL_ASK_RE.search(blob))


def _tell_pack_comms(plan: QueryPlan) -> bool:
    if str(getattr(plan, "output_mode", "") or "") == "tell":
        return True
    return "tell_multimodal_i11" in (getattr(plan, "notes", ()) or ())


def trip_discovery_pending(plan: QueryPlan) -> bool:
    """Named trip TELL: person/time retrieve first; place is a hint until clustered."""
    notes = getattr(plan, "notes", ()) or ()
    return "trip_window_unresolved" in notes and "trip_window_resolved" not in notes


def _exclusive_place_trip_keywords(plan: QueryPlan) -> list[str]:
    if trip_discovery_pending(plan):
        return []
    return _place_trip_keywords(plan)


def _bounded_period_tell(plan: QueryPlan) -> bool:
    """Dated tell (month, year, trip window): every in-scope row may contribute."""
    if not _tell_pack_comms(plan):
        return False
    if getattr(plan, "temporal_windows", ()) or ():
        return True
    return bool(getattr(plan, "time_start", None) and getattr(plan, "time_end", None))


def visual_library_person_ids(plan: QueryPlan) -> tuple[list[str], str | None]:
    """Person ids for photo/video library search.

    Named subjects on the Ask (Peggy, …) stay the library. When the Ask has no
    person slot — typical of “my January” — use the requestor Person (today the
    single owner; later the signed-in user). Do not write that id onto the plan,
    or inherit/subject-change will treat a period tell as “about the owner.”
    """
    asked_ids = [str(p) for p in (getattr(plan, "person_ids", ()) or ()) if p]
    asked_names = [
        str(n).strip()
        for n in (getattr(plan, "person_names", ()) or ())
        if str(n).strip()
    ]
    if asked_ids or asked_names:
        return asked_ids, None
    try:
        from memorybox.profile.owner import get_requestor_person_id

        rid = get_requestor_person_id()
    except Exception:  # noqa: BLE001
        rid = None
    if rid:
        return [str(rid)], str(rid)
    return [], None


def _apply_result_limit(items: list[Any], limit: int | None) -> list[Any]:
    """Slice only when a caller asked for a page. 0/None is not 'return nothing'."""
    if limit is None or int(limit) <= 0:
        return list(items)
    return list(items)[: int(limit)]


def _provider_fetch_n(limit: int | None) -> int:
    """SQL/provider page size under processing capacity — not a consider-cap."""
    if limit is None or int(limit) <= 0:
        return 500_000
    return max(1, int(limit))


def _iter_evidence_rows(where_sql: str, params: list[Any]):
    """Page through Evidence. Page size is not a consider-cap."""
    offset = 0
    with connection() as conn:
        while True:
            rows = conn.execute(
                f"""
                SELECT id, evidence_kind, summary, payload_json
                FROM evidence
                WHERE {where_sql}
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                list(params) + [TELL_DB_PAGE, offset],
            ).fetchall()
            if not rows:
                break
            for r in rows:
                yield r
            if len(rows) < TELL_DB_PAGE:
                break
            offset += TELL_DB_PAGE


def _sql_json_day_windows(
    windows: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...],
    json_key: str,
) -> tuple[str, list[Any]]:
    """Inclusive YYYY-MM-DD windows on a JSON text timestamp field."""
    if json_key not in {"sent_at", "start"}:
        return "TRUE", []
    if not windows:
        return "TRUE", []
    parts: list[str] = []
    params: list[Any] = []
    expr = f"left(coalesce(payload_json->>'{json_key}', ''), 10)"
    for a, b in windows:
        parts.append(f"({expr} BETWEEN %s AND %s)")
        params.extend([str(a)[:10], str(b)[:10]])
    return "(" + " OR ".join(parts) + ")", params


def _strip_temporal_tell_keywords(keywords: list[str], *, windows: list) -> list[str]:
    out = list(keywords)
    if windows:
        out = [k for k in out if not re.fullmatch(r"(?:19|20)\d{2}", k)]
        out = [k for k in out if k not in _MONTH_KEYWORD_STOP and k not in _TELL_KEYWORD_STOP]
    return out


def _place_trip_keywords(plan: QueryPlan) -> list[str]:
    """Place/trip tokens that must survive a dated tell (not a year dump)."""
    names: list[str] = []
    for n in list(getattr(plan, "trip_labels", ()) or ()) + list(
        getattr(plan, "place_names", ()) or ()
    ):
        if n:
            names.append(str(n))
    stop = {
        "the",
        "and",
        "our",
        "trip",
        "my",
        "a",
        "an",
        "to",
        "in",
    }
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        low = name.lower().strip()
        if not low or low in stop:
            continue
        if low not in seen:
            seen.add(low)
            out.append(low)
        for tok in re.findall(r"[a-z0-9']{4,}", low):
            # Drop 3-letter splits ("las" from Las Vegas) — they false-hit unrelated mail.
            if tok in stop or tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
        try:
            from memorybox.ask.place_match import geo_tokens_for_label, trip_hint_tokens

            for tok in geo_tokens_for_label(low):
                if tok in seen:
                    continue
                seen.add(tok)
                out.append(tok)
            for tok in trip_hint_tokens(low):
                if tok in seen:
                    continue
                seen.add(tok)
                out.append(tok)
        except Exception:  # noqa: BLE001
            pass
    return out


def _sms_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    atts = [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]
    if atts:
        return atts
    meta = payload.get("source_metadata") or {}
    if not isinstance(meta, dict):
        return []
    raw = str(meta.get("Attachment") or meta.get("attachment") or "").strip()
    if not raw:
        return []
    kind = str(meta.get("Attachment type") or meta.get("attachment_type") or "").strip()
    name = raw.replace("\\", "/").rstrip("/").split("/")[-1] or raw
    return [
        {
            "filename": name,
            "source_ref": raw,
            "attachment_type": kind or None,
            "promoted_to_immich": False,
            "standalone_explore_media": False,
            "from_source_metadata": True,
        }
    ]


def _sms_name_match(blob: str, names: list[str], *, allow_first_token: bool = False) -> bool:
    """Match display names on a participant blob.

    P2-BL-I8-02: a single first-name token must not union every matching person.
    Unique Person lock supplies person_ids; full display names may still match.
    """
    text = (blob or "").lower()
    if not text or not names:
        return False
    for n in names:
        if not n:
            continue
        parts = [p for p in re.findall(r"[a-z0-9']+", n) if len(p) > 2]
        if len(parts) >= 2:
            if n in text or (text.strip() and text.strip() in n):
                return True
            if all(re.search(rf"\b{re.escape(p)}\b", text) for p in parts):
                return True
            if allow_first_token and re.search(rf"\b{re.escape(parts[0])}\b", text):
                return True
            continue
        if allow_first_token and parts and re.search(rf"\b{re.escape(parts[0])}\b", text):
            return True
    return False


def _sms_has_heart(payload: dict[str, Any], summary: str = "") -> bool:
    blob = f"{summary} {payload.get('body_text') or ''}"
    meta = payload.get("source_metadata") or {}
    if isinstance(meta, dict):
        for key, val in meta.items():
            if re.search(r"(?i)react|tapback|loved|heart", str(key)):
                blob += f" {val}"
        blob += " " + str(meta.get("Reactions") or meta.get("Reaction") or "")
        blob += " " + str(meta.get("Tapback") or "")
    return bool(_HEART_MARK_RE.search(blob))


def _sms_sender_matches_person(
    payload: dict[str, Any],
    *,
    person_ids: set[str],
    person_names: list[str],
) -> bool:
    sender = str(payload.get("sender_name") or "").strip().lower()
    handle = str(payload.get("sender_handle") or "").strip().lower()
    if person_names and _sms_name_match(
        f"{sender} {handle}", person_names, allow_first_token=True
    ):
        return True
    mapped = (payload.get("identity_resolution") or {}).get("mapped") or []
    for m in mapped:
        if not isinstance(m, dict):
            continue
        pid = str(m.get("person_id") or "")
        h = str(m.get("handle") or m.get("normalized") or "").lower()
        if person_ids and pid in person_ids and h and (h in handle or handle in h or h in sender):
            return True
    if person_ids and not payload.get("from_owner"):
        have = {str(x) for x in (payload.get("person_ids") or [])}
        participants = [str(p).strip() for p in (payload.get("participants") or []) if str(p).strip()]
        if have & person_ids and len(participants) <= 3:
            return True
    return False


def _sms_hit(row: dict[str, Any], payload: dict[str, Any], *, score: float) -> EvidenceHit:
    people = [
        str(p)
        for p in (payload.get("participants") or [])
        if str(p).strip() and str(p).strip().lower() not in _SMS_FAKE_PEOPLE
    ]
    if payload.get("sender_name") and payload["sender_name"] not in people:
        people.insert(0, str(payload["sender_name"]))
    mapped = (payload.get("identity_resolution") or {}).get("mapped") or []
    identity = [
        {
            "handle": str(m.get("handle") or m.get("normalized") or ""),
            "normalized": str(m.get("normalized") or ""),
            "person_id": str(m.get("person_id") or ""),
            "status": str(m.get("status") or "auto_mapped"),
        }
        for m in mapped
        if isinstance(m, dict) and (m.get("handle") or m.get("normalized"))
    ]
    return EvidenceHit(
        evidence_id=str(row["id"]),
        evidence_kind=row["evidence_kind"],
        summary=row["summary"] or (payload.get("body_text") or "text message")[:80],
        score=score,
        excerpt=_excerpt(payload, row["evidence_kind"], limit=800),
        source="sms_export",
        sent_at=payload.get("sent_at"),
        channel=str(payload.get("evidence_channel") or payload.get("service") or "text"),
        people=people or None,
        thread_id=(
            payload.get("thread_id")
            or payload.get("chat_identifier")
            or payload.get("chat_id")
            or payload.get("handle")
            or payload.get("group_name")
        ),
        direction=payload.get("direction"),
        attachments=_sms_attachments(payload) or None,
        identity_mapped=identity or None,
    )


def _year_fair_slice(hits: list[EvidenceHit], limit: int) -> tuple[list[EvidenceHit], bool]:
    """Keep every year represented when a retrieve cap would otherwise drop recent texts."""
    cap = max(1, int(limit))
    if len(hits) <= cap:
        return hits, False
    by_year: dict[str, list[EvidenceHit]] = {}
    for h in hits:
        year = (h.sent_at or "")[:4] or "undated"
        by_year.setdefault(year, []).append(h)
    years = sorted(by_year)
    min_per = max(24, cap // max(len(years), 1))
    selected: list[EvidenceHit] = []
    leftovers: list[EvidenceHit] = []
    budget = cap
    for year in years:
        group = sorted(
            by_year[year],
            key=lambda h: (h.sent_at or "", h.evidence_id),
            reverse=True,
        )
        take = min(len(group), min_per, budget)
        selected.extend(group[:take])
        leftovers.extend(group[take:])
        budget -= take
        if budget <= 0:
            break
    leftovers.sort(key=lambda h: (h.sent_at or "", h.evidence_id), reverse=True)
    if budget > 0:
        selected.extend(leftovers[:budget])
    selected.sort(key=lambda h: (h.sent_at or "", h.evidence_id))
    return selected, True


def search_sms_messages(plan: QueryPlan, *, limit: int = SMS_RETRIEVE_CAP) -> list[EvidenceHit]:
    """Person / date / keyword retrieve over ingested SMS/iMessage Evidence."""
    from memorybox.person.phone_map import normalize_handle

    ask = plan.original_ask or ""
    want_count = bool(SMS_COUNT_RE.search(ask))
    outbound_only = bool(SMS_OUTBOUND_RE.search(ask))
    inbound_only = bool(SMS_INBOUND_RE.search(ask)) and not outbound_only
    attach_only = bool(SMS_ATTACH_ASK_RE.search(ask))
    heart_only = bool(SMS_HEART_ASK_RE.search(ask))
    last_n_m = SMS_LAST_N_RE.search(ask)
    last_n = int(last_n_m.group(1)) if last_n_m else None
    if last_n is not None and last_n < 1:
        last_n = None
    person_ids = {str(p) for p in (plan.person_ids or ()) if p}
    person_names = [
        n.strip().lower()
        for n in (plan.person_names or ())
        if n.strip() and n.strip().lower() not in _SMS_FAKE_PEOPLE
    ]
    name_tokens = {
        tok
        for n in person_names
        for tok in re.findall(r"[a-z0-9']{2,}", n)
    }
    windows = list(plan.temporal_windows or ())
    if not windows and plan.time_start and plan.time_end:
        windows = [(plan.time_start, plan.time_end)]
    keyword_stop = {
        "the", "and", "for", "with", "from", "that", "this", "show", "me",
        "just", "ones", "what", "else", "have", "how", "many", "times",
        "did", "text", "texts", "texted", "sms", "imessage", "message",
        "messages", "all", "my", "each", "other", "sent", "send", "total",
        "summarize", "summary",
        "everything", "about", "have",
    } | _SMS_KEYWORD_EXTRA_STOP | name_tokens | set(person_names)
    keywords = [
        t.lower().replace("'", "")
        for t in re.findall(r"[A-Za-z0-9']{3,}", ask)
        if t.lower().replace("'", "") not in keyword_stop
    ]
    keywords = _strip_temporal_tell_keywords(keywords, windows=windows)
    if _tell_pack_comms(plan) and windows:
        # Dated tell is a window, not a hunt for "narrative" — exclusive place
        # keywords wait until trip discovery has a resolved window.
        keywords = _exclusive_place_trip_keywords(plan)
    if last_n is not None:
        keywords = [k for k in keywords if not re.fullmatch(r"\d+", k)]
    if heart_only or attach_only:
        keywords = [
            k
            for k in keywords
            if k not in {"hear", "heart", "emoji", "emojis", "attachment", "attachments"}
            and not k.startswith(("emoji", "hear", "heart", "attach"))
        ]
    holiday_ask = bool(
        re.search(
            r"(?i)\b(christmas|xmas|thanksgiving|easter|halloween|"
            r"nye|nyd|holiday|memorial\s+day|labor\s+day|juneteenth)\b",
            ask,
        )
        or "temporal=holiday" in (plan.notes or ())
        or "christmas_window" in " ".join(plan.notes or ())
    )
    if holiday_ask:
        holiday_stop = {
            "christmas",
            "xmas",
            "christmastime",
            "season",
            "time",
            "holiday",
            "thanksgiving",
            "easter",
            "halloween",
            "during",
            "around",
        }
        keywords = [k for k in keywords if k not in holiday_stop]

    hits: list[EvidenceHit] = []
    seen_sms_sig: set[tuple[str, str, str]] = set()
    if (
        _tell_pack_comms(plan)
        and not windows
        and not person_ids
        and not person_names
        and last_n is None
    ):
        return []
    win_sql, win_params = _sql_json_day_windows(windows, "sent_at")
    where_sql = (
        "evidence_kind = 'communication' "
        "AND lower(coalesce(payload_json->>'evidence_channel', '')) "
        "IN ('sms', 'text', 'imessage', 'mms', 'rcs') "
        f"AND {win_sql}"
    )
    for r in _iter_evidence_rows(where_sql, list(win_params)):
        payload = _payload_dict(r["payload_json"])
        ch = str(payload.get("evidence_channel") or payload.get("service") or "").lower()
        if ch not in _SMS_CHANNELS:
            continue
        if outbound_only and not payload.get("from_owner"):
            continue
        if inbound_only:
            if payload.get("from_owner"):
                continue
            if (person_ids or person_names) and not _sms_sender_matches_person(
                payload, person_ids=person_ids, person_names=person_names
            ):
                continue
        sent = str(payload.get("sent_at") or "")
        if windows:
            day = sent[:10]
            if not day or not any(str(a)[:10] <= day <= str(b)[:10] for a, b in windows):
                continue
        if person_ids:
            have = {str(x) for x in (payload.get("person_ids") or [])}
            if not (have & person_ids):
                # name fallback on participants / thread
                blob = " ".join(
                    [
                        str(payload.get("sender_name") or ""),
                        str(payload.get("thread_id") or ""),
                        " ".join(str(p) for p in (payload.get("participants") or [])),
                    ]
                ).lower()
                if person_names and not _sms_name_match(
                    blob, person_names, allow_first_token=True
                ):
                    continue
                if not person_names:
                    continue
        elif person_names:
            blob = " ".join(
                [
                    str(payload.get("sender_name") or ""),
                    str(payload.get("thread_id") or ""),
                    str(payload.get("group_name") or ""),
                    " ".join(str(p) for p in (payload.get("participants") or [])),
                ]
            ).lower()
            handles = " ".join(
                normalize_handle(str(p)) for p in (payload.get("participants") or [])
            )
            if not _sms_name_match(
                f"{blob} {handles}", person_names, allow_first_token=True
            ):
                continue
        # "Peggy and I send" = messages Peggy or the owner sent, not a third sender
        # in a group that merely includes Peggy.
        if (person_ids or person_names) and re.search(
            r"(?i)\band i\b|\bi and\b|\band me\b", ask
        ):
            if not (
                payload.get("from_owner")
                or _sms_sender_matches_person(
                    payload, person_ids=person_ids, person_names=person_names
                )
            ):
                continue
        if attach_only and not _sms_attachments(payload):
            continue
        if heart_only and not _sms_has_heart(payload, str(r["summary"] or "")):
            continue
        if keywords:
            blob = f"{r['summary'] or ''} {payload.get('body_text') or ''} {payload.get('thread_id') or ''}".lower()
            if not any(k in blob for k in keywords):
                continue
        sig = (
            str(
                payload.get("thread_id")
                or payload.get("chat_identifier")
                or payload.get("handle")
                or ""
            ),
            str(payload.get("sent_at") or ""),
            re.sub(r"\s+", " ", str(payload.get("body_text") or "")).strip().lower(),
        )
        if sig[2] and sig in seen_sms_sig:
            continue
        if sig[2]:
            seen_sms_sig.add(sig)
        hits.append(_sms_hit(r, payload, score=1.0))
    hits.sort(key=lambda h: (h.sent_at or "", h.evidence_id))
    if _bounded_period_tell(plan):
        total = len(hits)
        for h in hits:
            h.match_total = total
            h.truncated = False
        if hits:
            hits[0].count_scope = f"bounded_tell_sms; processed={total}; eligible={total}"
        return hits
    scope_bits = [
        "ingested SMS/iMessage/MMS export",
        f"n={len(hits)}",
    ]
    if person_names:
        scope_bits.append("person=" + ", ".join(n for n in plan.person_names if str(n).lower() not in _SMS_FAKE_PEOPLE))
    if windows:
        scope_bits.append("dates=" + ";".join(f"{a[:10]}..{b[:10]}" for a, b in windows))
    if outbound_only:
        scope_bits.append("outbound_only")
    if inbound_only:
        scope_bits.append("inbound_only")
    if attach_only:
        scope_bits.append("attachments_only")
    if heart_only:
        scope_bits.append("heart_emoji_or_loved_tapback")
    if last_n is not None:
        scope_bits.append(f"last_{last_n}_newest")
    if keywords:
        scope_bits.append("keyword=" + ",".join(keywords))
    scope = "; ".join(scope_bits)
    total = len(hits)
    if last_n is not None:
        newest = sorted(hits, key=lambda h: (h.sent_at or "", h.evidence_id), reverse=True)
        sliced = list(reversed(newest[: last_n]))
        truncated = total > len(sliced)
        if truncated:
            scope = f"{scope}; showing newest {len(sliced)} of {total}"
    else:
        sliced, truncated = _year_fair_slice(hits, max(1, int(limit)))
        if truncated:
            years = sorted({(h.sent_at or "")[:4] for h in sliced if (h.sent_at or "")[:4]})
            scope = (
                f"{scope}; showing {len(sliced)} of {total} "
                f"(year-fair sample; years {years[0] if years else '?'}–{years[-1] if years else '?'})"
            )
    if sliced:
        sliced[0].count_scope = scope
        sliced[0].match_total = total
        sliced[0].truncated = truncated
        if want_count:
            label = "heart emoji / Loved tapbacks" if heart_only else "text messages"
            sliced[0].summary = f"{total} {label} ({scope}). {sliced[0].summary}"
        elif last_n is not None:
            sliced[0].summary = (
                f"Last {len(sliced)} of {total} text messages ({scope}). "
                f"{sliced[0].summary}"
            )
        elif truncated:
            sliced[0].summary = (
                f"Showing {len(sliced)} of {total} text messages ({scope}). "
                f"{sliced[0].summary}"
            )
        for h in sliced:
            h.match_total = total
            h.truncated = truncated
            h.count_scope = scope
    return sliced


def _payload_email_addresses(payload: dict[str, Any]) -> set[str]:
    from memorybox.person.phone_map import normalize_handle

    out: set[str] = set()
    for rec in (
        list(payload.get("from_parsed") or [])
        + list(payload.get("to_parsed") or [])
        + list(payload.get("cc_parsed") or [])
    ):
        if not isinstance(rec, dict):
            continue
        n = normalize_handle(str(rec.get("normalized") or rec.get("address") or ""))
        if n and "@" in n:
            out.add(n)
    return out


def _confirmed_emails_for_people(person_ids: set[str]) -> set[str]:
    from memorybox.person.phone_map import normalize_handle

    ids = [str(p) for p in person_ids if str(p).strip()]
    if not ids:
        return set()
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT value_text
                FROM person_contact_points
                WHERE contact_kind = 'email'
                  AND status = 'confirmed'
                  AND person_id::text = ANY(%s)
                """,
                (ids,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    for r in rows:
        n = normalize_handle(str(r.get("value_text") or ""))
        if n and "@" in n:
            out.add(n)
    return out


def _asked_person_is_owner(plan: QueryPlan) -> bool:
    try:
        from memorybox.profile.owner import get_owner_person_id
    except Exception:  # noqa: BLE001
        return False
    oid = get_owner_person_id()
    if not oid:
        return False
    if str(oid) in {str(p) for p in (plan.person_ids or ()) if p}:
        return True
    asked = {str(n).strip().lower() for n in (plan.person_names or ()) if str(n).strip()}
    if not asked:
        return False
    try:
        with connection() as conn:
            row = conn.execute(
                "SELECT display_name FROM people WHERE id = %s",
                (oid,),
            ).fetchone()
    except Exception:  # noqa: BLE001
        return False
    dn = str((row or {}).get("display_name") or "").strip().lower()
    if not dn:
        return False
    if dn in asked:
        return True
    first = dn.split()[0]
    return first in asked and len(first) > 2


def _email_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (payload.get("attachments") or []) if isinstance(a, dict)]


def _email_hit(row: dict[str, Any], payload: dict[str, Any], *, score: float) -> EvidenceHit:
    people = [str(p) for p in (payload.get("people") or []) if str(p).strip()]
    mapped = (payload.get("identity_resolution") or {}).get("mapped") or []
    identity = [
        {
            "handle": str(m.get("handle") or m.get("normalized") or ""),
            "normalized": str(m.get("normalized") or ""),
            "person_id": str(m.get("person_id") or ""),
            "status": str(m.get("status") or "auto_mapped"),
        }
        for m in mapped
        if isinstance(m, dict) and (m.get("handle") or m.get("normalized"))
    ]
    return EvidenceHit(
        evidence_id=str(row["id"]),
        evidence_kind=row["evidence_kind"],
        summary=row["summary"] or (payload.get("subject") or "email")[:80],
        score=score,
        excerpt=_excerpt(payload, row["evidence_kind"], limit=800),
        source="email_mbox",
        sent_at=payload.get("sent_at"),
        channel="email",
        people=people or None,
        thread_id=payload.get("thread_id"),
        direction=payload.get("direction"),
        attachments=_email_attachments(payload) or None,
        identity_mapped=identity or None,
        from_header=(str(payload.get("from") or "").strip() or None),
        to_header=_fmt_addr_header(payload.get("to")),
    )


def _fmt_addr_header(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        bits = [str(x).strip() for x in val if str(x).strip()]
        return ", ".join(bits)[:160] or None
    s = str(val).strip()
    return s[:160] if s else None


def _email_person_blob(payload: dict[str, Any]) -> str:
    bits = [
        str(payload.get("from") or ""),
        str(payload.get("from_raw") or ""),
        " ".join(str(t) for t in (payload.get("to") or [])),
        " ".join(str(p) for p in (payload.get("people") or [])),
    ]
    for rec in list(payload.get("from_parsed") or []) + list(payload.get("to_parsed") or []):
        if isinstance(rec, dict):
            bits.append(str(rec.get("display_name") or ""))
            bits.append(str(rec.get("address") or ""))
            bits.append(str(rec.get("normalized") or ""))
    mapped = (payload.get("identity_resolution") or {}).get("mapped") or []
    for m in mapped:
        if isinstance(m, dict):
            bits.append(str(m.get("handle") or ""))
            bits.append(str(m.get("normalized") or ""))
    return " ".join(bits).lower()


def search_email_messages(plan: QueryPlan, *, limit: int = SMS_RETRIEVE_CAP) -> list[EvidenceHit]:
    """Person / date / keyword retrieve over ingested email Evidence."""
    ask = plan.original_ask or ""
    want_count = bool(EMAIL_COUNT_RE.search(ask))
    outbound_only = bool(EMAIL_OUTBOUND_RE.search(ask))
    inbound_only = bool(EMAIL_INBOUND_RE.search(ask)) and not outbound_only
    attach_only = bool(EMAIL_ATTACH_ASK_RE.search(ask))
    thread_open = bool(EMAIL_THREAD_RE.search(ask))
    person_ids = {str(p) for p in (plan.person_ids or ()) if p}
    from memorybox.ingest.comms_email import owner_emails

    owner_addrs = owner_emails()
    asked_owner = _asked_person_is_owner(plan)
    confirmed_addrs = _confirmed_emails_for_people(person_ids)
    person_names = [
        n.strip().lower()
        for n in (plan.person_names or ())
        if n.strip() and n.strip().lower() not in _EMAIL_FAKE_PEOPLE
    ]
    name_tokens = {tok for n in person_names for tok in re.findall(r"[a-z0-9']{2,}", n)}
    windows = list(plan.temporal_windows or ())
    if not windows and plan.time_start and plan.time_end:
        windows = [(plan.time_start, plan.time_end)]
    keyword_stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "show",
        "me",
        "just",
        "ones",
        "what",
        "else",
        "have",
        "how",
        "many",
        "times",
        "did",
        "email",
        "emails",
        "e-mail",
        "e-mails",
        "mail",
        "inbox",
        "all",
        "my",
        "each",
        "other",
        "sent",
        "send",
        "total",
        "summarize",
        "summary",
        "respond",
        "responded",
        "replied",
        "thread",
        "replies",
        "any",
        "about",
        "everything",
        "have",
    } | name_tokens | set(person_names)
    keywords = [
        t.lower().replace("'", "")
        for t in re.findall(r"[A-Za-z0-9']{3,}", ask)
        if t.lower().replace("'", "") not in keyword_stop
    ]
    keywords = _strip_temporal_tell_keywords(keywords, windows=windows)
    if _tell_pack_comms(plan) and windows:
        # Dated tell is a window, not a hunt for "narrative" — exclusive place
        # keywords wait until trip discovery has a resolved window.
        keywords = _exclusive_place_trip_keywords(plan)
    holiday_ask = bool(
        re.search(
            r"(?i)\b(christmas|xmas|thanksgiving|easter|halloween|"
            r"nye|nyd|holiday|memorial\s+day|labor\s+day|juneteenth)\b",
            ask,
        )
        or "temporal=holiday" in (plan.notes or ())
        or "christmas_window" in " ".join(plan.notes or ())
    )
    if holiday_ask:
        keywords = [
            k
            for k in keywords
            if k
            not in {
                "christmas",
                "xmas",
                "christmastime",
                "season",
                "time",
                "holiday",
                "thanksgiving",
                "easter",
                "halloween",
                "during",
                "around",
                "coordinate",
                "coordinated",
            }
        ]

    rows_payload: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if (
        _tell_pack_comms(plan)
        and not windows
        and not person_ids
        and not person_names
    ):
        return []
    win_sql, win_params = _sql_json_day_windows(windows, "sent_at")
    where_sql = (
        "evidence_kind = 'communication' "
        "AND lower(coalesce(payload_json->>'evidence_channel', 'email')) "
        "NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs') "
        f"AND {win_sql}"
    )
    for r in _iter_evidence_rows(where_sql, list(win_params)):
        payload = _payload_dict(r["payload_json"])
        if str(payload.get("evidence_channel") or "email").lower() != "email":
            continue
        skip = str(payload.get("mailbox_skip") or payload.get("skip_reason") or "").strip().lower()
        if skip in {"spam", "trash"}:
            continue
        rows_payload.append((r, payload))

    def _keep(payload: dict[str, Any], row: dict[str, Any]) -> bool:
        owner_intent = asked_owner or bool(
            re.search(r"(?i)\b(i|me|my)\b", plan.original_ask or "")
        )
        if outbound_only and not payload.get("from_owner") and not owner_intent:
            return False
        if inbound_only and payload.get("from_owner"):
            return False
        sent = str(payload.get("sent_at") or "")
        if windows:
            day = sent[:10]
            if not day or not any(str(a)[:10] <= day <= str(b)[:10] for a, b in windows):
                return False
        if person_ids or person_names:
            have = {str(x) for x in (payload.get("person_ids") or [])}
            addrs = _payload_email_addresses(payload)
            mapped_ids = {
                str(m.get("person_id"))
                for m in ((payload.get("identity_resolution") or {}).get("mapped") or [])
                if isinstance(m, dict) and m.get("person_id")
            }
            if person_ids and (have & person_ids or mapped_ids & person_ids):
                pass
            elif confirmed_addrs and (addrs & confirmed_addrs):
                pass
            elif asked_owner and (
                payload.get("from_owner")
                or (owner_addrs and (addrs & owner_addrs))
                or (asked_owner and not owner_addrs and not confirmed_addrs)
            ):
                # Owner Person + personal Takeout: mailbox is theirs even when
                # MEMORYBOX_OWNER_EMAIL / confirmed contacts are not set.
                pass
            elif (
                person_names
                and _sms_name_match(
                    _email_person_blob(payload),
                    person_names,
                    allow_first_token=False,
                )
            ):
                # Full display-name match even when Person ids are set.
                # Ingest often leaves person_ids empty on email rows; unique
                # Person lock still supplies person_names (P2-BL-I8-02).
                pass
            else:
                return False
        if attach_only and not _email_attachments(payload):
            return False
        if keywords:
            blob = (
                f"{row['summary'] or ''} {payload.get('subject') or ''} "
                f"{payload.get('body_text') or ''} {payload.get('thread_id') or ''}"
            ).lower()
            if not any(k in blob for k in keywords):
                return False
        return True

    matched: list[EvidenceHit] = []
    for r, payload in rows_payload:
        if _keep(payload, r):
            matched.append(_email_hit(r, payload, score=1.0))
    if thread_open:
        thread_ids = {h.thread_id for h in matched if h.thread_id}
        if thread_ids:
            extra: list[EvidenceHit] = []
            have = {h.evidence_id for h in matched}
            for r, payload in rows_payload:
                tid = payload.get("thread_id")
                if tid in thread_ids and str(r["id"]) not in have:
                    extra.append(_email_hit(r, payload, score=0.8))
            matched.extend(extra)
    hits = matched
    hits.sort(key=lambda h: (h.sent_at or "", h.evidence_id))
    if _bounded_period_tell(plan):
        total = len(hits)
        for h in hits:
            h.match_total = total
            h.truncated = False
        if hits:
            hits[0].count_scope = f"bounded_tell_email; processed={total}; eligible={total}"
        return hits
    scope_bits = [
        "ingested email export",
        f"n={len(hits)}",
    ]
    if person_names:
        scope_bits.append(
            "person="
            + ", ".join(n for n in plan.person_names if str(n).lower() not in _EMAIL_FAKE_PEOPLE)
        )
    if windows:
        scope_bits.append("dates=" + ";".join(f"{a[:10]}..{b[:10]}" for a, b in windows))
    if outbound_only:
        scope_bits.append("outbound_only")
    if inbound_only:
        scope_bits.append("inbound_only")
    if attach_only:
        scope_bits.append("attachments_only")
    if thread_open:
        scope_bits.append("thread_open_rfc_or_vendor_only")
    if keywords:
        scope_bits.append("keyword=" + ",".join(keywords))
    unthreaded_n = sum(1 for h in hits if not h.thread_id)
    if unthreaded_n:
        scope_bits.append(f"unthreaded={unthreaded_n}")
    scope = "; ".join(scope_bits)
    total = len(hits)
    sliced, truncated = _year_fair_slice(hits, max(1, int(limit)))
    if truncated:
        years = sorted({(h.sent_at or "")[:4] for h in sliced if (h.sent_at or "")[:4]})
        scope = (
            f"{scope}; showing {len(sliced)} of {total} "
            f"(year-fair sample; years {years[0] if years else '?'}–{years[-1] if years else '?'})"
        )
    if sliced:
        sliced[0].count_scope = scope
        sliced[0].match_total = total
        sliced[0].truncated = truncated
        if want_count:
            sliced[0].summary = f"{total} emails ({scope}). {sliced[0].summary}"
        elif truncated:
            sliced[0].summary = (
                f"Showing {len(sliced)} of {total} emails ({scope}). {sliced[0].summary}"
            )
        for h in sliced:
            h.match_total = total
            h.truncated = truncated
            h.count_scope = scope
    return sliced


def search_calendar_events(plan: QueryPlan, *, limit: int = SMS_RETRIEVE_CAP) -> list[EvidenceHit]:
    """Person / date retrieve over ingested calendar_event Evidence."""
    person_ids = {str(p) for p in (plan.person_ids or ()) if p}
    person_names = [
        n.strip().lower()
        for n in (plan.person_names or ())
        if n.strip()
    ]
    confirmed_addrs = _confirmed_emails_for_people(person_ids) if person_ids else set()
    windows = list(plan.temporal_windows or ())
    if not windows and plan.time_start and plan.time_end:
        windows = [(plan.time_start, plan.time_end)]
    hits: list[EvidenceHit] = []
    if _tell_pack_comms(plan) and not windows and not person_ids and not person_names:
        return []
    win_sql, win_params = _sql_json_day_windows(windows, "start")
    where_sql = f"evidence_kind = 'calendar_event' AND {win_sql}"
    for r in _iter_evidence_rows(where_sql, list(win_params)):
        payload = _payload_dict(r["payload_json"])
        start = str(payload.get("start") or "")
        day = start[:10]
        if windows:
            if not day or not any(str(a)[:10] <= day <= str(b)[:10] for a, b in windows):
                continue
        blob = " ".join(
            [
                str(payload.get("title") or ""),
                str(payload.get("summary") or ""),
                str(payload.get("description") or ""),
                str(payload.get("location") or ""),
                str(payload.get("organizer") or ""),
                " ".join(str(a) for a in (payload.get("attendees") or [])),
            ]
        ).lower()
        if person_ids or person_names:
            have = {str(x) for x in (payload.get("person_ids") or [])}
            if person_ids and (have & person_ids):
                pass
            elif person_names and _sms_name_match(blob, person_names, allow_first_token=False):
                pass
            elif confirmed_addrs and any(a in blob for a in confirmed_addrs):
                pass
            elif not person_ids and not person_names:
                pass
            elif person_ids and not (have & person_ids) and not person_names:
                continue
            elif person_names and not _sms_name_match(blob, person_names, allow_first_token=False):
                if not (person_ids and (have & person_ids)):
                    continue
        place_trip = _exclusive_place_trip_keywords(plan)
        if _tell_pack_comms(plan) and place_trip:
            if not any(k in blob for k in place_trip):
                continue
        people = [str(a) for a in (payload.get("attendees") or []) if str(a).strip()]
        org = str(payload.get("organizer") or "").strip()
        if org and org not in people:
            people.insert(0, org)
        hits.append(
            EvidenceHit(
                evidence_id=str(r["id"]),
                evidence_kind="calendar_event",
                summary=str(payload.get("title") or r["summary"] or "Calendar"),
                score=1.0,
                excerpt=str(payload.get("description") or payload.get("location") or "")[:240],
                source="ics",
                sent_at=start or None,
                channel="calendar",
                people=people or None,
                thread_id=str(payload.get("event_uid") or "") or None,
            )
        )
    hits.sort(key=lambda h: (h.sent_at or "", h.evidence_id))
    total = len(hits)
    if _bounded_period_tell(plan):
        for h in hits:
            h.match_total = total
            h.truncated = False
        if hits:
            hits[0].count_scope = f"bounded_tell_calendar; processed={total}; eligible={total}"
        return hits
    cap_n = max(1, int(limit))
    sliced = hits[:cap_n] if hits else []
    truncated = total > len(sliced)
    if sliced:
        sliced[0].match_total = total
        sliced[0].truncated = truncated
        sliced[0].count_scope = f"ingested calendar_event; n={total}"
        for h in sliced:
            h.match_total = total
            h.truncated = truncated
    return sliced


def search_evidence_pg(plan: QueryPlan, *, limit: int = 20) -> list[EvidenceHit]:
    """Keyword search over authoritative PostgreSQL Evidence (always available)."""
    sms_q = _sms_ask(plan) and plan.want_communication
    email_q = _email_ask(plan) and plan.want_communication
    cal_q = bool(plan.want_calendar)
    if _tell_pack_comms(plan) and plan.want_communication and not sms_q and not email_q:
        mail = search_email_messages(plan)
        sms = search_sms_messages(plan)
        cal = search_calendar_events(plan) if cal_q else []
        combined = list(mail) + list(sms) + list(cal)
        if combined:
            combined[0].count_scope = (
                f"tell pack; email_n={mail[0].match_total if mail else 0}; "
                f"sms_n={sms[0].match_total if sms else 0}; "
                f"cal_n={len(cal)}"
            )
            combined[0].match_total = (
                (mail[0].match_total if mail else 0)
                + (sms[0].match_total if sms else 0)
                + len(cal)
            )
        return combined
    if cal_q and not sms_q and not email_q:
        return search_calendar_events(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
    if sms_q and email_q:
        sms = search_sms_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        mail = search_email_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        combined = list(mail) + list(sms)
        if cal_q:
            combined.extend(search_calendar_events(plan, limit=max(int(limit), SMS_RETRIEVE_CAP)))
        if combined:
            scope = (
                f"email+sms; email_n={mail[0].match_total if mail else 0}; "
                f"sms_n={sms[0].match_total if sms else 0}; "
                "I8 retrieves email; I7 retrieves texts; no joint narrative"
            )
            combined[0].count_scope = scope
            combined[0].match_total = (mail[0].match_total if mail else 0) + (
                sms[0].match_total if sms else 0
            )
        return combined
    if sms_q:
        sms = search_sms_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        if cal_q:
            sms = list(sms) + list(search_calendar_events(plan, limit=max(int(limit), SMS_RETRIEVE_CAP)))
        # SMS-specific asks stay on the SMS corpus (do not pad with email keyword dump).
        if sms or sms_q:
            return sms
    if email_q:
        mail = search_email_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        if cal_q:
            mail = list(mail) + list(search_calendar_events(plan, limit=max(int(limit), SMS_RETRIEVE_CAP)))
        return mail
    kinds: list[str] = []
    if plan.want_communication:
        kinds.append("communication")
    if plan.want_calendar:
        kinds.append("calendar_event")
    if not kinds:
        return []

    terms: list[str] = []
    # Rule G: prefer explicit retrieval constraints when present
    for name in plan.retrieval_constraints or ():
        terms.append(name)
    for name in plan.person_names:
        terms.append(name)
    for name in plan.place_names:
        terms.append(name)
    for name in plan.trip_labels:
        terms.append(name)
    for name in plan.event_labels:
        if name.lower().startswith("trip:"):
            terms.append(name.split(":", 1)[1])
        else:
            terms.append(name)
    for name in getattr(plan, "theme_labels", ()) or ():
        terms.append(name)
    # tokens from original ask (drop tiny words)
    for tok in re.findall(r"[A-Za-z0-9']{3,}", plan.original_ask):
        if tok.lower() not in {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "show",
            "me",
            "just",
            "ones",
            "what",
            "else",
            "have",
            "happened",
            "after",
            "right",
            "pictures",
            "photos",
            "emails",
            "email",
            "calendar",
        }:
            terms.append(tok)
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for t in terms:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    if not uniq:
        uniq = ["a"]  # fall through to recent evidence of requested kinds

    hits: list[EvidenceHit] = []
    with connection() as conn:
        clauses = []
        params: list[Any] = []
        for t in uniq[:12]:
            like = f"%{t}%"
            clauses.append("(summary ILIKE %s OR payload_json::text ILIKE %s)")
            params.extend([like, like])
        where_terms = " OR ".join(clauses) if clauses else "TRUE"
        kind_ph = ",".join(["%s"] * len(kinds))
        sql = f"""
            SELECT id, evidence_kind, summary, payload_json
            FROM evidence
            WHERE evidence_kind IN ({kind_ph})
              AND ({where_terms})
            ORDER BY created_at DESC
            LIMIT %s
        """
        params = list(kinds) + params + [limit * 3]
        rows = conn.execute(sql, params).fetchall()
        scored: list[EvidenceHit] = []
        distinctive = [t for t in uniq if len(t) >= 4]
        # Capitalized tokens from the ask are strong constraints (people/places/proper nouns).
        required = [
            m.group(0)
            for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}\b", plan.original_ask or "")
            if m.group(0).lower()
            not in {
                "show",
                "what",
                "just",
                "only",
                "from",
                "with",
                "that",
                "this",
                "have",
                "else",
                "after",
                "right",
                "pictures",
                "photos",
                "emails",
                "email",
                "christmas",
                "grandpa",
                "tell",
                "know",
                "about",
            }
        ]
        for r in rows:
            payload = _payload_dict(r["payload_json"])
            blob = f"{r['summary'] or ''} {json.dumps(payload)}".lower()
            if required and not any(t.lower() in blob for t in required):
                continue
            match_n = sum(1 for t in distinctive if t.lower() in blob)
            if distinctive and match_n == 0:
                continue
            scored.append(
                EvidenceHit(
                    evidence_id=str(r["id"]),
                    evidence_kind=r["evidence_kind"],
                    summary=r["summary"] or "",
                    score=float(match_n) + 0.1,
                    excerpt=_excerpt(payload, r["evidence_kind"]),
                    source="postgres_keyword",
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        hits = scored[:limit]
    if plan.retrieval_constraints:
        hits = filter_hits_by_constraints(hits, plan.retrieval_constraints)
    return hits


def filter_hits_by_constraints(
    hits: list[EvidenceHit], constraints: tuple[str, ...] | list[str]
) -> list[EvidenceHit]:
    """Rule G: keep hits that match at least one resolved context constraint.

    If no hit matches, return empty (insufficient) rather than unconstrained
    vector/keyword leftovers.
    """
    cons = [c for c in constraints if c and len(c) >= 2]
    if not cons:
        return hits
    year_cons = {c for c in cons if re.fullmatch(r"(?:19|20)\d{2}", c)}
    other_cons = [c for c in cons if c not in year_cons]
    kept: list[EvidenceHit] = []
    for h in hits:
        blob = " ".join(
            [
                h.summary or "",
                h.excerpt or "",
                " ".join(h.people or []),
                h.thread_id or "",
                h.channel or "",
                h.sent_at or "",
            ]
        ).lower()
        year_ok = True
        if year_cons:
            sent_y = str(h.sent_at or "")[:4]
            year_ok = sent_y in year_cons
        other_ok = True
        if other_cons:
            other_ok = any(c.lower() in blob for c in other_cons)
        if year_ok and other_ok:
            kept.append(h)
    return kept


def search_evidence_qdrant(
    plan: QueryPlan, *, limit: int = 12, cfg: Settings | None = None
) -> tuple[list[EvidenceHit], dict[str, Any]]:
    """Derived Qdrant semantic search. Returns (hits, status)."""
    cfg = cfg or settings
    status: dict[str, Any] = {"ok": False, "detail": ""}
    try:
        embedder = rebuild_index._llm_embedder(cfg)
        from memorybox.ai_trace.context import reset_assembled_context, set_assembled_context

        assembled_tok = set_assembled_context(
            {
                "component": "retrieve",
                "purpose": "query",
                "ask": plan.effective_ask,
                "original_ask": plan.original_ask,
            }
        )
        try:
            vec = list(embedder.embed(plan.effective_ask, purpose="query").vector)
        finally:
            reset_assembled_context(assembled_tok)
        client = rebuild_index._qdrant_client(cfg)
        name = cfg.qdrant_collection
        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            status["detail"] = "collection_missing"
            return [], status
        result = client.query_points(collection_name=name, query=vec, limit=limit)
        points = result.points if hasattr(result, "points") else result
        hits: list[EvidenceHit] = []
        distinctive = [
            t
            for t in re.findall(r"[A-Za-z0-9']{4,}", plan.original_ask)
            if t.lower()
            not in {
                "show",
                "emails",
                "email",
                "about",
                "what",
                "else",
                "have",
                "from",
                "that",
                "this",
                "with",
                "just",
                "ones",
                "pictures",
                "photos",
                "after",
                "right",
                "happened",
                "secret",
                "family",
                "signed",
                "year",
                "sign",
                "did",
            }
        ]
        if plan.retrieval_constraints:
            # Rule G: constraints outrank bare ask tokens for semantic neighbors
            required = list(plan.retrieval_constraints)
        else:
            required = [
                m.group(0)
                for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}\b", plan.original_ask or "")
                if m.group(0).lower()
                not in {
                    "show",
                    "what",
                    "just",
                    "only",
                    "from",
                    "with",
                    "christmas",
                    "grandpa",
                    "tell",
                    "know",
                    "about",
                }
            ]
        for p in points:
            payload = p.payload or {}
            kind = str(payload.get("evidence_kind") or "")
            if kind == "communication" and not plan.want_communication:
                continue
            if kind == "calendar_event" and not plan.want_calendar:
                continue
            eid = str(payload.get("evidence_id") or p.id)
            row = None
            try:
                row = __import__("memorybox.ingest.store", fromlist=["store"]).store.get_evidence(
                    UUID(eid)
                )
            except Exception:  # noqa: BLE001
                row = None
            summary = (payload.get("summary") or "") if not row else (row.get("summary") or "")
            excerpt = ""
            blob = str(summary).lower()
            if row:
                excerpt = _excerpt(_payload_dict(row.get("payload_json")), kind)
                blob = f"{summary} {excerpt} {json.dumps(_payload_dict(row.get('payload_json')))}".lower()
            if required and not any(t.lower() in blob for t in required):
                continue
            if distinctive and not any(t.lower() in blob for t in distinctive):
                continue
            hits.append(
                EvidenceHit(
                    evidence_id=eid,
                    evidence_kind=kind or "unknown",
                    summary=str(summary),
                    score=float(getattr(p, "score", 0.0) or 0.0),
                    excerpt=excerpt,
                    source="qdrant",
                )
            )
        status["ok"] = True
        if plan.retrieval_constraints:
            hits = filter_hits_by_constraints(hits, plan.retrieval_constraints)
            status["detail"] = f"hits={len(hits)}_constrained"
        else:
            status["detail"] = f"hits={len(hits)}"
        return hits, status
    except Exception as exc:  # noqa: BLE001
        status["detail"] = str(exc)
        return [], status


def merge_evidence_hits(*groups: list[EvidenceHit], limit: int = 20) -> list[EvidenceHit]:
    by_id: dict[str, EvidenceHit] = {}
    for group in groups:
        for h in group:
            prev = by_id.get(h.evidence_id)
            if prev is None or h.score > prev.score:
                by_id[h.evidence_id] = h
    ranked = sorted(by_id.values(), key=lambda x: x.score, reverse=True)
    return ranked[:limit]


def search_photos(
    plan: QueryPlan, photo: PhotoProvider, *, limit: int = 5000
) -> tuple[list[PhotoHit], dict[str, Any]]:
    """Search photos via PhotoProvider with I6/I7 identity authority rules.

    Confirmed and trusted-provider-seeded MB Persons retrieve via provider_identities.
    Unconfirmed Immich name matches remain candidates and never become confirmed.
    Empty mapped Immich results fall through to Immich **person-id** name
    lookup (stale mapping safe). Never pad a successful personIds result with
    bare Immich text/metadata search — that returns newest library pages and
    over-counts person asks (e.g. 661 → 912 with unrelated 2026 photos).
    Limit defaults high so person asks can return the full Immich person library
    (hundreds–thousands), not only the newest page (~48–120).
    """
    from memorybox.person import (
        AUTHORITY_TRUSTED_PROVIDER,
        AmbiguousIdentityError,
        find_ask_person_by_name,
        find_confirmed_person_by_name,
        is_negative,
        list_provider_external_ids_for_person,
        resolve_immich_external_ids_for_person,
        asked_name_matches_person,
        immich_ids_matching_asked_name,
    )

    status: dict[str, Any] = {
        "provider_key": getattr(photo, "provider_key", "photo"),
        "ok": False,
        "unavailable": False,
        "detail": "",
        "identity_mode": "none",
    }

    def _filter_photo_hits(hits: list[PhotoHit]) -> list[PhotoHit]:
        """Apply shared plan time windows + place tokens to photo hits."""
        from memorybox.planner.temporal import date_in_windows

        windows = tuple(getattr(plan, "temporal_windows", ()) or ())
        if not windows and plan.time_start and plan.time_end:
            windows = ((plan.time_start, plan.time_end),)
        places = [str(p) for p in (plan.place_names or ()) if p]
        if not windows and not places:
            return hits
        timed = hits
        if windows:
            timed = []
            for h in hits:
                # Explore keeps undated in Gallery (off the Timeline). Dropping
                # them here emptied Christmas / year asks: face stubs have no EXIF,
                # so "Peggy during Christmas" showed 0 cards ("gallery is lost").
                if h.taken_at and not date_in_windows(h.taken_at, windows):
                    continue
                timed.append(h)
            status["temporal_windows"] = [list(w) for w in windows]
            status["temporal_label"] = getattr(plan, "temporal_label", None)
            status["before_temporal_filter"] = len(hits)
            status["after_temporal_filter"] = len(timed)
        out = timed
        if places and trip_discovery_pending(plan):
            status["place_filter"] = list(plan.place_names)
            status["constraint_mode"] = "deferred_trip_discovery"
            status["before_place_filter"] = len(timed)
            status["after_place_filter"] = len(timed)
            status["semantic_constraint"] = places[0]
            return out
        if places:
            before = len(timed)
            out = filter_photo_hits_to_places(timed, places)
            spec = place_match_spec(tuple(places))
            status["place_filter"] = list(plan.place_names)
            status["place_match"] = spec
            status["constraint_mode"] = "exclusive_place_filter"
            status["before_place_filter"] = before
            status["after_place_filter"] = len(out)
            status["semantic_constraint"] = places[0]
            dropped = before - len(out)
            if dropped > 0:
                label = places[0]
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + (
                        f" Showing {len(out)} photo(s) in {label}"
                        f" ({dropped} in this person library had no {label} location)."
                    )
                ).strip()
        return out

    def _finish(hits: list[PhotoHit]) -> tuple[list[PhotoHit], dict[str, Any]]:
        client = getattr(photo, "_client", None)
        snap = getattr(client, "diag_snapshot", None)
        if callable(snap):
            status["immich_diag"] = snap()
            diag = status["immich_diag"] if isinstance(status.get("immich_diag"), dict) else {}
            for key in (
                "person_library_unwindowed_n",
                "person_assets_in_window_n",
                "person_stills_in_window_n",
                "person_videos_in_window_n",
                "year_fair_applied",
            ):
                if key in diag and status.get(key) is None:
                    status[key] = diag.get(key)
        status["gallery_display_is_presentation_only"] = True
        status["media_provider_candidates"] = int(
            status.get("media_provider_candidates") or len(hits)
        )
        status["person_filtered_media_count"] = len(hits)
        filtered = _filter_photo_hits(hits)
        if "after_temporal_filter" in status:
            status["time_filtered_media_count"] = int(status["after_temporal_filter"])
        else:
            status["time_filtered_media_count"] = len(filtered)
        if "after_place_filter" in status:
            status["location_filtered_count"] = int(status["after_place_filter"])
        else:
            status["location_filtered_count"] = None
        if _bounded_period_tell(plan) or int(limit) <= 0:
            status["photo_truncated"] = False
            status["eligible_n"] = len(filtered)
            status["processed_n"] = len(filtered)
            return filtered, status
        sliced = filtered[: max(1, int(limit))]
        status["photo_truncated"] = len(filtered) > len(sliced)
        status["eligible_n"] = len(filtered)
        status["processed_n"] = len(sliced)
        return sliced, status

    if not plan.want_still and not plan.want_photo:
        status["ok"] = True
        status["detail"] = "not_requested"
        return [], status
    try:
        library_person_ids, requestor_id = visual_library_person_ids(plan)
        if requestor_id:
            status["requestor_library"] = True
            status["requestor_person_id"] = requestor_id
        named_person = bool(
            getattr(plan, "person_names", ()) or library_person_ids
        )
        if named_person:
            status["health_skipped"] = "named_person_ask"
        else:
            health = photo.health()
            if not health.ok:
                # Ping/health must not zero a person library. FlightSim Immich ping
                # can fail while /people + asset GETs still return photos.
                status["health_detail"] = health.detail or "photo provider unhealthy"

        photo_pk = getattr(photo, "provider_key", "immich") or "immich"
        lookup_keys = [photo_pk]
        if photo_pk == "fake_photo":
            lookup_keys = ["fake_photo", "immich"]
        elif photo_pk == "immich":
            lookup_keys = ["immich", "fake_photo"]

        mapped_ext: list[str] = []
        mapped_meta: list[dict[str, str]] = []
        mapped_names: list[str] = []
        unmapped_resolvable_names: list[str] = []
        ambiguous_names: list[str] = []
        ambiguous_candidates: list[dict[str, Any]] = []
        clarify_message: str | None = None

        # I9A: prefer MB Person ids from relational resolve (owner ? Relationship ? id)
        from memorybox.person import get_person as _get_person_by_id

        asked_names = [n for n in (plan.person_names or ()) if str(n).strip()]

        def _person_name_is_asked(display: str) -> bool:
            if not asked_names:
                return True
            return any(asked_name_matches_person(a, display) for a in asked_names)

        resolved_by_id: set[str] = set()
        for pid in library_person_ids:
            person = _get_person_by_id(pid)
            if not person:
                continue
            if asked_names and not _person_name_is_asked(person.display_name or ""):
                continue
            resolved_by_id.add(person.id)
            name = person.display_name or pid
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            try:
                ids.extend(resolve_immich_external_ids_for_person(person.id, photo=photo))
            except Exception:  # noqa: BLE001
                pass
            ids = list(dict.fromkeys(ids))
            if ids:
                mapped_names.append(name)
                mapping_auth = person.identity_authority
                for m in person.provider_mappings:
                    if (
                        m.get("provider_key") in lookup_keys
                        and m.get("external_id") in ids
                    ):
                        mapping_auth = (
                            m.get("identity_authority") or person.identity_authority
                        )
                        break
                trust = (
                    "trusted_provider"
                    if mapping_auth == AUTHORITY_TRUSTED_PROVIDER
                    else "confirmed"
                )
                for eid in ids:
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": name,
                            "trust": trust,
                        }
                    )
            else:
                unmapped_resolvable_names.append(name)

        for name in plan.person_names:
            try:
                person = find_ask_person_by_name(name, photo=photo, lazy_seed=True)
            except AmbiguousIdentityError as exc:
                ambiguous_names.append(name)
                ambiguous_candidates.extend(list(exc.candidates or []))
                clarify_message = str(exc) or clarify_message
                status["disclosure"] = str(exc)
                continue
            if person:
                if person.id in resolved_by_id:
                    continue
                ids: list[str] = []
                for pk in lookup_keys:
                    ids.extend(list_provider_external_ids_for_person(person.id, pk))
                try:
                    ids.extend(resolve_immich_external_ids_for_person(person.id, photo=photo))
                except Exception:  # noqa: BLE001
                    pass
                ids = list(dict.fromkeys(ids))
                if ids:
                    mapped_names.append(name)
                    mapping_auth = person.identity_authority
                    for m in person.provider_mappings:
                        if (
                            m.get("provider_key") in lookup_keys
                            and m.get("external_id") in ids
                        ):
                            mapping_auth = (
                                m.get("identity_authority") or person.identity_authority
                            )
                            break
                    trust = (
                        "trusted_provider"
                        if mapping_auth == AUTHORITY_TRUSTED_PROVIDER
                        else "confirmed"
                    )
                    for eid in ids:
                        mapped_ext.append(eid)
                        mapped_meta.append(
                            {
                                "external_id": eid,
                                "person_id": person.id,
                                "name": name,
                                "trust": trust,
                            }
                        )
                else:
                    unmapped_resolvable_names.append(name)

        if ambiguous_names and not mapped_ext:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            status["candidates"] = ambiguous_candidates
            status["clarify_message"] = clarify_message or (
                f"Please specify which {ambiguous_names[0].split()[0]} you would like."
            )
            status["ambiguous_person_names"] = list(ambiguous_names)
            return [], status

        # Named person ask with zero MB+Immich matches → ask who (do not dump library).
        if (
            plan.person_names
            and not mapped_ext
            and not unmapped_resolvable_names
            and not ambiguous_names
            and not (getattr(plan, "person_ids", None) or ())
        ):
            from memorybox.person import (
                _ask_named_photo_people,
                list_people_by_exact_name,
                list_people_by_first_token,
            )

            unknown: list[str] = []
            for name in plan.person_names:
                mb_hits = (
                    list_people_by_first_token(name)
                    if " " not in name.strip()
                    else list_people_by_exact_name(name)
                )
                photo_hits = _ask_named_photo_people(photo, name)
                if not mb_hits and not photo_hits:
                    unknown.append(name)
            if unknown and len(unknown) == len(list(plan.person_names)):
                who = unknown[0]
                status["identity_mode"] = "unknown_person"
                status["ok"] = True
                status["detail"] = f"unknown={unknown}"
                status["unknown_person_names"] = list(unknown)
                status["clarify_message"] = f"Who is {who}?"
                return [], status

        hits: list[PhotoHit] = []

        def _people_for_hit(a: PhotoAssetDto, person_name: str | None) -> list[str]:
            """Immich personId search often omits per-asset people[]; keep ask person."""
            out: list[str] = []
            for pref in a.people or ():
                n = (pref.display_name or "").strip()
                if n and n.lower() != "unknown" and n not in out:
                    out.append(n)
            for face in getattr(a, "faces", ()) or ():
                n = (getattr(face, "display_name", None) or "").strip()
                if n and n.lower() != "unknown" and n not in out:
                    out.append(n)
            pn = (person_name or "").strip()
            if pn and pn.lower() != "unknown" and pn not in out:
                # Do not relabel Tom's stills as Peggy/Dan when people[] already
                # names someone else.
                if out and not any(asked_name_matches_person(pn, existing) for existing in out):
                    return out
                out.insert(0, pn)
            return out

        def _search_person_assets(ext_ids: list[str]) -> list[PhotoAssetDto]:
            """Person library via personIds, then face-asset fallback.

            FlightSim Immich /search/metadata often RST/times out. That is not
            “this person has no photos.”
            """
            ids = list(dict.fromkeys(str(x).strip() for x in ext_ids if str(x).strip()))
            if not ids:
                return []
            try:
                assets = photo.search_assets(
                    PhotoSearchQuery(
                        person_external_ids=tuple(ids),
                        limit=_provider_fetch_n(limit),
                        time_windows=tuple(
                            getattr(plan, "temporal_windows", ()) or ()
                        ),
                        need_location=bool(getattr(plan, "place_names", ()) or ())
                        and not trip_discovery_pending(plan),
                    )
                )
            except (ProviderError, ProviderUnavailable, Exception):  # noqa: BLE001
                assets = []
                status["photo_search_error"] = "personIds_search_failed"
            src = getattr(getattr(photo, "_client", None), "_last_person_source", None)
            if src:
                status["person_library_source"] = src
            if assets:
                return list(assets)
            _client = getattr(photo, "_client", None)
            if _client is not None and getattr(_client, "_circuit", lambda: False)():
                return []
            list_fn = getattr(photo, "list_face_assets", None)
            if not callable(list_fn):
                return []
            seen: set[str] = set()
            out: list[PhotoAssetDto] = []
            if _bounded_period_tell(plan) or int(limit) <= 0:
                # Face listing is already fetched in full; do not treat 400 as
                # "MemoryBox considered only 400 photos."
                cap = 10**9
            else:
                cap = min(max(1, int(limit)), 400)
            for pid in ids:
                try:
                    faces = list_fn(person_external_id=pid, limit=cap)
                except Exception:  # noqa: BLE001
                    continue
                for face in faces or []:
                    aid = str(getattr(face, "source_asset_id", None) or "").strip()
                    if not aid or "/" in aid or aid in seen:
                        continue
                    seen.add(aid)
                    # Do not GET /assets/{id} per face — that RST's Immich after
                    # a failed person search. Gallery can thumb from the id alone.
                    out.append(
                        PhotoAssetDto(
                            provider_key=getattr(photo, "provider_key", "immich")
                            or "immich",
                            external_id=aid,
                        )
                    )
                    if len(out) >= cap:
                        status["face_asset_fallback"] = len(out)
                        return out
            if out:
                status["face_asset_fallback"] = len(out)
            return out

        def _intersect_person_assets(meta_rows: list[dict[str, str]]) -> list[PhotoAssetDto]:
            """Two+ named people: photos that appear in every person library (AND)."""
            ids = list(
                dict.fromkeys(
                    str(m.get("external_id") or "").strip()
                    for m in meta_rows
                    if str(m.get("external_id") or "").strip()
                )
            )
            if len(ids) < 2:
                return _search_person_assets(ids)
            maps: list[dict[str, PhotoAssetDto]] = []
            for pid in ids:
                chunk = _search_person_assets([pid])
                maps.append({a.external_id: a for a in chunk if a.external_id})
            common = set(maps[0]) if maps else set()
            for amap in maps[1:]:
                common &= set(amap)
            out: list[PhotoAssetDto] = []
            seen: set[str] = set()
            for amap in maps:
                for eid in common:
                    if eid in seen or eid not in amap:
                        continue
                    out.append(amap[eid])
                    seen.add(eid)
            status["person_combine"] = "and_intersection"
            status["and_person_ids"] = ids
            status["and_library_sizes"] = [len(m) for m in maps]
            status["and_intersection"] = len(out)
            return out

        def _faces_for_hit(a: PhotoAssetDto) -> list[dict[str, Any]] | None:
            rows: list[dict[str, Any]] = []
            for face in getattr(a, "faces", ()) or ():
                name = (getattr(face, "display_name", None) or "").strip()
                if not name:
                    continue
                row: dict[str, Any] = {
                    "name": name,
                    "person_external_id": getattr(face, "external_person_id", None),
                }
                box = getattr(face, "face_box", None)
                if box and len(box) == 4:
                    row["face_box"] = {
                        "x": float(box[0]),
                        "y": float(box[1]),
                        "w": float(box[2]),
                        "h": float(box[3]),
                    }
                rows.append(row)
            return rows or None

        def _asset_to_hit(
            a: PhotoAssetDto,
            *,
            trust: str,
            person_id: str | None = None,
            person_name: str | None = None,
        ) -> PhotoHit:
            loc = None
            city = state = country = None
            lat = lon = None
            place = None
            if a.location:
                city = a.location.city
                state = a.location.state
                country = a.location.country
                lat = a.location.latitude
                lon = a.location.longitude
                parts = [city, state, country]
                loc = ", ".join(p for p in parts if p)
                place = city or state or country or loc
            if trust == "confirmed":
                attrib = (
                    f"MB Person {person_name} via owner-confirmed Immich mapping"
                    if person_name
                    else "owner-confirmed MB Person mapping"
                )
            elif trust == "trusted_provider":
                attrib = (
                    f"MB Person {person_name} via trusted Immich/provider identity "
                    "(not owner-confirmed)"
                    if person_name
                    else "trusted-provider-seeded MB Person mapping (not owner-confirmed)"
                )
            else:
                attrib = (
                    "unconfirmed Immich name candidate (not MB-confirmed identity)"
                )
            exif_d = dict(getattr(a, "exif", ()) or ()) or {}
            albums = tuple(getattr(a, "albums", ()) or ())
            if albums and "albums" not in exif_d:
                exif_d["albums"] = ", ".join(str(x) for x in albums if x)
            media_type = "image"
            if str(exif_d.get("media") or "").lower() == "video":
                media_type = "video"
            fn = str(getattr(a, "original_filename", None) or "").lower()
            if fn.endswith((".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")):
                media_type = "video"
            dur = None
            for k in ("Duration", "duration", "duration_sec"):
                raw_d = exif_d.get(k)
                if raw_d not in (None, ""):
                    try:
                        dur = float(str(raw_d).split()[0])
                    except (TypeError, ValueError):
                        dur = None
                    break
            return PhotoHit(
                provider_key=a.provider_key,
                external_id=a.external_id,
                taken_at=a.taken_at.isoformat() if a.taken_at else None,
                people=_people_for_hit(a, person_name),
                location=loc,
                # Browser-safe MB proxy (Immich URLs are not cookie-auth'd for Ask UI)
                thumb_url=(
                    f"/library/media/photo/{a.external_id}" if a.external_id else a.thumb_url
                ),
                web_url=a.web_url,
                identity_trust=trust,
                mb_person_id=person_id,
                mb_person_name=person_name,
                attribution=attrib,
                place=place,
                city=city,
                state=state,
                country=country,
                latitude=lat,
                longitude=lon,
                original_filename=getattr(a, "original_filename", None),
                exif=exif_d or None,
                faces=_faces_for_hit(a),
                media_type=media_type,
                duration_sec=dur,
            )

        if mapped_ext and asked_names:
            verified: list[str] = []
            for name in asked_names:
                verified.extend(immich_ids_matching_asked_name(photo, name, mapped_ext))
            verified = list(dict.fromkeys(verified))
            status["mapped_immich_ids_before_verify"] = list(dict.fromkeys(mapped_ext))
            status["mapped_immich_ids"] = list(verified)
            if verified != list(dict.fromkeys(mapped_ext)):
                status["stale_immich_mapping_dropped"] = True
            mapped_ext = verified
            mapped_meta = [m for m in mapped_meta if m.get("external_id") in set(mapped_ext)]

        if mapped_ext:
            trusts = {m.get("trust") for m in mapped_meta}
            if trusts == {"trusted_provider"}:
                status["identity_mode"] = "trusted_provider_mapping"
            elif "trusted_provider" in trusts:
                status["identity_mode"] = "mixed_mapping"
            else:
                status["identity_mode"] = "confirmed_mapping"
            and_people = len(asked_names) >= 2 and len(
                {str(m.get("external_id") or "") for m in mapped_meta if m.get("external_id")}
            ) >= 2
            assets = (
                _intersect_person_assets(mapped_meta)
                if and_people
                else _search_person_assets(mapped_ext)
            )
            by_person_ext = {m["external_id"]: m for m in mapped_meta}
            for a in assets:
                meta: dict[str, str] = {}
                for pref in a.people or ():
                    hit_meta = by_person_ext.get(pref.external_id)
                    if hit_meta:
                        meta = hit_meta
                        break
                if not meta and mapped_meta:
                    meta = mapped_meta[0]
                hits.append(
                    _asset_to_hit(
                        a,
                        trust=meta.get("trust") or "confirmed",
                        person_id=meta.get("person_id"),
                        person_name=meta.get("name"),
                    )
                )
            status["ok"] = True
            status["detail"] = (
                f"mapped_hits={len(hits)} mapped_names={mapped_names}"
            )
            status["mapped_person_names"] = list(mapped_names)
            status["unmapped_person_names"] = list(unmapped_resolvable_names)
            if unmapped_resolvable_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + f" No Immich/photo provider mapping for: {unmapped_resolvable_names}."
                ).strip()
            if ambiguous_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + f" Ambiguous identity for: {ambiguous_names}."
                ).strip()
            # PersonIds hits are the Immich person library. Do **not** "fill"
            # remaining slots with Immich text/metadata search — that path
            # often ignores `query` and returns the newest ~page of the whole
            # library (FlightSim: Eugene 661 + ~250 recent 2026 → 912).
            # Only fall through when the mapped id returned zero (stale mapping).
            if hits:
                return _finish(hits)
            status["detail"] = (
                f"mapped_hits=0 mapped_names={mapped_names}; "
                "fallback_via_name_person_ids"
            )

        status["identity_mode"] = (
            "candidate_unmapped_person"
            if unmapped_resolvable_names and not hits
            else (
                "mixed_mapping_plus_name"
                if hits and mapped_ext
                else (
                    "candidate_after_empty_mapping"
                    if mapped_ext and not hits
                    else (
                        "candidate_unmapped_person"
                        if unmapped_resolvable_names
                        else "candidate_provider_name"
                    )
                )
            )
        )
        if ambiguous_names and not hits:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            status["candidates"] = ambiguous_candidates
            status["clarify_message"] = clarify_message or (
                f"Please specify which {ambiguous_names[0].split()[0]} you would like."
            )
            status["ambiguous_person_names"] = list(ambiguous_names)
            return [], status

        person_ext: list[str] = []
        # Do not reset the Immich circuit here — that re-floods a recovering NAS.
        # Name lookup stays allowlisted while the circuit is open.
        # Prefer resolved MB display names (Peggy → Peggy George) for Immich lookup
        name_queries: list[str] = []
        for name in plan.person_names:
            if name and name not in name_queries:
                name_queries.append(name)
        for meta in mapped_meta:
            n = meta.get("name")
            if n and n not in name_queries:
                name_queries.append(n)
        for name in name_queries:
            confirmed = find_confirmed_person_by_name(name)
            from memorybox.person import _ask_named_photo_people

            # Strict Immich name resolution only (exact / unique first-token).
            try:
                refs = _ask_named_photo_people(photo, name)
            except Exception:  # noqa: BLE001
                refs = []
            if len(refs) > 1:
                first = name.split()[0] if name.split() else name
                labels = [
                    str(getattr(r, "display_name", "") or "").strip()
                    for r in refs
                    if str(getattr(r, "display_name", "") or "").strip()
                ]
                status["identity_mode"] = "ambiguous_identity"
                status["ok"] = True
                status["detail"] = f"ambiguous={name}"
                status["clarify_message"] = (
                    f"Please specify which {first} you would like"
                    + (f": {', '.join(labels)}." if labels else ".")
                )
                status["ambiguous_person_names"] = [name]
                status["candidates"] = [
                    {
                        "external_id": str(getattr(r, "external_id", "") or ""),
                        "display_name": getattr(r, "display_name", name),
                    }
                    for r in refs
                ]
                return [], status
            for r in refs or []:
                if confirmed and is_negative(
                    provider_key=photo_pk,
                    external_id=r.external_id,
                    person_id=confirmed.id,
                ):
                    continue
                if r.external_id in mapped_ext:
                    # Already searched (including timeout). Retrying the same
                    # id just re-opens the 6s RST and skips a live Immich name.
                    continue
                person_ext.append(r.external_id)

        person_ext = list(dict.fromkeys(person_ext))
        if not person_ext:
            status["ok"] = True
            # MB Person resolved (mapped or unmapped) is not “Who is X?” —
            # that wipe also cleared video moments on FlightSim person asks.
            if (
                plan.person_names
                and not hits
                and not mapped_names
                and not unmapped_resolvable_names
            ):
                who = list(plan.person_names)[0]
                status["identity_mode"] = "unknown_person"
                status["detail"] = f"unknown={list(plan.person_names)}"
                status["unknown_person_names"] = list(plan.person_names)
                status["clarify_message"] = f"Who is {who}?"
                return _finish(hits)
            status["identity_mode"] = "photos_empty_person_resolved"
            src = status.get("person_library_source") or getattr(
                getattr(photo, "_client", None), "_last_person_source", None
            )
            if src == "timeout":
                status["unavailable"] = True
                status["detail"] = (
                    f"immich_timeout names={name_queries} "
                    f"mapped_names={mapped_names}"
                )
            else:
                status["detail"] = (
                    f"no_immich_person_ids names={name_queries} "
                    f"unmapped_resolvable={unmapped_resolvable_names or []} "
                    f"mapped_names={mapped_names}"
                    + (f" source={src}" if src else "")
                    + (f" requestor={requestor_id}" if requestor_id else "")
                )
            if mapped_names or unmapped_resolvable_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + " Photo library did not return stills for this person; "
                    "video moments stay visible."
                ).strip()
            return _finish(hits)

        # Person asks must stay on personIds only — never bare Immich text search
        # (unfiltered newest-library page).
        assets = _search_person_assets(person_ext)
        seen_ext = {h.external_id for h in hits}
        for a in assets:
            if a.external_id in seen_ext:
                continue
            hits.append(_asset_to_hit(a, trust="candidate"))
            seen_ext.add(a.external_id)
        status["ok"] = True
        status["detail"] = (
            f"candidate_hits={len(hits)} person_ids={len(person_ext)} "
            f"unmapped_resolvable={unmapped_resolvable_names or []}"
        )
        if unmapped_resolvable_names:
            status["disclosure"] = (
                "Resolvable MB Person(s) exist without Immich mapping; "
                "Immich name matches are unconfirmed candidates only."
            )
        return _finish(hits)
    except ProviderUnavailable as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return _finish([])
    except ProviderError as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return _finish([])
    except Exception as exc:  # noqa: BLE001
        status["unavailable"] = True
        status["detail"] = str(exc)
        return _finish([])


def _hit_score(h: VideoHit) -> tuple[int, int, int, float, int]:
    named = 1 if (h.mb_person_name or (h.label and h.label != "face-appearance-moment")) else 0
    trust = {"confirmed": 3, "trusted_provider": 2, "candidate": 1}.get(
        h.identity_trust or "", 0
    )
    native = 1 if "mb_native" in str(h.attribution or "") else 0
    dur = max(0.0, float(h.end_sec or 0) - float(h.start_sec or 0))
    has_face = 1 if h.face_external_id else 0
    return (named, trust, native, dur, has_face)


def _merge_overlapping_video_hits(
    hits: list[VideoHit], *, gap_sec: float = 8.0
) -> list[VideoHit]:
    """One gallery card per presence span. Stacked native writes of the same visit collapse."""
    from memorybox.recognition.process import ensure_timeslot_play_url

    by_vid: dict[str, list[VideoHit]] = {}
    order: list[str] = []
    for h in hits:
        vid = str(h.video_external_id or h.external_id or "")
        if vid not in by_vid:
            order.append(vid)
            by_vid[vid] = []
        by_vid[vid].append(h)
    out: list[VideoHit] = []
    for vid in order:
        group = sorted(by_vid[vid], key=lambda x: float(x.start_sec or 0))
        merged: list[VideoHit] = []
        for h in group:
            if not merged:
                merged.append(h)
                continue
            prev = merged[-1]
            if float(h.start_sec or 0) <= float(prev.end_sec or 0) + float(gap_sec):
                start = min(float(prev.start_sec or 0), float(h.start_sec or 0))
                end = max(float(prev.end_sec or 0), float(h.end_sec or 0))
                keep = h if _hit_score(h) > _hit_score(prev) else prev
                keep.start_sec = start
                keep.end_sec = end
                keep.play_url = ensure_timeslot_play_url(
                    video_external_id=str(keep.video_external_id or vid),
                    start_sec=start,
                    play_url=keep.play_url,
                    video_provider_key=str(keep.provider_key or ""),
                )
                keep.thumb_url = None
                merged[-1] = keep
            else:
                merged.append(h)
        out.extend(merged)
    return [_origin_on_video_hit(h) for h in out]


def _dedupe_video_hits(
    hits: list[VideoHit], *, window_sec: float = 2.5, limit: int = 48
) -> list[VideoHit]:
    """Collapse near-duplicate moments (HVRT segment + stacked native ranges).

    Prefer labeled / named / confirmed hits over generic face-appearance copies.
    Overlapping or adjacent spans on the same file become one card whose
    entry time (and poster) is the earliest start_sec — not file t=0.
    """
    buckets: dict[tuple[str, int], VideoHit] = {}
    order: list[tuple[str, int]] = []
    for h in hits:
        vid = str(h.video_external_id or h.external_id or "")
        slot = int(float(h.start_sec or 0) // window_sec)
        key = (vid, slot)
        prev = buckets.get(key)
        if prev is None:
            buckets[key] = h
            order.append(key)
            continue
        if _hit_score(h) > _hit_score(prev):
            buckets[key] = h
    collapsed = [buckets[k] for k in order]
    merged = _merge_overlapping_video_hits(collapsed)
    if limit is None or int(limit) <= 0:
        return merged
    return merged[: int(limit)]


def search_videos(
    plan: QueryPlan,
    video: Any,
    *,
    limit: int = 48,
    photo: Any | None = None,
) -> tuple[list[VideoHit], dict[str, Any]]:
    """Search video presence spans with I6/I7 identity authority rules."""
    from memorybox.person import (
        AUTHORITY_TRUSTED_PROVIDER,
        AmbiguousIdentityError,
        find_ask_person_by_name,
        list_provider_external_ids_for_person,
    )
    from memorybox.providers.video.dto import VideoSearchQuery

    status: dict[str, Any] = {
        "provider_key": getattr(video, "provider_key", "video"),
        "ok": False,
        "unavailable": False,
        "detail": "",
        "identity_mode": "none",
    }
    if not getattr(plan, "want_video", False):
        status["ok"] = True
        status["detail"] = "not_requested"
        return [], status
    if _bounded_period_tell(plan):
        limit = 0
    fetch_n = _provider_fetch_n(limit)
    try:
        health = video.health()
        if not health.ok:
            status["unavailable"] = True
            status["detail"] = health.detail or "video provider unhealthy"
            return [], status

        mapped_ext: list[str] = []
        mapped_meta: list[dict[str, str]] = []
        unmapped: list[str] = []
        ambiguous_names: list[str] = []
        provider_key = getattr(video, "provider_key", "hvrt")
        lookup_keys = [provider_key]
        if provider_key == "fake_video":
            lookup_keys = ["fake_video", "hvrt"]

        if photo is None:
            try:
                from memorybox.ask.deps import build_photo

                photo = build_photo()
            except Exception:  # noqa: BLE001
                photo = None

        from memorybox.person import get_person as _get_person_by_id

        asked_video_names = [n for n in (plan.person_names or ()) if str(n).strip()]

        def _video_person_is_asked(display: str) -> bool:
            if not asked_video_names:
                return True
            from memorybox.person import asked_name_matches_person as _nm

            return any(_nm(a, display) for a in asked_video_names)

        library_person_ids, requestor_id = visual_library_person_ids(plan)
        if requestor_id:
            status["requestor_library"] = True
            status["requestor_person_id"] = requestor_id
        seen_pids: set[str] = set()
        for pid in library_person_ids:
            person = _get_person_by_id(pid)
            if not person:
                continue
            if asked_video_names and not _video_person_is_asked(person.display_name or ""):
                continue
            seen_pids.add(person.id)
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            ids = list(dict.fromkeys(ids))
            if ids:
                for eid in ids:
                    trust = "confirmed"
                    for m in person.provider_mappings:
                        if m.get("external_id") == eid:
                            if m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                                trust = "trusted_provider"
                            break
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": person.display_name or pid,
                            "trust": trust,
                        }
                    )
            else:
                unmapped.append(person.display_name or pid)

        for name in plan.person_names:
            try:
                person = find_ask_person_by_name(name, photo=photo, lazy_seed=True)
            except AmbiguousIdentityError as exc:
                ambiguous_names.append(name)
                status["disclosure"] = str(exc)
                continue
            if not person:
                continue
            if person.id in seen_pids:
                continue
            ids: list[str] = []
            for pk in lookup_keys:
                ids.extend(list_provider_external_ids_for_person(person.id, pk))
            ids = list(dict.fromkeys(ids))
            if ids:
                for eid in ids:
                    trust = "confirmed"
                    for m in person.provider_mappings:
                        if m.get("external_id") == eid:
                            if m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                                trust = "trusted_provider"
                            break
                    mapped_ext.append(eid)
                    mapped_meta.append(
                        {
                            "external_id": eid,
                            "person_id": person.id,
                            "name": name,
                            "trust": trust,
                        }
                    )
            else:
                unmapped.append(name)

        hits: list[VideoHit] = []
        if mapped_ext:
            trusts = {m.get("trust") for m in mapped_meta}
            if trusts == {"trusted_provider"}:
                status["identity_mode"] = "trusted_provider_mapping"
            elif "trusted_provider" in trusts:
                status["identity_mode"] = "mixed_mapping"
            else:
                status["identity_mode"] = "confirmed_mapping"
            q = VideoSearchQuery(
                person_external_ids=tuple(dict.fromkeys(mapped_ext)),
                limit=fetch_n,
            )
            segs = video.search_segments(q)
            by_face = {m["external_id"]: m for m in mapped_meta}
            for s in segs:
                meta = by_face.get(s.face_external_id or "") or (
                    mapped_meta[0] if mapped_meta else {}
                )
                trust = meta.get("trust") or "confirmed"
                if trust == "trusted_provider":
                    attrib = (
                        f"MB Person {meta.get('name')} via trusted-provider video mapping "
                        "(not owner-confirmed)"
                        if meta.get("name")
                        else "trusted-provider video mapping (not owner-confirmed)"
                    )
                else:
                    attrib = (
                        f"MB Person {meta.get('name')} via owner-confirmed video mapping"
                        if meta.get("name")
                        else "owner-confirmed MB Person video mapping"
                    )
                hits.append(
                    VideoHit(
                        provider_key=s.provider_key,
                        external_id=s.external_id,
                        video_external_id=s.video_external_id,
                        start_sec=s.start_sec,
                        end_sec=s.end_sec,
                        face_external_id=s.face_external_id,
                        label=s.label,
                        play_url=s.play_url,
                        identity_trust=trust,
                        mb_person_id=meta.get("person_id"),
                        mb_person_name=meta.get("name"),
                        attribution=attrib,
                    )
                )
                hits[-1] = _origin_on_video_hit(hits[-1])
            status["ok"] = True
            status["detail"] = f"mapped_video_hits={len(hits)}"
            status["unmapped_person_names"] = list(unmapped)
            # Merge durable face_appearance_moments (P2-I1) with seek URLs
            try:
                from memorybox.recognition.process import (
                    ensure_timeslot_play_url,
                    list_appearance_moments,
                )

                person_ids = {
                    str(m.get("person_id"))
                    for m in mapped_meta
                    if m.get("person_id")
                }
                name_by_pid = {
                    str(m.get("person_id")): str(m.get("name") or "")
                    for m in mapped_meta
                    if m.get("person_id")
                }
                existing_keys = {
                    (
                        str(h.video_external_id or ""),
                        int(float(h.start_sec or 0) // 2.5),
                    )
                    for h in hits
                }
                for pid in person_ids:
                    for mom in list_appearance_moments(pid, limit=fetch_n):
                        if str(mom.get("status") or "accepted") == "withdrawn":
                            continue
                        vid = str(mom["video_external_id"])
                        t0 = float(mom["start_sec"])
                        slot_key = (vid, int(t0 // 2.5))
                        if slot_key in existing_keys:
                            continue
                        play = ensure_timeslot_play_url(
                            video_external_id=vid,
                            start_sec=t0,
                            play_url=mom.get("play_url"),
                            video_provider_key=str(mom.get("video_provider_key") or ""),
                        )
                        pname = name_by_pid.get(pid) or None
                        hits.append(
                            VideoHit(
                                provider_key=mom["video_provider_key"],
                                external_id=mom["id"],
                                video_external_id=vid,
                                start_sec=t0,
                                end_sec=float(mom["end_sec"]),
                                face_external_id=mom.get("face_external_id"),
                                label=pname or "Video moment",
                                play_url=play,
                                identity_trust=(
                                    "confirmed"
                                    if mom.get("authority") == "owner_confirmed"
                                    else "trusted_provider"
                                    if mom.get("authority") == "trusted_provider"
                                    else "candidate"
                                ),
                                mb_person_id=pid,
                                mb_person_name=pname,
                                attribution=(
                                    f"face-appearance moment "
                                    f"({mom.get('method')}, {mom.get('confirmation_state')})"
                                ),
                            )
                        )
                        existing_keys.add(slot_key)
            except Exception:  # noqa: BLE001
                pass
            if unmapped:
                status["disclosure"] = (
                    f"No HVRT/video provider mapping for: {unmapped}. "
                    "Teach/confirm the video face onto the same MB Person in Review "
                    "(do not recreate the human in each provider)."
                )
            return _dedupe_video_hits(hits, limit=limit), status

        if ambiguous_names:
            status["identity_mode"] = "ambiguous_identity"
            status["ok"] = True
            status["detail"] = f"ambiguous={ambiguous_names}"
            return [], status

        status["identity_mode"] = (
            "candidate_unmapped_person" if unmapped else "candidate_provider_name"
        )
        text = " ".join(plan.person_names) if plan.person_names else plan.original_ask
        segs = video.search_segments(VideoSearchQuery(text=text, limit=fetch_n))
        for s in segs:
            hits.append(
                VideoHit(
                    provider_key=s.provider_key,
                    external_id=s.external_id,
                    video_external_id=s.video_external_id,
                    start_sec=s.start_sec,
                    end_sec=s.end_sec,
                    face_external_id=s.face_external_id,
                    label=s.label,
                    play_url=s.play_url,
                    identity_trust="candidate",
                    attribution=(
                        "unconfirmed video face candidate (not MB-confirmed identity)"
                    ),
                )
            )
        status["ok"] = True
        status["detail"] = f"candidate_video_hits={len(hits)} unmapped={unmapped}"
        if unmapped:
            status["disclosure"] = (
                "Resolvable MB Person(s) exist without video provider mapping; "
                "results are unconfirmed candidates only."
            )
        return _apply_result_limit([_origin_on_video_hit(h) for h in hits], limit), status
    except ProviderUnavailable as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status
    except ProviderError as exc:
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status
    except Exception as exc:  # noqa: BLE001
        status["unavailable"] = True
        status["detail"] = str(exc)
        return [], status


def search_stories(plan: QueryPlan, *, limit: int = 12) -> list[StoryHit]:
    """Retrieve current Story versions relevant to plan constraints / ask tokens.

    Queries stories/story_versions (+ person relationships) directly ? no silo,
    no required story_passage Evidence materialization for I5.
    """
    if not getattr(plan, "want_story", False):
        return []
    person_ids = [str(p) for p in (getattr(plan, "person_ids", ()) or ()) if p]
    tokens = story_search_tokens(plan)
    hits: list[StoryHit] = []
    with connection() as conn:
        about_ids: set[str] = set()
        if person_ids:
            r_about = conn.execute(
                """
                SELECT r.from_id
                FROM relationships r
                WHERE r.from_type = 'story'
                  AND r.to_type = 'person'
                  AND r.to_id = ANY(%s)
                UNION
                SELECT s.id
                FROM stories s
                JOIN story_version_people sp
                  ON sp.version_id = s.current_saved_version_id
                WHERE s.current_saved_version_id IS NOT NULL
                  AND sp.person_id = ANY(%s)
                """,
                (person_ids, person_ids),
            ).fetchall()
            about_ids = {str(r["from_id"]) for r in r_about}

        fetch_n = (
            _provider_fetch_n(0)
            if (_bounded_period_tell(plan) or int(limit) <= 0)
            else max(limit * 8, 80 if person_ids else 0)
        )
        rows = conn.execute(
            """
            SELECT
                s.id AS story_id,
                COALESCE(sv.title, s.title) AS title,
                sv.description,
                COALESCE(sv.narrator_person_id, s.narrator_person_id) AS narrator_person_id,
                s.current_version,
                sv.body_text,
                sv.version,
                sv.note,
                p.display_name AS narrator_name,
                (
                    SELECT string_agg(b.text, ' ')
                    FROM story_version_blocks b
                    WHERE b.version_id = sv.id AND COALESCE(b.text, '') <> ''
                ) AS block_text
            FROM stories s
            JOIN story_versions sv ON sv.id = s.current_saved_version_id
            LEFT JOIN people p ON p.id = COALESCE(sv.narrator_person_id, s.narrator_person_id)
            WHERE s.status = 'active'
              AND sv.lifecycle = 'saved'
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (fetch_n or (limit * 8),),
        ).fetchall()

        # Also gather person names linked via about_person
        rel_people: dict[str, list[str]] = {}
        if rows:
            ids = [r["story_id"] for r in rows]
            # psycopg handles list for ANY
            rrows = conn.execute(
                """
                SELECT r.from_id, p.display_name
                FROM relationships r
                JOIN people p ON p.id = r.to_id
                WHERE r.from_type = 'story'
                  AND r.to_type = 'person'
                  AND r.from_id = ANY(%s)
                UNION
                SELECT s.id, p.display_name
                FROM stories s
                JOIN story_version_people sp ON sp.version_id = s.current_saved_version_id
                JOIN people p ON p.id = sp.person_id
                WHERE s.id = ANY(%s)
                """,
                (ids, ids),
            ).fetchall()
            for rr in rrows:
                rel_people.setdefault(str(rr["from_id"]), []).append(
                    rr["display_name"] or ""
                )

        thumbs: dict[str, str] = {}
        if rows:
            from memorybox.story import memory_thumb_url

            trows = conn.execute(
                """
                SELECT s.id AS story_id, m.thumb_url, m.source_kind, m.source_id
                FROM stories s
                JOIN story_version_memories m ON m.version_id = s.current_saved_version_id
                WHERE s.id = ANY(%s)
                ORDER BY m.position ASC
                """,
                (ids,),
            ).fetchall()
            for tr in trows:
                sid = str(tr["story_id"])
                if sid in thumbs:
                    continue
                url = memory_thumb_url(
                    tr.get("source_kind"), tr.get("source_id"), tr.get("thumb_url")
                )
                if url:
                    thumbs[sid] = url

        for r in rows:
            sid = str(r["story_id"])
            blob = " ".join(
                [
                    r["title"] or "",
                    r.get("description") or "",
                    r["body_text"] or "",
                    r.get("block_text") or "",
                    r["narrator_name"] or "",
                    " ".join(rel_people.get(sid, [])),
                ]
            ).lower()
            match_n = sum(1 for t in tokens if t.lower() in blob)
            linked = sid in about_ids
            if match_n == 0 and not linked:
                continue
            narrator = r["narrator_name"] or "owner"
            body = r["body_text"] or r.get("block_text") or ""
            excerpt = body[:200] + ("…" if len(body) > 200 else "")
            note = str(r.get("note") or "")
            photo_m = re.search(r"mb_source_photo=(\S+)", note)
            taken_m = re.search(r"mb_taken_at=(\S+)", note)
            thumb_m = re.search(r"mb_thumb=(\S+)", note)
            photo_id = photo_m.group(1) if photo_m else None
            thumb = thumb_m.group(1) if thumb_m else thumbs.get(sid)
            if photo_id and not thumb:
                thumb = f"/library/media/photo/{photo_id}"
            hits.append(
                StoryHit(
                    story_id=sid,
                    version=int(r["version"]),
                    title=r["title"],
                    excerpt=excerpt,
                    narrator_person_id=str(r["narrator_person_id"])
                    if r["narrator_person_id"]
                    else None,
                    narrator_display_name=r["narrator_name"],
                    provenance_kind="owner_narrator_recollection",
                    attribution=f"{narrator} recalled (Story v{int(r['version'])})",
                    score=float(match_n) + (2.0 if linked else 0.0),
                    taken_at=(taken_m.group(1) if taken_m else None),
                    thumb_url=thumb,
                    source_photo_id=photo_id,
                    people=list(rel_people.get(sid) or []),
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    if _bounded_period_tell(plan) or int(limit) <= 0:
        return hits
    return hits[: max(limit, 24 if person_ids else limit)]


@dataclass
class JournalHit:
    journal_id: str
    version: int
    title: str | None
    excerpt: str
    author_person_id: str | None
    author_display_name: str | None
    captured_at: str | None
    described_start_date: str | None
    described_end_date: str | None
    described_precision: str
    provenance_kind: str
    attribution: str
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def search_journals(plan: QueryPlan, *, limit: int = 12) -> list[JournalHit]:
    """Retrieve current Journal versions via direct PG ? no journal_passage required."""
    if not getattr(plan, "want_journal", False):
        return []
    tokens = [t for t in plan.retrieval_constraints if t and len(t) >= 2]
    place_trip = _exclusive_place_trip_keywords(plan)
    if place_trip:
        tokens = [t for t in tokens if not re.fullmatch(r"(?:19|20)\d{2}", str(t))]
        have = {str(t).lower() for t in tokens}
        for k in place_trip:
            if k not in have:
                tokens.append(k)
                have.add(k)
    if not tokens:
        tokens = [
            t
            for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", plan.original_ask or "")
            if t.lower()
            not in {
                "what",
                "you",
                "know",
                "about",
                "tell",
                "have",
                "from",
                "our",
                "the",
                "trip",
                "show",
                "me",
                "emails",
                "photos",
                "journal",
                "journals",
                "entry",
                "entries",
            }
        ]
    loose = not tokens
    # Listing asks ("show my journals") must not truncate owner entries under
    # synthetic prove noise ? pull a wider recent window when unconstrained.
    unbounded = _bounded_period_tell(plan) or int(limit) <= 0
    if unbounded:
        fetch_n = _provider_fetch_n(0)
        result_n = 0
    else:
        fetch_n = max(limit * 8, 80) if loose else limit * 8
        result_n = max(limit, 50) if loose else limit

    hits: list[JournalHit] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                j.id AS journal_id,
                j.title,
                j.author_person_id,
                j.current_version,
                j.captured_at,
                j.described_start_date,
                j.described_end_date,
                j.described_precision,
                jv.body_text,
                jv.version,
                p.display_name AS author_name
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id
             AND jv.version = j.current_saved_version
             AND jv.lifecycle = 'saved'
            LEFT JOIN people p ON p.id = j.author_person_id
            WHERE j.status = 'active'
              AND j.current_saved_version IS NOT NULL
            ORDER BY j.updated_at DESC
            LIMIT %s
            """,
            (fetch_n,),
        ).fetchall()

        rel_people: dict[str, list[str]] = {}
        if rows:
            ids = [r["journal_id"] for r in rows]
            rrows = conn.execute(
                """
                SELECT r.from_id, p.display_name
                FROM relationships r
                JOIN people p ON p.id = r.to_id
                WHERE r.from_type = 'journal'
                  AND r.to_type = 'person'
                  AND r.from_id = ANY(%s)
                """,
                (ids,),
            ).fetchall()
            for rr in rrows:
                rel_people.setdefault(str(rr["from_id"]), []).append(
                    rr["display_name"] or ""
                )

        for r in rows:
            jid = str(r["journal_id"])
            blob = " ".join(
                [
                    r["title"] or "",
                    r["body_text"] or "",
                    r["author_name"] or "",
                    " ".join(rel_people.get(jid, [])),
                    str(r.get("described_start_date") or ""),
                    str(r.get("described_end_date") or ""),
                ]
            ).lower()
            if loose:
                match_n = 1
            else:
                match_n = sum(1 for t in tokens if t.lower() in blob)
                if match_n == 0:
                    continue
            if plan.time_start or plan.time_end:
                ds = str(r.get("described_start_date") or "")
                de = str(r.get("described_end_date") or "")
                if plan.time_start and de and de < plan.time_start[:10]:
                    continue
                if plan.time_end and ds and ds > plan.time_end[:10]:
                    continue
            author = r["author_name"] or "owner"
            body = r["body_text"] or ""
            excerpt = body[:200] + ("?" if len(body) > 200 else "")
            prec = r.get("described_precision") or "unknown"
            hits.append(
                JournalHit(
                    journal_id=jid,
                    version=int(r["version"]),
                    title=r["title"],
                    excerpt=excerpt,
                    author_person_id=str(r["author_person_id"])
                    if r["author_person_id"]
                    else None,
                    author_display_name=r["author_name"],
                    captured_at=str(r["captured_at"]) if r.get("captured_at") else None,
                    described_start_date=str(r["described_start_date"])
                    if r.get("described_start_date")
                    else None,
                    described_end_date=str(r["described_end_date"])
                    if r.get("described_end_date")
                    else None,
                    described_precision=prec,
                    provenance_kind="owner_journal",
                    attribution=f"{author} journaled (Journal v{int(r['version'])})",
                    score=float(match_n),
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    if result_n <= 0:
        return hits
    return hits[:result_n]

def search_artifacts(plan: QueryPlan, *, limit: int = 12) -> list[dict[str, Any]]:
    """Thin I9 Ask earn-in: Artifact identity/metadata, not filename-as-meaning."""
    if not getattr(plan, "want_artifact", False):
        return []
    from memorybox.artifact import search_artifacts_for_ask

    q = (plan.original_ask or "").strip()
    # Prefer constraint tokens / entity slots when present
    bits = list(plan.retrieval_constraints or ())
    bits.extend(plan.person_names or ())
    bits.extend(getattr(plan, "place_names", ()) or ())
    if bits:
        q = " ".join([q] + [str(b) for b in bits if b])
    art_limit = _provider_fetch_n(0) if (_bounded_period_tell(plan) or int(limit) <= 0) else limit
    return search_artifacts_for_ask(q, limit=art_limit)


def search_guided_capture(plan: QueryPlan, *, limit: int = 12) -> list[dict[str, Any]]:
    """I11: cite Guided Capture Responses directly (no Story promotion required)."""
    if not getattr(plan, "want_guided_capture", False):
        return []
    from memorybox.guided_capture import search_responses_for_ask

    return search_responses_for_ask(
        query=plan.original_ask or "",
        person_names=tuple(plan.person_names or ()),
        limit=_provider_fetch_n(0) if (_bounded_period_tell(plan) or int(limit) <= 0) else limit,
    )
