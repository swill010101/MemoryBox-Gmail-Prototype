"""Owner Learn from existing Review box/Teach — no new Person Learn UX."""
from __future__ import annotations

from typing import Any

from memorybox.person import AUTHORITY_OWNER_CONFIRMED
from memorybox.person.face_evidence import CONFIRM_OWNER
from memorybox.recognition.constants import (
    MODEL_ID,
    PRIORITY_OTHER_VIDEO,
)
from memorybox.recognition.crops import decode_data_url_jpeg, parse_bbox, quality_flags
from memorybox.recognition.embeddings import embed_jpeg_bytes
from memorybox.recognition.exemplars import persist_exemplar
from memorybox.recognition.queue import enqueue_full_eligible_archive
from memorybox.recognition.scan import scan_video_for_person


def save_pending_review_crop(
    *,
    face_external_id: str,
    video_external_id: str | None,
    t_sec: float | None,
    bbox: dict[str, Any] | None,
    crop_jpeg_base64: str | None,
) -> None:
    from memorybox.db import connection
    import json

    if not face_external_id:
        return
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_review_face_crops (
                face_external_id, video_external_id, t_sec, bbox_json, crop_jpeg_base64
            ) VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (face_external_id) DO UPDATE SET
                video_external_id = COALESCE(EXCLUDED.video_external_id, pending_review_face_crops.video_external_id),
                t_sec = COALESCE(EXCLUDED.t_sec, pending_review_face_crops.t_sec),
                bbox_json = COALESCE(EXCLUDED.bbox_json, pending_review_face_crops.bbox_json),
                crop_jpeg_base64 = COALESCE(EXCLUDED.crop_jpeg_base64, pending_review_face_crops.crop_jpeg_base64),
                updated_at = now()
            """,
            (
                face_external_id,
                video_external_id,
                t_sec,
                json.dumps(bbox or {}),
                crop_jpeg_base64,
            ),
        )


def take_pending_review_crop(face_external_id: str) -> dict[str, Any] | None:
    from memorybox.db import connection
    import json

    with connection() as conn:
        row = conn.execute(
            """
            SELECT face_external_id, video_external_id, t_sec, bbox_json, crop_jpeg_base64
            FROM pending_review_face_crops
            WHERE face_external_id = %s
            """,
            (face_external_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("bbox_json"), str):
        d["bbox_json"] = json.loads(d["bbox_json"])
    return d


def owner_learn_from_review(
    *,
    person_id: str,
    face_external_id: str,
    video_provider: Any,
    video_external_id: str | None = None,
    t_sec: float | None = None,
    bbox: dict[str, Any] | None = None,
    crop_jpeg_base64: str | None = None,
    embedding: list[float] | None = None,
    provider_key: str | None = None,
) -> dict[str, Any]:
    pending = take_pending_review_crop(face_external_id) or {}
    video_external_id = video_external_id or pending.get("video_external_id")
    t_sec = t_sec if t_sec is not None else pending.get("t_sec")
    bbox = bbox or pending.get("bbox_json")
    crop_jpeg_base64 = crop_jpeg_base64 or pending.get("crop_jpeg_base64")
    vpk = provider_key or getattr(video_provider, "provider_key", None) or "hvrt"
    parsed = parse_bbox(bbox) if bbox else None
    q = quality_flags(parsed) if parsed else {"usable": True, "reject_reason": None}
    if parsed and not q.get("usable"):
        return {"ok": False, "reason": "unusable_crop", "quality": q}

    emb = embedding
    jpeg = decode_data_url_jpeg(crop_jpeg_base64)
    if emb is None and not jpeg:
        return {
            "ok": False,
            "reason": "crop_decode_failed",
            "detail": "Could not read the boxed face JPEG. Box again on the paused picture.",
        }
    if emb is None and jpeg:
        try:
            emb = embed_jpeg_bytes(jpeg)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"embed_failed:{exc}", "detail": str(exc)}
    if not emb:
        return {
            "ok": False,
            "reason": "no_embedding",
            "detail": "buffalo_l found no face in that box. Drag a larger box around the whole head, then Learn again.",
        }

    row = persist_exemplar(
        person_id=person_id,
        source_type="owner_video",
        provider_key=vpk,
        method="owner_learn",
        authority=AUTHORITY_OWNER_CONFIRMED,
        confirmation_state=CONFIRM_OWNER,
        embedding=emb,
        embedding_model=MODEL_ID,
        external_face_id=face_external_id,
        source_asset_id=video_external_id,
        bbox=parsed or bbox,
        quality=q,
        meta={
            "provenance": "owner_review_learn",
            "t_sec": t_sec,
            "video_external_id": video_external_id,
        },
        confidence=1.0,
    )
    from memorybox.recognition.allowlist import set_face_scan

    set_face_scan(person_id, True)

    display_name = person_id
    try:
        from memorybox.person import get_person

        view = get_person(person_id)
        if view and view.display_name:
            display_name = view.display_name
    except Exception:
        pass

    current_scan = None
    if video_external_id:
        current_scan = scan_video_for_person(
            person_id=person_id,
            video_provider=video_provider,
            video_external_id=video_external_id,
            video_provider_key=vpk,
            run_kind="owner_learned",
            trigger="owner_learn",
        )

    enqueue = None
    from memorybox.recognition.inventory import inventory_video_rows

    if video_external_id:
        others = []
        for v in inventory_video_rows(video_provider):
            veid = str(v.get("video_external_id") or "")
            if not veid or veid == video_external_id:
                continue
            item = dict(v)
            item["priority"] = PRIORITY_OTHER_VIDEO
            others.append(item)
        if others:
            enqueue = enqueue_full_eligible_archive(
                person_id=person_id,
                videos=others,
                enqueue_reason="owner_learn",
                priority=PRIORITY_OTHER_VIDEO,
                run_kind="owner_learned",
            )

    return {
        "ok": True,
        "exemplar": row,
        "person": {"id": person_id, "display_name": display_name},
        "current_video_scan": current_scan,
        "enqueue_others": enqueue,
        "rescan_policy": "current_video_first_then_priority_enqueue",
    }
