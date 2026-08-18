"""P2-I1 process recognition queue items into face_appearance_moments."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from memorybox.db import connection
from memorybox.person import AUTHORITY_AI_INFERRED, list_provider_external_ids_for_person
from memorybox.recognition.queue import (
    STATUS_COMPLETED,
    STATUS_EXCLUDED,
    STATUS_FAILED,
    claim_next_item,
    complete_item,
)


def ensure_timeslot_play_url(
    *,
    video_external_id: str,
    start_sec: float,
    play_url: str | None = None,
) -> str:
    """Return a seekable play URL (must include t= for jump-to-timeslot).

    Prefer keeping a provider media path when present, but always attach t=.
    Fall back to Review UI deep-link when no provider URL is given.
    """
    t = float(start_sec)
    raw = (play_url or "").strip()
    if not raw:
        return f"/review/ui?video={video_external_id}&t={t}"
    # HVRT worker paths are /media/{id}. Explore/Ask serve :8790 — that 404s
    # unless we send the browser through the Review proxy.
    if raw.startswith("/media/"):
        raw = "/review" + raw
    if "t=" in raw:
        return raw
    # Absolute or relative URL/path — append t=
    if "://" in raw or raw.startswith("/"):
        parts = urlparse(raw)
        q = parse_qs(parts.query, keep_blank_values=True)
        q["t"] = [str(t)]
        new_query = urlencode(q, doseq=True)
        return urlunparse(
            (parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment)
        )
    return f"/review/ui?video={video_external_id}&t={t}"


def upsert_appearance_moment(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    start_sec: float,
    end_sec: float,
    face_external_id: str | None,
    method: str,
    confidence: float | None,
    confirmation_state: str = "system_associated",
    authority: str = AUTHORITY_AI_INFERRED,
    play_url: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO face_appearance_moments (
                person_id, video_provider_key, video_external_id,
                start_sec, end_sec, face_external_id, method, confidence,
                confirmation_state, authority, play_url, meta_json
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            RETURNING id::text
            """,
            (
                person_id,
                video_provider_key,
                video_external_id,
                float(start_sec),
                float(end_sec),
                face_external_id,
                method,
                confidence,
                confirmation_state,
                authority,
                play_url,
                json.dumps(meta or {}),
            ),
        ).fetchone()
    return str(row["id"])


def list_appearance_moments(
    person_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, face_external_id, method, confidence,
                   confirmation_state, authority, play_url, meta_json, created_at
            FROM face_appearance_moments
            WHERE person_id = %s::uuid
            ORDER BY start_sec ASC
            LIMIT %s
            """,
            (person_id, int(limit)),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("created_at") is not None:
            d["created_at"] = d["created_at"].isoformat()
        if isinstance(d.get("meta_json"), str):
            d["meta_json"] = json.loads(d["meta_json"])
        # Normalize legacy rows that stored media paths without t=
        d["play_url"] = ensure_timeslot_play_url(
            video_external_id=str(d.get("video_external_id") or ""),
            start_sec=float(d.get("start_sec") or 0),
            play_url=d.get("play_url"),
        )
        out.append(d)
    return out


def process_one(
    *,
    video_provider: Any,
    person_id: str | None = None,
) -> dict[str, Any] | None:
    """Claim one queued item and process via video provider presence/search."""
    item = claim_next_item(person_id=person_id)
    if not item:
        return None
    pid = item["person_id"]
    veid = item["video_external_id"]
    try:
        # Eligibility / processability probe
        videos = {v.external_id: v for v in video_provider.list_videos(limit=5000)}
        if veid not in videos:
            complete_item(
                item["id"],
                status=STATUS_EXCLUDED,
                reason="unavailable_source",
                result={"detail": "video not in healthy source inventory"},
            )
            return {"item_id": item["id"], "status": STATUS_EXCLUDED, "reason": "unavailable_source"}

        vpk = getattr(video_provider, "provider_key", None) or item["video_provider_key"]
        face_ids: list[str] = []
        for pk in {vpk, "fake_video", "hvrt", "immich", "fake_photo"}:
            try:
                face_ids.extend(list_provider_external_ids_for_person(pid, pk))
            except Exception:  # noqa: BLE001
                continue
        # de-dupe
        face_ids = list(dict.fromkeys(face_ids))

        from memorybox.providers.video.dto import VideoSearchQuery

        hits = []
        if face_ids:
            hits = video_provider.search_segments(
                VideoSearchQuery(
                    person_external_ids=tuple(face_ids),
                    video_external_id=veid,
                    limit=50,
                )
            )
        moments = []
        for h in hits or []:
            mid = upsert_appearance_moment(
                person_id=pid,
                video_provider_key=item["video_provider_key"],
                video_external_id=veid,
                start_sec=float(h.start_sec),
                end_sec=float(h.end_sec),
                face_external_id=getattr(h, "face_external_id", None),
                method="auto_associate",
                confidence=getattr(h, "confidence", None) or 0.7,
                play_url=ensure_timeslot_play_url(
                    video_external_id=veid,
                    start_sec=float(h.start_sec),
                    play_url=getattr(h, "play_url", None),
                ),
                meta={"queue_item_id": item["id"]},
            )
            moments.append(mid)
        complete_item(
            item["id"],
            status=STATUS_COMPLETED,
            result={"moments": moments, "hit_count": len(moments)},
        )
        return {
            "item_id": item["id"],
            "status": STATUS_COMPLETED,
            "moments": moments,
            "person_id": pid,
            "video_external_id": veid,
        }
    except Exception as exc:  # noqa: BLE001
        complete_item(
            item["id"],
            status=STATUS_FAILED,
            reason=str(exc),
            result={"error": str(exc)},
        )
        return {"item_id": item["id"], "status": STATUS_FAILED, "reason": str(exc)}


def process_queue(
    *,
    video_provider: Any,
    person_id: str | None = None,
    max_items: int = 100,
) -> dict[str, Any]:
    results = []
    for _ in range(max(1, max_items)):
        r = process_one(video_provider=video_provider, person_id=person_id)
        if r is None:
            break
        results.append(r)
    return {"processed": len(results), "results": results}


def owner_correct_appearance(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    start_sec: float,
    end_sec: float | None = None,
    face_external_id: str | None = None,
) -> dict[str, Any]:
    """Owner correction creates higher-authority appearance + face evidence."""
    from memorybox.person.face_evidence import owner_confirm_or_correct

    fe = owner_confirm_or_correct(
        person_id=person_id,
        provider_key=video_provider_key,
        method="owner_correct",
        external_face_id=face_external_id,
        meta={
            "video_external_id": video_external_id,
            "start_sec": start_sec,
        },
    )
    mid = upsert_appearance_moment(
        person_id=person_id,
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        start_sec=float(start_sec),
        end_sec=float(end_sec if end_sec is not None else start_sec + 1.0),
        face_external_id=face_external_id,
        method="owner_correct",
        confidence=1.0,
        confirmation_state="owner_corrected",
        authority="owner_confirmed",
        play_url=f"/review/ui?video={video_external_id}&t={float(start_sec)}",
        meta={"face_evidence_id": fe["id"]},
    )
    return {"appearance_id": mid, "face_evidence": fe}
