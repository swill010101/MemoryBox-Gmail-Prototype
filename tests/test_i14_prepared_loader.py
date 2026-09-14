"""Disposable PostgreSQL proofs for the household-email prepared loader."""
from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import AuditError, run_audit
from memorybox.ops.i14_prepared_loader import (
    LoaderError,
    read_source_messages,
    run_load,
)
from memorybox.ops.i14_thread_review import IdentityLedger, add_confirmed_address
from tests.test_p2_i14_036_schema import SQL_036
from tests.test_p2_i14_lineage_pg import SQL_001, SQL_035, _DisposablePg, _apply_file

SQL_037 = Path(__file__).resolve().parents[1] / "memorybox" / "migrations" / "037_p2_i14_prepared_evidence_ref_scale.sql"

RFC_SQL = """
CREATE TABLE IF NOT EXISTS communication_rfc_ids (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evidence_id UUID NOT NULL,
  role TEXT NOT NULL,
  rfc_message_id TEXT NOT NULL
)
"""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _payload(**kwargs) -> dict:
    body = kwargs.pop("body_text", "Hello from the household.")
    sent = kwargs.pop("sent_at", "2011-09-29T15:01:58+00:00")
    frm = kwargs.pop("from_addr", "peggy@example.test")
    to = kwargs.pop("to_addr", "tom@example.test")
    subject = kwargs.pop("subject", "RE: Stuff")
    rfc = kwargs.pop("rfc", "<msg-1@example.test>")
    digest = kwargs.pop("content_hash", _hash(rfc + body))
    atts = kwargs.pop("attachments", [])
    extra = kwargs
    payload = {
        "rfc_message_id": rfc,
        "content_hash": digest,
        "sent_at": sent,
        "subject": subject,
        "body_text": body,
        "from": frm,
        "to": to,
        "cc": extra.get("cc", ""),
        "from_parsed": [{"address": frm, "normalized": frm, "display_name": "Peggy"}],
        "to_parsed": [{"address": to, "normalized": to, "display_name": "Tom"}],
        "in_reply_to_ids": extra.get("in_reply_to_ids") or [],
        "attachments": atts,
        "mailbox_skip": extra.get("mailbox_skip") or "",
        "source_locator": extra.get("source_locator") or "synthetic-msg",
    }
    return payload


