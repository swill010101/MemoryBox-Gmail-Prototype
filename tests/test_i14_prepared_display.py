"""Founder-reviewed short-text display vs voice (no live DSN)."""
from __future__ import annotations

import unittest

from memorybox.ops.i14_empty_body import classify_empty_prepared
from memorybox.ops.i14_prepared_display import (
    FOUNDER_SHORT_TEXT_V3,
    KIND_DISPLAYABLE_AUTHORED,
    KIND_SIGNATURE_CLOSING,
    KIND_UNCERTAIN_FRAGMENT,
    V2_SHORT_NONBLANK_CLEANUP,
    V2_VOICE_IN_180,
    V3_SHORT_DISPLAYABLE,
    V3_SHORT_OMITTED,
    V3_VOICE_IN_180,
    classify_stored_prepared,
    display_and_voice_for_stored,
    is_displayable,
)
from memorybox.ops.i14_prepared_loader import _schema_message_fields
from memorybox.ops.i14_prepared_recovery import disposition_for


class FounderShortText(unittest.TestCase):
    def test_all_founder_reviewed_cleaned_texts(self) -> None:
        for text, from_person, kind, displayable in FOUNDER_SHORT_TEXT_V3:
            got = classify_stored_prepared(text, from_person=from_person)
            self.assertEqual(got, kind, text)
            self.assertEqual(is_displayable(got), displayable, text)

    def test_question_marks_are_authored_why(self) -> None:
        kind = classify_stored_prepared("??????", from_person="Sue")
        self.assertEqual(kind, KIND_DISPLAYABLE_AUTHORED)
        d = display_and_voice_for_stored(
            "??????", from_authenticated=True, quote_quality="clean", from_person="Sue"
        )
        self.assertTrue(d["displayable"])
        self.assertTrue(d["voice_corpus"])
        self.assertEqual(d["stored_cleaned"], "??????")

    def test_ed_comma_is_signoff_not_voice(self) -> None:
        kind = classify_stored_prepared("Ed,", from_person="Tom")
        self.assertEqual(kind, KIND_SIGNATURE_CLOSING)
        d = display_and_voice_for_stored(
            "Ed,", from_authenticated=True, quote_quality="clean", from_person="Tom"
        )
        self.assertFalse(d["displayable"])
        self.assertFalse(d["voice_corpus"])
        self.assertEqual(d["stored_cleaned"], "")

    def test_confirmed_fragment_omitted(self) -> None:
        text = "A a ml\n\n________________________________"
        kind = classify_stored_prepared(text, from_person="ph")
        self.assertEqual(kind, KIND_UNCERTAIN_FRAGMENT)
        d = display_and_voice_for_stored(
            text, from_authenticated=True, quote_quality="clean", from_person="ph"
        )
        self.assertFalse(d["displayable"])
        self.assertFalse(d["voice_corpus"])

    def test_eight_letter_threshold_is_not_the_rule(self) -> None:
        for text in ("Thanks", "Ok", "Yes", "👍🎉🙌🏖", "No!", "What day?"):
            self.assertTrue(is_displayable(classify_stored_prepared(text)))

    def test_empty_body_classifies_stored_before_original(self) -> None:
        original = (
            "Thanks\n\nOn Thu, Dec 18, 2025 at 8:24 AM Tom Will wrote:\n"
            "> Requesting prayers for my sister\n"
        )
        kept = classify_empty_prepared(
            body_text=original,
            stored_cleaned="Thanks",
            from_person="Sue",
        )
        self.assertEqual(kept["category"], "authored_prepared")
        self.assertEqual(kept["disposition"], "authored_prepared")
        omitted = classify_empty_prepared(
            body_text="Ed,\n\nOn Thu wrote:\n> prior",
            stored_cleaned="Ed,",
            from_person="Tom",
        )
        self.assertNotEqual(omitted["disposition"], "authored_prepared")
        self.assertNotEqual(omitted["disposition"], "prepared_text_unavailable")
        self.assertEqual(omitted["kind"], KIND_SIGNATURE_CLOSING)

    def test_loader_fields_keep_thanks_and_questions_voice(self) -> None:
        party = {
            "person_id": "p-sue",
            "status": "authenticated_other",
            "address": "sue@example.test",
            "label": "Sue Will",
        }
        thanks = _schema_message_fields(
            {
                "from_parties": [party],
                "cleaned_body": "Thanks",
                "authorship": "authenticated_other",
            }
        )
        self.assertEqual(thanks["cleaned"], "Thanks")
        self.assertTrue(thanks["voice_corpus"])
        self.assertEqual(thanks["prepared_text_disposition"], "authored_displayable")
        why = _schema_message_fields(
            {
                "from_parties": [party],
                "cleaned_body": "??????",
                "authorship": "authenticated_other",
            }
        )
        self.assertEqual(why["cleaned"], "??????")
        self.assertTrue(why["voice_corpus"])
        self.assertEqual(why["prepared_text_disposition"], "authored_displayable")

    def test_loader_fields_blank_signoff_and_fragment(self) -> None:
        party = {
            "person_id": "p-tom",
            "status": "authenticated_other",
            "address": "tom@example.test",
            "label": "Tom Will",
        }
        ed = _schema_message_fields(
            {
                "from_parties": [party],
                "cleaned_body": "Ed,",
                "authorship": "authenticated_other",
            }
        )
        self.assertEqual(ed["cleaned"], "")
        self.assertFalse(ed["voice_corpus"])
        self.assertEqual(ed["prepared_text_disposition"], "non_substantive")
        frag = _schema_message_fields(
            {
                "from_parties": [party],
                "cleaned_body": "A a ml\n\n________________________________",
                "authorship": "authenticated_other",
            }
        )
        self.assertEqual(frag["prepared_text_disposition"], "non_substantive")

    def test_disposition_never_unavailable_and_voice_for_signoff(self) -> None:
        d = disposition_for(
            cleaned="",
            source_text="Ed,",
            has_attachments=False,
            quote_history_removed=False,
            method="none",
        )
        self.assertEqual(d, "non_substantive")
        authored = disposition_for(
            cleaned="Thanks",
            source_text="Thanks\n\nOn wrote:\n> prior",
            has_attachments=False,
            quote_history_removed=True,
            method="on_wrote",
        )
        self.assertEqual(authored, "authored_displayable")

    def test_v3_short_text_forecast_vs_v2(self) -> None:
        self.assertEqual(V2_SHORT_NONBLANK_CLEANUP, 180)
        self.assertEqual(V3_SHORT_DISPLAYABLE, 165)
        self.assertEqual(V3_SHORT_OMITTED, 15)
        self.assertEqual(V3_SHORT_DISPLAYABLE + V3_SHORT_OMITTED, 180)
        self.assertEqual(V2_VOICE_IN_180, 22)
        self.assertEqual(V3_VOICE_IN_180, 22)
        self.assertEqual(V3_VOICE_IN_180 - V2_VOICE_IN_180, 0)

    def test_html_recovery_beyond_eight_letter_is_additional(self) -> None:
        from memorybox.ops.i14_prepared_display import html_recovery_beyond_v2_eight_letter

        self.assertTrue(
            html_recovery_beyond_v2_eight_letter(
                {
                    "body_text": "On Thu, Dec 18, 2025 at 8:24 AM Tom Will wrote:\n> Requesting prayers\n",
                    "body_html": "<p>Thanks</p>",
                }
            )
        )
        self.assertFalse(
            html_recovery_beyond_v2_eight_letter(
                {"body_text": "", "body_html": "<p>Thanks</p>"}
            )
        )


if __name__ == "__main__":
    unittest.main()
