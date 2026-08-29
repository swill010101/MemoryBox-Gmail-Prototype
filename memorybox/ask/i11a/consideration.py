"""Three evidence sets + calendar/media consideration traces.

Retrieved, inference, and presentation must never be conflated.
Gallery representative counts are presentation-only.
"""
from __future__ import annotations

from typing import Any


def _ids_in_document(document: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    if not isinstance(document, dict):
        return ids
    for ep in document.get("episodes") or []:
        if not isinstance(ep, dict):
            continue
        for raw in ep.get("supporting_evidence_ids") or []:
            s = str(raw or "").strip()
            if s:
                ids.add(s)
        for cl in ep.get("claims") or []:
            if not isinstance(cl, dict):
                continue
            for raw in cl.get("supporting_evidence_ids") or []:
                s = str(raw or "").strip()
                if s:
                    ids.add(s)
        for raw in ep.get("candidate_visual_ids") or []:
            s = str(raw or "").strip()
            if s:
                ids.add(s)
    return ids


def finish_consideration(
    pack: dict[str, Any],
    *,
    chunk_map: dict[str, int] | None = None,
    document: dict[str, Any] | None = None,
    accounting: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill sent-in-chunk / merged-pack flags after inference."""
    chunk_map = chunk_map or {}
    merged_ids = _ids_in_document(document)
    rows = list(pack.get("calendar_pipeline") or [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        keys = [
            str(row.get("unit_id") or ""),
            str(row.get("evidence_id") or ""),
        ]
        chunk_i = None
        for k in keys:
            if k and k in chunk_map:
                chunk_i = chunk_map[k]
                break
        row["sent_in_chunk"] = chunk_i is not None
        row["chunk_index"] = chunk_i
        row["represented_in_merged_semantic_pack"] = any(
            k in merged_ids for k in keys if k
        )
    pack["calendar_pipeline"] = rows
    for row in pack.get("comm_pipeline") or []:
        if not isinstance(row, dict):
            continue
        keys = [str(row.get("unit_id") or ""), str(row.get("evidence_id") or "")]
        chunk_i = None
        for k in keys:
            if k and k in chunk_map:
                chunk_i = chunk_map[k]
                break
        row["sent_in_chunk"] = chunk_i is not None
        row["chunk_index"] = chunk_i
        row["represented_in_merged_semantic_pack"] = any(
            k in merged_ids for k in keys if k
        )
    sets = pack.get("evidence_sets") if isinstance(pack.get("evidence_sets"), dict) else {}
    inf = sets.get("inference") if isinstance(sets.get("inference"), dict) else {}
    acc = accounting or {}
    inf["units_generated"] = acc.get("units_generated", inf.get("units_generated"))
    inf["units_passed_to_inference"] = acc.get(
        "units_passed_to_inference", inf.get("units_passed_to_inference")
    )
    inf["chunk_n"] = acc.get("chunk_n", inf.get("chunk_n"))
    sets["inference"] = inf
    pres = sets.get("presentation") if isinstance(sets.get("presentation"), dict) else {}
    vis = pack.get("candidate_visual_ids") or []
    if vis:
        pres["representative_gallery_assets_selected"] = len(vis)
        pres["note"] = (
            "candidate_visual_ids are presentation ranking only — not an inference cap"
        )
    sets["presentation"] = pres
    pack["evidence_sets"] = sets
    pack["consideration"] = {
        "calendar_pipeline": rows,
        "comm_pipeline": pack.get("comm_pipeline") or [],
        "media": pack.get("media_consideration") or {},
        "evidence_sets": sets,
        "accounting": acc,
        "preaggregation": pack.get("preaggregation"),
        "semantic_observations": pack.get("semantic_observations"),
        "semantic_ir": pack.get("semantic_ir"),
        "ask_relative_view": pack.get("ask_relative_view"),
        "leaf_calls": acc.get("leaf_calls"),
        "rejected": pack.get("inference", {}).get("rejected") if isinstance(pack.get("inference"), dict) else None,
    }
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store

        tid = ai_ctx.current_trace_id()
        if tid:
            store.insert_span(
                trace_id=tid,
                stage="i11a_consideration",
                component="i11a",
                operation="consideration",
                status="ok",
                assembled_context=pack["consideration"],
            )
    except Exception:  # noqa: BLE001
        pass
    return pack
