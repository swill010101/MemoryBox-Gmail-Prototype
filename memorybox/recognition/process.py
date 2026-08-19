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


def _looks_like_uuid(value: str) -> bool:
    raw = (value or "").strip()
    return len(raw) == 36 and raw.count("-") == 4


def ensure_timeslot_play_url(
    *,
    video_external_id: str,
    start_sec: float,
    play_url: str | None = None,
    video_provider_key: str | None = None,
) -> str:
    """Return a seekable play URL (must include t= for jump-to-timeslot).

    Immich library videos stream at /library/media/immich-video/{asset}.
    HVRT worker paths are /media/{id} and must go through the Review proxy.
    """
    t = float(start_sec)
    vid = (video_external_id or "").strip()
    raw = (play_url or "").strip()
    pk = (video_provider_key or "").strip().lower()
    looks_immich = pk == "immich" or _looks_like_uuid(vid)
    if looks_immich:
        if (
            not raw
            or raw.startswith("/review/")
            or raw.startswith("/media/")
            or "/library/media/immich-video/" not in raw
        ):
            return f"/library/media/immich-video/{vid}?t={t}"
    if not raw:
        return f"/review/ui?video={vid}&t={t}"
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
    return f"/review/ui?video={vid}&t={t}"


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
    sql_i8b = """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, face_external_id, method, confidence,
                   confirmation_state, authority, play_url, meta_json, created_at,
                   COALESCE(status, 'accepted') AS status,
                   model_version,
                   COALESCE(evidence_lineage,
                     CASE WHEN method = 'mb_native_i8b' THEN 'mb_native_i8b' ELSE 'i1_hvrt' END
                   ) AS evidence_lineage
            FROM face_appearance_moments
            WHERE person_id = %s::uuid
            ORDER BY start_sec ASC
            LIMIT %s
            """
    sql_i1 = """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, face_external_id, method, confidence,
                   confirmation_state, authority, play_url, meta_json, created_at
            FROM face_appearance_moments
            WHERE person_id = %s::uuid
            ORDER BY start_sec ASC
            LIMIT %s
            """
    with connection() as conn:
        try:
            rows = conn.execute(sql_i8b, (person_id, int(limit))).fetchall()
        except Exception:
            conn.execute("ROLLBACK")
            rows = conn.execute(sql_i1, (person_id, int(limit))).fetchall()
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
            video_provider_key=str(d.get("video_provider_key") or ""),
        )
        out.append(d)
    return out


def get_appearance_moment(moment_id: str) -> dict[str, Any] | None:
    mid = (moment_id or "").strip()
    if not mid:
        return None
    sql = """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, face_external_id, method, confidence,
                   confirmation_state, authority, play_url, meta_json, created_at,
                   COALESCE(status, 'accepted') AS status,
                   model_version,
                   COALESCE(evidence_lineage,
                     CASE WHEN method = 'mb_native_i8b' THEN 'mb_native_i8b' ELSE 'i1_hvrt' END
                   ) AS evidence_lineage
            FROM face_appearance_moments
            WHERE id = %s::uuid
            """
    with connection() as conn:
        try:
            row = conn.execute(sql, (mid,)).fetchone()
        except Exception:
            conn.execute("ROLLBACK")
            return None
    if not row:
        return None
    d = dict(row)
    if d.get("created_at") is not None:
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("meta_json"), str):
        try:
            d["meta_json"] = json.loads(d["meta_json"])
        except json.JSONDecodeError:
            pass
    d["play_url"] = ensure_timeslot_play_url(
        video_external_id=str(d.get("video_external_id") or ""),
        start_sec=float(d.get("start_sec") or 0),
        play_url=d.get("play_url"),
        video_provider_key=str(d.get("video_provider_key") or ""),
    )
    return d


