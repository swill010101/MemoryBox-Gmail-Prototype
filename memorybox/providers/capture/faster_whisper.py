"""Local faster-whisper Capture/STT adapter (FlightSim default when installed)."""
from __future__ import annotations

import os
import shutil
import subprocess
import wave
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
    """Resolve ffmpeg even when the serve shell missed a refreshed PATH."""
    which = shutil.which("ffmpeg")
    if which:
        return which
    local = os.environ.get("LOCALAPPDATA") or ""
    roots = [
        Path(local) / "Microsoft" / "WinGet" / "Packages",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ffmpeg" / "bin",
        Path(r"C:\ffmpeg\bin"),
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.name.lower() == "ffmpeg.exe":
            return str(root)
        # WinGet Gyan.FFmpeg layout
        for cand in root.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
            return str(cand)
        direct = root / "ffmpeg.exe"
        if direct.is_file():
            return str(direct)
    return None


def _to_wav_for_whisper(src: Path) -> Path:
    """Normalize browser WebM/Opus (etc.) to 16 kHz mono WAV for reliable decode."""
    if src.suffix.lower() == ".wav" and src.stat().st_size > 44:
        return src
    wav = src.with_suffix(".wav")
    if wav.is_file() and wav.stat().st_size > 44:
        return wav

    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise ProviderError(
            "ffmpeg not found on PATH (required to decode browser WebM). "
            "Install Gyan.FFmpeg, open a NEW PowerShell, verify `ffmpeg -version`, restart serve."
        )

    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-y",
                "-i",
                str(src),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            check=False,
            capture_output=True,
            timeout=120,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProviderError(f"ffmpeg timed out converting {src.name}") from exc
    except OSError as exc:
        raise ProviderError(f"ffmpeg failed to start ({ffmpeg}): {exc}") from exc

    if proc.returncode != 0 or not wav.is_file() or wav.stat().st_size <= 44:
        err = (proc.stderr or proc.stdout or "").strip()
        tail = err[-800:] if err else f"exit={proc.returncode}"
        raise ProviderError(
            f"ffmpeg could not convert {src.name} → wav. {tail}"
        )
    return wav


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
        # Windows HF downloads often fail without this (symlink privilege).
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        base = _env("MEMORYBOX_CAPTURE_DIR")
        self._root = Path(base) if base else (root or Path.cwd() / ".memorybox_capture")
        self._root.mkdir(parents=True, exist_ok=True)
        # base = better short-phrase accuracy than tiny; override with MEMORYBOX_WHISPER_MODEL
        self._model_size = model_size or _env("MEMORYBOX_WHISPER_MODEL", "base") or "base"
        self._device = device or _env("MEMORYBOX_WHISPER_DEVICE", "cpu") or "cpu"
        self._compute = compute_type or _env("MEMORYBOX_WHISPER_COMPUTE", "int8") or "int8"
        self._language = language or _env("MEMORYBOX_WHISPER_LANGUAGE", "en") or "en"
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
            ok=bool(ff),
            detail=(
                f"faster_whisper model={self._model_size} device={self._device} "
                f"compute={self._compute} ffmpeg={ff or 'MISSING'}"
            ),
            meta={"ffmpeg": ff, "model": self._model_size},
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
        if len(data) < 256:
            raise ProviderError(
                f"audio payload too small ({len(data)} bytes) — record longer before Stop"
            )
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
        originals = [
            p
            for p in matches
            if p.suffix.lower() not in {".wav", ".txt", ".json"}
        ]
        if originals:
            self._index[audio_id] = originals[0]
            return originals[0]
        if matches:
            self._index[audio_id] = matches[0]
            return matches[0]
        raise ProviderError(
            f"audio_id not found under {self._root}: {audio_id}"
        )

    def _get_model(self, device: str, compute: str):
        key = (self._model_size, device, compute)
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        from faster_whisper import WhisperModel

        model_dir = self._root / "whisper-models"
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            model = WhisperModel(
                self._model_size,
                device=device,
                compute_type=compute,
                download_root=str(model_dir),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Whisper model load failed ({self._model_size}/{device}/{compute}): {exc}. "
                "On Windows set HF_HUB_DISABLE_SYMLINKS=1 (already attempted). "
                "Check network access to Hugging Face for first download."
            ) from exc
        _MODEL_CACHE[key] = model
        return model

    def _wav_stats(self, wav_path: Path) -> tuple[float, float]:
        """Return (duration_sec, peak-normalized RMS 0..1)."""
        import array
        import math

        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate() or 16000
            duration = frames / float(rate)
            raw = wf.readframes(frames)
            width = wf.getsampwidth()
        if width != 2 or not raw:
            return duration, 0.0
        samples = array.array("h")
        samples.frombytes(raw)
        if not samples:
            return duration, 0.0
        acc = 0.0
        for s in samples:
            acc += float(s) * float(s)
        rms = math.sqrt(acc / len(samples)) / 32768.0
        return duration, rms

    def _transcribe_wav(self, wav_path: Path, *, vad_filter: bool) -> tuple[str, str | None]:
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

        model = self._get_model(device, compute)
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=self._language,
            vad_filter=vad_filter,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.5,
        )
        texts: list[str] = []
        for seg in segments_iter:
            t = (seg.text or "").strip()
            if t:
                texts.append(t)
        text = " ".join(texts).strip()
        lang = getattr(info, "language", None) or self._language
        return text, str(lang) if lang else None

    def transcribe(self, audio_id: str) -> TranscriptDraft:
        path = self._resolve_path(audio_id)
        try:
            import faster_whisper  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailable(
                "faster-whisper not installed. pip install faster-whisper"
            ) from exc

        wav_path = _to_wav_for_whisper(path)
        try:
            duration, rms = self._wav_stats(wav_path)
        except wave.Error as exc:
            raise ProviderError(f"Invalid WAV after convert: {exc}") from exc
        if duration < 0.35:
            raise ProviderError(
                f"Audio too short after convert ({duration:.2f}s). "
                "Record 2–5 seconds of clear speech, then Stop."
            )
        # Near-silent clips make Whisper hallucinate words like "You" / "Thank you."
        if rms < 0.008:
            raise ProviderError(
                f"Recording is nearly silent (rms={rms:.4f}, {duration:.1f}s). "
                "In the browser mic picker, choose the physical USB/headset mic "
                "(not Stereo Mix / cable output), speak louder, then re-Record."
            )

        try:
            text, lang = self._transcribe_wav(wav_path, vad_filter=False)
            if not text:
                text, lang = self._transcribe_wav(wav_path, vad_filter=True)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Whisper transcribe failed: {exc}") from exc

        words = [w for w in (text or "").split() if w]
        if not text:
            raise ProviderError(
                f"STT produced empty transcript ({duration:.1f}s, rms={rms:.4f}). "
                "Speak louder/longer; check mic input device. "
                f"Audio preserved as {audio_id}"
            )
        if duration >= 2.0 and len(words) <= 2:
            raise ProviderError(
                f"STT draft too short for a {duration:.1f}s clip ({text!r}, rms={rms:.4f}). "
                "Likely wrong/silent mic input or tiny-model hallucination. "
                "Re-Record with the correct mic selected; use MEMORYBOX_WHISPER_MODEL=base. "
                f"Audio preserved as {audio_id}"
            )
        return TranscriptDraft(
            audio_id=audio_id,
            audio_uri=path.resolve().as_uri(),
            text=text,
            provider_key=self.provider_key,
            language=lang,
            status="draft",
            duration_sec=round(duration, 2),
            rms=round(rms, 4),
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


def smoke_transcribe_file(path: Path) -> dict:
    """CLI helper — opaque status only (includes transcript length, not body by default)."""
    stt = FasterWhisperCaptureStt()
    data = path.read_bytes()
    draft = stt.preserve_and_transcribe(data, filename=path.name)
    return {
        "ok": True,
        "provider": stt.provider_key,
        "health": stt.health().__dict__,
        "audio_id": draft.audio_id,
        "text_len": len(draft.text or ""),
        "text_preview": (draft.text or "")[:120],
        "language": draft.language,
    }
