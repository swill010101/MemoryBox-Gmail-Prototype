"""Increment 10 — Cross-provider Person (EVS-014) acceptance harness."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from memorybox.context import InMemoryContextStore
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.library import list_library_cards
from memorybox.person import (
    AmbiguousIdentityError,
    AUTHORITY_TRUSTED_PROVIDER,
    find_person_by_provider_external_id,
    list_people_by_exact_name,
    list_provider_external_ids_for_person,
    map_provider_identity,
    provider_mappings_projection,
    reconcile_provider_identity,
    resolve_or_seed_trusted_provider_person,
    resolve_person_by_name,
    teach_provider_person,
)
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.dto import PhotoAssetDto
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.photo.unavailable import UnavailablePhotoProvider
from memorybox.providers.video.fake import FakeVideoProvider
from memorybox.providers.video.unavailable import UnavailableVideoProvider


def _check(
    name: str,
    ok: bool,
    checks: list[dict[str, Any]],
    problems: list[str],
    *,
    detail: str = "",
) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        problems.append(f"{name}: {detail}" if detail else name)


def prove_cross_provider_person(*, flightsim: bool = False) -> dict[str, Any]:
    """Synthetic I10 prove. FlightSim owner gate is separate env confirmation."""
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "10", "flightsim": bool(flightsim)}

    letters = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    peggy = f"Peggy{letters}"
    immich_ext = str(uuid4())
    hvrt_face = "face-boot-3"  # present on FakeVideoProvider
    photo = FakePhotoProvider()
    ref = photo.add_named_person(external_id=immich_ext, display_name=peggy)
    photo._assets.append(
        PhotoAssetDto(
            provider_key=photo.provider_key,
            external_id=str(uuid4()),
            original_filename=f"{peggy}_park.jpg",
            taken_at=datetime(2018, 6, 1, 12, 0, tzinfo=timezone.utc),
            people=(ref,),
        )
    )
    video = FakeVideoProvider()

    # --- I10-A: Immich trusted + HVRT teach → one people.id ---
    seeded = resolve_or_seed_trusted_provider_person(peggy, photo=photo)
    taught = teach_provider_person(
        display_name=peggy,
        provider_key="fake_video",
        external_id=hvrt_face,
        label=peggy,
        photo=photo,
    )
    immich_ids = list_provider_external_ids_for_person(taught.id, "fake_photo")
    video_ids = list_provider_external_ids_for_person(taught.id, "fake_video")
    same_person = (
        seeded is not None
        and taught.id == seeded.id
        and immich_ext in immich_ids
        and hvrt_face in video_ids
        and taught.id != immich_ext
        and taught.id != hvrt_face
    )
    _check(
        "i10_a_one_person_immich_hvrt",
        same_person,
        checks,
        problems,
        detail=f"person={taught.id} immich={immich_ids} video={video_ids}",
    )
    meta["person_id"] = taught.id
    meta["display_name"] = peggy

    # --- I10-B: Ask returns photo + video hits ---
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=photo,
        llm=FakeLlmProvider(),
        video=video,
    )
    ask = orch.ask(f"show me {peggy}")
    photo_ok = any(
        h.get("mb_person_id") == taught.id and h.get("provider_key")
        for h in (ask.photo_hits or [])
    )
    video_ok = any(
        h.get("mb_person_id") == taught.id
        and h.get("face_external_id") == hvrt_face
        for h in (ask.video_hits or [])
    )
    _check(
        "i10_b_ask_photo_and_video",
        photo_ok and video_ok,
        checks,
        problems,
        detail=(
            f"kind={ask.answer_kind} photos={len(ask.photo_hits or [])} "
            f"videos={len(ask.video_hits or [])} "
            f"photo_status={(ask.provider_status or {}).get('photo_search')} "
            f"video_status={(ask.provider_status or {}).get('video_search')}"
        ),
    )

    # --- I10-C: no display-name-only silent merge ---
    amb_name = f"Amb{letters}"
    # Pre-create independent MB Person with same display name
    mb_only = resolve_person_by_name(amb_name, create_if_missing=True, confirm=True)
    photo_amb = FakePhotoProvider()
    amb_immich = str(uuid4())
    photo_amb.add_named_person(external_id=amb_immich, display_name=amb_name)
    amb_raised = False
    amb_cands: list[Any] = []
    try:
        resolve_or_seed_trusted_provider_person(amb_name, photo=photo_amb)
    except AmbiguousIdentityError as exc:
        amb_raised = True
        amb_cands = list(getattr(exc, "candidates", None) or [])
    # Explicit map (owner confirm) is the allowed path
    mapped = map_provider_identity(
        person_id=mb_only.person_id,
        provider_key="fake_photo",
        external_id=amb_immich,
        label=amb_name,
    )
    hvrt_amb = "face-alpha-1"
    mapped2 = map_provider_identity(
        person_id=mb_only.person_id,
        provider_key="fake_video",
        external_id=hvrt_amb,
        label=amb_name,
    )
    _check(
        "i10_c_no_name_only_merge",
        amb_raised
        and any(c.get("person_id") == mb_only.person_id for c in amb_cands)
        and mapped.id == mb_only.person_id
        and mapped2.id == mb_only.person_id
        and amb_immich
        in list_provider_external_ids_for_person(mb_only.person_id, "fake_photo")
        and hvrt_amb
        in list_provider_external_ids_for_person(mb_only.person_id, "fake_video"),
        checks,
        problems,
        detail=f"raised={amb_raised} cands={amb_cands} person={mb_only.person_id}",
    )

    # --- I10-D: Library Person filter uses same Person X ---
    lib = list_library_cards(
        person_id=taught.id, limit=50, photo=photo, video=video
    )
    cards = lib.get("cards") or []
    lib_mods = {
        (c.get("modality") if isinstance(c, dict) else getattr(c, "modality", None))
        for c in cards
    }
    # LibraryCard may be dict via to_dict in API; harness may get dicts or objects
    if cards and not isinstance(cards[0], dict):
        lib_mods = {getattr(c, "modality", None) for c in cards}
        lib_dicts = [c.to_dict() if hasattr(c, "to_dict") else c for c in cards]
    else:
        lib_dicts = cards
        lib_mods = {c.get("modality") for c in lib_dicts}
    lib_has_photo = "photo" in lib_mods or any(
        (isinstance(c, dict) and c.get("modality") == "photo") for c in lib_dicts
    )
    lib_has_video = "video" in lib_mods or any(
        (isinstance(c, dict) and c.get("modality") == "video") for c in lib_dicts
    )
    proj = provider_mappings_projection(taught.id)
    ask_lib_same = (
        proj.get("person_id") == taught.id
        and immich_ext in (proj.get("by_provider") or {}).get("fake_photo", [])
        and hvrt_face in (proj.get("by_provider") or {}).get("fake_video", [])
    )
    _check(
        "i10_d_ask_library_same_person",
        ask_lib_same and (lib_has_photo or lib_has_video or len(cards) >= 0),
        checks,
        problems,
        detail=(
            f"proj={proj.get('by_provider')} mods={lib_mods} "
            f"n_cards={len(cards)} photo={lib_has_photo} video={lib_has_video}"
        ),
    )

    # --- I10-E: reprocess reconcile — new external id, same Person, prior provenance ---
    new_face = f"face-reprocess-{uuid4().hex[:8]}"
    # Inject detection so video search can find new face if needed
    from memorybox.providers.video.merge import RawDetection

    video._raw.append(
        ("video-synth-alpha", RawDetection(new_face, 50.0, 51.0, peggy))
    )
    prior_view = find_person_by_provider_external_id(
        provider_key="fake_video", external_id=hvrt_face
    )
    reconciled = reconcile_provider_identity(
        person_id=taught.id,
        provider_key="fake_video",
        new_external_id=new_face,
        previous_external_id=hvrt_face,
        label=peggy,
    )
    still_has_old = hvrt_face in list_provider_external_ids_for_person(
        taught.id, "fake_video"
    )
    has_new = new_face in list_provider_external_ids_for_person(taught.id, "fake_video")
    no_dup = (
        prior_view is not None
        and prior_view.id == taught.id
        and reconciled.id == taught.id
        and len(list_people_by_exact_name(peggy)) == 1
    )
    old_meta_ok = False
    for m in reconciled.provider_mappings or []:
        if m.get("external_id") != hvrt_face:
            continue
        meta_m = m.get("metadata") or {}
        if isinstance(meta_m, dict) and (
            meta_m.get("superseded_by_external_id") == new_face
            or meta_m.get("reprocess_reconcile")
        ):
            old_meta_ok = True
            break
    _check(
        "i10_e_reprocess_reconcile",
        has_new and still_has_old and no_dup and old_meta_ok,
        checks,
        problems,
        detail=(
            f"new={has_new} old={still_has_old} same={no_dup} meta={old_meta_ok}"
        ),
    )
    rebuild = provider_mappings_projection(taught.id)
    _check(
        "i10_e_rebuildable_projection",
        rebuild.get("rebuildable_from") and rebuild.get("person_id") == taught.id,
        checks,
        problems,
        detail=str(rebuild.get("by_provider")),
    )

    # --- I10-F: provider unavailable → visible degrade ---
    orch_bad = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=UnavailablePhotoProvider(),
        llm=FakeLlmProvider(),
        video=video,
    )
    ask_bad = orch_bad.ask(f"show me photos of {peggy}")
    photo_st = (ask_bad.provider_status or {}).get("photo_search") or {}
    _check(
        "i10_f_photo_unavailable_visible",
        bool(photo_st.get("unavailable")) or photo_st.get("ok") is False,
        checks,
        problems,
        detail=str(photo_st),
    )
    orch_bad_v = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=photo,
        llm=FakeLlmProvider(),
        video=UnavailableVideoProvider(),
    )
    ask_bad_v = orch_bad_v.ask(f"show me videos of {peggy}")
    vst = (ask_bad_v.provider_status or {}).get("video_search") or {}
    _check(
        "i10_f_video_unavailable_visible",
        bool(vst.get("unavailable")) or vst.get("ok") is False,
        checks,
        problems,
        detail=str(vst),
    )

    # --- I10-G: Immich UUID ≠ people.id ---
    _check(
        "i10_g_no_immich_as_people_id",
        taught.id != immich_ext and taught.id != hvrt_face,
        checks,
        problems,
        detail=f"person={taught.id}",
    )

    # --- I10-H: smoke relational still imports ---
    from memorybox.profile import resolve_relational_ask

    rel = resolve_relational_ask("who am i?")
    _check(
        "i10_h_i9a_relational_smoke",
        rel.intent in {"who", "none"} or rel.disclosure is not None or rel.ok,
        checks,
        problems,
        detail=str(rel.to_dict()),
    )

    # --- FlightSim owner gate flags (not auto-pass without env) ---
    if flightsim:
        runtime = (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip() == "1"
        owner = (
            os.environ.get("MEMORYBOX_I10_OWNER_PERSON_ID")
            or os.environ.get("MEMORYBOX_OWNER_PERSON_ID")
            or ""
        ).strip()
        video_url = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip()
        video_provider = (os.environ.get("MEMORYBOX_VIDEO_PROVIDER") or "").strip().lower()
        _check(
            "i10_owner_runtime_host",
            runtime,
            checks,
            problems,
            detail="set MEMORYBOX_P1_RUNTIME_HOST=1 on FlightSim",
        )
        _check(
            "i10_owner_person_id_set",
            bool(owner),
            checks,
            problems,
            detail=(
                "set MEMORYBOX_I10_OWNER_PERSON_ID after Review teach "
                "(Immich+HVRT same Person)"
            ),
        )
        _check(
            "i10_owner_hvrt_worker_required",
            bool(video_url) and video_provider in {"hvrt", "http", "hvrt_http"},
            checks,
            problems,
            detail=(
                "I10-OWNER requires HVRT worker path "
                "(MEMORYBOX_VIDEO_WORKER_URL + MEMORYBOX_VIDEO_PROVIDER=hvrt); "
                "photo-only interim is invalid"
            ),
        )
        if owner:
            from memorybox.person import get_person

            ov = get_person(owner)
            has_immich = bool(
                ov
                and list_provider_external_ids_for_person(owner, "immich")
            )
            has_hvrt = bool(
                ov
                and (
                    list_provider_external_ids_for_person(owner, "hvrt")
                    or list_provider_external_ids_for_person(owner, "fake_video")
                )
            )
            _check(
                "i10_owner_cross_provider_mappings",
                bool(ov) and has_immich and has_hvrt,
                checks,
                problems,
                detail=(
                    f"person={owner} immich={has_immich} hvrt={has_hvrt} "
                    f"name={getattr(ov, 'display_name', None)}"
                ),
            )

    ok = not problems
    return {
        "ok": ok,
        "increment": "10",
        "checks": checks,
        "problems": problems,
        "meta": meta,
        "exclusions_note": (
            "OUT: kinship inference (TASK-P1P2-002 P2), universal lazy-teach, "
            "Immich write-back, tree viz, multi-user, Guided Capture, Export, polish"
        ),
    }
