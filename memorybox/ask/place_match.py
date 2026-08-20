"""Place filter for person+location Asks.

Person-library retrieve is identity-first (Immich personIds). A Place slot is a
filter on that library, not a second Person. FlightSim reverse-geocode is often
missing: GPS-only map pins, city without state, or ``FL`` instead of Florida.
Matching uses aliases, well-known cities, filenames, and a state bounding box.
Unlocated assets do not match — do not fall back to the full person library.
"""
from __future__ import annotations

import re
from typing import Any

# USPS / common abbreviations. Keys are lowercase display names (GEO slots).
_STATE_ALIASES: dict[str, tuple[str, ...]] = {
    "alabama": ("al",),
    "alaska": ("ak",),
    "arizona": ("az",),
    "arkansas": ("ar",),
    "california": ("ca", "calif"),
    "colorado": ("co",),
    "connecticut": ("ct",),
    "delaware": ("de",),
    "florida": ("fl", "fla"),
    "hawaii": ("hi",),
    "idaho": ("id",),
    "illinois": ("il",),
    "indiana": ("in",),
    "iowa": ("ia",),
    "kansas": ("ks",),
    "kentucky": ("ky",),
    "louisiana": ("la",),
    "maine": ("me",),
    "maryland": ("md",),
    "massachusetts": ("ma", "mass"),
    "michigan": ("mi",),
    "minnesota": ("mn",),
    "mississippi": ("ms",),
    "missouri": ("mo",),
    "montana": ("mt",),
    "nebraska": ("ne",),
    "nevada": ("nv",),
    "ohio": ("oh",),
    "oklahoma": ("ok",),
    "oregon": ("or",),
    "pennsylvania": ("pa", "penn"),
    "tennessee": ("tn",),
    "texas": ("tx",),
    "utah": ("ut",),
    "vermont": ("vt",),
    "virginia": ("va",),
    "wisconsin": ("wi", "wisc"),
    "wyoming": ("wy",),
    "new york": ("ny", "n.y.", "nyc"),
    "new jersey": ("nj", "n.j."),
    "new mexico": ("nm", "n.m."),
    "new hampshire": ("nh", "n.h."),
    "north carolina": ("nc", "n.c."),
    "south carolina": ("sc", "s.c."),
    "north dakota": ("nd", "n.d."),
    "south dakota": ("sd", "s.d."),
    "rhode island": ("ri", "r.i."),
    "west virginia": ("wv", "w.v."),
    "washington dc": ("dc", "d.c.", "washington d.c.", "district of columbia"),
    "washington d.c.": ("dc", "d.c.", "washington dc", "district of columbia"),
    "district of columbia": ("dc", "d.c.", "washington dc", "washington d.c."),
}

