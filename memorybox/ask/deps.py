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


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def build_llm(cfg: Settings | None = None) -> LlmProvider:
    cfg = cfg or settings
    if not cfg.ollama_base_url:
        return FakeLlmProvider()
    try:
        from memorybox.providers.llm.ollama import OllamaLlmProvider

        p = OllamaLlmProvider(
            base_url=cfg.ollama_base_url,
            chat_model=cfg.ollama_chat_model,
            embed_model=cfg.ollama_embed_model,
        )
        if p.health().ok:
            return p
    except Exception:  # noqa: BLE001
        pass
    return FakeLlmProvider()


def build_photo(cfg: Settings | None = None) -> PhotoProvider:
    """Select photo provider via MEMORYBOX_PHOTO_PROVIDER.

    Values: immich (default when immich.env present) | fake | unavailable
    Path to immich env: MEMORYBOX_IMMICH_ENV (optional).
    """
    cfg = cfg or settings
    mode = (_env("MEMORYBOX_PHOTO_PROVIDER") or "").lower()
    if mode == "unavailable":
        return UnavailablePhotoProvider()
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
            except Exception:  # noqa: BLE001 — treat as unavailable, not empty
                return UnavailablePhotoProvider()
        if mode == "immich":
            return UnavailablePhotoProvider()
        # auto: no immich.env → fake for desktop prove
        if getattr(cfg, "allow_dev_defaults", False):
            return FakePhotoProvider()
        return UnavailablePhotoProvider()

    return UnavailablePhotoProvider()


def provider_snapshot(photo: PhotoProvider, llm: LlmProvider) -> dict[str, Any]:
    ph = photo.health()
    lh = llm.health()
    return {
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
