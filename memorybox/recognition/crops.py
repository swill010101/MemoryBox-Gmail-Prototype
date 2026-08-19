"""Pragmatic crop helpers — reject unusable boxes; no quality-research stack."""
from __future__ import annotations

from typing import Any

from memorybox.recognition.constants import MIN_CROP_PX


def _num(value: Any) -> float | None:
    if value is None or value is False:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bbox(raw: dict[str, Any] | None) -> dict[str, float] | None:
    """Parse Immich/Review boxes. Keys may be present with null values."""
    if not isinstance(raw, dict):
        return None
    # Immich GET /faces uses boundingBoxX1..Y2; x1..y2 are often absent/null.
    bx1 = _num(raw.get("boundingBoxX1"))
    by1 = _num(raw.get("boundingBoxY1"))
    bx2 = _num(raw.get("boundingBoxX2"))
    by2 = _num(raw.get("boundingBoxY2"))
    x1 = _num(raw.get("x1"))
    y1 = _num(raw.get("y1"))
    x2 = _num(raw.get("x2"))
    y2 = _num(raw.get("y2"))
    x = _num(raw.get("x"))
    y = _num(raw.get("y"))
    w = _num(raw.get("w"))
    h = _num(raw.get("h"))
    if None not in (bx1, by1, bx2, by2):
        x1, y1, x2, y2 = bx1, by1, bx2, by2
    elif None not in (x1, y1, x2, y2):
        pass
    elif None not in (x, y, w, h):
        x1, y1, x2, y2 = x, y, x + w, y + h
    else:
        return None
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    w = x2 - x1
    h = y2 - y1
    if w < 1 or h < 1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": w, "h": h}


def quality_flags(bbox: dict[str, float], *, image_w: float | None = None, image_h: float | None = None) -> dict[str, Any]:
    w = float(bbox.get("w") or 0)
    h = float(bbox.get("h") or 0)
    usable = w >= MIN_CROP_PX and h >= MIN_CROP_PX
    aspect = (w / h) if h else 0.0
    if aspect < 0.35 or aspect > 2.8:
        usable = False
    flags = {
        "usable": usable,
        "width_px": w,
        "height_px": h,
        "aspect": round(aspect, 3),
        "image_w": image_w,
        "image_h": image_h,
        "reject_reason": None if usable else "unusable_crop",
    }
    return flags


def crop_jpeg_bytes(
    image_bytes: bytes,
    bbox: dict[str, float],
    *,
    image_w: float | None = None,
    image_h: float | None = None,
) -> bytes | None:
    """Crop using preview pixels. Scale bbox if Immich imageWidth/Height differ."""
    try:
        from PIL import Image
        import io
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    pw, ph = im.size
    src_w = float(image_w or pw)
    src_h = float(image_h or ph)
    sx = pw / src_w if src_w else 1.0
    sy = ph / src_h if src_h else 1.0
    x1 = max(0, int(bbox["x1"] * sx))
    y1 = max(0, int(bbox["y1"] * sy))
    x2 = min(pw, int(bbox["x2"] * sx))
    y2 = min(ph, int(bbox["y2"] * sy))
    if x2 - x1 < MIN_CROP_PX or y2 - y1 < MIN_CROP_PX:
        return None
    cropped = im.crop((x1, y1, x2, y2))
    out = io.BytesIO()
    cropped.save(out, format="JPEG", quality=90)
    return out.getvalue()


def decode_data_url_jpeg(raw: str | None) -> bytes | None:
    if not raw:
        return None
    s = raw.strip()
    if "," in s and s.lower().startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        import base64

        return base64.b64decode(s)
    except Exception:
        return None
