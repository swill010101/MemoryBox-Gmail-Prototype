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
    checks = [
        {
            "table": table,
            "name": name,
            "columns": list(cols),
            "contype": "c",
            "convalidated": True,
        }
        for table, name, cols in d035.EXPECTED_CHECKS
    ]
    uniques = [
        {"table": table, "name": f"{table}_key", "columns": list(cols)}
        for table, cols in d035.EXPECTED_UNIQUES
    ]
    fks = [
        {
            "table": table,
            "name": f"{table}_fk",
            "columns": list(cols),
            "foreign_table": ft,
            "foreign_columns": list(fcols),
            "confdeltype": deltype,
        }
        for table, cols, ft, fcols, deltype in d035.EXPECTED_FKS
    ]
    return {
        "tables": list(d035.COMMS_TABLES),
        "row_counts": {t: 0 for t in d035.COMMS_TABLES},
        "columns": {k: list(v) for k, v in d035.EXPECTED_COLUMNS.items()},
        "primary_keys": {k: list(v) for k, v in d035.EXPECTED_PKS.items()},
        "foreign_keys": fks,
        "uniques": uniques,
        "checks": checks,
        "check_defs": [
            "CHECK ((source_kind IN ('email', 'calendar', 'sms')))",
            "CHECK ((source_kind = ANY (ARRAY['email'::text, 'calendar'::text, 'sms'::text])))",
        ],
        "checkpoint_confdeltype": "r",
        "indexes": {name: False for name in d035.EXPECTED_INDEXES},
        "baseline_counts": {"evidence": 3, "sources": 2, "communication_rfc_ids": 4},
        "after_counts": {"evidence": 3, "sources": 2, "communication_rfc_ids": 4},
        "ledger_035": {"version": "035", "filename": d035.MIGRATION_FILENAME},
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

    def test_preflight_health_allows_top_level_false_when_only_035_pending(self) -> None:
        payload = {
            "ok": False,
            "database": {"status": "ok"},
            "migrations": {
                "status": "ok",
                "pending": [d035.MIGRATION_FILENAME],
                "applied": [{"version": "034"}],
            },
        }
        out = d035.assert_health_pending_only_035(payload)
        self.assertTrue(out["preflight_ok"])
        self.assertEqual(out["pending"], [d035.MIGRATION_FILENAME])
        self.assertFalse(out["ok"])
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_health_pending_only_035(
                {
                    "ok": True,
                    "database": {"status": "ok"},
                    "migrations": {"status": "ok", "pending": [], "applied": []},
                }
            )
        self.assertIn("pending_not_only_035", str(ctx.exception))
        with self.assertRaises(DeployValidationError):
            d035.assert_health_pending_only_035(
                {
                    "ok": False,
                    "database": {"status": "error"},
                    "migrations": {
                        "status": "ok",
                        "pending": [d035.MIGRATION_FILENAME],
                        "applied": [],
                    },
                }
            )
        scalar = json.loads(json.dumps(payload))
        scalar["migrations"]["pending"] = d035.MIGRATION_FILENAME
        self.assertEqual(
            d035.assert_health_pending_only_035(scalar)["pending"],
            [d035.MIGRATION_FILENAME],
        )


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
        self.assertTrue(result["checks_structural"])

    def test_check_validation_ignores_pg_constraintdef_text(self) -> None:
        snap = _contract_ok()
        snap["check_defs"] = [
            "CHECK ((source_kind = ANY (ARRAY['email'::text, 'calendar'::text, 'sms'::text])))"
        ]
        out = d035.assert_035_contract(snap)
        self.assertTrue(out["ok"])
        self.assertTrue(out["checks_structural"])

    def test_rejects_missing_structural_check(self) -> None:
        snap = _contract_ok()
        snap["checks"] = [c for c in snap["checks"] if c["name"] != "comms_logical_sources_source_kind_check"]
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_035_contract(snap)
        self.assertIn("missing_check:comms_logical_sources_source_kind_check", str(ctx.exception))

    def test_rejects_unique_source_id_and_set_null(self) -> None:
        snap = _contract_ok()
        snap["uniques"].append(
            {"table": "comms_extract_instances", "name": "bad", "columns": ["source_id"]}
        )
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)
        snap = _contract_ok()
        snap["foreign_keys"].append(
            {
                "table": "comms_source_checkpoint",
                "name": "bad_set_null",
                "columns": ["x"],
                "foreign_table": "y",
                "foreign_columns": ["id"],
                "confdeltype": "n",
            }
        )
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

        snap = _contract_ok()
        snap["columns"]["comms_logical_sources"] = ["id"]
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_035_contract(snap)
        self.assertIn("columns_mismatch_comms_logical_sources", str(ctx.exception))

    def test_indexes_source_id_nonunique(self) -> None:
        snap = _contract_ok()
        snap["indexes"]["idx_comms_extract_instances_source"] = True
        with self.assertRaises(DeployValidationError):
            d035.assert_035_contract(snap)

    def test_catalog_execute_never_sends_empty_params_with_percent(self) -> None:
        class Boom:
            def execute(self, sql, params=None):
                raise AssertionError("should not execute")

        with self.assertRaises(DeployValidationError) as ctx:
            d035.catalog_execute(Boom(), "SELECT 1 LIKE 'comms_%'")
        self.assertIn("unsafe_percent_sql", str(ctx.exception))
        with self.assertRaises(DeployValidationError):
            d035.catalog_execute(Boom(), "SELECT 1 LIKE 'comms_%'", ())

    def test_snapshot_query_helper_does_not_use_like(self) -> None:
        import inspect

        src = inspect.getsource(d035.collect_schema_snapshot)
        self.assertNotIn("LIKE", src)
        self.assertIn("ANY(%s)", src)
        self.assertIn("catalog_execute", src)


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


