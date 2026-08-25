"""Correlate leaf observations into trip episodes. Leaves are not final trip truth."""
from __future__ import annotations

from typing import Any

from memorybox.ask.i11a.support import _las_vegas_blob
from memorybox.ask.i11a.windows import _day, _index_pack_units, union_windows


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
    return _day(ds.get("start") or ds.get("end")) or _day(
        (ep.get("observed_window") or {}).get("start")
    )


def _vegas_ep(ep: dict[str, Any]) -> bool:
    if _las_vegas_blob(ep):
        return True
    blob = _ep_blob(ep)
    return any(
        tok in blob
        for tok in ("las vegas", "vegas", "sphere", "eagles", "paradise")
    )


def _vegas_unit(unit: dict[str, Any]) -> bool:
    blob = " ".join(
        str(x or "")
        for x in (
            unit.get("content"),
            unit.get("title"),
            unit.get("place"),
            unit.get("city"),
            unit.get("state"),
        )
    ).lower()
    if any(tok in blob for tok in ("las vegas", "vegas", "paradise", "sphere")):
        return True
    lat = unit.get("latitude")
    lon = unit.get("longitude")
    media = unit.get("media") if isinstance(unit.get("media"), dict) else {}
    gps = media.get("exif_gps") if isinstance(media.get("exif_gps"), dict) else {}
    try:
        lat_f = float(lat if lat is not None else (gps or {}).get("latitude"))
        lon_f = float(lon if lon is not None else (gps or {}).get("longitude"))
    except (TypeError, ValueError):
        return False
    return 35.85 <= lat_f <= 36.45 and -115.45 <= lon_f <= -114.85


def _merge_trip_group(
    rows: list[dict[str, Any]],
    *,
    label: str,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    observed_parts: list[dict[str, Any]] = []
    scheduled_parts: list[dict[str, Any]] = []
    derived_parts: list[dict[str, Any]] = []
    for ep in rows:
        observed_parts.append(ep.get("observed_window") or {})
        scheduled_parts.append(ep.get("scheduled_window") or {})
        derived_parts.append(ep.get("derived_window") or {})
        for c in ep.get("claims") or []:
            if not isinstance(c, dict):
                continue
            key = str(c.get("text") or "")[:240]
            if key in seen_c:
                continue
            seen_c.add(key)
            claims.append(c)
        for i in list(ep.get("supporting_evidence_ids") or []) + list(
            ep.get("candidate_visual_ids") or []
        ):
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
    idx = _index_pack_units(pack)
    for unit in idx.values():
        kind = str(unit.get("kind") or "")
        if kind not in {"media_observation", "video_asset", "video_moment", "spoken_moment"}:
            continue
        if not _vegas_unit(unit):
            continue
        eid = str(unit.get("evidence_id") or unit.get("asset_ref") or unit.get("unit_id") or "")
        if eid and eid not in seen_e:
            seen_e.add(eid)
            eids.append(eid)
        if eid and eid not in seen_v:
            seen_v.add(eid)
            vis.append(eid)
        day = _day(unit.get("time") or unit.get("captured_at"))
        if day:
            days.append(day)
            observed_parts.append({"start": day, "end": day, "evidence_ids": [eid] if eid else []})
        if kind == "media_observation" and eid:
            text = str(unit.get("place") or unit.get("content") or "photograph")
            key = f"media:{eid}"
            if key not in seen_c:
                seen_c.add(key)
                claims.append(
                    {
                        "text": f"Photograph at {text}"[:500],
                        "supporting_evidence_ids": [eid],
                        "claim_type": "observed",
                        "uncertainty": [],
                    }
                )
    start = min(days) if days else None
    end = max(days) if days else None
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
        "observed_window": union_windows(observed_parts),
        "scheduled_window": union_windows(scheduled_parts),
        "derived_window": union_windows(derived_parts),
    }


