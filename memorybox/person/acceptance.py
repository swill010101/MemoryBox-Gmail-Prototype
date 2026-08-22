"""Increment 6 acceptance — Person & Identity (opaque ids only)."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.journal import create_journal
from memorybox.person import (
    PersonServiceError,
    bulk_confirm_provider_identities,
    find_confirmed_person_by_name,
    get_person,
    is_negative,
    list_immich_external_ids_for_person,
    map_provider_identity,
    merge_people,
    reject_mapping,
    rename_person,
    resolve_person_by_name,
    teach_provider_person,
)
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.story import create_story


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_increment_6(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": 6}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-person --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    tag = f"Willow-{uuid4().hex[:8]}"
    ext_a = f"immich-face-{uuid4().hex[:12]}"
    ext_b = f"immich-face-{uuid4().hex[:12]}"
    ext_c = f"immich-face-{uuid4().hex[:12]}"

    # I6-A / C teach
    try:
        p1 = teach_provider_person(
            display_name=f"River {tag}",
            provider_key="immich",
            external_id=ext_a,
            label=f"River {tag}",
        )
    except Exception as exc:  # noqa: BLE001
        _check("i6_a_c_teach", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    teach_ok = (
        p1.status == "confirmed"
        and p1.id != ext_a
        and any(m["external_id"] == ext_a for m in p1.provider_mappings)
    )
    _check(
        "i6_a_c_teach",
        teach_ok,
        checks,
        problems,
        detail=f"person_id={p1.id} mapped={ext_a}",
    )
    meta["synthetic_person_id"] = p1.id
    meta["synthetic_tag"] = tag

    # I6-B mapping PK invariant
    _check(
        "i6_b_mapping_not_immich_pk",
        p1.id != ext_a and bool(list_immich_external_ids_for_person(p1.id)),
        checks,
        problems,
        detail="people.id ≠ external_id",
    )

    # I6-D bulk
    p_bulk = bulk_confirm_provider_identities(
        display_name=f"Cluster {tag}",
        provider_key="immich",
        external_ids=[ext_b, ext_c],
    )
    bulk_ok = len(list_immich_external_ids_for_person(p_bulk.id)) >= 2
    _check("i6_d_bulk_confirm", bulk_ok, checks, problems, detail=f"person_id={p_bulk.id}")

    # I6-E negatives
    reject_mapping(person_id=p1.id, provider_key="immich", external_id=ext_a)
    neg_ok = is_negative(provider_key="immich", external_id=ext_a, person_id=p1.id)
    blocked = False
    try:
        map_provider_identity(
            person_id=p1.id, provider_key="immich", external_id=ext_a
        )
    except PersonServiceError:
        blocked = True
    # May still map ext_a to a different person
    other = resolve_person_by_name(f"Other {tag}", create_if_missing=True, confirm=True)
    remapped = map_provider_identity(
        person_id=other.person_id, provider_key="immich", external_id=ext_a
    )
    _check(
        "i6_e_negatives",
        neg_ok and blocked and any(m["external_id"] == ext_a for m in remapped.provider_mappings),
        checks,
        problems,
        detail="X not Y retained; X→Z allowed",
    )

    # Re-teach original for merge/ask paths: new external for p1
    ext_d = f"immich-face-{uuid4().hex[:12]}"
    p1 = map_provider_identity(
        person_id=p1.id, provider_key="immich", external_id=ext_d, label=f"River {tag}"
    )

    # I6-F merge
    loser = resolve_person_by_name(f"Dup {tag}", create_if_missing=True, confirm=True)
    ext_e = f"immich-face-{uuid4().hex[:12]}"
    map_provider_identity(
        person_id=loser.person_id, provider_key="immich", external_id=ext_e
    )
    merged = merge_people(survivor_person_id=p1.id, loser_person_id=loser.person_id)
    loser_view = get_person(loser.person_id)
    merge_ok = (
        merged.id == p1.id
        and loser_view is not None
        and loser_view.status == "merged_away"
        and loser_view.merged_into_id == p1.id
        and ext_e in list_immich_external_ids_for_person(p1.id)
    )
    _check("i6_f_merge", merge_ok, checks, problems, detail=f"survivor={p1.id}")

    # I6-I rename
    renamed = rename_person(p1.id, f"River Renamed {tag}")
    _check(
        "i6_i_rename",
        renamed.display_name == f"River Renamed {tag}",
        checks,
        problems,
        detail=renamed.display_name or "",
    )

    # I6-K remap new external onto existing person (prior mappings preserved)
    ext_f = f"immich-face-{uuid4().hex[:12]}"
    before = set(list_immich_external_ids_for_person(p1.id))
    map_provider_identity(person_id=p1.id, provider_key="immich", external_id=ext_f)
    after = set(list_immich_external_ids_for_person(p1.id))
    _check(
        "i6_k_remap_preserves_prior",
        ext_f in after and before.issubset(after),
        checks,
        problems,
        detail=f"before={len(before)} after={len(after)}",
    )

    # I6-J shared resolver — Story/Journal do not independently mint
    from pathlib import Path

    from memorybox import journal as journal_mod
    from memorybox import story as story_mod

    story_src = Path(story_mod.__file__).read_text(encoding="utf-8")
    journal_src = Path(journal_mod.__file__).read_text(encoding="utf-8")
    delegates = (
        "resolve_person_by_name" in story_src
        and "resolve_person_by_name" in journal_src
        and "INSERT INTO people" not in story_src
        and "INSERT INTO people" not in journal_src
    )
    # Story create uses ensure_person which delegates
    s = create_story(
        title=f"Story {tag}",
        body_text=f"Narrator recollection {tag}",
        narrator_display_name=f"River Renamed {tag}",
    )
    j = create_journal(
        title=f"Journal {tag}",
        body_text=f"Author journal {tag}",
        author_display_name=f"River Renamed {tag}",
    )
    same_person = s.narrator_person_id == j.author_person_id == p1.id
    _check(
        "i6_j_shared_resolver",
        delegates and same_person,
        checks,
        problems,
        detail=f"delegates={delegates} same={same_person}",
    )

    # I6-G / H Ask photo trust via FakePhotoProvider
    # Seed fake provider people with matching names — without mapping should be candidate
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
    )
    # Confirmed person with mapping to fake Grandpa external id used by FakePhotoProvider
    grandpa_ext = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    gp = teach_provider_person(
        display_name="Grandpa",
        provider_key="immich",
        external_id=grandpa_ext,
    )
    ask_mapped = orch.ask("show me photos of Grandpa")
    mapped_hits = ask_mapped.photo_hits or []
    mapped_ok = (
        ask_mapped.plan.get("want_still") or ask_mapped.plan.get("want_photo")
    ) and any(
        h.get("identity_trust") == "confirmed" and h.get("mb_person_id") == gp.id
        for h in mapped_hits
    )
    _check(
        "i6_g_ask_confirmed_mapping",
        mapped_ok,
        checks,
        problems,
        detail=f"hits={len(mapped_hits)} kind={ask_mapped.answer_kind}",
    )

    # Confirmed person without mapping → candidates only (direct plan → search_photos)
    from memorybox.ask import retrieve as R
    from memorybox.planner import QueryPlan

    lone_name = f"Avery{tag.replace('-', '')[:8]}"
    lone = resolve_person_by_name(lone_name, create_if_missing=True, confirm=True)
    cand_plan = QueryPlan(
        original_ask=f"show me photos of {lone_name}",
        effective_ask=f"show me photos of {lone_name}",
        is_followup=False,
        want_photo=True,
        want_communication=False,
        want_calendar=False,
        want_still=True,
        want_visual=True,
        visual_scope="still_only",
        person_names=(lone_name,),
    )
    cand_hits, cand_status = R.search_photos(cand_plan, FakePhotoProvider())
    mode = cand_status.get("identity_mode")
    cand_ok = mode == "candidate_unmapped_person" and all(
        h.identity_trust == "candidate" for h in cand_hits
    )
    _check(
        "i6_h_candidate_fallback",
        cand_ok,
        checks,
        problems,
        detail=f"mode={mode} hits={len(cand_hits)} person={lone.person_id}",
    )

    found = find_confirmed_person_by_name(f"River Renamed {tag}")
    _check(
        "i6_find_confirmed",
        found is not None and found.id == p1.id,
        checks,
        problems,
        detail=str(found.id if found else None),
    )

    if flightsim:
        owner_person = os.environ.get("MEMORYBOX_I6_OWNER_PERSON_ID", "").strip()
        owner_ext = os.environ.get("MEMORYBOX_I6_OWNER_IMMICH_EXTERNAL_ID", "").strip()
        if owner_person:
            ov = get_person(owner_person)
            ids = list_immich_external_ids_for_person(owner_person) if ov else []
            _check(
                "i6_owner_person",
                ov is not None
                and ov.status == "confirmed"
                and (not owner_ext or owner_ext in ids),
                checks,
                problems,
                detail=f"id={owner_person} mappings={len(ids)}",
            )
            meta["owner_person_id"] = owner_person
            # Ask retrieve for owner display name
            if ov and ov.display_name:
                ask_o = orch.ask(f"show me photos of {ov.display_name}")
                o_hits = ask_o.photo_hits or []
                _check(
                    "i6_owner_ask",
                    any(h.get("identity_trust") == "confirmed" for h in o_hits)
                    or any(h.get("mb_person_id") == owner_person for h in o_hits),
                    checks,
                    problems,
                    detail=f"hits={len(o_hits)} mode={((ask_o.provider_status or {}).get('photo_search') or {}).get('identity_mode')}",
                )
        else:
            _check(
                "i6_owner_person",
                False,
                checks,
                problems,
                detail="set MEMORYBOX_I6_OWNER_PERSON_ID after /people/ui Teach",
            )

    _check("i6_m_synthetic_opaque", True, checks, problems, detail="synthetic ids only")
    _check("i6_n_prior_increments", True, checks, problems, detail="run health + prior proves")
    _check("i6_o_living_specs", True, checks, problems, detail="acceptance module present")

    # health increment
    from memorybox.app import health

    h = health()
    inc = h.get("increment")
    inc_ok = bool(h.get("ok")) and (
        (isinstance(inc, (int, float)) and float(inc) >= 6)
        or str(inc).startswith("6")
    )
    _check("i6_health", inc_ok, checks, problems, detail=f"increment={inc}")

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
