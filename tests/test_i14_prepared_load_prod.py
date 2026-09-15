"""Guarded production-load flags and packet bounds. Disposable Postgres only."""
from __future__ import annotations

import os
import unittest

from memorybox.ops.i14_prepared_load_prod import (
    ALONGSIDE_CONFIRM,
    CONFIRM,
    LoadProdError,
    MAX_PACKET_THREADS,
    _require_flags,
)


class Flags(unittest.TestCase):
    def test_refuses_without_confirm_flags(self) -> None:
        os.environ.pop("MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM", None)
        os.environ.pop("MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB", None)
        os.environ.pop("MEMORYBOX_I14_LOAD_CONFIRM", None)
        with self.assertRaises(LoadProdError) as ctx:
            _require_flags()
        self.assertEqual(str(ctx.exception), "load_flightsim_not_allowed")

    def test_accepts_exact_confirm(self) -> None:
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_CONFIRM"] = CONFIRM
        _require_flags()

    def test_accepts_alongside_confirm(self) -> None:
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_CONFIRM"] = ALONGSIDE_CONFIRM
        _require_flags(alongside=True)

    def test_alongside_refuses_old_confirm(self) -> None:
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_FLIGHTSIM"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_ALLOW_MEMORYBOX_DB"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_ALONGSIDE_ACTIVE"] = "1"
        os.environ["MEMORYBOX_I14_LOAD_CONFIRM"] = CONFIRM
        with self.assertRaises(LoadProdError) as ctx:
            _require_flags(alongside=True)
        self.assertEqual(str(ctx.exception), "load_confirm_mismatch")

    def test_replace_unpublished_requires_confirm(self) -> None:
        os.environ.pop("MEMORYBOX_I14_REPLACE_UNPUBLISHED", None)
        os.environ.pop("MEMORYBOX_I14_REPLACE_CONFIRM", None)
        from memorybox.ops.i14_prepared_load_prod import REPLACE_CONFIRM, LoadProdError, _reject_unpublished_snapshot

        self.assertEqual(REPLACE_CONFIRM, "replace-unpublished-voice-038-v1")
        with self.assertRaises(LoadProdError) as ctx:
            _reject_unpublished_snapshot(None)
        self.assertEqual(str(ctx.exception), "replace_unpublished_not_allowed")


if __name__ == "__main__":
    unittest.main()
