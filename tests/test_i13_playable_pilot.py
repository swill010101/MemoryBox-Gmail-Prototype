"""Offline pilot guard tests. Synthetic bytes only; never invoke media tools."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pilot", ROOT / "docs/implementation/p2-i13-stage-a/playable-copy-pilot.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def metadata(output=False):
    return {"format":{"duration":"1105.104", "start_time":"0"}, "streams":[
        {"codec_type":"video", "codec_name":"h264" if output else "mpeg4", "width":1280,
         "height":720,"pix_fmt":"yuv420p", "nb_frames":"33120", "duration":"1105.104","start_time":"0"},
        {"codec_type":"audio", "codec_name":"aac", "sample_rate":"24000", "channels":1,
         "duration":"1105.066667", "start_time":"0"}]}


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="i13-pilot-test-")
        self.root = Path(self.tmp.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.addCleanup(self.tmp.cleanup)

    def test_known_source_and_output_metadata(self):
        pilot.validate_streams(metadata())
        pilot.validate_streams(metadata(True), output=True)

    def test_truncated_or_changed_streams_rejected(self):
        for change in ("duration", "frames", "codec", "rotation", "audio", "start"):
            data = metadata(True)
            if change == "duration": data["format"]["duration"]="2"
            if change == "frames": data["streams"][0]["nb_frames"]="20"
            if change == "codec": data["streams"][0]["codec_name"]="mpeg4"
            if change == "rotation": data["streams"][0]["tags"]={"rotate":"90"}
            if change == "audio": data["streams"][1]["channels"]=2
            if change == "start": data["streams"][0]["start_time"]="10"
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                pilot.validate_streams(data, output=True)

    def test_no_overwrite_or_trimming_in_command(self):
        args = pilot.encode_args("synthetic-ffmpeg", Path("source.mp4"), Path("staged.mp4"))
        self.assertIn("-n", args)
        for forbidden in ("-y", "-ss", "-t", "-to"):
            self.assertNotIn(forbidden, args)
        self.assertEqual(args[args.index("-c:a")+1], "copy")
        self.assertEqual(args[args.index("-fs")+1], str(pilot.MAX_BYTES))

    def test_source_hash_mismatch_rejected(self):
        source=self.root/"source";source.write_bytes(b"synthetic")
        with patch.object(pilot,"SOURCE_SIZE",len(b"synthetic")), self.assertRaises(RuntimeError):
            pilot.source_check(source)

    def test_destination_escape_rejected(self):
        with self.assertRaises(RuntimeError):
            pilot.contained(self.root,"../outside.mp4")

    def test_existing_destination_is_preserved(self):
        source=self.root/"source";source.write_bytes(b"source")
        staged=self.root/"staged";staged.write_bytes(b"s"*2048)
        dest=self.root/"destination";dest.write_bytes(b"existing")
        report={"output_sha256":pilot.sha256(staged)}
        with self.assertRaises(FileExistsError):
            pilot.publish_copy(staged,dest,report,source)
        self.assertEqual(dest.read_bytes(),b"existing")
        self.assertEqual(staged.read_bytes(),b"s"*2048)

    def test_publish_preserves_staged_copy(self):
        source=self.root/"source";source.write_bytes(b"source")
        staged=self.root/"staged";staged.write_bytes(b"s"*2048)
        dest=self.root/"destination"
        pilot.publish_copy(staged,dest,{"output_sha256":pilot.sha256(staged)},source)
        self.assertEqual(dest.read_bytes(),staged.read_bytes())
        self.assertTrue(staged.exists())

    def test_changed_staged_output_not_published(self):
        source=self.root/"source";source.write_bytes(b"source")
        staged=self.root/"staged";staged.write_bytes(b"s"*2048)
        dest=self.root/"destination"
        with self.assertRaises(RuntimeError):
            pilot.publish_copy(staged,dest,{"output_sha256":"wrong"},source)
        self.assertFalse(dest.exists())

    def test_lock_checks(self):
        good={"MEMORYBOX_RECOGNITION_DRAIN":"0","MEMORYBOX_SPEECH_DRAIN":"0"}
        pilot.require_locks(good)
        for env in ({}, {**good,"MEMORYBOX_SPEECH_DRAIN":"1"}, {**good,"MEMORYBOX_I13_ADMISSION_ID":"active"}):
            with self.assertRaises(RuntimeError):pilot.require_locks(env)

    def test_approval_required_before_execute(self):
        with patch.object(pilot,"require_locks"), patch.object(pilot,"source_check") as check:
            with self.assertRaisesRegex(RuntimeError,"approval"):
                pilot.main(["--execute"])
            check.assert_not_called()

    def test_publication_requires_visual_review(self):
        with patch.object(pilot,"require_locks"), patch.object(pilot,"source_check") as check:
            with self.assertRaisesRegex(RuntimeError,"review"):
                pilot.main(["--publish","--approval-ref","synthetic"])
            check.assert_not_called()

    def test_expired_budget_never_starts_process(self):
        with patch.object(pilot.subprocess,"Popen") as popen:
            with self.assertRaises(RuntimeError):
                pilot.run_limited(["not-run"],self.root/"log",time.monotonic()-1)
            popen.assert_not_called()
        self.assertFalse((self.root/"log").exists())

    def test_packet_timestamps(self):
        self.assertEqual(pilot.validate_packet_times("0,-0.067\n1,0\n0,-0.033\n1,0.04"),{0:2,1:2})
        for invalid in ("0,0\n0,-1\n1,0", "0,nan\n1,0", "0,0", "2,0\n1,0"):
            with self.assertRaises(RuntimeError):pilot.validate_packet_times(invalid)

    def test_check_only_creates_no_files_or_process(self):
        fake_tools={k:{"path":"synthetic", "version":"synthetic"} for k in ("ffmpeg","ffprobe")}
        with patch.object(pilot,"ROOT",self.root), patch.object(pilot,"require_locks"), patch.object(pilot,"source_check",return_value={"sha256":pilot.SOURCE_HASH}), patch.object(pilot,"tools",return_value=fake_tools), patch.object(pilot,"probe",return_value=metadata()), patch.object(pilot.shutil,"disk_usage",return_value=type("Usage",(),{"free":pilot.MIN_FREE})()), patch.object(pilot.subprocess,"Popen") as process, redirect_stdout(io.StringIO()) as output:
            pilot.main([])
            self.assertEqual(json.loads(output.getvalue())["mode"],"check_only")
            process.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=="__main__":unittest.main()
