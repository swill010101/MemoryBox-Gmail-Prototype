"""Flags and call sequence for guarded household-email activation. No live DSN."""
from __future__ import annotations

import os
import unittest

from memorybox.ops.i14_prepared_activate import (
    CONFIRM,
    ActivateError,
    require_flags,
    run_activation,
    select_target,
)


class _Rows:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class Flags(unittest.TestCase):
    def test_refuses_without_flags(self) -> None:
        os.environ.pop("MEMORYBOX_I14_ACTIVATE_ALLOW_FLIGHTSIM", None)
        os.environ.pop("MEMORYBOX_I14_ACTIVATE_ALLOW_MEMORYBOX_DB", None)
        os.environ.pop("MEMORYBOX_I14_ACTIVATE_CONFIRM", None)
        with self.assertRaises(ActivateError) as ctx:
            require_flags()
        self.assertEqual(str(ctx.exception), "activate_flightsim_not_allowed")

    def test_confirm_string(self) -> None:
        self.assertEqual(CONFIRM, "activate-unpublished-voice-038-v1")
        os.environ["MEMORYBOX_I14_ACTIVATE_ALLOW_FLIGHTSIM"] = "1"
        os.environ["MEMORYBOX_I14_ACTIVATE_ALLOW_MEMORYBOX_DB"] = "1"
        os.environ["MEMORYBOX_I14_ACTIVATE_CONFIRM"] = CONFIRM
        require_flags()


class Select(unittest.TestCase):
    def test_refuses_two_eligible(self) -> None:
        class Conn:
            def execute(self, sql: str, params: tuple | None = None) -> _Rows:
                if "WHERE published" in sql:
                    return _Rows([{"n": 0}])
                if "comms_prepared_active_generations" in sql:
                    return _Rows([{"n": 0}])
                if "failed" in sql:
                    return _Rows([{"n": 0}])
                return _Rows(
                    [
                        {
                            "id": "a",
                            "status": "validated",
                            "published": False,
                            "is_active": False,
                            "checksum": "x" * 64,
                            "scope_key": "household_email",
                        },
                        {
                            "id": "b",
                            "status": "validated",
                            "published": False,
                            "is_active": False,
                            "checksum": "y" * 64,
                            "scope_key": "household_email",
                        },
                    ]
                )

        with self.assertRaises(ActivateError) as ctx:
            select_target(Conn())
        self.assertEqual(str(ctx.exception), "eligible_unpublished_not_one")


class Sequence(unittest.TestCase):
    def test_dry_run_does_not_call_activate(self) -> None:
        calls: list[str] = []

        class Conn:
            def execute(self, sql: str, params: tuple | None = None) -> _Rows:
                calls.append(" ".join(sql.split()))
                if "schema_migrations" in sql:
                    return _Rows(
                        [{"version": f"{i:03d}", "filename": f"{i:03d}_x.sql"} for i in range(1, 38)]
                        + [
                            {
                                "version": "038",
                                "filename": "038_p2_i14_voice_without_recipient_identity.sql",
                            }
                        ]
                    )
                if "pg_get_constraintdef" in sql:
                    return _Rows(
                        [
                            {
                                "def": (
                                    "CHECK (((NOT voice_corpus) OR "
                                    "((quote_quality = 'clean'::text) AND "
                                    "(authorship = 'authenticated_focal'::text))))"
                                )
                            }
                        ]
                    )
                if "split_part" in sql:
                    return _Rows(
                        [
                            {"who": "Tom", "n": 12071},
                            {"who": "Peggy", "n": 1368},
                            {"who": "Sue", "n": 307},
                        ]
                    )
                if "COUNT(*)" in sql:
                    if "comms_prepared_participants" in sql:
                        return _Rows([{"n": 294061}])
                    if "comms_prepared_attachments" in sql:
                        return _Rows([{"n": 28467}])
                    if "comms_prepared_threads" in sql:
                        return _Rows([{"n": 40996}])
                    if "comms_prepared_messages" in sql:
                        return _Rows([{"n": 91247}])
                    if "FROM evidence" in sql:
                        return _Rows([{"n": 188656}])
                    if "FROM sources" in sql:
                        return _Rows([{"n": 27}])
                    if "communication_rfc_ids" in sql:
                        return _Rows([{"n": 287010}])
                    return _Rows([{"n": 0}])
                if "FROM comms_prepared_generations" in sql and "checksum" in sql:
                    return _Rows(
                        [
                            {
                                "id": "gen-1",
                                "status": "validated",
                                "published": False,
                                "is_active": False,
                                "checksum": "c" * 64,
                                "scope_key": "household_email",
                            }
                        ]
                    )
                return _Rows([])

        public = run_activation(Conn(), dry_run=True)
        self.assertTrue(public["dry_run"])
        self.assertFalse(public["activation_called"])
        self.assertTrue(any("comms_prepared_assert_generation_ready" in c for c in calls))
        self.assertFalse(any("comms_prepared_activate_generation" in c for c in calls))
        self.assertFalse(any("SET published" in c for c in calls))


if __name__ == "__main__":
    unittest.main()
