"""Synthetic proofs for canonical TXT review packets and address-ledger authorship."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memorybox.ops import i14_peggy_preview as preview
from memorybox.ops import i14_thread_review as review
from memorybox.ops.i14_peggy_preview import PreviewError
from tests.test_i14_peggy_preview import _all_case_messages, _build_all_cases, _msg


class AuthorshipLedger(unittest.TestCase):
    def _ledger(self) -> review.IdentityLedger:
        ledger = review.IdentityLedger(focal_person_id="person-peggy")
        review.add_confirmed_address(ledger, address="peggy@example.test", person_id="person-peggy", label="Peggy Example")
        review.add_confirmed_address(ledger, address="alice@example.test", person_id="person-alice", label="Alice Example")
        return ledger

    def test_voice_corpus_requires_authenticated_from_address(self) -> None:
        ledger = self._ledger()
        sent_by = review.classify_message(
            {
                "from": "Peg Legg <peggy@example.test>",
                "to": ["Alice Example <alice@example.test>"],
                "from_parsed": [{"display_name": "Peg Legg", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
                "to_parsed": [{"display_name": "Alice Example", "address": "alice@example.test", "normalized": "alice@example.test"}],
            },
            ledger,
        )
        sent_to = review.classify_message(
            {
                "from": "Alice Example <alice@example.test>",
                "to": ["Peg Legg <peggy@example.test>"],
                "from_parsed": [{"display_name": "Alice Example", "address": "alice@example.test", "normalized": "alice@example.test"}],
                "to_parsed": [{"display_name": "Peg Legg", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
            },
            ledger,
        )
        nickname_only = review.classify_message(
            {
                "from": "Peg Legg <other@example.test>",
                "to": ["Alice Example <alice@example.test>"],
                "from_parsed": [{"display_name": "Peg Legg", "address": "other@example.test", "normalized": "other@example.test"}],
                "to_parsed": [{"display_name": "Alice Example", "address": "alice@example.test", "normalized": "alice@example.test"}],
            },
            ledger,
        )
        self.assertTrue(sent_by["voice_corpus"])
        self.assertEqual(sent_by["direction"], "sent_by_authenticated_peggy")
        self.assertFalse(sent_to["voice_corpus"])
        self.assertEqual(sent_to["direction"], "sent_to_peggy_authored_other")
        self.assertEqual(sent_to["authorship"], review.AUTH_OTHER)
        self.assertFalse(nickname_only["voice_corpus"])
        self.assertEqual(nickname_only["authorship"], review.UNVERIFIED)
        self.assertTrue(nickname_only["display_name_only_peggy_rejected"])

    def test_ambiguous_is_not_universal_when_ledger_binds(self) -> None:
        ledger = self._ledger()
        a = _msg(
            1,
            **{"from": "Alice <alice@example.test>"},
            to=["Peggy <peggy@example.test>"],
            from_parsed=[{"display_name": "Alice", "address": "alice@example.test", "normalized": "alice@example.test"}],
            to_parsed=[{"display_name": "Peggy", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
            rfc_message_id="<a@example.test>",
            content_hash="aa" * 32,
        )
        b = _msg(
            2,
            **{"from": "Peggy <peggy@example.test>"},
            to=["Alice <alice@example.test>"],
            from_parsed=[{"display_name": "Peggy", "address": "peggy@example.test", "normalized": "peggy@example.test"}],
            to_parsed=[{"display_name": "Alice", "address": "alice@example.test", "normalized": "alice@example.test"}],
            rfc_message_id="<b@example.test>",
            in_reply_to_ids=["<a@example.test>"],
            content_hash="bb" * 32,
            sent_at="2020-01-01T13:00:00+00:00",
        )
        pack = preview.reconstruct([a, b], ledger=ledger)
        self.assertEqual(pack["thread_count"], 1)
        self.assertNotIn("ambiguous_participant_identity", pack["threads"][0]["cases"])
        self.assertEqual(pack["authorship"]["sent_by_authenticated_peggy"], 1)
        self.assertEqual(pack["authorship"]["sent_to_peggy_authored_other"], 1)
        self.assertEqual(pack["authorship"]["voice_corpus"], 1)

    def test_txt_layout_and_single_original(self) -> None:
        sample = review.sanitized_layout_example()
        self.assertIn("BEGIN THREAD  T-0001", sample)
        self.assertIn("END THREAD  T-0001", sample)
        self.assertIn("From: Alice Example <alice@example.test> [authenticated other Person (Alice Example)]", sample)
        self.assertIn("To: Peggy Example <peggy@example.test> [authenticated Peggy]", sample)
        self.assertIn("Authorship: authenticated Peggy", sample)
        self.assertIn("Voice corpus: yes", sample)
        self.assertIn("Voice corpus: no", sample)
        self.assertIn("Evidence-ref: T-0001-M-01", sample)
        self.assertIn("America/Chicago", sample)
        with tempfile.TemporaryDirectory() as tmp:
            pack = preview.reconstruct(_all_case_messages())
            meta = review.write_review_tree(pack, Path(tmp), representative_only=True)
            self.assertTrue((Path(tmp) / "INDEX.txt").exists())
            self.assertTrue((Path(tmp) / "README.txt").exists())
            self.assertTrue((Path(tmp) / "packet-001.txt").exists())
            ref = "T-0001-M-01"
            original = Path(tmp) / "originals" / f"{ref}.txt"
            self.assertTrue(original.exists())
            self.assertIn("Evidence-ref:", original.read_text(encoding="utf-8"))
            self.assertLessEqual(meta["thread_count_written"], 25)
            self.assertIn("accept_thread", (Path(tmp) / "README.txt").read_text(encoding="utf-8"))

    def test_packet_chunk_size(self) -> None:
        threads = [{"preview_thread_id": f"T-{i:04d}", "messages": [], "cases": []} for i in range(1, 53)]
        chunks = review.packet_chunks(threads, size=25)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 25)
        self.assertEqual(len(chunks[1]), 25)
        self.assertEqual(len(chunks[2]), 2)

    def test_production_emit_refused_without_env(self) -> None:
        import os

        os.environ.pop("MEMORYBOX_I14_REVIEW_EMIT_PRIVATE", None)
        with self.assertRaises(PreviewError) as ctx:
            preview.main(["--review-out", "working/i14-thread-review"])
        self.assertEqual(str(ctx.exception), "private_review_emit_not_authorized")


class HtmlRetired(unittest.TestCase):
    def test_html_retired(self) -> None:
        with self.assertRaises(PreviewError) as ctx:
            preview.render_html({})
        self.assertEqual(str(ctx.exception), "html_review_retired")


class RepresentativeCases(unittest.TestCase):
    def test_fixture_covers_required_or_explicit_missing(self) -> None:
        pack = _build_all_cases()
        _, coverage = review.select_representative(pack["threads"])
        for case, value in coverage.items():
            self.assertTrue(value.startswith("T-") or value == "not_present_in_corpus", msg=f"{case}={value}")
        self.assertNotEqual(coverage["normal_two_person"], "not_present_in_corpus")
        self.assertNotEqual(coverage["long_thread"], "not_present_in_corpus")
        self.assertNotEqual(coverage["forwarded_message"], "not_present_in_corpus")
        self.assertNotEqual(coverage["quoted_reply_stripping"], "not_present_in_corpus")
        self.assertNotEqual(coverage["changed_subject"], "not_present_in_corpus")
        self.assertNotEqual(coverage["attachment_indicators"], "not_present_in_corpus")
        self.assertNotEqual(coverage["ambiguous_participant_identity"], "not_present_in_corpus")


class CommercialAndBounds(unittest.TestCase):
    def test_commercial_classes(self) -> None:
        retain = review.classify_commercial({"subject": "Your United itinerary", "from_handle": "a@example.test"})
        suppress = review.classify_commercial({"subject": "Weekly deals 20% off", "from_handle": "x@mailchimp.com"})
        uncertain = review.classify_commercial({"subject": "Order confirmation #12", "from_handle": "store@example.test"})
        self.assertEqual(retain["commercial_class"], "commercial_retain")
        self.assertEqual(suppress["commercial_class"], "commercial_suppress")
        self.assertEqual(uncertain["commercial_class"], "commercial_uncertain")

    def test_full_corpus_emit_refused(self) -> None:
        threads = [{"preview_thread_id": f"T-{i:04d}", "messages": [], "cases": []} for i in range(26)]
        with self.assertRaises(review.ReviewError) as ctx:
            with tempfile.TemporaryDirectory() as tmp:
                review.write_review_tree({"threads": threads}, Path(tmp), representative_only=False)
        self.assertEqual(str(ctx.exception), "full_corpus_emit_refused")

    def test_one_packet_file_only(self) -> None:
        pack = _build_all_cases()
        with tempfile.TemporaryDirectory() as tmp:
            meta = review.write_review_tree(pack, Path(tmp), founder_packet=True)
            packets = list(Path(tmp).glob("packet-*.txt"))
            self.assertEqual(len(packets), 1)
            self.assertEqual(packets[0].name, "packet-001.txt")
            self.assertLessEqual(meta["thread_count_written"], 25)
            self.assertLessEqual(meta["sizes"]["packet_bytes"], review.MAX_PACKET_BYTES)
            self.assertEqual(meta["sizes"]["packet_files"], 1)

    def test_image_vs_pdf_attachment_action(self) -> None:
        self.assertEqual(review.gallery_attachment_action("pic.JPG", "image/jpeg"), "view_image")
        self.assertEqual(review.gallery_attachment_action("t.pdf", "application/pdf"), "open_pdf")
        self.assertEqual(review.gallery_attachment_action("x.bin", "application/octet-stream"), "record_only")


if __name__ == "__main__":
    unittest.main()
