"""Synthetic guard tests for the N1 check-only playback preflight."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("n1", ROOT / "docs/implementation/p2-i13-stage-a/n1-playback-preflight.py")
n1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n1)


class N1PreflightTests(unittest.TestCase):
    def test_proxy_key_matches_worker_algorithm(self):
        self.assertEqual(str(n1.proxy_relative_path(n1.VIDEO_ID)), "browser_proxies\\9eca7338d7a661aed03b02b9.mp4")

    def test_locks_are_required(self):
        good = {"MEMORYBOX_RECOGNITION_DRAIN": "0", "MEMORYBOX_SPEECH_DRAIN": "0"}
        n1.require_locks(good)
        for env in ({}, {**good, "MEMORYBOX_SPEECH_DRAIN": "1"}, {**good, "MEMORYBOX_I13_ADMISSION_ID": "active"}):
            with self.subTest(env=env):
                with self.assertRaises(RuntimeError):
                    n1.require_locks(env)

    def test_layout_requires_one_video_and_expected_duration(self):
        valid = {"format": {"duration": str(n1.DURATION)}, "streams": [
            {"codec_type": "video", "codec_name": "hevc", "width": 1920, "height": 1080, "pix_fmt": "yuv420p"},
            {"codec_type": "audio", "codec_name": "aac"},
        ]}
        summary = n1.summarize_streams(valid)
        self.assertEqual(summary["video_codec"], "hevc")
        for invalid in ({"format": {"duration": "1"}, "streams": valid["streams"]}, {"format": {"duration": str(n1.DURATION)}, "streams": []}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RuntimeError):
                    n1.summarize_streams(invalid)

    def test_source_hash_mismatch_rejected_without_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic"
            source.write_bytes(b"synthetic")
            with patch.object(n1, "sha256", return_value="wrong"):
                with self.assertRaises(RuntimeError):
                    n1.source_check(source)


if __name__ == "__main__":
    unittest.main()