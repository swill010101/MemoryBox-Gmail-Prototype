"""Interactive Learn worker lifecycle, isolation, inspector gate — offline doubles only."""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybox.processing import scope  # noqa: E402

PERSON = "00000000-0000-4000-8000-000000000001"
ADMISSION = "00000000-0000-4000-8000-000000000002"
INSPECTOR = ROOT / "docs/implementation/p2-i13-stage-a/inspect-interactive-learn-reconciliation.py"


def _plan():
    return {
        "scope_kind": "bounded",
        "manifest": {
            "id": "synthetic-test-only",
            "version": "1",
            "sources": [
                {
                    "provider_key": "synthetic",
                    "video_external_id": f"video-{i}",
                    "source_sha256": f"{i:064x}",
                    "duration_sec": 60,
                    "owner_confirmed": True,
                    "owner_truth_ref": "synthetic test fixture, not real owner truth",
                    "coverage_tags": sorted(scope.COVERAGE),
                    "truth": [{"modality": "face", "person_id": PERSON, "start_sec": 1, "end_sec": 2}],
                }
                for i in range(22)
            ],
        },
        "person_ids": [PERSON],
        "lanes": ["face", "voice", "transcribe"],
        "max_work_items": 66,
        "max_attempts_per_item": 2,
        "purpose": "acceptance_learning",
    }


def _admission(**kw):
    p = deepcopy(_plan())
    state = kw.pop("state", "started")
    return scope.Admission(
        ADMISSION,
        p,
        state,
        scope.digest(p),
        start_ref="synthetic start" if state == "started" else None,
        interactive_learn_enabled=kw.get("interactive_learn_enabled", False),
        interactive_learn_ref=kw.get("interactive_learn_ref"),
    )


def _function(path, name, env=None):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = dict(env or {})
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), "exec"), ns)
    return ns[name]


class Result:
    def __init__(self, row=None, rows=None, rowcount=0):
        self.row = row
        self.rows = rows or []
        self.rowcount = rowcount

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, admission):
        self.row = {
            "id": admission.id,
            "plan_json": admission.plan,
            "plan_sha256": admission.plan_sha256,
            "state": admission.state,
            "acceptance_ref": admission.acceptance_ref,
            "unlock_ref": admission.unlock_ref,
            "start_ref": admission.start_ref,
            "interactive_learn_enabled": admission.interactive_learn_enabled,
            "interactive_learn_ref": admission.interactive_learn_ref,
        }
        self.attempts = {}
        self.queue_rows = []

    def execute(self, sql, args=()):
        if "FROM i13_processing_admissions" in sql and sql.strip().startswith("SELECT"):
            return Result(dict(self.row))
        if "INSERT INTO i13_work_attempts" in sql:
            key = tuple(args[1:5])
            n = self.attempts.get(key, 0)
            if n >= args[5]:
                return Result()
            self.attempts[key] = n + 1
            return Result({"attempts": n + 1})
        if "FROM recognition_queue_items" in sql and "owner_learn" in sql and "status" in sql and "queued" in sql:
            for row in self.queue_rows:
                if (
                    row.get("lane") == "face"
                    and row.get("status") == "queued"
                    and row.get("enqueue_reason") == "owner_learn"
                ):
                    return Result(dict(row))
            return Result()
        if "FROM speech_queue_items" in sql and "owner_learn" in sql and "status" in sql and "queued" in sql:
            for row in self.queue_rows:
                if (
                    row.get("lane") == "voice"
                    and row.get("status") == "queued"
                    and row.get("enqueue_reason") == "owner_learn"
                ):
                    return Result(dict(row))
            return Result()
        if "FROM recognition_queue_items" in sql and "status" in sql and "failed" in sql:
            return Result(rows=[r for r in self.queue_rows if r.get("lane") == "face"])
        if "UPDATE recognition_queue_items" in sql and "SET status = 'running'" in sql:
            return Result()
        if "UPDATE speech_queue_items" in sql and "SET status = 'running'" in sql:
            return Result()
        if "UPDATE recognition_queue_items" in sql and "SET status = 'queued'" in sql and "WHERE status = 'running'" in sql:
            return Result(rowcount=1)
        if "UPDATE speech_queue_items" in sql and "SET status = 'queued'" in sql and "WHERE status = 'running'" in sql:
            return Result(rowcount=1)
        if "UPDATE recognition_queue_items" in sql and "SET status = 'queued'" in sql:
            return Result(rowcount=1)
        if "UPDATE speech_queue_items" in sql and "SET status = 'queued'" in sql:
            return Result(rowcount=1)
        if "UPDATE recognition_queue_items" in sql:
            return Result(rowcount=1)
        if "UPDATE speech_queue_items" in sql:
            return Result(rowcount=1)
        raise AssertionError(f"Unexpected SQL: {sql[:160]}")


