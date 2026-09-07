"""Offline N1 normalization-pilot guards. Synthetic metadata only."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("n1pilot", ROOT / "docs/implementation/p2-i13-stage-a/n1-playable-copy-pilot.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def metadata(output=False):
    return {"format": {"duration": str(pilot.DURATION), "start_time": "0"}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240,
         "pix_fmt": "yuv420p" if output else "yuvj420p", "duration": str(pilot.DURATION), "start_time": "0"},
        {"codec_type": "audio", "codec_name": "aac", "sample_rate": "24000", "channels": 1,
         "duration": str(pilot.DURATION), "start_time": "0"},
    ]}


class N1PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="i13-n1-pilot-")
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def test_known_source_and_normalized_output_metadata(self):
        pilot.validate_streams(metadata())
        pilot.validate_streams(metadata(True), output=True)

    def test_source_full_range_and_output_video_format_are_enforced(self):
        for source_output, change in ((False, "source-pix"), (True, "output-pix"), (False, "dimensions"), (True, "duration"), (False, "audio")):
            data = metadata(source_output)
            if change == "source-pix": data["streams"][0]["pix_fmt"] = "yuv420p"
            if change == "output-pix": data["streams"][0]["pix_fmt"] = "yuvj420p"
            if change == "dimensions": data["streams"][0]["width"] = 640
            if change == "duration": data["format"]["duration"] = "2"
            if change == "audio": data["streams"][1]["codec_name"] = "mp3"
            with self.subTest(change=change):
                with self.assertRaises(RuntimeError):
                    pilot.validate_streams(data, output=source_output)

    def test_no_overwrite_or_trim_and_audio_is_copied(self):
        args = pilot.encode_args("synthetic-ffmpeg", Path("source.mp4"), Path("staged.mp4"))
        self.assertIn("-n", args)
        self.assertEqual(args[args.index("-c:a") + 1], "copy")
        for forbidden in ("-y", "-ss", "-t", "-to"):
            self.assertNotIn(forbidden, args)

    def test_destination_escape_is_rejected(self):
        with self.assertRaises(RuntimeError):
            pilot.contained(self.root, "../outside.mp4")

    def test_execution_and_publication_need_distinct_approvals(self):
        with patch.object(pilot, "require_locks"), patch.object(pilot, "source_check") as source_check:
            with self.assertRaisesRegex(RuntimeError, "approval"):
                pilot.main(["--execute"])
            with self.assertRaisesRegex(RuntimeError, "review"):
                pilot.main(["--publish", "--approval-ref", "synthetic"])
            source_check.assert_not_called()

    def test_check_only_creates_no_files_or_process(self):
        tools = {name: {"path": "synthetic", "version": "synthetic"} for name in ("ffmpeg", "ffprobe")}
        with patch.object(pilot, "ROOT", self.root), patch.object(pilot, "require_locks"), patch.object(pilot, "source_check", return_value={"sha256": pilot.SOURCE_HASH}), patch.object(pilot, "tools", return_value=tools), patch.object(pilot, "probe", return_value=metadata()), patch.object(pilot.shutil, "disk_usage", return_value=type("Usage", (), {"free": pilot.MIN_FREE})()), redirect_stdout(io.StringIO()) as output:
            pilot.main([])
            self.assertEqual(json.loads(output.getvalue())["mode"], "check_only")
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()