class ReleaseGate(unittest.TestCase):
    def _ok(self, **over: object) -> dict:
        head = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        payload = {
            "head": head,
            "release_sha": head,
            "origin_sha": head,
            "schema_is_ancestor": True,
            "migration_head_oid": "blob-same",
            "migration_schema_oid": "blob-same",
            "allow_offline_origin": False,
            "files_present": d035.OPS_PACK_PATHS,
        }
        payload.update(over)
        return payload

    def test_wrong_release_sha_fails(self) -> None:
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_release_state(**self._ok(release_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"))
        self.assertIn("head_ne_release_sha", str(ctx.exception))

    def test_non_descendant_fails(self) -> None:
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_release_state(**self._ok(schema_is_ancestor=False))
        self.assertIn("not_descendant_of_schema_review", str(ctx.exception))

    def test_altered_035_sql_fails(self) -> None:
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_release_state(
                **self._ok(migration_head_oid="blob-a", migration_schema_oid="blob-b")
            )
        self.assertIn("035_sql_differs_from_schema_review", str(ctx.exception))

    def test_correct_descendant_identical_035_passes(self) -> None:
        out = d035.assert_release_state(**self._ok())
        self.assertTrue(out["ok"])
        self.assertEqual(out["035_blob"], "blob-same")

    def test_real_repo_head_matches_schema_review_blob(self) -> None:
        import subprocess

        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report = d035.inspect_release_repo(ROOT, head, allow_offline_origin=True)
        self.assertTrue(report["ok"])
        schema_blob = subprocess.check_output(
            ["git", "rev-parse", f"{d035.SCHEMA_REVIEW_SHA}:{d035.MIGRATION_RELPATH}"],
            cwd=ROOT,
            text=True,
        ).strip()
        self.assertEqual(report["035_blob"], schema_blob)

    def test_validation_module_survives_simulated_apply_without_checkout(self) -> None:
        d035.assert_ops_pack_present(ROOT)
        from memorybox.ops import i14_migration_035 as again

        again.assert_ops_pack_present(ROOT)
        self.assertTrue(again.assert_035_contract(_contract_ok())["ok"])
        self.assertTrue((ROOT / "memorybox" / "ops" / "i14_migration_035.py").is_file())
        self.assertTrue((ROOT / "scripts" / "ops" / "Deploy-I14Migration035.ps1").is_file())


class RuntimeEnvAndMigrate(unittest.TestCase):
    def test_missing_qdrant_fails_before_backup_migrate(self) -> None:
        with self.assertRaises(DeployValidationError) as ctx:
            d035.assert_runtime_env(
                {"MEMORYBOX_DATABASE_URL": "postgresql://memorybox:s3cret@127.0.0.1:5432/memorybox"}
            )
        self.assertIn("runtime_env_missing:MEMORYBOX_QDRANT_URL", str(ctx.exception))
        text = PS1.read_text(encoding="utf-8")
        self.assertLess(text.index("assert-runtime-env"), text.index("=== BACKUP ==="))
        self.assertLess(text.index("=== RUNTIME ENV ==="), text.index("=== BACKUP ==="))
        self.assertLess(text.index("=== BACKUP ==="), text.index("$mig = Invoke-MbMigrate"))

    def test_startmb_prefers_venv_python_with_uvicorn(self) -> None:
        startmb = (ROOT / "startmb.ps1").read_text(encoding="utf-8")
        self.assertIn(".venv\\Scripts\\python.exe", startmb)
        self.assertIn("Test-PythonHasServeDeps", startmb)
        self.assertIn("uvicorn=True", startmb)
        self.assertLess(
            startmb.index(".venv\\Scripts\\python.exe"),
            startmb.index("Get-Command python"),
        )

    def test_production_equivalent_defaults_supply_qdrant(self) -> None:
        startmb = (ROOT / "startmb.ps1").read_text(encoding="utf-8")
        self.assertIn('MEMORYBOX_QDRANT_URL = "http://127.0.0.1:6333"', startmb)
        filled, sources = d035.apply_startmb_nonsecret_defaults({})
        self.assertEqual(filled["MEMORYBOX_QDRANT_URL"], "http://127.0.0.1:6333")
        self.assertEqual(sources["MEMORYBOX_QDRANT_URL"], "startmb.ps1 Load-MbEnv default")
        report = d035.assert_runtime_env(filled)
        self.assertEqual(report["qdrant_endpoint"], "http://127.0.0.1:6333")
        self.assertEqual(report["qdrant_source"], "startmb.ps1 Load-MbEnv default")

    def test_secrets_are_not_printed(self) -> None:
        env = {
            "MEMORYBOX_DATABASE_URL": "postgresql://memorybox:super-secret-pass@127.0.0.1:5432/memorybox",
            "MEMORYBOX_QDRANT_URL": "http://127.0.0.1:6333",
        }
        report = d035.assert_runtime_env(env)
        blob = json.dumps(report)
        self.assertNotIn("super-secret-pass", blob)
        self.assertNotIn("memorybox:super-secret-pass@", blob)
        self.assertIn("MEMORYBOX_QDRANT_URL", blob)
        self.assertEqual(report["settings"][0]["endpoint"], "postgresql://127.0.0.1:5432")

    def test_nonzero_migrate_exit_is_not_json_success(self) -> None:
        with self.assertRaises(DeployValidationError) as ctx:
            d035.interpret_migrate_process(
                1, "", "RuntimeError: MEMORYBOX_QDRANT_URL is required"
            )
        self.assertIn("migrate_not_started:configuration", str(ctx.exception))
        with self.assertRaises(DeployValidationError) as ctx:
            d035.interpret_migrate_process(2, "", "ERROR:  syntax error at or near CREATE")
        self.assertIn("migrate_failed:sql_or_runtime", str(ctx.exception))
        self.assertIn("syntax error", str(ctx.exception))
        with self.assertRaises(DeployValidationError) as ctx:
            d035.interpret_migrate_process(0, "not-json", "")
        self.assertIn("migrate_invalid_output", str(ctx.exception))
        with self.assertRaises(DeployValidationError):
            d035.interpret_migrate_process(0, '{"applied":[]}', "")
        out = d035.interpret_migrate_process(
            0, json.dumps({"applied": [d035.MIGRATION_FILENAME]}), ""
        )
        self.assertEqual(out["applied"], [d035.MIGRATION_FILENAME])
        recovered = d035.interpret_migrate_process(
            1,
            '{\n  "applied": [\n    "035_p2_i14_communications_lineage.sql"\n  ]\n}\n',
            "",
        )
        self.assertEqual(recovered["applied"], [d035.MIGRATION_FILENAME])
        self.assertTrue(recovered["exit_nonzero_after_applied"])
        self.assertEqual(recovered["process_exit_code"], 1)

    def test_no_restart_after_migrate_failure(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertLess(text.index("$mig = Invoke-MbMigrate"), text.index("=== RESTART SERVE ==="))
        self.assertLess(
            text.index("restart_without_migrate_success"),
            text.index("=== RESTART SERVE ==="),
        )
        self.assertIn("$script:MigrateSucceeded = $false", text)
        self.assertIn("$script:MigrateSucceeded = $true", text)
        true_at = text.index("$script:MigrateSucceeded = $true")
        restart_at = text.index("=== RESTART SERVE ===")
        self.assertLess(true_at, restart_at)


class ScriptAndRunbook(unittest.TestCase):
    def test_ps1_has_no_internal_apply_checkout(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertIn("$ReleaseSha", text)
        self.assertIn("Mandatory = $true", text)
        self.assertIn("-ReleaseSha", RUNBOOK.read_text(encoding="utf-8"))
        self.assertIn("assert-health-preflight", text)
        self.assertIn("assert-release", text)
        self.assertNotIn("if (-not $health.ok)", text)
        self.assertIn("function Get-GitText", text)
        self.assertNotRegex(text, r"branch --show-current\)\.Trim\(\)")
        self.assertIn("(detached)", text)
        self.assertNotIn("checkout -B", text)
        self.assertNotIn("git fetch origin", text)
        self.assertIn("checkout --detach $RequiredPrior", text)
        self.assertIn("Invoke-MbMigrate", text)
        self.assertIn("interpret-migrate", text)
        self.assertIn("assert-runtime-env", text)
        self.assertLess(text.index("assert-runtime-env"), text.index("=== BACKUP ==="))
        self.assertLess(text.index("$mig = Invoke-MbMigrate"), text.index("=== RESTART SERVE ==="))
        self.assertIn("restart_without_migrate_success", text)
        self.assertIn("& $py -m memorybox migrate", text)
        self.assertIn("MIGRATE_STDERR_SANITIZED", text)
        self.assertNotIn("& $Python -m memorybox migrate", text)
        self.assertNotIn("Start-Sleep 8", text)
        rb = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("git checkout <new full ops-fix SHA>", rb)
        self.assertIn("-ReleaseSha <same full SHA> -PreflightOnly", rb)
        self.assertIn("-ReleaseSha <same full SHA>", rb)
        self.assertIn("Do **not** seed", rb)
        self.assertIn("$ResumeAfterMigrate", text)
        self.assertIn("=== RESUME AFTER MIGRATE ===", text)
        self.assertIn("no backup; no migrate", text)
        self.assertIn("does **not** change Git commits", rb)
        self.assertIn("No migration SQL was applied", rb)
        self.assertIn("Do not use `-ResumeAfterMigrate`", rb)
        self.assertIn("python.exe -m memorybox.ops.i14_migration_035 verify-schema", rb)
        self.assertIn(".\\startmb.cmd -Restart", rb)
        self.assertIn("= ANY (ARRAY[", rb)


if __name__ == "__main__":
    unittest.main()
