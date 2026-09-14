"""I14 Phase C Gallery prepared-comms reads. No live DSN."""
from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

from memorybox.explore import prepared_comms as pc
from memorybox.explore.find import build_explore_find


class _Rows:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class FakeConn:
    def __init__(self, *, active: str | None = "gen-active") -> None:
        self.active = active
        self.sql: list[str] = []

    def execute(self, sql: str, params: tuple | None = None) -> _Rows:
        text = " ".join(sql.split())
        self.sql.append(text)
        if "FROM comms_prepared_active_generations" in text:
            return _Rows([{"id": self.active}] if self.active else [])
        if "GROUP BY t.gallery_eligibility" in text:
            return _Rows(
                [
                    {"gallery_eligibility": "show_by_default", "n": 3},
                    {"gallery_eligibility": "suppress_default", "n": 2},
                    {"gallery_eligibility": "hold_uncertain", "n": 1},
                ]
            )
        if "gallery_eligibility = 'show_by_default'" in text:
            assert "voice_corpus" not in text
            assert "p.person_id = %s" in text or "p.person_id = %s" in text.replace(
                " ", ""
            )
            return _Rows(
                [
                    {
                        "display_id": "T-100",
                        "earliest_at": None,
                        "latest_at": None,
                        "message_count": 2,
                        "identity_confidence": "authenticated_focal",
                        "gallery_eligibility": "show_by_default",
                        "subject": "Hello",
                        "preview": "Hi there",
                        "attachment_count": 1,
                        "participants": "Peggy, Tom",
                    },
                    {
                        "display_id": "T-100",
                        "earliest_at": None,
                        "latest_at": None,
                        "message_count": 2,
                        "identity_confidence": "authenticated_focal",
                        "gallery_eligibility": "show_by_default",
                        "subject": "Hello",
                        "preview": "Hi there",
                        "attachment_count": 1,
                        "participants": "Peggy, Tom",
                    },
                ]
            )
        if "FROM comms_prepared_threads" in text and "display_id" in text:
            return _Rows(
                [
                    {
                        "id": "tid",
                        "identity_confidence": "authenticated_focal",
                    }
                ]
            )
        if "FROM comms_prepared_messages" in text:
            return _Rows(
                [
                    {
                        "id": "mid",
                        "ordinal": 1,
                        "evidence_ref": "EV-1",
                        "evidence_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "subject": "Hello",
                        "sent_at": None,
                        "cleaned_authored_text": "Hi there",
                        "quote_quality": "clean",
                        "identity_quality": "authenticated",
                        "voice_corpus": False,
                        "commercial_class": "not_commercial",
                    }
                ]
            )
        if "FROM comms_prepared_participants" in text:
            return _Rows(
                [
                    {
                        "role": "from",
                        "display_name": "Peggy",
                        "identity_confidence": "authenticated_focal",
                        "person_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    },
                    {
                        "role": "to",
                        "display_name": "Tom",
                        "identity_confidence": "authenticated_other",
                        "person_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    },
                    {
                        "role": "cc",
                        "display_name": "someone",
                        "identity_confidence": "unverified",
                        "person_id": None,
                    },
                ]
            )
        if "FROM comms_prepared_attachments" in text:
            return _Rows(
                [
                    {
                        "filename": "photo.jpg",
                        "mime_type": "image/jpeg",
                        "byte_size": 12,
                        "gallery_action": "view_image",
                        "attachment_evidence_id": None,
                        "source_locator": "mbox:1",
                        "attachment_ordinal": 0,
                    }
                ]
            )
        return _Rows([])


class Flag(unittest.TestCase):
    def test_default_off(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        self.assertFalse(pc.gallery_comms_enabled())

    def test_on(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        self.assertTrue(pc.gallery_comms_enabled())
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)


class ListThreads(unittest.TestCase):
    def tearDown(self) -> None:
        pc._last_complete.clear()
        pc._tokens.clear()

    def test_active_only_dedupes_and_hides_commercial(self) -> None:
        token = pc.new_ask_token()
        out = pc.list_person_threads(FakeConn(), person_id="person-p", token=token)
        self.assertTrue(out["active_generation"])
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["id"], "prepared:T-100")
        self.assertEqual(out["excluded"]["suppress_default"], 2)
        self.assertEqual(out["excluded"]["hold_uncertain"], 1)
        self.assertEqual(out["thread_total"], 3)
        self.assertFalse(out["items"][0]["gallery_default_hidden"])

    def test_cancel_after_abandon(self) -> None:
        token = pc.new_ask_token()
        pc.abandon_token(token)
        out = pc.list_person_threads(FakeConn(), person_id="person-p", token=token)
        self.assertTrue(out["cancelled"])
        self.assertEqual(out["items"], [])

    def test_new_ask_cancels_previous_token(self) -> None:
        first = pc.new_ask_token()
        pc.new_ask_token()
        self.assertFalse(pc.token_live(first))

    def test_stale_uses_last_complete(self) -> None:
        token = pc.new_ask_token()
        first = pc.list_person_threads(FakeConn(), person_id="person-p", token=token)
        token2 = pc.new_ask_token()
        stale = pc.list_person_threads(
            FakeConn(active=None), person_id="person-p", token=token2
        )
        self.assertTrue(stale["stale"])
        self.assertEqual(len(stale["items"]), len(first["items"]))
        self.assertTrue(stale["updated_through"])

    def test_roles_not_voice_only(self) -> None:
        token = pc.new_ask_token()
        conn = FakeConn()
        pc.list_person_threads(conn, person_id="person-p", token=token)
        listing = "\n".join(conn.sql)
        self.assertIn("EXISTS", listing)
        self.assertNotIn("voice_corpus", listing)
        self.assertNotIn("role = 'from'", listing)


class LoadThread(unittest.TestCase):
    def test_story_and_unverified_cc(self) -> None:
        out = pc.load_thread(FakeConn(), "T-100")
        self.assertTrue(out["ok"])
        self.assertEqual(out["story_memory"]["source_kind"], "email_thread")
        self.assertEqual(out["story_memory"]["source_id"], "T-100")
        cc = out["messages"][0]["cc"][0]
        self.assertFalse(cc["trusted"])
        self.assertTrue(out["messages"][0]["from"][0]["trusted"])
        self.assertIn("Hi there", out["story_body"])


class ExploreFind(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        pc._tokens.clear()

    def test_flag_off_person_ask_does_not_pending_prepared(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        payload = build_explore_find(
            ask_text="Show me Peggy", session_id="s", orchestrator=orch
        )
        self.assertFalse(payload["explore_state"]["prepared_comms_pending"])
        self.assertFalse(payload["explore_state"]["gallery_show_email"])

    def test_flag_off_explicit_email_still_uses_raw_retrieve(self) -> None:
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        with patch("memorybox.ask.retrieve.search_email_messages", return_value=[]) as search:
            payload = build_explore_find(
                ask_text="Show me Peggy emails", session_id="s", orchestrator=orch
            )
        self.assertFalse(payload["explore_state"]["prepared_comms_pending"])
        search.assert_called()

    def test_flag_on_skips_raw_email(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"
        orch = types.SimpleNamespace(
            ask=lambda *a, **k: {
                "plan": {
                    "person_ids": ["11111111-1111-1111-1111-111111111111"],
                    "person_names": ["Peggy"],
                    "output_mode": "show",
                },
                "photo_hits": [
                    {"external_id": "photo-1", "people": ["Peggy"], "taken_at": "2010-01-02"}
                ],
                "video_hits": [],
                "evidence_hits": [],
                "provider_status": {},
            }
        )
        with patch(
            "memorybox.ask.retrieve.search_email_messages",
            side_effect=AssertionError("raw email parse forbidden"),
        ):
            payload = build_explore_find(
                ask_text="Show me Peggy", session_id="s", orchestrator=orch
            )
        self.assertTrue(payload["explore_state"]["prepared_comms_pending"])
        self.assertTrue(payload["explore_state"]["prepared_comms_token"])
        self.assertTrue(payload["explore_state"]["gallery_show_email"])
        types_ = {str(i.get("type")) for i in payload["items"]}
        self.assertIn("photo", types_)
        self.assertNotIn("email", types_)


if __name__ == "__main__":
    unittest.main()
