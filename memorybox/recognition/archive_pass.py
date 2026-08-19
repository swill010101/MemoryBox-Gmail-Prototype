"""Enqueue known MB people × eligible Home Videos + Immich videos, one-by-one via the queue."""
from __future__ import annotations

from typing import Any

from memorybox.person import list_people
from memorybox.recognition.exemplars import list_active_exemplars
from memorybox.recognition.inventory import inventory_video_rows
from memorybox.recognition.queue import enqueue_full_eligible_archive


def list_immich_video_rows(*, photo_provider: Any, limit: int = 2000) -> list[dict[str, Any]]:
    client = getattr(photo_provider, "_client", None)
    search = getattr(client, "search_metadata", None)
    if not callable(search):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    page = 1
    while len(out) < int(limit) and page <= 40:
        try:
            data = search({"type": "VIDEO", "size": min(250, int(limit)), "page": page}) or {}
        except Exception:
            break
        assets = []
        if isinstance(data, dict):
            assets = list((data.get("assets") or {}).get("items") or data.get("items") or [])
            if not assets and isinstance(data.get("assets"), list):
                assets = list(data.get("assets") or [])
        if not assets:
            break
        for raw in assets:
            if not isinstance(raw, dict):
                continue
            aid = str(raw.get("id") or "").strip()
            if not aid or aid in seen:
                continue
            kind = str(raw.get("type") or "").upper()
            if kind and kind != "VIDEO":
                continue
            seen.add(aid)
            out.append(
                {
                    "video_provider_key": "immich",
                    "video_external_id": aid,
                    "eligible": True,
                }
            )
            if len(out) >= int(limit):
                return out
        page += 1
    return out


def combined_eligible_videos(*, video_provider: Any, photo_provider: Any | None = None) -> list[dict[str, Any]]:
    rows = list(inventory_video_rows(video_provider) or [])
    seen = {str(r.get("video_external_id") or "") for r in rows}
    if photo_provider is not None:
        for r in list_immich_video_rows(photo_provider=photo_provider):
            vid = str(r.get("video_external_id") or "")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            rows.append(r)
    return [r for r in rows if r.get("video_external_id")]


def enqueue_known_people_archive(
    *,
    video_provider: Any,
    photo_provider: Any | None = None,
    seed_immich: bool = False,
    person_limit: int = 80,
) -> dict[str, Any]:
    """Known MemoryBox people with exemplars → queue every eligible video."""
    videos = combined_eligible_videos(
        video_provider=video_provider, photo_provider=photo_provider
    )
    people_out: list[dict[str, Any]] = []
    seeded = 0
    skipped = 0
    queued_people = 0
    for row in list_people(limit=person_limit):
        pid = str(row.get("id") or "")
        name = str(row.get("display_name") or "").strip() or "(unnamed)"
        if not pid:
            continue
        exemplars = list_active_exemplars(pid)
        if not exemplars and seed_immich and photo_provider is not None:
            try:
                from memorybox.recognition.seed import seed_exemplars_from_immich

                seed_exemplars_from_immich(
                    person_id=pid, photo_provider=photo_provider, max_assets=80
                )
                seeded += 1
                exemplars = list_active_exemplars(pid)
            except Exception as exc:  # noqa: BLE001
                people_out.append({"person_id": pid, "name": name, "skipped": str(exc)[:160]})
                skipped += 1
                continue
        if not exemplars:
            skipped += 1
            people_out.append({"person_id": pid, "name": name, "skipped": "no_exemplars"})
            continue
        enq = enqueue_full_eligible_archive(
            person_id=pid,
            videos=videos,
            enqueue_reason="exemplar_change",
            priority=50,
            run_kind="provider_seeded",
        )
        queued_people += 1
        people_out.append(
            {
                "person_id": pid,
                "name": name,
                "exemplars": len(exemplars),
                "enqueue": enq,
            }
        )
    return {
        "ok": True,
        "video_count": len(videos),
        "people_queued": queued_people,
        "people_seeded": seeded,
        "people_skipped": skipped,
        "people": people_out[:40],
        "note": "Serve drains recognition_queue one video at a time when MEMORYBOX_P1_RUNTIME_HOST=1.",
    }
