"""Local faster-whisper Capture/STT adapter (FlightSim default when installed)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.capture.protocol import AudioHandle, TranscriptDraft

# Process-wide model cache (first load is slow; avoid reloading per request)
_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def _ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def _to_wav_for_whisper(src: Path) -> Path:
    """Normalize browser WebM/Opus (etc.) to 16 kHz mono WAV for reliable decode."""
    if src.suffix.lower() == ".wav":
        return src
    wav = src.with_suffix(".wav")
    if wav.is_file() and wav.stat().st_size > 44:
        return wav

    ffmpeg = _ffmpeg_bin()
    if ffmpeg:
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(src),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-f",
                    "wav",
                    str(wav),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            if wav.is_file() and wav.stat().st_size > 44:
                return wav
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass

    # Fallback: PyAV re-encode when ffmpeg CLI is missing
    try:
        import av
        import numpy as np
    except ImportError as exc:
        raise ProviderError(
            f"Cannot decode {src.suffix} audio (install ffmpeg on PATH, or ensure PyAV works). "
            f"Original file kept at {src}"
        ) from exc

    try:
        container = av.open(str(src))
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ProviderError(f"No audio stream in {src.name}")
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
        frames_out: list[np.ndarray] = []
        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                arr = rf.to_ndarray()
                if arr.ndim > 1:
                    arr = arr[0]
                frames_out.append(arr.astype(np.int16, copy=False))
        # flush
        for rf in resampler.resample(None):
            arr = rf.to_ndarray()
            if arr.ndim > 1:
                arr = arr[0]
            frames_out.append(arr.astype(np.int16, copy=False))
        container.close()
        if not frames_out:
            raise ProviderError(f"Decoded empty audio from {src.name}")
        pcm = np.concatenate(frames_out)
        # Write minimal WAV
        import wave

        with wave.open(str(wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())
        return wav
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(
            f"Audio decode failed for {src.name}: {exc}. "
            "Install ffmpeg on PATH for browser WebM clips."
        ) from exc


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
        self._root = Path(base) if base else (root or Path.cwd() / ".memorybox_capture")
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
        ff = _ffmpeg_bin()
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=True,
            detail=(
                f"faster_whisper model={self._model_size} device={self._device} "
                f"ffmpeg={'yes' if ff else 'no'}"
            ),
            meta={"ffmpeg": bool(ff)},
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
        # Prefer original over derived .wav
        originals = [p for p in matches if p.suffix.lower() != ".wav"]
        if originals:
            return originals[0]
        if matches:
            return matches[0]
        raise ProviderError(f"audio_id not found: {audio_id}")

    def _get_model(self, device: str, compute: str):
        key = (self._model_size, device, compute)
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        from faster_whisper import WhisperModel

        model_dir = self._root / "whisper-models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=compute,
            download_root=str(model_dir),
        )
        _MODEL_CACHE[key] = model
        return model

    def transcribe(self, audio_id: str) -> TranscriptDraft:
        path = self._resolve_path(audio_id)
        try:
            from faster_whisper import WhisperModel  # noqa: F401
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

        wav_path = _to_wav_for_whisper(path)
        try:
            model = self._get_model(device, compute)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Whisper model load failed ({self._model_size}/{device}/{compute}): {exc}"
            ) from exc

        try:
            segments_iter, info = model.transcribe(
                str(wav_path),
                language=self._language or "en",
                vad_filter=True,
            )
            texts: list[str] = []
            for seg in segments_iter:
                t = (seg.text or "").strip()
                if t:
                    texts.append(t)
            text = " ".join(texts).strip()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Whisper transcribe failed: {exc}") from exc

        if not text:
            raise ProviderError(
                "STT produced empty transcript (speak longer, or check mic levels). "
                f"Audio preserved as {audio_id}"
            )
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
