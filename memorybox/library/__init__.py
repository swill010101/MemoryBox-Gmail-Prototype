"""Library read API — unified evidence cards (Increment 8).

Browse without Ask. Person filter required via I6. Defensible dates + undated.
Paginated/bounded — never pull full Immich/HVRT corpora for first page.
"""
from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.person import (
    AUTHORITY_TRUSTED_PROVIDER,
    PersonServiceError,
    get_person,
    list_provider_external_ids_for_person,
)

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 50
# Per-modality fetch bound for merge (page-scoped, not full corpus)
_MODALITY_FETCH_CAP = 40


class LibraryServiceError(Exception):
    pass


@dataclass
class LibraryCard:
    card_id: str
    modality: str
    title: str
    summary: str | None = None
    browse_date: str | None = None
    browse_date_end: str | None = None
    date_provenance: str = "undated"
    date_precision: str | None = None
    undated: bool = True
    capture_at: str | None = None
    identity_trust: str | None = None
    person_ids: list[str] = field(default_factory=list)
    person_names: list[str] = field(default_factory=list)
    provider_key: str | None = None
    external_id: str | None = None
    domain_id: str | None = None
    deep_links: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def _parse_uuid(value: str, *, field_name: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise LibraryServiceError(f"{field_name} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise LibraryServiceError(f"{field_name} must be a UUID") from exc


def _encode_cursor(offset: int) -> str:
    raw = json.dumps({"o": int(offset)}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return max(0, int(data.get("o") or 0))
    except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
        raise LibraryServiceError("invalid cursor")


def _sort_key(card: LibraryCard) -> tuple:
    # Dated first (newest), undated last
    if card.undated or not card.browse_date:
        return (1, "", card.card_id)
    return (0, card.browse_date, card.card_id)


def _trust_for_person(person) -> str:
    if person is None:
        return "n/a"
    if getattr(person, "identity_authority", None) == AUTHORITY_TRUSTED_PROVIDER:
        return "trusted_provider"
    if person.status == "confirmed":
        return "confirmed"
    return "trusted_provider"


def _stories_for_person(person_id: UUID, *, limit: int) -> list[LibraryCard]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT s.id, s.title, s.narrator_person_id, s.created_at, s.updated_at,
                   sv.body_text
            FROM stories s
            LEFT JOIN story_versions sv
              ON sv.story_id = s.id AND sv.version = s.current_version
            WHERE s.status = 'active'
              AND (
                s.narrator_person_id = %s
                OR EXISTS (
                  SELECT 1 FROM relationships r
                  WHERE r.from_type = 'story' AND r.from_id = s.id
                    AND r.to_type = 'person' AND r.to_id = %s
                    AND r.relationship_kind = 'about_person'
                    AND r.status IN ('candidate', 'confirmed')
                )
              )
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (person_id, person_id, limit),
        ).fetchall()
    out: list[LibraryCard] = []
    for r in rows:
        sid = str(r["id"])
        body = (r.get("body_text") or "")[:240]
        # No described/event date column yet — explicit undated (do not invent)
        out.append(
            LibraryCard(
                card_id=f"story:{sid}",
                modality="story",
                title=(r.get("title") or "Story").strip() or "Story",
                summary=body or None,
                browse_date=None,
                date_provenance="undated",
                undated=True,
                capture_at=_iso(r.get("created_at")),
                identity_trust="confirmed",
                person_ids=[str(person_id)],
                domain_id=sid,
                deep_links={"story": f"/story/ui?id={sid}", "people": "/people/ui"},
                provenance={
                    "kind": "story",
                    "note": "No described/event date on Story — undated (not invented)",
                },
            )
        )
    return out


def _journals_for_person(person_id: UUID, *, limit: int) -> list[LibraryCard]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT j.id, j.title, j.author_person_id, j.created_at, j.updated_at,
                   j.captured_at, j.described_start_date, j.described_end_date,
                   j.described_precision, jv.body_text
            FROM journal_entries j
            LEFT JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.current_version
            WHERE j.status = 'active'
              AND (
                j.author_person_id = %s
                OR EXISTS (
                  SELECT 1 FROM relationships r
                  WHERE r.from_type = 'journal' AND r.from_id = j.id
                    AND r.to_type = 'person' AND r.to_id = %s
                    AND r.relationship_kind = 'about_person'
                    AND r.status IN ('candidate', 'confirmed')
                )
              )
            ORDER BY j.updated_at DESC
            LIMIT %s
            """,
            (person_id, person_id, limit),
        ).fetchall()
    out: list[LibraryCard] = []
    for r in rows:
        jid = str(r["id"])
        body = (r.get("body_text") or "")[:240]
        start = r.get("described_start_date")
        end = r.get("described_end_date")
        precision = (r.get("described_precision") or "unknown").strip()
        capture = _iso(r.get("captured_at")) or _iso(r.get("created_at"))
        if start and precision != "unknown":
            undated = False
            browse = _iso(start)
            browse_end = _iso(end) if end else None
            prov = "journal.described_start_date"
            prec = precision
        else:
            undated = True
            browse = None
            browse_end = None
            prov = "undated"
            prec = precision if precision else "unknown"
        out.append(
            LibraryCard(
                card_id=f"journal:{jid}",
                modality="journal",
                title=(r.get("title") or "Journal").strip() or "Journal",
                summary=body or None,
                browse_date=browse,
                browse_date_end=browse_end,
                date_provenance=prov,
                date_precision=prec,
                undated=undated,
                capture_at=capture,
                identity_trust="confirmed",
                person_ids=[str(person_id)],
                domain_id=jid,
                deep_links={
                    "journal": f"/journal/ui?id={jid}",
                    "people": "/people/ui",
                },
                provenance={
                    "kind": "journal",
                    "described_precision": precision,
                    "capture_at": capture,
                    "note": (
                        "Browse uses described/effective date when defensible; "
                        "capture_at is separate (I5A)"
                    ),
                },
            )
        )
    return out


def _email_for_person(
    person_id: UUID, person_name: str | None, *, limit: int
) -> list[LibraryCard]:
    """Optional earn-in: emails are not strongly person-linked in PG yet.

    When filtering by Person, include communication Evidence whose payload
    subject/from/to mentions the Person display name (disclosure in provenance).
    Never invent dates — use payload.sent_at or undated.
    """
    name = (person_name or "").strip()
    if len(name) < 2:
        return []
    needle = f"%{name}%"
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json, created_at
            FROM evidence
            WHERE evidence_kind = 'communication'
              AND (
                summary ILIKE %s
                OR payload_json::text ILIKE %s
              )
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (needle, needle, limit),
        ).fetchall()
    out: list[LibraryCard] = []
    for r in rows:
        eid = str(r["id"])
        payload = r.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
        sent = payload.get("sent_at")
        subject = payload.get("subject") or r.get("summary") or "Email"
        if sent:
            undated = False
            browse = _iso(sent)
            prov = "email.payload.sent_at"
        else:
            undated = True
            browse = None
            prov = "undated"
        out.append(
            LibraryCard(
                card_id=f"email:{eid}",
                modality="email",
                title=str(subject)[:120],
                summary=(r.get("summary") or None),
                browse_date=browse,
                date_provenance=prov,
                undated=undated,
                identity_trust=None,
                person_ids=[str(person_id)],
                person_names=[name] if name else [],
                domain_id=eid,
                deep_links={"ask": "/ask/ui", "people": "/people/ui"},
                provenance={
                    "kind": "communication",
                    "match": "display_name_in_payload_or_summary",
                    "note": "Thin person association via name match — not a hard identity link",
                },
            )
        )
    return out


def _calendar_for_person(
    person_id: UUID, person_name: str | None, *, limit: int
) -> list[LibraryCard]:
    name = (person_name or "").strip()
    if len(name) < 2:
        return []
    needle = f"%{name}%"
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json, created_at
            FROM evidence
            WHERE evidence_kind = 'calendar_event'
              AND (
                summary ILIKE %s
                OR payload_json::text ILIKE %s
              )
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (needle, needle, limit),
        ).fetchall()
    out: list[LibraryCard] = []
    for r in rows:
        eid = str(r["id"])
        payload = r.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
        start = payload.get("start")
        end = payload.get("end")
        title = payload.get("title") or r.get("summary") or "Calendar event"
        if start:
            undated = False
            browse = _iso(start)
            browse_end = _iso(end) if end else None
            prov = "calendar.payload.start"
        else:
            undated = True
            browse = None
            browse_end = None
            prov = "undated"
        out.append(
            LibraryCard(
                card_id=f"calendar:{eid}",
                modality="calendar",
                title=str(title)[:120],
                summary=(r.get("summary") or None),
                browse_date=browse,
                browse_date_end=browse_end,
                date_provenance=prov,
                undated=undated,
                person_ids=[str(person_id)],
                person_names=[name] if name else [],
                domain_id=eid,
                deep_links={"ask": "/ask/ui"},
                provenance={"kind": "calendar_event"},
            )
        )
    return out


def _photos_for_person(
    person,
    *,
    photo: Any,
    limit: int,
    date_from: datetime | None,
    date_to: datetime | None,
    status: dict[str, Any],
) -> list[LibraryCard]:
    if photo is None:
        status["photo"] = {"ok": False, "unavailable": True, "detail": "no photo provider"}
        return []
    try:
        h = photo.health()
        if not h.ok:
            status["photo"] = {
                "ok": False,
                "unavailable": True,
                "detail": h.detail or "unhealthy",
                "provider_key": h.provider_key,
            }
            return []
        pk = getattr(photo, "provider_key", "immich") or "immich"
        keys = [pk]
        if pk == "fake_photo":
            keys = ["fake_photo", "immich"]
        elif pk == "immich":
            keys = ["immich", "fake_photo"]
        ext_ids: list[str] = []
        for k in keys:
            ext_ids.extend(list_provider_external_ids_for_person(person.id, k))
        ext_ids = list(dict.fromkeys(ext_ids))
        if not ext_ids:
            status["photo"] = {
                "ok": True,
                "unavailable": False,
                "detail": "no_provider_mapping",
                "provider_key": pk,
            }
            return []
        from memorybox.providers.photo.dto import PhotoSearchQuery

        assets = photo.search_assets(
            PhotoSearchQuery(
                person_external_ids=tuple(ext_ids[:20]),
                taken_after=date_from,
                taken_before=date_to,
                limit=min(limit, _MODALITY_FETCH_CAP),
            )
        )
        status["photo"] = {
            "ok": True,
            "unavailable": False,
            "detail": f"hits={len(assets)}",
            "provider_key": pk,
        }
        trust = _trust_for_person(person)
        # Prefer mapping-row authority when Immich mapping is trusted_provider
        for m in person.provider_mappings or []:
            if m.get("provider_key") in keys and m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                trust = "trusted_provider"
                break
        out: list[LibraryCard] = []
        for a in assets:
            taken = a.taken_at
            if taken:
                undated = False
                browse = _iso(taken)
                prov = "photo.taken_at"
            else:
                undated = True
                browse = None
                prov = "undated"
            out.append(
                LibraryCard(
                    card_id=f"photo:{a.provider_key}:{a.external_id}",
                    modality="photo",
                    title=a.original_filename or "Photo",
                    summary=None,
                    browse_date=browse,
                    date_provenance=prov,
                    undated=undated,
                    identity_trust=trust,
                    person_ids=[person.id],
                    person_names=[person.display_name] if person.display_name else [],
                    provider_key=a.provider_key,
                    external_id=a.external_id,
                    deep_links={
                        "ask": "/ask/ui",
                        "people": f"/people/ui?person_id={person.id}",
                    },
                    provenance={
                        "kind": "photo",
                        "thumb_url": a.thumb_url,
                        "web_url": a.web_url,
                    },
                )
            )
        return out
    except Exception as exc:  # noqa: BLE001
        status["photo"] = {
            "ok": False,
            "unavailable": True,
            "detail": str(exc),
        }
        return []


def _videos_for_person(
    person,
    *,
    video: Any,
    limit: int,
    status: dict[str, Any],
) -> list[LibraryCard]:
    if video is None:
        status["video"] = {"ok": False, "unavailable": True, "detail": "no video provider"}
        return []
    try:
        h = video.health()
        if not h.ok:
            status["video"] = {
                "ok": False,
                "unavailable": True,
                "detail": h.detail or "unhealthy",
                "provider_key": h.provider_key,
            }
            return []
        pk = getattr(video, "provider_key", "hvrt") or "hvrt"
        keys = [pk]
        if pk == "fake_video":
            keys = ["fake_video", "hvrt"]
        ext_ids: list[str] = []
        for k in keys:
            ext_ids.extend(list_provider_external_ids_for_person(person.id, k))
        ext_ids = list(dict.fromkeys(ext_ids))
        if not ext_ids:
            status["video"] = {
                "ok": True,
                "unavailable": False,
                "detail": "no_provider_mapping",
                "provider_key": pk,
            }
            return []
        from memorybox.providers.video.dto import VideoSearchQuery

        segs = video.search_segments(
            VideoSearchQuery(
                person_external_ids=tuple(ext_ids[:20]),
                limit=min(limit, _MODALITY_FETCH_CAP),
            )
        )
        status["video"] = {
            "ok": True,
            "unavailable": False,
            "detail": f"hits={len(segs)}",
            "provider_key": pk,
        }
        trust = "confirmed"
        for m in person.provider_mappings or []:
            if m.get("provider_key") in keys:
                if m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER:
                    trust = "trusted_provider"
                break
        out: list[LibraryCard] = []
        for s in segs:
            # Segment times are in-video offsets, not calendar dates — undated
            # unless provider exposes a media date later.
            out.append(
                LibraryCard(
                    card_id=f"video:{s.provider_key}:{s.external_id}",
                    modality="video",
                    title=s.label or s.video_external_id or "Video segment",
                    summary=f"{s.start_sec:.1f}s–{s.end_sec:.1f}s",
                    browse_date=None,
                    date_provenance="undated",
                    undated=True,
                    identity_trust=trust,
                    person_ids=[person.id],
                    person_names=[person.display_name] if person.display_name else [],
                    provider_key=s.provider_key,
                    external_id=s.external_id,
                    deep_links={
                        "review": (
                            f"/review/ui?video={s.video_external_id}"
                            f"&t={s.start_sec}"
                        ),
                        "people": f"/people/ui?person_id={person.id}",
                    },
                    provenance={
                        "kind": "video_segment",
                        "video_external_id": s.video_external_id,
                        "start_sec": s.start_sec,
                        "end_sec": s.end_sec,
                        "face_external_id": s.face_external_id,
                        "note": (
                            "In-video span is not a calendar browse date — undated "
                            "until media date is known"
                        ),
                    },
                )
            )
        return out
    except Exception as exc:  # noqa: BLE001
        status["video"] = {
            "ok": False,
            "unavailable": True,
            "detail": str(exc),
        }
        return []


def list_library_cards(
    *,
    person_id: str,
    modalities: list[str] | None = None,
    bucket: str = "timeline",
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    photo: Any | None = None,
    video: Any | None = None,
) -> dict[str, Any]:
    """Paginated Library cards for a required MB Person.

    bucket: timeline (dated only) | undated | all
    """
    pid = _parse_uuid(person_id, field_name="person_id")
    person = get_person(str(pid))
    if not person or person.status == "merged_away":
        raise LibraryServiceError("person not found")

    lim = max(1, min(int(limit or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
    offset = _decode_cursor(cursor)
    bucket_norm = (bucket or "timeline").strip().lower()
    if bucket_norm not in {"timeline", "undated", "all"}:
        raise LibraryServiceError("bucket must be timeline|undated|all")

    wanted = None
    if modalities:
        wanted = {m.strip().lower() for m in modalities if (m or "").strip()}
        if not wanted:
            wanted = None

    df = None
    dt = None
    if date_from:
        try:
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LibraryServiceError("date_from must be ISO datetime/date") from exc
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LibraryServiceError("date_to must be ISO datetime/date") from exc

    if photo is None or video is None:
        from memorybox.ask.deps import build_photo, build_video

        if photo is None:
            photo = build_photo()
        if video is None:
            video = build_video()

    provider_status: dict[str, Any] = {}
    fetch_n = min(_MODALITY_FETCH_CAP, lim + offset + 5)
    cards: list[LibraryCard] = []

    def _want(mod: str) -> bool:
        return wanted is None or mod in wanted

    if _want("story"):
        cards.extend(_stories_for_person(pid, limit=fetch_n))
    if _want("journal"):
        cards.extend(_journals_for_person(pid, limit=fetch_n))
    if _want("email"):
        cards.extend(
            _email_for_person(pid, person.display_name, limit=fetch_n)
        )
    if _want("calendar"):
        cards.extend(
            _calendar_for_person(pid, person.display_name, limit=fetch_n)
        )
    if _want("photo"):
        cards.extend(
            _photos_for_person(
                person,
                photo=photo,
                limit=fetch_n,
                date_from=df,
                date_to=dt,
                status=provider_status,
            )
        )
    if _want("video"):
        cards.extend(
            _videos_for_person(
                person, video=video, limit=fetch_n, status=provider_status
            )
        )

    # Attach display name
    for c in cards:
        if person.display_name and person.display_name not in c.person_names:
            c.person_names = list(dict.fromkeys([*c.person_names, person.display_name]))

    if bucket_norm == "timeline":
        cards = [c for c in cards if not c.undated and c.browse_date]
    elif bucket_norm == "undated":
        cards = [c for c in cards if c.undated or not c.browse_date]

    # Optional date window on browse_date (timeline items)
    if df or dt:
        filtered: list[LibraryCard] = []
        for c in cards:
            if c.undated or not c.browse_date:
                if bucket_norm == "undated":
                    filtered.append(c)
                continue
            try:
                bd = datetime.fromisoformat(c.browse_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if df and bd < df:
                continue
            if dt and bd > dt:
                continue
            filtered.append(c)
        cards = filtered

    # Sort: timeline newest-first among dated; undated by card_id
    if bucket_norm == "undated":
        cards.sort(key=lambda c: c.card_id)
    else:
        cards.sort(key=_sort_key, reverse=False)
        # _sort_key puts dated as (0, date, id) — reverse True for newest first among dated
        dated = [c for c in cards if not c.undated]
        undated = [c for c in cards if c.undated]
        dated.sort(key=lambda c: (c.browse_date or "", c.card_id), reverse=True)
        cards = dated + undated

    page = cards[offset : offset + lim]
    next_off = offset + lim
    next_cursor = _encode_cursor(next_off) if next_off < len(cards) else None

    modalities_present = sorted({c.modality for c in cards})
    return {
        "ok": True,
        "person_id": person.id,
        "person_display_name": person.display_name,
        "bucket": bucket_norm,
        "cards": [c.to_dict() for c in page],
        "count": len(page),
        "total_matched_bounded": len(cards),
        "next_cursor": next_cursor,
        "modalities_present": modalities_present,
        "provider_status": provider_status,
        "view_hint": "timeline_default_gallery_alternate_same_api",
    }


def get_library_card(
    card_id: str,
    *,
    person_id: str,
    photo: Any | None = None,
    video: Any | None = None,
) -> LibraryCard | None:
    """Thin detail: re-list bounded page and find card (sufficient for I8)."""
    raw = (card_id or "").strip()
    if not raw:
        raise LibraryServiceError("card_id required")
    result = list_library_cards(
        person_id=person_id,
        bucket="all",
        limit=MAX_PAGE_SIZE,
        photo=photo,
        video=video,
    )
    for c in result.get("cards") or []:
        if c.get("card_id") == raw:
            return LibraryCard(**{k: c.get(k) for k in LibraryCard.__dataclass_fields__})
    # Scan further pages lightly
    cursor = result.get("next_cursor")
    while cursor:
        result = list_library_cards(
            person_id=person_id,
            bucket="all",
            limit=MAX_PAGE_SIZE,
            cursor=cursor,
            photo=photo,
            video=video,
        )
        for c in result.get("cards") or []:
            if c.get("card_id") == raw:
                return LibraryCard(
                    **{k: c.get(k) for k in LibraryCard.__dataclass_fields__}
                )
        cursor = result.get("next_cursor")
    return None
