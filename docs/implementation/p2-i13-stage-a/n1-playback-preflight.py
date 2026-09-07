"""Read-only preflight for one unavailable N1 browser-playback source.

Imports no MemoryBox modules and never creates derivatives, runs an encoder,
or changes the database. Any future copy needs a separate, source-specific
staging approval after this report is reviewed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

VIDEO_ID = "vid-c015e0fe07414fcc"
SOURCE_HASH = "09e6dfb523724448888586183d9e265f3181f241ab37fa9d6d800ac1b6cf92b3"
SOURCE_SIZE = 6_249_411
DURATION = 305.4066666666667
SOURCE = Path(r"P:\Photos\Home Videos\second meals on wheels.mp4")
DERIVED_ROOT = Path(r"C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived")
MIN_FREE = 10 * 1024**3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def proxy_relative_path(video_id: str) -> Path:
    key = hashlib.sha256(video_id.encode("utf-8")).hexdigest()[:24]
    return Path("browser_proxies") / f"{key}.mp4"


def require_locks(env: dict[str, str]) -> None:
    for key in ("MEMORYBOX_RECOGNITION_DRAIN", "MEMORYBOX_SPEECH_DRAIN"):
        if env.get(key) != "0":
            raise RuntimeError("Both drain settings must explicitly be 0 in this shell")
    if env.get("MEMORYBOX_I13_ADMISSION_ID"):
        raise RuntimeError("Admission must be unset")


def source_check(source: Path) -> dict[str, int | str]:
    stat = source.stat()
    actual_hash = sha256(source)
    if stat.st_size != SOURCE_SIZE or actual_hash != SOURCE_HASH:
        raise RuntimeError("Source does not match the approved 22-source manifest")
    return {"bytes": stat.st_size, "sha256": actual_hash, "mtime_ns": stat.st_mtime_ns}


def read_command(args: list[str], timeout: int = 60) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Read-only tool check failed: " + Path(args[0]).name)
    return result.stdout


def tool(name: str) -> dict[str, str]:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(name + " is missing")
    version = read_command([executable, "-version"], 15).splitlines()[0]
    return {"path": executable, "version": version}


def probe(ffprobe: str, source: Path) -> dict:
    return json.loads(read_command([ffprobe, "-v", "error", "-show_streams", "-show_format",
                                    "-of", "json", str(source)]))


def summarize_streams(metadata: dict) -> dict:
    streams = metadata.get("streams") or []
    video = [row for row in streams if row.get("codec_type") == "video"]
    audio = [row for row in streams if row.get("codec_type") == "audio"]
    duration = float((metadata.get("format") or {}).get("duration", "nan"))
    if len(video) != 1 or not math.isfinite(duration) or abs(duration - DURATION) > 0.5:
        raise RuntimeError("Unexpected source layout or duration requires review")
    first = video[0]
    rotations = [first.get("tags", {}).get("rotate", 0)]
    rotations += [row.get("rotation", 0) for row in first.get("side_data_list", [])]
    return {
        "video_streams": len(video), "audio_streams": len(audio),
        "video_codec": first.get("codec_name"), "width": first.get("width"),
        "height": first.get("height"), "pixel_format": first.get("pix_fmt"),
        "rotation": rotations, "duration_sec": duration,
        "audio_codecs": [row.get("codec_name") for row in audio],
    }


def main() -> None:
    require_locks(dict(os.environ))
    root = DERIVED_ROOT.resolve(strict=True)
    if os.path.normcase(str(root)) != os.path.normcase(str(DERIVED_ROOT.absolute())):
        raise RuntimeError("Redirected derivative root requires review")
    destination = root / proxy_relative_path(VIDEO_ID)
    if not destination.resolve().is_relative_to(root):
        raise RuntimeError("Proxy destination is outside derivative root")
    if destination.exists():
        raise RuntimeError("Existing proxy must be preserved and investigated; no replacement is allowed")
    ffprobe = tool("ffprobe")
    ffmpeg = tool("ffmpeg")
    original = source_check(SOURCE)
    metadata = probe(ffprobe["path"], SOURCE)
    summary = summarize_streams(metadata)
    free = shutil.disk_usage(root).free
    if free < MIN_FREE:
        raise RuntimeError("Less than 10 GiB free on the derivative volume")
    print(json.dumps({
        "ok": True, "mode": "check_only", "source_id": VIDEO_ID,
        "source": str(SOURCE), "original": original, "streams": summary,
        "destination": str(destination), "destination_exists": False,
        "tools": {"ffmpeg": ffmpeg, "ffprobe": ffprobe}, "free_bytes": free,
        "private_media_processed": False, "database_writes": False,
        "next": "Stop. Review this report; a separately approved one-source staging plan is required before any copy is created.",
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": str(exc),
                          "action": "Stop. No proxy was created and no automatic retry is permitted."}))
        raise SystemExit(2)