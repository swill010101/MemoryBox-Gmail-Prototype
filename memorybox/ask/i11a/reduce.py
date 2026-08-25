"""Correlate leaf observations into trip episodes. Leaves are not final trip truth."""
from __future__ import annotations

from typing import Any

from memorybox.ask.i11a.support import _las_vegas_blob
from memorybox.ask.i11a.windows import _day


def _ep_blob(ep: dict[str, Any]) -> str:
    claims = []
    for c in ep.get("claims") or []:
        if isinstance(c, dict):
            claims.append(c.get("text"))
        else:
            claims.append(c)
    return " ".join(
        str(x or "")
        for x in (
            ep.get("label"),
            " ".join(str(p) for p in (ep.get("places") or [])),
            *claims,
        )
    ).lower()


def _ep_day(ep: dict[str, Any]) -> str | None:
    ds = ep.get("date_span") if isinstance(ep.get("date_span"), dict) else {}
    return _day(ds.get("start") or ds.get("end"))


def _vegas_ep(ep: dict[str, Any]) -> bool:
    if _las_vegas_blob(ep):
        return True
    blob = _ep_blob(ep)
    return any(
        tok in blob
        for tok in ("las vegas", "vegas", "sphere", "eagles", "paradise")
    )


def _merge_trip_group(rows: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    days = sorted(d for d in (_ep_day(e) for e in rows) if d)
    claims: list[dict[str, Any]] = []
    eids: list[str] = []
    vis: list[str] = []
    people: list[dict[str, Any]] = []
    places: list[str] = []
    seen_c: set[str] = set()
    seen_e: set[str] = set()
    seen_v: set[str] = set()
    seen_p: set[str] = set()
    for ep in rows:
        for c in ep.get("claims") or []:
            if not isinstance(c, dict):
                continue
            key = str(c.get("text") or "")[:240]
            if key in seen_c:
                continue
            seen_c.add(key)
            claims.append(c)
        for i in ep.get("supporting_evidence_ids") or []:
            s = str(i)
            if s and s not in seen_e:
                seen_e.add(s)
                eids.append(s)
        for i in ep.get("candidate_visual_ids") or []:
            s = str(i)
            if s and s not in seen_v:
                seen_v.add(s)
                vis.append(s)
        for p in ep.get("people") or []:
            if isinstance(p, dict):
                k = str(p.get("person_id") or p.get("name") or "")
            else:
                k = str(p)
            if k and k not in seen_p:
                seen_p.add(k)
                people.append(p if isinstance(p, dict) else {"name": k, "role": "participant"})
        for pl in ep.get("places") or []:
            s = str(pl or "").strip()
            if s and s not in places:
                places.append(s)
    start = days[0] if days else None
    end = days[-1] if days else None
    return {
        "label": label,
        "date_span": {"start": start, "end": end},
        "people": people[:24],
        "places": places[:12] or ["Las Vegas"],
        "claims": claims[:40],
        "why_relevant_to_ask": "correlated leaf observations for one trip",
        "supporting_evidence_ids": eids[:40],
        "candidate_visual_ids": vis[:24],
        "correlated_from_leaves": True,
    }


def reduce_leaf_observations(document: dict[str, Any] | None) -> dict[str, Any]:
    """One normalized trip episode when leaves describe the same Vegas (or similar) cluster."""
    if not isinstance(document, dict):
        return {"schema_version": 2, "episodes": []}
    episodes = [e for e in (document.get("episodes") or []) if isinstance(e, dict)]
    vegas = [e for e in episodes if _vegas_ep(e)]
    rest = [e for e in episodes if e not in vegas]
    out: list[dict[str, Any]] = []
    if len(vegas) >= 1:
        out.append(_merge_trip_group(vegas, label="Las Vegas trip"))
    out.extend(rest)
    reduced = dict(document)
    reduced["episodes"] = out
    reduced["ask_semantics"] = dict(document.get("ask_semantics") or {})
    if vegas and str((reduced["ask_semantics"] or {}).get("kind") or "") in {"period", "other", ""}:
        reduced["ask_semantics"]["kind"] = "trip"
    return reduced
