"""Incremental overnight pass: new/changed exemplars only — not a full restart."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from memorybox.db import connection
from memorybox.person import list_people, resolve_immich_external_ids_for_person
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


def _sha(parts: list[str]) -> str:
    raw = "|".join(parts) or "empty"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def catalog_fingerprint(candidates: list[dict[str, Any]]) -> str:
    """Stable Immich face-id catalog (no embeddings). Changes when a name gets new stills or a merge."""
    bits = sorted(
        f"{c.get('external_face_id') or c.get('id') or ''}:"
        f"{c.get('source_asset_id') or ''}:"
        f"{c.get('external_person_id') or ''}"
        for c in (candidates or [])
    )
    return _sha(bits)


def exemplar_fingerprint(exemplars: list[dict[str, Any]], immich_ids: list[str]) -> str:
    bits = sorted(
        f"{e.get('external_face_id') or e.get('id') or ''}:"
        f"{e.get('source_asset_id') or ''}"
        for e in (exemplars or [])
    )
    bits.extend(sorted(str(x) for x in (immich_ids or []) if x))
    return _sha(bits)


def _ensure_watermark_table() -> None:
    try:
        from memorybox.migrate import migrate

        migrate()
    except Exception:
        pass


def _load_watermark(person_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT person_id::text, exemplar_fingerprint, last_video_count,
                   last_pass_at, last_reason, meta_json
            FROM recognition_person_watermark
            WHERE person_id = %s::uuid
            """,
            (person_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    meta = d.get("meta_json")
    if isinstance(meta, str):
        try:
            d["meta_json"] = json.loads(meta)
        except json.JSONDecodeError:
            d["meta_json"] = {}
    if not isinstance(d.get("meta_json"), dict):
        d["meta_json"] = {}
    return d


def _save_watermark(
    person_id: str,
    fingerprint: str,
    video_count: int,
    reason: str,
    *,
    meta: dict[str, Any] | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO recognition_person_watermark (
                person_id, exemplar_fingerprint, last_video_count, last_reason,
                last_pass_at, meta_json
            ) VALUES (%s::uuid, %s, %s, %s, now(), %s::jsonb)
            ON CONFLICT (person_id) DO UPDATE SET
                exemplar_fingerprint = EXCLUDED.exemplar_fingerprint,
                last_video_count = EXCLUDED.last_video_count,
                last_reason = EXCLUDED.last_reason,
                last_pass_at = now(),
                meta_json = EXCLUDED.meta_json
            """,
            (person_id, fingerprint, int(video_count), reason, json.dumps(meta or {})),
        )


def _video_ids_already_queued(person_id: str) -> set[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT video_external_id
            FROM recognition_queue_items
            WHERE person_id = %s::uuid
              AND status IN ('queued', 'running', 'completed')
            """,
            (person_id,),
        ).fetchall()
    return {str(r["video_external_id"]) for r in rows}


def enqueue_known_people_archive(
    *,
    video_provider: Any,
    photo_provider: Any | None = None,
    seed_immich: bool = False,
    person_limit: int = 80,
    full: bool = False,
) -> dict[str, Any]:
    """Overnight incremental pass.

    Does **not** restart recognition for everyone. With seed_immich:
    - new Immich-named person with usable still faces → seed exemplars → scan all videos
    - Immich merge / more faces on a mapped Person → catalog/fingerprint changes → rescan that Person only
    Unchanged people: skip embedding and skip video queue, except **new** files not yet queued.
    Pass full=True to ignore watermarks and rescan everyone.
    """
    _ensure_watermark_table()
    if seed_immich and photo_provider is not None:
        try:
            from memorybox.person.immich_sync import sync_immich_people

            def _faces(pref: Any) -> list[dict[str, Any]]:
                client = getattr(photo_provider, "_client", None)
                lister = getattr(client, "list_face_assets", None)
                if not callable(lister):
                    return []
                try:
                    assets = lister(person_external_id=pref.external_id, limit=50) or []
                except Exception:
                    return []
                out = []
                for a in assets:
                    out.append(
                        {
                            "id": getattr(a, "external_face_id", None),
                            "external_face_id": getattr(a, "external_face_id", None),
                            "source_asset_id": getattr(a, "source_asset_id", None),
                            "bbox": getattr(a, "bbox", None),
                            "confidence": getattr(a, "confidence", None),
                        }
                    )
                return out

            sync_immich_people(
                photo_provider=photo_provider,
                list_eligible_videos=lambda: combined_eligible_videos(
                    video_provider=video_provider, photo_provider=photo_provider
                ),
                trigger="nightly",
                ingest_faces=True,
                list_face_assets=_faces if hasattr(photo_provider, "_client") else None,
            )
        except Exception:
            pass

    videos = combined_eligible_videos(
        video_provider=video_provider, photo_provider=photo_provider
    )
    people_out: list[dict[str, Any]] = []
    seeded = 0
    seed_skipped = 0
    skipped = 0
    queued_people = 0
    unchanged = 0
    for row in list_people(limit=person_limit):
        pid = str(row.get("id") or "")
        name = str(row.get("display_name") or "").strip() or "(unnamed)"
        if not pid:
            continue
        immich_ids: list[str] = []
        try:
            immich_ids = list(
                resolve_immich_external_ids_for_person(pid, photo=photo_provider) or []
            )
        except Exception:
            immich_ids = []
        try:
            wm = None if full else _load_watermark(pid)
        except Exception:
            wm = None
        wm_meta = (wm or {}).get("meta_json") if isinstance((wm or {}).get("meta_json"), dict) else {}
        catalog_fp = str(wm_meta.get("immich_catalog") or "")
        exemplars = list_active_exemplars(pid)
        if seed_immich and photo_provider is not None and immich_ids:
            try:
                from memorybox.recognition.seed import (
                    collect_immich_face_candidates,
                    seed_exemplars_from_immich,
                )

                faces = collect_immich_face_candidates(
                    person_id=pid, photo_provider=photo_provider, max_assets=80
                )
                catalog_fp = catalog_fingerprint(faces)
                saved_catalog = str(wm_meta.get("immich_catalog") or "")
                # New named person (no exemplars) always seeds. Later nights seed only
                # when the Immich still-face catalog changed (new still or merge).
                catalog_changed = bool(full) or (not exemplars) or (
                    bool(wm) and catalog_fp != saved_catalog
                )
                if catalog_changed:
                    seed_exemplars_from_immich(
                        person_id=pid,
                        photo_provider=photo_provider,
                        max_assets=80,
                        candidates=faces,
                    )
                    seeded += 1
                    exemplars = list_active_exemplars(pid)
                else:
                    seed_skipped += 1
            except Exception as exc:  # noqa: BLE001
                people_out.append({"person_id": pid, "name": name, "skipped": str(exc)[:160]})
                skipped += 1
                continue
        if not exemplars:
            skipped += 1
            people_out.append({"person_id": pid, "name": name, "skipped": "no_exemplars"})
            continue
        fp = exemplar_fingerprint(exemplars, immich_ids)
        already = _video_ids_already_queued(pid)
        meta = {"immich_catalog": catalog_fp, "immich_ids": immich_ids}
        saved_fp = str((wm or {}).get("exemplar_fingerprint") or "")
        missing = [v for v in videos if str(v.get("video_external_id") or "") not in already]
        fp_changed = bool(full) or (bool(wm) and saved_fp != fp)
        if fp_changed:
            reason = "exemplar_change"
            to_run = videos
            action = "all_videos_exemplars_changed"
        elif not wm and not already:
            reason = "exemplar_change"
            to_run = videos
            action = "all_videos_first_seen"
        elif not wm and missing:
            reason = "new_video"
            to_run = missing
            action = "new_videos_only"
        else:
            to_run = [
                v
                for v in videos
                if str(v.get("video_external_id") or "") not in already
            ]
            if not to_run:
                unchanged += 1
                people_out.append(
                    {
                        "person_id": pid,
                        "name": name,
                        "exemplars": len(exemplars),
                        "skipped": "unchanged",
                    }
                )
                _save_watermark(pid, fp, len(videos), "unchanged", meta=meta)
                continue
            reason = "new_video"
            action = "new_videos_only"
        enq = enqueue_full_eligible_archive(
            person_id=pid,
            videos=to_run,
            enqueue_reason=reason,
            priority=50,
            run_kind="provider_seeded",
        )
        queued_people += 1
        _save_watermark(pid, fp, len(videos), reason, meta=meta)
        people_out.append(
            {
                "person_id": pid,
                "name": name,
                "exemplars": len(exemplars),
                "action": action,
                "videos": len(to_run),
                "enqueue": enq,
            }
        )
    return {
        "ok": True,
        "incremental": not full,
        "video_count": len(videos),
        "people_queued": queued_people,
        "people_unchanged": unchanged,
        "people_seeded": seeded,
        "people_seed_skipped_unchanged_catalog": seed_skipped,
        "people_skipped": skipped,
        "people": people_out[:40],
        "note": (
            "Incremental overnight: does not restart everyone. New Immich names "
            "or more exemplars (new still, merge) rescan that Person across all "
            "videos. Unchanged People are skipped except brand-new video files. "
            "Use --full / full=true for a complete rescan. Serve drains one video "
            "at a time when MEMORYBOX_P1_RUNTIME_HOST=1."
        ),
    }
