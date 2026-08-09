"""Local faster-whisper Capture/STT adapter (FlightSim default when installed)."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.capture.protocol import AudioHandle, TranscriptDraft


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


class FasterWhisperCaptureStt:
    """Whisper behind Capture/STT boundary — Journal must not import this module."""

    provider_key = "faster_whisper"

    def __init__(
        self,
        *,
        root: Path | None = None,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
    ) -> None:
        base = _env("MEMORYBOX_CAPTURE_DIR")
        self._root = root or Path(base) if base else Path.cwd() / ".memorybox_capture"
        self._root.mkdir(parents=True, exist_ok=True)
        self._model_size = model_size or _env("MEMORYBOX_WHISPER_MODEL", "base") or "base"
        self._device = device or _env("MEMORYBOX_WHISPER_DEVICE", "auto") or "auto"
        self._compute = compute_type or _env("MEMORYBOX_WHISPER_COMPUTE", "default") or "default"
        self._language = language or _env("MEMORYBOX_WHISPER_LANGUAGE")
        self._index: dict[str, Path] = {}

    def health(self) -> ProviderHealth:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return ProviderHealth(
                provider_key=self.provider_key,
                ok=False,
                detail="faster-whisper not installed (pip install faster-whisper)",
            )
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=True,
            detail=f"faster_whisper model={self._model_size} device={self._device}",
        )

    def preserve_audio(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> AudioHandle:
        if not data:
            raise ProviderError("empty audio payload")
        audio_id = str(uuid4())
        ext = Path(filename or "clip.webm").suffix or ".webm"
        path = self._root / f"{audio_id}{ext}"
        path.write_bytes(data)
        self._index[audio_id] = path
        return AudioHandle(
            audio_id=audio_id,
            audio_uri=path.resolve().as_uri(),
            content_type=content_type,
            byte_count=len(data),
        )

    def _resolve_path(self, audio_id: str) -> Path:
        path = self._index.get(audio_id)
        if path and path.is_file():
            return path
        matches = list(self._root.glob(f"{audio_id}.*"))
        if not matches:
            raise ProviderError(f"audio_id not found: {audio_id}")
        return matches[0]

    def transcribe(self, audio_id: str) -> TranscriptDraft:
        path = self._resolve_path(audio_id)
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderUnavailable(
                "faster-whisper not installed. pip install faster-whisper"
            ) from exc

        device = self._device
        compute = self._compute
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        if compute == "default":
            compute = "float16" if device == "cuda" else "int8"

        model_dir = self._root / "whisper-models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=compute,
            download_root=str(model_dir),
        )
        segments_iter, info = model.transcribe(
            str(path),
            language=self._language,
            vad_filter=True,
        )
        texts: list[str] = []
        for seg in segments_iter:
            t = (seg.text or "").strip()
            if t:
                texts.append(t)
        text = " ".join(texts).strip()
        if not text:
            raise ProviderError("STT produced empty transcript")
        lang = getattr(info, "language", None) or self._language
        return TranscriptDraft(
            audio_id=audio_id,
            audio_uri=path.resolve().as_uri(),
            text=text,
            provider_key=self.provider_key,
            language=str(lang) if lang else None,
            status="draft",
        )

    def preserve_and_transcribe(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> TranscriptDraft:
        handle = self.preserve_audio(data, filename=filename, content_type=content_type)
        return self.transcribe(handle.audio_id)