def _pattern_eps(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    idx = _index_pack_units(pack)
    seen: set[str] = set()
    for unit in idx.values():
        if str(unit.get("kind") or "") != "comm_pattern":
            continue
        uid = str(unit.get("unit_id") or unit.get("evidence_id") or "")
        if uid in seen:
            continue
        seen.add(uid)
        eids = list(unit.get("source_evidence_ids") or unit.get("extra_ids") or [])
        span = unit.get("date_span") if isinstance(unit.get("date_span"), dict) else {}
        out.append(
            {
                "label": str(unit.get("content") or "communication pattern")[:160],
                "date_span": {
                    "start": span.get("start") or _day(unit.get("time")),
                    "end": span.get("end") or span.get("start") or _day(unit.get("time")),
                },
                "people": unit.get("people") or [],
                "places": [unit["place"]] if unit.get("place") else [],
                "claims": [
                    {
                        "text": str(unit.get("content") or "")[:500],
                        "supporting_evidence_ids": eids[:24] or [uid],
                        "claim_type": "observed",
                        "uncertainty": ["pattern_count_is_trace_not_psychology"],
                    }
                ],
                "why_relevant_to_ask": "grounded communication pattern",
                "supporting_evidence_ids": eids[:40],
                "candidate_visual_ids": [],
                "theme": "communication_pattern",
                "pattern_type": unit.get("pattern_type"),
            }
        )
    return out


def reduce_person_understanding(
    document: dict[str, Any],
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Person understanding: many structured observations, not one life episode."""
    episodes = [e for e in (document.get("episodes") or []) if isinstance(e, dict)]
    vegas = [e for e in episodes if _vegas_ep(e)]
    rest = [e for e in episodes if e not in vegas]
    out: list[dict[str, Any]] = []
    if vegas:
        trip = _merge_trip_group(vegas, label="Las Vegas trip", pack=pack)
        trip["theme"] = "trip"
        trip["why_relevant_to_ask"] = "correlated travel observations"
        out.append(trip)
    patterns = _pattern_eps(pack)
    used_labels = {str(p.get("label") or "") for p in patterns}
    out.extend(patterns)
    for ep in rest:
        if str(ep.get("label") or "") in used_labels:
            continue
        out.append(ep)
    idx = _index_pack_units(pack)
    places: list[dict[str, Any]] = []
    seen_pl: set[str] = set()
    for unit in idx.values():
        if str(unit.get("kind") or "") not in {"place_observation", "media_cluster"}:
            continue
        place = str(unit.get("place") or "").strip()
        if not place or place.lower() in seen_pl:
            continue
        seen_pl.add(place.lower())
        eids = list(unit.get("source_evidence_ids") or unit.get("extra_ids") or [])
        places.append(
            {
                "place": place,
                "evidence_ids": eids[:40],
                "note": "presence at capture time, not residence",
            }
        )
        if not any(place.lower() in _ep_blob(e) for e in out):
            out.append(
                {
                    "label": f"Observed at {place}",
                    "date_span": {
                        "start": _day(unit.get("time")),
                        "end": _day(unit.get("time")),
                    },
                    "people": unit.get("people") or [],
                    "places": [place],
                    "claims": [
                        {
                            "text": str(unit.get("content") or f"Photographs place people at {place}")[:500],
                            "supporting_evidence_ids": eids[:24] or [str(unit.get("evidence_id") or "")],
                            "claim_type": "observed",
                            "uncertainty": ["presence_not_residence"],
                        }
                    ],
                    "why_relevant_to_ask": "media-supported place observation",
                    "supporting_evidence_ids": eids[:40],
                    "candidate_visual_ids": eids[:24],
                    "theme": "observed_place",
                }
            )
    for unit in idx.values():
        if str(unit.get("kind") or "") != "correlated_event":
            continue
        eids = list(unit.get("source_evidence_ids") or unit.get("extra_ids") or [])
        out.append(
            {
                "label": str(unit.get("content") or "correlated event")[:160],
                "date_span": {"start": _day(unit.get("time")), "end": _day(unit.get("time"))},
                "people": unit.get("people") or [],
                "places": [unit["place"]] if unit.get("place") else [],
                "claims": [
                    {
                        "text": str(unit.get("content") or "")[:500],
                        "supporting_evidence_ids": eids[:24],
                        "claim_type": "inferred",
                        "uncertainty": ["cross_source_candidate"],
                    }
                ],
                "why_relevant_to_ask": "calendar/communication/media correlation",
                "supporting_evidence_ids": eids[:40],
                "candidate_visual_ids": [
                    i for i in eids if str(i).startswith("ph-") or "photo" in str(i)
                ][:12],
                "theme": "recurring_activity",
            }
        )
    pc = (pack or {}).get("person_context") if isinstance(pack, dict) else None
    confirmed = []
    inferred = []
    if isinstance(pc, dict):
        req = pc.get("requestor") if isinstance(pc.get("requestor"), dict) else {}
        for rel in req.get("known_relationships") or []:
            if isinstance(rel, dict):
                confirmed.append(rel)
        for sub in pc.get("focal_subjects") or []:
            if isinstance(sub, dict):
                for rel in sub.get("known_relationships") or []:
                    if isinstance(rel, dict):
                        confirmed.append(rel)
    understanding = {
        "biographical_facts": [],
        "relationships": {"confirmed": confirmed[:24], "inferred": inferred},
        "recurring_interactions": [e for e in out if e.get("theme") == "communication_pattern"],
        "life_episodes": [e for e in out if e.get("theme") not in {"communication_pattern", "observed_place"}],
        "recurring_activities": [e for e in out if e.get("theme") == "recurring_activity"],
        "trips": [e for e in out if e.get("theme") == "trip"],
        "observed_places": places,
        "communication_patterns": [e for e in out if e.get("theme") == "communication_pattern"],
        "themes": list(
            dict.fromkeys(str(e.get("theme") or e.get("label") or "") for e in out if e.get("theme"))
        ),
        "unresolved": list(document.get("unresolved") or [])[:24],
    }
    reduced = dict(document)
    reduced["episodes"] = out
    reduced["ask_semantics"] = dict(document.get("ask_semantics") or {})
    reduced["ask_semantics"]["kind"] = "person"
    reduced["person_understanding"] = understanding
    return reduced


def reduce_leaf_observations(
    document: dict[str, Any] | None,
    pack: dict[str, Any] | None = None,
    *,
    ask_kind: str | None = None,
) -> dict[str, Any]:
    """Ask-kind-specific correlation. Person asks must not collapse into one trip."""
    if not isinstance(document, dict):
        return {"schema_version": 2, "episodes": []}
    kind = ask_kind or str((document.get("ask_semantics") or {}).get("kind") or "")
    if kind == "person":
        return reduce_person_understanding(document, pack)
    episodes = [e for e in (document.get("episodes") or []) if isinstance(e, dict)]
    vegas = [e for e in episodes if _vegas_ep(e)]
    rest = [e for e in episodes if e not in vegas]
    out: list[dict[str, Any]] = []
    if len(vegas) >= 1:
        out.append(_merge_trip_group(vegas, label="Las Vegas trip", pack=pack))
    out.extend(rest)
    reduced = dict(document)
    reduced["episodes"] = out
    reduced["ask_semantics"] = dict(document.get("ask_semantics") or {})
    if vegas and str((reduced["ask_semantics"] or {}).get("kind") or "") in {"period", "other", ""}:
        reduced["ask_semantics"]["kind"] = "trip"
    return reduced
