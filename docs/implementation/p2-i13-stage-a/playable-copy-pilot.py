"""Single pinned-source pilot. Default: read-only check. No MB imports.

Execute stages/validates only; publication requires a separate visual review.
No retry, overwrite, cleanup, recognition, transcription or database access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

VID = "vid-c57dbd21f993f6d1"
SOURCE_HASH = "26f3646b4adbda7573ff19c02da3b11bafceff4ac5cd7d967d5b0053a2e10705"
SOURCE_SIZE = 1251525801
DURATION = 1105.104
MAX_BYTES = 4 * 1024**3
MIN_FREE = 10 * 1024**3
WALL_SECONDS = 7200
SOURCE = Path(r"P:\Photos\Home Videos\20111105_1532.MP4")
ROOT = Path(r"C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived")
DEST_REL = "browser_proxies/edda398dc1204bb272364d87.mp4"
ATTEMPT_REL = "i13-playable-pilot-c57dbd21f993f6d1-v01"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def contained(root, relative):
    root = root.resolve(strict=True)
    path = root / relative
    # Reject links/junctions/redirection, including a dangling final symlink.
    current = root
    for part in Path(relative).parts:
        if part in {"..", "."}:
            raise RuntimeError("Invalid relative path")
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise RuntimeError("Redirected destination requires review")
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise RuntimeError("Destination is outside approved derivative root")
    return path


def require_locks(env):
    for key in ("MEMORYBOX_RECOGNITION_DRAIN", "MEMORYBOX_SPEECH_DRAIN"):
        if env.get(key) != "0":
            raise RuntimeError("Both drain settings must explicitly be 0 in this shell")
    if env.get("MEMORYBOX_I13_ADMISSION_ID"):
        raise RuntimeError("Admission must be unset")


def read_command(args, timeout=60):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Read-only tool check failed: " + Path(args[0]).name)
    return result.stdout


def tools():
    found = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if not executable:
            raise RuntimeError(name + " is missing")
        version = read_command([executable, "-version"], 15).splitlines()[0]
        if not version.startswith(name + " version ") or version.split()[2].split("-")[0] != "9.0":
            raise RuntimeError("Tool version differs from reviewed 9.0 preflight")
        found[name] = {"path": executable, "version": version}
    return found


def probe(executable, path):
    return json.loads(read_command([executable, "-v", "error", "-show_streams",
                                   "-show_format", "-of", "json", str(path)]))


def validate_streams(data, output=False):
    streams = data.get("streams", [])
    if len(streams) != 2:
        raise RuntimeError("Expected exactly one video and one audio stream")
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise RuntimeError("Unexpected stream layout")
    video, audio = videos[0], audios[0]
    expected = "h264" if output else "mpeg4"
    if (video.get("codec_name"), video.get("width"), video.get("height"), video.get("pix_fmt")) != (expected, 1280, 720, "yuv420p"):
        raise RuntimeError("Unexpected video format")
    if (audio.get("codec_name"), int(audio.get("sample_rate", 0)), audio.get("channels")) != ("aac", 24000, 1):
        raise RuntimeError("Unexpected audio format")
    if int(video.get("nb_frames", 0)) != 33120:
        raise RuntimeError("Unexpected frame count or truncated video")
    for row in (data.get("format", {}), video, audio):
        duration = float(row.get("duration", "nan"))
        start = float(row.get("start_time", "nan"))
        if not math.isfinite(duration) or abs(duration - DURATION) > 0.5:
            raise RuntimeError("Duration mismatch")
        if not math.isfinite(start) or abs(start) > 0.05:
            raise RuntimeError("Source-zero timeline mismatch")
    rotations = [video.get("tags", {}).get("rotate", 0)]
    rotations += [d.get("rotation", 0) for d in video.get("side_data_list", [])]
    if any(float(r) != 0 for r in rotations):
        raise RuntimeError("Unexpected rotation requires review")


def source_check(source):
    stat = source.stat()
    if stat.st_size != SOURCE_SIZE or sha256(source) != SOURCE_HASH:
        raise RuntimeError("Source does not match the accepted manifest")
    return {"sha256": SOURCE_HASH, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def encode_args(ffmpeg, source, staged):
    return [ffmpeg, "-hide_banner", "-nostdin", "-n", "-xerror", "-threads", "2",
            "-i", str(source), "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264", "-threads", "2", "-filter_threads", "1",
            "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", "-fs", str(MAX_BYTES), str(staged)]


def run_limited(args, log, deadline, output=None):
    if time.monotonic() >= deadline:
        raise RuntimeError("Pilot wall-time limit reached before tool start")
    with log.open("xb") as stream:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Pilot wall-time limit reached")
                if output and output.exists() and output.stat().st_size >= MAX_BYTES:
                    raise RuntimeError("Output size limit reached")
                time.sleep(0.25)
            if process.returncode:
                raise RuntimeError("Tool failed; preserve and review " + str(log))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    if output and (not output.is_file() or not 1000 < output.stat().st_size < MAX_BYTES):
        raise RuntimeError("Invalid or size-limited output; do not publish")


def validate_packet_times(csv):
    previous = {}
    counts = {}
    for line in csv.splitlines():
        fields = line.split(",")
        if len(fields) < 2:
            raise RuntimeError("Missing packet timestamps")
        index, stamp = int(fields[0]), float(fields[1])
        if index not in {0, 1} or not math.isfinite(stamp):
            raise RuntimeError("Unexpected packet stream/timestamp")
        if index in previous and stamp <= previous[index]:
            raise RuntimeError("Nonmonotonic decode timestamps")
        previous[index] = stamp
        counts[index] = counts.get(index, 0) + 1
    if set(counts) != {0, 1}:
        raise RuntimeError("Missing output packets")
    return counts


def write_new(path, data):
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def publish_copy(staged, dest, report, source):
    if sha256(staged) != report["output_sha256"]:
        raise RuntimeError("Staged output changed after validation")
    if not 1000 < staged.stat().st_size < MAX_BYTES:
        raise RuntimeError("Invalid staged size")
    if staged.stat().st_mtime_ns < source.stat().st_mtime_ns:
        raise RuntimeError("Copy would fail the existing ready check")
    # Same-volume hard link is atomic and refuses an existing destination.
    # Preserve staged bytes; never fall back to overwrite/copy/rename.
    os.link(staged, dest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--publish", action="store_true")
    parser.add_argument("--approval-ref")
    parser.add_argument("--expected-release")
    parser.add_argument("--visual-review-ref")
    args = parser.parse_args(argv)
    if os.name != "nt":
        raise RuntimeError("This pinned pilot is for FlightSim Windows only")
    require_locks(os.environ)
    if (args.execute or args.publish) and not (args.approval_ref or "").strip():
        raise RuntimeError("Explicit execution/publication approval reference required")
    if args.publish and not (args.visual_review_ref or "").strip():
        raise RuntimeError("Beginning/middle/end visual and audio review reference required")
    if args.execute or args.publish:
        release = Path(__file__).resolve().parents[3]
        head = read_command(["git", "-C", str(release), "rev-parse", "HEAD"]).strip()
        dirty = read_command(["git", "-C", str(release), "status", "--porcelain"]).strip()
        if head != args.expected_release or dirty:
            raise RuntimeError("An exact, clean, reviewed helper release is required")
    root = ROOT.resolve(strict=True)
    if os.path.normcase(str(root)) != os.path.normcase(str(ROOT.absolute())):
        raise RuntimeError("Redirected derivative root requires review")
    dest = contained(root, DEST_REL)
    attempt = contained(root, ATTEMPT_REL)
    staged = contained(root, ATTEMPT_REL + "/staged.mp4")
    if dest.exists():
        raise RuntimeError("Proxy already exists; preserve it and stop")
    original = source_check(SOURCE)
    installed = tools()
    metadata = probe(installed["ffprobe"]["path"], SOURCE)
    validate_streams(metadata)
    free = shutil.disk_usage(root).free
    if free < MIN_FREE:
        raise RuntimeError("Less than 10 GiB free in the actual derivative volume")
    command = encode_args(installed["ffmpeg"]["path"], SOURCE, staged)
    check = {"mode":"check_only", "source":str(SOURCE), "source_id":VID,
             "original":original, "streams":metadata, "tools":installed,
             "destination":str(dest), "attempt_exists":attempt.exists(),
             "free_bytes":free, "proposed_encode_args":command,
             "helper_sha256":sha256(Path(__file__)),
             "limits":{"wall_seconds":WALL_SECONDS,"max_output_bytes":MAX_BYTES,"attempts":1}}
    if not args.execute and not args.publish:
        print(json.dumps(check, indent=2))
        return
    if args.publish:
        report = json.loads((attempt / "validated.json").read_text(encoding="utf-8"))
        if (report.get("source_id") != VID or report.get("source_sha256") != SOURCE_HASH
                or report.get("full_decode_passed") is not True or report.get("source_unchanged") is not True):
            raise RuntimeError("Validation report is for another source")
        if (attempt / "published.json").exists():
            raise RuntimeError("Publication was already recorded; stop for review")
        validate_streams(probe(installed["ffprobe"]["path"], staged), output=True)
        if not dest.parent.exists():
            dest.parent.mkdir()  # No recursive path creation.
        dest = contained(root, DEST_REL)
        publish_copy(staged, dest, report, SOURCE)
        write_new(attempt / "published.json", {"destination":str(dest),
                  "approval_ref":args.approval_ref, "visual_review_ref":args.visual_review_ref,
                  "output_sha256":report["output_sha256"], "published_at":time.time()})
        print(json.dumps({"published":True,"source_id":VID,"destination":str(dest)}))
        return
    # Persistent reservation: reruns/concurrent invocations cannot start attempt two.
    attempt.mkdir(exist_ok=False)
    write_new(attempt / "attempt.json", {**check, "mode":"execute", "approval_ref":args.approval_ref,
                                        "started_at":time.time()})
    deadline = time.monotonic() + WALL_SECONDS
    run_limited(command, attempt / "encode.log", deadline, staged)
    output = probe(installed["ffprobe"]["path"], staged)
    validate_streams(output, output=True)
    decode = [installed["ffmpeg"]["path"], "-hide_banner", "-nostdin", "-v", "error",
              "-xerror", "-threads", "2", "-i", str(staged), "-map", "0:v:0",
              "-map", "0:a:0", "-threads", "2", "-f", "null", "-"]
    run_limited(decode, attempt / "decode.log", deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("Pilot wall-time limit reached")
    packet_args = [installed["ffprobe"]["path"], "-v", "error", "-show_packets",
                   "-show_entries", "packet=stream_index,dts_time", "-of", "csv=p=0", str(staged)]
    packet_counts = validate_packet_times(read_command(packet_args, min(60, remaining)))
    after = source_check(SOURCE)
    if after != original:
        raise RuntimeError("Original changed during the pilot")
    report = {"source_id":VID,"source_sha256":SOURCE_HASH,"output_sha256":sha256(staged),
              "output_bytes":staged.stat().st_size,"output_metadata":output,"decode_args":decode,
              "full_decode_passed":True,"packet_counts":packet_counts,"packet_probe_args":packet_args,"source_unchanged":True,"finished_at":time.time()}
    write_new(attempt / "validated.json", report)
    print(json.dumps({"validated":True,"published":False,"staged_path":str(staged),
          "report":str(attempt / "validated.json"),
          "next":"Stop. Review moving video and audio at beginning/middle/end before separate publication."},indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok":False,"error_type":type(exc).__name__,"message":str(exc),
                          "action":"Stop; preserve all existing and staged files. No automatic retry."}))
        raise SystemExit(2)
