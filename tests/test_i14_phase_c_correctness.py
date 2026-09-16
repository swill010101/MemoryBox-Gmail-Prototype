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
        self.assertLess(text.index("email thread"), text.index("text message"))
        self.assertNotIn("1970", text)

    def test_partial_communications_is_marked_loading(self) -> None:
        from memorybox.explore.gallery_scope import (
            communications_parent_label,
            curator_gallery_sentence,
            email_pill_label,
            text_pill_label,
        )

        c = scoped_counts(email_threads=1257, sms_n=0, sms_loading=True)
        self.assertFalse(c["counts_final"])
        self.assertEqual(c["communications"], 1257)
        parent = communications_parent_label(
            email_threads=1257, sms=0, sms_loading=True
        )
        self.assertIn("1,257", parent)
        self.assertIn("Text loading", parent)
        self.assertNotEqual(parent, "Communications · 1,257")
        self.assertEqual(email_pill_label(email_threads=1257), "Email · 1,257")
        self.assertEqual(text_pill_label(sms=0, sms_loading=True), "Text · loading…")
        text = curator_gallery_sentence(
            person_label="Sue Will",
            year=None,
            photo_n=100,
            thread_n=1257,
            sms_n=0,
            loading_sms=True,
        )
        self.assertIn("1,257 email threads", text)
        self.assertIn("Text messages loading", text)

    def test_final_email_plus_sms_arithmetic(self) -> None:
        from memorybox.explore.gallery_scope import communications_parent_label

        c = scoped_counts(email_threads=1257, sms_n=4869)
        self.assertTrue(c["counts_final"])
        self.assertEqual(c["communications"], 6126)
        self.assertEqual(
            communications_parent_label(email_threads=1257, sms=4869),
            "Communications · 6,126",
        )
        text = curator_gallery_sentence(
            person_label="Sue Will",
            year=None,
            thread_n=1257,
            sms_n=4869,
        )
        self.assertIn("1,257 email threads and 4,869 text messages", text)

    def test_no_duplicate_sms_refetch_on_filter(self) -> None:
        from memorybox.explore.gallery_scope import comms_filter_may_refetch_sms

        self.assertFalse(
            comms_filter_may_refetch_sms(
                mixed_gallery=True, sms_pending=True, sms_cached=False
            )
        )
        self.assertFalse(
            comms_filter_may_refetch_sms(
                mixed_gallery=True, sms_pending=False, sms_cached=True
            )
        )

    def test_visual_equation_unexplained_zero(self) -> None:
        from memorybox.explore.gallery_scope import visual_count_equation

        eq = visual_count_equation(
            immich_assets=5015,
            immich_photos=4900,
            immich_videos=115,
            mb_photos=4923,
            mb_videos=0,
            pagination_or_window=92,
        )
        self.assertEqual(eq["unexplained"], 0)
        self.assertTrue(eq["ok"])


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

    def test_hydrate_reuses_cache(self) -> None:
        from memorybox.explore.find import clear_sms_hydrate_cache, hydrate_sms_payload

        clear_sms_hydrate_cache()
        with patch("memorybox.explore.prepared_comms.token_live", return_value=True):
            with patch("memorybox.ask.retrieve.search_sms_messages", return_value=[]) as search:
                first = hydrate_sms_payload(
                    person_id="x",
                    token="t1",
                    ask_text="Show me Sue Will",
                )
                second = hydrate_sms_payload(
                    person_id="x",
                    token="t1",
                    ask_text="Show me Sue Will",
                )
        search.assert_called_once()
        self.assertFalse(first.get("from_cache"))
        self.assertTrue(second.get("from_cache"))


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
