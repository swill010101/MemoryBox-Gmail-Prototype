"""Phase 3: semantic chunking of a frozen trusted Full-Evidence V2 fixture.

Begin only after both single-pass model runs exist. This module can still
partition a fixture and prove no evidence loss without calling a model.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

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
    return {
        "ok": bool(proof.get("ok")) and not lost,
        "input_sha256": stored,
        "unchunked_item_count": len(items),
        "chunk_count": len(chunked.get("chunks") or []),
        "l1_unit_kinds": dict(kinds),
        "evidence_lost": lost,
        "unsupported_additions": extra,
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
    seen_claim: set[str] = set()
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
    episodes.sort(key=lambda e: str(e.get("when") or ""))
    merged = {"episodes": episodes, "claims": claims, "relationships": []}
    check = validate_fev2_document(
        merged, allowed_ids=allowed_ids, email_evidence_ids=email_evidence_ids
    )
    return {"document": merged, "validation": check, "ok": bool(check.get("ok"))}
