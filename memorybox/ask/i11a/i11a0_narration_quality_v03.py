"""One corrected 27K Qwen B narration-quality confirmation (v0.3).

Not a capacity ladder. Does not start I11A.1, I11A.2, Peggy, A/C, or production narration.
Does not rewrite COMPLETE capacity-run directories or the prior narration-quality bundle.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    I11A0Error,
    InferenceNotAuthorized,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
    estimate_tokens,
)
from memorybox.ask.i11a.i11a0_full_prompt_v4 import QWEN_B_ADVERTISED_CTX, align_ctx
from memorybox.ask.i11a.i11a0_full_prompt_v5 import plan_reserve_aware_run
from memorybox.ask.i11a.i11a0_narration_quality_validate import (
    packet_evidence_refs,
    validate_narration_quality,
)
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT as SYSTEM_PROMPT_V02
from memorybox.ask.i11a.i11a0_prompt import prompt_sha256 as prompt_sha256_v02
from memorybox.ask.i11a.i11a0_prompt_v03 import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    prompt_canonical_text,
    prompt_sha256,
    render_user_message,
)
from memorybox.ask.i11a.i11a0_request_identity import stable_packet_id
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT

EXPERIMENT_ID = "gate3-b-i14-narration-quality-v03-27k-confirm"
EXPECTED_PACKET_SHA256 = "ae0fcbb738dd956282aef23188fd53e703adefed7ba2ee1630a0a653b6ce20d7"
EXPECTED_V02_PROMPT_SHA256 = "c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b"
EXPECTED_V03_PROMPT_SHA256 = "2716689aa039860a465a8ebe3f7e55a0b8aa2a3e75992593e51549e36ea6d851"
PINNED_NUM_CTX = 39424
EXPECTED_DIGEST = PINNED_B_DIGEST
EXPECTED_EVIDENCE_TOKENS = 27054
EXPECTED_EVIDENCE_BYTES = 108216
EXPECTED_MESSAGES = 62
EXPECTED_THREADS = 42
EXPECTED_V02_ACTUAL_COMPLETE_PROMPT_TOKENS = 34806
INCLUDED_BOUNDARY = "93a44b2a-03c9-4f7c-8764-f9855d3b1ccb"
OMITTED_BOUNDARY = "8c2b7377-b841-4be3-8b52-0a34a25a4d43"
PARTIAL_THREAD = "T-0958"
DEFAULT_SOURCE_RUN = (
    REPO_ROOT
    / "docs"
    / "test-output"
    / "i11a0-benchmark"
    / "gate3-b-i14-full-prompt-v5"
    / "runs"
    / "d22f720fd063b6befe09fe02f5ca96f4a5f9693252b8868570f8ee310ec747d9"
)
FLIGHTSIM_SOURCE_RUN = Path(
    r"\\flightsim\FlightSim User\MemoryBox\docs\test-output\i11a0-benchmark"
    r"\gate3-b-i14-full-prompt-v5\runs"
    r"\d22f720fd063b6befe09fe02f5ca96f4a5f9693252b8868570f8ee310ec747d9"
)
DEFAULT_OUT = REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark" / EXPERIMENT_ID
CANDIDATE_A_SHA = "9b0214c086a2ebf97c257b0a8a577a26c5b1ac3ba58e24c236dfcfe97326b512"
CANDIDATE_C_SHA = "6fea966a230552756d711aa7eb9a379cd0cc00e11b682179bbe58d1036275cbd"
CANDIDATE_D_SHA = "889f3e0dccccb61d0a08a706c4ff03c39aea8c5c648709816878b1babb79c2f9"

V02_CANDIDATE_NARRATIONS = {
    "A_coarse": CANDIDATE_A_SHA,
    "B_repeat_1": CANDIDATE_A_SHA,
    "C_repeat_2": CANDIDATE_C_SHA,
    "D_repeat_3": CANDIDATE_D_SHA,
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_source_run(path: Path | str | None = None) -> Path:
    if path:
        candidate = Path(path)
        if (candidate / "evidence_packet.txt").is_file():
            return candidate
        raise I11A0Error(f"source run is missing evidence_packet.txt: {candidate}")
    for candidate in (DEFAULT_SOURCE_RUN, FLIGHTSIM_SOURCE_RUN):
        if (candidate / "evidence_packet.txt").is_file():
            return candidate
    raise I11A0Error("accepted 27K COMPLETE run is not available on this machine")


def load_accepted_27k_packet(source_run: Path) -> dict[str, Any]:
    evidence = (source_run / "evidence_packet.txt").read_text(encoding="utf-8")
    manifest = json.loads((source_run / "packet_manifest.json").read_text(encoding="utf-8"))
    packet_sha = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    if packet_sha != EXPECTED_PACKET_SHA256:
        raise I11A0Error(f"source packet sha mismatch: {packet_sha}")
    if packet_sha != manifest.get("packet_sha256"):
        raise I11A0Error("manifest packet_sha256 does not match evidence_packet.txt")
    if int(manifest.get("estimated_evidence_tokens") or 0) != EXPECTED_EVIDENCE_TOKENS:
        raise I11A0Error("estimated_evidence_tokens mismatch")
    if int(manifest.get("evidence_bytes") or 0) != EXPECTED_EVIDENCE_BYTES:
        raise I11A0Error("evidence_bytes mismatch")
    if int(manifest.get("message_count") or 0) != EXPECTED_MESSAGES:
        raise I11A0Error("message_count mismatch")
    if int(manifest.get("conversation_count") or 0) != EXPECTED_THREADS:
        raise I11A0Error("thread_count mismatch")
    if not manifest.get("partial_context"):
        raise I11A0Error("accepted 27K packet must be partial_context true")
    return {
        "source_run": str(source_run),
        "text": evidence,
        "manifest": manifest,
        "sha256": packet_sha,
        "evidence_ids": list(manifest.get("evidence_ids") or []),
        "partial_context": True,
        "partial_boundary_note": str(manifest.get("partial_boundary_note") or ""),
        "partial_thread_ids": list(manifest.get("partial_thread_ids") or []),
        "included_boundary_evidence_ids": list(manifest.get("included_boundary_evidence_ids") or []),
        "omitted_boundary_evidence_ids": list(manifest.get("omitted_boundary_evidence_ids") or []),
        "time_start": manifest.get("time_start"),
        "time_end": manifest.get("time_end"),
        "evidence_bytes": int(manifest.get("evidence_bytes") or len(evidence.encode("utf-8"))),
        "estimated_evidence_tokens": int(manifest.get("estimated_evidence_tokens") or 0),
        "message_count": int(manifest.get("message_count") or 0),
        "thread_count": int(manifest.get("conversation_count") or 0),
        "evidence_refs": packet_evidence_refs(evidence),
    }


def build_user_message(packet: dict[str, Any]) -> str:
    return render_user_message(
        packet_id=stable_packet_id(packet["sha256"]),
        packet_role="narration_quality_confirmation",
        time_start=str(packet.get("time_start") or ""),
        time_end=str(packet.get("time_end") or ""),
        partial_context=True,
        partial_boundary_note=str(packet.get("partial_boundary_note") or ""),
        evidence_ids=list(packet.get("evidence_ids") or []),
        evidence_text=packet["text"],
    )


def plan_complete_revised_request(packet: dict[str, Any], user: str) -> dict[str, Any]:
    complete_prompt = SYSTEM_PROMPT + "\n" + user
    request_bytes_div4 = estimate_tokens(complete_prompt)
    system_delta = estimate_tokens(SYSTEM_PROMPT) - estimate_tokens(SYSTEM_PROMPT_V02)
    from_measured_27k = EXPECTED_V02_ACTUAL_COMPLETE_PROMPT_TOKENS + max(0, system_delta)
    v5_bytes_plan = plan_reserve_aware_run(evidence_bytes=int(packet["evidence_bytes"]))
    from_v5 = int(v5_bytes_plan.get("predicted_complete_prompt_tokens") or 0)
    estimated_complete = max(request_bytes_div4, from_measured_27k, from_v5)
    minimum = estimated_complete + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    planned_num_ctx = align_ctx(minimum)
    reserve_ok = estimated_complete + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS <= planned_num_ctx
    model_ok = planned_num_ctx <= int(QWEN_B_ADVERTISED_CTX)
    eligible = reserve_ok and model_ok
    reason = None
    if not model_ok:
        reason = "planned_ctx_exceeds_model_limit"
    elif not reserve_ok:
        reason = "reserves_not_satisfied"
    return {
        "planner": "max(request_bytes_div4, v5_evidence_bytes_predicted, measured_27k_v02_complete_plus_system_delta)",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "v02_prompt_sha256_unchanged": prompt_sha256_v02(),
        "system_bytes": len(SYSTEM_PROMPT.encode("utf-8")),
        "v02_system_bytes": len(SYSTEM_PROMPT_V02.encode("utf-8")),
        "user_bytes": len(user.encode("utf-8")),
        "complete_prompt_bytes": len(complete_prompt.encode("utf-8")),
        "request_bytes_div4_tokens": request_bytes_div4,
        "system_prompt_delta_tokens": system_delta,
        "measured_27k_v02_complete_plus_system_delta": from_measured_27k,
        "estimated_complete_prompt_tokens": estimated_complete,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "minimum_num_ctx_for_reserves": minimum,
        "planned_num_ctx": planned_num_ctx,
        "model_context_limit": int(QWEN_B_ADVERTISED_CTX),
        "reserve_check": reserve_ok,
        "model_context_check": model_ok,
        "eligible": eligible,
        "rejection_reason": reason,
        "do_not_shrink_evidence": True,
        "v5_bytes_planner_comparison_only": {
            "predicted_complete_prompt_tokens": v5_bytes_plan.get("predicted_complete_prompt_tokens"),
            "planned_num_ctx": v5_bytes_plan.get("planned_num_ctx"),
            "note": "v5 evidence-byte prediction is an envelope, not a substitute for shrinking evidence.",
        },
        "truncate": False,
        "shift": False,
        "temperature": 0.1,
        "seed": 42,
        "think": False,
        "digest": EXPECTED_DIGEST,
        "tag": "qwen3:14b-q8_0",
        "maximum_vram_gb": VRAM_CEILING_GB,
    }


def build_request_json(user: str, num_ctx: int) -> dict[str, Any]:
    return {
        "model": "qwen3:14b-q8_0",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "think": False,
        "keep_alive": "2m",
        "truncate": False,
        "shift": False,
        "options": {
            "num_ctx": int(num_ctx),
            "num_predict": OUTPUT_RESERVE_TOKENS,
            "temperature": 0.1,
            "seed": 42,
        },
    }


def request_body_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_confirmation_identity(packet: dict[str, Any], user: str, plan: dict[str, Any]) -> None:
    if prompt_sha256() != EXPECTED_V03_PROMPT_SHA256:
        raise I11A0Error(f"prompt v0.3 sha mismatch: {prompt_sha256()}")
    if packet["sha256"] != EXPECTED_PACKET_SHA256:
        raise I11A0Error(f"packet sha mismatch: {packet['sha256']}")
    if int(plan.get("planned_num_ctx") or 0) != PINNED_NUM_CTX:
        raise I11A0Error(f"planned_num_ctx {plan.get('planned_num_ctx')} is not {PINNED_NUM_CTX}")
    header = user.split("===== EVIDENCE =====", 1)[0]
    if "\npartial_context: yes\n" not in user:
        raise I11A0Error("user wrapper partial_context is not yes")
    if stable_packet_id(packet["sha256"]) not in header:
        raise I11A0Error("stable content-derived packet_id missing from wrapper")
    if "cold-" in header or "repeat" in header.lower():
        raise I11A0Error("unstable repetition identity leaked into the model-visible wrapper")
    if INCLUDED_BOUNDARY not in header or OMITTED_BOUNDARY not in header:
        raise I11A0Error("partial-context boundary evidence ids missing from wrapper")


def load_ops(path: Path | str | None = None) -> dict[str, Any]:
    ops_path = Path(path) if path else REPO_ROOT / "docs" / "ops" / "i11a0.b.narration-quality-v03-27k.json"
    return json.loads(ops_path.read_text(encoding="utf-8"))


def prove_narration_quality_v03_offline(*, source_run: Path | str | None = None) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    from memorybox.ask.i11a.i11a0_smoke import _chat, _unload, require_qwen_smoke_configuration

    ok("live_imports_resolve", callable(_chat) and callable(_unload) and callable(require_qwen_smoke_configuration), None)
    ok("v02_prompt_unchanged", prompt_sha256_v02() == EXPECTED_V02_PROMPT_SHA256, prompt_sha256_v02())
    ok("v03_prompt_sha_pinned", prompt_sha256() == EXPECTED_V03_PROMPT_SHA256, prompt_sha256())
    ok("v03_version_label", PROMPT_VERSION == "i11a0-narration-v0.3-candidate", PROMPT_VERSION)
    packet_available = False
    planning: dict[str, Any] = {}
    try:
        source = resolve_source_run(source_run)
        packet = load_accepted_27k_packet(source)
        packet_available = True
        ok("packet_sha", packet["sha256"] == EXPECTED_PACKET_SHA256, packet["sha256"])
        ok("partial_thread", PARTIAL_THREAD in packet["partial_thread_ids"], packet["partial_thread_ids"])
        ok("included_boundary", INCLUDED_BOUNDARY in packet["included_boundary_evidence_ids"], None)
        ok("omitted_boundary", OMITTED_BOUNDARY in packet["omitted_boundary_evidence_ids"], None)
        user = build_user_message(packet)
        ok("user_partial_context_yes", "\npartial_context: yes\n" in user, user.split("=====", 1)[0])
        ok("user_has_boundary_note", INCLUDED_BOUNDARY in user and OMITTED_BOUNDARY in user, None)
        ok("user_has_no_cold_suffix", "cold-1" not in user and "cold-2" not in user and "cold-3" not in user, None)
        ok("user_packet_id_is_content_hash", stable_packet_id(packet["sha256"]) in user, None)
        repeat_user = build_user_message(packet)
        ok("repeat_user_byte_identical", user == repeat_user, None)
        payload_a = build_request_json(user, 39424)
        payload_b = build_request_json(repeat_user, 39424)
        ok("repeat_request_bodies_byte_identical", request_body_sha256(payload_a) == request_body_sha256(payload_b), None)
        planning = plan_complete_revised_request(packet, user)
        ok("planning_reported", "planned_num_ctx" in planning, planning)
        require_confirmation_identity(packet, user, planning)
        ok("confirmation_identity_gate", True, None)
        if not planning.get("eligible"):
            ok("ineligible_stops_before_inference", planning.get("rejection_reason") is not None, planning)
        else:
            ok("planned_num_ctx_is_39424", planning.get("planned_num_ctx") == PINNED_NUM_CTX, planning.get("planned_num_ctx"))
            ok(
                "reserve_equation_on_revised_request",
                planning["estimated_complete_prompt_tokens"] + 2500 + 1500 <= planning["planned_num_ctx"],
                planning,
            )
    except I11A0Error as exc:
        ok("accepted_27k_packet_available", False, str(exc))

    fake_packet = (
        "Evidence-ref: T-0106-M-01\nEvidence-id: 992d6453-3376-425c-a62b-fa05db1b4a3e\n\n"
        "Evidence-ref: T-0333-M-01\nEvidence-id: 54e1bfd3-820c-4ba5-8724-b4212bc5bb88\n\n"
        "Evidence-ref: T-0958-M-01\nEvidence-id: 93a44b2a-03c9-4f7c-8764-f9855d3b1ccb\n"
    )
    good = (
        "On 10 December 2005 Peg forwarded a Christmas wish list [T-0106-M-01]. "
        "In November 2006 she wrote about Christmas shopping [T-0333-M-01]. "
        "A later 2007 message is in the supplied segment [T-0958-M-01]. "
        "This account covers only the supplied segment. Part of thread T-0958 continues outside the packet. "
        f"The cut is identified by included {INCLUDED_BOUNDARY} and omitted {OMITTED_BOUNDARY}."
    )
    passed = validate_narration_quality(
        narration=good,
        packet_text=fake_packet,
        partial_context=True,
        partial_boundary_note=f"included={INCLUDED_BOUNDARY} omitted={OMITTED_BOUNDARY}",
        included_boundary_ids=[INCLUDED_BOUNDARY],
        omitted_boundary_ids=[OMITTED_BOUNDARY],
        partial_thread_ids=[PARTIAL_THREAD],
        done_reason="stop",
        eval_count=900,
        truncate=False,
        shift=False,
        prompt_eval_count=34806,
        configured_num_ctx=39424,
        predicted_or_actual_prompt_tokens=34806,
        gpu_resident=True,
        vram_peak_gb=21.9,
        unload_recorded=True,
        vram_released=True,
    )
    ok("validator_accepts_cited_coverage", passed["ok"] is True, passed.get("problems"))
    bad = "Peg was filled with palpable excitement and everyone received gifts."
    failed = validate_narration_quality(
        narration=bad,
        packet_text=fake_packet,
        partial_context=True,
        partial_boundary_note=f"included={INCLUDED_BOUNDARY} omitted={OMITTED_BOUNDARY}",
        included_boundary_ids=[INCLUDED_BOUNDARY],
        omitted_boundary_ids=[OMITTED_BOUNDARY],
        partial_thread_ids=[PARTIAL_THREAD],
        done_reason="stop",
        eval_count=40,
        truncate=False,
        shift=False,
        prompt_eval_count=34806,
        configured_num_ctx=39424,
        predicted_or_actual_prompt_tokens=34806,
        gpu_resident=True,
        vram_peak_gb=21.9,
        unload_recorded=True,
        vram_released=True,
    )
    ok(
        "validator_fails_uncited_and_missing_disclosure",
        failed["ok"] is False and failed["classification"] == "narration_quality_validation_failed",
        failed.get("problems"),
    )
    invented = "Peg bought a spaceship. [T-9999-M-01]"
    inv = validate_narration_quality(
        narration=invented + " This account covers only the supplied segment. Part of thread T-0958 continues outside the packet. "
        f"The cut is identified by {INCLUDED_BOUNDARY}.",
        packet_text=fake_packet,
        partial_context=True,
        partial_boundary_note=f"included={INCLUDED_BOUNDARY}",
        included_boundary_ids=[INCLUDED_BOUNDARY],
        omitted_boundary_ids=[OMITTED_BOUNDARY],
        partial_thread_ids=[PARTIAL_THREAD],
        done_reason="stop",
        eval_count=20,
        truncate=False,
        shift=False,
        prompt_eval_count=100,
        configured_num_ctx=40960,
        predicted_or_actual_prompt_tokens=100,
        gpu_resident=True,
        vram_peak_gb=20.0,
        unload_recorded=True,
        vram_released=True,
    )
    ok("validator_rejects_unknown_ref", any("unknown_refs" in p or "invented" in p for p in inv["problems"]), inv["problems"])
    ops = load_ops()
    ok("ops_inference_authorized_is_bool", isinstance(ops.get("inference_authorized"), bool), ops.get("inference_authorized"))
    ok("ops_not_a_ladder", ops.get("capacity_ladder") is False, ops)
    ok("i11a1_false", ops.get("i11a1") is False and ops.get("peggy_scenario") is False, ops)
    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "inference_started": False,
        "i11a1_started": False,
        "ladder_resumed": False,
        "packet_available": packet_available,
        "prompt_v03_sha256": prompt_sha256(),
        "prompt_v02_sha256": prompt_sha256_v02(),
        "planning": planning,
        "experiment_id": EXPERIMENT_ID,
    }


def write_pre_inference_package(out_dir: Path, packet: dict[str, Any], user: str, plan: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_request_json(user, int(plan["planned_num_ctx"]))
    (out_dir / "prompt_v03.txt").write_text(prompt_canonical_text(), encoding="utf-8", newline="\n")
    (out_dir / "prompt_v03_hashes.json").write_text(
        json.dumps(
            {
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": prompt_sha256(),
                "system_sha256": _sha256_text(SYSTEM_PROMPT),
                "v02_retained_sha256": prompt_sha256_v02(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "user_wrapper.txt").write_text(user.split("===== EVIDENCE =====", 1)[0], encoding="utf-8", newline="\n")
    (out_dir / "packet_identity.json").write_text(
        json.dumps(
            {
                "packet_sha256": packet["sha256"],
                "stable_packet_id": stable_packet_id(packet["sha256"]),
                "estimated_evidence_tokens": packet["estimated_evidence_tokens"],
                "evidence_bytes": packet["evidence_bytes"],
                "message_count": packet["message_count"],
                "thread_count": packet["thread_count"],
                "partial_context": True,
                "partial_thread_ids": packet["partial_thread_ids"],
                "included_boundary_evidence_ids": packet["included_boundary_evidence_ids"],
                "omitted_boundary_evidence_ids": packet["omitted_boundary_evidence_ids"],
                "source_run": packet["source_run"],
                "source_not_rewritten": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    capture = {
        "request_json": payload,
        "request_body_sha256": request_body_sha256(payload),
        "user_sha256": _sha256_text(user),
        "system_sha256": _sha256_text(SYSTEM_PROMPT),
        "repeat_identity_note": "A second render of the same packet must match request_body_sha256.",
    }
    (out_dir / "planned_request_capture.json").write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "context_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "comparison_with_candidates_ad.md").write_text(
        "\n".join(
            [
                "# Comparison with v0.2 Candidates A–D",
                "",
                "Capacity success (27K Qwen B hardware/context) is already accepted and is not reopened here.",
                "v0.2 Candidates A–D failed narration quality: zero citations, unsupported emotion/significance,",
                "plans as completed events, Christmas-2006 compression, omitted clusters, no partial-context disclosure,",
                "too short, and incomplete repeatability (A=B; C and D differ).",
                "",
                f"- A/B narration sha256: `{CANDIDATE_A_SHA}`",
                f"- C narration sha256: `{CANDIDATE_C_SHA}`",
                f"- D narration sha256: `{CANDIDATE_D_SHA}`",
                "",
                "This experiment uses prompt v0.3, a truthful partial_context wrapper, and a content-derived packet_id.",
                "After the authorized confirmation, score separately: capacity success, mechanical prompt compliance,",
                "factual fidelity, prose/narrative quality, and repeatability (one shot; repeats are not part of this command).",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "founder_score_sheet.md").write_text(
        "\n".join(
            [
                "# Founder score sheet — v0.3 27K confirmation",
                "",
                "Score the confirmation narration, not a full Peggy biography.",
                "",
                "| Criterion | Score 1–5 | Notes |",
                "| --- | --- | --- |",
                "| I trust the facts. |  |  |",
                "| I recognize the people and events. |  |  |",
                "| The narrative is clear and readable. |  |  |",
                "| The narrative feels human without inventing emotion. |  |  |",
                "| The amount of detail feels right. |  |  |",
                "| The story emphasizes what matters. |  |  |",
                "| Citations are useful without disrupting the prose. |  |  |",
                "| Partial context is disclosed honestly. |  |  |",
                "| I would be comfortable sharing this with family. |  |  |",
                "| Good enough as a Qwen B narration foundation. |  |  |",
                "",
                "Disposition: [ ] Accept Qwen B narration foundation  [ ] Revise again  [ ] Move to a finalist comparison",
                "",
                "Do not start Words of Life from this sheet unless the confirmation meets the decision rule.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    lines = ["# Pre-inference HASHES", ""]
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "HASHES.txt"):
        lines.append(f"{_sha256_file(path)}  {path.relative_to(out_dir).as_posix()}")
    (out_dir / "HASHES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"ok": True, "out": str(out_dir), "models_called": False, "eligible": plan.get("eligible")}


def run_narration_quality_v03(
    *,
    confirm_benchmark: bool,
    config_path: Path | str | None = None,
    source_run: Path | str | None = None,
    results_dir: Path | str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    ops = load_ops(config_path)
    source = resolve_source_run(source_run)
    packet = load_accepted_27k_packet(source)
    user = build_user_message(packet)
    plan = plan_complete_revised_request(packet, user)
    out = Path(results_dir) if results_dir else DEFAULT_OUT
    written = write_pre_inference_package(out / "preflight", packet, user, plan)
    payload = {
        "ok": bool(plan.get("eligible")),
        "experiment_id": EXPERIMENT_ID,
        "models_called": False,
        "inference_started": False,
        "i11a1_started": False,
        "capacity_ladder": False,
        "planning": plan,
        "preflight_dir": written.get("out"),
        "ops_inference_authorized": bool(ops.get("inference_authorized")),
        "confirm_benchmark": bool(confirm_benchmark),
        "stopped_before_inference": True,
    }
    if not plan.get("eligible"):
        payload["reason"] = plan.get("rejection_reason")
        payload["do_not_shrink_evidence"] = True
        return payload
    if not confirm_benchmark or not ops.get("inference_authorized"):
        payload["authorization"] = "awaiting_founder_before_ollama"
        return payload
    return run_live_confirmation(
        confirm_benchmark=True,
        config_path=config_path,
        source_run=source,
        results_dir=out,
        ollama_base_url=ollama_base_url,
    )


def assemble_review_package(
    out: Path,
    run_dir: Path,
    packet: dict[str, Any],
    user: str,
    plan: dict[str, Any],
    rec: dict[str, Any],
    validation: dict[str, Any],
    narration: str,
) -> Path:
    review = out / "review"
    review.mkdir(parents=True, exist_ok=True)
    for name in (
        "narration.txt",
        "request_capture.json",
        "raw_api.jsonl",
        "token_accounting.json",
        "telemetry.jsonl",
        "citation_validation.json",
        "chronology_coverage.json",
        "claim_audit.json",
        "log_correlation.json",
        "safety_checks.json",
        "run_record.json",
        "user_wrapper.txt",
    ):
        src = run_dir / name
        if src.is_file():
            shutil.copy2(src, review / name)
    (review / "canonical_narration.md").write_text(
        "---\n"
        f"execution_id: {rec.get('execution_id')}\n"
        f"narration_sha256: {_sha256_text(narration)}\n"
        f"classification: {rec.get('classification')}\n"
        "---\n\n"
        + (narration or "")
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (review / "packet_identity.json").write_text(
        json.dumps(
            {
                "packet_sha256": packet["sha256"],
                "stable_packet_id": stable_packet_id(packet["sha256"]),
                "partial_context": True,
                "included": packet.get("included_boundary_evidence_ids"),
                "omitted": packet.get("omitted_boundary_evidence_ids"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (review / "context_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
    (review / "README.md").write_text(
        "\n".join(
            [
                "# 27K Qwen B narration-quality v0.3 confirmation",
                "",
                f"Classification: `{rec.get('classification')}`",
                f"Execution: `{rec.get('execution_id')}`",
                "One confirmation. Not a ladder. Narration was not auto-repaired.",
                "",
                "Score capacity/hardware, wrapper compliance, citations, fidelity, coverage,",
                "plan vs completed events, emotion/significance, partial-context disclosure,",
                "and prose separately. See founder_assessment.md after the run is reviewed.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = ["# Review package HASHES", ""]
    for path in sorted(p for p in review.rglob("*") if p.is_file() and p.name != "HASHES.txt"):
        lines.append(f"{_sha256_file(path)}  {path.relative_to(review).as_posix()}")
    (review / "HASHES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return review


def run_live_confirmation(
    *,
    confirm_benchmark: bool,
    config_path: Path | str | None = None,
    source_run: Path | str | None = None,
    results_dir: Path | str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    """FlightSim-only path. Requires ops inference_authorized true and --confirm-benchmark."""
    from memorybox.ask.i11a.i11a0_benchmark import ModelSpec, RunRequest, new_execution_id
    from memorybox.ask.i11a.i11a0_host import HardwareSampler, collect_host_affinity_preflight, require_flightsim_host_affinity
    from memorybox.ask.i11a.i11a0_placement import interpret_ollama_placement, read_ollama_ps
    from memorybox.ask.i11a.i11a0_ollama_log_cursor import classify_appended_log, snapshot_log
    from memorybox.ask.i11a.i11a0_benchmark import inventory_installed_models
    from memorybox.ask.i11a.i11a0_smoke import _chat, _unload, require_qwen_smoke_configuration

    ops = load_ops(config_path)
    if not confirm_benchmark:
        raise InferenceNotAuthorized("pass --confirm-benchmark")
    if not ops.get("inference_authorized"):
        raise InferenceNotAuthorized("ops inference_authorized is false")
    source = resolve_source_run(source_run)
    packet = load_accepted_27k_packet(source)
    user = build_user_message(packet)
    plan = plan_complete_revised_request(packet, user)
    out = Path(results_dir) if results_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    write_pre_inference_package(out / "preflight", packet, user, plan)
    require_confirmation_identity(packet, user, plan)
    if not plan.get("eligible"):
        return {
            "ok": False,
            "stopped_before_inference": True,
            "reason": plan.get("rejection_reason"),
            "planning": plan,
            "models_called": False,
        }
    preflight = collect_host_affinity_preflight(
        ollama_base_url=ollama_base_url,
        output_path=out,
        chunks_path=REPO_ROOT / "docs" / "test-output",
        repo=REPO_ROOT,
    )
    require_flightsim_host_affinity(preflight)
    inventory = inventory_installed_models(base_url=ollama_base_url)
    spec = ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", EXPECTED_DIGEST)
    by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
    row = by_tag.get(spec.tag) or {}
    require_qwen_smoke_configuration(spec, row)
    request = RunRequest(
        model_tag=spec.tag,
        digest=EXPECTED_DIGEST,
        requested_evidence_tokens=EXPECTED_EVIDENCE_TOKENS,
        evidence_sha256=packet["sha256"],
        evidence_text=packet["text"],
        repetition=1,
        warm_or_cold="cold",
        confirmation=True,
        thinking_mode="off",
        seed=42,
        num_ctx=PINNED_NUM_CTX,
        reserved_output_tokens=OUTPUT_RESERVE_TOKENS,
        prompt_sha256=prompt_sha256(),
        time_start=str(packet.get("time_start") or ""),
        time_end=str(packet.get("time_end") or ""),
        partial_context=True,
        partial_boundary_note=str(packet.get("partial_boundary_note") or ""),
        evidence_ids=tuple(packet.get("evidence_ids") or ()),
        model_visible_packet_id=stable_packet_id(packet["sha256"]),
    )
    request.num_ctx = PINNED_NUM_CTX
    sampler = HardwareSampler()
    sampler.capture("baseline")
    loaded_ps: dict[str, Any] = {}

    def on_first_token() -> None:
        loaded_ps["payload"] = read_ollama_ps(ollama_base_url)
        loaded_ps["interpreted"] = interpret_ollama_placement(
            loaded_ps["payload"],
            tag=spec.tag,
            digest=spec.digest,
            queried_while_loaded=True,
        )

    log_before = snapshot_log(
        execution_id="",
        model_tag=spec.tag,
        digest=spec.digest,
        num_ctx=PINNED_NUM_CTX,
    )
    measurement, narration, events, capture = _chat(
        request,
        base_url=ollama_base_url,
        timeout=int(ops.get("timeout_seconds") or 1800),
        sampler=sampler,
        packet_role="narration_quality_confirmation",
        keep_alive="2m",
        system_text=SYSTEM_PROMPT,
        user_text=user,
        on_first_token=on_first_token,
    )
    sampler.capture("pre_unload")
    unload_s = _unload(ollama_base_url, spec.tag)
    sampler.capture("after_unload")
    last = events[-1] if events else {}
    vram_vals = sampler.vram_used_values()
    peak = max(vram_vals) if vram_vals else None
    baseline = vram_vals[0] if vram_vals else None
    final = vram_vals[-1] if vram_vals else None
    placed = loaded_ps.get("interpreted") or {}
    gpu_resident = bool(placed.get("gpu_resident")) if placed else None
    vram_released = None
    if baseline is not None and final is not None:
        vram_released = final <= baseline + 2.0
    pec = measurement.prompt_eval_count or last.get("prompt_eval_count")
    log_verdict = classify_appended_log(
        log_before,
        num_ctx=PINNED_NUM_CTX,
        prompt_eval_count=None if pec is None else int(pec),
        predicted_complete=int(plan.get("estimated_complete_prompt_tokens") or 0),
    )
    safety_problems: list[str] = []
    if capture.get("truncate_top_level") is not False:
        safety_problems.append("truncate_not_false")
    if capture.get("shift_top_level") is not False:
        safety_problems.append("shift_not_false")
    if pec in (None, 0):
        safety_problems.append("full_prompt_not_evaluated")
    elif int(pec) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS > PINNED_NUM_CTX:
        safety_problems.append("reserve_equation_failed")
    if log_verdict.get("truncation_occurred") is True:
        safety_problems.append("log_truncation")
    if gpu_resident is not True:
        safety_problems.append("not_gpu_resident")
    if peak is not None and float(peak) >= 22.5:
        safety_problems.append("vram_ceiling")
    if vram_released is False:
        safety_problems.append("vram_not_released")
    validation = validate_narration_quality(
        narration=narration,
        packet_text=packet["text"],
        partial_context=True,
        partial_boundary_note=str(packet.get("partial_boundary_note") or ""),
        included_boundary_ids=packet.get("included_boundary_evidence_ids") or [],
        omitted_boundary_ids=packet.get("omitted_boundary_evidence_ids") or [],
        partial_thread_ids=packet.get("partial_thread_ids") or [],
        done_reason=str(last.get("done_reason") or ""),
        eval_count=last.get("eval_count"),
        truncate=False,
        shift=False,
        prompt_eval_count=pec,
        configured_num_ctx=PINNED_NUM_CTX,
        predicted_or_actual_prompt_tokens=pec,
        gpu_resident=gpu_resident,
        vram_peak_gb=peak,
        unload_recorded=True,
        vram_released=vram_released,
    )
    execution_id = new_execution_id()
    run_dir = out / "runs" / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "narration.txt").write_text(narration, encoding="utf-8", newline="\n")
    (run_dir / "raw_api.jsonl").write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "request_capture.json").write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "citation_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "chronology_coverage.json").write_text(
        json.dumps(validation.get("coverage") or {}, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (run_dir / "claim_audit.json").write_text(
        json.dumps({"rows": validation.get("claim_audit_rows") or [], "support": "unreviewed_founder_codex"}, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "telemetry.jsonl").write_text(
        "\n".join(json.dumps(sample) for sample in sampler.samples) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "log_correlation.json").write_text(
        json.dumps(log_verdict, indent=2, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    (run_dir / "token_accounting.json").write_text(
        json.dumps(
            {
                "actual_prompt_eval_count": pec,
                "configured_num_ctx": PINNED_NUM_CTX,
                "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
                "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
                "estimated_complete_prompt_tokens": plan.get("estimated_complete_prompt_tokens"),
                "prompt_sha256": prompt_sha256(),
                "packet_sha256": packet["sha256"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "user_wrapper.txt").write_text(user.split("===== EVIDENCE =====", 1)[0], encoding="utf-8", newline="\n")
    (run_dir / "evidence_packet.txt").write_text(packet["text"], encoding="utf-8", newline="\n")
    (run_dir / "safety_checks.json").write_text(
        json.dumps({"ok": not safety_problems, "problems": safety_problems, "retried": False}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    classification = "narration_quality_validation_failed"
    if safety_problems:
        classification = "safety_or_identity_failed"
    elif validation["ok"]:
        classification = "mechanical_validation_passed"
    rec = {
        "ok": (not safety_problems) and bool(validation["ok"]),
        "classification": classification,
        "execution_id": execution_id,
        "models_called": True,
        "planning": plan,
        "unload_seconds": unload_s,
        "measurement": asdict(measurement),
        "i11a1_started": False,
        "capacity_ladder": False,
        "safety_problems": safety_problems,
        "hardware": {
            "vram_peak_gb": peak,
            "gpu_resident": gpu_resident,
            "placement": placed,
            "vram_released": vram_released,
        },
        "log_correlation": {k: v for k, v in log_verdict.items() if k != "segment"},
        "recommendation": (
            "founder_and_codex_review_required"
            if not safety_problems
            else "stop_without_retry"
        ),
    }
    (run_dir / "run_record.json").write_text(json.dumps(rec, indent=2, default=str) + "\n", encoding="utf-8")
    (run_dir / "COMPLETE").write_text("complete\n", encoding="utf-8")
    assemble_review_package(out, run_dir, packet, user, plan, rec, validation, narration)
    return rec
