"""Focused tests for I14 035 FlightSim deploy validation. No production apply."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from memorybox.ops import i14_migration_035 as d035
from memorybox.ops.i14_migration_035 import DeployValidationError

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "ops" / "Deploy-I14Migration035.ps1"
RUNBOOK = ROOT / "docs" / "ops" / "I14_MIGRATION_035_FLIGHTSIM.md"


def _ledger_ok() -> list[dict[str, str]]:
    rows = []
    for i in range(1, 35):
        ver = f"{i:03d}"
        name = d035.FLIGHTSIM_LEDGER_FILENAMES.get(ver, f"{ver}_placeholder.sql")
        rows.append({"version": ver, "filename": name})
    return rows


def _contract_ok() -> dict:
    return {
        "tables": list(d035.COMMS_TABLES),
        "row_counts": {t: 0 for t in d035.COMMS_TABLES},
        "primary_keys": {
            "comms_logical_sources": ["id"],
            "comms_source_memberships": ["source_id"],
            "comms_extract_instances": ["id"],
            "comms_source_checkpoint": ["logical_source_id"],
            "comms_record_identities": ["id"],
            "comms_record_identity_aliases": ["id"],
        },
        "foreign_keys": [
            "FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT",
            "FOREIGN KEY (logical_source_id) REFERENCES comms_logical_sources(id) ON DELETE RESTRICT",
            "FOREIGN KEY (source_id, logical_source_id) REFERENCES comms_source_memberships(source_id, logical_source_id) ON DELETE RESTRICT",
            "FOREIGN KEY (logical_source_id, current_extract_instance_id) REFERENCES comms_extract_instances(logical_source_id, id) ON DELETE RESTRICT",
            "FOREIGN KEY (logical_source_id, first_extract_instance_id) REFERENCES comms_extract_instances(logical_source_id, id) ON DELETE RESTRICT",
            "FOREIGN KEY (canonical_record_id, logical_source_id) REFERENCES comms_record_identities(id, logical_source_id) ON DELETE RESTRICT",
            "FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT",
        ],
        "uniques": [
            "UNIQUE (source_kind, logical_key)",
            "UNIQUE (source_id, logical_source_id)",
            "UNIQUE (logical_source_id, fingerprint)",
            "UNIQUE (logical_source_id, id)",
            "UNIQUE (evidence_id)",
            "UNIQUE (id, logical_source_id)",
            "UNIQUE (logical_source_id, identity_method, record_key)",
        ],
        "uniques_by_table": [
            ("comms_extract_instances", "UNIQUE (logical_source_id, fingerprint)"),
            ("comms_extract_instances", "UNIQUE (logical_source_id, id)"),
        ],
        "checks": [
            "CHECK ((logical_key ~ '^[a-z][a-z0-9_]{1,62}$'))",
            "CHECK ((source_kind IN ('email', 'calendar', 'sms')))",
            "CHECK ((fingerprint ~ '^[a-f0-9]{64}$'))",
            "CHECK ((landing_alias ~ '^[a-z][a-z0-9_]{1,62}$'))",
            "CHECK ((validation_status IN ('pending', 'valid', 'invalid')))",
            "CHECK ((ingest_status IN ('not_started', 'running', 'checked_unchanged', 'ingested', 'failed')))",
            "CHECK ((identity_method IN ('email_rfc_message_id')))",
        ],
        "checkpoint_confdeltype": "r",
        "indexes": {name: False for name in d035.EXPECTED_INDEXES},
        "baseline_counts": {"evidence": 3, "sources": 2, "communication_rfc_ids": 4},
        "after_counts": {"evidence": 3, "sources": 2, "communication_rfc_ids": 4},
    }


class LedgerPreflight(unittest.TestCase):
    def test_requires_ordered_001_through_034_not_count_only(self) -> None:
        report = d035.validate_ledger_preflight(_ledger_ok())
        self.assertEqual(report["filenames_009_025_029"]["025"], "025_trusted_retrieval_identity.sql")
        self.assertEqual(report["filenames_009_025_029"]["009"], "009_person_fact_residence.sql")
        short = _ledger_ok()[:-1]
        with self.assertRaises(DeployValidationError):
            d035.validate_ledger_preflight(short)
        extra = _ledger_ok() + [{"version": "035", "filename": d035.MIGRATION_FILENAME}]
        with self.assertRaises(DeployValidationError):
            d035.validate_ledger_preflight(extra)
        wrong_025 = _ledger_ok()
        wrong_025[24]["filename"] = "025_historian_capture_i12.sql"
        with self.assertRaises(DeployValidationError):
            d035.validate_ledger_preflight(wrong_025)

    def test_pending_only_035_skips_009_and_025_collisions(self) -> None:
        applied = {f"{i:03d}": f"{i:03d}_applied.sql" for i in range(1, 35)}
        applied["009"] = "009_person_fact_residence.sql"
        applied["025"] = "025_trusted_retrieval_identity.sql"
        local = {f"{i:03d}": f"{i:03d}_repo.sql" for i in range(1, 26)}
        local["030"] = "030_p2_i13_scope_admission.sql"
        local["035"] = d035.MIGRATION_FILENAME
        local["009"] = "009_p2_i7a_ai_trace_ensure.sql"
        local["025"] = "025_historian_capture_i12.sql"
        report = d035.pending_from_files(applied, local)
        d035.assert_only_035_pending(report)
        replay = d035.pending_from_files({}, {"025": "025_historian_capture_i12.sql", "035": d035.MIGRATION_FILENAME})
        with self.assertRaises(DeployValidationError):
            d035.assert_only_035_pending(replay)


class MigrateAndHealth(unittest.TestCase):
    def test_migrate_result_scalar(self) -> None:
        d035.assert_migrate_applied({"applied": [d035.MIGRATION_FILENAME]})
        with self.assertRaises(DeployValidationError):
            d035.assert_migrate_applied({"applied": [d035.MIGRATION_FILENAME, "036_x.sql"]})
        with self.assertRaises(DeployValidationError):
            d035.assert_migrate_applied({"applied": []})

    def test_health_poll_succeeds_and_times_out_with_last_failure(self) -> None:
        calls = {"n": 0}

        def ok_later(_url: str) -> dict:
            calls["n"] += 1
            if calls["n"] < 2:
                return {"ok": False, "migrations": {"pending": ["035_x.sql"], "applied": []}}
            return {"ok": True, "migrations": {"pending": [], "applied": [1] * 35}, "database": {"ok": True}}

        slept: list[float] = []
        out = d035.poll_health("http://example/health", timeout_sec=5, interval_sec=0, opener=ok_later, sleeper=slept.append)
        self.assertTrue(out["ok"])
        self.assertEqual(out["health"]["pending"], [])

        def always_bad(_url: str) -> dict:
            return {"ok": False, "migrations": {"pending": ["035"], "applied": []}}

        with self.assertRaises(DeployValidationError) as ctx:
            d035.poll_health(
                "http://example/health",
                timeout_sec=0,
                interval_sec=0,
                opener=always_bad,
                sleeper=lambda _s: None,
            )
        self.assertIn("health_poll_timeout", str(ctx.exception))
        self.assertIn("pending", str(ctx.exception))


class HcAssertions(unittest.TestCase):
    def test_email_requires_namecheap(self) -> None:
        d035.assert_email_status({"ok": True, "provider_key": d035.HC_PROVIDER_KEY, "reason": "live_ok"})
        with self.assertRaises(DeployValidationError):
            d035.assert_email_status({"ok": True, "provider_key": "marvin_historian_gmail"})
        with self.assertRaises(DeployValidationError):
            d035.assert_email_status({"ok": False, "provider_key": d035.HC_PROVIDER_KEY})

    def test_scheduled_services_one_hc_entry(self) -> None:
        base = {
            "ok": True,
            "services": [
                {
                    "id": "historian_capture_email",
                    "kind": "recurring_service",
                    "title": "Historian Capture email",
                    "status": "Active",
                }
            ],
        }
        self.assertFalse(d035.assert_scheduled_services(base)["delayed"])
        delayed = json.loads(json.dumps(base))
        delayed["services"][0]["status"] = "Delayed"
        self.assertTrue(d035.assert_scheduled_services(delayed)["delayed"])
        for bad in ("Error", "Disabled", "Not configured"):
            payload = json.loads(json.dumps(base))
            payload["services"][0]["status"] = bad
            with self.assertRaises(DeployValidationError):
                d035.assert_scheduled_services(payload)
        two = json.loads(json.dumps(base))
        two["services"].append(dict(base["services"][0], id="other"))
        with self.assertRaises(DeployValidationError):
            d035.assert_scheduled_services(two)


class SchemaContract(unittest.TestCase):
    def test_approved_035_contract(self) -> None:
        result = d035.assert_035_contract(_contract_ok())
        self.assertEqual(result["checkpoint_delete"], "RESTRICT")
        self.assertFalse(result["extract_source_id_unique"])

    def test_rejects_unique_source_id_and_set_null(self) -> None:
        snap = _contract_ok()
        snap["uniques_by_table"].append(("comms_extract_instances", "UNIQUE (source_id)"))
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)
        snap = _contract_ok()
        snap["foreign_keys"].append("FOREIGN KEY (x) REFERENCES y(id) ON DELETE SET NULL")
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)
        snap = _contract_ok()
        snap["checkpoint_confdeltype"] = "n"
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)
        snap = _contract_ok()
        snap["row_counts"]["comms_logical_sources"] = 1
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)
        snap = _contract_ok()
        snap["after_counts"]["evidence"] = 99
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)

    def test_indexes_source_id_nonunique(self) -> None:
        snap = _contract_ok()
        snap["indexes"]["idx_comms_extract_instances_source"] = True
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)


class UntrackedAndRollback(unittest.TestCase):
    def test_untracked_collisions(self) -> None:
        hits = d035.untracked_collisions(
            ["docs/ops/I14_MIGRATION_035_FLIGHTSIM.md", "local.tmp"],
            ["docs/ops/I14_MIGRATION_035_FLIGHTSIM.md", "memorybox/x.py"],
        )
        self.assertEqual(hits, ["docs/ops/I14_MIGRATION_035_FLIGHTSIM.md"])

    def test_rollback_order(self) -> None:
        self.assertEqual(
            d035.ROLLBACK_DROP_ORDER[0],
            "comms_record_identity_aliases",
        )
        self.assertEqual(d035.ROLLBACK_DROP_ORDER[-1], "comms_logical_sources")
        self.assertEqual(d035.ROLLBACK_DROP_ORDER[4], "comms_source_memberships")

    def test_rollback_refuses_nonempty_and_file_present(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.sql: list[str] = []

            def execute(self, sql: str, params=None):
                self.sql.append(sql)
                if "to_regclass" in sql:
                    return _Rows([{"e": True}])
                if "COUNT" in sql:
                    return _Rows([{"n": 1}])
                return _Rows([])

        with self.assertRaises(DeployValidationError):
            d035.rollback_empty_035(Fake(), file_absent=True)
        with self.assertRaises(DeployValidationError):
            d035.rollback_empty_035(Fake(), file_absent=False)


class _Rows:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class ScriptAndRunbook(unittest.TestCase):
    def test_ps1_has_scalar_migrate_check_and_preflight_switch(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertIn("$applied = @($migObj.applied)", text)
        self.assertIn("$applied.Count -ne 1", text)
        self.assertIn("035_p2_i14_communications_lineage.sql", text)
        self.assertIn("PreflightOnly", text)
        self.assertIn("poll-health", text)
        self.assertIn("merge-base --is-ancestor", text)
        self.assertIn("untracked files collide", text.lower())
        rb = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("4c13f70aae0d18f217eec4dcf43a98e6b964b14d", rb)
        self.assertIn("Do **not** seed", rb)
        self.assertIn("-PreflightOnly", rb)
        self.assertIn("-Rollback", rb)


if __name__ == "__main__":
    unittest.main()
