"""Conservative derived travel facts. Never replaces the source communication."""
from __future__ import annotations

import re
from typing import Any

_AIRLINE = re.compile(
    r"(?i)\b(delta|united|american airlines|southwest|alaska airlines|"
    r"hawaiian|jetblue|spirit|frontier|air canada|british airways|lufthansa)\b"
)
_HOTEL = re.compile(
    r"(?i)\b(marriott|hilton|hyatt|ihg|holiday inn|airbnb|vrbo|"
    r"hotels?|resorts?|lodging)\b"
)
_CAR = re.compile(
    r"(?i)\b(hertz|enterprise|avis|budget|national|alamo|rental car|car rental)\b"
)
_ROUTE = re.compile(
    r"\b([A-Z]{3})\s*(?:→|->|–|—|-| to )\s*([A-Z]{3})\b"
)
_CONFIRM = re.compile(
    r"(?i)\b(?:confirmation(?:\s+(?:code|number|#|ref(?:erence)?)?)?|"
    r"record\s+locator|itinerary\s+(?:number|#)|reservation(?:\s+(?:number|#))?)"
    r"\s*[:#]?\s*([A-Z0-9]{5,8})\b"
)
_ISO = re.compile(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b")
_MDY = re.compile(
    r"(?i)\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+(\d{1,2}),?\s+(20\d{2}|19\d{2})\b"
)
_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def _dates(text: str) -> list[str]:
    found: list[str] = []
    for m in _ISO.finditer(text or ""):
        found.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    for m in _MDY.finditer(text or ""):
        found.append(f"{m.group(3)}-{_MONTHS[m.group(1).lower()]}-{int(m.group(2)):02d}")
    out: list[str] = []
    seen: set[str] = set()
    for d in found:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def extract_travel(
    *,
    subject: str,
    body: str,
    source_unit_id: str,
    source_evidence_id: str,
) -> dict[str, Any] | None:
    blob = f"{subject or ''}\n{body or ''}"
    if not blob.strip():
        return None
    airline = _AIRLINE.search(blob)
    hotel = _HOTEL.search(blob)
    car = _CAR.search(blob)
    route = _ROUTE.search(blob)
    dates = _dates(blob)
    confirm_code = None
    for confirm in _CONFIRM.finditer(blob):
        raw = confirm.group(1).upper()
        if re.search(r"\d", raw) and raw.lower() not in {
            "delta",
            "united",
            "alaska",
            "spirit",
        }:
            confirm_code = raw
            break
    kind = None
    if airline or route:
        kind = "flight"
    elif car and not hotel:
        kind = "car"
    elif hotel:
        kind = "lodging"
    elif confirm_code and re.search(r"(?i)\breservation\b", blob):
        kind = "reservation"
    if not kind:
        return None
    signals = sum(
        [
            bool(airline or hotel or car),
            bool(route) or bool(re.search(r"(?i)\b(maui|hawaii|ogg|hnl)\b", blob)),
            bool(dates),
            bool(confirm_code),
        ]
    )
    # Require enough structure that we are not inventing an itinerary from a chatty email.
    if signals < 2 and not (route and dates):
        return None
    if kind == "flight" and not (route or dates):
        return None
    if kind == "lodging" and hotel and re.fullmatch(
        r"(?i)hotels?|resorts?|lodging", hotel.group(0) or ""
    ):
        if not confirm_code:
            return None
    if kind == "car" and not (confirm_code or re.search(r"(?i)\brental\b", blob)):
        return None
    origin = dest = property_name = None
    if route:
        origin, dest = route.group(1), route.group(2)
    if kind == "lodging":
        property_name = (hotel.group(0) if hotel else None)
    return {
        "travel_kind": kind,
        "origin": origin,
        "destination": dest,
        "property": property_name,
        "start": dates[0] if dates else None,
        "end": dates[1] if len(dates) > 1 else (dates[0] if dates else None),
        "confirmation": confirm_code,
        "carrier": airline.group(0) if airline else None,
        "derived_from": {
            "unit_id": source_unit_id,
            "evidence_id": source_evidence_id,
        },
        "reliable": True,
    }
