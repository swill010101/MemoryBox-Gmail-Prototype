"""Regression for the v3 activator postcheck KeyError and disposable activate/rollback."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from memorybox.migrate import _BOOTSTRAP
from memorybox.ops import i14_prepared_activate_v3 as activate_v3
from memorybox.ops.i14_prepared_activate_v3 import (
    V1,
    V2,
    V3,
    ActivateV3Error,
    postcheck,
)
from tests.test_i14_prepared_loader import PreparedLoaderPg


class _Rows:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class PostcheckGenerationId(unittest.TestCase):
    def test_omitting_id_reproduces_keyerror(self) -> None:
        v3 = uuid4()
        child = {"threads": 1, "messages": 1, "participants": 1, "attachments": 0}

        class Conn:
            def execute(self, sql: str, params: tuple | None = None) -> _Rows:
                blob = " ".join(sql.split())
                if "FROM comms_prepared_generations ORDER BY created_at" in blob:
                    return _Rows(
                        [
                            {
                                "algo_version": V1,
                                "status": "superseded",
                                "published": False,
                                "is_active": False,
                            },
                            {
                                "algo_version": V2,
                                "status": "validated",
                                "published": False,
                                "is_active": False,
                            },
                            {
                                "algo_version": V3,
                                "status": "published",
                                "published": True,
                                "is_active": True,
                            },
                        ]
                    )
                if "FROM comms_prepared_active_generations a" in blob:
                    return _Rows([{"algo_version": V3}])
                if "COUNT(*)" in blob:
                    if "failed" in blob or "building" in blob:
                        return _Rows([{"n": 0}])
                    if "comms_prepared_attachments" in blob:
                        return _Rows([{"n": 0}])
                    return _Rows([{"n": 1}])
                return _Rows([])

        with patch.object(activate_v3, "CHILD", child):
            with self.assertRaises(KeyError) as ctx:
                postcheck(Conn(), v3)
        self.assertEqual(ctx.exception.args[0], "id")

    def test_selecting_id_reaches_child_lookup(self) -> None:
        v1 = uuid4()
        v2 = uuid4()
        v3 = uuid4()
        child = {"threads": 1, "messages": 1, "participants": 1, "attachments": 0}

        class Conn:
            def execute(self, sql: str, params: tuple | None = None) -> _Rows:
                blob = " ".join(sql.split())
                if "FROM comms_prepared_generations ORDER BY created_at" in blob:
                    return _Rows(
                        [
                            {
                                "id": v1,
                                "algo_version": V1,
                                "status": "superseded",
                                "published": False,
                                "is_active": False,
                            },
                            {
                                "id": v2,
                                "algo_version": V2,
                                "status": "validated",
                                "published": False,
                                "is_active": False,
                            },
                            {
                                "id": v3,
                                "algo_version": V3,
                                "status": "published",
                                "published": True,
                                "is_active": True,
                            },
                        ]
                    )
                if "FROM comms_prepared_active_generations a" in blob:
                    return _Rows([{"algo_version": V3}])
                if "prepared_text_disposition" in blob:
                    return _Rows([{"d": "authored_displayable", "n": 1}])
                if "split_part" in blob:
                    return _Rows([{"who": "Peggy", "n": 1}])
                if "commercial_class" in blob:
                    return _Rows([{"k": "not_commercial", "n": 1}])
                if "quote_quality" in blob:
                    return _Rows([{"k": "clean", "n": 1}])
                if "COUNT(*)" in blob:
                    if "failed" in blob or "building" in blob:
                        return _Rows([{"n": 0}])
                    if "comms_prepared_attachments" in blob:
                        return _Rows([{"n": 0}])
                    if "FROM evidence" in blob:
                        return _Rows([{"n": 3}])
                    if "FROM sources" in blob:
                        return _Rows([{"n": 1}])
                    if "communication_rfc_ids" in blob:
                        return _Rows([{"n": 0}])
                    return _Rows([{"n": 1}])
                return _Rows([])

        disp = {
            "authored_displayable": 1,
            "non_substantive": 0,
            "correctly_empty": 0,
            "attachment_only": 0,
            "prepared_text_unavailable": 0,
            "uncertain": 0,
        }
        with (
            patch.object(activate_v3, "CHILD", child),
            patch.object(activate_v3, "DISP", disp),
            patch.object(activate_v3, "VOICE", {"Peggy": 1}),
            patch.object(
                activate_v3,
                "ARCHIVE",
                {"evidence": 3, "sources": 1, "communication_rfc_ids": 0},
            ),
        ):
            proof = postcheck(Conn(), v3)
        self.assertEqual(proof["child"], child)
        self.assertEqual(proof["voice"], {"Peggy": 1})


class DisposableActivateV3(PreparedLoaderPg):
    def _ledger40(self, conn) -> None:
        conn.execute(_BOOTSTRAP)
        conn.execute("DELETE FROM schema_migrations")
        files = [
            "001_domain_v0.sql",
            "002_journal_i5a.sql",
            "003_person_i6.sql",
            "004_artifact_i9.sql",
            "005_person_profile_i9a.sql",
            "006_owner_runtime_setting.sql",
            "007_guided_capture_i11.sql",
            "008_p2_i1_person_in_media.sql",
            "009_person_fact_residence.sql",
            "010_p2_i7a_ai_trace_ensure.sql",
            "011_p2_i8b_video_face.sql",
            "012_p2_i8b_person_watermark.sql",
            "013_p2_i9_spoken.sql",
            "014_p2_i10_correlate.sql",
            "015_p2_i10a_stories.sql",
            "016_p2_i10b_artifacts.sql",
            "017_p2_i10a1_person_date_precision.sql",
            "018_p2_i10a2_story_speech.sql",
            "019_p2_i10c_journal.sql",
            "020_p2_i11_evidence_sent_windows.sql",
            "021_p2_i11a_semantic_observations.sql",
            "022_p2_i11a_extract_cache.sql",
            "023_p2_i11a_person_retrieve.sql",
            "024_communication_identities.sql",
            "025_trusted_retrieval_identity.sql",
            "026_backfill_email_retrieval_trust.sql",
            "027_demote_untrusted_email_status.sql",
            "028_communication_rfc_ids.sql",
            "029_communication_rfc_ids_length.sql",
            "030_p2_i13_scope_admission.sql",
            "031_p2_i13_transcript_annotations.sql",
            "032_p2_i13_voice_pilot.sql",
            "033_p2_i13_interactive_learn.sql",
            "034_historian_capture_hc2_tick.sql",
            "035_p2_i14_communications_lineage.sql",
            "036_p2_i14_prepared_communications.sql",
            "037_p2_i14_prepared_evidence_ref_scale.sql",
            "038_p2_i14_voice_without_recipient_identity.sql",
            "039_p2_i14_voice_requires_prepared_text.sql",
            "040_p2_i14_voice_requires_displayable_authored.sql",
        ]
        for name in files:
            conn.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
                (name.split("_", 1)[0], name),
            )

    def _expected(self, conn, v3: UUID) -> dict:
        child = activate_v3._child(conn, v3)
        archive = {
            "evidence": activate_v3._n(conn, "SELECT COUNT(*) AS n FROM evidence"),
            "sources": activate_v3._n(conn, "SELECT COUNT(*) AS n FROM sources"),
            "communication_rfc_ids": activate_v3._n(
                conn, "SELECT COUNT(*) AS n FROM communication_rfc_ids"
            ),
        }
        disp = {
            "authored_displayable": 1,
            "non_substantive": 0,
            "correctly_empty": 0,
            "attachment_only": 0,
            "prepared_text_unavailable": 0,
            "uncertain": 0,
        }
        return {
            "child": child,
            "archive": archive,
            "disp": disp,
            "voice": {"Peggy": 1},
        }

    def _seed_v1_v2_v3(self, conn) -> tuple[UUID, UUID, UUID]:
        self._wipe(conn)
        self._ledger40(conn)
        src = self._source(conn)
        _ledger, focal, _other = self._ledger(conn)
        v1 = self._activatable_generation(
            conn,
            src=src,
            person_id=focal,
            algo=V1,
            rfc="<v1-ok@example.test>",
            cleaned="Thanks",
            voice=True,
            disposition=None,
            display_id="T-9001",
        )
        conn.execute("SELECT comms_prepared_activate_generation(%s)", (v1,))
        v2 = self._activatable_generation(
            conn,
            src=src,
            person_id=focal,
            algo=V2,
            rfc="<v2-ok@example.test>",
            cleaned="Thanks",
            voice=True,
            disposition=None,
            display_id="T-9002",
        )
        v3 = self._activatable_generation(
            conn,
            src=src,
            person_id=focal,
            algo=V3,
            rfc="<v3-ok@example.test>",
            cleaned="Thanks",
            voice=True,
            disposition="authored_displayable",
            display_id="T-9003",
        )
        conn.commit()
        return v1, v2, v3

    def _patches(self, conn, v3: UUID, private: Path):
        exp = self._expected(conn, v3)
        return (
            patch.object(activate_v3, "PRIVATE_PATH", private),
            patch.object(activate_v3, "CHILD", exp["child"]),
            patch.object(activate_v3, "DISP", exp["disp"]),
            patch.object(activate_v3, "VOICE", exp["voice"]),
            patch.object(activate_v3, "ARCHIVE", exp["archive"]),
        )

    def test_activation_and_postcheck_succeed_on_disposable_postgres(self) -> None:
        self._require_dsn()
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            _v1, _v2, v3 = self._seed_v1_v2_v3(conn)
            with tempfile.TemporaryDirectory() as tmp:
                private = Path(tmp) / "v3.json"
                private.write_text(json.dumps({"generation_id": str(v3)}), encoding="utf-8")
                patches = self._patches(conn, v3, private)
                with patches[0], patches[1], patches[2], patches[3], patches[4]:
                    public = activate_v3.run(conn)
                    conn.commit()
            self.assertTrue(public["ok"])
            self.assertTrue(public["activation_called"])
            self.assertEqual(public["algo_version"], V3)
            gens = {g["algo_version"]: g for g in public["generations"]}
            self.assertTrue(gens[V3]["published"] and gens[V3]["is_active"])
            self.assertEqual(gens[V1]["status"], "superseded")
            self.assertFalse(gens[V1]["is_active"])
            self.assertEqual(gens[V2]["status"], "validated")
            self.assertFalse(gens[V2]["published"])
            active = conn.execute(
                "SELECT algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()["algo_version"]
            self.assertEqual(active, V3)

    def test_postcheck_exception_rolls_back_activation_on_disposable_postgres(self) -> None:
        self._require_dsn()
        import psycopg
        from psycopg.rows import dict_row

        def boom(conn, v3):
            raise ActivateV3Error("injected_postcheck")

        with psycopg.connect(
            self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5
        ) as conn:
            v1, _v2, v3 = self._seed_v1_v2_v3(conn)
            with tempfile.TemporaryDirectory() as tmp:
                private = Path(tmp) / "v3.json"
                private.write_text(json.dumps({"generation_id": str(v3)}), encoding="utf-8")
                patches = self._patches(conn, v3, private)
                with patches[0], patches[1], patches[2], patches[3], patches[4]:
                    with patch.object(activate_v3, "postcheck", boom):
                        with self.assertRaises(ActivateV3Error) as ctx:
                            activate_v3.run(conn)
                        self.assertEqual(ctx.exception.code, "injected_postcheck")
                        conn.rollback()
            live = conn.execute(
                "SELECT algo_version, status, published, is_active FROM comms_prepared_generations"
                " ORDER BY created_at"
            ).fetchall()
            by = {str(r["algo_version"]): r for r in live}
            self.assertTrue(by[V1]["published"] and by[V1]["is_active"])
            self.assertEqual(by[V1]["status"], "published")
            self.assertFalse(by[V3]["published"] or by[V3]["is_active"])
            self.assertEqual(by[V3]["status"], "validated")

    def test_v1_v3_v1_rollback_on_disposable_postgres(self) -> None:
        self._require_dsn()
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            v1, _v2, v3 = self._seed_v1_v2_v3(conn)
            with tempfile.TemporaryDirectory() as tmp:
                private = Path(tmp) / "v3.json"
                private.write_text(json.dumps({"generation_id": str(v3)}), encoding="utf-8")
                patches = self._patches(conn, v3, private)
                with patches[0], patches[1], patches[2], patches[3], patches[4]:
                    activate_v3.run(conn)
                    conn.commit()
            conn.execute(
                "UPDATE comms_prepared_generations SET status = 'validated' WHERE id = %s",
                (v1,),
            )
            conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v1,))
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (v1,))
            conn.commit()
            active = conn.execute(
                "SELECT id, algo_version FROM comms_prepared_generations WHERE is_active"
            ).fetchone()
            self.assertEqual(active["id"], v1)
            self.assertEqual(active["algo_version"], V1)
            v3_state = conn.execute(
                "SELECT is_active, published, status FROM comms_prepared_generations WHERE id = %s",
                (v3,),
            ).fetchone()
            self.assertFalse(v3_state["is_active"])
            self.assertFalse(v3_state["published"])
            self.assertEqual(v3_state["status"], "superseded")
            v2_state = conn.execute(
                "SELECT status, published, is_active FROM comms_prepared_generations"
                " WHERE algo_version = %s",
                (V2,),
            ).fetchone()
            self.assertEqual(v2_state["status"], "validated")
            self.assertFalse(v2_state["published"] or v2_state["is_active"])


def load_tests(loader, standard_tests, pattern):
    del standard_tests, pattern
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(PostcheckGenerationId))
    for name in (
        "test_activation_and_postcheck_succeed_on_disposable_postgres",
        "test_postcheck_exception_rolls_back_activation_on_disposable_postgres",
        "test_v1_v3_v1_rollback_on_disposable_postgres",
    ):
        suite.addTest(DisposableActivateV3(name))
    return suite


if __name__ == "__main__":
    unittest.main()
