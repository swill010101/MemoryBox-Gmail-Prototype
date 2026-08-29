"""Phase 3: semantic chunking of a frozen trusted Full-Evidence V2 fixture.

Begin only after both single-pass model runs exist. This module can still
partition a fixture and prove no evidence loss without calling a model.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.full_evidence_diagnostic import estimate_tokens
from memorybox.ask.i11a.full_evidence_l1_chunker import run_l1_chunker
from memorybox.ask.i11a.trusted_full_evidence_v2 import (
    all_fixture_evidence_ids,
    fev2_input_sha256,
    item_evidence_ids,
    validate_fev2_document,
)


def compare_chunked_vs_unchunked(fixture_path: Path | str) -> dict[str, Any]:
    """Partition by semantic units; report loss vs the frozen unchunked item set."""
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    stored = data.get("input_sha256")
    recomputed = fev2_input_sha256(data)
    if stored and stored != recomputed:
        return {
            "ok": False,
            "error": "fixture_hash_mismatch",
            "file": stored,
            "recomputed": recomputed,
        }
    items = list(data.get("items") or [])
    original_ids = all_fixture_evidence_ids(items)
    item_ids = {str(it.get("item_id") or "") for it in items if it.get("item_id")}
    chunked = run_l1_chunker(
        items,
        person_context=data.get("person_context") or {},
        ask=str(data.get("ask") or ""),
    )
    proof = chunked.get("proof") or {}
    chunk_item_ids: set[str] = set()
    for ch in chunked.get("chunks") or []:
        for it in ch.get("items") or []:
            iid = str(it.get("item_id") or "")
            if iid:
                chunk_item_ids.add(iid)
            chunk_item_ids.update(item_evidence_ids(it))
    lost = sorted((item_ids | original_ids) - chunk_item_ids)
    extra = sorted(chunk_item_ids - (item_ids | original_ids))
    units = list(chunked.get("units") or [])
    kinds = Counter(str(u.get("unit_kind") or "other") for u in units)
    seen_in_units: list[str] = []
    dupes: list[str] = []
    for u in units:
        for iid in u.get("item_ids") or []:
            s = str(iid)
            if s in seen_in_units:
                dupes.append(s)
            else:
                seen_in_units.append(s)
    chrono_ok = True
    for u in units:
        item_times = [
            str(it.get("timestamp") or it.get("sent_at") or it.get("start") or "")
            for it in (u.get("items") or [])
        ]
        if item_times != sorted(item_times):
            chrono_ok = False
            break
    unchunked_tokens = int(data.get("estimated_tokens") or 0)
    if not unchunked_tokens:
        unchunked_tokens = estimate_tokens(str(data.get("user_message") or ""))
    chunk_tokens = []
    for ch in chunked.get("chunks") or []:
        text = "\n".join(str(it.get("body") or it.get("text") or "") for it in (ch.get("items") or []))
        chunk_tokens.append(estimate_tokens(text))
    sources = {str(it.get("source") or "") for it in items}
    expected_kinds = []
    if "email" in sources:
        expected_kinds.append("email_thread")
    if "sms" in sources:
        expected_kinds.append("sms_episode")
    if "calendar" in sources:
        expected_kinds.append("calendar_event")
    if "travel" in sources:
        expected_kinds.append("travel")
    missing_kinds = [k for k in expected_kinds if k not in kinds]
    return {
        "ok": bool(proof.get("ok")) and not lost and not dupes and not missing_kinds,
        "input_sha256": stored,
        "unchunked_item_count": len(items),
        "chunk_count": len(chunked.get("chunks") or []),
        "l1_unit_kinds": dict(kinds),
        "evidence_lost": lost,
        "duplicate_item_ids": dupes,
        "unsupported_additions": extra,
        "chronological_units": chrono_ok,
        "tokens": {
            "unchunked_estimated": unchunked_tokens,
            "chunk_estimated": chunk_tokens,
            "chunk_estimated_sum": sum(chunk_tokens),
        },
        "missing_semantic_unit_kinds": missing_kinds,
        "completeness_proof": proof,
        "chunking": True,
        "model_calls": 0,
        "note": (
            "Structure-only compare. Run models per chunk only after both "
            "single-pass Gemma and Sol reports exist for this fixture hash."
        ),
    }


def merge_chunk_documents(
    docs: list[dict[str, Any]],
    *,
    allowed_ids: set[str],
    email_evidence_ids: set[str],
) -> dict[str, Any]:
    """Chronological reduce + claim dedupe; fail closed on bad provenance."""
    claims: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    seen_claim: set[str] = set()
    seen_rel: set[str] = set()
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        for ep in doc.get("episodes") or []:
            if isinstance(ep, dict):
                episodes.append(ep)
        for cl in doc.get("claims") or []:
            if not isinstance(cl, dict):
                continue
            key = (
                str(cl.get("text") or "").strip().lower(),
                tuple(sorted(str(x) for x in (cl.get("evidence_ids") or []) if x)),
            )
            if key in seen_claim:
                continue
            seen_claim.add(key)
            claims.append(cl)
        for rel in doc.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            rkey = json.dumps(
                {
                    "from": rel.get("from") or rel.get("from_person_id"),
                    "to": rel.get("to") or rel.get("to_person_id"),
                    "role": rel.get("role") or rel.get("role_kind"),
                    "ids": sorted(str(x) for x in (rel.get("evidence_ids") or []) if x),
                },
                sort_keys=True,
            )
            if rkey in seen_rel:
                continue
            seen_rel.add(rkey)
            rels.append(rel)
    episodes.sort(key=lambda e: str(e.get("when") or ""))
    merged = {
        "episodes": episodes,
        "claims": claims,
        "relationships": rels,
        "narrator": "",
    }
    check = validate_fev2_document(
        merged, allowed_ids=allowed_ids, email_evidence_ids=email_evidence_ids
    )
    return {"document": merged, "validation": check, "ok": bool(check.get("ok"))}


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ready_for_chunk_models(
    fixture_path: Path | str,
    gemma_report: dict[str, Any] | None,
    sol_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Both single-pass reports must be ok and share the frozen fixture hash."""
    data = _load_json(fixture_path)
    fixture_hash = str(data.get("input_sha256") or "")
    recomputed = fev2_input_sha256(data)
    if fixture_hash and fixture_hash != recomputed:
        return {"ok": False, "error": "fixture_hash_mismatch", "ran": False}
    gemma = gemma_report or {}
    sol = sol_report or {}
    if gemma.get("phase2_report"):
        gemma = gemma.get("phase2_report") or gemma
    if sol.get("phase2_report"):
        sol = sol.get("phase2_report") or sol
    g_hash = str(gemma.get("input_sha256") or "")
    s_hash = str(sol.get("input_sha256") or "")
    if not gemma.get("ok") or not sol.get("ok"):
        return {
            "ok": False,
            "ran": False,
            "error": "blocked_until_both_single_pass_reports_exist_for_same_fixture_hash",
            "gemma_ok": bool(gemma.get("ok")),
            "sol_ok": bool(sol.get("ok")),
        }
    if not fixture_hash or g_hash != fixture_hash or s_hash != fixture_hash:
        return {
            "ok": False,
            "ran": False,
            "error": "single_pass_hash_mismatch",
            "fixture": fixture_hash,
            "gemma": g_hash,
            "sol": s_hash,
        }
    if not gemma.get("email_reached_model_and_grounded_output") or not sol.get(
        "email_reached_model_and_grounded_output"
    ):
        return {
            "ok": False,
            "ran": False,
            "error": "single_pass_email_did_not_ground_output",
        }
    return {"ok": True, "input_sha256": fixture_hash, "ran": False}


