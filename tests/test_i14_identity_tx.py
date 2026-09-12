"""Disposable proofs for I14 identity transactions. Never uses dbname memorybox."""
from __future__ import annotations

import hashlib
import json
import threading
import unittest
import psycopg
from psycopg.rows import dict_row

from memorybox.ops import i14_identity_tx as ident
from tests.test_p2_i14_lineage_pg import SQL_001, SQL_035, _DisposablePg, _apply_file

HASH = "ab" * 32
HASH_B = "cd" * 32
RFC = "rfc:<one@example.test>"
FP1 = hashlib.sha256(b"extract-1").hexdigest()
FP2 = hashlib.sha256(b"extract-2").hexdigest()


class IdentityTxPg(_DisposablePg):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if cls.boot_error or not cls.dsn:
            return
        with psycopg.connect(cls.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            if conn.execute("SELECT current_database() AS d").fetchone()["d"].lower() == "memorybox":
                cls.boot_error = "refused_memorybox_on_fixture_dsn"
                return
            _apply_file(conn, SQL_001)
            _apply_file(conn, SQL_035)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS communication_rfc_ids (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  evidence_id UUID NOT NULL,
                  role TEXT NOT NULL,
                  rfc_message_id TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _conn(self):
        self._require_dsn()
        return psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5)

    def _reset(self, conn) -> None:
        conn.execute(
            """
            TRUNCATE
              comms_record_identity_aliases,
              comms_record_identities,
              comms_source_checkpoint,
              comms_extract_instances,
              comms_source_memberships,
              comms_logical_sources,
              communication_rfc_ids,
              evidence,
              sources
            CASCADE
            """
        )
        conn.commit()

    def _source(self, conn, uri: str, kind: str = "mbox_import"):
        return conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES (%s, %s, %s, 'referenced') RETURNING id
            """,
            (kind, uri, uri),
        ).fetchone()["id"]

    def _stream(self, conn, source_id, key="household_email"):
        lid = ident.ensure_logical_source(
            conn, source_kind="email", logical_key=key, label="Household email"
        )
        self.assertEqual(ident.ensure_membership(conn, source_id=source_id, logical_source_id=lid), "ok")
        return lid

    def _extract(self, conn, lid, source_id, fp=FP1, alias="household_email", base="mail.mbox"):
        status, eid = ident.register_extract(
            conn,
            logical_source_id=lid,
            source_id=source_id,
            fingerprint=fp,
            landing_alias=alias,
            landing_basename=base,
        )
        return status, eid

    def test_refuses_memorybox_name(self) -> None:
        class Fake:
            autocommit = False

            def execute(self, sql, params=None):
                class R:
                    def fetchone(self_inner):
                        return {"d": "memorybox"}

                return R()

        with self.assertRaises(ident.IdentityError) as ctx:
            ident.ensure_logical_source(Fake(), source_kind="email", logical_key="household_email", label="x")
        self.assertEqual(ctx.exception.code, "refused_memorybox_dbname")

    def test_new_insert_then_reuse_adds_missing_alias(self) -> None:
        with self._conn() as conn:
            self._reset(conn)
            s1 = self._source(conn, "synthetic:/a.mbox")
            s2 = self._source(conn, "synthetic:/b.mbox")
            lid = self._stream(conn, s1)
            self.assertEqual(ident.ensure_membership(conn, source_id=s2, logical_source_id=lid), "ok")
            st, ext = self._extract(conn, lid, s1)
            self.assertEqual(st, "new_extract")
            aliases = [("email_rfc_message_id", RFC), ("email_full_sha256", HASH)]
            r1 = ident.apply_record(
                conn,
                logical_source_id=lid,
                extract_instance_id=ext,
                source_id=s1,
                source_kind="email",
                evidence_kind="communication",
                content_hash=HASH,
                aliases=aliases[:1],
                stream_source_ids=[s1, s2],
                rfc_own="<one@example.test>",
            )
            self.assertEqual(r1.code, ident.OUT_INSERTED)
            r2 = ident.apply_record(
                conn,
                logical_source_id=lid,
                extract_instance_id=ext,
                source_id=s2,
                source_kind="email",
                evidence_kind="communication",
                content_hash=HASH,
                aliases=aliases,
                stream_source_ids=[s1, s2],
            )
            self.assertEqual(r2.code, ident.OUT_REUSED)
            self.assertEqual(r2.evidence_id, r1.evidence_id)
            n_ev = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            n_id = conn.execute("SELECT COUNT(*) AS n FROM comms_record_identities").fetchone()["n"]
            n_al = conn.execute("SELECT COUNT(*) AS n FROM comms_record_identity_aliases").fetchone()["n"]
            self.assertEqual(int(n_ev), 1)
            self.assertEqual(int(n_id), 1)
            self.assertEqual(int(n_al), 2)
            conn.commit()

    def test_alias_conflict_two_canonicals_rolls_back(self) -> None:
        with self._conn() as conn:
            self._reset(conn)
            s1 = self._source(conn, "synthetic:/c.mbox")
            lid = self._stream(conn, s1, key="household_email")
            _, ext = self._extract(conn, lid, s1, fp=hashlib.sha256(b"c").hexdigest())
            a = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                source_kind="email", evidence_kind="communication", content_hash=HASH,
                aliases=[("email_rfc_message_id", RFC)], stream_source_ids=[s1],
            )
            b = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                source_kind="email", evidence_kind="communication", content_hash=HASH_B,
                aliases=[("email_full_sha256", HASH_B)], stream_source_ids=[s1],
            )
            self.assertEqual(a.code, ident.OUT_INSERTED)
            self.assertEqual(b.code, ident.OUT_INSERTED)
            before = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            r = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                source_kind="email", evidence_kind="communication", content_hash="ee" * 32,
                aliases=[("email_rfc_message_id", RFC), ("email_full_sha256", HASH_B)],
                stream_source_ids=[s1],
            )
            self.assertEqual(r.code, ident.OUT_ALIAS_CONFLICT)
            after = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(int(before), int(after))
            conn.commit()

    def test_historical_one_and_two_and_none(self) -> None:
        with self._conn() as conn:
            self._reset(conn)
            s1 = self._source(conn, "synthetic:/e1.mbox")
            s2 = self._source(conn, "synthetic:/e2.mbox")
            lid = self._stream(conn, s1, key="household_email")
            ident.ensure_membership(conn, source_id=s2, logical_source_id=lid)
            _, ext = self._extract(conn, lid, s1, fp=hashlib.sha256(b"e").hexdigest())
            conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'hist', %s::jsonb)
                """,
                (s1, json.dumps({"content_hash": HASH})),
            )
            one = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s2,
                source_kind="email", evidence_kind="communication", content_hash=HASH,
                aliases=[("email_full_sha256", HASH)], stream_source_ids=[s1, s2],
            )
            self.assertEqual(one.code, ident.OUT_ELIGIBLE_BACKFILL)
            self.assertEqual(
                int(conn.execute("SELECT COUNT(*) AS n FROM comms_record_identities").fetchone()["n"]),
                0,
            )
            conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'hist2', %s::jsonb)
                """,
                (s2, json.dumps({"content_hash": HASH})),
            )
            two = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s2,
                source_kind="email", evidence_kind="communication", content_hash=HASH,
                aliases=[("email_full_sha256", HASH)], stream_source_ids=[s1, s2],
            )
            self.assertEqual(two.code, ident.OUT_NEEDS_POLICY)
            fresh = ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                source_kind="email", evidence_kind="communication", content_hash=HASH_B,
                aliases=[("email_full_sha256", HASH_B)], stream_source_ids=[s1, s2],
            )
            self.assertEqual(fresh.code, ident.OUT_INSERTED)
            conn.commit()

    def test_checked_unchanged_and_cross_stream_isolation(self) -> None:
        with self._conn() as conn:
            self._reset(conn)
            s1 = self._source(conn, "synthetic:/f.mbox")
            s_sms = self._source(conn, "synthetic:/f.csv", kind="sms_export")
            lid = self._stream(conn, s1, key="household_email")
            sms = ident.ensure_logical_source(
                conn, source_kind="sms", logical_key="household_sms", label="Household SMS"
            )
            ident.ensure_membership(conn, source_id=s_sms, logical_source_id=sms)
            st1, ext = self._extract(conn, lid, s1, fp=FP2)
            self.assertEqual(st1, "new_extract")
            st2, ext2 = self._extract(conn, lid, s1, fp=FP2)
            self.assertEqual(st2, ident.OUT_CHECKED_UNCHANGED)
            self.assertEqual(ext, ext2)
            other = ident.ensure_membership(conn, source_id=s1, logical_source_id=sms)
            self.assertEqual(other, ident.OUT_MEMBERSHIP_CONFLICT)
            _, ext_sms = ident.register_extract(
                conn, logical_source_id=sms, source_id=s_sms, fingerprint=hashlib.sha256(b"sms").hexdigest(),
                landing_alias="household_sms", landing_basename="sms.csv",
            )
            ident.apply_record(
                conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                source_kind="email", evidence_kind="communication", content_hash=HASH,
                aliases=[("email_full_sha256", HASH)], stream_source_ids=[s1],
            )
            r = ident.apply_record(
                conn, logical_source_id=sms, extract_instance_id=ext_sms, source_id=s_sms,
                source_kind="sms", evidence_kind="communication", content_hash=HASH,
                aliases=[("sms_normalized_sha256", HASH)], stream_source_ids=[s_sms],
            )
            self.assertEqual(r.code, ident.OUT_INSERTED)
            n = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(int(n), 2)
            conn.commit()

    def test_concurrent_workers_one_evidence(self) -> None:
        with self._conn() as setup:
            self._reset(setup)
            s1 = self._source(setup, "synthetic:/g.mbox")
            lid = self._stream(setup, s1, key="household_email")
            _, ext = self._extract(setup, lid, s1, fp=hashlib.sha256(b"g").hexdigest())
            setup.commit()
        barrier = threading.Barrier(2)
        results: list[str] = []

        def worker() -> None:
            with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
                barrier.wait(timeout=10)
                r = ident.apply_record(
                    conn, logical_source_id=lid, extract_instance_id=ext, source_id=s1,
                    source_kind="email", evidence_kind="communication", content_hash=HASH,
                    aliases=[("email_full_sha256", HASH), ("email_rfc_message_id", RFC)],
                    stream_source_ids=[s1],
                )
                conn.commit()
                results.append(r.code)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=20)
        t2.join(timeout=20)
        self.assertEqual(len(results), 2)
        self.assertEqual(results.count(ident.OUT_INSERTED), 1)
        self.assertTrue(all(c in (ident.OUT_INSERTED, ident.OUT_REUSED) for c in results))
        with self._conn() as conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(int(n), 1)


if __name__ == "__main__":
    unittest.main()
