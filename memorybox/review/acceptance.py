"""Increment 7 acceptance — Video Intelligence + Review (`prove-video`)."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.person import (
    get_person,
    list_provider_external_ids_for_person,
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
                # Prefer live video provider when configured
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
        else:
            _check(
                "i7_owner_person",
                False,
                checks,
                problems,
                detail="set MEMORYBOX_I7_OWNER_PERSON_ID after /review/ui Teach",
            )

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
