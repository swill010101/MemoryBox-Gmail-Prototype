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


def mapped_pixel_box(
    bbox: dict[str, float],
    *,
    pixel_w: int,
    pixel_h: int,
    image_w: float | None = None,
    image_h: float | None = None,
    pad_ratio: float = 0.4,
) -> tuple[int, int, int, int] | None:
    """Map Immich box onto the bytes we actually fetched (preview/thumb).

    If the box already fits the fetched image, treat it as pixel space.
    Otherwise scale from Immich imageWidth/imageHeight. Pad so buffalo_l
    can detect a face (tight crops often miss).
    """
    if pixel_w < 1 or pixel_h < 1:
        return None
    x2 = float(bbox.get("x2") or 0)
    y2 = float(bbox.get("y2") or 0)
    fits = x2 <= pixel_w * 1.08 and y2 <= pixel_h * 1.08
    if fits:
        sx, sy = 1.0, 1.0
    else:
        src_w = float(image_w or pixel_w) or float(pixel_w)
        src_h = float(image_h or pixel_h) or float(pixel_h)
        sx = pixel_w / src_w if src_w else 1.0
        sy = pixel_h / src_h if src_h else 1.0
    x1 = float(bbox["x1"]) * sx
    y1 = float(bbox["y1"]) * sy
    x2 = float(bbox["x2"]) * sx
    y2 = float(bbox["y2"]) * sy
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    pad = max(0.0, float(pad_ratio))
    x1 = max(0.0, x1 - bw * pad)
    y1 = max(0.0, y1 - bh * pad)
    x2 = min(float(pixel_w), x2 + bw * pad)
    y2 = min(float(pixel_h), y2 + bh * pad)
    ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
    if ix2 - ix1 < MIN_CROP_PX or iy2 - iy1 < MIN_CROP_PX:
        return None
    return ix1, iy1, ix2, iy2


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
    mapped = mapped_pixel_box(
        bbox,
        pixel_w=pw,
        pixel_h=ph,
        image_w=image_w,
        image_h=image_h,
        pad_ratio=0.4,
    )
    if not mapped:
        return None
    x1, y1, x2, y2 = mapped
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
