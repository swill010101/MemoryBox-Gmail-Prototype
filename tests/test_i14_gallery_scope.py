"""Ask-date Gallery scope helpers."""
from __future__ import annotations

import unittest

from memorybox.explore.gallery_scope import (
    comms_ask_scope,
    curator_gallery_sentence,
    curator_language_ok,
    restrict_items_to_ask_dates,
)


class Scope(unittest.TestCase):
    def test_year_ask_is_month_grain(self) -> None:
        s = comms_ask_scope("2017-01-01", "2017-12-31")
        self.assertEqual(s.grain, "month")
        self.assertEqual(s.calendar_year, 2017)
        self.assertTrue(s.dated)

    def test_person_only_is_year_grain(self) -> None:
        s = comms_ask_scope(None, None)
        self.assertEqual(s.grain, "year")
        self.assertFalse(s.dated)

    def test_dated_ask_drops_undated_and_other_years(self) -> None:
        items = [
            {"type": "photo", "date": "2017-06-01", "undated": False},
            {"type": "photo", "date": "2016-06-01", "undated": False},
            {"type": "story", "date": "", "undated": True},
            {"type": "email", "date": "2018-01-02", "undated": False},
        ]
        out = restrict_items_to_ask_dates(
            items, time_start="2017-01-01", time_end="2017-12-31"
        )
        self.assertEqual([i["type"] for i in out], ["photo"])
        self.assertEqual(out[0]["date"], "2017-06-01")

    def test_curator_has_no_paging_language(self) -> None:
        text = curator_gallery_sentence(
            person_label="Sue Will",
            year=2017,
            photo_n=4,
            video_n=1,
            story_n=2,
            thread_n=10,
        )
        self.assertIn("Sue Will", text)
        self.assertIn("2017", text)
        self.assertIn("conversations", text)
        self.assertTrue(curator_language_ok(text))
        self.assertFalse(curator_language_ok("80 of 1325 reachable email threads"))
        self.assertFalse(curator_language_ok("page 80 max"))


if __name__ == "__main__":
    unittest.main()
