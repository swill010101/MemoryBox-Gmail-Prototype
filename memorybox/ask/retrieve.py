"""Evidence + photo retrieval for Ask (PostgreSQL / Qdrant / PhotoProvider)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Hard ceiling so a 90k-row export cannot dump the whole archive into Explore.
# Year-fair sampling keeps every year on the Timeline when we must truncate.
# The old default of 5000 oldest-first silently dropped 2020–2025 on FlightSim.
SMS_RETRIEVE_CAP = 25000


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    blob = f"{plan.original_ask or ''} {plan.effective_ask or ''} {' '.join(plan.notes or ())}"
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
    blob = f"{plan.original_ask or ''} {plan.effective_ask or ''} {' '.join(plan.notes or ())}"
    return bool(EMAIL_ASK_RE.search(blob))


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


def _sms_name_match(blob: str, names: list[str]) -> bool:
    text = (blob or "").lower()
    if not text or not names:
        return False
    for n in names:
        if not n:
            continue
        if n in text or (text.strip() and text.strip() in n):
            return True
        parts = [p for p in re.findall(r"[a-z0-9']+", n) if len(p) > 2]
        if parts and all(re.search(rf"\b{re.escape(p)}\b", text) for p in parts):
            return True
        if parts and re.search(rf"\b{re.escape(parts[0])}\b", text):
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
    if person_names and _sms_name_match(f"{sender} {handle}", person_names):
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
        thread_id=payload.get("thread_id") or payload.get("group_name"),
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
    } | _SMS_KEYWORD_EXTRA_STOP | name_tokens | set(person_names)
    keywords = [
        t.lower().replace("'", "")
        for t in re.findall(r"[A-Za-z0-9']{3,}", ask)
        if t.lower().replace("'", "") not in keyword_stop
    ]
    # Year tokens belong to the date window, not the body-text keyword filter
    if windows:
        keywords = [k for k in keywords if not re.fullmatch(r"(?:19|20)\d{2}", k)]
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
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'communication'
              AND lower(coalesce(payload_json->>'evidence_channel', ''))
                  IN ('sms', 'text', 'imessage', 'mms', 'rcs')
            """
        ).fetchall()
    for r in rows:
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
                if person_names and not _sms_name_match(blob, person_names):
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
            if not _sms_name_match(f"{blob} {handles}", person_names):
                continue
        if attach_only and not _sms_attachments(payload):
            continue
        if heart_only and not _sms_has_heart(payload, str(r["summary"] or "")):
            continue
        if keywords:
            blob = f"{r['summary'] or ''} {payload.get('body_text') or ''} {payload.get('thread_id') or ''}".lower()
            if not any(k in blob for k in keywords):
                continue
        hits.append(_sms_hit(r, payload, score=1.0))
    hits.sort(key=lambda h: (h.sent_at or "", h.evidence_id))
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
    )


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
    } | name_tokens | set(person_names)
    keywords = [
        t.lower().replace("'", "")
        for t in re.findall(r"[A-Za-z0-9']{3,}", ask)
        if t.lower().replace("'", "") not in keyword_stop
    ]
    if windows:
        keywords = [k for k in keywords if not re.fullmatch(r"(?:19|20)\d{2}", k)]
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
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'communication'
              AND lower(coalesce(payload_json->>'evidence_channel', 'email'))
                  NOT IN ('sms', 'text', 'imessage', 'mms', 'rcs')
            """
        ).fetchall()
    for r in rows:
        payload = _payload_dict(r["payload_json"])
        if str(payload.get("evidence_channel") or "email").lower() != "email":
            continue
        rows_payload.append((r, payload))

    def _keep(payload: dict[str, Any], row: dict[str, Any]) -> bool:
        if outbound_only and not payload.get("from_owner"):
            return False
        if inbound_only and payload.get("from_owner"):
            return False
        sent = str(payload.get("sent_at") or "")
        if windows:
            day = sent[:10]
            if not day or not any(str(a)[:10] <= day <= str(b)[:10] for a, b in windows):
                return False
        if person_ids:
            have = {str(x) for x in (payload.get("person_ids") or [])}
            if not (have & person_ids):
                blob = _email_person_blob(payload)
                if person_names and not _sms_name_match(blob, person_names):
                    return False
                if not person_names:
                    return False
        elif person_names:
            if not _sms_name_match(_email_person_blob(payload), person_names):
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


def search_evidence_pg(plan: QueryPlan, *, limit: int = 20) -> list[EvidenceHit]:
    """Keyword search over authoritative PostgreSQL Evidence (always available)."""
    sms_q = _sms_ask(plan) and plan.want_communication
    email_q = _email_ask(plan) and plan.want_communication
    if sms_q and email_q:
        sms = search_sms_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        mail = search_email_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
        combined = list(mail) + list(sms)
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
        # SMS-specific asks stay on the SMS corpus (do not pad with email keyword dump).
        if sms or sms_q:
            return sms
    if email_q:
        return search_email_messages(plan, limit=max(int(limit), SMS_RETRIEVE_CAP))
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
    kept: list[EvidenceHit] = []
    for h in hits:
        blob = " ".join(
            [
                h.summary or "",
                h.excerpt or "",
                " ".join(h.people or []),
                h.thread_id or "",
                h.channel or "",
            ]
        ).lower()
        if any(c.lower() in blob for c in cons):
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
        places = [str(p).lower() for p in (plan.place_names or ()) if p]
        if not windows and not places:
            return hits
        out: list[PhotoHit] = []
        for h in hits:
            # Explore keeps undated in Gallery (off the Timeline). Dropping
            # them here emptied Christmas / year asks: face stubs have no EXIF,
            # so "Peggy during Christmas" showed 0 cards ("gallery is lost").
            if windows and h.taken_at and not date_in_windows(h.taken_at, windows):
                continue
            if places:
                blob = " ".join(
                    str(x)
                    for x in (
                        h.location,
                        getattr(h, "place", None),
                        h.city,
                        h.state,
                        h.country,
                    )
                    if x
                ).lower()
                if not any(p in blob for p in places):
                    continue
            out.append(h)
        if windows:
            status["temporal_windows"] = [list(w) for w in windows]
            status["temporal_label"] = getattr(plan, "temporal_label", None)
            status["before_temporal_filter"] = len(hits)
            status["after_temporal_filter"] = len(out)
        if places:
            status["place_filter"] = list(plan.place_names)
            status["after_place_filter"] = len(out)
        return out

    def _finish(hits: list[PhotoHit]) -> tuple[list[PhotoHit], dict[str, Any]]:
        client = getattr(photo, "_client", None)
        snap = getattr(client, "diag_snapshot", None)
        if callable(snap):
            status["immich_diag"] = snap()
        filtered = _filter_photo_hits(hits)
        return filtered[:limit], status

    if not plan.want_still and not plan.want_photo:
        status["ok"] = True
        status["detail"] = "not_requested"
        return [], status
    try:
        named_person = bool(
            getattr(plan, "person_names", ()) or getattr(plan, "person_ids", ())
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
        for pid in getattr(plan, "person_ids", ()) or ():
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
                        limit=limit,
                        time_windows=tuple(
                            getattr(plan, "temporal_windows", ()) or ()
                        ),
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
                exif=dict(getattr(a, "exif", ()) or ()) or None,
                faces=_faces_for_hit(a),
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
                )
            if mapped_names or unmapped_resolvable_names:
                status["disclosure"] = (
                    (status.get("disclosure") or "")
                    + " Photo library did not return stills for this person; "
                    "video moments stay visible."
                ).strip()
            return _finish(hits)
            status["detail"] = (
                f"no_immich_person_ids names={name_queries} "
                f"unmapped_resolvable={unmapped_resolvable_names or []}"
            )
            if unmapped_resolvable_names:
                status["disclosure"] = (
                    "Resolvable MB Person(s) exist without Immich mapping; "
                    "no Immich person id resolved for name search."
                )
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


def _dedupe_video_hits(
    hits: list[VideoHit], *, window_sec: float = 2.5, limit: int = 48
) -> list[VideoHit]:
    """Collapse near-duplicate moments (HVRT segment + appearance merge).

    Prefer labeled / named / confirmed hits over generic face-appearance copies.
    """

    def _score(h: VideoHit) -> tuple[int, int, int]:
        named = 1 if (h.mb_person_name or (h.label and h.label != "face-appearance-moment")) else 0
        trust = {"confirmed": 3, "trusted_provider": 2, "candidate": 1}.get(
            h.identity_trust or "", 0
        )
        has_face = 1 if h.face_external_id else 0
        return (named, trust, has_face)

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
        if _score(h) > _score(prev):
            buckets[key] = h
    return [buckets[k] for k in order][:limit]


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

        seen_pids: set[str] = set()
        for pid in getattr(plan, "person_ids", ()) or ():
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
                limit=limit,
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
                    for mom in list_appearance_moments(pid, limit=limit):
                        vid = str(mom["video_external_id"])
                        t0 = float(mom["start_sec"])
                        slot_key = (vid, int(t0 // 2.5))
                        if slot_key in existing_keys:
                            continue
                        play = ensure_timeslot_play_url(
                            video_external_id=vid,
                            start_sec=t0,
                            play_url=mom.get("play_url"),
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
        segs = video.search_segments(VideoSearchQuery(text=text, limit=limit))
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
        return hits[:limit], status
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
    token_stop = {
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
        "grandma",
        "grandpa",
        "grandmother",
        "grandfather",
        "nana",
        "grammy",
        "gram",
        "my",
        "and",
    }
    tokens = [t for t in plan.retrieval_constraints if t and len(t) >= 2]
    if not tokens:
        tokens = [
            t
            for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", plan.original_ask or "")
            if t.lower() not in token_stop
        ]
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
                """,
                (person_ids,),
            ).fetchall()
            about_ids = {str(r["from_id"]) for r in r_about}

        fetch_n = max(limit * 8, 80 if person_ids else 0)
        rows = conn.execute(
            """
            SELECT
                s.id AS story_id,
                s.title,
                s.narrator_person_id,
                s.current_version,
                sv.body_text,
                sv.version,
                sv.note,
                p.display_name AS narrator_name
            FROM stories s
            JOIN story_versions sv
              ON sv.story_id = s.id AND sv.version = s.current_version
            LEFT JOIN people p ON p.id = s.narrator_person_id
            WHERE s.status = 'active'
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
                """,
                (ids,),
            ).fetchall()
            for rr in rrows:
                rel_people.setdefault(str(rr["from_id"]), []).append(
                    rr["display_name"] or ""
                )

        for r in rows:
            sid = str(r["story_id"])
            blob = " ".join(
                [
                    r["title"] or "",
                    r["body_text"] or "",
                    r["narrator_name"] or "",
                    " ".join(rel_people.get(sid, [])),
                ]
            ).lower()
            match_n = sum(1 for t in tokens if t.lower() in blob)
            linked = sid in about_ids
            if match_n == 0 and not linked:
                continue
            narrator = r["narrator_name"] or "owner"
            body = r["body_text"] or ""
            excerpt = body[:200] + ("?" if len(body) > 200 else "")
            note = str(r.get("note") or "")
            photo_m = re.search(r"mb_source_photo=(\S+)", note)
            taken_m = re.search(r"mb_taken_at=(\S+)", note)
            thumb_m = re.search(r"mb_thumb=(\S+)", note)
            photo_id = photo_m.group(1) if photo_m else None
            thumb = thumb_m.group(1) if thumb_m else None
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
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
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
              ON jv.journal_id = j.id AND jv.version = j.current_version
            LEFT JOIN people p ON p.id = j.author_person_id
            WHERE j.status = 'active'
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
    return search_artifacts_for_ask(q, limit=limit)


def search_guided_capture(plan: QueryPlan, *, limit: int = 12) -> list[dict[str, Any]]:
    """I11: cite Guided Capture Responses directly (no Story promotion required)."""
    if not getattr(plan, "want_guided_capture", False):
        return []
    from memorybox.guided_capture import search_responses_for_ask

    return search_responses_for_ask(
        query=plan.original_ask or "",
        person_names=tuple(plan.person_names or ()),
        limit=limit,
    )
