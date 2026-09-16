"""Phase C count, 1970, Cora story, and progressive-Ask regressions."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from memorybox.explore.gallery_scope import (
    curator_gallery_sentence,
    is_sentinel_date,
    item_in_ask_window,
    restrict_items_to_ask_dates,
    scoped_counts,
    comms_ask_scope,
)
from memorybox.explore.find import hydrate_sms_payload
from memorybox.ask.retrieve import story_search_tokens


class Sentinel1970(unittest.TestCase):
    def test_sentinel_is_not_a_real_year(self) -> None:
        self.assertTrue(is_sentinel_date("1970-01-01T00:00:00+00:00"))
        self.assertFalse(is_sentinel_date("1970-06-15"))
        self.assertFalse(is_sentinel_date("2017-01-01"))

    def test_dated_ask_drops_sentinel(self) -> None:
        items = [
            {"type": "email", "date": "1970-01-01T00:00:00Z", "undated": False},
            {"type": "email", "date": "2017-04-02", "undated": False},
        ]
        out = restrict_items_to_ask_dates(
            items, time_start="2017-01-01", time_end="2017-12-31"
        )
        self.assertEqual([i["date"] for i in out], ["2017-04-02"])


class ScopedCounts(unittest.TestCase):
    def test_communications_is_email_plus_sms(self) -> None:
        c = scoped_counts(sms_n=328, email_threads=10, photo_n=246)
        self.assertEqual(c["communications"], 338)
        self.assertEqual(c["email_threads"], 10)
        text = curator_gallery_sentence(
            person_label="Sue Will",
            year=2017,
            photo_n=246,
            sms_n=328,
            thread_n=10,
        )
        self.assertIn("10 email threads", text)
        self.assertIn("328 text messages", text)
        self.assertNotIn("1970", text)


class CoraStoryTokens(unittest.TestCase):
    def test_will_is_a_name_token_not_a_topic(self) -> None:
        class Plan:
            original_ask = "Show me Cora Will"
            retrieval_constraints = ("Cora Will",)
            person_names = ("Cora Will",)

        tokens = [t.lower() for t in story_search_tokens(Plan())]
        self.assertIn("cora", tokens)
        self.assertIn("will", tokens)


class SmsHydrateCancel(unittest.TestCase):
    def test_stale_token_cancels(self) -> None:
        with patch("memorybox.explore.prepared_comms.token_live", return_value=False):
            out = hydrate_sms_payload(
                person_id="x",
                token="stale",
                ask_text="Show me Cora Will",
            )
        self.assertTrue(out["cancelled"])
        self.assertEqual(out["items"], [])


class FindSkipsBlockingSms(unittest.TestCase):
    def test_mixed_gallery_marks_sms_pending(self) -> None:
        os.environ["MEMORYBOX_I14_GALLERY_COMMS"] = "1"

        class Orch:
            def ask(self, text, session_id=None):
                return {
                    "ok": True,
                    "session_id": session_id or "s1",
                    "plan": {
                        "person_ids": ["11111111-1111-1111-1111-111111111111"],
                        "person_names": ["Tom Will"],
                        "output_mode": "show",
                        "want_story": False,
                        "time_start": None,
                        "time_end": None,
                    },
                    "evidence_hits": [],
                    "photo_hits": [],
                    "story_hits": [],
                    "artifact_hits": [],
                    "answer_kind": "show",
                    "context": {},
                    "provider_status": {},
                }

        with patch("memorybox.explore.find._attach_hidden_sms") as sms:
            from memorybox.explore.find import build_explore_find

            payload = build_explore_find(ask_text="Show me Tom Will", orchestrator=Orch())
        sms.assert_not_called()
        st = payload.get("explore_state") or {}
        self.assertTrue(st.get("sms_pending"))
        self.assertTrue(st.get("prepared_comms_pending"))
        os.environ.pop("MEMORYBOX_I14_GALLERY_COMMS", None)


if __name__ == "__main__":
    unittest.main()
