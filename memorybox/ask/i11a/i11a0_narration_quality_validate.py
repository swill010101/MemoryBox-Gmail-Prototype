"""Fail-closed mechanical validation for I11A.0 narration-quality v0.3.

Does not prove factual support. Does not rewrite narration.
"""
from __future__ import annotations

import re
from typing import Any

EVIDENCE_REF_RE = re.compile(r"\[(T-\d+-M-\d+)\]")
EVIDENCE_REF_LINE_RE = re.compile(r"^Evidence-ref:\s*(T-\d+-M-\d+)\s*$", re.M)
EVIDENCE_ID_LINE_RE = re.compile(
    r"^Evidence-id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*$",
    re.M | re.I,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
BANNED_UNLESS_EVIDENCED = (
    "palpable excitement",
    "close-knit",
    "heartfelt",
    "joy of giving",
    "efforts paid off",
    "everyone received",
    "love and laughter",
    "resilience",
    "determination",
    "cherished memories",
)


def split_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if not compact:
        return []
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(compact) if part.strip()]


def packet_evidence_refs(packet_text: str) -> list[str]:
    return EVIDENCE_REF_LINE_RE.findall(packet_text or "")


def packet_evidence_ids(packet_text: str) -> list[str]:
    return [item.lower() for item in EVIDENCE_ID_LINE_RE.findall(packet_text or "")]


def refs_in_text(text: str) -> list[str]:
    return EVIDENCE_REF_RE.findall(text or "")


def is_partial_disclosure_sentence(sentence: str, *, boundary_tokens: list[str]) -> bool:
    lowered = sentence.lower()
    if any(token.lower() in lowered for token in boundary_tokens if token and len(token) >= 8):
        return True
    if "covers only" in lowered or "supplied segment" in lowered or "this account covers" in lowered:
        return True
    if "continues" in lowered and ("outside" in lowered or "packet" in lowered):
        return True
    return False


def disclosure_complete(sentences: list[str], *, boundary_tokens: list[str]) -> bool:
    blob = " ".join(sentences).lower()
    covers = "covers only" in blob or "supplied segment" in blob or "this account covers" in blob
    continues = "continues" in blob and ("outside" in blob or "not in the packet" in blob)
    boundary = any(token.lower() in blob for token in boundary_tokens if token and len(str(token)) >= 8)
    return covers and continues and boundary


def sentence_claim_rows(narration: str, packet_text: str) -> list[dict[str, Any]]:
    allowed = set(packet_evidence_refs(packet_text))
    rows: list[dict[str, Any]] = []
    for index, sentence in enumerate(split_sentences(narration), start=1):
        cited = refs_in_text(sentence)
        unknown = [item for item in cited if item not in allowed]
        rows.append(
            {
                "sentence_number": index,
                "exact_text": sentence,
                "cited_evidence_refs": cited,
                "every_cited_ref_exists_in_packet": not unknown,
                "unknown_refs": unknown,
                "has_citation": bool(cited),
                "support": "unreviewed_founder_codex",
                "notes": "Mechanical row only. Does not prove the sentence is factually supported.",
            }
        )
    return rows


