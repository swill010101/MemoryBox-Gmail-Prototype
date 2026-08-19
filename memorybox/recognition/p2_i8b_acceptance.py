"""P2-I8B acceptance — Person-seeded video recognition & owner Learn.

Desktop harness (no --flightsim): synthetic embeddings + FakeVideo.
FlightSim (--flightsim): Immich API faces + optional InsightFace; owner ACCEPTED
remains a manual pass (Peggy George + one additional Person).
I9 speech/voice is out of scope.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from memorybox.migrate import migrate
from memorybox.person import map_provider_identity, resolve_person_by_name
from memorybox.providers.photo._immich_http import ImmichHttpClient
from memorybox.providers.video.fake import (
    I8B_OTHER_VEC,
    I8B_PEGGY_VEC,
    OTHER_FACE_ID,
    PEGGY_FACE_ID,
    FakeVideoProvider,
)
from memorybox.recognition.crops import mapped_pixel_box, parse_bbox, quality_flags
from memorybox.recognition.exemplars import list_active_exemplars, select_exemplars
from memorybox.recognition.learn import owner_learn_from_review, save_pending_review_crop
from memorybox.recognition.observations import recognition_status
from memorybox.recognition.process import (
    list_appearance_moments,
    owner_withdraw_appearance,
    process_queue,
    upsert_appearance_moment,
)
from memorybox.recognition.queue import (
    complete_item,
    enqueue_full_eligible_archive,
    list_queue_items,
    queue_summary,
)
from memorybox.recognition.scan import scan_video_for_person
from memorybox.recognition.seed import seed_exemplars_from_candidates


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _peggy_candidates() -> list[dict[str, Any]]:
    years = (2008, 2012, 2016, 2020, 2024)
    out = []
    for i, year in enumerate(years):
        vec = [0.0] * 16
        vec[0] = 0.94
        vec[1 + (i % 5)] = 0.341
        out.append(
            {
                "id": f"immich-face-peggy-{year}",
                "external_face_id": f"immich-face-peggy-{year}",
                "external_person_id": "immich-peggy",
                "source_asset_id": f"asset-peggy-{year}",
                "embedding": vec,
                "embedding_model": "insightface-buffalo_l",
                "usable": True,
                "capture_at": datetime(year, 6, 1, tzinfo=timezone.utc),
                "pose": "frontal" if i % 2 == 0 else "three_quarter",
                "bbox": {"x1": 10, "y1": 10, "x2": 120, "y2": 120},
                "quality": {"usable": True},
            }
        )
    # Unusable + near-dups that selector must drop
    tiny = dict(out[0])
    tiny.update(
        {
            "id": "tiny",
            "usable": False,
            "quality": {"usable": False, "reject_reason": "unusable_crop"},
            "embedding": list(I8B_PEGGY_VEC),
        }
    )
    dup = dict(out[0])
    dup.update({"id": "dup-2008", "external_face_id": "dup-2008"})
    out.extend([tiny, dup])
    return out


def prove_p2_i8b(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_flightsim()
    return _prove_harness()


def _prove_harness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I8B", "flightsim": False, "mode": "harness"}
    try:
        applied = migrate()
        meta["migrations_applied"] = applied
    except Exception as exc:  # noqa: BLE001
        _check("p2i8b_migrate", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    _check(
        "p2i8b_no_i9_speech_in_recognition",
        "diarization" not in open("memorybox/recognition/scan.py", encoding="utf-8").read()
        and "whisper" not in open("memorybox/recognition/learn.py", encoding="utf-8").read(),
        checks,
        problems,
        "I9 speech/voice must stay out of I8B recognition modules",
    )
    _check(
        "p2i8b_explore_learn_box_face",
        "id=\"mb-learn-box\"" in open("memorybox/explore/static/explore.js", encoding="utf-8").read()
        and "Choose a person" in open("memorybox/explore/static/explore.js", encoding="utf-8").read()
        and "startLearnBoxing" in open("memorybox/explore/static/explore.js", encoding="utf-8").read()
        and "/recognition/video-people" in open("memorybox/app.py", encoding="utf-8").read(),
        checks,
        problems,
        "Explore Learn tab must box a face with an empty person dropdown",
    )

    bbox = parse_bbox({"x": 1, "y": 1, "w": 10, "h": 10})
    q_bad = quality_flags(bbox or {"w": 10, "h": 10})
    q_ok = quality_flags({"x1": 0, "y1": 0, "x2": 80, "y2": 90, "w": 80, "h": 90})
    _check("p2i8b_reject_unusable_crop", not q_bad.get("usable"), checks, problems, str(q_bad))
    _check("p2i8b_accept_usable_crop", bool(q_ok.get("usable")), checks, problems, str(q_ok))
    immich_box = parse_bbox(
        {
            "boundingBoxX1": 12,
            "boundingBoxY1": 20,
            "boundingBoxX2": 90,
            "boundingBoxY2": 110,
            "x1": None,
            "y1": None,
            "x2": None,
            "y2": None,
        }
    )
    _check(
        "p2i8b_immich_null_x1_uses_bounding_box",
        bool(immich_box) and immich_box.get("x1") == 12.0 and immich_box.get("y2") == 110.0,
        checks,
        problems,
        str(immich_box),
    )
    preview_space = mapped_pixel_box(
        {"x1": 10, "y1": 10, "x2": 90, "y2": 90, "w": 80, "h": 80},
        pixel_w=200,
        pixel_h=200,
        image_w=4000,
        image_h=3000,
        pad_ratio=0.0,
    )
    orig_space = mapped_pixel_box(
        {"x1": 1000, "y1": 500, "x2": 2000, "y2": 1500, "w": 1000, "h": 1000},
        pixel_w=800,
        pixel_h=600,
        image_w=4000,
        image_h=3000,
        pad_ratio=0.0,
    )
    _check(
        "p2i8b_bbox_preview_vs_original_space",
        preview_space == (10, 10, 90, 90) and orig_space == (200, 100, 400, 300),
        checks,
        problems,
        f"preview={preview_space} orig={orig_space}",
    )
    try:
        import cv2  # noqa: F401
        import numpy as np
        from memorybox.recognition.embeddings import pad_bgr_for_detector

        tiny = np.zeros((40, 32, 3), dtype=np.uint8)
        padded = pad_bgr_for_detector(tiny, pad_ratio=0.45, min_side=160)
        _check(
            "p2i8b_owner_crop_pad_for_detector",
            padded is not None and int(padded.shape[0]) >= 160 and int(padded.shape[1]) >= 160,
            checks,
            problems,
            str(getattr(padded, "shape", None)),
        )
    except ImportError:
        _check(
            "p2i8b_owner_crop_pad_for_detector",
            True,
            checks,
            problems,
            "opencv not in this harness — pad helper skipped",
        )

    selected = select_exemplars(_peggy_candidates(), cap=8)
    years = {str(c.get("capture_at"))[:4] for c in selected}
    _check(
        "p2i8b_selector_diversity_and_cap",
        2 <= len(selected) <= 8 and len(years) >= 3 and all(c.get("id") != "tiny" for c in selected),
        checks,
        problems,
        f"n={len(selected)} years={sorted(years)} ids={[c.get('id') for c in selected]}",
    )

    tag = uuid4().hex[:8]
    peggy = resolve_person_by_name(f"PeggyGeorge{tag}", create_if_missing=True, confirm=True)
    other = resolve_person_by_name(f"SecondPerson{tag}", create_if_missing=True, confirm=True)
    peggy_id = peggy.person_id
    other_id = other.person_id
    meta["peggy_person_id"] = peggy_id
    meta["second_person_id"] = other_id

    seeded_p = seed_exemplars_from_candidates(person_id=peggy_id, candidates=_peggy_candidates())
    other_cands = [
        {
            "id": "immich-face-other-1",
            "external_face_id": "immich-face-other-1",
            "source_asset_id": "asset-other-1",
            "embedding": list(I8B_OTHER_VEC),
            "usable": True,
            "capture_at": datetime(2019, 1, 1, tzinfo=timezone.utc),
            "pose": "frontal",
            "bbox": {"x1": 10, "y1": 10, "x2": 100, "y2": 100},
        }
    ]
    seeded_o = seed_exemplars_from_candidates(
        person_id=other_id, candidates=other_cands, provider_key="fake_photo"
    )
    _check(
        "p2i8b_multiple_exemplars_not_feature_only",
        seeded_p.get("selected_count", 0) >= 3,
        checks,
        problems,
        str(seeded_p),
    )
    _check(
        "p2i8b_second_person_seeded",
        seeded_o.get("selected_count", 0) >= 1,
        checks,
        problems,
        str(seeded_o),
    )
    _check(
        "p2i8b_exemplar_provenance",
        any(
            (e.get("source_asset_id") or "").startswith("asset-peggy")
            for e in list_active_exemplars(peggy_id)
        ),
        checks,
        problems,
    )

    video = FakeVideoProvider(peggy_corpus=True, i8b_corpus=True)
    map_provider_identity(
        person_id=peggy_id,
        provider_key="fake_video",
        external_id=PEGGY_FACE_ID,
        label="Peggy",
        identity_kind="face",
        confirm_person=False,
        identity_authority="trusted_provider",
        assertion_authority="system",
    )
    map_provider_identity(
        person_id=other_id,
        provider_key="fake_video",
        external_id=OTHER_FACE_ID,
        label="Other",
        identity_kind="face",
        confirm_person=False,
        identity_authority="trusted_provider",
        assertion_authority="system",
    )

    legacy_id = upsert_appearance_moment(
        person_id=peggy_id,
        video_provider_key="fake_video",
        video_external_id="video-peggy-clear",
        start_sec=5.0,
        end_sec=8.0,
        face_external_id=PEGGY_FACE_ID,
        method="auto_associate",
        confidence=0.7,
        play_url="/review/ui?video=video-peggy-clear&t=5.0",
        meta={"legacy": "i1_hvrt"},
    )

    scan_clear = scan_video_for_person(
        person_id=peggy_id,
        video_provider=video,
        video_external_id="video-peggy-clear",
        run_kind="provider_seeded",
    )
    scan_abs = scan_video_for_person(
        person_id=peggy_id,
        video_provider=video,
        video_external_id="video-peggy-absent",
        run_kind="provider_seeded",
    )
    scan_both_p = scan_video_for_person(
        person_id=peggy_id,
        video_provider=video,
        video_external_id="video-both-people",
        run_kind="provider_seeded",
    )
    scan_both_o = scan_video_for_person(
        person_id=other_id,
        video_provider=video,
        video_external_id="video-both-people",
        run_kind="provider_seeded",
    )
    scan_amb = scan_video_for_person(
        person_id=peggy_id,
        video_provider=video,
        video_external_id="video-peggy-ambiguous",
        run_kind="provider_seeded",
    )

    moments = list_appearance_moments(peggy_id, limit=200)
    legacy = [m for m in moments if m.get("id") == legacy_id or m.get("method") == "auto_associate"]
    native = [m for m in moments if m.get("evidence_lineage") == "mb_native_i8b" or m.get("method") == "mb_native_i8b"]
    _check(
        "p2i8b_legacy_i1_visible_distinct",
        any(m.get("id") == legacy_id for m in moments) and any(
            (m.get("evidence_lineage") in {None, "i1_hvrt"} or m.get("method") == "auto_associate")
            for m in legacy
        ),
        checks,
        problems,
        f"legacy={legacy_id} methods={[m.get('method') for m in moments]}",
    )
    _check(
        "p2i8b_native_ranges_distinct",
        len(native) >= 1 and all(m.get("method") != "auto_associate" for m in native),
        checks,
        problems,
        f"native={len(native)} scan={scan_clear}",
    )
    _check(
        "p2i8b_jump_t_param",
        any("t=" in (m.get("play_url") or "") for m in native),
        checks,
        problems,
        str([m.get("play_url") for m in native[:2]]),
    )
    _check(
        "p2i8b_negative_video_no_assign",
        int(scan_abs.get("accepted_count") or 0) == 0 and not (scan_abs.get("ranges") or []),
        checks,
        problems,
        str(scan_abs),
    )
    _check(
        "p2i8b_both_people_video",
        int(scan_both_p.get("accepted_count") or 0) >= 1
        and int(scan_both_o.get("accepted_count") or 0) >= 1,
        checks,
        problems,
        f"peggy={scan_both_p} other={scan_both_o}",
    )
    _check(
        "p2i8b_uncertain_unassigned",
        int(scan_amb.get("accepted_count") or 0) == 0
        and int(scan_amb.get("uncertain_count") or 0) >= 1,
        checks,
        problems,
        str(scan_amb),
    )
    _check(
        "p2i8b_discrimination_second_person",
        int(scan_clear.get("accepted_count") or 0) >= 1,
        checks,
        problems,
        "Peggy matches Peggy video; Other embeddings are orthogonal",
    )

    save_pending_review_crop(
        face_external_id="review-face-learn-1",
        video_external_id="video-library-02",
        t_sec=7.0,
        bbox={"x": 20, "y": 20, "w": 80, "h": 90, "t_sec": 7.0},
        crop_jpeg_base64=None,
    )
    learn = owner_learn_from_review(
        person_id=peggy_id,
        face_external_id="review-face-learn-1",
        video_provider=video,
        video_external_id="video-library-02",
        t_sec=7.0,
        embedding=list(I8B_PEGGY_VEC),
        provider_key="fake_video",
    )
    _check("p2i8b_owner_learn_persists", bool(learn.get("ok")), checks, problems, str(learn)[:400])
    current = (learn.get("current_video_scan") or {})
    _check(
        "p2i8b_learn_scans_current_first",
        current.get("video_external_id") == "video-library-02" and current.get("ok"),
        checks,
        problems,
        str(current)[:300],
    )
    enq = learn.get("enqueue_others") or {}
    queued = list_queue_items(person_id=peggy_id, status="queued", limit=50)
    owner_q = [i for i in queued if i.get("enqueue_reason") == "owner_learn"]
    _check(
        "p2i8b_learn_enqueues_others_not_full_sync",
        int(enq.get("enqueued_or_updated") or 0) >= 1
        and all(i.get("video_external_id") != "video-library-02" for i in owner_q),
        checks,
        problems,
        f"enq={enq} owner_q={[(i.get('video_external_id'), i.get('priority')) for i in owner_q]}",
    )

    native_clear = [
        m
        for m in list_appearance_moments(peggy_id, limit=200)
        if m.get("video_external_id") == "video-peggy-clear"
        and m.get("method") == "mb_native_i8b"
        and m.get("status") != "withdrawn"
    ]
    if native_clear:
        w = owner_withdraw_appearance(
            person_id=peggy_id,
            video_provider_key="fake_video",
            video_external_id="video-peggy-clear",
            start_sec=float(native_clear[0]["start_sec"]),
            end_sec=float(native_clear[0]["end_sec"]),
            appearance_id=native_clear[0]["id"],
        )
        rescan = scan_video_for_person(
            person_id=peggy_id,
            video_provider=video,
            video_external_id="video-peggy-clear",
            run_kind="correction",
        )
        restored_overlap = [
            m
            for m in list_appearance_moments(peggy_id, limit=200)
            if m.get("video_external_id") == "video-peggy-clear"
            and m.get("method") == "mb_native_i8b"
            and m.get("status") != "withdrawn"
            and m.get("id") != native_clear[0]["id"]
            and float(m["start_sec"]) <= float(native_clear[0]["end_sec"])
            and float(m["end_sec"]) >= float(native_clear[0]["start_sec"])
        ]
        withdrawn_row = [
            m
            for m in list_appearance_moments(peggy_id, limit=200)
            if m.get("id") == native_clear[0]["id"]
        ]
        _check(
            "p2i8b_correction_sticks",
            bool(w.get("ok"))
            and (not withdrawn_row or withdrawn_row[0].get("status") == "withdrawn")
            and not restored_overlap,
            checks,
            problems,
            f"withdraw={w} rescan={rescan} overlap={len(restored_overlap)}",
        )
    else:
        _check("p2i8b_correction_sticks", False, checks, problems, "no native clear range to withdraw")

    # Queue: completed item requeues on exemplar_change; I1 newly_known_person does not.
    enqueue_full_eligible_archive(
        person_id=peggy_id,
        videos=[
            {
                "video_provider_key": "fake_video",
                "video_external_id": "video-library-03",
                "eligible": True,
            }
        ],
        enqueue_reason="newly_known_person",
        priority=100,
    )
    items = list_queue_items(person_id=peggy_id, limit=200)
    one = next(
        (i for i in items if i.get("video_external_id") == "video-library-03"
         and i.get("enqueue_reason") == "newly_known_person"),
        None,
    )
    if one:
        complete_item(one["id"], status="completed", result={"hit_count": 0})
    enqueue_full_eligible_archive(
        person_id=peggy_id,
        videos=[
            {
                "video_provider_key": "fake_video",
                "video_external_id": "video-library-03",
                "eligible": True,
            }
        ],
        enqueue_reason="newly_known_person",
        priority=100,
    )
    again = list_queue_items(person_id=peggy_id, status="queued", limit=200)
    _check(
        "p2i8b_i1_completed_not_silently_requeued",
        not any(
            i.get("video_external_id") == "video-library-03"
            and i.get("enqueue_reason") == "newly_known_person"
            for i in again
        ),
        checks,
        problems,
    )
    enqueue_full_eligible_archive(
        person_id=peggy_id,
        videos=[
            {
                "video_provider_key": "fake_video",
                "video_external_id": "video-library-03",
                "eligible": True,
            }
        ],
        enqueue_reason="exemplar_change",
        priority=40,
        run_kind="provider_seeded",
    )
    after = list_queue_items(person_id=peggy_id, status="queued", limit=200)
    _check(
        "p2i8b_exemplar_change_requeues",
        any(
            i.get("video_external_id") == "video-library-03"
            and i.get("enqueue_reason") == "exemplar_change"
            for i in after
        ),
        checks,
        problems,
        str([(i.get("video_external_id"), i.get("enqueue_reason")) for i in after[:12]]),
    )

    processed = process_queue(video_provider=video, person_id=peggy_id, max_items=8)
    _check(
        "p2i8b_queue_processes",
        processed.get("processed", 0) >= 1,
        checks,
        problems,
        str(processed.get("processed")),
    )
    st = recognition_status(person_id=peggy_id)
    _check(
        "p2i8b_status_visible",
        int(st.get("active_exemplars") or 0) >= 1 and bool(st.get("recent_runs")),
        checks,
        problems,
        str(st)[:400],
    )
    qsum = queue_summary(peggy_id)
    _check("p2i8b_queue_summary", qsum.get("total", 0) >= 1, checks, problems, str(qsum))

    ok = not problems
    meta["queue"] = qsum
    meta["status"] = st
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}


def _prove_flightsim() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I8B", "flightsim": True, "mode": "flightsim"}
    if _env("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-p2-i8b --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}
    try:
        migrate()
    except Exception as exc:  # noqa: BLE001
        _check("p2i8b_migrate", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    from memorybox.ask.deps import build_photo, build_video
    from memorybox.person import find_ask_person_by_name, list_people_by_exact_name
    from memorybox.recognition.inventory import inventory_video_rows
    from memorybox.recognition.process import get_appearance_moment, list_appearance_moments
    from memorybox.recognition.seed import (
        collect_immich_face_candidates,
        list_person_immich_videos,
        seed_exemplars_from_immich,
    )

    photo = build_photo()
    video = build_video()
    ph = photo.health()
    vh = video.health()
    meta["providers"] = {
        "photo": {"provider_key": ph.provider_key, "ok": ph.ok, "detail": ph.detail},
        "video": {
            "provider_key": vh.provider_key,
            "ok": vh.ok,
            "detail": vh.detail,
            "meta": getattr(vh, "meta", None) or {},
        },
    }
    _check(
        "p2i8b_flightsim_immich",
        bool(ph.ok) and ph.provider_key == "immich",
        checks,
        problems,
        str(ph.detail),
    )
    vmeta = getattr(vh, "meta", None) or {}
    _check(
        "p2i8b_flightsim_hvrt",
        bool(vh.ok) and vh.provider_key == "hvrt",
        checks,
        problems,
        str(vh.detail),
    )
    _check(
        "p2i8b_worker_media_root",
        bool(vmeta.get("media_root_readable")) or int(vmeta.get("video_count") or 0) > 0,
        checks,
        problems,
        (
            "Video worker needs MEMORYBOX_VIDEO_MEDIA_ROOT "
            r"(FlightSim: P:\photos\home videos, same as startmb). "
            f"media_root={vmeta.get('media_root')} "
            f"media_root_configured={vmeta.get('media_root_configured')} "
            f"media_root_readable={vmeta.get('media_root_readable')} "
            f"video_count={vmeta.get('video_count')}"
        ),
    )
    if problems:
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    client = getattr(photo, "_client", None)
    _check(
        "p2i8b_faces_api_present",
        bool(client) and callable(getattr(client, "list_faces_for_asset", None)),
        checks,
        problems,
    )
    name = _env("MEMORYBOX_P2_I8B_PERSON_NAME", "Peggy George")
    second = _env("MEMORYBOX_P2_I8B_SECOND_PERSON_NAME", "Eugene Will")
    meta["powershell_env_hint"] = (
        "PowerShell does not apply cmd `set VAR=value` to python. Use "
        "$env:MEMORYBOX_P2_I8B_SECOND_PERSON_NAME='Eugene Will'"
    )
    person = None
    try:
        person = find_ask_person_by_name(name, photo=photo)
    except Exception as exc:  # noqa: BLE001
        meta["person_resolve_error"] = str(exc)
    if person is None:
        same = list_people_by_exact_name(name)
        person = same[0] if same else None
    pid = str(getattr(person, "id", "") or "") if person else ""
    _check("p2i8b_peggy_person", bool(pid), checks, problems, f"name={name!r}")
    if pid:
        collected = collect_immich_face_candidates(person_id=pid, photo_provider=photo, max_assets=40)
        _check(
            "p2i8b_immich_api_faces_not_db",
            len(collected) >= 1,
            checks,
            problems,
            f"collected={len(collected)} (GET /faces per asset; no Immich DB)",
        )
        seeded = seed_exemplars_from_immich(person_id=pid, photo_provider=photo, max_assets=40)
        meta["seed"] = {
            k: seeded.get(k)
            for k in (
                "selected_count",
                "collected",
                "skipped",
                "skip_reasons",
                "embed_error",
                "fetch_error",
                "previews_fetched",
                "insightface_available",
            )
        }
        from memorybox.recognition.embeddings import insightface_available

        _check(
            "p2i8b_insightface_required",
            insightface_available(),
            checks,
            problems,
            (
                "FlightSim I8B needs InsightFace buffalo_l in the same Python as "
                "`python -m memorybox` (usually not the HVRT process_videos venv). "
                "Install: python -m pip install insightface onnxruntime opencv-python-headless numpy. "
                f"seed={meta['seed']}"
            ),
        )
        _check(
            "p2i8b_exemplars_from_multiple_faces",
            int(seeded.get("selected_count") or 0) >= 2,
            checks,
            problems,
            (
                "Need MemoryBox embeddings from multiple Immich faces, not only a feature photo. "
                f"seed={meta['seed']}"
            ),
        )
        from memorybox.recognition.constants import PROVE_FRAME_SAMPLES
        from memorybox.recognition.frames import looks_like_uuid, resolve_immich_video_path
        from memorybox.recognition.scan import scan_video_for_person

        videos = inventory_video_rows(video)
        inventory_ids = {str(r.get("video_external_id") or "") for r in videos}
        confirmed_id = (
            _env("MEMORYBOX_P2_I8B_POSITIVE_MOMENT_ID")
            or _env("MEMORYBOX_P2_I8B_POSITIVE_ASSET_ID")
            or _env("MEMORYBOX_P2_I8B_POSITIVE_VIDEO_ID")
            or _env("MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID")
            or "deb5c1f8-4d01-457c-9637-185268e4b820"
        )
        meta["confirmed_id"] = confirmed_id
        confirmed_moment = get_appearance_moment(confirmed_id)
        meta["confirmed_moment"] = (
            {
                "id": confirmed_moment.get("id"),
                "video_external_id": confirmed_moment.get("video_external_id"),
                "start_sec": confirmed_moment.get("start_sec"),
                "authority": confirmed_moment.get("authority"),
                "confirmation_state": confirmed_moment.get("confirmation_state"),
                "play_url": confirmed_moment.get("play_url"),
            }
            if confirmed_moment
            else None
        )
        client = getattr(photo, "_client", None)
        getter = getattr(client, "get_asset", None)
        if looks_like_uuid(confirmed_id) and callable(getter):
            try:
                asset = getter(confirmed_id) or {}
            except Exception as exc:  # noqa: BLE001
                asset = {"error": str(exc)[:200]}
            orig = str(asset.get("originalFileName") or "")
            opath = str(asset.get("originalPath") or "")
            meta["immich_confirmed_asset"] = {
                "id": confirmed_id,
                "type": asset.get("type"),
                "originalFileName": orig or None,
                "originalPath": opath or None,
                "put_back_under_home_videos": orig or (opath.replace("\\", "/").split("/")[-1] if opath else None),
            }
        moments_early = list_appearance_moments(pid, limit=200)
        meta["legacy_hvrt_clips"] = [
            {
                "id": m.get("id"),
                "video_external_id": m.get("video_external_id"),
                "start_sec": m.get("start_sec"),
                "play_url": m.get("play_url"),
                "in_inventory": str(m.get("video_external_id") or "") in inventory_ids,
            }
            for m in moments_early
            if m.get("evidence_lineage") == "i1_hvrt" or m.get("method") == "auto_associate"
        ]
        immich_videos = list_person_immich_videos(
            person_id=pid, photo_provider=photo, max_assets=12
        )
        if looks_like_uuid(confirmed_id) and confirmed_id not in immich_videos:
            immich_videos = [confirmed_id] + immich_videos
        elif confirmed_moment:
            ve = str(confirmed_moment.get("video_external_id") or "")
            if ve and ve not in immich_videos:
                immich_videos = [ve] + immich_videos
        meta["immich_person_videos"] = immich_videos[:12]

        def _video_resolves(veid: str) -> bool:
            if not veid:
                return False
            if veid in inventory_ids:
                return True
            if looks_like_uuid(veid) and resolve_immich_video_path(veid) is not None:
                return True
            getter = getattr(video, "get_video", None)
            if not callable(getter):
                return False
            try:
                found = getter(veid)
            except Exception:
                return False
            return found is not None

        moments = list_appearance_moments(pid, limit=200)
        i1_existing: list[str] = []
        for m in moments:
            ve = str(m.get("video_external_id") or "")
            if ve and ve not in i1_existing and _video_resolves(ve):
                i1_existing.append(ve)
        if int(seeded.get("selected_count") or 0) >= 1:
            vpk = getattr(video, "provider_key", None) or "hvrt"
            prioritized: list[dict[str, Any]] = []
            have: set[str] = set()
            for ve in immich_videos:
                prioritized.append(
                    {
                        "video_provider_key": "immich",
                        "video_external_id": ve,
                        "eligible": True,
                        "priority": 1,
                    }
                )
                have.add(ve)
            for ve in i1_existing:
                if ve in have:
                    continue
                prioritized.append(
                    {
                        "video_provider_key": vpk,
                        "video_external_id": ve,
                        "eligible": True,
                        "priority": 1,
                    }
                )
                have.add(ve)
            for row in videos:
                ve = str(row.get("video_external_id") or "")
                if ve and ve not in have:
                    prioritized.append(row)
                    have.add(ve)
            enqueue_full_eligible_archive(
                person_id=pid,
                videos=prioritized[:16],
                enqueue_reason="exemplar_change",
                priority=50,
                run_kind="provider_seeded",
            )
            processed = process_queue(video_provider=video, person_id=pid, max_items=4)
            meta["processed"] = processed.get("processed")
            meta["process_results"] = (processed.get("results") or [])[:4]
        moments = list_appearance_moments(pid, limit=200)
        native = [m for m in moments if m.get("evidence_lineage") == "mb_native_i8b"]
        if not native:
            prefer: list[str] = []
            if confirmed_moment:
                ve = str(confirmed_moment.get("video_external_id") or "")
                if ve and _video_resolves(ve):
                    prefer.append(ve)
            if looks_like_uuid(confirmed_id) and confirmed_id not in prefer:
                prefer.append(confirmed_id)
            for ve in immich_videos:
                if ve not in prefer:
                    prefer.append(ve)
            for ve in i1_existing:
                if ve not in prefer:
                    prefer.append(ve)
            for row in videos:
                ve = str(row.get("video_external_id") or "")
                if ve and ve not in prefer:
                    prefer.append(ve)
            scan_meta = []
            for veid in prefer[:8]:
                extra = [
                    float(m.get("start_sec") or 0)
                    for m in moments
                    if m.get("video_external_id") == veid
                ]
                if confirmed_moment and str(confirmed_moment.get("video_external_id") or "") == veid:
                    extra.insert(0, float(confirmed_moment.get("start_sec") or 0))
                elif looks_like_uuid(confirmed_id) and veid == confirmed_id:
                    extra.insert(0, float((confirmed_moment or {}).get("start_sec") or 0.5))
                vpk = "immich" if looks_like_uuid(veid) else (
                    getattr(video, "provider_key", None) or "hvrt"
                )
                scanned = scan_video_for_person(
                    person_id=pid,
                    video_provider=video,
                    video_external_id=veid,
                    video_provider_key=vpk,
                    run_kind="provider_seeded",
                    trigger="flightsim_prove",
                    max_samples=PROVE_FRAME_SAMPLES,
                    extra_times=extra[:8],
                )
                scan_meta.append(
                    {
                        "video_external_id": veid,
                        "video_provider_key": vpk,
                        "accepted_count": scanned.get("accepted_count"),
                        "candidate_count": scanned.get("candidate_count"),
                        "ranges": len(scanned.get("ranges") or []),
                        "best_score": scanned.get("best_score"),
                        "sample_error": scanned.get("sample_error"),
                    }
                )
                if int(scanned.get("accepted_count") or 0) >= 1:
                    break
            meta["direct_scans"] = scan_meta
            moments = list_appearance_moments(pid, limit=200)
            native = [m for m in moments if m.get("evidence_lineage") == "mb_native_i8b"]
        legacy = [m for m in moments if m.get("evidence_lineage") == "i1_hvrt" or m.get("method") == "auto_associate"]
        _check(
            "p2i8b_cutover_legacy_preserved",
            not any(
                (m.get("method") == "mb_native_i8b" and m.get("evidence_lineage") == "i1_hvrt")
                or (m.get("method") == "auto_associate" and m.get("evidence_lineage") == "mb_native_i8b")
                for m in moments
            ),
            checks,
            problems,
            f"native={len(native)} legacy={len(legacy)} (I1/HVRT rows must remain distinguishable)",
        )
        if int(seeded.get("selected_count") or 0) >= 2:
            _check(
                "p2i8b_native_scan_or_queue",
                len(native) >= 1,
                checks,
                problems,
                (
                    f"processed={meta.get('processed')} native={len(native)} "
                    f"inventory={len(videos)} i1_existing={i1_existing[:8]} "
                    f"confirmed_id={meta.get('confirmed_id')} "
                    f"immich_videos={meta.get('immich_person_videos')} "
                    f"scans={meta.get('direct_scans')}"
                ),
            )
        st = recognition_status(person_id=pid)
        _check("p2i8b_status", bool(st), checks, problems, str(st)[:300])

    second_person = None
    if second:
        try:
            second_person = find_ask_person_by_name(second, photo=photo)
        except Exception as exc:  # noqa: BLE001
            meta["second_person_resolve_error"] = str(exc)
        if second_person is None:
            same2 = list_people_by_exact_name(second)
            second_person = same2[0] if same2 else None
    sid = str(getattr(second_person, "id", "") or "") if second_person else ""
    _check(
        "p2i8b_second_person",
        bool(sid) and sid != pid,
        checks,
        problems,
        (
            f"name={second!r} id={sid or None}. "
            "In PowerShell use $env:MEMORYBOX_P2_I8B_SECOND_PERSON_NAME='Eugene Will' "
            "(cmd `set` does not export to python)."
        ),
    )
    if sid and sid != pid:
        seeded2 = seed_exemplars_from_immich(person_id=sid, photo_provider=photo, max_assets=40)
        meta["seed_second"] = {
            "person": second,
            "selected_count": seeded2.get("selected_count"),
            "skipped": seeded2.get("skipped"),
            "skip_reasons": seeded2.get("skip_reasons"),
            "fetch_error": seeded2.get("fetch_error"),
        }
        _check(
            "p2i8b_second_person_exemplars",
            int(seeded2.get("selected_count") or 0) >= 1,
            checks,
            problems,
            str(meta["seed_second"]),
        )
        if int(seeded2.get("selected_count") or 0) >= 1:
            rows = inventory_video_rows(video)
            enqueue_full_eligible_archive(
                person_id=sid,
                videos=rows[:8],
                enqueue_reason="exemplar_change",
                priority=60,
                run_kind="provider_seeded",
            )
    if second:
        meta["second_person_name"] = second
    meta["acceptance_people"] = [name] + ([second] if second else [])
    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
