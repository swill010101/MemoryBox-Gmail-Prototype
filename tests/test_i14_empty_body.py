"""Empty prepared-body classification (no live DSN)."""
from __future__ import annotations

import unittest

from memorybox.ops.i14_empty_body import classify_empty_prepared, notice_for


class EmptyBody(unittest.TestCase):
    def test_original_empty(self) -> None:
        c = classify_empty_prepared(body_text="", body_html="", has_attachments=False)
        self.assertEqual(c["category"], "original_genuinely_empty")
        self.assertEqual(c["disposition"], "correct_empty")

    def test_attachment_only(self) -> None:
        c = classify_empty_prepared(body_text="  ", has_attachments=True)
        self.assertEqual(c["category"], "attachment_only")
        self.assertIn("attachments", notice_for(c["category"], has_attachments=True).lower())

    def test_quoted_history_only(self) -> None:
        raw = (
            "On Thu, Dec 18, 2025 at 8:24 AM Tom Will wrote:\n"
            "> Requesting prayers for my sister\n"
        )
        c = classify_empty_prepared(body_text=raw, commercial_class="not_commercial")
        self.assertEqual(c["category"], "quoted_history_only")
        self.assertEqual(c["disposition"], "correct_empty")

    def test_stored_short_authored_is_not_unavailable(self) -> None:
        c = classify_empty_prepared(
            body_text="Thanks\n\nOn Thu wrote:\n> prior",
            stored_cleaned="Thanks",
            from_person="Sue",
        )
        self.assertEqual(c["disposition"], "authored_prepared")

    def test_stored_ed_signoff_is_not_voice_or_unavailable(self) -> None:
        c = classify_empty_prepared(
            body_text="Ed,",
            stored_cleaned="Ed,",
            from_person="Tom",
        )
        self.assertEqual(c["kind"], "signature_closing")
        self.assertNotEqual(c["disposition"], "prepared_text_unavailable")
        self.assertNotEqual(c["disposition"], "authored_prepared")

    def test_cleanup_removed_meaningful_before_quote(self) -> None:
        raw = (
            "I am so sorry to hear this news about Peggy.\n\n"
            "On Thu, Dec 18, 2025 at 8:24 AM Tom Will wrote:\n"
            "> Requesting prayers\n"
        )
        c = classify_empty_prepared(body_text=raw, commercial_class="not_commercial")
        # Current cleaner should KEEP the authored sentence; this is not empty after prepare.
        from memorybox.ops.i14_prepared_text import prepare_message_text

        kept = prepare_message_text(raw).authored
        self.assertTrue(len(kept.strip()) > 8)
        self.assertEqual(c["category"], "cleanup_removed_meaningful")
        self.assertEqual(c["disposition"], "prepared_text_unavailable")

    def test_defect_when_unique_text_sits_inside_hotmail_block(self) -> None:
        raw = (
            "Date: Thu, 18 Dec 2025 08:27:00 -0600\n"
            "Subject: Re: Passing of my sister, Peggy on 12/14\n"
            "From: John Schroeder <jschroeder@example.test>\n"
            "To: Tom Will <tom@example.test>\n"
            "I am so sorry to hear this about your sister.\n"
        )
        c = classify_empty_prepared(body_text=raw, commercial_class="not_commercial")
        self.assertEqual(c["disposition"], "prepared_text_unavailable")
        self.assertEqual(c["category"], "cleanup_removed_meaningful")

    def test_html_only_defect_when_html_has_authored(self) -> None:
        html = "<p>Thank you for telling us.</p>"
        c = classify_empty_prepared(
            body_text="",
            body_html=html,
            html_only=True,
            commercial_class="not_commercial",
        )
        self.assertEqual(c["category"], "html_only_or_alt_part")
        self.assertEqual(c["disposition"], "defect")


if __name__ == "__main__":
    unittest.main()
