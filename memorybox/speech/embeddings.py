"""Voice embeddings from original video audio (HVRT ECAPA path). Harness may inject vectors."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from memorybox.recognition.embeddings import cosine
from memorybox.speech.constants import VOICE_MODEL


def embed_injected(vec: Sequence[float] | None) -> list[float] | None:
    if not vec:
        return None
    return [float(x) for x in vec]


def extract_wav(video_path: str, t_start: float, t_end: float, dest: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg  # type: ignore

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return False
    dur = max(0.4, float(t_end) - float(t_start))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{max(0.0, float(t_start)):.3f}",
        "-t",
        f"{dur:.3f}",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(dest),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return dest.is_file() and dest.stat().st_size > 200


def embed_wav_ecapa(wav_path: Path) -> list[float] | None:
    try:
        from speechbrain.inference.speaker import EncoderClassifier  # type: ignore
        import torchaudio  # type: ignore
        import numpy as np
    except ImportError:
        return None
    try:
        savedir = Path(tempfile.gettempdir()) / "mb-spkrec-ecapa-voxceleb"
        savedir.mkdir(parents=True, exist_ok=True)
        encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(savedir),
            run_opts={"device": "cpu"},
        )
        signal, fs = torchaudio.load(str(wav_path))
        if fs != 16000:
            signal = torchaudio.functional.resample(signal, fs, 16000)
        if signal.shape[0] > 1:
            signal = signal.mean(dim=0, keepdim=True)
        emb = encoder.encode_batch(signal)
        vec = emb.squeeze().detach().cpu().numpy().astype("float32").ravel()
        n = float(np.linalg.norm(vec))
        if n > 1e-9:
            vec = vec / n
        return [float(x) for x in vec]
    except Exception:
        return None


def embed_video_span(
    video_path: str | None,
    t_start: float,
    t_end: float,
    *,
    injected: Sequence[float] | None = None,
) -> tuple[list[float] | None, str]:
    if injected:
        return list(injected), "harness_inject"
    if not video_path:
        return None, "no_source_audio"
    with tempfile.TemporaryDirectory(prefix="mb-i9-voice-") as td:
        wav = Path(td) / "span.wav"
        if not extract_wav(video_path, t_start, t_end, wav):
            return None, "ffmpeg_extract_failed"
        vec = embed_wav_ecapa(wav)
        if vec:
            return vec, VOICE_MODEL
    return None, "ecapa_unavailable"


def best_voice_score(probe: Sequence[float], exemplars: list[dict[str, Any]]) -> float:
    best = -1.0
    for ex in exemplars:
        s = cosine(probe, ex.get("embedding") or [])
        if s > best:
            best = s
    return float(best)
