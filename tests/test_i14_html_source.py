"""Safe HTML source selection for prepared text (no live DSN)."""
from __future__ import annotations

import unittest

from memorybox.ops.i14_prepared_recovery import disposition_for
from memorybox.ops.i14_prepared_text import html_to_plain, select_authored_source, source_is_meaningful


class HtmlSourceSelection(unittest.TestCase):
    def test_keeps_meaningful_plain_over_html(self) -> None:
        src = select_authored_source(
            {
                "body_text": "Hello from the household picnic.",
                "body_html": "<p>Different HTML body that must not win.</p>",
            }
        )
        self.assertEqual(src.kind, "body_text")
        self.assertIn("household picnic", src.text)

    def test_recovers_html_when_plain_empty(self) -> None:
        src = select_authored_source(
            {
                "body_text": "  ",
                "body_html": "<p>Thank you for telling us.</p><script>alert(1)</script>",
            }
        )
        self.assertEqual(src.kind, "html")
        self.assertIn("Thank you for telling us.", src.text)
        self.assertNotIn("<p>", src.text)
        self.assertNotIn("alert", src.text)

    def test_recovers_alt_mime_part(self) -> None:
        src = select_authored_source(
            {
                "body_text": "",
                "body_html": "",
                "body_parts": [
                    {"mime_type": "text/html", "text": "<div>Alternate part authored line here.</div>"}
                ],
            }
        )
        self.assertEqual(src.kind, "alt_part")
        self.assertIn("Alternate part authored line", src.text)

    def test_html_to_plain_strips_tracking_and_preserves_paragraphs(self) -> None:
        raw = (
            "<p>First paragraph.</p>"
            "<div style='display:none'>hidden tracking</div>"
            "<p>Second paragraph.</p>"
            "<img src='https://ads.example.test/pixel.gif'>"
        )
        plain = html_to_plain(raw)
        self.assertIn("First paragraph.", plain)
        self.assertIn("Second paragraph.", plain)
        self.assertNotIn("hidden tracking", plain)
        self.assertNotIn("<p>", plain)
        self.assertIn("\n", plain)

    def test_entities_and_hotmail_glue(self) -> None:
        html = (
            "<p>Pegs &amp; Tom went later.</p>"
            "<p>Date: Tue, 23 Dec 2008 17:10:47 -0600From: a@example.test"
            "To: b@example.testSubject: Crazy</p>"
        )
        src = select_authored_source({"body_text": "", "body_html": html})
        self.assertTrue(src.hotmail_glued)
        self.assertIn("Pegs & Tom went later.", src.text)
        self.assertNotIn("&amp;", src.text)

    def test_dispositions(self) -> None:
        self.assertEqual(
            disposition_for(
                cleaned="Thank you for telling us.",
                source_text="Thank you for telling us.",
                has_attachments=False,
                quote_history_removed=False,
                method="plain",
            ),
            "authored_prepared",
        )
        self.assertEqual(
            disposition_for(
                cleaned="",
                source_text="",
                has_attachments=True,
                quote_history_removed=False,
                method="",
            ),
            "attachment_only",
        )
        self.assertEqual(
            disposition_for(
                cleaned="",
                source_text="> q",
                has_attachments=False,
                quote_history_removed=True,
                method="on_wrote",
            ),
            "correctly_empty",
        )
        self.assertEqual(
            disposition_for(
                cleaned="",
                source_text="Meaningful original still present here.",
                has_attachments=False,
                quote_history_removed=False,
                method="",
            ),
            "prepared_text_unavailable",
        )

    def test_voice_drop_reasons_are_mutually_exclusive(self) -> None:
        from memorybox.ops.i14_prepared_recovery import classify_voice_drop

        self.assertEqual(
            classify_voice_drop(
                stored_voice=True,
                after_voice=False,
                cleaned="",
                disposition="prepared_text_unavailable",
                quote_after="clean",
                from_authenticated=True,
                commercial_after="not_commercial",
            ),
            "prepared_text_unavailable",
        )
        self.assertEqual(
            classify_voice_drop(
                stored_voice=True,
                after_voice=False,
                cleaned="kept text here",
                disposition="authored_prepared",
                quote_after="suspected_contamination",
                from_authenticated=True,
                commercial_after="suppress_default",
            ),
            "quote_contamination",
        )
        self.assertIsNone(
            classify_voice_drop(
                stored_voice=True,
                after_voice=True,
                cleaned="kept",
                disposition="authored_prepared",
                quote_after="clean",
                from_authenticated=True,
                commercial_after="not_commercial",
            )
        )

    def test_john_html_only_recovers_without_markup(self) -> None:
        html = (
            "<html><head><style>p{display:none}</style><script>alert(1)</script></head>"
            "<body><p>I am so sorry to hear this news about your sister.</p>"
            "<p>On Thu, Dec 18, 2025 at 8:24 AM Tom Will wrote:<br>"
            "&gt; Requesting prayers</p>"
            "<img src='https://track.example.test/pixel.gif'></body></html>"
        )
        src = select_authored_source({"body_text": "", "body_html": html})
        from memorybox.ops.i14_prepared_text import prepare_message_text

        prep = prepare_message_text(src.text, subject="Re: Passing")
        self.assertEqual(src.kind, "html")
        self.assertIn("so sorry to hear this news", prep.authored)
        self.assertNotIn("<p>", prep.authored)
        self.assertNotIn("alert", prep.authored)
        self.assertNotIn("https://", prep.authored)
        self.assertNotIn("Requesting prayers", prep.authored)
        self.assertTrue(source_is_meaningful("Thank you for telling us."))

    def test_founder_packet_accepts_slot_map(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from memorybox.ops.i14_prepared_recovery import write_founder_packet

        census = {
            "sample_rows": {
                "john_t39987": {
                    "slot": "john_t39987",
                    "display_id": "T-39987",
                    "ordinal": 2,
                    "evidence_id": "00000000-0000-0000-0000-000000000001",
                    "source_kind": "html",
                    "disposition": "authored_prepared",
                    "stored_empty": True,
                    "prepared_text": "synthetic recovered sentence",
                }
            }
        }
        with TemporaryDirectory() as tmp:
            path = write_founder_packet(census, Path(tmp))
            text = path.read_text(encoding="utf-8")
        self.assertIn("T-39987", text)
        self.assertIn("synthetic recovered sentence", text)


if __name__ == "__main__":
    unittest.main()