@contextmanager
def _db_env(admission, conn):
    @contextmanager
    def connection():
        yield conn

    with patch.dict(os.environ, {"MEMORYBOX_I13_ADMISSION_ID": admission.id}, clear=False), patch(
        "memorybox.recognition.queue.connection", connection
    ), patch("memorybox.speech.queue.connection", connection), patch(
        "memorybox.db.connection", connection
    ), patch.object(scope, "load_admission", return_value=admission), patch.object(
        scope, "require_interactive_source", return_value=admission
    ):
        yield


class InteractiveLearnWorkerLifecycleTests(unittest.TestCase):
    def setUp(self):
        from memorybox.processing import interactive_drain as drain

        drain.reset_interactive_learn_worker_for_tests()

    def test_face_owner_learn_claims_only_owner_learn_row(self):
        a = _admission(state="stopped", interactive_learn_enabled=True)
        c = FakeConnection(a)
        c.queue_rows = [
            {
                "id": str(UUID(int=1)),
                "person_id": PERSON,
                "video_provider_key": "synthetic",
                "video_external_id": "video-0",
                "enqueue_reason": "transcribe",
                "attempt_count": 0,
                "lane": "face",
                "status": "queued",
            },
            {
                "id": str(UUID(int=2)),
                "person_id": PERSON,
                "video_provider_key": "synthetic",
                "video_external_id": "video-0",
                "enqueue_reason": "owner_learn",
                "attempt_count": 0,
                "lane": "face",
                "status": "queued",
            },
        ]
        from memorybox.recognition import queue as rq

        with _db_env(a, c):
            got = rq.claim_next_interactive_item()
        self.assertEqual(got["enqueue_reason"], "owner_learn")

    def test_voice_owner_learn_claim_when_stopped_with_flag(self):
        a = _admission(state="stopped", interactive_learn_enabled=True)
        c = FakeConnection(a)
        c.queue_rows = [
            {
                "id": str(UUID(int=3)),
                "person_id": PERSON,
                "video_provider_key": "synthetic",
                "video_external_id": "video-1",
                "enqueue_reason": "owner_learn",
                "attempt_count": 0,
                "lane": "voice",
                "status": "queued",
            }
        ]
        from memorybox.speech import queue as sq

        with _db_env(a, c):
            got = sq.claim_next_interactive_item()
        self.assertEqual(got["video_external_id"], "video-1")

    def test_interactive_claim_rejects_archive_and_pilot_admissions(self):
        archive = _admission(state="stopped", interactive_learn_enabled=True)
        archive.plan["scope_kind"] = "archive"
        pilot = _admission(state="stopped", interactive_learn_enabled=True)
        pilot.plan["purpose"] = "voice_pilot"
        fn = _function("memorybox/recognition/queue.py", "claim_next_interactive_item")
        for bad in (archive, pilot):
            with self.subTest(admission=bad.plan.get("purpose") or bad.plan.get("scope_kind")):
                with patch.object(scope, "load_admission", return_value=bad):
                    with self.assertRaisesRegex(scope.ScopeDenied, "interactive_learn_locked"):
                        fn()

    def test_face_owner_learn_process_completes_queue_row(self):
        from memorybox.recognition import process as rec_process
        from memorybox.recognition.queue import STATUS_COMPLETED

        item = {
            "id": str(UUID(int=4)),
            "person_id": PERSON,
            "video_provider_key": "synthetic",
            "video_external_id": "video-0",
            "enqueue_reason": "owner_learn",
            "attempt_count": 1,
        }
        completed = []

        def _complete(item_id, *, status, reason=None, result=None):
            completed.append({"item_id": item_id, "status": status})

        video = MagicMock()
        video.list_videos.return_value = [MagicMock(external_id="video-0", provider_key="synthetic")]
        video.provider_key = "synthetic"

        with patch("memorybox.recognition.queue.claim_next_interactive_item", return_value=item), patch(
            "memorybox.recognition.process.complete_item", side_effect=_complete
        ), patch("memorybox.recognition.allowlist.face_scan_enabled", return_value=True), patch(
            "memorybox.recognition.exemplars.list_active_exemplars", return_value=[{"id": "ex-1"}]
        ), patch(
            "memorybox.recognition.scan.scan_video_for_person",
            return_value={"ranges": [], "accepted_count": 0},
        ):
            result = rec_process.process_one(video_provider=video, interactive=True)
        self.assertEqual(result["status"], STATUS_COMPLETED)
        self.assertEqual(completed[0]["status"], STATUS_COMPLETED)

    def test_voice_owner_learn_process_completes_queue_row(self):
        from memorybox.speech import process as speech_process
        from memorybox.speech.queue import STATUS_COMPLETED

        item = {
            "id": str(UUID(int=5)),
            "person_id": PERSON,
            "video_provider_key": "synthetic",
            "video_external_id": "video-0",
            "enqueue_reason": "owner_learn",
            "attempt_count": 1,
        }
        completed = []

        def _complete(item_id, *, status, reason=None, result=None):
            completed.append({"item_id": item_id, "status": status})

        with patch("memorybox.speech.queue.claim_next_interactive_item", return_value=item), patch(
            "memorybox.speech.process.complete_item", side_effect=_complete
        ), patch(
            "memorybox.speech.process.recognize_person_on_video",
            return_value={"ok": True, "assigned": 1},
        ):
            result = speech_process.process_one(video_provider=MagicMock(), interactive=True)
        self.assertEqual(result["status"], STATUS_COMPLETED)

    def test_recover_stale_running_owner_learn_rows(self):
        a = _admission(state="started")
        c = FakeConnection(a)
        from memorybox.processing import interactive_drain as drain

        with _db_env(a, c):
            recovered = drain.recover_stale_interactive_jobs()
        self.assertEqual(recovered["face"], 1)
        self.assertEqual(recovered["voice"], 1)

    def test_claim_is_idempotent_when_no_queued_rows(self):
        a = _admission(state="started")
        c = FakeConnection(a)
        from memorybox.recognition import queue as rq

        with _db_env(a, c):
            self.assertIsNone(rq.claim_next_interactive_item())
            self.assertIsNone(rq.claim_next_interactive_item())

    def test_retry_interactive_failed_requeues_owner_learn_only(self):
        a = _admission(state="stopped", interactive_learn_enabled=True)
        c = FakeConnection(a)
        c.queue_rows = [
            {
                "id": str(UUID(int=6)),
                "person_id": PERSON,
                "video_provider_key": "synthetic",
                "video_external_id": "video-0",
                "enqueue_reason": "owner_learn",
                "lane": "face",
            }
        ]
        from memorybox.recognition import queue as rq

        with _db_env(a, c):
            retried = rq.retry_interactive_failed_items()
        self.assertEqual(retried, 1)

    def test_worker_starts_only_once(self):
        from memorybox.processing import interactive_drain as drain

        drain.reset_interactive_learn_worker_for_tests()
        with patch.object(drain, "interactive_learn_worker_enabled", return_value=True), patch.object(
            drain, "recover_stale_interactive_jobs", return_value={"face": 0, "voice": 0}
        ), patch.object(drain.threading, "Thread") as Thread:
            drain.start_interactive_learn_worker()
            drain.start_interactive_learn_worker()
        Thread.assert_called_once()


