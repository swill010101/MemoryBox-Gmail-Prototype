"""Capture/STT factory — config-only provider selection (D7)."""
from __future__ import annotations

import os

from memorybox.providers.capture.fake import FakeCaptureSttProvider
from memorybox.providers.capture.faster_whisper import FasterWhisperCaptureStt
from memorybox.providers.capture.protocol import CaptureSttProvider
from memorybox.providers.capture.whisper_http import WhisperHttpCaptureStt


def _provider_name() -> str:
    return (os.environ.get("MEMORYBOX_STT_PROVIDER") or "auto").strip().lower()


def build_capture_stt() -> CaptureSttProvider:
    """Resolve Capture/STT provider.

    MEMORYBOX_STT_PROVIDER:
      - auto (default): whisper_http if endpoint set, else faster_whisper if importable, else fake
      - faster_whisper | whisper_http | fake
    """
    name = _provider_name()
    if name == "fake":
        return FakeCaptureSttProvider()
    if name == "whisper_http":
        return WhisperHttpCaptureStt()
    if name == "faster_whisper":
        return FasterWhisperCaptureStt()

    # auto
    if os.environ.get("MEMORYBOX_WHISPER_ENDPOINT", "").strip():
        return WhisperHttpCaptureStt()
    try:
        import faster_whisper  # noqa: F401

        return FasterWhisperCaptureStt()
    except ImportError:
        return FakeCaptureSttProvider()
