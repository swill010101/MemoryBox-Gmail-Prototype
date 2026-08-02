"""Learn-from-annotations: speaker ID from enrolled voice spans.

Extracts enrolled clips with ffmpeg, embeds with SpeechBrain ECAPA (if installed),
scores other transcript segments, writes AI person_voice annotations.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np

VOICE_SIM_THRESHOLD = 0.55  # cosine on ECAPA embeddings (stricter than faces)
MIN_SEG_SEC = 1.25
MAX_SEGS_PER_VIDEO = 120


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _which_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def _extract_wav(ffmpeg: str, video: Path, start: float, end: float, dest: Path) -> bool:
    dur = max(0.4, float(end) - float(start))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{max(0.0, start):.3f}",
        "-t",
        f"{dur:.3f}",
        "-i",
        str(video),
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
    return dest.is_file() and dest.stat().st_size > 1000


def _load_encoder(working_dir: Path):
    try:
        from speechbrain.inference.speaker import EncoderClassifier  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "speechbrain not installed — run: pip install speechbrain torch torchaudio"
        ) from e
    savedir = working_dir / "models" / "spkrec-ecapa-voxceleb"
    savedir.mkdir(parents=True, exist_ok=True)
    return EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(savedir),
        run_opts={"device": "cpu"},
    )


def _embed_file(encoder, wav_path: Path) -> np.ndarray | None:
    try:
        import torchaudio  # type: ignore

        signal, fs = torchaudio.load(str(wav_path))
        if fs != 16000:
            signal = torchaudio.functional.resample(signal, fs, 16000)
        if signal.shape[0] > 1:
            signal = signal.mean(dim=0, keepdim=True)
        emb = encoder.encode_batch(signal)
        vec = emb.squeeze().detach().cpu().numpy().astype(np.float32).ravel()
        n = np.linalg.norm(vec)
        return vec / n if n > 1e-9 else vec
    except Exception:  # noqa: BLE001
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _enrollments(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT vs.id, vs.person_id, vs.video_id, vs.start_sec, vs.end_sec, vs.path,
               pe.name AS person_name, v.path AS video_path
        FROM voice_samples vs
        JOIN people pe ON pe.id = vs.person_id
        LEFT JOIN videos v ON v.id = vs.video_id
        ORDER BY vs.person_id, vs.id
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "sample_id": r["id"],
                "person_id": int(r["person_id"]),
                "person_name": r["person_name"],
                "video_id": r["video_id"],
                "start_sec": float(r["start_sec"] or 0),
                "end_sec": float(r["end_sec"] or (r["start_sec"] or 0) + 2),
                "marker_path": r["path"],
                "video_path": r["video_path"],
            }
        )
    # Also pull person_voice annotations not yet in voice_samples
    for r in conn.execute(
        """
        SELECT a.id, a.person_id, a.video_id, a.start_sec, a.end_sec, pe.name, v.path
        FROM annotations a
        JOIN people pe ON pe.id = a.person_id
        JOIN videos v ON v.id = a.video_id
        WHERE a.kind='person_voice' AND a.revoked=0 AND a.actor_key IN ('owner','user')
          AND a.person_id IS NOT NULL
        """
    ):
        out.append(
            {
                "sample_id": f"ann-{r['id']}",
                "person_id": int(r["person_id"]),
                "person_name": r["name"],
                "video_id": int(r["video_id"]),
                "start_sec": float(r["start_sec"]),
                "end_sec": float(r["end_sec"]),
                "marker_path": None,
                "video_path": r["path"],
            }
        )
    return out


def recognize_voices(
    conn: sqlite3.Connection,
    *,
    working_dir: Path,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    def prog(pct: float, msg: str) -> None:
        if progress:
            progress(pct, msg)

    ffmpeg = _which_ffmpeg()
    if not ffmpeg:
        return "ffmpeg not found — install ffmpeg or pip install imageio-ffmpeg"

    enrolls = _enrollments(conn)
    if not enrolls:
        return "No voice enrollments — highlight transcript words and Enroll voice span first"

    prog(5, "Loading speaker model (SpeechBrain ECAPA)")
    try:
        encoder = _load_encoder(working_dir)
    except RuntimeError as e:
        return str(e)

    wav_root = working_dir / "exemplars" / "voice" / "_clips"
    wav_root.mkdir(parents=True, exist_ok=True)

    prog(15, "Embedding enrolled voice spans")
    centroids: dict[int, np.ndarray] = {}
    by_person: dict[int, list[np.ndarray]] = {}
    for e in enrolls:
        vpath = Path(e["video_path"] or "")
        if not vpath.is_file():
            continue
        dest = wav_root / f"enroll_{e['person_id']}_{e['video_id']}_{int(e['start_sec'])}.wav"
        if not dest.is_file():
            if not _extract_wav(ffmpeg, vpath, e["start_sec"], e["end_sec"], dest):
                continue
        emb = _embed_file(encoder, dest)
        if emb is None:
            continue
        by_person.setdefault(int(e["person_id"]), []).append(emb)

    for pid, embs in by_person.items():
        mat = np.stack(embs, axis=0)
        c = mat.mean(axis=0)
        n = np.linalg.norm(c)
        centroids[pid] = c / n if n > 1e-9 else c

    if not centroids:
        return "Could not embed any enrolled voice spans — check ffmpeg/audio tracks"

    # Candidate segments: transcript lines long enough, not already owner-labeled nearby
    if "transcript_segments" not in {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }:
        return "No transcript_segments table — run process_videos Whisper first"

    segs = conn.execute(
        """
        SELECT s.id, s.video_id, s.start_sec, s.end_sec, s.text, v.path AS video_path, v.filename
        FROM transcript_segments s
        JOIN videos v ON v.id = s.video_id
        WHERE (s.end_sec - s.start_sec) >= ?
        ORDER BY s.video_id, s.start_sec
        """,
        (MIN_SEG_SEC,),
    ).fetchall()

    owner_spans = conn.execute(
        """
        SELECT video_id, person_id, start_sec, end_sec FROM annotations
        WHERE kind='person_voice' AND revoked=0 AND actor_key IN ('owner','user')
        """
    ).fetchall()

    def covered(video_id: int, start: float, end: float) -> bool:
        for o in owner_spans:
            if int(o["video_id"]) != video_id:
                continue
            if start < float(o["end_sec"]) + 0.3 and float(o["start_sec"]) < end + 0.3:
                return True
        return False

    prog(30, f"Scoring {len(segs)} transcript segments")
    written = 0
    per_video_count: dict[int, int] = {}

    with tempfile.TemporaryDirectory(prefix="hvrt_voice_") as tmp:
        tmp_path = Path(tmp)
        for i, s in enumerate(segs):
            if i % 10 == 0:
                prog(30 + 65 * (i / max(len(segs), 1)), f"Voice match {i}/{len(segs)}")
            vid = int(s["video_id"])
            if per_video_count.get(vid, 0) >= MAX_SEGS_PER_VIDEO:
                continue
            start = float(s["start_sec"])
            end = float(s["end_sec"])
            if covered(vid, start, end):
                continue
            vpath = Path(s["video_path"])
            if not vpath.is_file():
                continue
            clip = tmp_path / f"seg_{s['id']}.wav"
            if not _extract_wav(ffmpeg, vpath, start, end, clip):
                continue
            emb = _embed_file(encoder, clip)
            if emb is None:
                continue
            best_pid = None
            best = -1.0
            for pid, c in centroids.items():
                score = _cosine(emb, c)
                if score > best:
                    best = score
                    best_pid = pid
            if best_pid is None or best < VOICE_SIM_THRESHOLD:
                continue

            # Skip duplicate AI annotation for same span/person
            dup = conn.execute(
                """
                SELECT id FROM annotations
                WHERE video_id=? AND kind='person_voice' AND person_id=? AND revoked=0
                  AND ABS(start_sec-?) < 0.4 AND ABS(end_sec-?) < 0.4
                LIMIT 1
                """,
                (vid, best_pid, start, end),
            ).fetchone()
            if dup:
                continue

            name = conn.execute(
                "SELECT name FROM people WHERE id=?", (best_pid,)
            ).fetchone()
            label = name["name"] if name else str(best_pid)
            conn.execute(
                """
                INSERT INTO annotations (
                    video_id, kind, start_sec, end_sec, label_text, person_id,
                    payload_json, actor_key, confidence, provenance_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    vid,
                    "person_voice",
                    start,
                    end,
                    label,
                    best_pid,
                    json.dumps(
                        {
                            "voice_match": True,
                            "transcript_segment_id": s["id"],
                            "text": s["text"],
                            "cosine": best,
                        }
                    ),
                    "ai",
                    float(best),
                    json.dumps({"engine": "speechbrain-ecapa", "threshold": VOICE_SIM_THRESHOLD}),
                ),
            )
            written += 1
            per_video_count[vid] = per_video_count.get(vid, 0) + 1
            if written % 5 == 0:
                conn.commit()

        conn.commit()

    from hvrt.rescoring import rebuild_effective_evidence

    rebuild_effective_evidence(conn)
    conn.commit()
    prog(100, "Voice recognition done")
    return (
        f"Voice: {len(centroids)} enrolled speaker(s) · "
        f"{written} AI speaker labels on transcript spans "
        f"(threshold {VOICE_SIM_THRESHOLD})"
    )
