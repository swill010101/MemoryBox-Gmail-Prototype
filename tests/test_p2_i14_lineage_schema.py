"""P2-I14 Phase B step 1 static and helper tests. No production database."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from memorybox.ingest import comms_lineage as lineage
from memorybox.migrate import _migration_files

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "memorybox" / "migrations"
SQL_PATH = MIGRATIONS / "035_p2_i14_communications_lineage.sql"
FORBIDDEN = re.compile(
    r"(memorybox@|@gmail\.|@marvinbot|PRIVATEEMAIL|"
    r"P:\\photos|C:\\MemoryBox|\\\\media-server|"
    r"all mail including spam|"
    r"password=|oauth|Bearer )",
    re.I,
)


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


class MigrationOrdering(unittest.TestCase):
    def test_035_follows_accepted_034_ledger(self) -> None:
        names = [p.name for p in _migration_files(MIGRATIONS)]
        self.assertIn("034_historian_capture_hc2_tick.sql", names)
        self.assertIn("035_p2_i14_communications_lineage.sql", names)
        self.assertLess(
            names.index("034_historian_capture_hc2_tick.sql"),
            names.index("035_p2_i14_communications_lineage.sql"),
        )
        self.assertEqual(names[-1], "035_p2_i14_communications_lineage.sql")

    def test_does_not_reuse_025_through_029_filenames(self) -> None:
        names = {p.name for p in _migration_files(MIGRATIONS)}
        self.assertNotIn("025_trusted_retrieval_identity.sql", names)
        self.assertTrue((MIGRATIONS / "025_historian_capture_i12.sql").is_file())


class AdditiveSqlContract(unittest.TestCase):
    def test_additive_and_does_not_touch_prior_migrations(self) -> None:
        sql = _sql()
        self.assertNotRegex(sql, r"(?i)alter table evidence\b")
        self.assertNotRegex(sql, r"(?i)drop table evidence\b")
        self.assertNotRegex(sql, r"(?i)update\s+evidence\b")
        self.assertNotRegex(sql, r"(?i)delete from evidence\b")
        self.assertNotIn("CREATE TABLE person_contact_points", sql)
        self.assertNotIn("CREATE TABLE communication_rfc_ids", sql)
        self.assertIn("retrieval_trust", sql)
        self.assertIn("communication_rfc_ids", sql)

    def test_integrity_clauses(self) -> None:
        sql = _sql()
        self.assertIn("UNIQUE (source_kind, logical_key)", sql)
        self.assertIn("UNIQUE (evidence_id)", sql)
        self.assertIn("REFERENCES evidence (id) ON DELETE RESTRICT", sql)
        self.assertIn("evidence_id                 UUID NOT NULL", sql)
        self.assertIn("UNIQUE (logical_source_id, identity_method, record_key)", sql)
        self.assertIn("REFERENCES sources (id) ON DELETE RESTRICT", sql)
        self.assertIn("idx_comms_extract_instances_source", sql)
        self.assertNotIn("UNIQUE (source_id)", sql)
        self.assertIn("comms_source_memberships", sql)
        self.assertIn("FOREIGN KEY (source_id, logical_source_id)", sql)
        self.assertNotIn("ON DELETE SET NULL", sql)
        self.assertIn("UNIQUE (logical_source_id, fingerprint)", sql)
        self.assertIn("FOREIGN KEY (logical_source_id, current_extract_instance_id)", sql)
        self.assertIn("FOREIGN KEY (logical_source_id, first_extract_instance_id)", sql)
        self.assertIn("FOREIGN KEY (canonical_record_id, logical_source_id)", sql)
        self.assertIn("landing_alias", sql)
        self.assertIn("landing_basename", sql)
        self.assertNotIn("comms_prepared_generation", sql)

    def test_rollback_order_documented(self) -> None:
        comment = _sql().split("CREATE TABLE", 1)[0]
        self.assertLess(
            comment.find("comms_record_identity_aliases"),
            comment.find("comms_record_identities"),
        )
        self.assertLess(
            comment.find("comms_source_checkpoint"),
            comment.find("comms_extract_instances"),
        )
        self.assertLess(
            comment.find("comms_extract_instances"),
            comment.find("comms_source_memberships"),
        )
        self.assertLess(
            comment.find("comms_source_memberships"),
            comment.find("comms_logical_sources"),
        )

    def test_no_private_material_in_migration_sql(self) -> None:
        sql = _sql()
        self.assertIsNone(FORBIDDEN.search(sql))
        helper = (ROOT / "memorybox" / "ingest" / "comms_lineage.py").read_text(
            encoding="utf-8"
        )
        self.assertIsNone(FORBIDDEN.search(helper))
        self.assertNotIn("class LineageStore", helper)


class IdentityRules(unittest.TestCase):
    def test_email_prefers_rfc_then_vendor_then_full_hash(self) -> None:
        method, key, klass = lineage.email_record_identity(
            rfc_message_id="<A.B@Host.Example>",
            vendor_message_id="gm-1",
            body="ignored-when-rfc-present",
        )
        self.assertEqual(method, lineage.EMAIL_RFC)
        self.assertTrue(key.startswith("rfc:<a.b@host.example>"))
        self.assertEqual(klass, "rfc_message_id")
        aliases = lineage.email_identity_aliases(
            rfc_message_id="<A.B@Host.Example>",
            vendor_message_id="gm-1",
            body="complete",
        )
        methods = [a[0] for a in aliases]
        self.assertEqual(
            methods,
            [lineage.EMAIL_RFC, lineage.EMAIL_VENDOR, lineage.EMAIL_FULL],
        )

    def test_email_full_hash_uses_complete_body_not_truncation(self) -> None:
        long_body = "Z" * 5000
        _, key_full, _ = lineage.email_record_identity(body=long_body)
        _, key_prefix, _ = lineage.email_record_identity(body=long_body[:2000])
        self.assertNotEqual(key_full, key_prefix)

    def test_email_never_subject_only(self) -> None:
        a = lineage.email_record_identity(body="same", date_header="1")
        b = lineage.email_record_identity(body="same", date_header="2")
        self.assertNotEqual(a[1], b[1])

    def test_calendar_uid_recurrence_then_dtstart_then_full(self) -> None:
        m, k, _c = lineage.calendar_record_identity(
            uid="evt-1", recurrence_id="2020-01-01", dtstart="other"
        )
        self.assertEqual(m, lineage.CAL_UID_RID)
        aliases = lineage.calendar_identity_aliases(
            uid="evt-1", recurrence_id="2020-01-01", dtstart="other"
        )
        self.assertEqual(aliases[0][0], lineage.CAL_UID_RID)
        self.assertEqual(aliases[-1][0], lineage.CAL_FULL)
        m, k, _c = lineage.calendar_record_identity(
            uid="evt-1", dtstart="2020-01-02T00:00:00+00:00"
        )
        self.assertEqual(m, lineage.CAL_UID_START)
        m, k, _c = lineage.calendar_record_identity(summary="untitled")
        self.assertEqual(m, lineage.CAL_FULL)

    def test_sms_ignores_row_index_fallback_ids(self) -> None:
        fake = "thread|2020-01-01|hello|12"
        m, _k, _c = lineage.sms_record_identity(
            provider_message_id=fake,
            source_row=12,
            participants=["p1"],
            direction="in",
            sent_at="2020-01-01",
            body="hello",
        )
        self.assertEqual(m, lineage.SMS_NORM)
        genuine = lineage.sms_record_identity(provider_message_id="GUID-ABC")
        self.assertEqual(genuine[0], lineage.SMS_PROVIDER)
        self.assertEqual(len(lineage.sms_identity_aliases(provider_message_id="GUID-ABC")), 2)


if __name__ == "__main__":
    unittest.main()
