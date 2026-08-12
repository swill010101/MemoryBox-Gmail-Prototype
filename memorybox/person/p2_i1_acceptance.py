"""P2-I1 acceptance — Show me Peggy (Person-in-Media Vertical).

Desktop harness (no --flightsim): synthetic FakePhoto/FakeVideo corpus.
FlightSim (--flightsim): real Immich + real HVRT only. Fakes/degraded fail.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from memorybox.ask.deps import build_photo, build_video
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.person import (
    find_ask_person_by_name,
    list_people_by_exact_name,
    list_provider_external_ids_for_person,
    map_provider_identity,
)
from memorybox.person.face_evidence import list_face_evidence
from memorybox.person.immich_sync import latest_sync_run, sync_immich_people
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.dto import PhotoAssetDto, PhotoPersonRef
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.video.fake import PEGGY_FACE_ID, FakeVideoProvider
from memorybox.recognition.process import (
    list_appearance_moments,
    owner_correct_appearance,
    process_queue,
)
from memorybox.recognition.queue import list_queue_items, queue_summary


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _eligible_video_rows(video: Any) -> list[dict[str, Any]]:
    """Same inventory shape used by POST /people/sync/immich."""
    if hasattr(video, "eligible_video_rows"):
        return list(video.eligible_video_rows())
    rows: list[dict[str, Any]] = []
    vpk = getattr(video, "provider_key", "hvrt")
    for v in video.list_videos(limit=5000):
        rows.append(
            {
                "video_provider_key": vpk,
                "video_external_id": v.external_id,
                "eligible": True,
            }
        )
    return rows


def _list_face_assets_fn(photo: Any) -> Callable[[Any], list[dict[str, Any]]]:
    def list_faces(pref: Any) -> list[dict[str, Any]]:
        if not hasattr(photo, "list_face_assets"):
            return []
        try:
            assets = photo.list_face_assets(
                person_external_id=getattr(pref, "external_id", None) or pref.get("external_id"),
                limit=50,
            )
        except Exception:  # noqa: BLE001
            return []
        out: list[dict[str, Any]] = []
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

    return list_faces


def _ask_citations(ask: Any) -> tuple[list[Any], list[Any]]:
    cites = ask.citations or []
    photo_cites = [
        c
        for c in cites
        if getattr(c, "kind", None) == "photo" or (isinstance(c, dict) and c.get("kind") == "photo")
    ]
    video_cites = [
        c
        for c in cites
        if getattr(c, "kind", None) == "video" or (isinstance(c, dict) and c.get("kind") == "video")
    ]
    ad = ask.to_dict() if hasattr(ask, "to_dict") else {}
    if not video_cites and isinstance(ad.get("citations"), list):
        video_cites = [c for c in ad["citations"] if c.get("kind") == "video"]
        photo_cites = [c for c in ad["citations"] if c.get("kind") == "photo"]
    return photo_cites, video_cites


def _play_urls(video_cites: list[Any], moments: list[dict[str, Any]]) -> list[str]:
    play_urls: list[str] = []
    for c in video_cites:
        if isinstance(c, dict):
            play_urls.append(c.get("play_url") or "")
        else:
            play_urls.append(getattr(c, "play_url", "") or "")
    for m in moments:
        play_urls.append(m.get("play_url") or "")
    return play_urls


def prove_p2_i1(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_p2_i1_flightsim()
    return _prove_p2_i1_harness()


def _prove_p2_i1_harness() -> dict[str, Any]:
    """Desktop synthetic corpus — FakePhoto + FakeVideo (not ACCEPTED)."""
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I1", "flightsim": False, "mode": "harness"}

    tag = "".join(c for c in uuid4().hex if c.isalpha())[:8]
    harness_name = f"PeggyQa{tag}"
    peggy_ext = str(uuid4())
    photo = FakePhotoProvider(
        extra_people=[
            PhotoPersonRef(
                provider_key="fake_photo",
                external_id=peggy_ext,
                display_name=harness_name,
            )
        ],
        extra_assets=[
            PhotoAssetDto(
                provider_key="fake_photo",
                external_id=str(uuid4()),
                original_filename="peggy_smile.jpg",
                taken_at=datetime(2018, 6, 1, tzinfo=timezone.utc),
                people=(
                    PhotoPersonRef(
                        provider_key="fake_photo",
                        external_id=peggy_ext,
                        display_name=harness_name,
                    ),
                ),
            )
        ],
    )
    video = FakeVideoProvider(peggy_corpus=True)

    def list_faces(pref: PhotoPersonRef) -> list[dict[str, Any]]:
        return [
            {
                "id": f"immich-face-{pref.external_id[:8]}",
                "external_face_id": f"immich-face-{pref.external_id[:8]}",
                "source_asset_id": "asset-peggy-1",
                "confidence": 0.93,
                "bbox": {"x1": 10, "y1": 10, "x2": 40, "y2": 40},
            }
        ]

    sync = sync_immich_people(
        photo_provider=photo,
        list_eligible_videos=video.eligible_video_rows,
        trigger="harness",
        ingest_faces=True,
        list_face_assets=list_faces,
    )
    _check("p2i1_sync_ok", bool(sync.get("ok")), checks, problems, detail=str(sync)[:200])
    _check(
        "p2i1_no_redundant_enrollment",
        sync.get("created", 0) >= 1 and bool(sync.get("newly_known_person_ids")),
        checks,
        problems,
        detail=f"created={sync.get('created')} newly={sync.get('newly_known_person_ids')}",
    )

    person_id = (sync.get("newly_known_person_ids") or [None])[0]
    _check("p2i1_person_id", bool(person_id), checks, problems)

    if person_id:
        map_provider_identity(
            person_id=person_id,
            provider_key="fake_video",
            external_id=PEGGY_FACE_ID,
            label=harness_name,
            identity_kind="face",
            confirm_person=False,
            identity_authority="trusted_provider",
            assertion_authority="system",
        )

    faces = list_face_evidence(person_id) if person_id else []
    _check(
        "p2i1_immich_face_evidence",
        any(f.get("method") == "immich_face_asset" for f in faces),
        checks,
        problems,
        detail=f"faces={len(faces)}",
    )

    summary = queue_summary(person_id) if person_id else {"total": 0}
    items = list_queue_items(person_id=person_id, limit=50) if person_id else []
    excluded = [i for i in items if i.get("status") == "excluded"]
    _check(
        "p2i1_full_library_queue",
        summary.get("total", 0) >= 6,
        checks,
        problems,
        detail=f"summary={summary}",
    )
    _check(
        "p2i1_excluded_visible",
        any(i.get("reason") == "unsupported_codec" for i in excluded),
        checks,
        problems,
        detail=f"excluded={excluded}",
    )

    processed = process_queue(video_provider=video, person_id=person_id, max_items=20)
    _check(
        "p2i1_queue_processed",
        processed.get("processed", 0) >= 1,
        checks,
        problems,
        detail=str(processed.get("processed")),
    )

    moments = list_appearance_moments(person_id) if person_id else []
    clear_hits = [m for m in moments if m["video_external_id"] == "video-peggy-clear"]
    absent_hits = [m for m in moments if m["video_external_id"] == "video-peggy-absent"]
    _check(
        "p2i1_positive_appearance",
        len(clear_hits) >= 1,
        checks,
        problems,
        detail=f"clear={len(clear_hits)} moments={len(moments)}",
    )
    _check(
        "p2i1_negative_no_false_moment",
        len(absent_hits) == 0,
        checks,
        problems,
        detail=f"absent_hits={absent_hits}",
    )

    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=photo,
        llm=FakeLlmProvider(),
        video=video,
    )
    ask = orch.ask(f"Show me {harness_name}")
    photo_cites, video_cites = _ask_citations(ask)
    _check(
        "p2i1_ask_photos_and_moments",
        len(photo_cites) >= 1 and (len(video_cites) >= 1 or len(moments) >= 1),
        checks,
        problems,
        detail=f"photos={len(photo_cites)} videos={len(video_cites)} moments={len(moments)}",
    )

    play_urls = _play_urls(video_cites, moments)
    _check(
        "p2i1_jump_to_timeslot",
        any("t=" in (u or "") for u in play_urls),
        checks,
        problems,
        detail=str(play_urls[:3]),
    )

    if person_id:
        corr = owner_correct_appearance(
            person_id=person_id,
            video_provider_key="fake_video",
            video_external_id="video-peggy-clear",
            start_sec=5.0,
            end_sec=8.0,
            face_external_id=PEGGY_FACE_ID,
        )
        fe = corr.get("face_evidence") or {}
        _check(
            "p2i1_owner_correct_higher_authority",
            fe.get("authority") == "owner_confirmed",
            checks,
            problems,
            detail=str(fe.get("authority")),
        )
        moments2 = list_appearance_moments(person_id)
        _check(
            "p2i1_correction_reuse",
            any(m.get("authority") == "owner_confirmed" for m in moments2),
            checks,
            problems,
            detail=f"moments_after={len(moments2)}",
        )

    run = latest_sync_run(provider_key="fake_photo")
    _check(
        "p2i1_sync_run_observable",
        bool(run and run.get("status") == "completed"),
        checks,
        problems,
        detail=str(run),
    )

    sync2 = sync_immich_people(
        photo_provider=photo,
        list_eligible_videos=video.eligible_video_rows,
        trigger="sync_now",
        ingest_faces=True,
        list_face_assets=list_faces,
    )
    _check(
        "p2i1_sync_now_idempotent",
        bool(sync2.get("ok")) and sync2.get("created", 0) == 0 and sync2.get("mapped", 0) >= 1,
        checks,
        problems,
        detail=f"created={sync2.get('created')} mapped={sync2.get('mapped')}",
    )

    ok = not problems
    meta["person_id"] = person_id
    meta["queue"] = summary
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}


def _prove_p2_i1_flightsim() -> dict[str, Any]:
    """Owner ACCEPTED gate — real Immich + real HVRT timeslots required."""
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I1", "flightsim": True, "mode": "flightsim"}

    if _env("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-p2-i1 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    person_name = _env("MEMORYBOX_P2_I1_PERSON_NAME", "Peggy")
    person_id_env = _env("MEMORYBOX_P2_I1_PERSON_ID")
    positive_video = _env("MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID")
    negative_video = _env("MEMORYBOX_P2_I1_NEGATIVE_VIDEO_ID")
    hvrt_face_id = _env("MEMORYBOX_P2_I1_HVRT_FACE_ID")
    min_queue_raw = _env("MEMORYBOX_P2_I1_MIN_QUEUE", "2")
    try:
        min_queue = max(2, int(min_queue_raw))
    except ValueError:
        min_queue = 2

    photo = build_photo()
    video = build_video()
    ph = photo.health()
    vh = video.health()
    meta["providers"] = {
        "photo": {"provider_key": ph.provider_key, "ok": ph.ok, "detail": ph.detail},
        "video": {"provider_key": vh.provider_key, "ok": vh.ok, "detail": vh.detail},
    }

    _check(
        "p2i1_flightsim_immich_required",
        bool(ph.ok) and ph.provider_key == "immich",
        checks,
        problems,
        detail=(
            f"provider_key={ph.provider_key!r} ok={ph.ok} detail={ph.detail!r}; "
            "set MEMORYBOX_PHOTO_PROVIDER=immich + IMMICH_BASE_URL/API_KEY "
            "(fake/unavailable/degraded fail)"
        ),
    )
    _check(
        "p2i1_flightsim_hvrt_required",
        bool(vh.ok) and vh.provider_key == "hvrt",
        checks,
        problems,
        detail=(
            f"provider_key={vh.provider_key!r} ok={vh.ok} detail={vh.detail!r}; "
            "set MEMORYBOX_VIDEO_PROVIDER=hvrt + MEMORYBOX_VIDEO_WORKER_URL "
            "with HVRT worker healthy (fake/unavailable/degraded fail)"
        ),
    )
    _check(
        "p2i1_flightsim_corpus_env",
        bool(positive_video) and bool(negative_video),
        checks,
        problems,
        detail=(
            "set MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID and MEMORYBOX_P2_I1_NEGATIVE_VIDEO_ID "
            f"(got positive={positive_video!r} negative={negative_video!r})"
        ),
    )

    # Hard stop: do not continue with fakes or incomplete corpus.
    if problems:
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    inventory = _eligible_video_rows(video)
    list_faces = _list_face_assets_fn(photo)
    sync = sync_immich_people(
        photo_provider=photo,
        list_eligible_videos=lambda: inventory,
        trigger="sync_now",
        ingest_faces=True,
        list_face_assets=list_faces,
    )
    _check("p2i1_sync_ok", bool(sync.get("ok")), checks, problems, detail=str(sync)[:300])

    person_id = person_id_env or None
    if not person_id:
        newly = sync.get("newly_known_person_ids") or []
        if newly:
            person_id = newly[0]
        else:
            found = None
            try:
                found = find_ask_person_by_name(person_name, photo=photo)
            except Exception as exc:  # noqa: BLE001 — ambiguity / seed errors are check failures
                meta["person_resolve_error"] = str(exc)
            if found is None:
                same = list_people_by_exact_name(person_name)
                found = same[0] if same else None
            if found is not None:
                person_id = str(getattr(found, "id", "") or "")

    _check(
        "p2i1_person_id",
        bool(person_id),
        checks,
        problems,
        detail=(
            f"name={person_name!r}; after Immich sync set MEMORYBOX_P2_I1_PERSON_ID "
            "or ensure Immich person display name matches MEMORYBOX_P2_I1_PERSON_NAME"
        ),
    )
    _check(
        "p2i1_no_redundant_enrollment",
        bool(person_id)
        and (
            bool(sync.get("newly_known_person_ids"))
            or int(sync.get("mapped") or 0) >= 1
            or int(sync.get("created") or 0) >= 1
        ),
        checks,
        problems,
        detail=f"created={sync.get('created')} mapped={sync.get('mapped')} newly={sync.get('newly_known_person_ids')}",
    )

    # Map HVRT face → Person (owner teach / env). Required for real timeslot search.
    face_ids: list[str] = []
    if person_id:
        face_ids = list_provider_external_ids_for_person(person_id, "hvrt")
        if hvrt_face_id and hvrt_face_id not in face_ids:
            map_provider_identity(
                person_id=person_id,
                provider_key="hvrt",
                external_id=hvrt_face_id,
                label=person_name,
                identity_kind="face",
                confirm_person=True,
                identity_authority="owner_confirmed",
                assertion_authority="owner",
            )
            face_ids = list_provider_external_ids_for_person(person_id, "hvrt")
    _check(
        "p2i1_hvrt_face_mapped",
        bool(face_ids),
        checks,
        problems,
        detail=(
            "map HVRT face → Person via Review teach, or set MEMORYBOX_P2_I1_HVRT_FACE_ID; "
            f"mapped={face_ids}"
        ),
    )

    faces = list_face_evidence(person_id) if person_id else []
    _check(
        "p2i1_immich_face_evidence",
        any(f.get("method") == "immich_face_asset" for f in faces),
        checks,
        problems,
        detail=f"faces={len(faces)} methods={[f.get('method') for f in faces[:5]]}",
    )

    summary = queue_summary(person_id) if person_id else {"total": 0}
    items = list_queue_items(person_id=person_id, limit=500) if person_id else []
    inv_ids = {r["video_external_id"] for r in inventory}
    queued_ids = {i["video_external_id"] for i in items}
    _check(
        "p2i1_full_library_queue",
        summary.get("total", 0) >= min(min_queue, max(len(inventory), 1))
        and (not inv_ids or inv_ids.issubset(queued_ids) or summary.get("total", 0) >= len(inventory)),
        checks,
        problems,
        detail=f"summary={summary} inventory={len(inventory)} min_queue={min_queue}",
    )

    excluded_or_failed = [
        i for i in items if i.get("status") in {"excluded", "failed"}
    ]
    _check(
        "p2i1_excluded_visible",
        (
            # Prefer at least one excluded/failed-with-reason when inventory has gaps,
            # otherwise require every excluded/failed row to carry a reason (no silent omit).
            all(bool((i.get("reason") or "").strip()) for i in excluded_or_failed)
            if excluded_or_failed
            else True
        )
        and (
            # Corpus videos must appear in the durable work set
            (not positive_video or positive_video in queued_ids)
            and (not negative_video or negative_video in queued_ids)
        ),
        checks,
        problems,
        detail=f"excluded_or_failed={excluded_or_failed[:5]} queued_has_pos={positive_video in queued_ids} queued_has_neg={negative_video in queued_ids}",
    )

    if problems:
        meta["person_id"] = person_id
        meta["queue"] = summary
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    processed = process_queue(
        video_provider=video,
        person_id=person_id,
        max_items=max(len(inventory), min_queue, 20),
    )
    _check(
        "p2i1_queue_processed",
        processed.get("processed", 0) >= 1,
        checks,
        problems,
        detail=str(processed.get("processed")),
    )

    moments = list_appearance_moments(person_id) if person_id else []
    # Real HVRT timeslots required — empty moments after process = fail (degraded-only).
    _check(
        "p2i1_hvrt_real_timeslots",
        any(
            float(m.get("start_sec") or 0) >= 0
            and float(m.get("end_sec") or 0) > float(m.get("start_sec") or 0)
            and (m.get("play_url") or "")
            for m in moments
        ),
        checks,
        problems,
        detail=f"moments={len(moments)} sample={moments[:2]}",
    )

    clear_hits = [m for m in moments if m["video_external_id"] == positive_video]
    absent_hits = [m for m in moments if m["video_external_id"] == negative_video]
    _check(
        "p2i1_positive_appearance",
        len(clear_hits) >= 1,
        checks,
        problems,
        detail=f"positive_video={positive_video!r} hits={len(clear_hits)} moments={len(moments)}",
    )
    _check(
        "p2i1_negative_no_false_moment",
        len(absent_hits) == 0,
        checks,
        problems,
        detail=f"negative_video={negative_video!r} absent_hits={absent_hits}",
    )

    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=photo,
        llm=FakeLlmProvider(),
        video=video,
    )
    ask = orch.ask(f"Show me {person_name}")
    photo_cites, video_cites = _ask_citations(ask)
    _check(
        "p2i1_ask_photos_and_moments",
        len(photo_cites) >= 1 and (len(video_cites) >= 1 or len(moments) >= 1),
        checks,
        problems,
        detail=f"photos={len(photo_cites)} videos={len(video_cites)} moments={len(moments)}",
    )

    play_urls = _play_urls(video_cites, moments)
    _check(
        "p2i1_jump_to_timeslot",
        any("t=" in (u or "") for u in play_urls),
        checks,
        problems,
        detail=str(play_urls[:5]),
    )

    if person_id and clear_hits:
        sample = clear_hits[0]
        corr = owner_correct_appearance(
            person_id=person_id,
            video_provider_key=sample.get("video_provider_key") or "hvrt",
            video_external_id=positive_video,
            start_sec=float(sample.get("start_sec") or 0),
            end_sec=float(sample.get("end_sec") or (float(sample.get("start_sec") or 0) + 3)),
            face_external_id=sample.get("face_external_id") or (face_ids[0] if face_ids else None),
        )
        fe = corr.get("face_evidence") or {}
        _check(
            "p2i1_owner_correct_higher_authority",
            fe.get("authority") == "owner_confirmed",
            checks,
            problems,
            detail=str(fe.get("authority")),
        )
        moments2 = list_appearance_moments(person_id)
        _check(
            "p2i1_correction_reuse",
            any(m.get("authority") == "owner_confirmed" for m in moments2),
            checks,
            problems,
            detail=f"moments_after={len(moments2)}",
        )
    else:
        _check(
            "p2i1_owner_correct_higher_authority",
            False,
            checks,
            problems,
            detail="no positive appearance moment to correct",
        )
        _check(
            "p2i1_correction_reuse",
            False,
            checks,
            problems,
            detail="skipped — no positive appearance",
        )

    run = latest_sync_run(provider_key="immich") or latest_sync_run(provider_key=ph.provider_key)
    _check(
        "p2i1_sync_run_observable",
        bool(run and run.get("status") == "completed"),
        checks,
        problems,
        detail=str(run)[:400] if run else "None",
    )

    sync2 = sync_immich_people(
        photo_provider=photo,
        list_eligible_videos=lambda: inventory,
        trigger="sync_now",
        ingest_faces=True,
        list_face_assets=list_faces,
    )
    _check(
        "p2i1_sync_now_idempotent",
        bool(sync2.get("ok")) and int(sync2.get("created") or 0) == 0 and int(sync2.get("mapped") or 0) >= 1,
        checks,
        problems,
        detail=f"created={sync2.get('created')} mapped={sync2.get('mapped')}",
    )

    ok = not problems
    meta["person_id"] = person_id
    meta["person_name"] = person_name
    meta["queue"] = summary
    meta["inventory_count"] = len(inventory)
    meta["moments"] = len(moments)
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
