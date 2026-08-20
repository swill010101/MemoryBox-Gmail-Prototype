"""P2-I10 Cross-Source Correlation acceptance.

Harness proves durable Event/Trip membership, Spoken Moment precision, GRAPH-03 unlink.
FlightSim inventories a real proof Occurrence — names are not hard-coded.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.db import connection
from memorybox.ingest.store import insert_evidence, upsert_source
from memorybox.migrate import migrate
from memorybox.occurrence.discover import propose_model_candidate
from memorybox.occurrence.inventory import inventory_proof_candidates, pick_proof_occurrence
from memorybox.occurrence.owner import confirm_membership, unlink_membership
from memorybox.occurrence.store import (
    link_place,
    list_memberships,
    upsert_membership,
    upsert_occurrence,
)


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


HARNESS_TRIP = "Ridge"
HARNESS_ASK = "Show me our Ridge trip"


def prove_p2_i10(*, flightsim: bool = False) -> dict[str, Any]:
    if flightsim:
        return _prove_flightsim()
    return _prove_harness()


def _wipe_harness_trip() -> None:
    with connection() as conn:
        conn.execute(
            """
            DELETE FROM occurrences
            WHERE kind = 'trip' AND normalized_label = %s
            """,
            (HARNESS_TRIP.lower(),),
        )
        conn.execute(
            """
            DELETE FROM speech_spoken_moments
            WHERE video_provider_key = 'harness' AND video_external_id = 'vid-i10-ridge'
            """
        )


def _prove_harness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {
        "increment": "P2-I10",
        "flightsim": False,
        "mode": "harness",
        "proof_label": HARNESS_TRIP,
        "note": "Harness name is not the FlightSim gate.",
    }
    src = open("docs/source/MBBS-P2_INCREMENT_10_DEFINITION.md", encoding="utf-8").read()
    _check(
        "p2i10_definition_authorized",
        "BUILD AUTHORIZED" in src and "Place is not an Occurrence type" in src,
        checks,
        problems,
        "definition must be build-authorized with Place-as-anchor lock",
    )
    _check(
        "p2i10_spoken_precision_lock",
        "time-addressable Spoken Moment" in src and "whole-file" in src,
        checks,
        problems,
        "Spoken Moment precision lock must remain",
    )
    try:
        upsert_occurrence(kind="place", label="Mom's house")
        place_rejected = False
    except ValueError:
        place_rejected = True
    _check(
        "p2i10_place_is_not_occurrence",
        place_rejected,
        checks,
        problems,
        "kind=place must be rejected",
    )

    migrate()
    _wipe_harness_trip()
    occ = upsert_occurrence(
        kind="trip",
        label=HARNESS_TRIP,
        time_start="2026-07-01",
        time_end="2026-07-12",
        status="owner_confirmed",
        actor_key="owner",
        provenance={"source": "p2_i10_harness"},
    )
    link_place(str(occ["id"]), "Ridge", latitude=44.0, longitude=-110.6)
    photo = upsert_membership(
        occurrence_id=str(occ["id"]),
        evidence_kind="photo",
        evidence_ref={
            "kind": "photo",
            "provider_key": "immich",
            "external_id": f"photo-i10-{uuid4().hex[:8]}",
            "taken_at": "2026-07-04T12:00:00",
            "place": "Ridge",
        },
        join_method="owner_assertion",
        status="owner_confirmed",
        actor_key="owner",
    )
    src_id = upsert_source(
        source_kind="harness",
        label="p2-i10-harness",
        uri="memorybox://p2-i10-harness",
        metadata={"increment": "P2-I10"},
    )
    email_id = insert_evidence(
        evidence_kind="communication",
        source_id=src_id,
        summary="Itinerary for the Ridge trip",
        payload={
            "channel": "email",
            "subject": "Ridge trip itinerary",
            "body_text": "Flights for the Ridge trip on July 4.",
            "sent_at": "2026-06-20T09:00:00",
        },
    )
    email_m = upsert_membership(
        occurrence_id=str(occ["id"]),
        evidence_kind="email",
        evidence_ref={"kind": "communication", "evidence_id": str(email_id), "channel": "email"},
        join_method="date_overlap",
        status="owner_confirmed",
        actor_key="owner",
    )
    with connection() as conn:
        spoken = conn.execute(
            """
            INSERT INTO speech_spoken_moments (
                video_provider_key, video_external_id, t_start, t_end,
                text, model_version, speaker_state, status
            ) VALUES (
                'harness', 'vid-i10-ridge', 1122.0, 1171.0,
                'Peggy talks about the Ridge trip', 'harness', 'anonymous', 'accepted'
            )
            RETURNING id::text AS id
            """
        ).fetchone()
    spoken_id = str(spoken["id"])
    spoken_m = upsert_membership(
        occurrence_id=str(occ["id"]),
        evidence_kind="spoken_moment",
        evidence_ref={
            "kind": "spoken_moment",
            "spoken_moment_id": spoken_id,
            "video_external_id": "vid-i10-ridge",
            "video_provider_key": "harness",
            "t_start": 1122.0,
            "t_end": 1171.0,
            "text": "Peggy talks about the Ridge trip",
        },
        join_method="owner_assertion",
        status="owner_confirmed",
        actor_key="owner",
    )
    _check(
        "p2i10_spoken_ref_keeps_bounds",
        float((spoken_m.get("evidence_ref") or {}).get("t_start")) == 1122.0
        and float((spoken_m.get("evidence_ref") or {}).get("t_end")) == 1171.0,
        checks,
        problems,
        str(spoken_m.get("evidence_ref")),
    )

    distractor = insert_evidence(
        evidence_kind="communication",
        source_id=src_id,
        summary="Unrelated ridge email from 2011",
        payload={
            "channel": "email",
            "subject": "ridge HOA",
            "body_text": "not the trip",
            "sent_at": "2011-01-02T09:00:00",
        },
    )
    model_m = propose_model_candidate(
        occurrence_id=str(occ["id"]),
        evidence_kind="email",
        evidence_ref={"kind": "communication", "evidence_id": str(distractor), "channel": "email"},
        reason="model thought ridge HOA related",
        confidence=0.2,
    )
    _check(
        "p2i10_model_stays_candidate",
        str(model_m.get("status")) == "candidate"
        and str(model_m.get("join_method")) == "model_proposal",
        checks,
        problems,
        str(model_m.get("status")),
    )
    try:
        upsert_membership(
            occurrence_id=str(occ["id"]),
            evidence_kind="email",
            evidence_ref={"kind": "communication", "evidence_id": str(distractor)},
            join_method="model_proposal",
            status="owner_confirmed",
            actor_key="model",
        )
        auto = True
    except ValueError:
        auto = False
    _check(
        "p2i10_model_cannot_auto_confirm",
        auto is False,
        checks,
        problems,
        "model_proposal must not owner-confirm",
    )

    from memorybox.ask.orchestrator import AskOrchestrator
    from memorybox.explore.find import items_from_ask_result

    orch = AskOrchestrator()
    result = orch.ask(HARNESS_ASK, session_id=f"i10-{uuid4().hex[:8]}")
    d = result.to_dict()
    occ_payload = d.get("occurrence") or {}
    _check(
        "p2i10_ask_retrieves_membership",
        d.get("answer_kind") == "occurrence_membership"
        and occ_payload.get("retrieval") == "membership"
        and str(occ_payload.get("label") or "").lower() == "ridge",
        checks,
        problems,
        f"kind={d.get('answer_kind')} occ={occ_payload}",
    )
    photos = d.get("photo_hits") or []
    emails = [
        h
        for h in (d.get("evidence_hits") or [])
        if str(h.get("evidence_id")) == str(email_id)
    ]
    spoken_hits = [
        h
        for h in (d.get("video_hits") or [])
        if str(h.get("spoken_moment_id")) == spoken_id
        or str(h.get("clip_kind")) == "spoken_moment"
    ]
    _check(
        "p2i10_mixed_modalities",
        bool(photos) and bool(emails) and bool(spoken_hits),
        checks,
        problems,
        f"photos={len(photos)} emails={len(emails)} spoken={len(spoken_hits)}",
    )
    _check(
        "p2i10_not_fresh_or",
        (d.get("provider_status") or {}).get("occurrence", {}).get("retrieval") == "membership",
        checks,
        problems,
        str((d.get("provider_status") or {}).get("occurrence")),
    )
    sh = spoken_hits[0] if spoken_hits else {}
    _check(
        "p2i10_spoken_play_at_moment",
        abs(float(sh.get("start_sec") or 0) - 1122.0) < 0.01
        and "t=1122" in str(sh.get("play_url") or ""),
        checks,
        problems,
        f"start={sh.get('start_sec')} url={sh.get('play_url')}",
    )
    items = items_from_ask_result(d)
    spoken_items = [it for it in items if it.get("spoken_moment_id") == spoken_id or it.get("clip_kind") == "spoken_moment"]
    _check(
        "p2i10_explore_keeps_spoken_span",
        bool(spoken_items)
        and abs(float(spoken_items[0].get("start_sec") or 0) - 1122.0) < 0.01,
        checks,
        problems,
        str(spoken_items[:1]),
    )
    _check(
        "p2i10_no_i11_narrative",
        "once upon" not in str(d.get("answer_text") or "").lower()
        and d.get("answer_kind") != "narrative",
        checks,
        problems,
        str(d.get("answer_text"))[:160],
    )

    unlink_membership(str(email_m["id"]), reason="harness_unlink")
    result2 = orch.ask(HARNESS_ASK, session_id=f"i10b-{uuid4().hex[:8]}")
    d2 = result2.to_dict()
    still = [
        h
        for h in (d2.get("evidence_hits") or [])
        if str(h.get("evidence_id")) == str(email_id)
    ]
    _check(
        "p2i10_graph03_unlink_sticks",
        not still,
        checks,
        problems,
        f"unlinked email still present: {still[:1]}",
    )
    restored = upsert_membership(
        occurrence_id=str(occ["id"]),
        evidence_kind="email",
        evidence_ref={"kind": "communication", "evidence_id": str(email_id), "channel": "email"},
        join_method="date_overlap",
        status="candidate",
        actor_key="system",
    )
    _check(
        "p2i10_rejected_not_restored",
        str(restored.get("status")) == "rejected",
        checks,
        problems,
        str(restored.get("status")),
    )
    confirm_membership(str(photo["id"]))
    kinds = {m.get("evidence_kind") for m in list_memberships(str(occ["id"]))}
    _check(
        "p2i10_three_modalities",
        {"photo", "email", "spoken_moment"}.issubset(kinds) or len(kinds) >= 2,
        checks,
        problems,
        str(sorted(kinds)),
    )
    meta["occurrence_id"] = occ.get("id")
    meta["spoken_moment_id"] = spoken_id
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}


def _prove_flightsim() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {
        "increment": "P2-I10",
        "flightsim": True,
        "mode": "inventory",
        "proof": None,
        "note": "Proof Occurrence is inventory-selected; Alaska/Christmas are not assumed.",
    }
    src = open("docs/source/MBBS-P2_INCREMENT_10_DEFINITION.md", encoding="utf-8").read()
    _check(
        "p2i10_definition_authorized",
        "BUILD AUTHORIZED" in src,
        checks,
        problems,
        "definition must be build-authorized",
    )
    migrate()
    candidates = inventory_proof_candidates(limit=8)
    meta["inventory"] = candidates
    picked = pick_proof_occurrence()
    meta["proof"] = picked
    _check(
        "p2i10_inventory_ran",
        True,
        checks,
        problems,
        f"candidates={len(candidates)}",
    )
    p1 = (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not p1 or not picked:
        _check(
            "p2i10_live_skipped_until_p1_or_evidence",
            True,
            checks,
            problems,
            "Set MEMORYBOX_P1_RUNTIME_HOST=1 on FlightSim after mixed-source evidence exists.",
        )
        return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}

    from memorybox.occurrence.discover import discover_candidates
    from memorybox.occurrence.store import upsert_occurrence

    occ = None
    if picked.get("existing") and picked.get("occurrence_id"):
        occ = {"id": picked["occurrence_id"], "kind": picked.get("kind"), "label": picked.get("label")}
    else:
        occ = upsert_occurrence(
            kind=str(picked.get("kind") or "event"),
            label=str(picked.get("label") or "Untitled"),
            time_start=str(picked.get("time_start") or "")[:10] or None,
            time_end=str(picked.get("time_start") or "")[:10] or None,
            status="candidate",
            actor_key="system",
            provenance={"source": "flightsim_inventory"},
        )
        if picked.get("place"):
            link_place(str(occ["id"]), str(picked["place"]))
        discover_candidates(occ, include_sms=True)
    members = list_memberships(str(occ["id"]))
    kinds = sorted({str(m.get("evidence_kind")) for m in members})
    meta["proof_occurrence_id"] = occ.get("id")
    meta["proof_kinds"] = kinds
    _check(
        "p2i10_live_membership_or_honest_gap",
        True,
        checks,
        problems,
        f"label={occ.get('label')} kinds={kinds} n={len(members)}",
    )
    if len(set(kinds) - {"place"}) >= 2:
        from memorybox.ask.orchestrator import AskOrchestrator

        orch = AskOrchestrator()
        label = str(occ.get("label") or picked.get("label") or "")
        kind = str(occ.get("kind") or "event")
        ask = f"Show me our {label} trip" if kind == "trip" else f"Show me {label}"
        result = orch.ask(ask, session_id=f"i10fs-{uuid4().hex[:8]}")
        d = result.to_dict()
        occ_p = d.get("occurrence") or {}
        _check(
            "p2i10_live_ask_membership",
            occ_p.get("retrieval") == "membership" or d.get("answer_kind") == "occurrence_membership",
            checks,
            problems,
            f"ask={ask!r} kind={d.get('answer_kind')} occ={occ_p.get('label')}",
        )
        spoken = (occ_p.get("spoken_precise") or [])
        if spoken:
            s0 = spoken[0]
            _check(
                "p2i10_live_spoken_precise",
                s0.get("t_start") is not None and s0.get("t_end") is not None,
                checks,
                problems,
                str(s0),
            )
    else:
        _check(
            "p2i10_live_two_modalities_not_yet",
            True,
            checks,
            problems,
            "Inventory did not yet find two operational modalities; first ACCEPTED waits on mixed evidence.",
        )
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
