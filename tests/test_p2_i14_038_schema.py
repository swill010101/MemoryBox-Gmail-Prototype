"""Static checks for migration 038 voice CHECK. Never dbname memorybox."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_038 = ROOT / "memorybox" / "migrations" / "038_p2_i14_voice_without_recipient_identity.sql"


class AdditiveSql038(unittest.TestCase):
    def test_038_only_replaces_voice_check(self) -> None:
        sql = SQL_038.read_text(encoding="utf-8")
        self.assertIn("comms_prepared_messages_voice_corpus_ck", sql)
        self.assertIn("quote_quality = 'clean'", sql)
        self.assertIn("authorship = 'authenticated_focal'", sql)
        self.assertNotIn("identity_quality = 'resolved'", sql)
        self.assertNotRegex(sql, r"(?i)\binsert\s+into\b")
        self.assertNotRegex(sql, r"(?i)drop table\b")
        self.assertNotRegex(sql, r"(?i)alter table evidence\b")
        self.assertNotIn("CREATE TABLE", sql)
        self.assertNotIn("comms_prepared_activate_generation", sql)
        self.assertNotIn("schema_migrations", sql)


if __name__ == "__main__":
    unittest.main()
