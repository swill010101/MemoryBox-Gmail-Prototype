"""Consolidation classes: identity keys only. Never merge similar distinct messages."""
from __future__ import annotations

import unittest
from uuid import uuid4

from memorybox.ops.i14_consolidation import classify_pair, consolidate_messages
from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn


HASH_A = "a" * 64
HASH_B = "b" * 64


def _row(**kwargs):
    base = {
        "evidence_id": str(uuid4()),
        "source_id": str(uuid4()),
        "content_hash": HASH_A,
        "rfc_message_id": "<one@example.test>",
        "timestamp": "2011-09-29T15:01:58+00:00",
    }
    base.update(kwargs)
    return base


class ConsolidationUnits(unittest.TestCase):
    def test_pair_classes(self) -> None:
        self.assertEqual(
            classify_pair(same_hash=True, same_rfc=True, same_source=True),
            "exact_duplicate_evidence",
        )
        self.assertEqual(
            classify_pair(same_hash=True, same_rfc=True, same_source=False),
            "same_communication_multiple_extracts",
        )
        self.assertEqual(
            classify_pair(same_hash=False, same_rfc=True, same_source=False),
            "same_communication_multiple_extracts",
        )
        self.assertEqual(
            classify_pair(same_hash=False, same_rfc=False, same_source=False),
            "distinct_evidence",
        )

    def test_similar_text_not_consolidated_without_identity(self) -> None:
        a = _row(content_hash=HASH_A, rfc_message_id="<a@example.test>", body="hello family")
        b = _row(content_hash=HASH_B, rfc_message_id="<b@example.test>", body="hello family")
        out = consolidate_messages([a, b])
        self.assertEqual(len(out["displayed"]), 2)
        self.assertEqual(out["duplicates"], [])
        self.assertEqual(out["unexplained"], 0)

    def test_same_hash_two_sources_one_displayed(self) -> None:
        src_a, src_b = str(uuid4()), str(uuid4())
        a = _row(source_id=src_a, content_hash=HASH_A, rfc_message_id="<same@example.test>")
        b = _row(source_id=src_b, content_hash=HASH_A, rfc_message_id="<same@example.test>")
        out = consolidate_messages([a, b])
        self.assertEqual(len(out["displayed"]), 1)
        self.assertEqual(len(out["duplicates"]), 1)
        self.assertEqual(
            out["duplicates"][0]["consolidation_class"],
            "same_communication_multiple_extracts",
        )
        self.assertEqual(out["unexplained"], 0)

    def test_same_rfc_different_hash_one_displayed(self) -> None:
        a = _row(content_hash=HASH_A, rfc_message_id="<same@example.test>")
        b = _row(content_hash=HASH_B, rfc_message_id="<same@example.test>")
        out = consolidate_messages([a, b])
        self.assertEqual(len(out["displayed"]), 1)
        self.assertEqual(len(out["duplicates"]), 1)
        self.assertEqual(
            out["duplicates"][0]["consolidation_class"],
            "same_communication_multiple_extracts",
        )
        self.assertEqual(out["duplicates"][0]["duplicate_of"], out["displayed"][0]["evidence_id"])
        self.assertEqual(out["unexplained"], 0)

    def test_refuse_flightsim_dsn(self) -> None:
        with self.assertRaises(ProductionDSNError):
            refuse_live_dsn("postgresql://memorybox:memorybox@flightsim:5432/i14_035")
        with self.assertRaises(ProductionDSNError):
            refuse_live_dsn("postgresql://x@127.0.0.1/app", "memorybox")
        refuse_live_dsn("postgresql://postgres@127.0.0.1:5432/i14_035", "i14_035")
