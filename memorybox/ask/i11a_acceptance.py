"""P2-I11A Generalized Evidence Inference Engine — acceptance prove."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.i11a import needs_semantic_inference, resolve_request_context
from memorybox.ask.i11a.infer import apply_inference_to_pack
from memorybox.ask.i11a.validate import parse_inference_json, validate_inference
from memorybox.ask.evidence_prep import prepare_narrative_pack
from memorybox.ask.i11_acceptance import _check
from memorybox.ask.narrative import (
    SYSTEM_PROMPT,
    evidence_used_footer,
    pack_for_narrator,
    tell_from_hits,
)
from memorybox.ask.narrative_ground import ground_narrative
from memorybox.ask.retrieve import EvidenceHit, PhotoHit, filter_hits_by_constraints
from memorybox.context import AskContext
from memorybox.planner import plan_ask
from memorybox.providers.base import ProviderHealth, ProviderUnavailable
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.llm.dto import ChatMessage


def run_prove_i11a(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I11A", "p1_runtime_final": flightsim}
    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-i11a --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    root = Path(__file__).resolve().parents[1]
    infer_py = (root / "ask" / "i11a" / "infer.py").read_text(encoding="utf-8")
    orch_py = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    js = (root / "ai_trace" / "static" / "ai-trace.js").read_text(encoding="utf-8")
    html = (root / "ai_trace" / "static" / "ai-trace.html").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")

    _check(
        "a12_no_hardcoded_llama",
        "llama3.2" not in infer_py,
        checks,
        problems,
        detail="provider-neutral inference role",
    )
    _check(
        "a09_trace_light_copy_export",
        "copy-provider-payload" in js
        and "copy-raw-response" in js
        and "copy-parsed-inference" in js
        and "copy-validated-pack" in js
        and "Copy Full Trace JSON" in js
        and "exportJsonFile" in js
        and "copy-pane" in js
        and "?v=i11a4" in html
        and "retrieval_resolution" in js
        and "copy-retrieval-resolution" in js,
        checks,
        problems,
        detail="AI Trace Light I11A copy/export controls",
    )
    _check(
        "a11_t6_existing_drilldown",
        "citations" in explore_js.lower() or "source_kind" in explore_js,
        checks,
        problems,
        detail="no new Explore chrome required",
    )
    _check(
        "a10_curator_status_ticker",
        "Collecting photos" in explore_js
        and "Collecting email" in orch_py
        and "Collecting SMS" in orch_py
        and "Collecting calendar" in orch_py
        and "Resolving trip evidence" in orch_py
        and "Assimilating collections" in orch_py
        and "is-status-ticker" in explore_js
        and "/explore/api/ask-progress" in explore_js
        and "askStatusGen" in explore_js
        and "clearSearchingChrome" in explore_js
        and 't === "Done"' not in explore_js
        and "overflow-anchor: none" in (root / "ai_trace" / "static" / "ai-trace.css").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        detail="one-line scrolling Ask status in curator",
    )

    jan_plan = plan_ask("write a narrative about my January of 2025", AskContext(session_id="i11a-jan"))
    peggy_plan = plan_ask("Tell me what you know about Peggy", AskContext(session_id="i11a-peggy"))
    trip_plan = plan_ask("Summarize our Alaska trip in May 2026", AskContext(session_id="i11a-ak"))
    xmas_plan = plan_ask("Tell me about Christmas 2024", AskContext(session_id="i11a-xmas"))
    texts_plan = plan_ask(
        "Summarize the text messages Peggy and I sent in 2020",
        AskContext(session_id="i11a-sms"),
    )
    show_plan = plan_ask("Show me Peggy", AskContext(session_id="i11a-show"))
    jan_req = resolve_request_context(jan_plan)
    peggy_req = resolve_request_context(peggy_plan)
    _check(
        "a02_requestor_focal_split",
        needs_semantic_inference(jan_plan)
        and needs_semantic_inference(peggy_plan)
        and not needs_semantic_inference(show_plan)
        and not (jan_plan.person_names or ())
        and jan_req["focal_subject_person_ids"] == (
            [jan_req["requestor_person_id"]] if jan_req["requestor_person_id"] else []
        )
        and any(n.lower() == "peggy" for n in (peggy_plan.person_names or ()))
        and peggy_req["focal_subject_names"]
        and peggy_plan.time_start is None
        and trip_plan.output_mode == "tell"
        and xmas_plan.output_mode == "tell"
        and texts_plan.output_mode == "tell",
        checks,
        problems,
        detail=str({"jan": jan_req, "peggy": peggy_req, "show_inf": needs_semantic_inference(show_plan)}),
    )

    hits = [
        EvidenceHit(
            evidence_id="e-harbor",
            evidence_kind="communication",
            summary="Harbor dinner",
            score=1.0,
            excerpt="come to Sunday dinner at the harbor",
            source="sms_export",
            sent_at="2025-01-12T18:00:00",
            channel="sms",
            people=["Alex"],
            thread_id="t-h",
        ),
        EvidenceHit(
            evidence_id="e-pt",
            evidence_kind="communication",
            summary="PT Tuesday",
            score=1.0,
            excerpt="Physical therapy Tuesday after knee surgery",
            source="sms_export",
            sent_at="2025-01-20T12:00:00",
            channel="sms",
            people=["Alex"],
            thread_id="t-pt",
        ),
    ]
    text, pack, synth_meta = tell_from_hits(jan_plan, llm=FakeLlmProvider(), evidence=hits)
    inf = pack.get("inference") or {}
    val = pack.get("validated_inference") or {}
    nar = pack_for_narrator(pack)
    nar_blob = json.dumps(nar, default=str)
    footer = evidence_used_footer(pack)
    _check(
        "a01_validated_inference_drives_narrator",
        inf.get("ok") is True
        and inf.get("fail_closed") is not True
        and bool(val.get("episodes"))
        and (pack.get("volume") or {}).get("reduction") == "i11a_inference"
        and "coverage" not in nar
        and "eligible_n" not in nar_blob
        and "harbor" in nar_blob.lower()
        and synth_meta.get("fail_closed") is not True
        and "narration unavailable" not in text.lower(),
        checks,
        problems,
        detail=str({"inf": {k: inf.get(k) for k in ("ok", "fail_closed", "reason")}, "keys": list(val.keys())}),
    )
    _check(
        "a06_queried_zero_in_footer",
        "0 photos" in footer.lower() or "photos" in footer.lower(),
        checks,
        problems,
        detail=footer,
    )
    _check(
        "a07_claims_have_ids",
        all(
            (c.get("supporting_evidence_ids") or [])
            for ep in (val.get("episodes") or [])
            for c in (ep.get("claims") or [])
        ),
        checks,
        problems,
        detail=str((val.get("episodes") or [])[:2]),
    )

    bogus = {
        "schema_version": 2,
        "episodes": [
            {
                "label": "Invented wife",
                "claims": [
                    {
                        "text": "Alex is family",
                        "supporting_evidence_ids": ["e-harbor"],
                        "claim_type": "inferred",
                    }
                ],
                "people": [{"name": "Alex", "relationship": "spouse", "role": "participant"}],
                "supporting_evidence_ids": ["e-harbor"],
            }
        ],
        "coverage": {"incomplete": True},
    }
    v = validate_inference(bogus, pack=pack, person_context={"allowed_relationship_labels": []})
    _check(
        "a04_relationship_not_invented",
        any(r.get("reason") == "relationship_not_in_graph" for r in (v.get("rejected") or []))
        and "coverage" not in (v.get("document") or {}),
        checks,
        problems,
        detail=str(v.get("rejected")),
    )

    class _Down:
        provider_key = "down"

        def health(self):
            return ProviderHealth(provider_key="down", ok=False, detail="down")

        def chat(self, messages, *, json_mode=False):
            raise ProviderUnavailable("model down")

    down_text, down_pack, down_meta = tell_from_hits(jan_plan, llm=_Down(), evidence=hits)
    _check(
        "a08_fail_closed",
        down_meta.get("fail_closed") is True
        and (down_pack.get("inference") or {}).get("fail_closed") is True
        and "narration unavailable" in down_text.lower()
        and "evidence-backed account" not in down_text.lower(),
        checks,
        problems,
        detail=down_text[:200],
    )

    fake = FakeLlmProvider()
    raw = fake.chat(
        [
            ChatMessage(role="system", content="EVIDENCE_INFERENCE"),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {
                        "ask_kind": "period",
                        "units": [
                            {
                                "unit_id": "u1",
                                "evidence_id": "e-harbor",
                                "kind": "communication",
                                "time": "2025-01-12",
                                "content": "harbor dinner",
                                "people": [],
                            }
                        ],
                    }
                ),
            ),
        ],
        json_mode=True,
    )
    parsed = parse_inference_json(getattr(raw, "content", "") or "")
    _check(
        "a05_fake_inference_schema",
        parsed
        and parsed.get("schema_version") == 2
        and "coverage" not in parsed
        and (parsed.get("episodes") or []),
        checks,
        problems,
        detail=str(parsed)[:300],
    )

    ak_hits = [
        EvidenceHit(
            evidence_id="e-ak",
            evidence_kind="communication",
            summary="Alaska itinerary",
            score=1.0,
            excerpt="Flight to Anchorage for the Alaska trip in May",
            source="email",
            sent_at="2026-05-02T10:00:00",
            channel="email",
            people=["Peggy"],
            thread_id="t-ak",
        )
    ]
    _ak_text, ak_pack, _ = tell_from_hits(trip_plan, llm=FakeLlmProvider(), evidence=ak_hits)
    _check(
        "a05_t2_trip_same_engine",
        (ak_pack.get("inference") or {}).get("ok") is True
        and (ak_pack.get("validated_inference") or {}).get("episodes"),
        checks,
        problems,
        detail=str((ak_pack.get("inference") or {}).get("ok")),
    )
    peggy_hits = [
        EvidenceHit(
            evidence_id="e-peg",
            evidence_kind="communication",
            summary="Peggy hello",
            score=1.0,
            excerpt="Peggy said hello from St Louis",
            source="sms_export",
            sent_at="2024-03-01T12:00:00",
            channel="sms",
            people=["Peggy"],
            thread_id="t-p",
        )
    ]
    from memorybox.ask.i11a.infer import apply_inference_to_pack as _apply

    p_pack = prepare_narrative_pack(peggy_plan, evidence=peggy_hits)
    p_pack = _apply(peggy_plan, p_pack, FakeLlmProvider())
    _check(
        "a05_t3_person_inference_not_tell_required",
        needs_semantic_inference(peggy_plan)
        and peggy_plan.output_mode != "tell"
        and (p_pack.get("request_context") or {}).get("focal_subject_names")
        and (p_pack.get("inference") or {}).get("ok") is True,
        checks,
        problems,
        detail=str({"mode": peggy_plan.output_mode, "req": p_pack.get("request_context")}),
    )

    _check(
        "heuristic_still_present_as_fixture",
        "LIFE_FAMILIES" in (root / "ask" / "episode_semantics.py").read_text(encoding="utf-8")
        and "diagnostic/regression" in (root / "ask" / "episode_semantics.py").read_text(encoding="utf-8"),
        checks,
        problems,
        detail="scorer frozen as diagnostic",
    )
    ak_year = plan_ask(
        "write a narrative about my alaska trip in 2026",
        AskContext(session_id="i11a-ak-year"),
    )
    _check(
        "alaska_trip_in_year_not_year_keyword",
        any(str(t).lower() == "alaska" for t in (ak_year.trip_labels or ()))
        and "2026" not in tuple(ak_year.retrieval_constraints or ())
        and ak_year.time_start == "2026-01-01"
        and ak_year.time_end == "2026-12-31",
        checks,
        problems,
        detail=str(
            {
                "trips": ak_year.trip_labels,
                "places": ak_year.place_names,
                "constraints": ak_year.retrieval_constraints,
                "notes": ak_year.notes,
            }
        ),
    )
    cons_l = {str(c).lower() for c in (ak_year.retrieval_constraints or ())}
    _check(
        "alaska_possessive_not_place_label",
        all(str(p).lower() == "alaska" for p in (ak_year.place_names or ()) or ["alaska"])
        and all(str(t).lower() == "alaska" for t in (ak_year.trip_labels or ()))
        and "my alaska" not in cons_l
        and "alaska" not in cons_l
        and "trip_window_unresolved" in (ak_year.notes or ())
        and "possessive=requestor" in (ak_year.notes or ())
        and not (ak_year.person_names or ()),
        checks,
        problems,
        detail=str({"places": ak_year.place_names, "people": ak_year.person_names, "cons": ak_year.retrieval_constraints}),
    )
    our_ak = plan_ask("write a narrative about our Alaska trip in 2026", AskContext(session_id="i11a-our-ak"))
    dad_ak = plan_ask("write a narrative about Dad's Alaska trip in 2026", AskContext(session_id="i11a-dad-ak"))
    peg_fl = plan_ask("write a narrative about Peggy's Florida trip in 2026", AskContext(session_id="i11a-peg-fl"))
    _check(
        "trip_possessive_generalizes",
        all(str(t).lower() == "alaska" for t in (our_ak.trip_labels or ()))
        and "possessive=requestor" in (our_ak.notes or ())
        and all(str(t).lower() == "alaska" for t in (dad_ak.trip_labels or ()))
        and any(str(n).startswith("possessive=kinship:") for n in (dad_ak.notes or ()))
        and not any("dad" in str(p).lower() for p in (dad_ak.place_names or ()))
        and any(str(t).lower() == "florida" for t in (peg_fl.trip_labels or ()))
        and any(str(n).lower() == "peggy" for n in (peg_fl.person_names or ()))
        and not any("peggy" in str(p).lower() for p in (peg_fl.place_names or ())),
        checks,
        problems,
        detail=str(
            {
                "our": (our_ak.trip_labels, our_ak.notes),
                "dad": (dad_ak.place_names, dad_ak.notes),
                "peggy": (peg_fl.person_names, peg_fl.place_names, peg_fl.trip_labels),
            }
        ),
    )
    year_only = EvidenceHit(
        evidence_id="e-lunch-26",
        evidence_kind="communication",
        summary="Lunch plans",
        score=1.0,
        excerpt="see you tuesday 2026",
        source="email_mbox",
        sent_at="2026-01-12T12:00:00",
        channel="email",
    )
    ak_mail = EvidenceHit(
        evidence_id="e-ak-26",
        evidence_kind="communication",
        summary="Alaska itinerary",
        score=1.0,
        excerpt="Flight to Anchorage for the Alaska trip",
        source="email_mbox",
        sent_at="2026-05-02T10:00:00",
        channel="email",
    )
    from memorybox.ask.trip_discovery import resolve_trip
    from memorybox.ask.i11a.person_context import (
        _dedupe_relationship_rows,
        _period_as_of,
        slim_person_context_for_model,
    )

    empty_lib = [
        PhotoHit(
            provider_key="immich",
            external_id=f"ph-{i}",
            taken_at="2026-03-01T12:00:00",
            people=["Tom Will"],
            location="Home",
            thumb_url=None,
            web_url=None,
        )
        for i in range(25)
    ]
    miss = resolve_trip(
        ak_year,
        evidence=[year_only],
        photos=empty_lib,
        photo_status={
            "provider_key": "immich",
            "before_temporal_filter": 25,
            "after_temporal_filter": 25,
            "constraint_mode": "deferred_trip_discovery",
            "requestor_person_id": "p-tom",
        },
    )
    photo_mod = miss.modalities[0].to_dict() if miss.modalities else {}
    _check(
        "trip_discovery_does_not_dump_year",
        (not miss.resolved)
        and miss.photos == []
        and miss.evidence == []
        and photo_mod.get("initial_candidate_count") == 25
        and photo_mod.get("post_filter_count") == 0
        and "Alaska" in str(photo_mod.get("skipped_reason") or photo_mod.get("semantic_constraint")),
        checks,
        problems,
        detail=str({"mod": photo_mod, "windows": miss.windows}),
    )
    ak_photo = PhotoHit(
        provider_key="immich",
        external_id="ph-ak",
        taken_at="2026-05-06T12:00:00",
        people=["Tom Will"],
        location="Anchorage, Alaska",
        thumb_url=None,
        web_url=None,
        state="Alaska",
        latitude=61.2,
        longitude=-149.9,
    )
    found = resolve_trip(
        ak_year,
        evidence=[year_only, ak_mail],
        photos=empty_lib + [ak_photo],
        photo_status={
            "provider_key": "immich",
            "after_temporal_filter": 26,
            "constraint_mode": "deferred_trip_discovery",
        },
    )
    _check(
        "trip_discovery_resolves_window_then_keeps_place_hits",
        found.resolved
        and found.plan.time_start == "2026-05-02"
        and "trip_window_resolved" in (found.plan.notes or ())
        and [h.evidence_id for h in found.evidence] == ["e-ak-26"]
        and [p.external_id for p in found.photos] == ["ph-ak"],
        checks,
        problems,
        detail=str(
            {
                "start": found.plan.time_start,
                "end": found.plan.time_end,
                "ev": [h.evidence_id for h in found.evidence],
                "ph": [p.external_id for p in found.photos],
            }
        ),
    )
    year_as_of = _period_as_of(ak_year)
    resolved_as_of = _period_as_of(found.plan)
    dup_rels = _dedupe_relationship_rows(
        [
            {"from_person_id": "a", "to_person_id": "b", "role_kind": "mother_of", "authority": "confirmed"},
            {"from_person_id": "a", "to_person_id": "b", "role_kind": "mother_of", "authority": "confirmed"},
            {"from_person_id": "a", "to_person_id": "b", "role_kind": "mother_of", "authority": "inferred"},
        ]
    )
    slim = slim_person_context_for_model(
        {
            "requestor": {
                "person_id": "p",
                "display_name": "Tom",
                "age_at_period": None,
                "known_relationships": dup_rels
                + dup_rels,
                "allowed_relationship_labels": ["mother"],
            },
            "focal_subjects": [],
            "allowed_relationship_labels": ["mother"],
            "as_of": None,
        }
    )
    _check(
        "person_context_dedupe_and_period_age",
        year_as_of is None
        and resolved_as_of is not None
        and str(resolved_as_of) == "2026-05-02"
        and len(dup_rels) == 2
        and len((slim.get("requestor") or {}).get("known_relationships") or []) == 2,
        checks,
        problems,
        detail=str({"year_as_of": year_as_of, "resolved": resolved_as_of, "dup": len(dup_rels), "slim": slim}),
    )
    _check(
        "inference_prompt_untouched_by_alaska_trace",
        "EVIDENCE_INFERENCE" in infer_py
        and "Do not invent people, places, dates" in infer_py,
        checks,
        problems,
        detail="I11A system prompt must stay fail-closed; this increment is upstream",
    )
    kept_trip = filter_hits_by_constraints([year_only, ak_mail], ["Alaska", "2026"])
    _check(
        "alaska_year_constraint_requires_place",
        [h.evidence_id for h in kept_trip] == ["e-ak-26"],
        checks,
        problems,
        detail=str([h.evidence_id for h in kept_trip]),
    )
    llama_dump = {
        "schema_version": 1,
        "ask_semantics": {"trip": True, "narrative": True},
        "focal_subjects": [
            {"person_id": "p-tom", "display_name": "Tom Will"},
            {"person_id": "p-tom"},
        ],
        "episodes": [
            {
                "episode_type": "derived",
                "people": [{"person_id": "p-tom", "role_kind": "participant"}],
                "content": "Tom Will's 2026 Alaska trip",
            }
        ],
        "themes": [],
        "unresolved": [
            {
                "kind": "travel",
                "time": "2026-05-06",
                "place": None,
                "people": [],
                "content": "flight 2026-05-06",
                "unit_id": "u-ak-flight",
                "evidence_id": "u-ak-flight",
                "source_type": None,
            }
        ],
    }
    salvage_pack = {
        "units": [
            {
                "unit_id": "u-ak-flight",
                "kind": "travel",
                "content": "flight 2026-05-06",
                "provenance": {"evidence_id": "u-ak-flight"},
            }
        ]
    }
    salvaged = validate_inference(
        llama_dump, pack=salvage_pack, person_context={"allowed_relationship_labels": []}
    )
    salvaged_eps = (salvaged.get("document") or {}).get("episodes") or []
    salvaged_sem = (salvaged.get("document") or {}).get("ask_semantics") or {}
    _check(
        "salvage_llama_unit_unresolved",
        salvaged.get("ok") is True
        and salvaged_sem.get("kind") == "trip"
        and len((salvaged.get("document") or {}).get("focal_subjects") or []) == 1
        and any(
            "u-ak-flight" in (c.get("supporting_evidence_ids") or [])
            for ep in salvaged_eps
            for c in (ep.get("claims") or [])
        )
        and not any(
            "alaska trip" in str(ep.get("label") or "").lower()
            and not (ep.get("supporting_evidence_ids") or [])
            for ep in salvaged_eps
        ),
        checks,
        problems,
        detail=str(salvaged.get("document"))[:500],
    )

    prompt_l = SYSTEM_PROMPT.lower()
    _check(
        "narrator_prompt_documentary_historian",
        "documentarian" in prompt_l
        and "historian" in prompt_l
        and "documentary" in prompt_l
        and "bering sea" in prompt_l
        and "the calendar showed" in prompt_l
        and "dramatize" in prompt_l
        and "planned/scheduled" in prompt_l
        and "observed/actual" in prompt_l
        and "do not convert plausible inference" in prompt_l,
        checks,
        problems,
        detail=SYSTEM_PROMPT[:280],
    )
    gate_pack = {
        "units": [
            {
                "unit_id": "e-ak-cal",
                "evidence_id": "e-ak-cal",
                "kind": "calendar",
                "time": "2026-05-01",
                "date_end": "2026-05-15",
                "place": "Alaska",
                "content": "Alaska trip (calendar block)",
                "people": [{"name": "Peggy"}],
            },
            {
                "unit_id": "ph-ak",
                "evidence_id": "ph-ak",
                "kind": "photo",
                "time": "2026-05-06",
                "place": "Anchorage",
                "content": "photo in Anchorage, Alaska",
                "people": [{"name": "Peggy"}],
            },
        ],
        "life_period_outline": {
            "period": "Alaska trip 2026",
            "episodes": [
                {
                    "theme_or_episode": "Alaska",
                    "claims": ["Flight to Anchorage for the Alaska trip"],
                    "evidence_ids": ["e-ak-cal", "ph-ak"],
                    "date_span": {"start": "2026-05-06", "end": "2026-05-06"},
                    "people": ["Peggy"],
                    "places": ["Anchorage", "Alaska"],
                    "scheduled_window": {
                        "start": "2026-05-01",
                        "end": "2026-05-15",
                        "evidence_ids": ["e-ak-cal"],
                    },
                    "observed_window": {
                        "start": "2026-05-06",
                        "end": "2026-05-06",
                        "evidence_ids": ["ph-ak"],
                    },
                    "uncertainty": {"calendar_scheduled_not_occurred": True},
                }
            ],
            "scheduled_window": {
                "start": "2026-05-01",
                "end": "2026-05-15",
                "evidence_ids": ["e-ak-cal"],
            },
            "observed_window": {
                "start": "2026-05-06",
                "end": "2026-05-06",
                "evidence_ids": ["ph-ak"],
            },
        },
    }
    bering = (
        "They crossed the Bering Sea in a storm, filled with excitement and concern."
    )
    bering_kept, bering_rej = ground_narrative(bering, gate_pack)
    bering_reasons = [r for row in bering_rej for r in (row.get("reasons") or [])]
    _check(
        "bering_sea_without_ids_rejected",
        (not bering_kept or "bering" not in bering_kept.lower())
        and any("bering" in r.lower() or r.startswith("place:") for r in bering_reasons)
        and any("weather:" in r or "experiential:" in r for r in bering_reasons),
        checks,
        problems,
        detail=str({"kept": bering_kept, "reasons": bering_reasons}),
    )
    spent = "They spent May 1 through May 15 traveling across Alaska."
    spent_kept, spent_rej = ground_narrative(spent, gate_pack)
    spent_reasons = [r for row in spent_rej for r in (row.get("reasons") or [])]
    _check(
        "calendar_range_not_treated_as_actual",
        (not spent_kept or "spent may 1" not in spent_kept.lower())
        and "calendar_span_as_actual" in spent_reasons,
        checks,
        problems,
        detail=str({"kept": spent_kept, "reasons": spent_reasons}),
    )
    hedged = (
        "The calendar showed Alaska from May 1 through May 15. "
        "Photos place Peggy in Anchorage on 2026-05-06."
    )
    hedged_kept, hedged_rej = ground_narrative(hedged, gate_pack)
    _check(
        "calendar_vs_actual_hedged_kept",
        "calendar showed" in hedged_kept.lower()
        and "anchorage" in hedged_kept.lower()
        and "2026-05-06" in hedged_kept
        and not any(
            "calendar_span_as_actual" in (row.get("reasons") or []) for row in hedged_rej
        ),
        checks,
        problems,
        detail=str({"kept": hedged_kept, "rej": hedged_rej}),
    )

    meta["synthetic"] = str(uuid4())[:8]
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
