"""P2-I1 Immich → MB Person sync (nightly + Sync now) and face-evidence ingest."""
from __future__ import annotations

import json
from typing import Any, Callable

from memorybox.db import connection
from memorybox.person import (
    AUTHORITY_TRUSTED_PROVIDER,
    AmbiguousIdentityError,
    find_person_by_provider_external_id,
    list_people_by_exact_name,
    seed_person_from_trusted_provider,
)
from memorybox.person.face_evidence import (
    CONFIRM_SYSTEM,
    upsert_face_evidence,
)
from memorybox.providers.photo.dto import PhotoPersonRef
from memorybox.recognition.queue import enqueue_full_eligible_archive, queue_summary


def _start_sync_run(*, provider_key: str, trigger: str) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO provider_person_sync_runs (provider_key, trigger, status)
            VALUES (%s, %s, 'running')
            RETURNING id::text
            """,
            (provider_key, trigger),
        ).fetchone()
    return str(row["id"])


def _finish_sync_run(
    run_id: str,
    *,
    status: str,
    detail: str | None = None,
    created: int = 0,
    mapped: int = 0,
    skipped: int = 0,
    conflicts: int = 0,
    meta: dict[str, Any] | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE provider_person_sync_runs
            SET finished_at = now(), status = %s, detail = %s,
                created_count = %s, mapped_count = %s, skipped_count = %s,
                conflict_count = %s, meta_json = %s::jsonb
            WHERE id = %s::uuid
            """,
            (
                status,
                detail,
                created,
                mapped,
                skipped,
                conflicts,
                json.dumps(meta or {}),
                run_id,
            ),
        )


def sync_immich_people(
    *,
    photo_provider: Any,
    list_eligible_videos: Callable[[], list[dict[str, Any]]],
    trigger: str = "sync_now",
    ingest_faces: bool = True,
    list_face_assets: Callable[[PhotoPersonRef], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Sync named Immich/photo people → canonical MB Persons; enqueue recognition."""
    provider_key = getattr(photo_provider, "provider_key", "immich")
    run_id = _start_sync_run(provider_key=provider_key, trigger=trigger)
    created = mapped = skipped = conflicts = 0
    newly_known: list[str] = []
    people_out: list[dict[str, Any]] = []
    try:
        people: list[PhotoPersonRef] = list(photo_provider.list_people(limit=5000) or [])
        for pref in people:
            name = (pref.display_name or "").strip()
            if not name:
                skipped += 1
                continue
            try:
                existing = find_person_by_provider_external_id(
                    provider_key=pref.provider_key,
                    external_id=pref.external_id,
                )
                if existing:
                    person = existing
                    mapped += 1
                    is_new = False
                else:
                    same = list_people_by_exact_name(name)
                    if same:
                        raise AmbiguousIdentityError(
                            f"Immich person {name!r} unmapped but MB Person(s) "
                            f"already use that display name — owner resolution required",
                            candidates=[
                                {"person_id": p.id, "display_name": p.display_name}
                                for p in same
                            ],
                        )
                    person = seed_person_from_trusted_provider(
                        provider_key=pref.provider_key,
                        external_id=pref.external_id,
                        display_name=name,
                    )
                    created += 1
                    is_new = True
                    newly_known.append(person.id)

                people_out.append(
                    {
                        "person_id": person.id,
                        "display_name": person.display_name,
                        "external_id": pref.external_id,
                        "newly_known": is_new,
                    }
                )
                if ingest_faces and list_face_assets is not None:
                    for face in list_face_assets(pref) or []:
                        upsert_face_evidence(
                            person_id=person.id,
                            provider_key=pref.provider_key,
                            method="immich_face_asset",
                            authority=AUTHORITY_TRUSTED_PROVIDER,
                            confirmation_state=CONFIRM_SYSTEM,
                            external_face_id=str(
                                face.get("external_face_id") or face.get("id") or ""
                            )
                            or None,
                            external_person_id=pref.external_id,
                            source_asset_id=str(face.get("source_asset_id") or "") or None,
                            bbox=face.get("bbox") if isinstance(face.get("bbox"), dict) else None,
                            confidence=face.get("confidence"),
                            exemplar_meta={"immich_person": pref.external_id},
                        )
            except AmbiguousIdentityError as exc:
                conflicts += 1
                people_out.append(
                    {
                        "display_name": name,
                        "external_id": pref.external_id,
                        "conflict": True,
                        "detail": str(exc),
                    }
                )
                continue

        videos = list_eligible_videos()
        enqueue_results = []
        for pid in newly_known:
            enqueue_results.append(
                enqueue_full_eligible_archive(
                    person_id=pid,
                    videos=videos,
                    enqueue_reason="newly_known_person",
                )
            )
        # First-time queue coverage for already-mapped people with empty queue
        for row in people_out:
            pid = row.get("person_id")
            if not pid or row.get("conflict"):
                continue
            summary = queue_summary(pid)
            if summary.get("total", 0) == 0:
                enqueue_results.append(
                    enqueue_full_eligible_archive(
                        person_id=pid,
                        videos=videos,
                        enqueue_reason="newly_known_person",
                    )
                )
                if pid not in newly_known:
                    newly_known.append(str(pid))

        _finish_sync_run(
            run_id,
            status="completed",
            created=created,
            mapped=mapped,
            skipped=skipped,
            conflicts=conflicts,
            meta={"newly_known": newly_known, "enqueue": enqueue_results},
        )
        return {
            "ok": True,
            "run_id": run_id,
            "provider_key": provider_key,
            "trigger": trigger,
            "created": created,
            "mapped": mapped,
            "skipped": skipped,
            "conflicts": conflicts,
            "newly_known_person_ids": newly_known,
            "people": people_out,
            "enqueue": enqueue_results,
        }
    except Exception as exc:  # noqa: BLE001
        _finish_sync_run(run_id, status="failed", detail=str(exc))
        return {"ok": False, "run_id": run_id, "error": str(exc)}


def latest_sync_run(provider_key: str = "immich") -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id::text, provider_key, trigger, started_at, finished_at, status,
                   detail, created_count, mapped_count, skipped_count, conflict_count,
                   meta_json
            FROM provider_person_sync_runs
            WHERE provider_key = %s
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (provider_key,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("started_at", "finished_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    if isinstance(d.get("meta_json"), str):
        d["meta_json"] = json.loads(d["meta_json"])
    return d
