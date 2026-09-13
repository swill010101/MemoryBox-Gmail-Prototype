"""Static contract tests for candidate 036 proposed SQL. No production database."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from memorybox.migrate import _migration_files

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "memorybox" / "migrations"
PROPOSED = ROOT / "docs" / "prd" / "p2-i14" / "036_p2_i14_prepared_communications.proposed.sql"
FORBIDDEN = re.compile(
    r"(memorybox@|@gmail\.|@marvinbot|PRIVATEEMAIL|"
    r"P:\\photos|C:\\MemoryBox|\\\\media-server|"
    r"all mail including spam|"
    r"password=|oauth|Bearer |http)",
    re.I,
)


def _sql() -> str:
    return PROPOSED.read_text(encoding="utf-8")


class ProposedFilePlacement(unittest.TestCase):
    def test_not_registered_as_migration(self) -> None:
        names = [p.name for p in _migration_files(MIGRATIONS)]
        self.assertTrue(PROPOSED.is_file())
        self.assertNotIn("036_p2_i14_prepared_communications.sql", names)
        self.assertEqual(names[-1], "035_p2_i14_communications_lineage.sql")
        self.assertTrue(_sql().lstrip().startswith("-- P2-I14 Phase B candidate 036"))


class AdditiveSqlContract(unittest.TestCase):
    def test_additive_and_does_not_touch_evidence(self) -> None:
        sql = _sql()
        self.assertNotRegex(sql, r"(?i)alter table evidence\b")
        self.assertNotRegex(sql, r"(?i)drop table evidence\b")
        self.assertNotRegex(sql, r"(?i)\binsert\s+into\b")
        self.assertNotRegex(sql, r"(?i)update\s+evidence\b")
        self.assertNotIn("CREATE TABLE person_contact_points", sql)
        self.assertNotIn("CREATE TABLE communication_rfc_ids", sql)
        self.assertNotIn("CREATE TABLE comms_prepared_calendar", sql)

    def test_integrity_clauses(self) -> None:
        sql = _sql()
        self.assertIn("CREATE TABLE IF NOT EXISTS comms_prepared_generations", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS comms_prepared_threads", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS comms_prepared_messages", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS comms_prepared_participants", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS comms_prepared_attachments", sql)
        self.assertIn("REFERENCES evidence (id) ON DELETE RESTRICT", sql)
        self.assertIn("UNIQUE (generation_id, evidence_id)", sql)
        self.assertIn("UNIQUE (thread_id, ordinal)", sql)
        self.assertIn("published           BOOLEAN NOT NULL DEFAULT FALSE", sql)
        self.assertIn("source_kind         TEXT NOT NULL", sql)
        self.assertIn("CHECK (source_kind IN ('email'))", sql)
        self.assertIn("commercial_suppress", sql)
        self.assertIn("duplicate_of_thread_message", sql)
        self.assertIn("commercial_body_omitted", sql)
        self.assertNotIn("ON DELETE SET NULL", sql)
        self.assertIn("REFERENCES people (id) ON DELETE RESTRICT", sql)

    def test_rollback_order_documented(self) -> None:
        comment = _sql().split("CREATE TABLE", 1)[0]
        self.assertLess(
            comment.find("comms_prepared_attachments"),
            comment.find("comms_prepared_participants"),
        )
        self.assertLess(
            comment.find("comms_prepared_participants"),
            comment.find("comms_prepared_messages"),
        )
        self.assertLess(
            comment.find("comms_prepared_messages"),
            comment.find("comms_prepared_threads"),
        )
        self.assertLess(
            comment.find("comms_prepared_threads"),
            comment.find("comms_prepared_generations"),
        )

    def test_no_private_material(self) -> None:
        self.assertIsNone(FORBIDDEN.search(_sql()))


if __name__ == "__main__":
    unittest.main()
