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
SQL_038 = Path(__file__).resolve().parents[1] / "memorybox" / "migrations" / "038_p2_i14_voice_without_recipient_identity.sql"
SQL_039 = Path(__file__).resolve().parents[1] / "memorybox" / "migrations" / "039_p2_i14_voice_requires_prepared_text.sql"
SQL_040 = (
    Path(__file__).resolve().parents[1]
    / "memorybox"
    / "migrations"
    / "040_p2_i14_voice_requires_displayable_authored.sql"
)
SQL_040_PROPOSED = SQL_040

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
            _apply_file(conn, SQL_038)
            conn.commit()
            _apply_file(conn, SQL_039)
            conn.commit()
            _apply_file(conn, SQL_040_PROPOSED)
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
            p_tom_open = _payload(
                rfc="<t-open@example.test>", from_addr="tom@example.test", to_addr="stranger@example.test",
                body_text="Tom authored a clean note to an unknown recipient uniquely.",
                sent_at="2014-01-01T14:30:00+00:00", content_hash=_hash("t-open"),
            )
            p_tom_open["from_parsed"] = [{"address": "tom@example.test", "normalized": "tom@example.test", "display_name": "Tom"}]
            p_tom_open["to_parsed"] = [{"address": "stranger@example.test", "normalized": "stranger@example.test", "display_name": "Stranger"}]
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
            self._evidence(conn, src, p_tom_open)
            self._evidence(conn, src, p_to_only)
            self._evidence(conn, src, p_dirty)
            conn.commit()
            messages = read_source_messages(conn, [src])
            loaded = run_load(conn, messages, ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["messages"], 6)
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
            self.assertEqual(counts.get(str(tom)), 2)
            self.assertEqual(sum(counts.values()), 4)
            tom_open = conn.execute(
                """
                SELECT m.voice_corpus, m.identity_quality
                  FROM comms_prepared_messages m
                 WHERE m.subject = 'RE: Stuff' AND m.cleaned_authored_text LIKE '%unknown recipient%'
                """
            ).fetchone()
            self.assertIsNotNone(tom_open)
            self.assertTrue(tom_open["voice_corpus"])
            self.assertEqual(tom_open["identity_quality"], "uncertain")
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
            self.assertEqual(voice_again.get(str(tom)), 2)

    def test_glued_hotmail_peggy_reply_keeps_authored_sentence_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            peggy = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Peggy Example', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            tom = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Tom Example', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            ledger = IdentityLedger(focal_person_id=str(peggy))
            add_confirmed_address(ledger, address="peggy@example.test", person_id=str(peggy), label="Peggy Example")
            add_confirmed_address(ledger, address="tom@example.test", person_id=str(tom), label="Tom Example")
            tom_line = "A bit too long, but funny all the same...... those crazy Japanese!"
            glue = (
                "Date: Tue, 23 Dec 2008 17:10:47 -0600"
                "From: tom@example.test"
                "To: peggy@example.test"
                "Subject: Crazy Japanese!"
            )
            p_tom = _payload(
                rfc="<glue-tom@example.test>",
                from_addr="tom@example.test",
                to_addr="peggy@example.test",
                subject="Crazy Japanese!",
                body_text=tom_line + " Have a great day!Tom",
                sent_at="2008-12-23T23:10:47+00:00",
                content_hash=_hash("glue-tom"),
            )
            p_tom["from_parsed"] = [{"address": "tom@example.test", "normalized": "tom@example.test", "display_name": "Tom"}]
            p_tom["to_parsed"] = [{"address": "peggy@example.test", "normalized": "peggy@example.test", "display_name": "Peggy"}]
            peggy_text = (
                "LOL....cough, cough!!  That chimp had to be the funniest.  "
                "He tries to stick finger to get a taste.  Matt in the pie??  LMAO"
            )
            p_peggy = _payload(
                rfc="<glue-peg@example.test>",
                from_addr="peggy@example.test",
                to_addr="tom@example.test",
                subject="RE: Crazy Japanese!",
                body_text=peggy_text + "\n\n" + glue + tom_line + " Have a great day!Tom\n",
                sent_at="2008-12-24T00:10:47+00:00",
                content_hash=_hash("glue-peg"),
                in_reply_to_ids=["<glue-tom@example.test>"],
            )
            p_peggy["from_parsed"] = [{"address": "peggy@example.test", "normalized": "peggy@example.test", "display_name": "Peggy"}]
            p_peggy["to_parsed"] = [{"address": "tom@example.test", "normalized": "tom@example.test", "display_name": "Tom"}]
            self._evidence(conn, src, p_tom)
            self._evidence(conn, src, p_peggy)
            conn.commit()
            messages = read_source_messages(conn, [src])
            loaded = run_load(conn, messages, ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            row = conn.execute(
                """
                SELECT m.cleaned_authored_text, m.voice_corpus, m.quote_quality, m.evidence_id
                  FROM comms_prepared_messages m
                  JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
                 WHERE p.person_id = %s
                """,
                (peggy,),
            ).fetchone()
            self.assertIn("Matt in the pie", row["cleaned_authored_text"])
            self.assertNotIn("A bit too long", row["cleaned_authored_text"])
            self.assertNotIn("Date: Tue", row["cleaned_authored_text"])
            self.assertEqual(row["quote_quality"], "clean")
            self.assertTrue(row["voice_corpus"])
            still = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(still, 2)

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

    def test_strips_http_substring_for_prepared_check(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            payload = _payload(
                rfc="<url-check@example.test>",
                body_text='Click href="http://most.example.test/plan" today.',
                content_hash=_hash("url-check"),
            )
            self._evidence(conn, src, payload)
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            row = conn.execute(
                "SELECT cleaned_authored_text, urls_stripped FROM comms_prepared_messages"
            ).fetchone()
            self.assertNotRegex(row["cleaned_authored_text"], r"(?i)https?://")
            self.assertTrue(row["urls_stripped"])

    def test_html_only_body_recovers_authored_text_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, focal, _ = self._ledger(conn)
            html_only = _payload(
                rfc="<html-only@example.test>",
                body_text="",
                content_hash=_hash("html-only"),
            )
            html_only["body_text"] = ""
            html_only["body_html"] = (
                "<html><head><style>p{color:red}</style><script>alert(1)</script></head>"
                "<body><p>Thank you for telling us about the reunion.</p>"
                "<img src='https://track.example.test/pixel.gif' width='1' height='1'>"
                "</body></html>"
            )
            plain_keep = _payload(
                rfc="<plain-keep@example.test>",
                body_text="This plain sentence must be kept even when HTML exists.",
                content_hash=_hash("plain-keep"),
                sent_at="2011-09-29T16:00:00+00:00",
            )
            plain_keep["body_html"] = "<p>Different HTML that must not replace the plain text.</p>"
            att_only = _payload(
                rfc="<att-only@example.test>",
                body_text="",
                content_hash=_hash("att-only"),
                sent_at="2011-09-29T17:00:00+00:00",
                attachments=[{"filename": "scan.pdf", "mime_type": "application/pdf", "byte_size": 20}],
            )
            att_only["body_text"] = ""
            self._evidence(conn, src, html_only)
            self._evidence(conn, src, plain_keep)
            self._evidence(conn, src, att_only)
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            rows = {
                r["subject"] if False else r["cleaned_authored_text"]: r
                for r in conn.execute(
                    """
                    SELECT cleaned_authored_text, voice_corpus, evidence_id
                      FROM comms_prepared_messages
                     ORDER BY sent_at
                    """
                ).fetchall()
            }
            texts = [
                r["cleaned_authored_text"]
                for r in conn.execute(
                    "SELECT cleaned_authored_text, voice_corpus FROM comms_prepared_messages ORDER BY sent_at"
                ).fetchall()
            ]
            voices = [
                r["voice_corpus"]
                for r in conn.execute(
                    "SELECT voice_corpus FROM comms_prepared_messages ORDER BY sent_at"
                ).fetchall()
            ]
            self.assertIn("Thank you for telling us about the reunion.", texts[0])
            self.assertNotIn("<p>", texts[0])
            self.assertNotIn("alert", texts[0])
            self.assertTrue(voices[0])
            self.assertIn("This plain sentence must be kept", texts[1])
            self.assertNotIn("Different HTML", texts[1])
            self.assertFalse(bool(str(texts[2] or "").strip()))
            self.assertFalse(voices[2])

    def test_proposed_039_blocks_blank_voice_without_rewriting_rows(self) -> None:
        self._require_dsn()
        sql_039 = SQL_039
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, _ = self._ledger(conn)
            payload = _payload(rfc="<blank-voice@example.test>", body_text="   ", content_hash=_hash("blank-v"))
            payload["body_text"] = "   "
            self._evidence(conn, src, payload)
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            gid = loaded["generation_id"]
            conn.execute(
                """
                UPDATE comms_prepared_messages
                   SET voice_corpus = TRUE,
                       quote_quality = 'clean',
                       authorship = 'authenticated_focal'
                 WHERE generation_id = %s
                """,
                (gid,),
            )
            conn.commit()
            conn.execute(sql_039.read_text(encoding="utf-8"))
            conn.commit()
            try:
                conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (gid,))
                self.fail("expected voice_requires_nonblank_prepared_text")
            except psycopg.Error as exc:
                self.assertIn("voice_requires_nonblank_prepared_text", str(exc))
            conn.rollback()
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
                (gid,),
            ).fetchone()["n"]
            self.assertEqual(n, 1)
            conn.execute(SQL_040_PROPOSED.read_text(encoding="utf-8"))
            conn.commit()

    def test_founder_short_text_load_and_proposed_040(self) -> None:
        self._require_dsn()
        from memorybox.ops.i14_prepared_load_prod import count_loaded_dispositions

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, other = self._ledger(conn)
            add_confirmed_address(
                ledger, address="sue@example.test", person_id=str(other), label="Sue Will"
            )
            cases = (
                ("<thanks@example.test>", "Thanks", "sue@example.test", "Thanks"),
                ("<why@example.test>", "??????", "sue@example.test", "??????"),
                ("<ok@example.test>", "Ok", "sue@example.test", "Ok"),
                ("<emoji@example.test>", "👍🎉🙌🏖", "sue@example.test", "👍🎉🙌🏖"),
                ("<ed@example.test>", "Ed,", "tom@example.test", ""),
                (
                    "<frag@example.test>",
                    "A a ml\n\n________________________________",
                    "tom@example.test",
                    "",
                ),
                ("<line@example.test>", "________________________________", "tom@example.test", ""),
            )
            for i, (rfc, body, frm, _want) in enumerate(cases):
                payload = _payload(
                    rfc=rfc,
                    body_text=body,
                    from_addr=frm,
                    to_addr="peggy@example.test",
                    sent_at=f"2018-03-15T17:16:{i:02d}+00:00",
                    content_hash=_hash(rfc + body),
                )
                payload["from_parsed"] = [
                    {
                        "address": frm,
                        "normalized": frm,
                        "display_name": "Sue" if frm.startswith("sue") else "Tom",
                    }
                ]
                self._evidence(conn, src, payload, summary=rfc)
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            gid = loaded["generation_id"]
            stored = list(
                conn.execute(
                    """
                    SELECT cleaned_authored_text, voice_corpus, prepared_text_disposition
                      FROM comms_prepared_messages
                     ORDER BY sent_at
                    """
                ).fetchall()
            )
            self.assertEqual(stored[0]["cleaned_authored_text"], "Thanks")
            self.assertTrue(stored[0]["voice_corpus"])
            self.assertEqual(stored[0]["prepared_text_disposition"], "authored_displayable")
            self.assertEqual(stored[1]["cleaned_authored_text"], "??????")
            self.assertTrue(stored[1]["voice_corpus"])
            self.assertEqual(stored[1]["prepared_text_disposition"], "authored_displayable")
            self.assertEqual(stored[2]["cleaned_authored_text"], "Ok")
            self.assertTrue(stored[2]["voice_corpus"])
            self.assertEqual(stored[3]["cleaned_authored_text"], "👍🎉🙌🏖")
            self.assertTrue(stored[3]["voice_corpus"])
            self.assertEqual(stored[4]["prepared_text_disposition"], "non_substantive")
            self.assertFalse(stored[4]["voice_corpus"])
            self.assertEqual(stored[5]["prepared_text_disposition"], "non_substantive")
            self.assertFalse(stored[5]["voice_corpus"])
            self.assertEqual(stored[6]["prepared_text_disposition"], "non_substantive")
            self.assertFalse(stored[6]["voice_corpus"])
            gallery = conn.execute(
                """
                SELECT prepared_text_disposition, COUNT(*)::int AS n
                  FROM comms_prepared_messages
                 WHERE generation_id = %s
                 GROUP BY prepared_text_disposition
                 ORDER BY prepared_text_disposition
                """,
                (gid,),
            ).fetchall()
            by_disp = {r["prepared_text_disposition"]: r["n"] for r in gallery}
            self.assertEqual(by_disp.get("authored_displayable"), 4)
            self.assertEqual(by_disp.get("non_substantive"), 3)
            self.assertEqual(
                int(
                    conn.execute(
                        """
                        SELECT COUNT(*)::int AS n FROM comms_prepared_messages
                         WHERE generation_id = %s AND voice_corpus
                           AND prepared_text_disposition <> 'authored_displayable'
                        """,
                        (gid,),
                    ).fetchone()["n"]
                ),
                0,
            )
            counts = count_loaded_dispositions(conn, gid)
            self.assertEqual(counts["blank_voice"], 0)
            self.assertEqual(counts["forbidden_disposition_and_voice"], 0)
            self.assertEqual(counts["authored_displayable"], 4)
            self.assertEqual(counts["non_substantive"], 3)
            before = conn.execute(
                """
                SELECT id, cleaned_authored_text, voice_corpus, prepared_text_disposition
                  FROM comms_prepared_messages
                 WHERE generation_id = %s
                   AND prepared_text_disposition = 'non_substantive'
                 ORDER BY sent_at LIMIT 1
                """,
                (gid,),
            ).fetchone()
            conn.execute(
                """
                UPDATE comms_prepared_messages
                   SET voice_corpus = TRUE,
                       quote_quality = 'clean',
                       authorship = 'authenticated_focal',
                       cleaned_authored_text = 'Ed,'
                 WHERE id = %s
                """,
                (before["id"],),
            )
            try:
                conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (gid,))
                self.fail("expected voice_requires_authored_displayable_disposition")
            except psycopg.Error as exc:
                self.assertIn("voice_requires_authored_displayable_disposition", str(exc))
            conn.rollback()
            after = conn.execute(
                """
                SELECT cleaned_authored_text, prepared_text_disposition
                  FROM comms_prepared_messages WHERE id = %s
                """,
                (before["id"],),
            ).fetchone()
            self.assertEqual(after["cleaned_authored_text"], before["cleaned_authored_text"])
            self.assertEqual(after["prepared_text_disposition"], "non_substantive")
            conn.execute(
                """
                UPDATE comms_prepared_messages
                   SET voice_corpus = FALSE
                 WHERE id = %s
                """,
                (before["id"],),
            )
            conn.commit()
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (gid,))

    def test_html_only_short_replies_recover_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, _, other = self._ledger(conn)
            add_confirmed_address(
                ledger, address="sue@example.test", person_id=str(other), label="Sue Will"
            )
            html_cases = (
                ("Thanks", "<thanks-html@example.test>"),
                ("Yes", "<yes-html@example.test>"),
                ("Ok", "<ok-html@example.test>"),
                ("Love you", "<love-html@example.test>"),
                ("Call me", "<call-html@example.test>"),
                ("Amen", "<amen-html@example.test>"),
                ("??????", "<why-html@example.test>"),
                ("👍🎉🙌🏖", "<emoji-html@example.test>"),
                ("Tom", "<tom-html@example.test>"),
            )
            for i, (text, rfc) in enumerate(html_cases):
                payload = _payload(
                    rfc=rfc,
                    body_text="",
                    from_addr="sue@example.test",
                    to_addr="peggy@example.test",
                    sent_at=f"2019-01-01T12:00:{i:02d}+00:00",
                    content_hash=_hash(rfc + text),
                )
                payload["body_html"] = (
                    f"<html><head><style>.x{{display:none}}</style></head>"
                    f"<body><p>{text}</p><script>alert(1)</script>"
                    f"<a href='https://ads.example.test/u'></a></body></html>"
                )
                payload["from_parsed"] = [
                    {"address": "sue@example.test", "normalized": "sue@example.test", "display_name": "Sue"}
                ]
                self._evidence(conn, src, payload, summary=rfc)
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            rows = conn.execute(
                """
                SELECT cleaned_authored_text, voice_corpus, prepared_text_disposition
                  FROM comms_prepared_messages
                 ORDER BY sent_at
                """
            ).fetchall()
            self.assertEqual(len(rows), 9)
            for i, (text, _rfc) in enumerate(html_cases):
                self.assertEqual(rows[i]["cleaned_authored_text"], text)
                self.assertEqual(rows[i]["prepared_text_disposition"], "authored_displayable")
                self.assertTrue(rows[i]["voice_corpus"])
                self.assertNotIn("<", rows[i]["cleaned_authored_text"])
                self.assertNotIn("alert", rows[i]["cleaned_authored_text"])
                self.assertNotIn("http", rows[i]["cleaned_authored_text"].lower())

    def _activatable_generation(
        self,
        conn,
        *,
        src,
        person_id,
        algo: str,
        rfc: str,
        cleaned: str,
        voice: bool,
        disposition: str | None,
        display_id: str,
        quote: str = "clean",
        authorship: str = "authenticated_focal",
    ):
        ev = self._evidence(
            conn,
            src,
            _payload(rfc=rfc, body_text=cleaned or " ", content_hash=_hash(rfc)),
            summary=rfc,
        )
        log = conn.execute(
            """
            INSERT INTO comms_logical_sources (logical_key, source_kind, label)
            VALUES ('household_email', 'email', 'Household email')
            ON CONFLICT (source_kind, logical_key) DO UPDATE SET label = EXCLUDED.label
            RETURNING id
            """
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO comms_source_memberships (source_id, logical_source_id)
            VALUES (%s, %s) ON CONFLICT (source_id) DO NOTHING
            """,
            (src, log),
        )
        extract = conn.execute(
            """
            INSERT INTO comms_extract_instances (
              logical_source_id, source_id, fingerprint, landing_alias, landing_basename,
              validation_status, ingest_status
            ) VALUES (%s, %s, %s, 'household_email', 'synthetic.mbox', 'valid', 'ingested')
            RETURNING id
            """,
            (log, src, _hash(algo + rfc)),
        ).fetchone()["id"]
        canonical = conn.execute(
            """
            INSERT INTO comms_record_identities (
              logical_source_id, evidence_id, source_kind, first_extract_instance_id
            ) VALUES (%s, %s, 'email', %s)
            RETURNING id
            """,
            (log, ev, extract),
        ).fetchone()["id"]
        gen = conn.execute(
            """
            INSERT INTO comms_prepared_generations (
              algo_version, logical_source_id, status, checksum
            ) VALUES (%s, %s, 'validated', %s)
            RETURNING id
            """,
            (algo, log, _hash("ck" + rfc + algo)),
        ).fetchone()["id"]
        thread_id = conn.execute(
            """
            INSERT INTO comms_prepared_threads (
              generation_id, thread_key, display_id, threading_confidence,
              identity_confidence, gallery_eligibility, founder_review_state,
              earliest_at, latest_at, message_count, evidence_count
            ) VALUES (
              %s, %s, %s, 'rfc', 'all_authenticated', 'show_by_default', 'unreviewed',
              '2011-09-29T15:00:00+00:00', '2011-09-29T15:00:00+00:00', 1, 1
            )
            RETURNING id
            """,
            (gen, "rfc:" + rfc, display_id),
        ).fetchone()["id"]
        cols = (
            "thread_id, generation_id, ordinal, evidence_id, canonical_record_id, "
            "evidence_ref, sent_at, cleaned_authored_text, authorship, voice_corpus, "
            "quote_quality, commercial_class, direction"
        )
        vals = (
            "%s, %s, 1, %s, %s, %s, '2011-09-29T15:00:00+00:00', %s, %s, %s, %s, "
            "'not_commercial', 'unresolved'"
        )
        params: list = [
            thread_id,
            gen,
            ev,
            canonical,
            display_id + "-M-01",
            cleaned,
            authorship,
            voice,
            quote,
        ]
        if disposition is not None:
            cols += ", prepared_text_disposition"
            vals += ", %s"
            params.append(disposition)
        mid = conn.execute(
            f"INSERT INTO comms_prepared_messages ({cols}) VALUES ({vals}) RETURNING id",
            tuple(params),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO comms_prepared_participants (
              message_id, role, display_name, address_normalized, identity_confidence, person_id
            ) VALUES (%s, 'from', 'Peggy Example', 'peggy@example.test', 'authenticated_focal', %s)
            """,
            (mid, person_id),
        )
        conn.commit()
        return gen

    def test_legacy_v1_v3_activation_rollback_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            _, focal, _ = self._ledger(conn)
            v1 = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v1",
                rfc="<v1-blank@example.test>",
                cleaned="",
                voice=True,
                disposition=None,
                display_id="T-7001",
            )
            disp = conn.execute(
                "SELECT prepared_text_disposition FROM comms_prepared_messages WHERE generation_id = %s",
                (v1,),
            ).fetchone()["prepared_text_disposition"]
            self.assertIsNone(disp)
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v1,))
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (v1,))
            conn.commit()
            active = conn.execute(
                "SELECT id, algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()
            self.assertEqual(active["id"], v1)
            self.assertEqual(active["algo_version"], "i14-prepared-email-v1")

            v2_blank = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v2",
                rfc="<v2-blank@example.test>",
                cleaned="",
                voice=True,
                disposition=None,
                display_id="T-7002",
            )
            try:
                conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v2_blank,))
                self.fail("v2 must refuse blank voice")
            except psycopg.Error as exc:
                self.assertIn("voice_requires_nonblank_prepared_text", str(exc))
            conn.rollback()

            v3_bad = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v3",
                rfc="<v3-null@example.test>",
                cleaned="Thanks",
                voice=True,
                disposition=None,
                display_id="T-7003",
            )
            try:
                conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v3_bad,))
                self.fail("v3 must require six-way disposition")
            except psycopg.Error as exc:
                self.assertIn("v3_requires_prepared_text_disposition", str(exc))
            conn.rollback()

            v3_junk = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v3",
                rfc="<v3-junk@example.test>",
                cleaned="Ed,",
                voice=True,
                disposition="non_substantive",
                display_id="T-7004",
            )
            try:
                conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v3_junk,))
                self.fail("v3 must refuse non_substantive voice")
            except psycopg.Error as exc:
                self.assertIn("voice_requires_authored_displayable_disposition", str(exc))
            conn.rollback()

            v3 = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v3",
                rfc="<v3-ok@example.test>",
                cleaned="Thanks",
                voice=True,
                disposition="authored_displayable",
                display_id="T-7005",
            )
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v3,))
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (v3,))
            conn.commit()
            active = conn.execute(
                "SELECT id, algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()
            self.assertEqual(active["id"], v3)
            self.assertEqual(active["algo_version"], "i14-prepared-email-v3")
            v1_state = conn.execute(
                "SELECT is_active, status FROM comms_prepared_generations WHERE id = %s",
                (v1,),
            ).fetchone()
            self.assertFalse(v1_state["is_active"])
            self.assertEqual(v1_state["status"], "superseded")

            conn.execute(
                """
                UPDATE comms_prepared_generations
                SET status = 'validated'
                WHERE id = %s
                """,
                (v1,),
            )
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v1,))
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (v1,))
            conn.commit()
            active = conn.execute(
                "SELECT id, algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()
            self.assertEqual(active["id"], v1)
            self.assertEqual(active["algo_version"], "i14-prepared-email-v1")
            v3_state = conn.execute(
                "SELECT is_active FROM comms_prepared_generations WHERE id = %s",
                (v3,),
            ).fetchone()
            self.assertFalse(v3_state["is_active"])

    def test_unpublished_v3_does_not_mutate_v1_or_v2_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            self._wipe(conn)
            src = self._source(conn)
            ledger, focal, _ = self._ledger(conn)
            v1 = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v1",
                rfc="<keep-v1@example.test>",
                cleaned="Thanks",
                voice=True,
                disposition=None,
                display_id="T-8001",
            )
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (v1,))
            conn.commit()
            v2 = self._activatable_generation(
                conn,
                src=src,
                person_id=focal,
                algo="i14-prepared-email-v2",
                rfc="<keep-v2@example.test>",
                cleaned="Thanks",
                voice=True,
                disposition=None,
                display_id="T-8002",
            )
            v2_before = conn.execute(
                """
                SELECT status, published, is_active, checksum,
                       (SELECT COUNT(*)::int FROM comms_prepared_messages
                         WHERE generation_id = %s) AS n
                  FROM comms_prepared_generations WHERE id = %s
                """,
                (v2, v2),
            ).fetchone()
            src3 = self._source(conn, uri="synthetic:mbox-v3")
            payload = _payload(
                rfc="<v3-keep@example.test>",
                body_text="Thanks",
                content_hash=_hash("v3-keep"),
            )
            self._evidence(conn, src3, payload, summary="v3")
            conn.commit()
            loaded = run_load(conn, read_source_messages(conn, [src3]), ledger, dsn=self.dsn)
            self.assertTrue(loaded["ok"])
            v3 = loaded["generation_id"]
            self.assertEqual(loaded["algo_version"], "i14-prepared-email-v3")
            self.assertNotEqual(v3, v1)
            self.assertNotEqual(v3, v2)
            active = conn.execute(
                "SELECT id, algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()
            self.assertEqual(active["id"], v1)
            self.assertEqual(active["algo_version"], "i14-prepared-email-v1")
            v2_after = conn.execute(
                """
                SELECT status, published, is_active, checksum,
                       (SELECT COUNT(*)::int FROM comms_prepared_messages
                         WHERE generation_id = %s) AS n
                  FROM comms_prepared_generations WHERE id = %s
                """,
                (v2, v2),
            ).fetchone()
            self.assertEqual(v2_after["status"], v2_before["status"])
            self.assertEqual(v2_after["published"], v2_before["published"])
            self.assertEqual(v2_after["is_active"], v2_before["is_active"])
            self.assertEqual(v2_after["checksum"], v2_before["checksum"])
            self.assertEqual(v2_after["n"], v2_before["n"])
            v3_row = conn.execute(
                """
                SELECT status, published, is_active, algo_version, prepared_text_disposition
                  FROM comms_prepared_generations g
                  JOIN comms_prepared_messages m ON m.generation_id = g.id
                 WHERE g.id = %s
                """,
                (v3,),
            ).fetchone()
            self.assertEqual(v3_row["status"], "validated")
            self.assertFalse(v3_row["published"])
            self.assertFalse(v3_row["is_active"])
            self.assertEqual(v3_row["algo_version"], "i14-prepared-email-v3")
            self.assertEqual(v3_row["prepared_text_disposition"], "authored_displayable")
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v1,))
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v2,))
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v3,))


if __name__ == "__main__":
    unittest.main()
