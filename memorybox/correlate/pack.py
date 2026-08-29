"""Build a cross-source evidence pack with coverage and GRAPH-03 filters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memorybox.correlate.store import date_conflicts, list_links, rejected_subject_keys
from memorybox.planner import QueryPlan


COVERAGE_KEYS = (
    "photos",
    "video",
    "spoken",
    "email",
    "sms",
    "calendar",
    "story",
    "journal",
    "artifact",
)


@dataclass
class CrossSourcePack:
    coverage: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dropped_rejected: int = 0
    hydrated_confirmed: int = 0
    event_id: str | None = None
    place_id: str | None = None
    summary: str = ""


def _is_sms(hit: Any) -> bool:
    if isinstance(hit, dict):
        ch = str(hit.get("channel") or hit.get("evidence_kind") or "").lower()
        kind = str(hit.get("evidence_kind") or hit.get("kind") or "").lower()
    else:
        ch = str(getattr(hit, "channel", "") or "").lower()
        kind = str(getattr(hit, "evidence_kind", "") or "").lower()
    return ch in {"sms", "text", "imessage", "mms", "rcs"} or kind in {
        "sms",
        "text",
    }


def _is_email(hit: Any) -> bool:
    if isinstance(hit, dict):
        ch = str(hit.get("channel") or "").lower()
        kind = str(hit.get("evidence_kind") or hit.get("kind") or "").lower()
    else:
        ch = str(getattr(hit, "channel", "") or "").lower()
        kind = str(getattr(hit, "evidence_kind", "") or "").lower()
    return ch == "email" or kind == "email" or "mail" in ch


def _is_calendar(hit: Any) -> bool:
    if isinstance(hit, dict):
        kind = str(hit.get("evidence_kind") or hit.get("kind") or "").lower()
        ch = str(hit.get("channel") or "").lower()
    else:
        kind = str(getattr(hit, "evidence_kind", "") or "").lower()
        ch = str(getattr(hit, "channel", "") or "").lower()
    return kind == "calendar_event" or ch == "calendar"


def _hit_key(kind: str, hit: Any) -> tuple[str, str]:
    if isinstance(hit, dict):
        hid = str(
            hit.get("evidence_id")
            or hit.get("external_id")
            or hit.get("story_id")
            or hit.get("journal_id")
            or hit.get("artifact_id")
            or hit.get("id")
            or ""
        )
    else:
        hid = str(
            getattr(hit, "evidence_id", None)
            or getattr(hit, "external_id", None)
            or getattr(hit, "story_id", None)
            or getattr(hit, "journal_id", None)
            or getattr(hit, "id", None)
            or ""
        )
    return (kind, hid)


def _filter_rejected(kind: str, items: list[Any], rejected: set[tuple[str, str]]) -> tuple[list[Any], int]:
    if not rejected:
        return list(items), 0
    kept: list[Any] = []
    dropped = 0
    for item in items:
        key = _hit_key(kind, item)
        if key in rejected or ("evidence", key[1]) in rejected:
            dropped += 1
            continue
        kept.append(item)
    return kept, dropped


def _ids_in(kind: str, items: list[Any]) -> set[str]:
    return {k[1] for k in (_hit_key(kind, it) for it in items) if k[1]}


def _load_evidence_hit(evidence_id: str) -> Any | None:
    from uuid import UUID

    from memorybox.ask.retrieve import EvidenceHit, _excerpt, _payload_dict
    from memorybox.ingest.store import get_evidence

    try:
        row = get_evidence(UUID(str(evidence_id)))
    except Exception:  # noqa: BLE001
        return None
    if not row:
        return None
    payload = _payload_dict(row.get("payload_json"))
    kind = str(row.get("evidence_kind") or "unknown")
    people = [str(p) for p in (payload.get("people") or []) if str(p).strip()]
    return EvidenceHit(
        evidence_id=str(row["id"]),
        evidence_kind=kind,
        summary=str(row.get("summary") or ""),
        score=1.0,
        excerpt=_excerpt(payload, kind),
        source="correlation_confirmed",
        sent_at=str(payload.get("sent_at") or "") or None,
        channel=str(payload.get("channel") or payload.get("evidence_channel") or "") or None,
        people=people or None,
    )


def _load_artifact_hit(artifact_id: str) -> dict[str, Any] | None:
    from memorybox.artifact import get_artifact

    try:
        view = get_artifact(str(artifact_id))
    except Exception:  # noqa: BLE001
        return None
    if not view:
        return None
    return {
        "artifact_id": view.id,
        "kind": view.kind,
        "label": view.label,
        "description": view.description,
        "person_ids": view.person_ids,
        "story_ids": view.story_ids,
        "hydrated": True,
        "correlation_status": "confirmed",
        "deep_link": f"/artifact/ui?id={view.id}",
    }


def _hydrate_confirmed(
    event_id: str,
    *,
    evidence: list[Any],
    photos: list[Any],
    videos: list[Any],
    stories: list[Any],
    journals: list[Any],
    artifacts: list[Any],
    rejected: set[tuple[str, str]],
) -> tuple[list[Any], list[Any], list[Any], list[Any], list[Any], list[Any], int]:
    """Owner-confirmed links stay in the pack even when keyword retrieve missed them."""
    confirmed = list_links(
        object_type="event",
        object_id=event_id,
        statuses=("confirmed",),
        limit=2000,
    )
    ev_ids = _ids_in("evidence", evidence)
    photo_ids = _ids_in("photo", photos)
    video_ids = _ids_in("video", videos)
    story_ids = _ids_in("story", stories)
    journal_ids = _ids_in("journal", journals)
    art_ids = _ids_in("artifact", artifacts)
    added = 0
    for link in confirmed:
        st = str(link.get("subject_type") or "")
        sid = str(link.get("subject_id") or "")
        if not st or not sid:
            continue
        if (st, sid) in rejected or (st == "evidence" and ("evidence", sid) in rejected):
            continue
        if st == "evidence" and sid not in ev_ids:
            hit = _load_evidence_hit(sid)
            if hit:
                evidence.append(hit)
                ev_ids.add(sid)
                added += 1
        elif st == "artifact" and sid not in art_ids:
            hit = _load_artifact_hit(sid)
            if hit:
                artifacts.append(hit)
                art_ids.add(sid)
                added += 1
        elif st == "photo" and sid not in photo_ids:
            photos.append({"external_id": sid, "attribution": "correlation_confirmed", "hydrated": True})
            photo_ids.add(sid)
            added += 1
        elif st == "video" and sid not in video_ids:
            videos.append(
                {
                    "external_id": sid,
                    "video_external_id": sid,
                    "attribution": "correlation_confirmed",
                    "hydrated": True,
                }
            )
            video_ids.add(sid)
            added += 1
        elif st == "story" and sid not in story_ids:
            stories.append({"story_id": sid, "title": "Confirmed story", "hydrated": True})
            story_ids.add(sid)
            added += 1
        elif st == "journal" and sid not in journal_ids:
            journals.append({"journal_id": sid, "hydrated": True})
            journal_ids.add(sid)
            added += 1
    return evidence, photos, videos, stories, journals, artifacts, added


def apply_cross_source(
    plan: QueryPlan,
    *,
    evidence: list[Any],
    photos: list[Any],
    videos: list[Any],
    stories: list[Any],
    journals: list[Any],
    artifacts: list[Any],
    event_id: str | None = None,
    place_id: str | None = None,
) -> tuple[CrossSourcePack, dict[str, list[Any]]]:
    """Filter rejected links, hydrate confirmed extras, compute coverage. Does not invent hits."""
    rejected: set[tuple[str, str]] = set()
    conflicts: list[dict[str, Any]] = []
    hydrated_confirmed = 0
    if event_id:
        rejected |= rejected_subject_keys("event", event_id)
        conflicts = date_conflicts(event_id)
        evidence, photos, videos, stories, journals, artifacts, hydrated_confirmed = _hydrate_confirmed(
            event_id,
            evidence=list(evidence),
            photos=list(photos),
            videos=list(videos),
            stories=list(stories),
            journals=list(journals),
            artifacts=list(artifacts),
            rejected=rejected,
        )
    if place_id:
        rejected |= rejected_subject_keys("place", place_id)

    dropped = 0
    evidence, n = _filter_rejected("evidence", evidence, rejected)
    dropped += n
    photos, n = _filter_rejected("photo", photos, rejected)
    dropped += n
    videos, n = _filter_rejected("video", videos, rejected)
    dropped += n
    stories, n = _filter_rejected("story", stories, rejected)
    dropped += n
    journals, n = _filter_rejected("journal", journals, rejected)
    dropped += n
    artifacts, n = _filter_rejected("artifact", artifacts, rejected)
    dropped += n

    spoken_n = 0
    video_n = 0
    for v in videos:
        spoken = False
        if isinstance(v, dict):
            spoken = bool(v.get("spoken_text") or v.get("attribution") == "spoken_moment")
        else:
            spoken = bool(getattr(v, "spoken_text", None) or getattr(v, "attribution", "") == "spoken_moment")
        if spoken:
            spoken_n += 1
        else:
            video_n += 1

    email_n = sum(1 for h in evidence if _is_email(h))
    sms_n = sum(1 for h in evidence if _is_sms(h))
    cal_n = sum(1 for h in evidence if _is_calendar(h))

    coverage = {
        "photos": len(photos),
        "video": video_n,
        "spoken": spoken_n,
        "email": email_n,
        "sms": sms_n,
        "calendar": cal_n,
        "story": len(stories),
        "journal": len(journals),
        "artifact": len(artifacts),
    }
    missing = [k for k, v in coverage.items() if int(v or 0) == 0]
    present = [f"{k} {v}" for k, v in coverage.items() if int(v or 0) > 0]
    theme = ", ".join(getattr(plan, "theme_labels", ()) or ()) or "this ask"
    people = ", ".join(plan.person_names or ()) or "the archive"
    summary = (
        f"Everything about {theme} for {people}: "
        + (", ".join(present) if present else "no sourced items yet")
        + "."
    )
    if missing:
        summary += " Missing: " + ", ".join(missing) + " (0 — not the same as unavailable)."
    if conflicts:
        dates = ", ".join(c["observed_date"] for c in conflicts)
        summary += f" Date conflict on this event: {dates}. Both kept; MemoryBox did not pick a winner."
    if dropped:
        summary += f" {dropped} item(s) omitted because the owner rejected that correlation."

    pack = CrossSourcePack(
        coverage=coverage,
        conflicts=conflicts,
        missing=missing,
        dropped_rejected=dropped,
        hydrated_confirmed=hydrated_confirmed,
        event_id=event_id,
        place_id=place_id,
        summary=summary,
    )
    filtered = {
        "evidence": evidence,
        "photos": photos,
        "videos": videos,
        "stories": stories,
        "journals": journals,
        "artifacts": artifacts,
    }
    return pack, filtered


def propose_theme_links(
    *,
    event_id: str,
    evidence_hits: list[Any],
    theme: str,
) -> list[dict[str, Any]]:
    """System-candidate links from retrieved evidence. Never auto-confirm."""
    from memorybox.correlate.store import upsert_link

    out: list[dict[str, Any]] = []
    needle = (theme or "").strip().lower()
    for h in evidence_hits:
        if isinstance(h, dict):
            eid = str(h.get("evidence_id") or "")
            blob = " ".join(
                str(h.get(k) or "")
                for k in ("summary", "excerpt", "channel", "evidence_kind")
            )
            sent = str(h.get("sent_at") or "")[:10] or None
        else:
            eid = str(getattr(h, "evidence_id", "") or "")
            blob = " ".join(
                str(getattr(h, k, "") or "")
                for k in ("summary", "excerpt", "channel", "evidence_kind")
            )
            sent = str(getattr(h, "sent_at", "") or "")[:10] or None
        if not eid:
            continue
        if needle and needle not in blob.lower() and not getattr(
            h, "match_total", None
        ):
            # Still link retrieved hits: they already passed person/theme retrieve.
            pass
        out.append(
            upsert_link(
                subject_type="evidence",
                subject_id=eid,
                object_type="event",
                object_id=event_id,
                predicate="about",
                evidence_id=eid,
                authority="system",
                status="candidate",
                observed_date=sent if sent and len(sent) >= 8 else None,
                provenance={"theme": theme, "source": "i10_retrieve"},
            )
        )
    return out
