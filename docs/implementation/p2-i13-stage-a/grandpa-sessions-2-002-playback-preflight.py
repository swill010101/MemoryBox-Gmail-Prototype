"""Read-only playback preflight for grandpa sessions 2 002; no media or database writes."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

VID = "vid-34df63e61b949890"
SHA = "61505855a1220985482c415238bd4622278bf4eff053687dffad5e02a1b77a32"
SIZE = 361851720
DURATION = 319.8195
SOURCE = Path(r"P:\Photos\Home Videos\2011-03-21 grandpa sessions 2\grandpa sessions 2 002.MP4")
ROOT = Path(r"C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def proxy_path(root: Path, vid: str) -> Path:
    return root / "browser_proxies" / (hashlib.sha256(vid.encode()).hexdigest()[:24] + ".mp4")


def main() -> None:
    if os.environ.get("MEMORYBOX_RECOGNITION_DRAIN") != "0" or os.environ.get("MEMORYBOX_SPEECH_DRAIN") != "0" or os.environ.get("MEMORYBOX_I13_ADMISSION_ID"):
        raise RuntimeError("Drains must be 0 and admission unset")
    if not SOURCE.is_file():
        raise RuntimeError("Original is unavailable")
    if SOURCE.stat().st_size != SIZE or digest(SOURCE) != SHA:
        raise RuntimeError("Original does not match the 22-source manifest")
    root = ROOT.resolve(strict=True)
    dest = proxy_path(root, VID)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe missing")
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(SOURCE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    video = [row for row in streams if row.get("codec_type") == "video"]
    audio = [row for row in streams if row.get("codec_type") == "audio"]
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "check_only",
                "source_id": VID,
                "source": str(SOURCE),
                "original": {"bytes": SIZE, "sha256": SHA, "duration_sec": DURATION},
                "streams": {
                    "video_streams": len(video),
                    "audio_streams": len(audio),
                    "video_codec": video[0].get("codec_name") if video else None,
                    "pixel_format": video[0].get("pix_fmt") if video else None,
                    "duration_sec": float(data.get("format", {}).get("duration", "nan")),
                    "audio_codecs": [row.get("codec_name") for row in audio],
                },
                "destination": str(dest),
                "destination_exists": dest.exists(),
                "ui_message_if_missing": "Playable copy unavailable. This video cannot play here yet. The original is preserved.",
                "private_media_processed": False,
                "database_writes": False,
                "next": "Stop. Review this report before any separate one-source staging proposal.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": str(exc), "action": "Stop; no proxy was created."}))
        raise SystemExit(2) from exc
