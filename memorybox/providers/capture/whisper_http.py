"""OpenAI-compatible Whisper HTTP Capture/STT adapter."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import httpx

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.capture.protocol import AudioHandle, TranscriptDraft


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


class WhisperHttpCaptureStt:
    provider_key = "whisper_http"

    def __init__(
        self,
        *,
        root: Path | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 300,
    ) -> None:
        base = _env("MEMORYBOX_CAPTURE_DIR")
        self._root = root or Path(base) if base else Path.cwd() / ".memorybox_capture"
        self._root.mkdir(parents=True, exist_ok=True)
        self._endpoint = endpoint or _env("MEMORYBOX_WHISPER_ENDPOINT")
        self._api_key = api_key if api_key is not None else (_env("MEMORYBOX_WHISPER_API_KEY") or "")
        self._model = model or _env("MEMORYBOX_WHISPER_HTTP_MODEL", "whisper-1") or "whisper-1"
        self._timeout = timeout_seconds
        self._index: dict[str, Path] = {}

    def health(self) -> ProviderHealth:
        if not self._endpoint:
            return ProviderHealth(
                provider_key=self.provider_key,
                ok=False,
                detail="MEMORYBOX_WHISPER_ENDPOINT not set",
            )
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=True,
            detail="whisper_http endpoint configured",
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
        if not self._endpoint:
            raise ProviderUnavailable("MEMORYBOX_WHISPER_ENDPOINT not set")
        path = self._resolve_path(audio_id)
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            with path.open("rb") as fh:
                files = {"file": (path.name, fh, "application/octet-stream")}
                data = {"model": self._model}
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(
                        self._endpoint, headers=headers, data=data, files=files
                    )
                    resp.raise_for_status()
                    payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"whisper_http failed: {exc}") from exc
        text = ""
        if isinstance(payload, dict):
            text = str(payload.get("text") or "").strip()
        else:
            text = str(payload).strip()
        if not text:
            raise ProviderError("STT produced empty transcript")
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
