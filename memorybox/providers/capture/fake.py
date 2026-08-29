"""Fake Capture/STT for harness proves — no Whisper dependency."""
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from memorybox.providers.base import ProviderHealth
from memorybox.providers.capture.protocol import AudioHandle, TranscriptDraft


class FakeCaptureSttProvider:
    provider_key = "fake_capture_stt"

    def __init__(self, *, root: Path | None = None, transcript: str = "fake spoken journal draft") -> None:
        self._root = root or Path.cwd() / ".memorybox_capture_fake"
        self._root.mkdir(parents=True, exist_ok=True)
        self._transcript = transcript
        self._index: dict[str, Path] = {}

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key, ok=True, detail="fake_capture_stt ready"
        )

    def preserve_audio(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> AudioHandle:
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

    def transcribe(self, audio_id: str) -> TranscriptDraft:
        path = self._index.get(audio_id)
        if path is None:
            # Allow resolve by scanning root
            matches = list(self._root.glob(f"{audio_id}.*"))
            if not matches:
                raise FileNotFoundError(f"audio_id not found: {audio_id}")
            path = matches[0]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        text = f"{self._transcript} [{digest}]"
        return TranscriptDraft(
            audio_id=audio_id,
            audio_uri=path.resolve().as_uri(),
            text=text,
            provider_key=self.provider_key,
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

    def resolve_audio_path(self, audio_id: str) -> Path | None:
        path = self._index.get(audio_id)
        if path and path.is_file():
            return path
        matches = list(self._root.glob(f"{audio_id}.*"))
        return matches[0] if matches else None

    def discard_audio(self, audio_id: str) -> bool:
        removed = False
        for path in list(self._root.glob(f"{audio_id}.*")):
            try:
                path.unlink()
                removed = True
            except OSError:
                pass
        self._index.pop(audio_id, None)
        return removed
