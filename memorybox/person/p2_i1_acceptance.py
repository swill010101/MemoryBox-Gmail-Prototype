"""P2-I1 acceptance — Show me Peggy (Person-in-Media Vertical)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.person import map_provider_identity
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


def prove_p2_i1(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I1", "flightsim": flightsim}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-p2-i1 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    peggy_ext = str(uuid4())
    photo = FakePhotoProvider(
        extra_people=[
            PhotoPersonRef(
                provider_key="fake_photo",
                external_id=peggy_ext,
                display_name="Peggy",
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
                        display_name="Peggy",
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

    # Map video face for recognition (owner-side mapping of HVRT/fake face id)
    if person_id:
        map_provider_identity(
            person_id=person_id,
            provider_key="fake_video",
            external_id=PEGGY_FACE_ID,
            label="Peggy",
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
    ask = orch.ask("Show me Peggy")
    cites = ask.citations or []
    photo_cites = [c for c in cites if getattr(c, "kind", None) == "photo" or (isinstance(c, dict) and c.get("kind") == "photo")]
    video_cites = [c for c in cites if getattr(c, "kind", None) == "video" or (isinstance(c, dict) and c.get("kind") == "video")]
    # citations may be dicts via to_dict path — also inspect answer payload
    ad = ask.to_dict() if hasattr(ask, "to_dict") else {}
    if not video_cites and isinstance(ad.get("citations"), list):
        video_cites = [c for c in ad["citations"] if c.get("kind") == "video"]
        photo_cites = [c for c in ad["citations"] if c.get("kind") == "photo"]
    _check(
        "p2i1_ask_photos_and_moments",
        len(photo_cites) >= 1 and (len(video_cites) >= 1 or len(moments) >= 1),
        checks,
        problems,
        detail=f"photos={len(photo_cites)} videos={len(video_cites)} moments={len(moments)}",
    )

    # Jump-to-moment URL present
    play_urls = []
    for c in video_cites:
        if isinstance(c, dict):
            play_urls.append(c.get("play_url") or "")
        else:
            play_urls.append(getattr(c, "play_url", "") or "")
    for m in moments:
        play_urls.append(m.get("play_url") or "")
    _check(
        "p2i1_jump_to_timeslot",
        any("t=" in (u or "") for u in play_urls),
        checks,
        problems,
        detail=str(play_urls[:3]),
    )

    # Correction case
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

    # Sync now second pass maps without re-creating
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
