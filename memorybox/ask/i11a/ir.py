"""Provenance-backed intermediate representation of grounded observations."""
from __future__ import annotations

from typing import Any


IR_SCHEMA_VERSION = 1


def ir_from_observations(observations: list[dict[str, Any]] | None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for obs in observations or []:
        if not isinstance(obs, dict):
            continue
        nodes.append(
            {
                "id": obs.get("observation_id"),
                "kind": obs.get("kind"),
                "text": obs.get("text"),
                "claim_type": obs.get("claim_type"),
                "people": obs.get("people") or [],
                "places": obs.get("places") or [],
                "time": obs.get("time"),
                "date_span": obs.get("date_span") or {},
                "source_type": obs.get("source_type"),
                "supporting_evidence_ids": list(obs.get("supporting_evidence_ids") or []),
                "representative_evidence_ids": list(obs.get("representative_evidence_ids") or []),
                "excerpts": list(obs.get("excerpts") or []),
                "uncertainty": list(obs.get("uncertainty") or []),
                "occurrence_count": obs.get("occurrence_count"),
                "pattern_type": obs.get("pattern_type"),
            }
        )
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "nodes": nodes,
        "links": [],
        "observation_n": len(nodes),
        "note": "Ask-independent IR. Correlation links are added by Ask-relative reasoning.",
    }


def attach_links(ir: dict[str, Any], correlations: list[dict[str, Any]] | None) -> dict[str, Any]:
    out = dict(ir or {})
    links: list[dict[str, Any]] = list(out.get("links") or [])
    for row in correlations or []:
        if not isinstance(row, dict):
            continue
        oids = [str(x) for x in (row.get("observation_ids") or []) if str(x).strip()]
        if len(oids) < 2 and not row.get("label"):
            continue
        links.append(
            {
                "kind": str(row.get("kind") or "same_real_world_thing"),
                "label": str(row.get("label") or "")[:200],
                "observation_ids": oids,
                "why": str(row.get("why") or "")[:400],
            }
        )
    out["links"] = links
    return out
