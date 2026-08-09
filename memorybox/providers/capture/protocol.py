"""Capture / STT provider protocol (Increment 5A) — Journal must not import Whisper."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from memorybox.providers.base import ProviderHealth


@dataclass(frozen=True)
class AudioHandle:
    """Opaque preserved-audio reference (not a Journal row)."""

    audio_id: str
    audio_uri: str
    content_type: str | None = None
    byte_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptDraft:
    """STT draft — not Journal truth until explicit Save."""

    audio_id: str
    audio_uri: str
    text: str
    provider_key: str
    language: str | None = None
    confidence: float | None = None
    status: str = "draft"
    duration_sec: float | None = None
    rms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Never imply persisted Journal
        d["persisted_as_journal"] = False
        return d


class CaptureSttProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def preserve_audio(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> AudioHandle: ...

    def transcribe(self, audio_id: str) -> TranscriptDraft: ...

    def preserve_and_transcribe(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> TranscriptDraft: ...
