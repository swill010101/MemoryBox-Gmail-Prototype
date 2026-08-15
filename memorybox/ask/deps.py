"""Wire Ask dependencies from host-portable configuration (D7)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from memorybox.config import Settings, settings
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.llm.protocol import LlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.photo.protocol import PhotoProvider
from memorybox.providers.photo.unavailable import UnavailablePhotoProvider
from memorybox.providers.video.fake import FakeVideoProvider
from memorybox.providers.video.protocol import VideoIntelligenceProvider
from memorybox.providers.video.unavailable import UnavailableVideoProvider


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def _presence_gap_sec() -> float:
    raw = _env("MEMORYBOX_VIDEO_PRESENCE_GAP_SEC", "60")
    try:
        return float(raw or "60")
    except ValueError:
        return 60.0


def build_llm(cfg: Settings | None = None) -> LlmProvider:
    from memorybox.ai_trace.wrapper import trace_llm

    cfg = cfg or settings
    if not cfg.ollama_base_url:
        return trace_llm(FakeLlmProvider())
    try:
        from memorybox.providers.llm.ollama import OllamaLlmProvider

        p = OllamaLlmProvider(
            base_url=cfg.ollama_base_url,
            chat_model=cfg.ollama_chat_model,
            embed_model=cfg.ollama_embed_model,
        )
        if p.health().ok:
            return trace_llm(p)
    except Exception:  # noqa: BLE001
        pass
    return trace_llm(FakeLlmProvider())


def build_photo(cfg: Settings | None = None) -> PhotoProvider:
    """Select photo provider via MEMORYBOX_PHOTO_PROVIDER.

    Values: immich (default when immich.env present) | fake | unavailable
    Path to immich env: MEMORYBOX_IMMICH_ENV (optional).
    """
    cfg = cfg or settings
    mode = (_env("MEMORYBOX_PHOTO_PROVIDER") or "").lower()
    if mode == "unavailable":
        return UnavailablePhotoProvider(
            "MEMORYBOX_PHOTO_PROVIDER=unavailable (deliberate I4-G mode)"
        )
    if mode == "fake":
        return FakePhotoProvider()

    env_path = _env("MEMORYBOX_IMMICH_ENV")
    path = (
        Path(env_path)
        if env_path
        else Path(__file__).resolve().parents[2] / "config" / "immich.env"
    )

    if mode in ("", "immich", "auto"):
        if path.is_file():
            try:
                from memorybox.providers.photo.immich import ImmichPhotoProvider

                return ImmichPhotoProvider(env_path=path)
            except Exception as exc:  # noqa: BLE001 — treat as unavailable, not empty
                return UnavailablePhotoProvider(
                    f"Immich init failed ({path}): {exc}"
                )
        missing = f"missing Immich env file: {path}"
        if mode == "immich":
            return UnavailablePhotoProvider(missing)
        if getattr(cfg, "allow_dev_defaults", False):
            return FakePhotoProvider()
        return UnavailablePhotoProvider(
            f"{missing}; set MEMORYBOX_IMMICH_ENV or create config/immich.env"
        )

    return UnavailablePhotoProvider(f"unknown MEMORYBOX_PHOTO_PROVIDER={mode!r}")


def build_video(cfg: Settings | None = None) -> VideoIntelligenceProvider:
    """Select video intelligence provider via MEMORYBOX_VIDEO_PROVIDER.

    Values: hvrt | fake | unavailable | auto (default).
    Worker URL: MEMORYBOX_VIDEO_WORKER_URL (e.g. http://127.0.0.1:8791).
    """
    cfg = cfg or settings
    mode = (_env("MEMORYBOX_VIDEO_PROVIDER") or "auto").lower()
    if mode == "unavailable":
        return UnavailableVideoProvider(
            "MEMORYBOX_VIDEO_PROVIDER=unavailable (deliberate degrade mode)"
        )
    if mode == "fake":
        return FakeVideoProvider(presence_gap_sec=_presence_gap_sec())

    worker_url = _env("MEMORYBOX_VIDEO_WORKER_URL")
    if mode in ("", "hvrt", "auto"):
        if worker_url:
            try:
                from memorybox.providers.video.hvrt_http import HvrtHttpVideoProvider

                return HvrtHttpVideoProvider(base_url=worker_url)
            except Exception as exc:  # noqa: BLE001
                return UnavailableVideoProvider(f"video worker init failed: {exc}")
        if mode == "hvrt":
            return UnavailableVideoProvider(
                "MEMORYBOX_VIDEO_WORKER_URL required when MEMORYBOX_VIDEO_PROVIDER=hvrt"
            )
        if getattr(cfg, "allow_dev_defaults", False):
            return FakeVideoProvider(presence_gap_sec=_presence_gap_sec())
        return UnavailableVideoProvider(
            "set MEMORYBOX_VIDEO_WORKER_URL or MEMORYBOX_VIDEO_PROVIDER=fake"
        )

    return UnavailableVideoProvider(f"unknown MEMORYBOX_VIDEO_PROVIDER={mode!r}")


def provider_snapshot(
    photo: PhotoProvider,
    llm: LlmProvider,
    video: VideoIntelligenceProvider | None = None,
) -> dict[str, Any]:
    ph = photo.health()
    lh = llm.health()
    out: dict[str, Any] = {
        "photo": {
            "provider_key": ph.provider_key,
            "ok": ph.ok,
            "detail": ph.detail,
        },
        "llm": {
            "provider_key": lh.provider_key,
            "ok": lh.ok,
            "detail": lh.detail,
        },
    }
    if video is not None:
        vh = video.health()
        out["video"] = {
            "provider_key": vh.provider_key,
            "ok": vh.ok,
            "detail": vh.detail,
        }
    return out
