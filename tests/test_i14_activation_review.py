"""Flags and bounded TXT packet formatting for the I14 activation-review tool."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memorybox.ops.i14_activation_review import (
    ActivationReviewError,
    FOCUS_OTHER,
    MAX_THREADS,
    NAMED_REFS,
    format_activation_thread,
    select_activation_threads,
    write_activation_packet,
)
from memorybox.ops.i14_prepared_text import HOTMAIL_DATE_FROM_TO_SUBJECT


class _Rows:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class _FakeSelectConn:
    def __init__(self, named: dict[str, str], glued: list[dict]) -> None:
        self.named = named
        self.glued = glued

    def execute(self, sql: str, params: tuple | None = None) -> _Rows:
        if "m.evidence_ref = %s" in sql:
            ref = str(params[1])
            return _Rows([{"display_id": self.named[ref], "evidence_ref": ref}])
        return _Rows(self.glued)


class Flags(unittest.TestCase):
    def test_refuses_without_private_emit(self) -> None:
        os.environ.pop("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", None)
        os.environ.pop("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", None)
        os.environ.pop("MEMORYBOX_I14_VOICE_DELTA_ALLOW_FLIGHTSIM", None)
        from memorybox.ops.i14_activation_review import _allow

        with self.assertRaises(ActivationReviewError) as ctx:
            _allow()
        self.assertEqual(str(ctx.exception), "private_review_emit_not_authorized")


class Bounds(unittest.TestCase):
    def test_named_refs_and_thread_cap(self) -> None:
        self.assertEqual(NAMED_REFS, ("T-2312-M-02", "T-2345-M-02"))
        self.assertEqual(MAX_THREADS, 12)
        self.assertEqual(FOCUS_OTHER, 10)

    def test_format_is_txt_not_html(self) -> None:
        text = format_activation_thread(
            {
                "preview_thread_id": "T-2312",
                "threading_confidence": "high",
                "identity_confidence": "resolved",
                "duplicate_omitted": 0,
                "messages": [
                    {
                        "ordinal": 2,
                        "evidence_ref": "T-2312-M-02",
                        "from_parties": [{"display": "Peggy", "status": "authenticated"}],
                        "to_parties": [{"display": "Tom", "status": "authenticated"}],
                        "cc_parties": [],
                        "timestamp": "2008-01-01T12:00:00+00:00",
                        "subject": "hello",
                        "voice_reason": "VOICE ACCEPTED | glued Hotmail",
                        "cleaned_body": "LOL Pegs",
                        "focus": True,
                    }
                ],
            }
        )
        self.assertIn("BEGIN THREAD  T-2312", text)
        self.assertIn("T-2312-M-02", text)
        self.assertIn("Cleaned authored text:", text)
        self.assertIn("LOL Pegs", text)
        self.assertIn("originals/T-2312-M-02.txt", text)
        self.assertNotIn("<html", text.lower())
        self.assertNotIn("<div", text.lower())

    def test_selects_named_plus_other_glued_threads(self) -> None:
        glued_body = "Date: Tue, 1 Jan 2008 12:00:00 +0000 From: x To: y Subject: z"
        self.assertTrue(HOTMAIL_DATE_FROM_TO_SUBJECT.search(glued_body))
        named = {"T-2312-M-02": "T-2312", "T-2345-M-02": "T-2345"}
        glued = []
        for i in range(12):
            tid = f"T-{3000 + i}"
            glued.append(
                {
                    "display_id": tid,
                    "evidence_ref": f"{tid}-M-01",
                    "ordinal": 1,
                    "payload_json": {"body_text": glued_body},
                }
            )
        glued.append(
            {
                "display_id": "T-2312",
                "evidence_ref": "T-2312-M-02",
                "ordinal": 2,
                "payload_json": {"body_text": glued_body},
            }
        )
        choice = select_activation_threads(_FakeSelectConn(named, glued), "gid")
        self.assertEqual(choice["selected"][:2], ["T-2312", "T-2345"])
        self.assertLessEqual(len(choice["selected"]), 12)
        self.assertEqual(len(choice["selected"]), 12)
        self.assertNotIn("T-2312-M-02", choice["other_glued_voice_refs"])
        self.assertEqual(choice["other_glued_voice_count_total"], 12)
        self.assertEqual(len(choice["other_glued_voice_refs"]), 10)


class PacketWriter(unittest.TestCase):
    def test_write_uses_txt_originals_and_caps_threads(self) -> None:
        class Conn:
            def execute(self, sql: str, params: tuple | None = None) -> _Rows:
                if "FROM comms_prepared_generations" in sql:
                    return _Rows([{"id": "gen-1"}])
                if "m.evidence_ref = %s" in sql:
                    ref = str(params[1])
                    tid = "T-2312" if ref == "T-2312-M-02" else "T-2345"
                    return _Rows([{"display_id": tid, "evidence_ref": ref}])
                if "FROM comms_prepared_threads" in sql and "display_id" in sql:
                    tid = str(params[1])
                    return _Rows(
                        [
                            {
                                "id": f"th-{tid}",
                                "display_id": tid,
                                "threading_confidence": "high",
                                "identity_confidence": "resolved",
                                "duplicate_omitted_count": 0,
                                "evidence_count": 1,
                                "gallery_eligibility": "eligible",
                                "message_count": 1,
                            }
                        ]
                    )
                if "FROM comms_prepared_participants" in sql:
                    return _Rows([])
                if "split_part" in sql:
                    return _Rows([])
                if "WHERE m.thread_id" in sql:
                    tid = "T-2312" if "th-T-2312" in str(params[0]) else "T-2345"
                    ref = "T-2312-M-02" if tid == "T-2312" else "T-2345-M-02"
                    return _Rows(
                        [
                            {
                                "id": f"m-{ref}",
                                "evidence_ref": ref,
                                "ordinal": 2,
                                "sent_at": None,
                                "subject": "hello",
                                "cleaned_authored_text": "Pegs",
                                "voice_corpus": True,
                                "quote_quality": "clean",
                                "identity_quality": "uncertain",
                                "authorship": "authenticated_focal",
                                "commercial_class": "none",
                                "forward_block": False,
                                "forward_omitted": False,
                                "payload_json": {"body_text": "Pegs"},
                            }
                        ]
                    )
                raise AssertionError(sql[:80])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "packet"
            leftover = out / "originals"
            leftover.mkdir(parents=True)
            (leftover / "T-9999-M-01.txt").write_text("stale\n", encoding="utf-8")
            meta = write_activation_packet(Conn(), out)
            self.assertEqual(meta["thread_count_written"], 2)
            self.assertEqual(meta["named_refs"], ["T-2312-M-02", "T-2345-M-02"])
            self.assertTrue((out / "INDEX.txt").is_file())
            self.assertTrue((out / "packet-001.txt").is_file())
            self.assertTrue((out / "README.txt").is_file())
            self.assertFalse(list(out.glob("*.html")))
            self.assertTrue((out / "originals" / "T-2312-M-02.txt").is_file())
            self.assertFalse((out / "originals" / "T-9999-M-01.txt").exists())
            packet = (out / "packet-001.txt").read_text(encoding="utf-8")
            self.assertIn("T-2312-M-02", packet)
            self.assertIn("T-2345-M-02", packet)
            self.assertNotIn("<html", packet.lower())


if __name__ == "__main__":
    unittest.main()
