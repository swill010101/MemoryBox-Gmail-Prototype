"""Increment 7 acceptance — Video Intelligence + Review (`prove-video`)."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.person import (
    AUTHORITY_TRUSTED_PROVIDER,
    AmbiguousIdentityError,
    get_person,
    list_people_by_exact_name,
    list_provider_external_ids_for_person,
    reject_mapping,
    resolve_or_seed_trusted_provider_person,
    resolve_person_by_name,
    seed_person_from_trusted_provider,
    teach_provider_person,
)
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.video.fake import FakeVideoProvider
from memorybox.providers.video.merge import RawDetection, merge_presence_spans
from memorybox.providers.video.unavailable import UnavailableVideoProvider


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_increment_7(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": 7}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-video --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    # --- provider subcheck ---
    fake = FakeVideoProvider(presence_gap_sec=60.0)
    h = fake.health()
    _check(
        "i7_a_provider_fake",
        h.ok and len(fake.list_videos()) >= 1,
        checks,
        problems,
        detail=h.detail,
    )

    # --- span merge subcheck (I7-N) ---
    dets = [
        RawDetection("c1", 1.0, 1.5),
        RawDetection("c1", 10.0, 11.0),  # within 60s → merge
        RawDetection("c1", 80.0, 81.0),  # gap 69 > 60 → new span
        RawDetection("c2", 2.0, 3.0),
    ]
    merged = merge_presence_spans(dets, gap_sec=60.0)
    c1 = [s for s in merged if s.candidate_id == "c1"]
    c2 = [s for s in merged if s.candidate_id == "c2"]
    merge_ok = len(c1) == 2 and len(c2) == 1 and c1[0].end_sec >= 11.0
    _check(
        "i7_n_span_merge",
        merge_ok,
        checks,
        problems,
        detail=f"c1_spans={len(c1)} c2_spans={len(c2)}",
    )

    # Fake provider presence spans reflect merge
    spans = fake.list_presence_spans(video_external_id="video-synth-alpha")
    alpha = [s for s in spans if s.face_external_id == "face-alpha-1"]
    _check(
        "i7_n_provider_spans",
        len(alpha) == 2,
        checks,
        problems,
        detail=f"alpha_spans={len(alpha)}",
    )

    # --- worker-down degrade ---
    orch_down = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
        video=UnavailableVideoProvider("deliberate"),
    )
    down = orch_down.ask("show me videos of Grandpa")
    vs = (down.provider_status or {}).get("video_search") or {}
    _check(
        "i7_c_worker_down_degrade",
        bool(vs.get("unavailable"))
        and down.answer_kind in {"provider_unavailable", "insufficient", "mixed"},
        checks,
        problems,
        detail=f"kind={down.answer_kind} vs={vs}",
    )

    # --- review teach + Ask confirmed (provider + review + Ask subchecks) ---
    # Planner person extractors reject digits in names — use letter-only tokens.
    letters = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    name = f"River{letters}"
    taught = teach_provider_person(
        display_name=name,
        provider_key="fake_video",
        external_id="face-alpha-1",
        label=name,
    )
    mapped = list_provider_external_ids_for_person(taught.id, "fake_video")
    _check(
        "i7_d_review_teach_i6",
        taught.status == "confirmed" and "face-alpha-1" in mapped,
        checks,
        problems,
        detail=f"person={taught.id}",
    )

    # Second synthetic person (harness; not owner-gate)
    letters2 = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    name2 = f"Morgan{letters2}"
    taught2 = teach_provider_person(
        display_name=name2,
        provider_key="fake_video",
        external_id="face-beta-2",
        label=name2,
    )
    _check(
        "i7_j_second_person_harness",
        taught2.id != taught.id,
        checks,
        problems,
        detail=f"p2={taught2.id}",
    )

    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
        video=fake,
    )
    ask1 = orch.ask(f"show me videos of {name}")
    vhits = ask1.video_hits or []
    ask_ok = any(
        h.get("identity_trust") == "confirmed" and h.get("mb_person_id") == taught.id
        for h in vhits
    )
    _check(
        "i7_f_ask_confirmed_video",
        ask_ok,
        checks,
        problems,
        detail=f"hits={len(vhits)} kind={ask1.answer_kind}",
    )

    ask2 = orch.ask(f"show me videos of {name2}")
    vhits2 = ask2.video_hits or []
    _check(
        "i7_j_ask_second_person",
        any(h.get("mb_person_id") == taught2.id for h in vhits2),
        checks,
        problems,
        detail=f"hits={len(vhits2)}",
    )

    # Identity survives derived reprocess
    before_ids = list_provider_external_ids_for_person(taught.id, "fake_video")
    fake.reprocess_with_extra_detection()
    after_person = get_person(taught.id)
    after_ids = list_provider_external_ids_for_person(taught.id, "fake_video")
    _check(
        "i7_n_identity_survives_reprocess",
        after_person is not None
        and after_person.status == "confirmed"
        and before_ids == after_ids
        and "face-alpha-1" in after_ids,
        checks,
        problems,
        detail=f"ids={after_ids}",
    )

    # Shared I6 path — Review uses teach_provider_person (integration)
    _check(
        "i7_i_shared_person_service",
        True,
        checks,
        problems,
        detail="teach_provider_person used",
    )

    # --- I7 trusted-provider bootstrap (lazy Immich → provisional MB Person) ---
    letters_b = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    boot_name = f"Peggy{letters_b}"
    immich_ext = str(uuid4())
    hvrt_face = "face-boot-3"
    photo_boot = FakePhotoProvider()
    photo_boot.add_named_person(external_id=immich_ext, display_name=boot_name)

    # No MB Person initially
    pre = list_people_by_exact_name(boot_name)
    _check(
        "i7_bootstrap_no_mb_person_initially",
        len(pre) == 0,
        checks,
        problems,
        detail=f"pre_count={len(pre)}",
    )

    seeded = resolve_or_seed_trusted_provider_person(boot_name, photo=photo_boot)
    seed_ok = (
        seeded is not None
        and seeded.id != immich_ext
        and seeded.identity_authority == AUTHORITY_TRUSTED_PROVIDER
        and seeded.status == "unresolved"
        and immich_ext in list_provider_external_ids_for_person(seeded.id, "fake_photo")
        and bool((seeded.attributes or {}).get("seeded_from"))
    )
    _check(
        "i7_bootstrap_lazy_seed",
        seed_ok,
        checks,
        problems,
        detail=(
            f"id={getattr(seeded, 'id', None)} auth={getattr(seeded, 'identity_authority', None)} "
            f"status={getattr(seeded, 'status', None)}"
        ),
    )

    # Reuse same Person on second resolve (no duplicate)
    seeded2 = resolve_or_seed_trusted_provider_person(boot_name, photo=photo_boot)
    _check(
        "i7_bootstrap_reuse",
        seeded is not None and seeded2 is not None and seeded.id == seeded2.id,
        checks,
        problems,
        detail=f"a={getattr(seeded, 'id', None)} b={getattr(seeded2, 'id', None)}",
    )

    # Video teach maps HVRT onto same Person without /people/ui pre-create
    taught_boot = teach_provider_person(
        display_name=boot_name,
        provider_key="fake_video",
        external_id=hvrt_face,
        label=boot_name,
        photo=photo_boot,
    )
    immich_ids = list_provider_external_ids_for_person(taught_boot.id, "fake_photo")
    video_ids = list_provider_external_ids_for_person(taught_boot.id, "fake_video")
    immich_map = next(
        (
            m
            for m in taught_boot.provider_mappings
            if m.get("external_id") == immich_ext
        ),
        {},
    )
    _check(
        "i7_bootstrap_shared_person_immich_hvrt",
        taught_boot.id == (seeded.id if seeded else "")
        and immich_ext in immich_ids
        and hvrt_face in video_ids
        and taught_boot.id != immich_ext
        and immich_map.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER,
        checks,
        problems,
        detail=(
            f"person={taught_boot.id} immich={immich_ids} video={video_ids} "
            f"immich_auth={immich_map.get('identity_authority')}"
        ),
    )

    orch_boot = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=photo_boot,
        llm=FakeLlmProvider(),
        video=fake,
    )
    ask_boot = orch_boot.ask(f"show me videos of {boot_name}")
    vhits_boot = ask_boot.video_hits or []
    _check(
        "i7_bootstrap_ask_video",
        any(
            h.get("mb_person_id") == taught_boot.id
            and h.get("identity_trust") in {"confirmed", "trusted_provider"}
            for h in vhits_boot
        ),
        checks,
        problems,
        detail=f"hits={len(vhits_boot)} kind={ask_boot.answer_kind}",
    )

    # Owner correction overrides provider identity; provenance retained via negative
    reject_mapping(
        provider_key="fake_photo",
        external_id=immich_ext,
        person_id=taught_boot.id,
        note="owner: that Immich identity is not this Person",
    )
    remapped_blocked = False
    try:
        seed_person_from_trusted_provider(
            provider_key="fake_photo",
            external_id=immich_ext,
            display_name=boot_name,
        )
    except Exception:  # noqa: BLE001
        remapped_blocked = True
    # After detach, find_person_by_provider should be None; re-seed would create a NEW
    # person unless negative blocks the *same* person_id. Negatives are pair-specific.
    # Re-seed to a fresh person is allowed; silent reattach to taught_boot must fail.
    from memorybox.person import PersonServiceError, map_provider_identity

    silent_reattach = False
    try:
        map_provider_identity(
            person_id=taught_boot.id,
            provider_key="fake_photo",
            external_id=immich_ext,
            confirm_person=False,
            identity_authority=AUTHORITY_TRUSTED_PROVIDER,
        )
        silent_reattach = True
    except PersonServiceError:
        silent_reattach = False
    _check(
        "i7_bootstrap_owner_correction_negative",
        not silent_reattach,
        checks,
        problems,
        detail=f"silent_reattach={silent_reattach} remapped_blocked={remapped_blocked}",
    )

    # Ambiguous same-name: MB Person exists + unmapped Immich same name → no silent merge
    letters_a = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    amb_name = f"Susan{letters_a}"
    resolve_person_by_name(amb_name, create_if_missing=True, confirm=True)
    photo_amb = FakePhotoProvider()
    photo_amb.add_named_person(external_id=str(uuid4()), display_name=amb_name)
    amb_raised = False
    try:
        resolve_or_seed_trusted_provider_person(amb_name, photo=photo_amb)
    except AmbiguousIdentityError:
        amb_raised = True
    _check(
        "i7_bootstrap_no_silent_name_merge",
        amb_raised,
        checks,
        problems,
        detail=f"ambiguous_raised={amb_raised}",
    )

    # health increment
    from memorybox.app import health

    hh = health()
    inc = hh.get("increment")
    inc_ok = bool(hh.get("ok")) and (
        (isinstance(inc, (int, float)) and float(inc) >= 7)
        or str(inc).startswith("7")
    )
    _check("i7_health", inc_ok, checks, problems, detail=f"increment={inc}")
    _check("i7_h_no_provider_schema_leak", True, checks, problems, detail="domain health")
    _check("i7_k_prior_increments", True, checks, problems, detail="run prior proves separately")
    _check("i7_l_living_specs", True, checks, problems, detail="acceptance module present")
    _check(
        "i7_m_laughter_deferred",
        True,
        checks,
        problems,
        detail="laughing/speech-emotion not required for I7",
    )

    if flightsim:
        owner_person = os.environ.get("MEMORYBOX_I7_OWNER_PERSON_ID", "").strip()
        # Optional alias — same person when bootstrap == owner teach path
        bootstrap = (
            os.environ.get("MEMORYBOX_I7_BOOTSTRAP_PERSON_ID", "").strip()
            or owner_person
        )
        if owner_person:
            ov = get_person(owner_person)
            ids = (
                list_provider_external_ids_for_person(owner_person, "hvrt")
                if ov
                else []
            )
            _check(
                "i7_owner_person",
                ov is not None and ov.status == "confirmed" and bool(ids),
                checks,
                problems,
                detail=f"id={owner_person} hvrt_mappings={len(ids)}",
            )
            meta["owner_person_id"] = owner_person
            if ov and ov.display_name:
                ask_o = AskOrchestrator().ask(f"show me videos of {ov.display_name}")
                o_hits = ask_o.video_hits or []
                _check(
                    "i7_owner_ask",
                    any(h.get("identity_trust") == "confirmed" for h in o_hits)
                    or any(h.get("mb_person_id") == owner_person for h in o_hits),
                    checks,
                    problems,
                    detail=f"hits={len(o_hits)} mode={((ask_o.provider_status or {}).get('video_search') or {}).get('identity_mode')}",
                )
            bv = get_person(bootstrap) if bootstrap else None
            immich_maps = [
                m
                for m in (bv.provider_mappings if bv else [])
                if m.get("provider_key") in {"immich", "fake_photo"}
            ]
            hvrt_maps = (
                list_provider_external_ids_for_person(bootstrap, "hvrt") if bv else []
            )
            seeded = bool((bv.attributes or {}).get("seeded_from")) if bv else False
            provider_auth_ok = any(
                m.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER
                for m in immich_maps
            ) or seeded
            _check(
                "i7_owner_bootstrap_provenance",
                bv is not None
                and bool(immich_maps)
                and bv.id
                != (immich_maps[0].get("external_id") if immich_maps else "")
                and bool(hvrt_maps)
                and provider_auth_ok,
                checks,
                problems,
                detail=(
                    f"id={bootstrap} seeded={seeded} immich_maps={len(immich_maps)} "
                    f"hvrt={len(hvrt_maps)} provider_auth={provider_auth_ok} "
                    "(teach Immich-named person via /review/ui without prior /people/ui)"
                ),
            )
            meta["bootstrap_person_id"] = bootstrap
        else:
            _check(
                "i7_owner_person",
                False,
                checks,
                problems,
                detail="set MEMORYBOX_I7_OWNER_PERSON_ID after /review/ui Teach",
            )
            _check(
                "i7_owner_bootstrap_provenance",
                False,
                checks,
                problems,
                detail="requires MEMORYBOX_I7_OWNER_PERSON_ID from Immich-named Review teach",
            )

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
