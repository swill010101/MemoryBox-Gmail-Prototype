"""Incremental overnight pass: new/changed exemplars only — not a full restart."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from memorybox.db import connection
from memorybox.person import list_people, resolve_immich_external_ids_for_person
from memorybox.recognition.exemplars import list_active_exemplars
from memorybox.recognition.allowlist import face_scan_enabled
from memorybox.recognition.inventory import inventory_video_rows, list_owned_folder_video_rows
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
    # Walk the MB-owned tape folder on this pass (not Immich). New files in
    # subfolders become vid-* rows even if the video-worker index is stale.
    for r in list_owned_folder_video_rows():
        vid = str(r.get("video_external_id") or "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        rows.append(r)
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
    *, video_provider: Any, photo_provider: Any | None = None,
    seed_immich: bool = False, person_limit: int = 80, full: bool = False,
) -> dict[str, Any]:
    """Admitted plan only. Never discover scope from reachable archive files."""
    from memorybox.processing.scope import require_admission, ScopeDenied, preview, admit
    admission = require_admission("face", archive=full)
    if seed_immich:
        raise ScopeDenied("provider_seed_not_in_video_manifest")
    people = admission.plan["person_ids"]
    if len(people) > person_limit:
        raise ScopeDenied("person_limit_would_truncate_approved_workload")
    videos = admission.videos
    admit("face", videos, people)  # whole Cartesian request before first enqueue
    results = [enqueue_full_eligible_archive(person_id=pid, videos=videos,
        enqueue_reason="exemplar_change", priority=50, run_kind="provider_seeded") for pid in people]
    return {"ok":True,"admission_id":admission.id,"preview":preview(admission.plan),
            "video_count":len(videos),"people_queued":len(people),"results":results}
