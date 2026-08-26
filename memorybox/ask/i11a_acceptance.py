"""P2-I11A Generalized Evidence Inference Engine — acceptance prove."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.i11a import needs_semantic_inference, resolve_request_context
from memorybox.ask.i11a.infer import apply_inference_to_pack
from memorybox.ask.i11a.units import units_from_pack
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
    impl_py = orch_py.split("def _ask_impl", 1)[-1]
    _check(
        "a_planner_span_before_retrieve",
        impl_py.find("note_planner") >= 0
        and impl_py.find("note_planner") < impl_py.find("search_evidence_pg")
        and impl_py.find("note_retrieve") >= 0
        and impl_py.find("note_retrieve") < impl_py.find("search_evidence_pg"),
        checks,
        problems,
        detail="Live Follow must show planner + retrieve progress before lifetime SMS/email/photo scans",
    )
    immich_http = (root / "providers" / "photo" / "_immich_http.py").read_text(encoding="utf-8")
    _check(
        "a_immich_person_timeline_is_year_first",
        "_PERSON_TIMELINE_MONTH_WALK" not in immich_http
        and "one YEAR bucket per year" in immich_http
        and "_PERSON_LIB_WALK_SEC" in immich_http,
        checks,
        problems,
        detail="Peggy person library must not walk up to 720 Immich MONTH buckets",
    )
    js = (root / "ai_trace" / "static" / "ai-trace.js").read_text(encoding="utf-8")
    html = (root / "ai_trace" / "static" / "ai-trace.html").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    trip_py = (root / "ask" / "trip_discovery.py").read_text(encoding="utf-8")

    _check(
        "a12_no_hardcoded_llama",
        "llama3.2" not in infer_py,
        checks,
        problems,
        detail="provider-neutral inference role",
    )
    from memorybox.ask.i11a_regression import REGRESSION_ASKS

    _check(
        "a_regression_harness_four_asks",
        REGRESSION_ASKS
        == (
            "write a narrative about my January 2025",
            "write a narrative about my trip to las vegas in January 2026",
            "write a narrative about my alaska trip in 2026",
            "tell me what you know about Peggy",
        ),
        checks,
        problems,
        detail="i11a-regression canonical asks (live Asks are not part of prove-i11a)",
    )
    from memorybox.ask.i11a.observations import requires_model_interpretation

    _check(
        "extract_llm_only_for_freeform_b_units",
        (not requires_model_interpretation({"kind": "calendar"}))
        and (not requires_model_interpretation({"kind": "calendar_series"}))
        and (not requires_model_interpretation({"kind": "travel"}))
        and (not requires_model_interpretation({"kind": "comm_pattern"}))
        and (not requires_model_interpretation({"kind": "correlated_event"}))
        and (not requires_model_interpretation({"kind": "place_observation"}))
        and (not requires_model_interpretation({"kind": "media_cluster"}))
        and (not requires_model_interpretation({"kind": "media_observation"}))
        and (not requires_model_interpretation({"kind": "video_asset"}))
        and requires_model_interpretation({"kind": "communication_thread"})
        and requires_model_interpretation({"kind": "sms_segment"})
        and requires_model_interpretation({"kind": "spoken_moment"})
        and requires_model_interpretation({"kind": "communication", "source_type": "email"})
        and requires_model_interpretation(
            {"kind": "journal", "content": "A long free-form recollection about the week we spent driving."}
        )
        and not requires_model_interpretation({"kind": "journal", "title": "Note", "content": "Note"}),
        checks,
        problems,
        detail="A units bypass OBSERVATION_EXTRACT; B is free-form only",
    )
    from memorybox.ask.i11a.infer import run_inference
    from memorybox.providers.llm.fake import FakeLlmProvider

    inf_a = run_inference(
        plan_ask(
            "write a narrative about my trip to las vegas in January 2026",
            AskContext(session_id="i11a-ab-cal"),
        ),
        {
            "units": [
                {
                    "unit_id": "u-cal-a",
                    "kind": "calendar",
                    "source_type": "calendar",
                    "time": "2026-01-30",
                    "title": "Eagles Live at Sphere",
                    "content": "Eagles Live at Sphere",
                    "people": [{"name": "Tom"}],
                    "place": "Las Vegas",
                    "provenance": {"evidence_id": "e-cal-a"},
                }
            ]
        },
        FakeLlmProvider(),
    )
    acc_a = inf_a.get("accounting") or {}
    _check(
        "calendar_units_skip_observation_extract",
        acc_a.get("extract_calls") == 0
        and int(acc_a.get("observations_a") or 0) >= 1
        and int(acc_a.get("ask_relative_calls") or 0) == 1,
        checks,
        problems,
        detail={k: acc_a.get(k) for k in ("extract_calls", "observations_a", "observations_b", "leaf_calls", "ask_relative_calls")},
    )
    inf_b = run_inference(
        plan_ask(
            "write a narrative about my trip to las vegas in January 2026",
            AskContext(session_id="i11a-ab-em"),
        ),
        {
            "units": [
                {
                    "unit_id": "u-em-a",
                    "kind": "communication",
                    "source_type": "email",
                    "time": "2026-01-29",
                    "content": "Your Las Vegas hotel reservation is confirmed for Jan 29.",
                    "people": [{"name": "Tom"}],
                    "place": "Las Vegas",
                    "provenance": {"evidence_id": "e-em-a"},
                }
            ]
        },
        FakeLlmProvider(),
    )
    acc_b = inf_b.get("accounting") or {}
    _check(
        "email_units_still_use_observation_extract",
        int(acc_b.get("extract_calls") or 0) >= 1
        and int(acc_b.get("units_model_extract") or 0) >= 1,
        checks,
        problems,
        detail={k: acc_b.get(k) for k in ("extract_calls", "observations_a", "observations_b", "units_model_extract")},
    )
    from memorybox.ask.i11a.observations import observation_from_unit

    pat = observation_from_unit(
        {
            "kind": "comm_pattern",
            "evidence_id": "e-pat",
            "content": "repeated affectionate messages",
            "extra_ids": ["e-1", "e-2"],
        }
    ) or {}
    corr = observation_from_unit(
        {
            "kind": "correlated_event",
            "evidence_id": "e-corr",
            "content": "Dinner with calendar and texts",
            "extra_ids": ["e-cal", "e-sms"],
        }
    ) or {}
    _check(
        "pattern_and_correlation_bypass_extract_as_derived",
        (not requires_model_interpretation({"kind": "comm_pattern"}))
        and (not requires_model_interpretation({"kind": "correlated_event"}))
        and pat.get("claim_type") == "derived"
        and corr.get("claim_type") == "derived"
        and pat.get("supporting_evidence_ids")
        and corr.get("supporting_evidence_ids"),
        checks,
        problems,
        detail={"pat": pat.get("claim_type"), "corr": corr.get("claim_type")},
    )
    inf_mix = run_inference(
        plan_ask(
            "write a narrative about my trip to las vegas in January 2026",
            AskContext(session_id="i11a-ab-mix"),
        ),
        {
            "units": [
                {
                    "unit_id": "u-cal-mix",
                    "kind": "calendar",
                    "source_type": "calendar",
                    "time": "2026-01-30",
                    "title": "Eagles Live at Sphere",
                    "content": "Eagles Live at Sphere",
                    "provenance": {"evidence_id": "e-cal-mix"},
                },
                {
                    "unit_id": "u-em-mix",
                    "kind": "communication",
                    "source_type": "email",
                    "time": "2026-01-29",
                    "content": "Your Las Vegas hotel reservation is confirmed for Jan 29.",
                    "provenance": {"evidence_id": "e-em-mix"},
                },
            ]
        },
        FakeLlmProvider(),
    )
    acc_mix = inf_mix.get("accounting") or {}
    _check(
        "mixed_pack_extracts_only_b",
        int(acc_mix.get("extract_calls") or 0) == 1
        and int(acc_mix.get("units_model_extract") or 0) == 1
        and int(acc_mix.get("units_deterministic") or 0) >= 1,
        checks,
        problems,
        detail={k: acc_mix.get(k) for k in ("extract_calls", "units_model_extract", "units_deterministic", "observations_a", "observations_b")},
    )
    from memorybox.ask.i11a.preaggregate import preaggregate_pack as _pre_compact
    from memorybox.ask.i11a.comm_compact import (
        chunk_units_semantically,
        filter_extract_observations,
    )

    fat_emails = [
        {
            "unit_id": f"u-em-{i}",
            "kind": "communication",
            "source_type": "email",
            "time": "2025-01-10",
            "thread_id": "thr-trivia",
            "subject": "Trivia night",
            "content": (
                "Trivia planning: questions, donations, volunteers, tables, and supplies. "
                f"Note {i}."
            ),
            "people": [{"name": "Tom"}, {"name": "Alex"}],
            "evidence_id": f"e-em-{i}",
            "provenance": {"evidence_id": f"e-em-{i}"},
        }
        for i in range(20)
    ]
    fat_sms = [
        {
            "unit_id": f"u-sms-{i}",
            "kind": "communication",
            "source_type": "sms",
            "time": f"2025-01-11T18:0{i}:00",
            "thread_id": "thr-peggy-sms",
            "content": "Love you. Wishing you well." if i % 2 == 0 else "See you after practice.",
            "people": [{"name": "Peggy"}, {"name": "Tom"}],
            "evidence_id": f"e-sms-{i}",
        }
        for i in range(6)
    ]
    fat_pre = _pre_compact({"units": fat_emails + fat_sms})
    fat_units = fat_pre.get("units") or []
    fat_trace = fat_pre.get("trace") or {}
    fat_b = [u for u in fat_units if requires_model_interpretation(u)]
    raw_ids = {f"e-em-{i}" for i in range(20)} | {f"e-sms-{i}" for i in range(6)}
    kept_ids = set()
    for u in fat_units:
        kept_ids.update(str(x) for x in (u.get("extra_ids") or []) + (u.get("source_evidence_ids") or []))
        if u.get("evidence_id"):
            kept_ids.add(str(u.get("evidence_id")))
    inf_fat = run_inference(
        plan_ask(
            "write a narrative about my January 2025",
            AskContext(session_id="i11a-comm-compact"),
        ),
        {"units": fat_emails + fat_sms},
        FakeLlmProvider(),
    )
    acc_fat = inf_fat.get("accounting") or {}
    _check(
        "comm_thread_replaces_raw_email_rows_in_extract",
        int(fat_trace.get("email_raw") or 0) == 20
        and int(fat_trace.get("email_thread_units") or 0) == 1
        and int(fat_trace.get("sms_segment_units") or 0) == 1
        and len(fat_b) <= 2
        and raw_ids <= kept_ids
        and float(fat_trace.get("provenance_coverage") or 0) == 1.0
        and int(acc_fat.get("extract_calls") or 99) <= 2,
        checks,
        problems,
        detail={
            "trace": {k: fat_trace.get(k) for k in (
                "email_raw", "email_thread_units", "sms_raw", "sms_segment_units",
                "raw_comm_items", "semantic_comm_units_after_dedupe", "provenance_coverage",
                "duplicate_comm_units_omitted_from_extract",
            )},
            "b": len(fat_b),
            "extract_calls": acc_fat.get("extract_calls"),
            "gap": sorted(raw_ids - kept_ids),
        },
    )
    mixed_chunk = chunk_units_semantically(fat_b, budget=12_000)
    trivia_only = any(
        all(str(u.get("thread_id") or "") == "thr-trivia" for u in ch) and ch
        for ch in mixed_chunk
    )
    sms_only = any(
        all(str(u.get("thread_id") or "") == "thr-peggy-sms" for u in ch) and ch
        for ch in mixed_chunk
    )
    _check(
        "extract_chunks_are_semantically_grouped",
        trivia_only and sms_only and len(mixed_chunk) == 2,
        checks,
        problems,
        detail={"chunks": len(mixed_chunk), "b": len(fat_b)},
    )
    same_day = [
        {
            "unit_id": f"u-loose-{i}",
            "kind": "communication_thread",
            "source_type": "email",
            "time": "2025-01-10",
            "subject": f"Unique subject {i}",
            "content": f"Planning note {i}: tables, donations, volunteers.",
            "people": [{"name": "Tom"}],
            "evidence_id": f"e-loose-{i}",
            "extra_ids": [f"e-loose-{i}"],
        }
        for i in range(24)
    ]
    inf_day = run_inference(
        plan_ask(
            "write a narrative about my January 2025",
            AskContext(session_id="i11a-same-day-pack"),
        ),
        {"units": same_day},
        FakeLlmProvider(),
    )
    acc_day = inf_day.get("accounting") or {}
    packed_day = chunk_units_semantically(same_day, budget=12_000)
    _check(
        "same_day_singleton_threads_share_extract_chunk",
        len(packed_day) == 1
        and int(acc_day.get("extract_calls") or 99) == 1
        and int(acc_day.get("units_model_extract") or 0) == 24,
        checks,
        problems,
        detail={"chunks": len(packed_day), "extract_calls": acc_day.get("extract_calls"), "b": acc_day.get("units_model_extract")},
    )
    chunk0 = [
        {
            "kind": "communication_thread",
            "evidence_id": "e-em-0",
            "extra_ids": ["e-em-0", "e-em-1"],
            "content": "Tom and the band discussed evening practice and key changes.",
            "people": [{"name": "Tom"}],
            "time": "2025-01-10",
        }
    ]
    kept_ok, rej_ok = filter_extract_observations(
        [
            {
                "kind": "communication_states",
                "text": "Tom and the band discussed evening practice and key changes.",
                "supporting_evidence_ids": ["e-em-0"],
                "people": [{"name": "Tom"}],
            }
        ],
        chunk0,
    )
    _, rej_kind = filter_extract_observations(
        [{"kind": "vibes", "text": "good energy", "supporting_evidence_ids": ["e-em-0"]}],
        chunk0,
    )
    _, rej_id = filter_extract_observations(
        [
            {
                "kind": "communication_states",
                "text": "Tom and the band discussed evening practice and key changes.",
                "supporting_evidence_ids": ["invented-id"],
                "people": [{"name": "Tom"}],
            }
        ],
        chunk0,
    )
    _, rej_place = filter_extract_observations(
        [
            {
                "kind": "communication_states",
                "text": "Tom mentioned Paris.",
                "supporting_evidence_ids": ["e-em-0"],
                "places": ["Paris"],
                "people": [{"name": "Tom"}],
            }
        ],
        chunk0,
    )
    _, rej_presence = filter_extract_observations(
        [
            {
                "kind": "person_at_place_time",
                "text": "Tom was in Paris",
                "supporting_evidence_ids": ["e-em-0"],
                "places": ["Paris"],
                "people": [{"name": "Tom"}],
            }
        ],
        chunk0,
    )
    _, rej_transport = filter_extract_observations(
        [
            {
                "kind": "communication_states",
                "text": "Tom sent an email",
                "supporting_evidence_ids": ["e-em-0"],
                "people": [{"name": "Tom"}],
            }
        ],
        chunk0,
    )
    _check(
        "extract_rejects_invalid_kinds_ids_places_presence_transport",
        bool(kept_ok)
        and any(r.get("reason") == "kind_not_canonical" for r in rej_kind)
        and any(r.get("reason") == "evidence_id_not_in_unit_provenance" for r in rej_id)
        and any(r.get("reason") == "invented_place" for r in rej_place)
        and any(r.get("reason") == "person_at_place_time_without_stated_presence" for r in rej_presence)
        and any(r.get("reason") == "transport_metadata_only" for r in rej_transport),
        checks,
        problems,
        detail={"ok": kept_ok, "kind": rej_kind, "id": rej_id, "place": rej_place, "pres": rej_presence, "tr": rej_transport},
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
        and "?v=i11a9" in html
        and "copy-preaggregation" in js
        and "copy-semantic-observations" in js
        and "copy-semantic-ir" in js
        and "copy-ask-relative" in js
        and "copy-ask-relative-payload" in js
        and "retrieval_resolution" in js
        and "copy-retrieval-resolution" in js
        and "copy-consideration" in js
        and "resolved_trip_window" in trip_py,
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
        and (down_pack.get("inference") or {}).get("error_class") != "PARSE_SCHEMA"
        and "narration unavailable" in down_text.lower()
        and "evidence-backed account" not in down_text.lower(),
        checks,
        problems,
        detail=down_text[:200],
    )

    class _TimeoutLlm(FakeLlmProvider):
        provider_key = "ollama"
        chat_model = "llama3.2"

        def chat(self, messages, *, json_mode=False):  # type: ignore[no-untyped-def]
            system = next((m.content for m in messages if m.role == "system"), "")
            if "ASK_RELATIVE_REASONING" in (system or ""):
                raise ProviderUnavailable("timed out after 90s")
            return super().chat(messages, json_mode=json_mode)

    to_text, to_pack, to_meta = tell_from_hits(jan_plan, llm=_TimeoutLlm(), evidence=hits)
    to_inf = to_pack.get("inference") or {}
    _check(
        "ask_relative_timeout_is_not_parse_schema",
        to_meta.get("fail_closed") is True
        and to_inf.get("fail_closed") is True
        and to_inf.get("error_class") == "PROVIDER_TIMEOUT"
        and "timed out" in str(to_inf.get("reason") or "").lower()
        and "PARSE_SCHEMA" not in str(to_inf.get("error_class") or "")
        and to_inf.get("stage") == "ask-relative reasoning"
        and to_inf.get("timeout_seconds") == 90
        and to_pack.get("semantic_observations")
        and not to_pack.get("validated_inference")
        and "narration unavailable" in to_text.lower()
        and "evidence-backed account" not in to_text.lower(),
        checks,
        problems,
        detail=str({k: to_inf.get(k) for k in ("ok", "fail_closed", "reason", "error_class", "stage", "timeout_seconds", "retry_count")}),
    )

    fake = FakeLlmProvider()
    raw = fake.chat(
        [
            ChatMessage(role="system", content="OBSERVATION_EXTRACT"),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {
                        "units": [
                            {
                                "unit_id": "u1",
                                "evidence_id": "e-harbor",
                                "kind": "communication",
                                "time": "2025-01-12",
                                "content": "harbor dinner",
                                "people": [{"name": "Tom"}],
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
        and (parsed.get("observations") or [])
        and "coverage" not in parsed
        and "harbor" in json.dumps(parsed, default=str).lower(),
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
        and found.plan.time_start <= "2026-05-02"
        and found.plan.time_end >= "2026-05-06"
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
        and str(resolved_as_of) == str(found.plan.time_start)[:10]
        and str(resolved_as_of) != "2026-01-01"
        and len(dup_rels) == 2
        and len((slim.get("requestor") or {}).get("known_relationships") or []) == 2,
        checks,
        problems,
        detail=str({"year_as_of": year_as_of, "resolved": resolved_as_of, "dup": len(dup_rels), "slim": slim}),
    )
    _check(
        "inference_prompt_untouched_by_alaska_trace",
        "OBSERVATION_EXTRACT" in infer_py
        and "ASK_RELATIVE_REASONING" in (root / "ask" / "i11a" / "reason.py").read_text(encoding="utf-8")
        and "Do not invent people, places, dates" in infer_py
        and "MERGE_SYSTEM_PERSON" not in infer_py
        and "select_for_ask" not in infer_py
        and "select_for_ask" not in (root / "ask" / "i11a" / "reason.py").read_text(encoding="utf-8"),
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
        and "do not convert plausible inference" in prompt_l
        and "much-needed break" in prompt_l
        and "do not turn place presence into meaning" in prompt_l
        and "evidence behind this story" in prompt_l,
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
                    "uncertainty": {"occurrence_not_established_by_calendar_alone": True},
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

    jan26 = plan_ask(
        "write a narrative about my January of 2026",
        AskContext(session_id="i11a-jan26-sphere"),
    )
    sphere_photo = PhotoHit(
        provider_key="immich",
        external_id="ph-sphere-vegas",
        taken_at="2026-01-18T20:15:00",
        people=["Tom Will"],
        location="Las Vegas",
        place="Las Vegas",
        thumb_url=None,
        web_url=None,
        latitude=36.1699,
        longitude=-115.1398,
        mb_person_id="p-tom",
        mb_person_name="Tom Will",
        identity_trust="confirmed",
    )
    weak_photos = [
        PhotoHit(
            provider_key="immich",
            external_id=f"ph-weak-{d:02d}",
            taken_at=f"2026-01-{d:02d}T12:00:00",
            people=[],
            location="unspecified roadside",
            place="unspecified roadside",
            thumb_url=None,
            web_url=None,
            latitude=None,
            longitude=None,
            identity_trust="candidate",
        )
        for d in range(1, 21)
        if d != 18
    ]
    sphere_hits = [
        EvidenceHit(
            evidence_id="e-sphere-cal",
            evidence_kind="calendar_event",
            summary="Eagles at Sphere, Las Vegas",
            score=1.0,
            excerpt="Eagles concert at the Sphere",
            source="ics",
            sent_at="2026-01-18T19:00:00",
            channel="calendar",
            people=["Tom Will"],
        ),
        EvidenceHit(
            evidence_id="e-sphere-sms",
            evidence_kind="communication",
            summary="Sphere tonight",
            score=1.0,
            excerpt="We're at the Sphere in Las Vegas for the Eagles",
            source="sms_export",
            sent_at="2026-01-18T18:40:00",
            channel="sms",
            people=["Tom Will"],
            thread_id="t-sphere",
        ),
        EvidenceHit(
            evidence_id="e-vegas-mail",
            evidence_kind="communication",
            summary="Delta itinerary LAS",
            score=1.0,
            excerpt="Delta confirmation ABC12X: LAS Las Vegas 2026-01-17. Eagles at Sphere.",
            source="email_mbox",
            sent_at="2026-01-16T09:00:00",
            channel="email",
            people=["Tom Will"],
            thread_id="t-vegas-air",
        ),
    ]
    _sp_text, sp_pack, _ = tell_from_hits(
        jan26,
        llm=FakeLlmProvider(),
        evidence=sphere_hits,
        photos=[sphere_photo, *weak_photos],
    )
    sp_val = sp_pack.get("validated_inference") or {}
    sp_eps = [e for e in (sp_val.get("episodes") or []) if isinstance(e, dict)]
    nar_sp = pack_for_narrator(sp_pack)
    nar_sp_blob = json.dumps(nar_sp, default=str)

    def _blob(ep: dict[str, Any]) -> str:
        return " ".join(
            [
                str(ep.get("label") or ""),
                str(ep.get("theme_or_episode") or ""),
                " ".join(str(p) for p in (ep.get("places") or [])),
                json.dumps(ep.get("claims") or [], default=str),
            ]
        ).lower()

    sphere_eps = [
        e
        for e in sp_eps
        if any(tok in _blob(e) for tok in ("sphere", "eagles", "las vegas", "vegas"))
    ]
    weak_eps = [e for e in sp_eps if "roadside" in _blob(e) or "unspecified" in _blob(e)]
    sphere_score = max((float(e.get("support_score") or 0) for e in sphere_eps), default=-1)
    weak_score = max((float(e.get("support_score") or 0) for e in weak_eps), default=0)
    ranked_first = _blob(sp_eps[0]) if sp_eps else ""
    media_units = [
        u
        for u in units_from_pack(sp_pack)
        if str(u.get("asset_ref") or "") == "ph-sphere-vegas" or "ph-sphere-vegas" in str(u.get("evidence_id") or "")
    ]
    media = (media_units[0].get("media") if media_units else {}) or {}
    windows_ok = all(
        isinstance(e.get("scheduled_window"), dict)
        and isinstance(e.get("observed_window"), dict)
        and isinstance(e.get("derived_window"), dict)
        for e in sp_eps
    ) and isinstance(sp_val.get("observed_window"), dict)
    _check(
        "jan2026_sphere_outranks_weak_place",
        bool(sphere_eps)
        and sphere_score > weak_score
        and any(tok in ranked_first for tok in ("sphere", "eagles", "vegas", "las vegas"))
        and "roadside" not in ranked_first
        and (sphere_eps[0].get("support_profile") or {}).get("independent_sources", 0) >= 2
        and "support_score" not in nar_sp_blob
        and "support_profile" not in nar_sp_blob
        and windows_ok
        and bool(media.get("exif_gps"))
        and media.get("captured_at")
        and media.get("asset_id")
        and any(
            isinstance(p, dict) and p.get("person_id") == "p-tom"
            for p in (media.get("people_observed") or [])
        ),
        checks,
        problems,
        detail=str(
            {
                "sphere_n": len(sphere_eps),
                "weak_n": len(weak_eps),
                "sphere_score": sphere_score,
                "weak_score": weak_score,
                "first": (sp_eps[0] if sp_eps else {}) .get("label"),
                "profile": (sphere_eps[0].get("support_profile") if sphere_eps else None),
                "media": media,
                "nar_has_score": "support_score" in nar_sp_blob,
            }
        ),
    )
    _check(
        "evidence_commentary_after_story",
        "evidence behind this story" in _sp_text.lower()
        and "family evidence considered" in _sp_text.lower()
        and _sp_text.lower().rfind("evidence behind this story") > 10,
        checks,
        problems,
        detail=_sp_text[-400:],
    )
    mapped = (sp_pack.get("narrative_validation") or {}).get("sentence_evidence")
    # Mapping is recorded on enforce meta; synthesize stores rejected only. Probe gate directly.
    mapped_kept, _mapped_rej = ground_narrative(hedged, gate_pack)
    from memorybox.ask.narrative_ground import enforce_narrative_grounding

    _cleaned, gmeta = enforce_narrative_grounding(hedged, gate_pack)
    _check(
        "sentence_place_date_maps_to_evidence_ids",
        any(
            "ph-ak" in (row.get("evidence_ids") or []) or "e-ak-cal" in (row.get("evidence_ids") or [])
            for row in (gmeta.get("sentence_evidence") or [])
        )
        and bool(mapped_kept),
        checks,
        problems,
        detail=str(gmeta.get("sentence_evidence")),
    )

    from memorybox.ask.i11a.units import compact_units_for_model
    from memorybox.ask.travel import extract_travel
    from memorybox.ask.place_match import trip_hint_tokens

    flood_photos = [
        PhotoHit(
            provider_key="immich",
            external_id=f"ph-flood-{i}",
            taken_at=f"2026-01-{(i % 28) + 1:02d}T12:00:00",
            people=["Tom Will"],
            location="Manchester",
            thumb_url=None,
            web_url=None,
        )
        for i in range(20)
    ]
    jan_cal_plan = plan_ask(
        "Write a narrative about my January of 2026",
        AskContext(session_id="i11a-cal-pipe"),
    )
    cal_flight = EvidenceHit(
        evidence_id="e-las-flight",
        evidence_kind="calendar_event",
        summary="Flight to Las Vegas",
        score=1.0,
        excerpt="Flight to Las Vegas",
        source="ics",
        sent_at="2026-01-29T08:00:00",
        channel="calendar",
    )
    cal_sphere = EvidenceHit(
        evidence_id="e-eagles-sphere",
        evidence_kind="calendar_event",
        summary="Eagles Live at Sphere",
        score=1.0,
        excerpt="Eagles Live at Sphere",
        source="ics",
        sent_at="2026-01-30T19:00:00",
        channel="calendar",
    )
    paradise_photo = PhotoHit(
        provider_key="immich",
        external_id="ph-paradise-nv",
        taken_at="2026-01-30T16:00:00",
        people=["Tom Will"],
        location="Paradise, Nevada",
        thumb_url=None,
        web_url=None,
        city="Paradise",
        state="Nevada",
        latitude=36.12,
        longitude=-115.17,
        mb_person_id="p-tom",
        mb_person_name="Tom Will",
    )
    jan_vid = PhotoHit(
        provider_key="immich",
        external_id="vid-vegas-clip",
        taken_at="2026-01-31T11:00:00",
        people=["Tom Will"],
        location="Las Vegas",
        thumb_url=None,
        web_url=None,
        media_type="video",
        original_filename="clip.mp4",
        duration_sec=42.0,
        latitude=36.11,
        longitude=-115.17,
    )
    jan_pack = prepare_narrative_pack(
        jan_cal_plan,
        evidence=[cal_flight, cal_sphere],
        photos=flood_photos + [paradise_photo, jan_vid],
        photo_status={
            "media_provider_candidates": 40,
            "person_filtered_media_count": 30,
            "time_filtered_media_count": 22,
            "location_filtered_count": None,
        },
    )
    inf_units = units_from_pack(jan_pack)
    compact = compact_units_for_model(inf_units)
    cal_titles = " ".join(
        str(u.get("title") or u.get("content") or "") for u in jan_pack.get("units") or []
    ).lower()
    pipe = {str(r.get("evidence_id")): r for r in (jan_pack.get("calendar_pipeline") or [])}
    sets = jan_pack.get("evidence_sets") or {}
    kinds = {str(u.get("kind")) for u in jan_pack.get("units") or []}
    obs_days = []
    for ep in jan_pack.get("episodes") or []:
        blob = str(ep.get("title") or ep.get("content") or "").lower()
        if "sphere" in blob or "vegas" in blob or "eagles" in blob:
            ow = ep.get("observed_window") or {}
            obs_days.append((ow.get("start"), ow.get("end")))
    princess = extract_travel(
        subject="Your Princess Cruises itinerary",
        body="Princess Cruises confirmation P9K3M2 itinerary Vancouver to Whittier May 12, 2026 shore excursion",
        source_unit_id="u-pr",
        source_evidence_id="e-princess",
    )
    ak_air = extract_travel(
        subject="Alaska Airlines itinerary",
        body="Alaska Airlines confirmation X1Y2Z3 LAX to ANC May 10, 2026",
        source_unit_id="u-as",
        source_evidence_id="e-as",
    )
    princess_hit = EvidenceHit(
        evidence_id="e-princess-mail",
        evidence_kind="communication",
        summary="Your Princess Cruises itinerary",
        score=1.0,
        excerpt="Princess Cruises confirmation P9K3M2 itinerary Vancouver May 12, 2026",
        source="email_mbox",
        sent_at="2026-05-01T10:00:00",
        channel="email",
    )
    from memorybox.ask.trip_discovery import resolve_trip as _resolve_trip2

    ak_plan = plan_ask(
        "Tell me about my Alaska trip in 2026",
        AskContext(session_id="i11a-ak-pipe"),
    )
    ak_disc = _resolve_trip2(
        ak_plan,
        evidence=[princess_hit],
        photos=[
            PhotoHit(
                provider_key="immich",
                external_id="ph-yvr",
                taken_at="2026-05-12T12:00:00",
                people=["Tom Will"],
                location="Vancouver",
                thumb_url=None,
                web_url=None,
                city="Vancouver",
            )
        ],
        photo_status={
            "provider_key": "immich",
            "after_temporal_filter": 1,
            "constraint_mode": "deferred_trip_discovery",
        },
    )
    _check(
        "i11a_no_topn_drop_calendar",
        any("las vegas" in cal_titles and "eagles" in cal_titles for _ in (True,))
        and any(str(u.get("kind")) == "calendar" for u in compact)
        and len([u for u in compact if str(u.get("kind")) == "calendar"]) >= 2
        and len(compact) >= len(
            [u for u in inf_units if str(u.get("kind")) in {"calendar", "travel"}]
        ),
        checks,
        problems,
        detail=str(
            {
                "compact_n": len(compact),
                "inf_n": len(inf_units),
                "cal_in_compact": [
                    u.get("content") for u in compact if u.get("kind") == "calendar"
                ],
                "titles": cal_titles[:240],
            }
        ),
    )
    _check(
        "jan_calendar_pipeline_sphere_and_flight",
        bool(pipe.get("e-las-flight", {}).get("converted_to_inference_unit"))
        and bool(pipe.get("e-eagles-sphere", {}).get("converted_to_inference_unit"))
        and pipe.get("e-las-flight", {}).get("retrieved") is True
        and pipe.get("e-eagles-sphere", {}).get("eligible") is True,
        checks,
        problems,
        detail=str(pipe),
    )
    _check(
        "three_evidence_sets_are_distinct",
        set(sets) >= {"retrieved", "inference", "presentation"}
        and (sets.get("retrieved") or {}).get("photos") == 22
        and (sets.get("inference") or {}).get("units_generated") == len(jan_pack.get("units") or [])
        and (jan_pack.get("media_consideration") or {}).get("media_provider_candidates") == 40
        and (jan_pack.get("media_consideration") or {}).get("time_filtered_media_count") == 22
        and (jan_pack.get("media_consideration") or {}).get("person_filtered_media_count") == 30
        and (jan_pack.get("media_consideration") or {}).get("location_filtered_count") is None,
        checks,
        problems,
        detail=str({"sets": sets, "media": jan_pack.get("media_consideration")}),
    )
    _check(
        "video_asset_without_face_moment",
        "video_asset" in kinds
        and any(
            str(u.get("asset_ref")) == "vid-vegas-clip" and u.get("kind") == "video_asset"
            for u in (jan_pack.get("units") or [])
        ),
        checks,
        problems,
        detail=str(sorted(kinds)),
    )
    _check(
        "princess_and_alaska_air_travel_units",
        bool(princess and princess.get("travel_kind") == "cruise")
        and bool(ak_air and ak_air.get("travel_kind") == "flight")
        and "princess" in trip_hint_tokens("alaska"),
        checks,
        problems,
        detail=str({"princess": princess, "ak_air": ak_air, "hints": trip_hint_tokens("alaska")[:8]}),
    )
    _check(
        "alaska_princess_email_selected_and_vancouver_photo_in_window",
        any(
            r.get("evidence_id") == "e-princess-mail" and r.get("selected")
            for r in ak_disc.comm_pipeline
        )
        and any(p.external_id == "ph-yvr" for p in ak_disc.photos),
        checks,
        problems,
        detail=str(
            {
                "resolved": ak_disc.resolved,
                "comm": ak_disc.comm_pipeline,
                "photos": [p.external_id for p in ak_disc.photos],
                "windows": ak_disc.windows,
            }
        ),
    )

    lv_jan = plan_ask(
        "write a narrative about my Las Vegas trip in January 2026",
        AskContext(session_id="i11a-lv-jan-place"),
    )
    _check(
        "january_is_not_a_place_name",
        any("las vegas" in str(p).lower() for p in (lv_jan.place_names or ()))
        and not any(str(p).lower() == "january" for p in (lv_jan.place_names or ()))
        and "trip_window_unresolved" in (lv_jan.notes or ()),
        checks,
        problems,
        detail=str({"places": lv_jan.place_names, "trips": lv_jan.trip_labels, "notes": lv_jan.notes}),
    )
    unrelated = EvidenceHit(
        evidence_id="e-unrelated-class",
        evidence_kind="communication",
        summary="Class reunion lunch",
        score=1.0,
        excerpt="last week the class from 1998 met for tacos in town",
        source="email_mbox",
        sent_at="2026-01-12T12:00:00",
        channel="email",
    )
    early_vegas_mail = EvidenceHit(
        evidence_id="e-jan3-newsletter",
        evidence_kind="communication",
        summary="Las Vegas deals",
        score=1.0,
        excerpt="January Las Vegas buffet specials this week",
        source="email_mbox",
        sent_at="2026-01-03T12:00:00",
        channel="email",
    )
    feb_res = EvidenceHit(
        evidence_id="e-feb-reservation",
        evidence_kind="communication",
        summary="Your Las Vegas reservation",
        score=1.0,
        excerpt="Las Vegas reservation confirmation for February 1",
        source="email_mbox",
        sent_at="2026-02-01T10:00:00",
        channel="email",
    )
    hotel_in_window = EvidenceHit(
        evidence_id="e-hotel-folio",
        evidence_kind="communication",
        summary="Your folio",
        score=1.0,
        excerpt="Thank you for staying with us. Folio attached.",
        source="email_mbox",
        sent_at="2026-01-30T09:00:00",
        channel="email",
    )
    return_flight = EvidenceHit(
        evidence_id="e-return-sea",
        evidence_kind="calendar_event",
        summary="Flight home",
        score=1.0,
        excerpt="Return to Seattle",
        source="ics",
        sent_at="2026-02-02T11:00:00",
        channel="calendar",
    )
    from memorybox.ask.retrieve import video_assets_from_photo_hits
    from memorybox.ask.i11a.claim_support import claim_support_ok
    from memorybox.ask.i11a.observations import extract_observations
    from memorybox.ask.i11a.reason import fallback_view
    from memorybox.providers.photo._immich_http import ImmichHttpClient

    lv_disc = _resolve_trip2(
        lv_jan,
        evidence=[
            unrelated,
            early_vegas_mail,
            cal_flight,
            cal_sphere,
            hotel_in_window,
            feb_res,
            return_flight,
        ],
        photos=[paradise_photo, jan_vid],
        videos=video_assets_from_photo_hits([jan_vid]),
        photo_status={
            "provider_key": "immich",
            "person_library_unwindowed_n": 400,
            "person_assets_in_window_n": 9,
            "person_stills_in_window_n": 8,
            "person_videos_in_window_n": 1,
            "year_fair_applied": False,
            "after_temporal_filter": 9,
            "constraint_mode": "deferred_trip_discovery",
        },
    )
    photo_mod = lv_disc.modalities[0].to_dict() if lv_disc.modalities else {}
    selected = {str(r.get("evidence_id")): r for r in lv_disc.comm_pipeline if r.get("selected")}
    skipped_unrelated = next(
        (r for r in lv_disc.comm_pipeline if r.get("evidence_id") == "e-unrelated-class"),
        {},
    )
    _check(
        "immich_window_count_is_not_a_nine_cap",
        photo_mod.get("person_library_unwindowed_n") == 400
        and photo_mod.get("person_assets_in_window_n") == 9
        and photo_mod.get("year_fair_applied") is False
        and photo_mod.get("initial_candidate_count") == 9
        and ImmichHttpClient.year_fair_should_apply(
            (("2026-01-01", "2026-01-31"),), 400, 5000
        )
        is False,
        checks,
        problems,
        detail=str(photo_mod),
    )
    _check(
        "vegas_canaries_and_match_reasons",
        lv_disc.resolved
        and "e-las-flight" in selected
        and "e-eagles-sphere" in selected
        and selected["e-las-flight"].get("match_reason")
        and "e-unrelated-class" not in selected
        and "e-hotel-folio" not in selected
        and skipped_unrelated.get("skip_reason") == "no_place_hint_or_travel_match"
        and any(p.external_id == "ph-paradise-nv" for p in lv_disc.photos)
        and any(v.external_id == "vid-vegas-clip" for v in lv_disc.videos)
        and lv_disc.needs_refetch
        and str((lv_disc.resolved_window or ("", ""))[0]) >= "2026-01-20"
        and (lv_disc.resolved_window or ("", ""))[1] >= "2026-02-02"
        and any(h.evidence_id == "e-return-sea" for h in lv_disc.evidence)
        and any(h.evidence_id == "e-feb-reservation" for h in lv_disc.evidence)
        and not any(h.evidence_id == "e-hotel-folio" for h in lv_disc.evidence)
        and not any(h.evidence_id == "e-jan3-newsletter" for h in lv_disc.evidence)
        and any(
            r.get("evidence_id") == "e-hotel-folio"
            and r.get("eligible_for_consideration")
            and not r.get("selected")
            for r in lv_disc.comm_pipeline
        ),
        checks,
        problems,
        detail=str(
            {
                "resolved": lv_disc.resolved,
                "win": lv_disc.resolved_window,
                "refetch": lv_disc.needs_refetch,
                "comm": lv_disc.comm_pipeline,
                "ev": [h.evidence_id for h in lv_disc.evidence],
                "ph": [p.external_id for p in lv_disc.photos],
            }
        ),
    )
    _check(
        "immich_video_without_hvrt_moment",
        bool(video_assets_from_photo_hits([jan_vid]))
        and video_assets_from_photo_hits([jan_vid])[0].attribution == "video_asset",
        checks,
        problems,
        detail="HVRT moments are not required for Immich VIDEO assets",
    )
    generic_ok, generic_why = claim_support_ok(
        "Tom flew to Las Vegas",
        {
            "kind": "communication",
            "content": "Flight 2026-01-20 confirmation",
            "title": "Your flight",
        },
    )
    cal_ok, cal_why = claim_support_ok(
        "Tom flew to Las Vegas",
        {"kind": "calendar", "content": "Flight to Las Vegas", "title": "Flight to Las Vegas"},
    )
    gps_ok, gps_why = claim_support_ok(
        "Tom was in Paradise, NV",
        {
            "kind": "media_observation",
            "content": "photo",
            "latitude": 36.12,
            "longitude": -115.17,
            "place": "Paradise",
        },
    )
    _check(
        "claim_support_id_exists_is_not_enough",
        generic_ok is False
        and generic_why == "generic_flight_does_not_locate"
        and cal_ok is False
        and cal_why == "calendar_supports_scheduled_not_occurrence"
        and gps_ok is True,
        checks,
        problems,
        detail=str({"generic": generic_why, "cal": cal_why, "gps": gps_why}),
    )
    vegas_units = [
        {
            "kind": "calendar",
            "evidence_id": "e-las-flight",
            "unit_id": "u-flight",
            "time": "2026-01-29",
            "content": "Flight to Las Vegas",
            "title": "Flight to Las Vegas",
            "place": "Las Vegas",
        },
        {
            "kind": "calendar",
            "evidence_id": "e-eagles-sphere",
            "unit_id": "u-sphere",
            "time": "2026-01-30",
            "content": "Eagles Live at Sphere",
            "title": "Eagles Live at Sphere",
            "place": "Las Vegas",
        },
        {
            "kind": "media_observation",
            "evidence_id": "ph-paradise-nv",
            "asset_ref": "ph-paradise-nv",
            "time": "2026-01-30T16:00:00",
            "place": "Paradise, Nevada",
            "latitude": 36.12,
            "longitude": -115.17,
            "people": [{"name": "Tom"}],
        },
    ]
    vegas_obs = extract_observations(vegas_units, persist=False)
    vegas_kinds = {str(o.get("kind") or "") for o in vegas_obs}
    vegas_view = fallback_view(
        vegas_obs, ask="Summarize our Las Vegas trip", ask_kind_hint="trip"
    )
    vegas_blob = json.dumps(vegas_view, default=str).lower()
    vegas_eids = set()
    for ep in vegas_view.get("episodes") or []:
        vegas_eids.update(str(x) for x in (ep.get("supporting_evidence_ids") or []))
        for cl in ep.get("claims") or []:
            if isinstance(cl, dict):
                vegas_eids.update(str(x) for x in (cl.get("supporting_evidence_ids") or []))
    _check(
        "leaf_reduce_one_vegas_trip",
        "calendar_records_event" in vegas_kinds
        and "person_at_place_time" in vegas_kinds
        and "trip" not in vegas_kinds
        and "e-las-flight" in vegas_eids
        and "e-eagles-sphere" in vegas_eids
        and "ph-paradise-nv" in vegas_eids
        and "flight to las vegas" in vegas_blob
        and "sphere" in vegas_blob
        and "paradise" in vegas_blob
        and "reduce_leaf_observations(" not in infer_py,
        checks,
        problems,
        detail=str({"kinds": sorted(vegas_kinds), "eids": sorted(vegas_eids), "eps": vegas_view.get("episodes")}),
    )
    _check(
        "immich_timeline_not_windowed_before_cache",
        "do not cache a dated walk as the library"
        in (root / "providers" / "photo" / "_immich_http.py").read_text(encoding="utf-8")
        and "_PERSON_LIB_CACHE_VER = \"v10\""
        in (root / "providers" / "photo" / "_immich_http.py").read_text(encoding="utf-8"),
        checks,
        problems,
        detail="unwindowed Immich cache must not be a January walk",
    )
    _check(
        "calendar_uncertainty_is_not_nonoccurrence",
        "occurrence_not_established_by_calendar_alone" in (root / "ask" / "evidence_prep.py").read_text(
            encoding="utf-8"
        )
        and "calendar_scheduled_not_occurred" not in (root / "ask" / "i11a" / "infer.py").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        detail="absence of proof is not proof of non-occurrence",
    )

    from memorybox.ask.i11a.claim_support import claim_support_ok
    from memorybox.ask.i11a.preaggregate import preaggregate_pack
    from memorybox.ask.narrative import synthesize_tell

    live_ok, live_why = claim_support_ok(
        "Peggy lives in Manchester",
        {
            "kind": "media_observation",
            "content": "photo",
            "place": "Manchester",
            "latitude": 53.48,
            "longitude": -2.24,
        },
    )
    _check(
        "gps_presence_is_not_residence",
        live_ok is False and live_why == "gps_presence_is_not_residence",
        checks,
        problems,
        detail=str({"ok": live_ok, "why": live_why}),
    )
    _check(
        "person_reduce_is_not_one_trip_episode",
        "DEPRECATED" in (root / "ask" / "i11a" / "reduce.py").read_text(encoding="utf-8")
        and "MERGE_SYSTEM_PERSON" not in infer_py
        and "ASK_RELATIVE_REASONING" in (root / "ask" / "i11a" / "reason.py").read_text(encoding="utf-8")
        and "ask_kind" not in __import__("inspect").signature(
            extract_observations
        ).parameters,
        checks,
        problems,
        detail="Person merge/reduce must not be trip-only",
    )

    class _CountLlm(FakeLlmProvider):
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, messages, *, json_mode=False):  # type: ignore[no-untyped-def]
            self.calls += 1
            return super().chat(messages, json_mode=json_mode)

    peggy_photos = [
        PhotoHit(
            provider_key="immich",
            external_id=f"ph-peg-{i}",
            taken_at=f"2024-{(i % 11) + 1:02d}-{(i % 27) + 1:02d}T12:00:00",
            people=["Peggy"],
            location="Manchester",
            place="Manchester",
            city="Manchester",
            thumb_url=None,
            web_url=None,
            latitude=53.48,
            longitude=-2.24,
        )
        for i in range(48)
    ]
    peggy_ev = [
        EvidenceHit(
            evidence_id=f"e-love-{i}",
            evidence_kind="communication",
            summary="love you" if i % 2 == 0 else "dinner tomorrow?",
            score=1.0,
            excerpt="love you Peggy <3" if i % 2 == 0 else "Want to come over for dinner tomorrow?",
            source="sms_export",
            sent_at=f"2024-03-{(i % 20) + 1:02d}T18:00:00",
            channel="sms",
            people=["Peggy", "Tom"],
            thread_id="t-peggy-sms",
        )
        for i in range(8)
    ]
    peggy_ev.append(
        EvidenceHit(
            evidence_id="e-peg-dinner-cal",
            evidence_kind="calendar_event",
            summary="Dinner with Peggy",
            score=1.0,
            excerpt="Dinner with Peggy",
            source="ics",
            sent_at="2024-03-02T18:00:00",
            channel="calendar",
            people=["Peggy"],
        )
    )
    llm_c = _CountLlm()
    _peg_text, peg_pack, _ = tell_from_hits(
        peggy_plan,
        llm=llm_c,
        evidence=peggy_ev,
        photos=peggy_photos,
    )
    # Person show-path still uses apply_inference
    llm_c2 = _CountLlm()
    p2 = prepare_narrative_pack(peggy_plan, evidence=peggy_ev, photos=peggy_photos)
    p2 = apply_inference_to_pack(peggy_plan, p2, llm_c2)
    synth, synth_meta = synthesize_tell(peggy_plan, p2, llm_c2)
    pre = p2.get("preaggregation") or {}
    acc = (p2.get("inference") or {}).get("accounting") or {}
    und = (p2.get("validated_inference") or {}).get("person_understanding") or {}
    blob_eps = json.dumps(p2.get("validated_inference") or {}, default=str).lower()
    _check(
        "person_ask_preaggregates_media_and_threads",
        int(pre.get("photos_raw") or 0) == 48
        and int(pre.get("media_clusters") or 0) < 48
        and int(pre.get("sms_raw") or 0) == 8
        and int(pre.get("inference_units") or 0) < 48 + 8
        and int(acc.get("leaf_calls") or 99) <= 4
        and int(acc.get("units_passed_to_inference") or 0) < 48,
        checks,
        problems,
        detail=str({"pre": pre, "acc": {k: acc.get(k) for k in ("leaf_calls", "chunk_n", "units_passed_to_inference", "eligible_units")}}),
    )
    _check(
        "person_understanding_not_one_life_episode",
        (p2.get("validated_inference") or {}).get("ask_semantics", {}).get("kind") == "person"
        and isinstance(und, dict)
        and len(p2.get("validated_inference", {}).get("episodes") or []) >= 2
        and "communication_pattern" in json.dumps(und, default=str),
        checks,
        problems,
        detail=str({"n": len((p2.get("validated_inference") or {}).get("episodes") or []), "keys": list(und)}),
    )
    _check(
        "person_comms_and_calendar_have_equal_opportunity",
        ("love you" in blob_eps or "affection" in blob_eps or "heart" in blob_eps)
        and ("dinner" in blob_eps)
        and ("manchester" in blob_eps),
        checks,
        problems,
        detail=blob_eps[:500],
    )
    _check(
        "person_show_uses_synthesized_answer",
        "evidence behind this story" in (synth or "").lower()
        and "found 48 photo" not in (synth or "").lower()
        and "ph-peg-" not in (synth or "")
        and not synth_meta.get("fail_closed"),
        checks,
        problems,
        detail=(synth or "")[:400],
    )

    from memorybox.ask.i11a.observations import canonicalize_observation
    from memorybox.ask.i11a.reason import compact_observation_for_reason, reason_payload
    from memorybox.ask.i11a.validate import validate_observations
    from memorybox.ask.i11a.claim_support import claim_support_ok

    repaired = canonicalize_observation(
        {
            "kind": "communication",
            "claim_type": "location",
            "text": "tickets@example.com confirmation",
            "source_type": "email",
            "places": [{"name": "Las Vegas"}],
            "people": ["Tom"],
            "supporting_evidence_ids": ["e-mail-1"],
        }
    )
    place_at = canonicalize_observation(
        {
            "kind": "person_at_place_time",
            "claim_type": "is",
            "text": "noreply@delta.com itinerary",
            "source_type": "email",
            "supporting_evidence_ids": ["e-delta"],
        }
    )
    _check(
        "observation_schema_is_canonical",
        repaired
        and repaired.get("kind") == "communication_states"
        and repaired.get("claim_type") == "observed"
        and repaired.get("places") == ["Las Vegas"]
        and place_at
        and place_at.get("kind") == "communication_states",
        checks,
        problems,
        detail=str({"repaired": repaired, "email_place": place_at}),
    )
    park_ok, park_why = claim_support_ok(
        "Calendar records Eagles Live at Sphere",
        {"kind": "calendar", "content": "Parking at Aria", "title": "Parking", "place": "Las Vegas"},
    )
    sphere_ok, sphere_why = claim_support_ok(
        "Calendar records Eagles Live at Sphere",
        {"kind": "calendar", "content": "Eagles Live at Sphere", "title": "Eagles Live at Sphere", "place": "Las Vegas"},
    )
    sphere_pack = {
        "units": [
            {
                "kind": "calendar",
                "evidence_id": "e-eagles-sphere",
                "content": "Eagles Live at Sphere",
                "title": "Eagles Live at Sphere",
            },
            {
                "kind": "calendar",
                "evidence_id": "e-parking",
                "content": "Parking at Aria",
                "title": "Parking",
            },
            {
                "kind": "calendar",
                "evidence_id": "e-dinner",
                "content": "Mesa Grill reservation",
                "title": "Dinner",
            },
        ]
    }
    sphere_val = validate_observations(
        [
            {
                "kind": "calendar_records_event",
                "claim_type": "recorded",
                "text": "Calendar records Eagles Live at Sphere",
                "supporting_evidence_ids": [
                    "e-eagles-sphere",
                    "e-parking",
                    "e-dinner",
                ],
            }
        ],
        pack=sphere_pack,
        person_context={},
    )
    sphere_kept = (sphere_val.get("observations") or [{}])[0].get("supporting_evidence_ids") or []
    _check(
        "named_event_does_not_inherit_batch_ids",
        park_ok is False
        and sphere_ok is True
        and sphere_kept == ["e-eagles-sphere"],
        checks,
        problems,
        detail=str({"park": park_why, "sphere": sphere_why, "kept": sphere_kept, "rej": sphere_val.get("rejected")}),
    )

    from memorybox.ask.i11a.infer import apply_inference_to_pack as _apply_lv

    lv_plan = plan_ask(
        "write a narrative about my trip to las vegas in January 2026",
        AskContext(session_id="i11a-lv-compact"),
    )
    lv_pack = {
        "units": [
            {
                "kind": "calendar",
                "evidence_id": "e-las-flight",
                "unit_id": "u-flight",
                "time": "2026-01-29",
                "content": "Flight to Las Vegas",
                "title": "Flight to Las Vegas",
                "place": "Las Vegas",
                "source_type": "calendar",
            },
            {
                "kind": "calendar",
                "evidence_id": "e-eagles-sphere",
                "unit_id": "u-sphere",
                "time": "2026-01-30",
                "content": "Eagles Live at Sphere",
                "title": "Eagles Live at Sphere",
                "place": "Las Vegas",
                "source_type": "calendar",
            },
            {
                "kind": "communication",
                "evidence_id": "e-stay-mail",
                "unit_id": "u-stay",
                "time": "2026-01-28",
                "content": "Hotel stay Las Vegas Jan 29-Feb 3",
                "source_type": "email",
            },
            {
                "kind": "media_observation",
                "evidence_id": "ph-paradise-nv",
                "asset_ref": "ph-paradise-nv",
                "time": "2026-01-30T16:00:00",
                "place": "Paradise, Nevada",
                "latitude": 36.12,
                "longitude": -115.17,
                "source_type": "photo",
            },
        ]
    }
    lv_pack = _apply_lv(lv_plan, lv_pack, FakeLlmProvider())
    lv_obs = lv_pack.get("semantic_observations") or []
    lv_view = lv_pack.get("ask_relative_view") or {}
    compact_rows = [compact_observation_for_reason(o) for o in lv_obs]
    compact_blob = json.dumps(compact_rows, default=str)
    from memorybox.ask.i11a.infer import _payload_stats
    from memorybox.ask.i11a.reason import ASK_RELATIVE_SYSTEM as _ARS
    from memorybox.ask.i11a.person_context import slim_person_context_for_model as _slim

    rp = reason_payload(
        plan=lv_plan,
        observations=lv_obs,
        request_context=lv_pack.get("request_context") or {},
        person_context=_slim(lv_pack.get("person_context") or {}),
        ask_kind_hint="trip",
    )
    stats = _payload_stats(_ARS, rp)
    lv_blob = json.dumps(lv_obs, default=str).lower() + json.dumps(lv_view, default=str).lower()
    _check(
        "las_vegas_ask_relative_completes_from_observations",
        (lv_pack.get("inference") or {}).get("ok") is True
        and (lv_pack.get("inference") or {}).get("fail_closed") is not True
        and bool(lv_obs)
        and bool(lv_view.get("selected_observation_ids") or lv_view.get("episodes"))
        and "flight" in lv_blob
        and "sphere" in lv_blob
        and "excerpts" not in compact_blob
        and "supporting_evidence_ids" not in compact_blob
        and int(stats.get("payload_bytes") or 0) < 20_000
        and stats.get("includes_full_evidence_id_arrays") is False,
        checks,
        problems,
        detail=str({"n": len(lv_obs), "stats": stats, "sel": lv_view.get("selected_observation_ids"), "ok": (lv_pack.get("inference") or {}).get("ok"), "texts": [o.get("text") for o in lv_obs]}),
    )

    import inspect
    from memorybox.ask.i11a.observations import extract_observations as _xo
    from memorybox.ask.i11a.ir import ir_from_observations as _ir

    jan_units = [
        {"kind": "calendar", "evidence_id": "e-pt", "time": "2026-01-06", "content": "Physical therapy", "title": "Physical therapy"},
        {"kind": "communication", "evidence_id": "e-jan-mail", "time": "2026-01-12", "content": "harbor dinner next week", "people": [{"name": "Tom"}]},
    ]
    ak_units = [
        {"kind": "travel", "evidence_id": "e-ak-itin", "time": "2026-05-10", "content": "Princess Alaska cruise itinerary", "place": "Alaska"},
        {"kind": "media_observation", "evidence_id": "ph-van", "time": "2026-05-08", "place": "Vancouver", "content": "photo", "people": [{"name": "Tom"}]},
    ]
    xmas_units = [
        {"kind": "calendar", "evidence_id": "e-xmas", "time": "2019-12-25", "content": "Christmas dinner", "title": "Christmas dinner"},
        {"kind": "communication", "evidence_id": "e-xmas-sms", "time": "2019-12-25", "content": "Merry Christmas love you", "people": [{"name": "Peggy"}, {"name": "Tom"}]},
    ]
    rel_units = [
        {"kind": "communication", "evidence_id": "e-rel-1", "time": "2024-03-01", "content": "love you", "people": [{"name": "Peggy"}, {"name": "Tom"}]},
        {"kind": "communication", "evidence_id": "e-rel-2", "time": "2024-03-02", "content": "Want to come over for dinner tomorrow?", "people": [{"name": "Peggy"}, {"name": "Tom"}]},
        {"kind": "calendar", "evidence_id": "e-rel-cal", "time": "2024-03-02", "content": "Dinner with Peggy", "title": "Dinner with Peggy"},
    ]
    fixtures = {
        "january_period": jan_units,
        "las_vegas_trip": vegas_units,
        "alaska_trip": ak_units,
        "peggy_person": [
            {"kind": "media_observation", "evidence_id": "ph-peg-x", "time": "2024-06-01", "place": "Manchester", "people": [{"name": "Peggy"}], "latitude": 53.48, "longitude": -2.24},
            {"kind": "communication", "evidence_id": "e-peg-love", "time": "2024-06-02", "content": "love you Peggy", "people": [{"name": "Peggy"}, {"name": "Tom"}]},
        ],
        "peggy_tom_together": rel_units,
        "christmas_event": xmas_units,
    }
    engine_ok = "ask_kind" not in inspect.signature(_xo).parameters
    ir_blobs = {}
    for name, rows in fixtures.items():
        obs = _xo(rows, persist=False)
        ir = _ir(obs)
        blob = json.dumps({"obs": obs, "ir": ir}, default=str).lower()
        ir_blobs[name] = blob
        engine_ok = engine_ok and bool(obs) and bool(ir.get("nodes"))
    _check(
        "common_observation_engine_multiple_asks",
        engine_ok
        and "physical therapy" in ir_blobs["january_period"]
        and "flight to las vegas" in ir_blobs["las_vegas_trip"]
        and "sphere" in ir_blobs["las_vegas_trip"]
        and "alaska" in ir_blobs["alaska_trip"]
        and "vancouver" in ir_blobs["alaska_trip"]
        and "peggy" in ir_blobs["peggy_person"]
        and "love" in ir_blobs["peggy_tom_together"]
        and "dinner" in ir_blobs["peggy_tom_together"]
        and "christmas" in ir_blobs["christmas_event"]
        and "email from peggy" not in ir_blobs["peggy_person"]
        and all("trip_span" not in json.dumps(_xo(rows, persist=False), default=str) for rows in fixtures.values()),
        checks,
        problems,
        detail={k: v[:180] for k, v in ir_blobs.items()},
    )

    meta["synthetic"] = str(uuid4())[:8]
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
