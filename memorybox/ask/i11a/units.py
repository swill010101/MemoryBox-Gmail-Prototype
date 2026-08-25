"""InferenceEvidenceUnit + I11A JSON schema helpers."""
from __future__ import annotations

import os
from typing import Any

SCHEMA_VERSION = 2
CLAIM_TYPES = frozenset(
    {"observed", "recorded", "recollection", "derived", "inferred"}
)
PEOPLE_ROLES = frozenset({"participant", "mentioned", "unknown"})
ASK_KINDS = frozenset(
    {"period", "trip", "person", "event", "communications", "other"}
)


def units_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Public prepared units become inference evidence units (same ids/types)."""
    out: list[dict[str, Any]] = []
    for u in pack.get("units") or []:
        if not isinstance(u, dict):
            continue
        prov = u.get("provenance") if isinstance(u.get("provenance"), dict) else {}
        eid = (
            str(prov.get("evidence_id") or "")
            or str(prov.get("journal_id") or "")
            or str(prov.get("story_id") or "")
            or str(prov.get("artifact_id") or "")
            or str(prov.get("external_id") or "")
            or str(u.get("asset_ref") or "")
            or str(u.get("unit_id") or "")
        )
        time_raw = u.get("time") or u.get("capture_time")
        if isinstance(time_raw, dict):
            time_raw = time_raw.get("value") or time_raw.get("start") or ""
        people = []
        for p in u.get("people") or []:
            if isinstance(p, dict):
                people.append(
                    {
                        "name": p.get("name"),
                        "person_id": p.get("person_id"),
                    }
                )
            elif str(p).strip():
                people.append({"name": str(p)})
        out.append(
            {
                "unit_id": u.get("unit_id"),
                "evidence_id": eid or u.get("unit_id"),
                "kind": u.get("kind"),
                "source_type": u.get("source_type")
                or (u.get("normalization") or {}).get("source_type"),
                "time": str(time_raw or "")[:32],
                "people": people[:8],
                "place": u.get("place"),
                "content": str(u.get("content") or u.get("title") or "")[:180],
                "asset_ref": u.get("asset_ref"),
            }
        )
    return out


def _max_model_units() -> int:
    raw = (os.environ.get("MEMORYBOX_I11A_MAX_MODEL_UNITS") or "").strip()
    if raw.isdigit() and int(raw) >= 8:
        return int(raw)
    return 12


def _cluster_key(unit: dict[str, Any], *, grain: str) -> str:
    day = str(unit.get("time") or "")[:10] or "undated"
    if grain == "week" and len(day) >= 10:
        try:
            from datetime import date

            d = date.fromisoformat(day)
            iso = d.isocalendar()
            day = f"{iso.year}-W{iso.week:02d}"
        except ValueError:
            pass
    kind = str(unit.get("kind") or "other")
    st = str(unit.get("source_type") or "")
    return f"{kind}|{st}|{day}"


def _merge_cluster(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = dict(rows[0])
    eids: list[str] = []
    snippets: list[str] = []
    for u in rows:
        eid = str(u.get("evidence_id") or u.get("unit_id") or "").strip()
        if eid and eid not in eids:
            eids.append(eid)
        text = str(u.get("content") or "").strip()
        if text:
            snippets.append(text[:72])
    first["extra_ids"] = eids
    first["content"] = (
        f"{len(rows)} items. " + " · ".join(snippets[:4])
    )[:120]
    return first


def compact_units_for_model(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slim + cluster for the model. Pack/accounting still keep every eligible unit."""
    seen: set[tuple[Any, ...]] = set()
    slim: list[dict[str, Any]] = []
    for u in units:
        kind = str(u.get("kind") or "")
        if kind == "travel":
            key = (
                kind,
                str(u.get("time") or "")[:10],
                str(u.get("place") or ""),
                str(u.get("content") or "")[:48],
            )
            if key in seen:
                continue
            seen.add(key)
        slim.append(u)
    cap = _max_model_units()
    for grain in ("day", "week"):
        if len(slim) <= cap:
            break
        buckets: dict[str, list[dict[str, Any]]] = {}
        passthrough: list[dict[str, Any]] = []
        for u in slim:
            kind = str(u.get("kind") or "")
            if kind in {"communication", "calendar"}:
                buckets.setdefault(_cluster_key(u, grain=grain), []).append(u)
            else:
                passthrough.append(u)
        clustered = passthrough[:]
        for rows in buckets.values():
            if len(rows) == 1:
                clustered.append(rows[0])
            else:
                clustered.append(_merge_cluster(rows))
        slim = clustered
    if len(slim) > cap:
        keep = [u for u in slim if str(u.get("kind") or "") not in {"communication", "calendar"}]
        overflow = [u for u in slim if str(u.get("kind") or "") in {"communication", "calendar"}]
        room = max(4, cap - len(keep))
        slim = keep + overflow[:room]
    return slim[:cap]


def in_scope_ids(pack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for u in list(pack.get("units") or []) + units_from_pack(pack):
        if not isinstance(u, dict):
            continue
        for key in ("evidence_id", "unit_id", "asset_ref"):
            v = str(u.get(key) or "").strip()
            if v:
                ids.add(v)
        for extra in u.get("extra_ids") or []:
            v = str(extra or "").strip()
            if v:
                ids.add(v)
        prov = u.get("provenance") if isinstance(u.get("provenance"), dict) else {}
        for k in (
            "evidence_id",
            "external_id",
            "story_id",
            "journal_id",
            "artifact_id",
        ):
            v = str(prov.get(k) or "").strip()
            if v:
                ids.add(v)
    return ids


def in_scope_visual_ids(pack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for u in units_from_pack(pack):
        kind = str(u.get("kind") or "")
        st = str(u.get("source_type") or "")
        if kind in {"media_observation", "spoken_moment"} or st in {"photo", "video"}:
            for key in ("asset_ref", "evidence_id", "unit_id"):
                v = str(u.get(key) or "").strip()
                if v:
                    ids.add(v)
            prov = u.get("provenance") if isinstance(u.get("provenance"), dict) else {}
            v = str(prov.get("external_id") or "").strip()
            if v:
                ids.add(v)
    return ids


def ask_kind_for_plan(plan: Any) -> str:
    notes = " ".join(getattr(plan, "notes", ()) or ())
    if "exploratory_about_subject" in notes:
        return "person"
    if getattr(plan, "trip_labels", ()) or "ask_kind=trip" in notes:
        return "trip"
    q = str(getattr(plan, "original_ask", "") or "").lower()
    if "text message" in q or "texts" in q or "sms" in q:
        return "communications"
    if "christmas" in q or "holiday" in notes or "temporal=holiday" in notes:
        return "event"
    if getattr(plan, "temporal_windows", ()) or (
        getattr(plan, "time_start", None) and getattr(plan, "time_end", None)
    ):
        return "period"
    if getattr(plan, "person_names", ()):
        return "person"
    return "other"


def empty_inference(*, ask: str, kind: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ask_semantics": {"kind": kind, "constraints": {}},
        "focal_subjects": [],
        "episodes": [],
        "themes": [],
        "unresolved": [],
    }
