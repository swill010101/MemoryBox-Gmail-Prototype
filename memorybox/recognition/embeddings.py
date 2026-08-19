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


def embed_jpeg_bytes(data: bytes) -> list[float] | None:
    if not data:
        return None
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("opencv-python required to embed JPEG crops") from exc
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return embed_bgr_crop(img)


def model_id() -> str:
    return MODEL_ID
