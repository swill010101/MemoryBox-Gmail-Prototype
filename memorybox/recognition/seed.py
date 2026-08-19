"""Provider-seeded Immich faces → MemoryBox crops → MB embeddings → exemplars."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from memorybox.person import resolve_immich_external_ids_for_person
from memorybox.person.face_evidence import CONFIRM_SYSTEM
from memorybox.person import AUTHORITY_TRUSTED_PROVIDER
from memorybox.recognition.constants import MODEL_ID
from memorybox.recognition.crops import crop_jpeg_bytes, parse_bbox, quality_flags
from memorybox.recognition.embeddings import (
    embed_image_bytes_for_bbox,
    insightface_available,
)
from memorybox.recognition.exemplars import persist_exemplar, select_exemplars


def _capture_at(raw: dict[str, Any] | None) -> datetime | None:
    if not isinstance(raw, dict):
        return None
    for key in ("localDateTime", "fileCreatedAt", "fileModifiedAt", "takenAt", "createdAt"):
        v = raw.get(key)
        if isinstance(v, str) and v.strip():
            try:
                return datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
    exif = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
    for key in ("dateTimeOriginal", "localDateTime"):
        v = exif.get(key)
        if isinstance(v, str) and v.strip():
            try:
                return datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def list_person_immich_videos(
    *,
    person_id: str,
    photo_provider: Any,
    max_assets: int = 20,
) -> list[str]:
    """Immich VIDEO assets for a mapped Person (Ask/Explore video filter)."""
    client = getattr(photo_provider, "_client", None)
    search = getattr(client, "search_by_person_ids", None)
    if not callable(search):
        return []
    ext_ids = resolve_immich_external_ids_for_person(person_id, photo=photo_provider) or []
    out: list[str] = []
    seen: set[str] = set()
    for ext in ext_ids:
        try:
            rows = search([ext], size=max(50, int(max_assets) * 4)) or []
        except Exception:
            rows = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            aid = str(raw.get("id") or "").strip()
            if not aid or aid in seen:
                continue
            kind = str(raw.get("type") or "").upper()
            name = str(raw.get("originalFileName") or raw.get("originalPath") or "").lower()
            is_video = kind == "VIDEO" or name.endswith(
                (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
            )
            if not is_video:
                continue
            seen.add(aid)
            out.append(aid)
            if len(out) >= int(max_assets):
                return out
    return out


def collect_immich_face_candidates(
    *,
    person_id: str,
    photo_provider: Any,
    max_assets: int = 80,
) -> list[dict[str, Any]]:
    """Enumerate Person assets (timeline-first client) then GET /faces per asset.

    Does not treat GET /people/{id} feature faces as a complete catalog.
    """
    client = getattr(photo_provider, "_client", None)
    if client is None:
        return []
    list_asset_faces = getattr(client, "list_faces_for_asset", None)
    search = getattr(client, "search_by_person_ids", None)
    get_asset = getattr(client, "get_asset", None)
    if not callable(list_asset_faces) or not callable(search):
        return []
    ext_ids = resolve_immich_external_ids_for_person(person_id, photo=photo_provider) or []
    out: list[dict[str, Any]] = []
    seen_face: set[str] = set()
    for ext in ext_ids:
        try:
            assets = search([ext], size=max_assets) or []
        except Exception:
            assets = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            aid = str(asset.get("id") or "").strip()
            if not aid:
                continue
            try:
                faces = list_asset_faces(aid) or []
            except Exception:
                faces = []
            asset_detail = asset
            if callable(get_asset):
                try:
                    got = get_asset(aid)
                    if isinstance(got, dict):
                        asset_detail = got
                except Exception:
                    pass
            captured = _capture_at(asset_detail) or _capture_at(asset)
            for face in faces:
                if not isinstance(face, dict):
                    continue
                person_obj = face.get("person") if isinstance(face.get("person"), dict) else {}
                pid = str(
                    face.get("personId")
                    or person_obj.get("id")
                    or ""
                ).strip()
                if pid and pid != str(ext):
                    continue
                fid = str(face.get("id") or face.get("faceId") or "").strip()
                if not fid or fid in seen_face:
                    continue
                seen_face.add(fid)
                bbox_src = {
                    "boundingBoxX1": face.get("boundingBoxX1"),
                    "boundingBoxY1": face.get("boundingBoxY1"),
                    "boundingBoxX2": face.get("boundingBoxX2"),
                    "boundingBoxY2": face.get("boundingBoxY2"),
                    "x1": face.get("x1"),
                    "y1": face.get("y1"),
                    "x2": face.get("x2"),
                    "y2": face.get("y2"),
                }
                try:
                    bbox = parse_bbox(bbox_src)
                except (TypeError, ValueError):
                    bbox = None
                image_w = face.get("imageWidth") or face.get("image_width")
                image_h = face.get("imageHeight") or face.get("image_height")
                q = quality_flags(bbox, image_w=image_w, image_h=image_h) if bbox else {
                    "usable": False,
                    "reject_reason": "missing_bbox",
                }
                out.append(
                    {
                        "id": fid,
                        "external_face_id": fid,
                        "external_person_id": ext,
                        "source_asset_id": aid,
                        "bbox": bbox,
                        "image_w": image_w,
                        "image_h": image_h,
                        "capture_at": captured,
                        "usable": bool(q.get("usable")),
                        "quality": q,
                        "pose": _pose_bucket(bbox, image_w),
                    }
                )
    return out


def _pose_bucket(bbox: dict[str, float] | None, image_w: Any) -> str:
    if not bbox:
        return "unknown"
    # Cheap heuristic: wider crops tend to be more frontal in stills; not a research model.
    aspect = float(bbox.get("w") or 0) / max(float(bbox.get("h") or 1), 1.0)
    if aspect >= 0.85:
        return "frontal"
    if aspect >= 0.65:
        return "three_quarter"
    return "profile"


def seed_exemplars_from_candidates(
    *,
    person_id: str,
    candidates: list[dict[str, Any]],
    provider_key: str = "immich",
) -> dict[str, Any]:
    """Persist a capped diverse set. Candidates must already carry embeddings."""
    selected = select_exemplars(candidates)
    saved = []
    for c in selected:
        row = persist_exemplar(
            person_id=person_id,
            source_type="immich_face",
            provider_key=provider_key,
            method="immich_face_asset",
            authority=AUTHORITY_TRUSTED_PROVIDER,
            confirmation_state=CONFIRM_SYSTEM,
            embedding=list(c.get("embedding") or []),
            embedding_model=str(c.get("embedding_model") or MODEL_ID),
            external_face_id=c.get("external_face_id") or c.get("id"),
            external_person_id=c.get("external_person_id"),
            source_asset_id=c.get("source_asset_id"),
            bbox=c.get("bbox"),
            capture_at=c.get("capture_at") if isinstance(c.get("capture_at"), datetime) else None,
            quality=c.get("quality"),
            meta={
                "provenance": "immich_api_face",
                "source_type": "immich_face",
                "pose": c.get("pose"),
            },
            confidence=c.get("confidence"),
        )
        saved.append(row["id"])
    return {
        "ok": True,
        "person_id": person_id,
        "candidate_count": len(candidates),
        "usable_count": sum(1 for c in candidates if c.get("usable", True) and c.get("embedding")),
        "selected_count": len(saved),
        "exemplar_ids": saved,
    }


def seed_exemplars_from_immich(
    *,
    person_id: str,
    photo_provider: Any,
    fetch_bytes: Callable[[str], bytes] | None = None,
    embed_fn: Callable[[bytes], list[float] | None] | None = None,
    max_assets: int = 80,
) -> dict[str, Any]:
    raw = collect_immich_face_candidates(
        person_id=person_id,
        photo_provider=photo_provider,
        max_assets=max_assets,
    )
    client = getattr(photo_provider, "_client", None)
    fetch = fetch_bytes
    if fetch is None and client is not None:
        fb = getattr(client, "fetch_preview_bytes", None)

        def _fetch(aid: str) -> bytes:
            data, _ctype, _src = fb(aid)
            return data

        fetch = _fetch if callable(fb) else None
    embed = embed_fn
    enriched: list[dict[str, Any]] = []
    skipped = 0
    skip_reasons: dict[str, int] = {
        "unusable_or_no_bbox": 0,
        "fetch": 0,
        "crop": 0,
        "embed": 0,
    }
    embed_error: str | None = None
    fetch_error: str | None = None
    preview_by_asset: dict[str, bytes] = {}
    for c in raw:
        if not c.get("usable") or not c.get("bbox"):
            skipped += 1
            skip_reasons["unusable_or_no_bbox"] += 1
            continue
        aid = str(c.get("source_asset_id") or "")
        img = preview_by_asset.get(aid)
        if img is None and fetch and aid:
            try:
                img = fetch(aid)
            except Exception as exc:  # noqa: BLE001
                img = None
                if fetch_error is None:
                    fetch_error = str(exc)[:240]
            if img:
                preview_by_asset[aid] = img
        if not img:
            skipped += 1
            skip_reasons["fetch"] += 1
            continue
        emb = None
        try:
            if embed is not None:
                jpeg = crop_jpeg_bytes(
                    img,
                    c["bbox"],
                    image_w=c.get("image_w"),
                    image_h=c.get("image_h"),
                )
                if not jpeg:
                    skipped += 1
                    skip_reasons["crop"] += 1
                    continue
                emb = embed(jpeg)
            else:
                emb = embed_image_bytes_for_bbox(
                    img,
                    c["bbox"],
                    image_w=c.get("image_w"),
                    image_h=c.get("image_h"),
                )
        except Exception as exc:  # noqa: BLE001
            emb = None
            if embed_error is None:
                embed_error = str(exc)[:240]
        if not emb:
            skipped += 1
            skip_reasons["embed"] += 1
            continue
        c = dict(c)
        c["embedding"] = emb
        c["embedding_model"] = MODEL_ID
        enriched.append(c)
    result = seed_exemplars_from_candidates(
        person_id=person_id,
        candidates=enriched,
        provider_key=getattr(photo_provider, "provider_key", None) or "immich",
    )
    result["skipped"] = skipped
    result["skip_reasons"] = skip_reasons
    result["embed_error"] = embed_error
    result["fetch_error"] = fetch_error
    result["previews_fetched"] = len(preview_by_asset)
    result["insightface_available"] = insightface_available()
    result["collected"] = len(raw)
    return result