def chronology_coverage(narration: str, packet_text: str) -> dict[str, Any]:
    ordered = packet_evidence_refs(packet_text)
    cited = refs_in_text(narration)
    if not ordered:
        return {"ok": False, "reason": "packet_has_no_evidence_refs", "early": [], "middle": [], "late": []}
    n = len(ordered)
    early_set = set(ordered[: max(1, n // 3)])
    late_set = set(ordered[-(max(1, n // 3)) :])
    mid_set = set(ordered) - early_set - late_set
    if not mid_set:
        mid_set = set(ordered[n // 3 : 2 * n // 3] or ordered)
    cited_set = set(cited)
    early = sorted(cited_set & early_set)
    middle = sorted(cited_set & mid_set)
    late = sorted(cited_set & late_set)
    return {
        "ok": bool(early and middle and late),
        "early_cited_refs": early,
        "middle_cited_refs": middle,
        "late_cited_refs": late,
        "packet_ref_count": n,
        "narration_citation_count": len(cited),
    }


def validate_narration_quality(
    *,
    narration: str,
    packet_text: str,
    partial_context: bool,
    partial_boundary_note: str,
    included_boundary_ids: list[str] | tuple[str, ...] = (),
    omitted_boundary_ids: list[str] | tuple[str, ...] = (),
    partial_thread_ids: list[str] | tuple[str, ...] = (),
    done_reason: str | None,
    eval_count: int | None,
    truncate: bool,
    shift: bool,
    prompt_eval_count: int | None,
    configured_num_ctx: int | None,
    predicted_or_actual_prompt_tokens: int | None,
    output_reserve_tokens: int = 2500,
    safety_margin_tokens: int = 1500,
    gpu_resident: bool | None,
    vram_peak_gb: float | None,
    vram_ceiling_gb: float = 22.5,
    unload_recorded: bool | None,
    vram_released: bool | None,
    nonempty_required: bool = True,
) -> dict[str, Any]:
    problems: list[str] = []
    warnings: list[str] = []
    text = narration or ""
    refs = refs_in_text(text)
    allowed = set(packet_evidence_refs(packet_text))
    if nonempty_required and not text.strip():
        problems.append("narration_empty")
    if not refs:
        problems.append("no_citations")
    unknown = sorted({item for item in refs if item not in allowed})
    if unknown:
        problems.append("invented_or_unknown_refs:" + ",".join(unknown))
    rows = sentence_claim_rows(text, packet_text)
    boundary_tokens = [
        *list(included_boundary_ids or ()),
        *list(omitted_boundary_ids or ()),
        *list(partial_thread_ids or ()),
        *(partial_boundary_note or "").replace("=", " ").replace(",", " ").split(),
    ]
    for row in rows:
        if row["has_citation"]:
            continue
        if partial_context and is_partial_disclosure_sentence(row["exact_text"], boundary_tokens=boundary_tokens):
            continue
        problems.append(f"uncited_sentence_{row['sentence_number']}")
    if partial_context:
        if not disclosure_complete([row["exact_text"] for row in rows], boundary_tokens=boundary_tokens):
            problems.append("missing_partial_context_disclosure")
    coverage = chronology_coverage(text, packet_text)
    if not coverage.get("ok"):
        problems.append("coverage_missing_early_middle_or_late_citations")
    if done_reason not in {None, "stop"}:
        problems.append(f"abnormal_done_reason:{done_reason}")
    if truncate:
        problems.append("truncate_true")
    if shift:
        problems.append("shift_true")
    if prompt_eval_count in (None, 0):
        problems.append("full_prompt_not_evaluated")
    if configured_num_ctx and predicted_or_actual_prompt_tokens:
        if int(predicted_or_actual_prompt_tokens) + output_reserve_tokens + safety_margin_tokens > int(
            configured_num_ctx
        ):
            problems.append("reserve_equation_failed")
    if gpu_resident is False:
        problems.append("not_gpu_resident")
    if vram_peak_gb is not None and float(vram_peak_gb) >= float(vram_ceiling_gb):
        problems.append("vram_at_or_above_ceiling")
    if unload_recorded is False:
        problems.append("unload_not_recorded")
    if vram_released is False:
        problems.append("vram_not_released")
    lowered = text.lower()
    for phrase in BANNED_UNLESS_EVIDENCED:
        if phrase in lowered:
            warnings.append(f"banned_phrase_present:{phrase}")
    classification = "narration_quality_validation_failed" if problems else "mechanical_validation_passed"
    return {
        "ok": not problems,
        "classification": classification,
        "problems": problems,
        "warnings": warnings,
        "citation_count": len(refs),
        "unique_cited_refs": sorted(set(refs)),
        "unknown_refs": unknown,
        "coverage": coverage,
        "claim_audit_rows": rows,
        "eval_count": eval_count,
        "done_reason": done_reason,
        "mechanical_validation_does_not_prove_factual_support": True,
    }