# (lat_min, lat_max, lon_min, lon_max) — west longitude is negative.
_STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    "alabama": (30.14, 35.01, -88.47, -84.89),
    "alaska": (51.21, 71.39, -179.15, -129.98),
    "arizona": (31.33, 37.00, -114.82, -109.05),
    "arkansas": (33.00, 36.50, -94.62, -89.64),
    "california": (32.53, 42.01, -124.48, -114.13),
    "colorado": (36.99, 41.00, -109.06, -102.04),
    "connecticut": (40.95, 42.05, -73.73, -71.79),
    "delaware": (38.45, 39.84, -75.79, -75.05),
    "florida": (24.39, 31.00, -87.63, -79.97),
    "hawaii": (18.91, 22.24, -160.25, -154.80),
    "idaho": (41.99, 49.00, -117.24, -111.04),
    "illinois": (36.97, 42.51, -91.51, -87.02),
    "indiana": (37.77, 41.76, -88.10, -84.78),
    "iowa": (40.38, 43.50, -96.64, -90.14),
    "kansas": (36.99, 40.00, -102.05, -94.59),
    "kentucky": (36.50, 39.15, -89.57, -81.96),
    "louisiana": (28.93, 33.02, -94.04, -88.82),
    "maine": (43.06, 47.46, -71.08, -66.95),
    "maryland": (37.91, 39.72, -79.49, -75.05),
    "massachusetts": (41.24, 42.89, -73.51, -69.93),
    "michigan": (41.70, 48.31, -90.42, -82.12),
    "minnesota": (43.50, 49.38, -97.24, -89.49),
    "mississippi": (30.17, 35.00, -91.66, -88.10),
    "missouri": (35.99, 40.61, -95.77, -89.10),
    "montana": (44.36, 49.00, -116.05, -104.04),
    "nebraska": (39.99, 43.00, -104.05, -95.31),
    "nevada": (35.00, 42.00, -120.01, -114.04),
    "ohio": (38.40, 42.33, -84.82, -80.52),
    "oklahoma": (33.62, 37.00, -103.00, -94.43),
    "oregon": (41.99, 46.29, -124.57, -116.46),
    "pennsylvania": (39.72, 42.27, -80.52, -74.69),
    "tennessee": (34.98, 36.68, -90.31, -81.65),
    "texas": (25.84, 36.50, -106.65, -93.51),
    "utah": (36.99, 42.00, -114.05, -109.04),
    "vermont": (42.73, 45.02, -73.44, -71.46),
    "virginia": (36.54, 39.47, -83.68, -75.24),
    "wisconsin": (42.49, 47.31, -92.89, -86.25),
    "wyoming": (40.99, 45.01, -111.05, -104.05),
    "new york": (40.48, 45.02, -79.76, -71.86),
    "new jersey": (38.93, 41.36, -75.56, -73.89),
    "new mexico": (31.33, 37.00, -109.05, -103.00),
    "new hampshire": (42.70, 45.31, -72.56, -70.70),
    "north carolina": (33.84, 36.59, -84.32, -75.46),
    "south carolina": (32.03, 35.22, -83.35, -78.54),
    "north dakota": (45.94, 49.00, -104.05, -96.55),
    "south dakota": (42.48, 45.95, -104.06, -96.44),
    "rhode island": (41.15, 42.02, -71.86, -71.12),
    "west virginia": (37.20, 40.64, -82.64, -77.72),
    "washington dc": (38.79, 39.00, -77.12, -76.91),
    "washington d.c.": (38.79, 39.00, -77.12, -76.91),
    "district of columbia": (38.79, 39.00, -77.12, -76.91),
}

