"""Ask-independent grounded semantic observations.

The extractor answers: what does this evidence actually establish?
It does not create trips, Person portraits, period narratives, or holiday stories.
"""
from __future__ import annotations

import hashlib
from typing import Any

from memorybox.ask.i11a.comm_patterns import _DINNER, _GIFT, _HEART, _INVITE, _LOVE, _TRAVEL
from memorybox.ask.i11a.observation_cache import (
    load_observation,
    save_observation,
    source_hash,
)
from memorybox.ask.i11a.windows import _day

OBS_METHOD = "grounded_semantic_observation"
OBS_VERSION = "i11a_obs_v2"

OBSERVATION_KINDS = (
    "person_at_place_time",
    "calendar_records_event",
    "communication_states",
    "travel_document_records",
    "repeated_communication_pattern",
    "people_interacting",
    "activity_named",
    "place_referenced",
    "relationship_stated",
    "media_observation",
)


def _ids(unit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in (
        unit.get("evidence_id"),
        unit.get("asset_ref"),
        unit.get("unit_id"),
        unit.get("source_id"),
    ):
        s = str(key or "").strip()
        if s and s not in out:
            out.append(s)
    for extra in list(unit.get("extra_ids") or []) + list(unit.get("source_evidence_ids") or []):
        s = str(extra or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _people(unit: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in unit.get("people") or []:
        if isinstance(p, dict):
            row = {
                "name": p.get("name"),
                "person_id": p.get("person_id"),
                "role": p.get("role") or "participant",
            }
            k = str(row.get("person_id") or row.get("name") or "")
        else:
            n = str(p).strip()
            if not n:
                continue
            row = {"name": n, "person_id": None, "role": "participant"}
            k = n
        if k and k not in seen:
            seen.add(k)
            out.append(row)
    return out


def _people_names(unit: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for p in _people(unit):
        n = str(p.get("name") or "").strip()
        if n and n not in names:
            names.append(n)
    return names


def _excerpt(unit: dict[str, Any], n: int = 180) -> str:
    return " ".join(
        str(x or "").strip()
        for x in (
            unit.get("content"),
            unit.get("authored_text"),
            unit.get("subject"),
            unit.get("title"),
        )
        if str(x or "").strip()
    )[:n]


def _obs_id(kind: str, ids: list[str], text: str) -> str:
    digest = hashlib.sha256(
        f"{kind}|{source_hash(ids)}|{text[:80]}".encode("utf-8")
    ).hexdigest()[:16]
    return f"obs-{digest}"


def _base(
    *,
    kind: str,
    text: str,
    unit: dict[str, Any],
    claim_type: str,
    ids: list[str] | None = None,
    uncertainty: list[str] | None = None,
) -> dict[str, Any]:
    ids = list(ids or _ids(unit))
    day = _day(unit.get("time") or unit.get("captured_at") or unit.get("timestamp"))
    span = unit.get("date_span") if isinstance(unit.get("date_span"), dict) else {}
    start = _day(span.get("start")) or day
    end = _day(span.get("end")) or day
    place = str(unit.get("place") or unit.get("city") or "").strip()
    places = [place] if place else []
    return {
        "observation_id": _obs_id(kind, ids, text),
        "kind": kind,
        "text": text[:500],
        "claim_type": claim_type,
        "people": _people(unit),
        "places": places[:8],
        "time": day,
        "date_span": {"start": start, "end": end},
        "source_type": unit.get("source_type") or unit.get("kind"),
        "unit_kind": unit.get("kind"),
        "supporting_evidence_ids": ids,
        "representative_evidence_ids": ids[:8],
        "excerpts": [x for x in [_excerpt(unit, 160)] if x],
        "uncertainty": list(uncertainty or []),
        "occurrence_count": unit.get("occurrence_count"),
        "pattern_type": unit.get("pattern_type"),
        "latitude": unit.get("latitude"),
        "longitude": unit.get("longitude"),
        "asset_ref": unit.get("asset_ref"),
        "media": unit.get("media") if isinstance(unit.get("media"), dict) else None,
    }


def _comm_meaning(unit: dict[str, Any]) -> str:
    excerpt = _excerpt(unit)
    names = _people_names(unit)
    who = " and ".join(names[:4]) if names else "Someone"
    if _LOVE.search(excerpt):
        if len(names) >= 2:
            return f"{names[0]} and {names[1]} exchanged affectionate messages: {excerpt[:160]}"
        return f"{who} expressed affection in a message: {excerpt[:160]}"
    if _HEART.search(excerpt) and not _LOVE.search(excerpt):
        return f"{who} used heart emoji in communication: {excerpt[:160]}"
    if _GIFT.search(excerpt):
        return f"{who} offered or sent a meal, gift, or support: {excerpt[:160]}"
    if _DINNER.search(excerpt):
        return f"{who} planned or discussed a meal together: {excerpt[:160]}"
    if _INVITE.search(excerpt):
        return f"{who} invited getting together: {excerpt[:160]}"
    if _TRAVEL.search(excerpt):
        return f"{who} discussed travel plans or itinerary: {excerpt[:160]}"
    if excerpt:
        return f"{who} stated or planned: {excerpt[:220]}"
    return f"{who} communicated."


def observation_from_unit(unit: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(unit, dict):
        return None
    kind = str(unit.get("kind") or "")
    ids = _ids(unit)
    if not ids:
        return None
    excerpt = _excerpt(unit)
    names = _people_names(unit)
    who = " and ".join(names[:4]) if names else None
    place = str(unit.get("place") or unit.get("city") or "").strip()
    day = _day(unit.get("time") or unit.get("captured_at"))

    if kind in {"calendar", "calendar_series"}:
        title = str(unit.get("title") or excerpt or "calendar item").strip()[:200]
        n = unit.get("occurrence_count")
        extra = f" ({n} scheduled dates)" if n and int(n) > 1 else ""
        text = f"Calendar records {title}{extra}" + (f" on {day}" if day else "")
        return _base(
            kind="calendar_records_event",
            text=text,
            unit=unit,
            claim_type="recorded",
            ids=ids,
            uncertainty=["calendar_listing_is_not_proof_of_occurrence"],
        )
    if kind == "travel":
        text = "Travel document records itinerary or reservation"
        if excerpt:
            text = f"Travel document records itinerary/reservation: {excerpt[:220]}"
        return _base(
            kind="travel_document_records",
            text=text,
            unit=unit,
            claim_type="derived",
            ids=ids,
            uncertainty=["itinerary_is_not_completed_travel"],
        )
    if kind == "comm_pattern":
        text = excerpt or str(unit.get("content") or "repeated communication pattern")
        return _base(
            kind="repeated_communication_pattern",
            text=text,
            unit=unit,
            claim_type="derived",
            ids=ids,
        )
    if kind in {"communication", "communication_thread", "sms_segment"}:
        return _base(
            kind="communication_states",
            text=_comm_meaning(unit),
            unit=unit,
            claim_type="observed",
            ids=ids,
        )
    if kind in {"media_observation", "video_asset", "video_moment", "spoken_moment", "media_cluster"}:
        loc = place or "an unspecified place"
        subject = who or "A person"
        when = f" on {day}" if day else ""
        media_kind = "Video asset" if kind == "video_asset" else "Photograph"
        if kind == "media_cluster":
            media_kind = excerpt or "Media observations"
            text = f"{subject} observed at {loc}{when}. {media_kind}"
        elif kind == "spoken_moment":
            text = f"Spoken moment{when}" + (f" at {loc}" if place else "")
            if excerpt:
                text = f"{text}: {excerpt[:160]}"
        else:
            text = f"{subject} observed at {loc}{when}"
        unc = ["gps_or_labeled_place_is_presence_not_residence"] if place else []
        obs_kind = "person_at_place_time" if (who or place) else "media_observation"
        return _base(
            kind=obs_kind,
            text=text,
            unit=unit,
            claim_type="observed",
            ids=ids,
            uncertainty=unc,
        )
    if kind == "place_observation":
        loc = place or "a place"
        text = excerpt or (
            f"Place referenced: observed at {loc}"
            + (f" on {day}" if day else "")
        )
        return _base(
            kind="place_referenced",
            text=text,
            unit=unit,
            claim_type="observed",
            ids=ids,
            uncertainty=["gps_or_labeled_place_is_presence_not_residence"],
        )
    if kind == "correlated_event":
        return _base(
            kind="people_interacting",
            text=excerpt or "People interacting around a named activity.",
            unit=unit,
            claim_type="derived",
            ids=ids,
        )
    if kind in {"journal", "story"}:
        text = f"Recollection: {excerpt[:240]}" if excerpt else "A recollection was recorded."
        return _base(
            kind="activity_named",
            text=text,
            unit=unit,
            claim_type="recollection",
            ids=ids,
        )
    if kind == "artifact":
        return _base(
            kind="activity_named",
            text=excerpt or "An artifact was recorded.",
            unit=unit,
            claim_type="observed",
            ids=ids,
        )
    if excerpt or ids:
        return _base(
            kind="activity_named",
            text=excerpt or str(kind or "evidence"),
            unit=unit,
            claim_type="inferred",
            ids=ids,
        )
    return None


# B: free-form text that is not already a typed Observation. A is everything else
# (calendar, travel, GPS/media, patterns, correlations, structured metadata).
_MODEL_INTERPRETATION_KINDS = frozenset(
    {
        "communication",
        "communication_thread",
        "sms_segment",
        "spoken_moment",
    }
)
_MODEL_INTERPRETATION_SOURCES = frozenset(
    {"email", "sms", "imessage", "text", "mms"}
)
_FREEFORM_METADATA_KINDS = frozenset({"journal", "story", "artifact"})


def requires_model_interpretation(unit: dict[str, Any] | None) -> bool:
    """True only for units that still need OBSERVATION_EXTRACT.

    Mechanical gate: kind/source/presence of a body. Not Ask-relative importance.
    """
    if not isinstance(unit, dict):
        return False
    kind = str(unit.get("kind") or "")
    if kind in _MODEL_INTERPRETATION_KINDS:
        return True
    source = str(unit.get("source_type") or "").lower()
    if source in _MODEL_INTERPRETATION_SOURCES and kind not in {
        "calendar",
        "calendar_series",
        "travel",
        "comm_pattern",
        "correlated_event",
        "media_observation",
        "media_cluster",
        "place_observation",
        "video_asset",
        "video_moment",
    }:
        return True
    if kind in _FREEFORM_METADATA_KINDS:
        body = " ".join(
            str(x or "").strip()
            for x in (unit.get("authored_text"), unit.get("content"), unit.get("excerpt"))
            if str(x or "").strip()
        )
        title = str(unit.get("title") or "").strip()
        rest = body
        if title and rest.startswith(title):
            rest = rest[len(title) :].strip()
        return len(rest) >= 32
    return False


def _maybe_cached(unit: dict[str, Any], *, person_id: str | None) -> dict[str, Any] | None:
    ids = _ids(unit)
    if not ids:
        return None
    hit = load_observation(
        person_id=person_id,
        method=OBS_METHOD,
        evidence_ids=ids,
        method_version=OBS_VERSION,
    )
    if isinstance(hit, dict) and hit.get("text") and hit.get("supporting_evidence_ids"):
        return hit
    return None


KIND_ALIASES = {
    "communication": "communication_states",
    "communications": "communication_states",
    "email": "communication_states",
    "sms": "communication_states",
    "message": "communication_states",
    "calendar": "calendar_records_event",
    "calendar_event": "calendar_records_event",
    "event": "activity_named",
    "named": "activity_named",
    "activity": "activity_named",
    "travel": "travel_document_records",
    "itinerary": "travel_document_records",
    "pattern": "repeated_communication_pattern",
    "media": "media_observation",
    "photo": "media_observation",
    "video": "media_observation",
    "place": "place_referenced",
    "location": "place_referenced",
    "referenced": "place_referenced",
    "relationship": "relationship_stated",
    "interaction": "people_interacting",
    "people": "people_interacting",
}
CLAIM_ALIASES = {
    "is": "inferred",
    "location": "observed",
    "event": "recorded",
    "named": "inferred",
    "referenced": "inferred",
    "scheduled": "recorded",
    "planned": "derived",
    "stated": "observed",
}


def _place_label(raw: Any) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:80]
    if isinstance(raw, dict):
        for k in ("name", "label", "place", "value", "city"):
            s = str(raw.get(k) or "").strip()
            if s:
                return s[:80]
    return None


def canonicalize_observation(
    obs: dict[str, Any] | None,
    *,
    strict_kind: bool = False,
) -> dict[str, Any] | None:
    """Repair model enum/schema drift into the canonical IR types."""
    if not isinstance(obs, dict):
        return None
    row = dict(obs)
    kind = str(row.get("kind") or "").strip().lower().replace(" ", "_")
    kind = KIND_ALIASES.get(kind, kind)
    if kind not in OBSERVATION_KINDS:
        if strict_kind:
            return None
        kind = "activity_named"
    source = str(row.get("source_type") or row.get("unit_kind") or "").lower()
    raw_text = row.get("text")
    if raw_text is None:
        text = ""
    else:
        text = str(raw_text).strip()
        if text.lower() in {"none", "null", "n/a", "undefined"}:
            return None
    has_gps = row.get("latitude") is not None or (
        isinstance(row.get("media"), dict) and (row.get("media") or {}).get("exif_gps")
    )
    if (
        not strict_kind
        and kind == "person_at_place_time"
        and (
            "@" in text or source in {"email", "sms", "imessage", "communication"}
        )
        and not has_gps
    ):
        kind = "communication_states"
    row["kind"] = kind
    ctype = str(row.get("claim_type") or "").strip().lower()
    ctype = CLAIM_ALIASES.get(ctype, ctype)
    if ctype not in {"observed", "recorded", "recollection", "derived", "inferred"}:
        if kind == "calendar_records_event":
            ctype = "recorded"
        elif kind == "travel_document_records":
            ctype = "derived"
        else:
            ctype = "observed"
    row["claim_type"] = ctype
    places: list[str] = []
    raw_places = row.get("places")
    if isinstance(raw_places, dict):
        raw_places = [raw_places]
    if isinstance(raw_places, (list, tuple)):
        for p in raw_places:
            lab = _place_label(p)
            if lab and lab not in places:
                places.append(lab)
    elif raw_places:
        lab = _place_label(raw_places)
        if lab:
            places.append(lab)
    if row.get("place") and not places:
        lab = _place_label(row.get("place"))
        if lab:
            places.append(lab)
    row["places"] = places[:8]
    people_out: list[dict[str, Any]] = []
    for p in row.get("people") or []:
        if isinstance(p, str) and p.strip():
            people_out.append({"name": p.strip(), "person_id": None, "role": "participant"})
        elif isinstance(p, dict) and (p.get("name") or p.get("person_id")):
            people_out.append(
                {
                    "name": p.get("name"),
                    "person_id": p.get("person_id"),
                    "role": p.get("role") or "participant",
                }
            )
    row["people"] = people_out
    ids = []
    for i in row.get("supporting_evidence_ids") or row.get("evidence_ids") or []:
        s = str(i).strip()
        if s and s not in ids:
            ids.append(s)
    row["supporting_evidence_ids"] = ids
    if not text or not ids:
        return None
    row["text"] = text[:500]
    return row


def extract_observations(
    units: list[dict[str, Any]] | None,
    *,
    person_id: str | None = None,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """Ask-blind extraction. Do not pass Ask kind, trip labels, or portrait instructions."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in units or []:
        cached = _maybe_cached(unit, person_id=person_id)
        obs = cached or observation_from_unit(unit)
        obs = canonicalize_observation(obs)
        if not obs:
            continue
        oid = str(obs.get("observation_id") or "")
        if oid and oid in seen:
            continue
        if oid:
            seen.add(oid)
        if persist and not (obs.get("_cache") or {}).get("hit"):
            save_observation(
                person_id=person_id,
                method=OBS_METHOD,
                evidence_ids=list(obs.get("supporting_evidence_ids") or []),
                payload=dict(obs),
                method_version=OBS_VERSION,
                uncertainty=";".join(obs.get("uncertainty") or []) or None,
            )
        out.append(obs)
    return out


def merge_model_observations(
    base: list[dict[str, Any]],
    extra: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Union model-enriched observations onto deterministic ones without dropping IDs."""
    by_hash: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for obs in list(base) + list(extra or []):
        if not isinstance(obs, dict):
            continue
        obs = canonicalize_observation(obs)
        if not obs:
            continue
        ids = [str(x) for x in (obs.get("supporting_evidence_ids") or []) if str(x).strip()]
        if not ids:
            continue
        key = source_hash(ids) + "|" + str(obs.get("kind") or "")
        prev = by_hash.get(key)
        text = str(obs.get("text") or "").strip()
        if not text:
            continue
        if prev is None:
            by_hash[key] = dict(obs)
            order.append(key)
            continue
        # Do not let a later model dump attach every batch ID onto a tighter observation.
        if len(text) > len(str(prev.get("text") or "")):
            prev["text"] = text[:500]
        by_hash[key] = prev
    return [by_hash[k] for k in order]
