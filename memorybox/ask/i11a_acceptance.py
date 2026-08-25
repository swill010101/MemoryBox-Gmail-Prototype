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
from memorybox.ask.retrieve import EvidenceHit
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
        and "?v=i11a2" in html,
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
        and "Assimilating collections" in orch_py
        and "is-status-ticker" in explore_js
        and "/explore/api/ask-progress" in explore_js,
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
    meta["synthetic"] = str(uuid4())[:8]
    return {"ok": not problems, "checks": checks, "problems": problems, "meta": meta}
