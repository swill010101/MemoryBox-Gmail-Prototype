"""MemoryBox-owned face embeddings (same model as video). Immich vectors unused."""
from __future__ import annotations

import math
from typing import Any, Sequence

from memorybox.recognition.constants import MODEL_ID

_APP = None
_APP_ERROR: str | None = None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        xf = float(x)
        yf = float(y)
        dot += xf * yf
        na += xf * xf
        nb += yf * yf
    if na < 1e-18 or nb < 1e-18:
        return -1.0
    return float(dot / math.sqrt(na * nb))


def insightface_available() -> bool:
    try:
        from insightface.app import FaceAnalysis  # noqa: F401
    except Exception:
        return False
    return True


def _face_app():
    global _APP, _APP_ERROR
    if _APP is not None:
        return _APP
    if _APP_ERROR:
        raise RuntimeError(_APP_ERROR)
    try:
        from insightface.app import FaceAnalysis
    except ImportError as exc:
        _APP_ERROR = (
            "InsightFace not installed — I8B video scan needs insightface "
            "(onnxruntime). Harness tests inject embeddings without it."
        )
        raise RuntimeError(_APP_ERROR) from exc
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    _APP = app
    return _APP


def embed_bgr_crop(bgr: Any) -> list[float] | None:
    """Embed an OpenCV BGR crop. Returns None if no face is detected."""
    app = _face_app()
    faces = app.get(bgr)
    if not faces:
        return None
    faces = sorted(faces, key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])), reverse=True)
    emb = getattr(faces[0], "embedding", None)
    if emb is None:
        return None
    return [float(x) for x in list(emb)]


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    den = area_a + area_b - inter
    return float(inter / den) if den else 0.0


def decode_to_bgr(data: bytes) -> Any | None:
    """Decode JPEG/WebP preview bytes. cv2 often misses WebP; PIL is the fallback."""
    if not data:
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = None
        np = None
    if cv2 is not None and np is not None:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    try:
        import io
        from PIL import Image
        import numpy as np
        import cv2
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    rgb = np.array(im)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def embed_image_bytes_for_bbox(
    data: bytes,
    bbox: dict[str, float],
    *,
    image_w: float | None = None,
    image_h: float | None = None,
) -> list[float] | None:
    """Detect+embed using Immich box on the fetched preview (padded, then full-frame IoU)."""
    from memorybox.recognition.crops import mapped_pixel_box

    bgr = decode_to_bgr(data)
    if bgr is None:
        return None
    h, w = int(bgr.shape[0]), int(bgr.shape[1])
    mapped = mapped_pixel_box(
        bbox,
        pixel_w=w,
        pixel_h=h,
        image_w=image_w,
        image_h=image_h,
        pad_ratio=0.45,
    )
    if mapped:
        x1, y1, x2, y2 = mapped
        crop = bgr[y1:y2, x1:x2]
        if crop.size:
            got = embed_bgr_crop(crop)
            if got:
                return got
    app = _face_app()
    faces = app.get(bgr)
    if not faces:
        return None
    target = mapped or (
        int(bbox.get("x1") or 0),
        int(bbox.get("y1") or 0),
        int(bbox.get("x2") or 0),
        int(bbox.get("y2") or 0),
    )
    best = None
    best_iou = 0.0
    for f in faces:
        fb = tuple(float(x) for x in f.bbox[:4])
        score = _iou(target, fb)
        if score > best_iou:
            best_iou = score
            best = f
    if best is None or best_iou < 0.12 or getattr(best, "embedding", None) is None:
        return None
    return [float(x) for x in list(best.embedding)]


def pad_bgr_for_detector(bgr: Any, *, pad_ratio: float = 0.45, min_side: int = 160) -> Any:
    """Widen a tight owner box so buffalo_l can still detect a face."""
    import cv2

    h, w = int(bgr.shape[0]), int(bgr.shape[1])
    pad_w = max(8, int(w * pad_ratio))
    pad_h = max(8, int(h * pad_ratio))
    out = cv2.copyMakeBorder(bgr, pad_h, pad_h, pad_w, pad_w, cv2.BORDER_REPLICATE)
    oh, ow = int(out.shape[0]), int(out.shape[1])
    scale = max(1.0, float(min_side) / float(max(1, min(oh, ow))))
    if scale > 1.05:
        out = cv2.resize(
            out,
            (max(min_side, int(ow * scale)), max(min_side, int(oh * scale))),
            interpolation=cv2.INTER_CUBIC,
        )
    return out


def embed_jpeg_bytes(data: bytes) -> list[float] | None:
    if not data:
        return None
    img = decode_to_bgr(data)
    if img is None:
        try:
            import cv2  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("opencv-python required to embed JPEG crops") from exc
        return None
    got = embed_bgr_crop(img)
    if got:
        return got
    try:
        padded = pad_bgr_for_detector(img)
    except Exception:
        return None
    return embed_bgr_crop(padded)


def model_id() -> str:
    return MODEL_ID