def process_one(
    *,
    video_provider: Any,
    person_id: str | None = None,
) -> dict[str, Any] | None:
    """Claim one queued item and process via MB-native I8B scan or I1 HVRT search."""
    item = claim_next_item(person_id=person_id)
    if not item:
        return None
    pid = item["person_id"]
    veid = item["video_external_id"]
    run_kind = str(item.get("enqueue_reason") or "newly_known_person")
    if run_kind in {"owner_learn", "exemplar_change"}:
        mapped_kind = "owner_learned" if run_kind == "owner_learn" else "provider_seeded"
    elif run_kind == "correction":
        mapped_kind = "correction"
    elif run_kind == "new_video":
        mapped_kind = "incremental"
    else:
        mapped_kind = "provider_seeded"
    try:
        videos = {v.external_id: v for v in video_provider.list_videos(limit=5000)}
        if veid not in videos:
            getter = getattr(video_provider, "get_video", None)
            found = None
            if callable(getter):
                try:
                    found = getter(veid)
                except Exception:
                    found = None
            if found is None:
                from memorybox.recognition.frames import looks_like_uuid, resolve_immich_video_path

                if looks_like_uuid(veid) and resolve_immich_video_path(veid) is not None:
                    vpk = "immich"
                    from memorybox.recognition.scan import scan_video_for_person

                    native = scan_video_for_person(
                        person_id=pid,
                        video_provider=video_provider,
                        video_external_id=veid,
                        video_provider_key=vpk,
                        run_kind=mapped_kind,
                        trigger=run_kind,
                    )
                    complete_item(
                        item["id"],
                        status=STATUS_COMPLETED,
                        result={
                            "engine": "mb_native_i8b",
                            "run_kind": mapped_kind,
                            "ranges": native.get("ranges") or [],
                            "hit_count": len(native.get("ranges") or []),
                            "accepted_count": native.get("accepted_count"),
                            "source": "immich_video",
                        },
                    )
                    return {
                        "item_id": item["id"],
                        "status": STATUS_COMPLETED,
                        "engine": "mb_native_i8b",
                        "run_kind": mapped_kind,
                        "moments": native.get("ranges") or [],
                        "person_id": pid,
                        "video_external_id": veid,
                    }
                complete_item(
                    item["id"],
                    status=STATUS_EXCLUDED,
                    reason="unavailable_source",
                    result={"detail": "video not in healthy source inventory"},
                )
                return {"item_id": item["id"], "status": STATUS_EXCLUDED, "reason": "unavailable_source"}
            videos[veid] = found

        vpk = getattr(video_provider, "provider_key", None) or item["video_provider_key"]
        from memorybox.recognition.exemplars import list_active_exemplars

        exemplars = list_active_exemplars(pid)
        if exemplars:
            from memorybox.recognition.scan import scan_video_for_person

            native = scan_video_for_person(
                person_id=pid,
                video_provider=video_provider,
                video_external_id=veid,
                video_provider_key=vpk,
                run_kind=mapped_kind,
                trigger=run_kind,
            )
            complete_item(
                item["id"],
                status=STATUS_COMPLETED,
                result={
                    "engine": "mb_native_i8b",
                    "run_kind": mapped_kind,
                    "ranges": native.get("ranges") or [],
                    "hit_count": len(native.get("ranges") or []),
                    "accepted_count": native.get("accepted_count"),
                    "uncertain_count": native.get("uncertain_count"),
                    "sample_error": native.get("sample_error"),
                    "candidate_count": native.get("candidate_count"),
                    "legacy_untouched": True,
                },
            )
            return {
                "item_id": item["id"],
                "status": STATUS_COMPLETED,
                "engine": "mb_native_i8b",
                "run_kind": mapped_kind,
                "moments": native.get("ranges") or [],
                "person_id": pid,
                "video_external_id": veid,
            }

        face_ids: list[str] = []
        for pk in {vpk, "fake_video", "hvrt", "immich", "fake_photo"}:
            try:
                face_ids.extend(list_provider_external_ids_for_person(pid, pk))
            except Exception:  # noqa: BLE001
                continue
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
                    video_provider_key=item.get("video_provider_key") or vpk,
                ),
                meta={"queue_item_id": item["id"], "evidence_lineage": "i1_hvrt"},
            )
            moments.append(mid)
        complete_item(
            item["id"],
            status=STATUS_COMPLETED,
            result={
                "engine": "i1_hvrt",
                "run_kind": mapped_kind,
                "moments": moments,
                "hit_count": len(moments),
            },
        )
        return {
            "item_id": item["id"],
            "status": STATUS_COMPLETED,
            "engine": "i1_hvrt",
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


def owner_withdraw_appearance(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    start_sec: float,
    end_sec: float | None = None,
    appearance_id: str | None = None,
    reason: str = "owner_withdraw",
) -> dict[str, Any]:
    """Correction safety: withdrawn identity is not restored on rescan."""
    from memorybox.recognition.observations import record_withdrawal
    from memorybox.recognition.queue import enqueue_full_eligible_archive

    end = float(end_sec if end_sec is not None else start_sec + 1.0)
    wid = record_withdrawal(
        person_id=person_id,
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        start_sec=float(start_sec),
        end_sec=end,
        appearance_id=appearance_id,
        reason=reason,
    )
    enqueue_full_eligible_archive(
        person_id=person_id,
        videos=[
            {
                "video_provider_key": video_provider_key,
                "video_external_id": video_external_id,
                "eligible": True,
                "priority": 1,
            }
        ],
        enqueue_reason="correction",
        priority=1,
        run_kind="correction",
    )
    return {"ok": True, "withdrawal_id": wid, "appearance_id": appearance_id}