def _chat_chunk(
    *,
    system: str,
    user_message: str,
    provider: str,
    model: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    from memorybox.ask.i11a.historian_provider import (
        HistorianProviderSpec,
        build_historian_provider,
        historian_chat_json,
        normalize_provider_kind,
    )
    from memorybox.ask.i11a.validate import parse_inference_json

    spec = HistorianProviderSpec(
        provider=normalize_provider_kind(provider),
        model=model,
        timeout_seconds=int(timeout_seconds),
    )
    llm = build_historian_provider(spec)
    raw, usage, wall_ms = historian_chat_json(
        llm,
        system=system,
        user_message=user_message,
        json_mode=True,
        requested_model=model,
    )
    parsed = parse_inference_json(raw) if raw else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return {"document": parsed, "usage": usage, "timing_ms": wall_ms, "raw": (raw or "")[:2000]}


def run_provider_over_chunks(
    fixture_path: Path | str,
    *,
    provider: str,
    model: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """Replay each L1 chunk through one model; chrono-reduce + fail closed."""
    from memorybox.ask.i11a.full_evidence_diagnostic import format_full_evidence_text
    from memorybox.ask.i11a.trusted_full_evidence_v2 import FEV2_SYSTEM

    data = _load_json(fixture_path)
    items = list(data.get("items") or [])
    allowed = all_fixture_evidence_ids(items)
    email_ids = {str(x) for x in (data.get("email_evidence_ids") or []) if x}
    chunked = run_l1_chunker(
        items,
        person_context=data.get("person_context") or {},
        ask=str(data.get("ask") or ""),
    )
    docs: list[dict[str, Any]] = []
    per_chunk: list[dict[str, Any]] = []
    for i, ch in enumerate(chunked.get("chunks") or []):
        ch_items = list(ch.get("items") or [])
        paste = format_full_evidence_text(
            ch_items,
            ask=str(data.get("ask") or ""),
            person_context=data.get("person_context") or {},
        )
        one = _chat_chunk(
            system=str(data.get("system") or FEV2_SYSTEM),
            user_message=paste,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        docs.append(one.get("document") or {})
        per_chunk.append(
            {
                "chunk_index": i,
                "item_count": len(ch_items),
                "timing_ms": one.get("timing_ms"),
                "usage": one.get("usage"),
            }
        )
    merged = merge_chunk_documents(
        docs, allowed_ids=allowed, email_evidence_ids=email_ids
    )
    return {
        "ok": bool(merged.get("ok")),
        "provider": provider,
        "model": model,
        "input_sha256": data.get("input_sha256"),
        "chunk_count": len(per_chunk),
        "per_chunk": per_chunk,
        "merged": merged,
        "chunking": True,
    }


def run_chunked_models_after_single_pass(
    fixture_path: Path | str,
    *,
    gemma_report_path: Path | str,
    sol_report_path: Path | str,
    gemma_model: str,
    sol_model: str,
    timeout_seconds: int = 1800,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Phase 3 model-per-chunk. Refuses unless both single-pass reports are ready."""
    gemma_rep = _load_json(gemma_report_path)
    sol_rep = _load_json(sol_report_path)
    gate = ready_for_chunk_models(fixture_path, gemma_rep, sol_rep)
    if not gate.get("ok"):
        return {**gate, "chunking": True, "model_calls": 0}
    gemma = run_provider_over_chunks(
        fixture_path,
        provider="ollama",
        model=gemma_model,
        timeout_seconds=timeout_seconds,
    )
    sol = run_provider_over_chunks(
        fixture_path,
        provider="cloud",
        model=sol_model,
        timeout_seconds=timeout_seconds,
    )
    structure = compare_chunked_vs_unchunked(fixture_path)
    result = {
        "ok": bool(gemma.get("ok")) and bool(sol.get("ok")) and bool(structure.get("ok")),
        "ran": True,
        "input_sha256": gate.get("input_sha256"),
        "structure": structure,
        "gemma_chunked": gemma,
        "sol_chunked": sol,
        "chunking": True,
    }
    dest = Path(out_dir) if out_dir else Path(fixture_path).parent
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"FEV2CHUNK_{gate.get('input_sha256', '')[:8]}.json"
    path.write_text(json.dumps(result, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    result["report_path"] = str(path)
    return result
