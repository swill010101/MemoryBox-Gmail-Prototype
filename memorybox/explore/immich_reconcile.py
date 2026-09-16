"""Read-only Immich vs MemoryBox visual-count equation. No writes."""
from __future__ import annotations

from typing import Any

from memorybox.explore.gallery_scope import visual_count_equation


def _row_archived_or_trashed(row: dict[str, Any]) -> bool:
    if row.get("isArchived") or row.get("isTrashed") or row.get("isOffline"):
        return True
    status = str(row.get("status") or "").lower()
    return status in {"archived", "trashed", "deleted", "offline"}


def _row_is_video(row: dict[str, Any]) -> bool:
    kind = str(row.get("type") or "").upper()
    name = str(row.get("originalFileName") or row.get("originalPath") or "").lower()
    return kind == "VIDEO" or name.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"))


def reconcile_person_visuals(
    *,
    person_id: str,
    person_name: str = "",
    photo: Any | None = None,
) -> dict[str, Any]:
    from memorybox.ask.deps import build_photo
    from memorybox.ask.retrieve import search_photos
    from memorybox.person import get_person, resolve_immich_external_ids_for_person
    from memorybox.planner import QueryPlan

    photo = photo or build_photo()
    person = get_person(person_id)
    display = person_name or ((person.display_name if person else "") or person_id)
    client = getattr(photo, "_client", None)
    ext_ids = resolve_immich_external_ids_for_person(person_id, photo=photo) or []
    reported = 0
    if client is not None:
        count_fn = getattr(client, "_reported_person_asset_count", None)
        if callable(count_fn):
            reported = int(count_fn(ext_ids) or 0)
    rows: list[dict[str, Any]] = []
    search = getattr(client, "search_by_person_ids", None) if client is not None else None
    if callable(search) and ext_ids:
        for ext in ext_ids:
            rows.extend(search([ext], size=25000) or [])
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    dupes = 0
    archived = 0
    photos_n = 0
    videos_n = 0
    no_membership = 0
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        aid = str(raw.get("id") or "").strip()
        if not aid:
            continue
        if aid in seen:
            dupes += 1
            continue
        seen.add(aid)
        unique.append(raw)
        if _row_archived_or_trashed(raw):
            archived += 1
        if _row_is_video(raw):
            videos_n += 1
        else:
            photos_n += 1
    walk_n = len(unique)
    if reported and walk_n < reported:
        no_membership = max(0, reported - walk_n)
    plan = QueryPlan(
        original_ask=f"Show me {display}",
        effective_ask=f"Show me {display}",
        is_followup=False,
        want_photo=True,
        want_still=True,
        want_communication=False,
        want_calendar=False,
        person_names=(display,),
        person_ids=(person_id,),
    )
    hits, status = search_photos(plan, photo, limit=25000)
    mb_photos = sum(1 for h in hits if not getattr(h, "is_video", False))
    mb_videos = 0
    for h in hits:
        mime = str(getattr(h, "mime_type", None) or getattr(h, "media_type", None) or "")
        if "video" in mime.lower() or bool(getattr(h, "is_video", False)):
            mb_videos += 1
            mb_photos = max(0, mb_photos - 1)
    # PhotoHit types are stills; videos come from a separate retrieve.
    still_n = len(hits)
    truncated = bool((status or {}).get("photo_truncated"))
    pagination = 0
    if truncated:
        pagination = max(0, walk_n - still_n)
    elif reported:
        pagination = max(0, reported - walk_n - no_membership)
        pagination = 0
    mapping = max(0, reported - walk_n) if reported else 0
    # Mapping vs pagination: if walk is short of Immich reported, that gap is
    # membership/mapping (or a remaining fetch cap), not MB-native evidence.
    pagination_or_window = max(0, int((status or {}).get("eligible_n") or still_n) - still_n)
    if truncated:
        pagination_or_window = max(
            pagination_or_window,
            int((status or {}).get("eligible_n") or 0) - still_n,
        )
    eq = visual_count_equation(
        immich_assets=reported or walk_n,
        immich_photos=photos_n,
        immich_videos=videos_n,
        mb_photos=still_n,
        mb_videos=mb_videos,
        duplicates_suppressed=dupes,
        archived_trashed_deleted_unavailable=archived,
        unsupported=0,
        person_mapping_diff=mapping,
        face_confidence_exclusions=0,
        date_filter_exclusions=int((status or {}).get("before_temporal_filter") or 0)
        - int((status or {}).get("after_temporal_filter") or 0)
        if (status or {}).get("before_temporal_filter") is not None
        else 0,
        mb_native_non_immich=0,
        pagination_or_window=pagination_or_window,
    )
    # If Immich reported > walk, mapping already subtracted those. Don't double-count.
    return {
        "ok": bool(eq["ok"]),
        "person_id": person_id,
        "person_name": display,
        "immich_external_ids": list(ext_ids),
        "walk_unique": walk_n,
        "photo_search_n": still_n,
        "photo_status": {
            "photo_truncated": truncated,
            "eligible_n": (status or {}).get("eligible_n"),
            "processed_n": (status or {}).get("processed_n"),
            "person_library_unwindowed_n": (status or {}).get("person_library_unwindowed_n"),
            "immich_person_asset_count": (status or {}).get("immich_person_asset_count"),
        },
        "equation": eq,
    }