class PreparedLoaderPg(_DisposablePg):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if cls.boot_error or not cls.dsn:
            return
        with psycopg.connect(cls.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            if str(db).lower() == "memorybox":
                cls.boot_error = "refused_memorybox_on_fixture_dsn"
                return
            _apply_file(conn, SQL_001)
            conn.execute(RFC_SQL)
            conn.commit()
            _apply_file(conn, SQL_035)
            conn.commit()
            _apply_file(conn, SQL_036)
            conn.commit()
            _apply_file(conn, SQL_037)
            conn.commit()

    def _wipe(self, conn) -> None:
        conn.execute(
            """
            TRUNCATE comms_prepared_attachments, comms_prepared_participants,
                     comms_prepared_messages, comms_prepared_threads,
                     comms_prepared_generations, comms_record_identity_aliases,
                     comms_record_identities, comms_source_checkpoint,
                     comms_extract_instances, comms_source_memberships,
                     comms_logical_sources, communication_rfc_ids,
                     evidence, sources, people RESTART IDENTITY CASCADE
            """
        )
        conn.commit()

    def _source(self, conn, uri: str = "synthetic:mbox-a"):
        return conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES ('mbox_import', 'synthetic-a', %s, 'referenced')
            RETURNING id
            """,
            (uri,),
        ).fetchone()["id"]

    def _evidence(self, conn, source_id, payload: dict, summary: str = "synthetic"):
        return conn.execute(
            """
            INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
            VALUES ('communication', %s, %s, %s::jsonb)
            RETURNING id
            """,
            (source_id, summary, json.dumps(payload)),
        ).fetchone()["id"]

    def _ledger(self, conn, focal_name: str = "Peggy Example"):
        focal = conn.execute(
            "INSERT INTO people (display_name, status) VALUES (%s, 'confirmed') RETURNING id",
            (focal_name,),
        ).fetchone()["id"]
        other = conn.execute(
            "INSERT INTO people (display_name, status) VALUES ('Tom Example', 'confirmed') RETURNING id"
        ).fetchone()["id"]
        ledger = IdentityLedger(focal_person_id=str(focal))
        add_confirmed_address(
            ledger, address="peggy@example.test", person_id=str(focal), label=focal_name
        )
        add_confirmed_address(
            ledger, address="tom@example.test", person_id=str(other), label="Tom Example"
        )
        return ledger, focal, other

    def test_refuses_flightsim(self) -> None:
        with self.assertRaises(ProductionDSNError):
            refuse_live_dsn("postgresql://memorybox:x@flightsim:5432/memorybox")

    def test_loader_contracts_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src_a = self._source(conn, "synthetic:mbox-a")
            src_b = self._source(conn, "synthetic:mbox-b")
            ledger, focal, _other = self._ledger(conn)
            prior = "Dad's financial status is holding up fine.\nGo Cards!"
            reply = (
                "I know you're doing an outstanding job with all.\n\n"
                "Date: Thu, 29 Sep 2011 10:01:58 -0500\n"
                "Subject: Stuff\n"
                "From: tom@example.test\n"
                "To: peggy@example.test\n\n"
                + prior
            )
            p1 = _payload(
                rfc="<t1@example.test>",
                from_addr="tom@example.test",
                to_addr="peggy@example.test",
                body_text=prior,
                sent_at="2011-09-29T15:01:58+00:00",
            )
            p2 = _payload(
                rfc="<t2@example.test>",
                from_addr="peggy@example.test",
                to_addr="tom@example.test",
                body_text=reply,
                sent_at="2011-09-29T16:10:00+00:00",
                in_reply_to_ids=["<t1@example.test>"],
            )
            p_dup = dict(p1)
            p_fwd = _payload(
                rfc="<fwd@example.test>",
                subject="FW: itinerary",
                body_text=(
                    "See below.\n\nBegin forwarded message:\n\n"
                    "Your flight confirmation AA 1234 is attached.\n"
                    "https://tracking.example.test/unsub"
                ),
                sent_at="2011-09-30T12:00:00+00:00",
                attachments=[{"filename": "pass.pdf", "mime_type": "application/pdf", "byte_size": 12}],
            )
            p_unknown = _payload(
                rfc="<unk@example.test>",
                from_addr="stranger@example.test",
                to_addr="peggy@example.test",
                body_text="Can you call me later?",
                sent_at="2011-10-01T12:00:00+00:00",
            )
            p_unknown["from_parsed"] = [
                {"address": "stranger@example.test", "normalized": "stranger@example.test", "display_name": "?"}
            ]
            p_spam = _payload(rfc="<spam@example.test>", mailbox_skip="spam")
            p_similar = _payload(
                rfc="<similar@example.test>",
                body_text=prior,
                sent_at="2011-10-02T12:00:00+00:00",
            )
            e1 = self._evidence(conn, src_a, p1)
            e1b = self._evidence(conn, src_b, p_dup)
            e2 = self._evidence(conn, src_a, p2)
            e3 = self._evidence(conn, src_a, p_fwd)
            e4 = self._evidence(conn, src_a, p_unknown)
            e5 = self._evidence(conn, src_a, p_spam)
            e6 = self._evidence(conn, src_a, p_similar)
            conn.execute(
                "INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id) VALUES (%s,'own',%s)",
                (e1, "<t1@example.test>"),
            )
            conn.execute(
                "INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id) VALUES (%s,'own',%s)",
                (e1b, "<t1@example.test>"),
            )
            conn.commit()
            before = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            messages = read_source_messages(conn, [src_a, src_b])
            started = time.monotonic()
            result = run_load(conn, messages, ledger, dsn=self.dsn)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self.assertTrue(result["ok"])
            self.assertFalse(result["published"])
            self.assertFalse(result["is_active"])
            self.assertFalse(result["activation_called"])
            self.assertEqual(result["unexplained"], 0)
            self.assertGreaterEqual(result["duplicates"], 1)
            self.assertGreaterEqual(result["excluded"], 1)
            after = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            self.assertEqual(dict(before), dict(after))
            gid = result["generation_id"]
            n_msg = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
                (gid,),
            ).fetchone()["n"]
            self.assertEqual(n_msg, result["messages"])
            uniq = conn.execute(
                """
                SELECT COUNT(*) AS n, COUNT(DISTINCT evidence_id) AS u
                  FROM comms_prepared_messages WHERE generation_id = %s
                """,
                (gid,),
            ).fetchone()
            self.assertEqual(uniq["n"], uniq["u"])
            missing_canon = conn.execute(
                """
                SELECT COUNT(*) AS n FROM comms_prepared_messages
                 WHERE generation_id = %s AND canonical_record_id IS NULL
                """,
                (gid,),
            ).fetchone()["n"]
            self.assertEqual(missing_canon, 0)
            from_n = conn.execute(
                """
                SELECT m.id
                  FROM comms_prepared_messages m
                  JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
                 WHERE m.generation_id = %s
                 GROUP BY m.id
                HAVING COUNT(*) <> 1
                """,
                (gid,),
            ).fetchall()
            self.assertEqual(from_n, [])
            unknown = conn.execute(
                """
                SELECT identity_confidence, person_id
                  FROM comms_prepared_participants
                 WHERE lower(address_normalized) = 'stranger@example.test'
                """
            ).fetchone()
            self.assertEqual(unknown["identity_confidence"], "unverified")
            self.assertIsNone(unknown["person_id"])
            voice_to = conn.execute(
                """
                SELECT COUNT(*) AS n
                  FROM comms_prepared_participants p
                  JOIN comms_prepared_messages m ON m.id = p.message_id
                 WHERE p.role IN ('to','cc') AND m.voice_corpus
                   AND p.identity_confidence = 'authenticated_focal'
                """
            ).fetchone()["n"]
            self.assertEqual(voice_to, 0)
            authored = conn.execute(
                """
                SELECT cleaned_authored_text, urls_stripped, commercial_class, forward_status
                  FROM comms_prepared_messages
                 WHERE evidence_id = %s
                """,
                (e2,),
            ).fetchone()
            self.assertNotIn("financial status", (authored["cleaned_authored_text"] or "").lower())
            self.assertNotIn("http://", authored["cleaned_authored_text"])
            fwd = conn.execute(
                "SELECT cleaned_authored_text, forward_block FROM comms_prepared_messages WHERE evidence_id = %s",
                (e3,),
            ).fetchone()
            self.assertNotRegex(fwd["cleaned_authored_text"] + fwd["forward_block"], r"https?://")
            att = conn.execute(
                """
                SELECT parent_evidence_id, gallery_action, COUNT(*) AS n
                  FROM comms_prepared_attachments a
                  JOIN comms_prepared_messages m ON m.id = a.message_id
                 WHERE m.evidence_id = %s
                 GROUP BY 1, 2
                """,
                (e3,),
            ).fetchone()
            self.assertEqual(att["parent_evidence_id"], e3)
            self.assertEqual(att["gallery_action"], "open_pdf")
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_prepared_active_generations"
            ).fetchone()["n"]
            self.assertEqual(active, 0)
            survivors = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE evidence_id IN (%s, %s, %s)",
                (e1, e1b, e6),
            ).fetchone()["n"]
            self.assertEqual(survivors, 2)
            order = conn.execute(
                """
                SELECT sent_at, evidence_id FROM comms_prepared_messages
                 WHERE generation_id = %s
                 ORDER BY sent_at, evidence_id
                """,
                (gid,),
            ).fetchall()
            self.assertEqual(order, sorted(order, key=lambda r: (r["sent_at"], str(r["evidence_id"]))))
            again = run_load(conn, messages, ledger, dsn=self.dsn)
            self.assertTrue(again["reused"])
            gens = conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_generations").fetchone()["n"]
            self.assertEqual(gens, 1)
            with self.assertRaises(LoaderError):
                run_load(conn, messages, ledger, dsn=self.dsn, fail_after="after_generation")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_generations").fetchone()["n"],
                1,
            )
            self.assertLess(elapsed_ms, 15000)
            result["elapsed_ms"] = elapsed_ms
            self._rehearsal = result

    def test_failed_load_leaves_no_partial_generation(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            payload = _payload()
            self._evidence(conn, src, payload)
            conn.commit()
            messages = read_source_messages(conn, [src])
            with self.assertRaises(LoaderError):
                run_load(conn, messages, ledger, dsn=self.dsn, fail_after="after_generation")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_generations").fetchone()["n"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_messages").fetchone()["n"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_active_generations").fetchone()["n"],
                0,
            )

    def test_persist_batches_marks_failed_generation(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            self._evidence(conn, src, _payload())
            conn.commit()
            messages = read_source_messages(conn, [src])
            with self.assertRaises(LoaderError):
                run_load(
                    conn,
                    messages,
                    ledger,
                    dsn=self.dsn,
                    persist_batches=True,
                    fail_after="after_generation",
                )
            row = conn.execute(
                "SELECT status, published, is_active FROM comms_prepared_generations"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "failed")
            self.assertFalse(row["published"])
            self.assertFalse(row["is_active"])
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_messages").fetchone()["n"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_active_generations").fetchone()["n"],
                0,
            )

    def test_loaded_review_packet_is_bounded(self) -> None:
        self._require_dsn()
        from memorybox.ops.i14_prepared_load_prod import write_loaded_review_packet

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            self._evidence(conn, src, _payload())
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            with tempfile.TemporaryDirectory() as tmp:
                meta = write_loaded_review_packet(conn, loaded["generation_id"], Path(tmp))
                self.assertLessEqual(meta["thread_count_written"], 12)
                self.assertTrue((Path(tmp) / "INDEX.txt").is_file())
                self.assertTrue((Path(tmp) / "packet-001.txt").is_file())

    def test_audit_and_loader_scale_budget(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            n = 400
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY evidence (evidence_kind, source_id, summary, payload_json) FROM STDIN"
                ) as copy:
                    for i in range(n):
                        rfc = f"<scale-{i}@example.test>"
                        body = f"Scale note {i}"
                        if i % 40 == 0:
                            body = "Your receipt and unsubscribe options are below."
                        payload = json.dumps(
                            _payload(
                                rfc=rfc,
                                body_text=body,
                                sent_at=f"2012-01-01T00:00:{i % 50:02d}+00:00",
                                content_hash=_hash(rfc),
                            )
                        )
                        copy.write_row(("communication", src, "scale", payload))
            conn.commit()
            started = time.monotonic()
            audit = run_audit(conn, batch_size=200, statement_timeout="15s", run_deadline_s=60)
            conn.rollback()
            audit_s = time.monotonic() - started
            self.assertTrue(audit["ok"])
            self.assertIn("consolidation", audit)
            self.assertLess(audit_s, 60)
            messages = read_source_messages(conn, [src])
            started = time.monotonic()
            loaded = run_load(conn, messages, ledger, dsn=self.dsn)
            load_s = time.monotonic() - started
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["unexplained"], 0)
            self.assertLess(load_s, 30)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM comms_prepared_active_generations").fetchone()["n"],
                0,
            )

    def test_household_voice_is_authenticated_from_not_focal_person(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            peggy = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Peggy Example', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            sue = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Sue Example', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            tom = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Tom Example', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            ledger = IdentityLedger(focal_person_id=str(peggy))
            add_confirmed_address(ledger, address="peggy@example.test", person_id=str(peggy), label="Peggy Example")
            add_confirmed_address(ledger, address="sue@example.test", person_id=str(sue), label="Sue Example")
            add_confirmed_address(ledger, address="tom@example.test", person_id=str(tom), label="Tom Example")
            p_peggy = _payload(
                rfc="<p-voice@example.test>", from_addr="peggy@example.test", to_addr="tom@example.test",
                body_text="Peggy authored a clean picnic note.", sent_at="2014-01-01T12:00:00+00:00", content_hash=_hash("p-voice"),
            )
            p_sue = _payload(
                rfc="<s-voice@example.test>", from_addr="sue@example.test", to_addr="peggy@example.test",
                body_text="Sue authored a clean school pickup note.", sent_at="2014-01-01T13:00:00+00:00", content_hash=_hash("s-voice"),
            )
            p_sue["from_parsed"] = [{"address": "sue@example.test", "normalized": "sue@example.test", "display_name": "Sue"}]
            p_sue["to_parsed"] = [{"address": "peggy@example.test", "normalized": "peggy@example.test", "display_name": "Peggy"}]
            p_tom = _payload(
                rfc="<t-voice@example.test>", from_addr="tom@example.test", to_addr="sue@example.test",
                body_text="Tom authored a clean hardware-store note.", sent_at="2014-01-01T14:00:00+00:00", content_hash=_hash("t-voice"),
            )
            p_to_only = _payload(
                rfc="<to-only@example.test>", from_addr="stranger@example.test", to_addr="peggy@example.test",
                body_text="Please call me about the picnic.", sent_at="2014-01-01T15:00:00+00:00",
                content_hash=_hash("to-only"),
            )
            p_to_only["from_parsed"] = [{"address": "stranger@example.test", "normalized": "stranger@example.test", "display_name": "?"}]
            p_dirty = _payload(
                rfc="<dirty@example.test>", from_addr="sue@example.test", to_addr="tom@example.test",
                subject="RE: dirty quote",
                body_text=(
                    "Ok.\n\n"
                    "Date: Thu, 29 Sep 2011 10:01:58 -0500\n"
                    "Subject: Stuff\n"
                    "From: tom@example.test\n"
                    "To: sue@example.test\n\n"
                    "quoted history"
                ),
                sent_at="2014-01-01T16:00:00+00:00",
                content_hash=_hash("dirty"),
            )
            p_dirty["from_parsed"] = [{"address": "sue@example.test", "normalized": "sue@example.test", "display_name": "Sue"}]
            self._evidence(conn, src, p_peggy)
            self._evidence(conn, src, p_sue)
            self._evidence(conn, src, p_tom)
            self._evidence(conn, src, p_to_only)
            self._evidence(conn, src, p_dirty)
            conn.commit()
            messages = read_source_messages(conn, [src])
            loaded = run_load(conn, messages, ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["messages"], 5)
            voice_by_person = conn.execute(
                """
                SELECT p.person_id, COUNT(*)::int AS n
                  FROM comms_prepared_messages m
                  JOIN comms_prepared_participants p
                    ON p.message_id = m.id AND p.role = 'from'
                 WHERE m.voice_corpus
                 GROUP BY p.person_id
                """
            ).fetchall()
            counts = {str(r["person_id"]): int(r["n"]) for r in voice_by_person}
            self.assertEqual(counts.get(str(peggy)), 1)
            self.assertEqual(counts.get(str(sue)), 1)
            self.assertEqual(counts.get(str(tom)), 1)
            self.assertEqual(sum(counts.values()), 3)
            to_cc_voice = conn.execute(
                """
                SELECT COUNT(*) AS n
                  FROM comms_prepared_participants p
                  JOIN comms_prepared_messages m ON m.id = p.message_id
                 WHERE p.role IN ('to','cc') AND m.voice_corpus
                   AND p.identity_confidence = 'authenticated_focal'
                """
            ).fetchone()["n"]
            self.assertEqual(to_cc_voice, 0)
            stranger = conn.execute(
                """
                SELECT m.voice_corpus, p.identity_confidence, p.person_id
                  FROM comms_prepared_messages m
                  JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
                 WHERE lower(p.address_normalized) = 'stranger@example.test'
                """
            ).fetchone()
            self.assertFalse(stranger["voice_corpus"])
            self.assertEqual(stranger["identity_confidence"], "unverified")
            self.assertIsNone(stranger["person_id"])
            dirty = conn.execute(
                """
                SELECT m.voice_corpus, m.quote_quality
                  FROM comms_prepared_messages m
                 WHERE m.subject = 'RE: dirty quote'
                """
            ).fetchone()
            self.assertIsNotNone(dirty)
            self.assertFalse(dirty["voice_corpus"])
            other_focal = IdentityLedger(focal_person_id=str(sue))
            add_confirmed_address(other_focal, address="peggy@example.test", person_id=str(peggy), label="Peggy Example")
            add_confirmed_address(other_focal, address="sue@example.test", person_id=str(sue), label="Sue Example")
            add_confirmed_address(other_focal, address="tom@example.test", person_id=str(tom), label="Tom Example")
            conn.execute("DELETE FROM comms_prepared_generations")
            conn.commit()
            again = run_load(conn, messages, other_focal, dsn=self.dsn)
            self.assertTrue(again["ok"])
            voice_again = {
                str(r["person_id"]): int(r["n"])
                for r in conn.execute(
                    """
                    SELECT p.person_id, COUNT(*)::int AS n
                      FROM comms_prepared_messages m
                      JOIN comms_prepared_participants p
                        ON p.message_id = m.id AND p.role = 'from'
                     WHERE m.voice_corpus
                     GROUP BY p.person_id
                    """
                ).fetchall()
            }
            self.assertEqual(voice_again.get(str(peggy)), 1)
            self.assertEqual(voice_again.get(str(sue)), 1)
            self.assertEqual(voice_again.get(str(tom)), 1)

    def test_long_thread_scales_evidence_ref_past_99(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            prev = None
            for i in range(1, 106):
                rfc = f"<long-{i}@example.test>"
                payload = _payload(
                    rfc=rfc,
                    body_text=f"Authored line {i} unique.",
                    sent_at=f"2013-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
                    content_hash=_hash(rfc),
                    in_reply_to_ids=[prev] if prev else [],
                )
                self._evidence(conn, src, payload)
                prev = rfc
            conn.commit()
            messages = read_source_messages(conn, [src])
            loaded = run_load(conn, messages, ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["messages"], 105)
            self.assertEqual(loaded["threads"], 1)
            refs = [
                r["evidence_ref"]
                for r in conn.execute(
                    """
                    SELECT evidence_ref, ordinal
                      FROM comms_prepared_messages
                     ORDER BY ordinal
                    """
                ).fetchall()
            ]
            self.assertEqual(refs[0], "T-0001-M-01")
            self.assertEqual(refs[98], "T-0001-M-99")
            self.assertEqual(refs[99], "T-0001-M-100")
            self.assertEqual(refs[-1], "T-0001-M-105")
            ev_n = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(ev_n, 105)


if __name__ == "__main__":
    unittest.main()
