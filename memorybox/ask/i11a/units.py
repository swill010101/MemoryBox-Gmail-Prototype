"""InferenceEvidenceUnit + I11A JSON schema helpers."""
from __future__ import annotations

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
                "content": str(u.get("content") or u.get("title") or "")[:400],
                "asset_ref": u.get("asset_ref"),
            }
        )
    return out


def in_scope_ids(pack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for u in list(pack.get("units") or []) + units_from_pack(pack):
        if not isinstance(u, dict):
            continue
        for key in ("evidence_id", "unit_id", "asset_ref"):
            v = str(u.get(key) or "").strip()
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
    if getattr(plan, "trip_labels", ()) or "alaska" in str(getattr(plan, "original_ask", "")).lower():
        if getattr(plan, "trip_labels", ()):
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
