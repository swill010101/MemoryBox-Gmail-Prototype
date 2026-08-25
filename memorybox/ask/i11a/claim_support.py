"""Whether cited evidence can actually support a claim — IDs existing is not enough."""
from __future__ import annotations

import re
from typing import Any

_RESIDENCE = re.compile(
    r"(?i)\b(lives?|lived|live\s+in|living\s+in|resident(?:s)?\s+of|resides?|"
    r"home\s+is|hometown|moved\s+to)\b"
)
_OCCURRENCE = re.compile(
    r"(?i)\b(flew|flew\s+to|went\s+to|visited|attended|saw\s+the|was\s+in|"
    r"spent|stayed|occurred|happened|did\s+go)\b"
)
_SCHEDULED = re.compile(
    r"(?i)\b(calendar\s+showed|scheduled|booked|planned|itinerary|"
    r"reservation|flight\s+to)\b"
)
_PLACE_PHRASES = (
    "las vegas",
    "vegas",
    "paradise",
    "sphere",
    "eagles",
    "alaska",
    "anchorage",
    "vancouver",
    "maui",
    "hawaii",
)


def _blob(unit: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (
            unit.get("content"),
            unit.get("title"),
            unit.get("subject"),
            unit.get("place"),
            (unit.get("media") or {}).get("location_provenance")
            if isinstance(unit.get("media"), dict)
            else "",
        )
    ).lower()


def _places_in_text(text: str) -> set[str]:
    low = (text or "").lower()
    return {p for p in _PLACE_PHRASES if p in low}


def _vegas_gps(unit: dict[str, Any]) -> bool:
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


def unit_modes(unit: dict[str, Any]) -> set[str]:
    """What this unit is allowed to ground: scheduled, derived, observed."""
    kind = str(unit.get("kind") or "")
    if kind == "calendar" or kind == "calendar_series":
        return {"scheduled"}
    if kind == "travel":
        return {"derived"}
    if kind in {
        "media_observation",
        "video_asset",
        "video_moment",
        "spoken_moment",
        "media_cluster",
        "place_observation",
    }:
        return {"observed"}
    if kind in {"communication", "communication_thread", "sms_segment", "comm_pattern"}:
        return {"derived", "scheduled", "observed"}
    if kind == "correlated_event":
        return {"inferred", "derived", "observed", "scheduled"}
    return {"inferred"}


def unit_places(unit: dict[str, Any]) -> set[str]:
    places = _places_in_text(_blob(unit))
    if _vegas_gps(unit):
        places.update({"las vegas", "vegas", "paradise"})
    dest = str(unit.get("destination") or unit.get("place") or "").lower()
    places |= _places_in_text(dest)
    return places


def claim_support_ok(text: str, unit: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, reason). Generic 'flight 2026-01-20' cannot locate Las Vegas."""
    claim_places = _places_in_text(text)
    modes = unit_modes(unit)
    uplaces = unit_places(unit)
    kind = str(unit.get("kind") or "")
    blob = _blob(unit)
    occurrence = bool(_OCCURRENCE.search(text or ""))
    scheduled_claim = bool(_SCHEDULED.search(text or ""))
    if _RESIDENCE.search(text or "") and kind in {
        "media_observation",
        "video_asset",
        "video_moment",
        "media_cluster",
        "place_observation",
        "spoken_moment",
    }:
        return False, "gps_presence_is_not_residence"

    if claim_places and not (claim_places & uplaces) and not _vegas_gps(unit):
        if "flight" in blob and "las vegas" in claim_places:
            return False, "generic_flight_does_not_locate"
        if claim_places:
            return False, "unit_place_does_not_support_claim_place"

    if occurrence and kind == "calendar":
        return False, "calendar_supports_scheduled_not_occurrence"
    if occurrence and "observed" not in modes and "derived" not in modes:
        return False, "occurrence_needs_observed_or_derived"
    if scheduled_claim and kind == "calendar":
        return True, "calendar_scheduled"
    if kind in {"media_observation", "video_asset", "media_cluster", "place_observation"} and (
        _vegas_gps(unit) or ("paradise" in uplaces) or ("las vegas" in uplaces)
    ):
        if occurrence and re.search(r"(?i)\bflew\b", text or ""):
            return False, "gps_photo_supports_presence_not_flight"
        return True, "observed_presence_at_capture"
    if not claim_places:
        return True, "no_place_constraint"
    if claim_places & uplaces:
        return True, "place_overlap"
    return False, "evidence_cannot_support_claim"


def filter_claim_ids(
    text: str,
    ids: list[str],
    index: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, str]]]:
    kept: list[str] = []
    rejected: list[dict[str, str]] = []
    for eid in ids:
        unit = index.get(eid)
        if not unit:
            rejected.append({"evidence_id": eid, "reason": "id_not_in_pack"})
            continue
        ok, reason = claim_support_ok(text, unit)
        if ok:
            kept.append(eid)
        else:
            rejected.append({"evidence_id": eid, "reason": reason})
    return kept, rejected