class InteractiveLearnInspectorGateTests(unittest.TestCase):
    def _load_inspector(self):
        spec = importlib.util.spec_from_file_location("learn_recon", INSPECTOR)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        return mod

    def _classify(self, mod, *, db: dict):
        return mod._classify(
            routes={
                "explore_ui": True,
                "recognition_learn_post": True,
                "speech_learn_post": True,
                "appearances_correct_post": True,
                "speech_moments_correct_post": True,
                "admin_landing": True,
                "admin_learned_evidence": True,
                "admin_jobs_i13": True,
            },
            explore={"submitExploreLearn": True, "transcript_selection": True},
            db=db,
            env={
                "MEMORYBOX_I13_ADMISSION_ID": ADMISSION,
                "MEMORYBOX_RECOGNITION_DRAIN": "0",
                "MEMORYBOX_SPEECH_DRAIN": "0",
            },
        )

    def _learn_db(self, **overrides):
        base = {
            "owner_learn_face_exemplars": 1,
            "owner_learn_voice_exemplars": 1,
            "scoped_owner_learn_stranded_total": 0,
            "scoped_owner_learn_stranded_face": 0,
            "scoped_owner_learn_stranded_voice": 0,
            "scoped_owner_learn_completed_face": 0,
            "scoped_owner_learn_completed_voice": 0,
            "scoped_owner_learn_failed_face": 0,
            "scoped_owner_learn_failed_voice": 0,
            "scoped_owner_learn_excluded_face": 0,
            "scoped_owner_learn_excluded_voice": 0,
            "scoped_owner_learn_total": 2,
            "admissions_recent": [
                {
                    "id": ADMISSION,
                    "purpose": "acceptance_learning",
                    "scope_kind": "bounded",
                    "lanes": ["face", "voice"],
                    "state": "started",
                    "start_ref": "founder-session",
                }
            ],
            "archive_admissions_unlocked_or_started": 0,
        }
        base.update(overrides)
        return base

    def test_queue_not_stranded_fails_when_queued_or_running(self):
        mod = self._load_inspector()
        items = self._classify(
            mod,
            db=self._learn_db(
                scoped_owner_learn_stranded_total=2,
                scoped_owner_learn_stranded_face=1,
                scoped_owner_learn_stranded_voice=1,
            ),
        )
        check = next(i for i in items if i["key"] == "queue_not_stranded")
        self.assertEqual(check["classification"], "failed")

    def test_queue_not_stranded_passes_when_terminal_only(self):
        mod = self._load_inspector()
        items = self._classify(
            mod,
            db=self._learn_db(
                scoped_owner_learn_failed_face=1,
                scoped_owner_learn_excluded_voice=1,
            ),
        )
        check = next(i for i in items if i["key"] == "queue_not_stranded")
        self.assertEqual(check["classification"], "passed")

    def test_owner_learn_success_fails_on_failed(self):
        mod = self._load_inspector()
        items = self._classify(
            mod,
            db=self._learn_db(scoped_owner_learn_failed_face=1),
        )
        check = next(i for i in items if i["key"] == "owner_learn_follow_on_succeeded")
        self.assertEqual(check["classification"], "failed")

    def test_owner_learn_success_fails_on_excluded(self):
        mod = self._load_inspector()
        items = self._classify(
            mod,
            db=self._learn_db(scoped_owner_learn_excluded_voice=1),
        )
        check = next(i for i in items if i["key"] == "owner_learn_follow_on_succeeded")
        self.assertEqual(check["classification"], "failed")

    def test_owner_learn_success_passes_when_face_and_voice_completed(self):
        mod = self._load_inspector()
        items = self._classify(
            mod,
            db=self._learn_db(
                scoped_owner_learn_completed_face=1,
                scoped_owner_learn_completed_voice=1,
            ),
        )
        queue = next(i for i in items if i["key"] == "queue_not_stranded")
        success = next(i for i in items if i["key"] == "owner_learn_follow_on_succeeded")
        self.assertEqual(queue["classification"], "passed")
        self.assertEqual(success["classification"], "passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
