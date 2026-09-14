"""Flags and sequential-prior uniqueness for the read-only voice-delta tool."""
from __future__ import annotations

import os
import unittest

from memorybox.ops.i14_prepared_loader import _schema_message_fields
from memorybox.ops.i14_voice_delta import VoiceDeltaError, _allow, _token


class VoiceDeltaFlags(unittest.TestCase):
    def test_refuses_without_flags(self) -> None:
        os.environ.pop("MEMORYBOX_I14_VOICE_DELTA_ALLOW_FLIGHTSIM", None)
        os.environ.pop("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", None)
        from memorybox.ops.i14_voice_delta import _allow

        with self.assertRaises(VoiceDeltaError):
            _allow()

    def test_first_token(self) -> None:
        self.assertEqual(_token("Tom Williams"), "Tom")


class SchemaVoice(unittest.TestCase):
    def test_quote_method_on_wrote_does_not_require_empty_authored(self) -> None:
        fields = _schema_message_fields(
            {
                "from_parties": [
                    {"person_id": "p1", "status": "authenticated_other", "address": "tom@example.test"}
                ],
                "cleaned_body": "ZZZX Picnic at Tower Grove at noon uniquely.",
                "clean_method": "on_wrote",
                "authorship": "authenticated_other",
            }
        )
        self.assertEqual(fields["quote_quality"], "suspected_contamination")
        self.assertFalse(fields["voice_corpus"])
        self.assertIn("ZZZX Picnic", fields["cleaned"])

    def test_unverified_recipient_does_not_strip_authenticated_from_voice(self) -> None:
        fields = _schema_message_fields(
            {
                "from_parties": [
                    {"person_id": "p1", "status": "authenticated_other", "address": "tom@example.test"}
                ],
                "cleaned_body": "Meet at the hardware store Saturday morning uniquely.",
                "clean_method": "none",
                "authorship": "authenticated_other",
                "ambiguous_participant": True,
            }
        )
        self.assertEqual(fields["identity_quality"], "uncertain")
        self.assertEqual(fields["quote_quality"], "clean")
        self.assertTrue(fields["voice_corpus"])


if __name__ == "__main__":
    unittest.main()