# Reverse-geocode often stores the city and omits the state name.
_STATE_CITIES: dict[str, tuple[str, ...]] = {
    "florida": (
        "miami",
        "miami beach",
        "fort lauderdale",
        "tampa",
        "orlando",
        "jacksonville",
        "naples",
        "fort myers",
        "cape coral",
        "sarasota",
        "bradenton",
        "clearwater",
        "st petersburg",
        "saint petersburg",
        "st. petersburg",
        "west palm beach",
        "boca raton",
        "hollywood",
        "hialeah",
        "tallahassee",
        "gainesville",
        "key west",
        "key largo",
        "islamorada",
        "marathon",
        "sanibel",
        "captiva",
        "marco island",
        "bonita springs",
        "estero",
        "punta gorda",
        "port charlotte",
        "venice",
        "lakeland",
        "daytona",
        "daytona beach",
        "melbourne",
        "vero beach",
        "jupiter",
        "palm beach",
        "delray beach",
        "pensacola",
        "destin",
        "panama city",
        "ocala",
        "kissimmee",
        "winter park",
        "coral gables",
        "doral",
        "homestead",
        "florida keys",
        "the keys",
        "fort walton",
        "st augustine",
        "saint augustine",
        "ponce inlet",
        "siesta key",
        "anna maria",
        "longboat key",
    ),
    "california": (
        "los angeles",
        "san francisco",
        "san diego",
        "sacramento",
        "san jose",
        "oakland",
        "anaheim",
        "long beach",
        "fresno",
        "palm springs",
    ),
    "texas": (
        "houston",
        "dallas",
        "austin",
        "san antonio",
        "fort worth",
        "el paso",
        "galveston",
    ),
    "new york": (
        "new york city",
        "manhattan",
        "brooklyn",
        "queens",
        "bronx",
        "staten island",
        "buffalo",
        "albany",
        "rochester",
        "syracuse",
    ),
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def canonical_place(place: str) -> str:
    raw = _norm(place)
    if not raw:
        return ""
    collapsed = re.sub(r"[.]+", "", raw)
    collapsed = re.sub(r"\s+", " ", collapsed).strip()
    for name, aliases in _STATE_ALIASES.items():
        if collapsed == name or collapsed in aliases:
            return name
        if collapsed.replace(" ", "") == name.replace(" ", ""):
            return name
    return collapsed


def place_needles(place: str) -> tuple[str, ...]:
    """Longer tokens first. Short USPS codes are matched on word boundaries."""
    key = canonical_place(place)
    if not key:
        return ()
    out: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        t = _norm(token)
        if not t or t in seen:
            return
        seen.add(t)
        out.append(t)

    add(key)
    add(place)
    for a in _STATE_ALIASES.get(key, ()):
        add(a)
    for city in _STATE_CITIES.get(key, ()):
        add(city)
    out.sort(key=lambda s: (-len(s), s))
    return tuple(out)


def place_bbox(place: str) -> tuple[float, float, float, float] | None:
    key = canonical_place(place)
    return _STATE_BBOX.get(key)


def place_match_spec(place_names: tuple[str, ...] | list[str] | None) -> dict[str, Any] | None:
    """JSON for Explore: needles + bbox for the first typed Place."""
    names = [str(p).strip() for p in (place_names or ()) if str(p).strip()]
    if not names:
        return None
    primary = names[0]
    needles = list(place_needles(primary))
    bbox = place_bbox(primary)
    spec: dict[str, Any] = {
        "place": primary,
        "needles": needles,
        "short_needles": [n for n in needles if len(n) <= 3],
    }
    if bbox:
        spec["bbox"] = list(bbox)
    return spec


def _blob_matches(blob: str, needles: tuple[str, ...], *, state: str | None = None) -> bool:
    """Long tokens substring-match. USPS codes only match the state field or ', FL'."""
    if not needles:
        return False
    state_n = re.sub(r"[.]", "", _norm(state))
    for needle in needles:
        compact = needle.replace(".", "")
        if len(compact) <= 3:
            if state_n == compact:
                return True
            if blob and re.search(
                rf"(?:,\s*|,\s|\s){re.escape(compact)}(?:\s|,|$)", blob
            ):
                return True
        elif needle and needle in (blob or ""):
            return True
    return False


def _in_bbox(
    lat: float | None,
    lon: float | None,
    bbox: tuple[float, float, float, float] | None,
) -> bool:
    if bbox is None or lat is None or lon is None:
        return False
    try:
        la = float(lat)
        lo = float(lon)
    except (TypeError, ValueError):
        return False
    lat_min, lat_max, lon_min, lon_max = bbox
    if lat_min <= la <= lat_max and lon_min <= lo <= lon_max:
        return True
    if lo > 0 and lon_min < 0:
        return lat_min <= la <= lat_max and lon_min <= -lo <= lon_max
    return False


def location_matches_place(
    place: str,
    *,
    location: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    original_filename: str | None = None,
    extra_text: str | None = None,
) -> bool:
    needles = place_needles(place)
    if not needles:
        return False
    blob = " ".join(
        _norm(x)
        for x in (
            location,
            city,
            state,
            country,
            original_filename,
            extra_text,
        )
        if x
    )
    if _blob_matches(blob, needles, state=state):
        return True
    return _in_bbox(latitude, longitude, place_bbox(place))


def hit_matches_place(hit: Any, place: str) -> bool:
    extra_bits: list[str] = []
    exif = getattr(hit, "exif", None)
    if isinstance(exif, dict):
        extra_bits.extend(str(v) for v in exif.values() if v)
    albums = getattr(hit, "albums", None)
    if albums:
        extra_bits.extend(str(a) for a in albums if a)
    return location_matches_place(
        place,
        location=getattr(hit, "location", None),
        city=getattr(hit, "city", None),
        state=getattr(hit, "state", None),
        country=getattr(hit, "country", None),
        latitude=getattr(hit, "latitude", None),
        longitude=getattr(hit, "longitude", None),
        original_filename=getattr(hit, "original_filename", None),
        extra_text=" ".join(extra_bits) if extra_bits else None,
    )


def filter_photo_hits_to_places(
    hits: list[Any],
    place_names: tuple[str, ...] | list[str] | None,
) -> list[Any]:
    places = [str(p).strip() for p in (place_names or ()) if str(p).strip()]
    if not places:
        return list(hits)
    return [h for h in hits if any(hit_matches_place(h, p) for p in places)]
