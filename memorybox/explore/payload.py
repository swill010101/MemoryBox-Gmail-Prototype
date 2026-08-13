"""P2-I4 Explore API helpers — normalize demo/fixture payloads for the UI."""
from __future__ import annotations

from typing import Any

from memorybox.explore.fixture import peggy_christmas_fixture


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Map fixture fields to the explore UI contract (type/preview/detail)."""
    kind = str(raw.get("type") or raw.get("kind") or "artifact").lower()
    title = str(raw.get("title") or kind)
    excerpt = str(raw.get("excerpt") or raw.get("preview") or "")
    detail = str(raw.get("detail") or excerpt or title)
    out = dict(raw)
    out["type"] = kind
    out["kind"] = kind
    out["title"] = title
    out["preview"] = excerpt
    out["detail"] = detail
    out["date"] = str(raw.get("date") or "")[:10] if raw.get("date") else ""
    out["undated"] = bool(raw.get("undated") or not raw.get("date"))
    # Preserve place / map coords when present (never invent).
    if raw.get("place") and not out.get("location"):
        out["location"] = raw.get("place")
    lat = raw.get("lat", raw.get("latitude"))
    lng = raw.get("lng", raw.get("longitude"))
    try:
        if lat is not None and lng is not None:
            out["lat"] = float(lat)
            out["lng"] = float(lng)
            out["latitude"] = out["lat"]
            out["longitude"] = out["lng"]
    except (TypeError, ValueError):
        out.pop("lat", None)
        out.pop("lng", None)
    return out


def demo_payload(demo_id: str) -> dict[str, Any] | None:
    """Return a UI-ready demo payload, or None if unknown."""
    key = (demo_id or "").strip().lower().replace("_", "-")
    if key in ("peggy-christmas", "peggy", "christmas"):
        fix = peggy_christmas_fixture()
        items = [_normalize_item(i) for i in fix.get("items") or []]
        return {
            "ok": True,
            "demo": True,
            "fixture_id": fix.get("fixture_id") or "peggy-christmas",
            "ask_text": fix.get("query") or "",
            "title": fix.get("title") or "Memories",
            "summary": fix.get("curator") or fix.get("summary") or "",
            "chips": fix.get("chips") or [],
            "range": fix.get("range") or {},
            "items": items,
            "counts": fix.get("counts") or {},
        }
    return None
