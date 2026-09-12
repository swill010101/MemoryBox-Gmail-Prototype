"""Production-scale disposable rehearsal for the I14 duplicate audit. Never uses dbname memorybox."""
from __future__ import annotations

import hashlib
import json
import time
import unittest

import psycopg
from psycopg.rows import dict_row

from memorybox.ops import i14_duplicate_audit as audit
from tests.test_p2_i14_lineage_pg import SQL_001, _DisposablePg, _apply_file

SCALE_EVIDENCE = 188656
SCALE_SOURCES = 27
SCALE_RFC = 80000
PAD = 1024

SNAP_SQL = """
SELECT
  (SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public') AS public_rels,
  (SELECT COUNT(*) FROM sources) AS sources,
  (SELECT COUNT(*) FROM evidence) AS evidence,
  (SELECT COUNT(*) FROM communication_rfc_ids) AS rfc
"""


def _plan_from_explain(row: dict) -> list:
    val = row.get("QUERY PLAN") or row.get("query plan") or next(iter(row.values()))
    if isinstance(val, str):
        val = json.loads(val)
    return val


class DuplicateAuditScalePg(_DisposablePg):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if cls.boot_error or not cls.dsn:
            return
        with psycopg.connect(cls.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            if str(db).lower() == "memorybox":
                cls.boot_error = "refused_memorybox_on_fixture_dsn"
                return
            _apply_file(conn, SQL_001)
            conn.execute(
                """
                CREATE TABLE communication_rfc_ids (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  evidence_id UUID NOT NULL,
                  role TEXT NOT NULL,
                  rfc_message_id TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def test_keyset_beats_offset_and_audit_finishes_under_deadline(self) -> None:
        self._require_dsn()
        pad = "x" * PAD
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            conn.execute("TRUNCATE communication_rfc_ids, evidence, sources CASCADE")
            src_ids = []
            for i in range(SCALE_SOURCES):
                ext = (".mbox", ".ics", ".csv")[i % 3]
                sid = conn.execute(
                    """
                    INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                    VALUES (%s, %s, %s, 'referenced')
                    RETURNING id
                    """,
                    ("synthetic", f"s{i}", f"synthetic:/scale-{i}{ext}"),
                ).fetchone()["id"]
                src_ids.append(sid)
            conn.commit()
            start_seed = time.monotonic()
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY evidence (evidence_kind, source_id, summary, payload_json) FROM STDIN"
                ) as copy:
                    for i in range(SCALE_EVIDENCE):
                        digest = hashlib.sha256(f"row-{i}".encode()).hexdigest()
                        if i % 80 == 0:
                            digest = hashlib.sha256(b"dup-bucket").hexdigest()
                        payload = json.dumps({"content_hash": digest, "pad": pad})
                        copy.write_row(("communication", src_ids[i % SCALE_SOURCES], "", payload))
            conn.commit()
            ev_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM evidence ORDER BY id LIMIT %s", (SCALE_RFC,)
                ).fetchall()
            ]
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY communication_rfc_ids (evidence_id, role, rfc_message_id) FROM STDIN"
                ) as copy:
                    for i, eid in enumerate(ev_ids):
                        token = f"<tok-{i // 3}@scale.test>"
                        copy.write_row((eid, "own", token))
            conn.commit()
            seed_s = time.monotonic() - start_seed
            n_ev = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            self.assertEqual(int(n_ev), SCALE_EVIDENCE)

            offset_sql = """
                EXPLAIN (FORMAT JSON)
                SELECT lower(btrim(COALESCE(e.payload_json->>'content_hash', '')))
                  FROM evidence e
                 ORDER BY e.id
                 LIMIT 500 OFFSET 150000
                """
            keyset_sql = """
                EXPLAIN (FORMAT JSON)
                SELECT lower(btrim(COALESCE(e.payload_json->>'content_hash', '')))
                  FROM evidence e
                 WHERE e.id > '00000000-0000-0000-0000-000000000000'
                 ORDER BY e.id
                 LIMIT 10000
                """
            offset_plan = _plan_from_explain(conn.execute(offset_sql).fetchone())
            keyset_plan = _plan_from_explain(conn.execute(keyset_sql).fetchone())
            offset_nodes = audit.plan_cost_tree(offset_plan)
            keyset_nodes = audit.plan_cost_tree(keyset_plan)
            self.assertTrue(offset_nodes)
            self.assertTrue(keyset_nodes)
            offset_cost = float(offset_nodes[0]["total_cost"])
            keyset_cost = float(keyset_nodes[0]["total_cost"])
            self.assertGreater(offset_cost, keyset_cost)

            before = dict(conn.execute(SNAP_SQL).fetchone())
            conn.commit()
            started = time.monotonic()
            report = audit.run_audit(
                conn,
                batch_size=10000,
                statement_timeout="30s",
                run_deadline_s=180,
            )
            elapsed_s = time.monotonic() - started
            conn.rollback()
            after = dict(conn.execute(SNAP_SQL).fetchone())
            conn.commit()
            self.assertEqual(before, after)
            self.assertTrue(report["ok"])
            self.assertEqual(report["loaded_rows"], SCALE_EVIDENCE)
            self.assertLess(elapsed_s, 180)
            audit.assert_counts_only(report)
            print(
                json.dumps(
                    {
                        "seed_s": round(seed_s, 2),
                        "audit_s": round(elapsed_s, 2),
                        "audit_elapsed_ms": report["elapsed_ms"],
                        "offset_cost": offset_cost,
                        "keyset_cost": keyset_cost,
                        "offset_nodes": offset_nodes[:6],
                        "keyset_nodes": keyset_nodes[:6],
                        "loaded_rows": report["loaded_rows"],
                        "missing_hash": report["missing_hash"],
                        "invalid_hash": report["invalid_hash"],
                        "within": report["within_source_duplicates"],
                        "rfc": report["rfc_own_fanout"],
                    },
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
