"""Scheduled vs observed vs derived time windows on the semantic pack.

A calendar range is planning evidence, not proof of presence. Photos/GPS and
other observations corroborate an actual window. Travel extracted from mail is
derived. Prefer the strongest corroborated observed window for display; keep
the broader scheduled window as planning.
"""
from __future__ import annotations

from typing import Any

_OBSERVED_KINDS = frozenset(
    {
        "media_observation",
        "photo",
        "video",
        "video_asset",
        "video_moment",
        "spoken_moment",
        "journal",
        "story",
        "media_cluster",
        "place_observation",
        "comm_pattern",
    }
)
_DERIVED_KINDS = frozenset({"travel", "communication_thread", "sms_segment", "correlated_event"})
_SCHEDULED_KINDS = frozenset({"calendar", "calendar_event", "calendar_series"})

_CLAIM_BUCKET = {
    "recorded": "scheduled",
    "observed": "observed",
    "recollection": "observed",
    "derived": "derived",
    "inferred": "derived",
}


def empty_window() -> dict[str, Any]:
    return {"start": None, "end": None, "evidence_ids": []}


def _day(raw: Any) -> str | None:
    if isinstance(raw, dict):
        raw = raw.get("value") or raw.get("start") or raw.get("end")
    s = str(raw or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def absorb(win: dict[str, Any], day: str | None, eid: str | None = None) -> dict[str, Any]:
    out = {
        "start": win.get("start"),
        "end": win.get("end"),
        "evidence_ids": list(win.get("evidence_ids") or []),
    }
    if eid and str(eid) not in out["evidence_ids"]:
        out["evidence_ids"].append(str(eid))
    if not day:
        return out
    start = out["start"]
    end = out["end"]
    if not start or day < str(start):
        out["start"] = day
    if not end or day > str(end):
        out["end"] = day
    return out


def union_windows(windows: list[dict[str, Any]] | None) -> dict[str, Any]:
    out = empty_window()
    for w in windows or []:
        if not isinstance(w, dict):
            continue
        out = absorb(out, _day(w.get("start")))
        out = absorb(out, _day(w.get("end")))
        for eid in w.get("evidence_ids") or []:
            out = absorb(out, None, str(eid))
    if not out["start"] and not out["evidence_ids"]:
        return empty_window()
    return out


def preferred_date_span(
    scheduled: dict[str, Any] | None,
    observed: dict[str, Any] | None,
    derived: dict[str, Any] | None,
) -> dict[str, Any]:
    """Actual corroborated window first; derived next; scheduled last (planning)."""
    for w in (observed, derived, scheduled):
        if isinstance(w, dict) and w.get("start"):
            return {"start": w.get("start"), "end": w.get("end") or w.get("start")}
    return {}


def bucket_for_unit(kind: Any, source_type: Any = None) -> str:
    k = str(kind or "").lower()
    st = str(source_type or "").lower()
    if k in _SCHEDULED_KINDS or st in {"ics", "calendar"}:
        return "scheduled"
    if k in _OBSERVED_KINDS or st in {"photo", "video", "immich"}:
        return "observed"
    if k in _DERIVED_KINDS:
        return "derived"
    return "derived"


def bucket_for_claim_type(claim_type: Any) -> str:
    return _CLAIM_BUCKET.get(str(claim_type or "").lower(), "derived")


def _index_pack_units(pack: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    if not isinstance(pack, dict):
        return idx
    for u in list(pack.get("units") or []) + list(pack.get("inference_units") or []):
        if not isinstance(u, dict):
            continue
        keys = [
            u.get("unit_id"),
            u.get("evidence_id"),
            u.get("asset_ref"),
            (u.get("provenance") or {}).get("evidence_id")
            if isinstance(u.get("provenance"), dict)
            else None,
            (u.get("provenance") or {}).get("external_id")
            if isinstance(u.get("provenance"), dict)
            else None,
        ]
        for extra in list(u.get("extra_ids") or []) + list(u.get("source_evidence_ids") or []):
            keys.append(extra)
        for key in keys:
            s = str(key or "").strip()
            if s and s not in idx:
                idx[s] = u
    return idx


def leaf_unit_index(pack: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index original retrieved units only — not aggregated extra_id aliases.

    Claim validation must not treat a parking receipt as Sphere evidence because
    both IDs appear on the same inference cluster.
    """
    idx: dict[str, dict[str, Any]] = {}
    if not isinstance(pack, dict):
        return idx
    for u in pack.get("units") or []:
        if not isinstance(u, dict):
            continue
        for key in (
            u.get("unit_id"),
            u.get("evidence_id"),
            u.get("asset_ref"),
        ):
            s = str(key or "").strip()
            if s and s not in idx:
                idx[s] = u
        prov = u.get("provenance") if isinstance(u.get("provenance"), dict) else {}
        for k in ("evidence_id", "external_id"):
            s = str(prov.get(k) or "").strip()
            if s and s not in idx:
                idx[s] = u
    return idx
    idx: dict[str, dict[str, Any]] = {}
    if not isinstance(pack, dict):
        return idx
    for u in list(pack.get("units") or []) + list(pack.get("inference_units") or []):
        if not isinstance(u, dict):
            continue
        keys = [
            u.get("unit_id"),
            u.get("evidence_id"),
            u.get("asset_ref"),
            (u.get("provenance") or {}).get("evidence_id")
            if isinstance(u.get("provenance"), dict)
            else None,
            (u.get("provenance") or {}).get("external_id")
            if isinstance(u.get("provenance"), dict)
            else None,
        ]
        for extra in list(u.get("extra_ids") or []) + list(u.get("source_evidence_ids") or []):
            keys.append(extra)
        for key in keys:
            s = str(key or "").strip()
            if s and s not in idx:
                idx[s] = u
    return idx


def windows_from_members(members: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    buckets = {
        "scheduled": empty_window(),
        "observed": empty_window(),
        "derived": empty_window(),
    }
    for m in members or []:
        if not isinstance(m, dict):
            continue
        kind = m.get("kind")
        st = m.get("source_type") or (m.get("normalization") or {}).get("source_type")
        bucket = bucket_for_unit(kind, st)
        day = _day(m.get("time") or m.get("sent_at") or m.get("taken_at") or m.get("start"))
        eid = str(
            m.get("evidence_id")
            or m.get("asset_ref")
            or m.get("unit_id")
            or ""
        ).strip() or None
        buckets[bucket] = absorb(buckets[bucket], day, eid)
    return buckets


def windows_from_episode(
    *,
    claims: list[dict[str, Any]] | None,
    evidence_ids: list[str] | None,
    date_span: dict[str, Any] | None,
    pack: dict[str, Any] | None = None,
    members: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    buckets = windows_from_members(members)
    idx = _index_pack_units(pack)
    for cl in claims or []:
        if not isinstance(cl, dict):
            continue
        bucket = bucket_for_claim_type(cl.get("claim_type"))
        ids = [str(x) for x in (cl.get("supporting_evidence_ids") or []) if str(x).strip()]
        placed = False
        for eid in ids:
            unit = idx.get(eid)
            day = None
            if unit:
                day = _day(unit.get("time") or unit.get("capture_time"))
                ukind = unit.get("kind")
                st = unit.get("source_type")
                # Claim type wins; unit kind only supplies the day.
                if not cl.get("claim_type") and ukind:
                    bucket = bucket_for_unit(ukind, st)
            buckets[bucket] = absorb(buckets[bucket], day, eid)
            placed = True
        if not placed:
            span = date_span if isinstance(date_span, dict) else {}
            buckets[bucket] = absorb(buckets[bucket], _day(span.get("start")))
            buckets[bucket] = absorb(buckets[bucket], _day(span.get("end")))
    for eid in evidence_ids or []:
        unit = idx.get(str(eid))
        if not unit:
            continue
        bucket = bucket_for_unit(unit.get("kind"), unit.get("source_type"))
        day = _day(unit.get("time") or unit.get("capture_time"))
        already = any(str(eid) in (buckets[b].get("evidence_ids") or []) for b in buckets)
        if already:
            continue
        buckets[bucket] = absorb(buckets[bucket], day, str(eid))
    return buckets


def attach_windows(
    target: dict[str, Any],
    buckets: dict[str, dict[str, Any]],
    *,
    fallback_span: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sched = buckets.get("scheduled") or empty_window()
    obs = buckets.get("observed") or empty_window()
    der = buckets.get("derived") or empty_window()
    target["scheduled_window"] = sched
    target["observed_window"] = obs
    target["derived_window"] = der
    preferred = preferred_date_span(sched, obs, der)
    if preferred:
        target["date_span"] = preferred
    elif fallback_span:
        target["date_span"] = fallback_span
    return target


def pack_level_windows(episodes: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        "scheduled_window": union_windows(
            [e.get("scheduled_window") for e in (episodes or []) if isinstance(e, dict)]
        ),
        "observed_window": union_windows(
            [e.get("observed_window") for e in (episodes or []) if isinstance(e, dict)]
        ),
        "derived_window": union_windows(
            [e.get("derived_window") for e in (episodes or []) if isinstance(e, dict)]
        ),
    }
