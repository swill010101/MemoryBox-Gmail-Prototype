#!/usr/bin/env python3
"""Force a MEM bank scheduler tick (for testing)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.mem_bank import tick_mem_bank  # noqa: E402
from marvin_capture.service import get_gmail_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--force", action="store_true", default=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = cfgmod.ensure_runtime_dirs()
    if args.fake:
        cfg["use_fake_gmail"] = True
    client = get_gmail_client(cfg, fake=args.fake)
    with store.db_session(cfg["sqlite_path"]) as conn:
        result = tick_mem_bank(conn, client, cfg, force=args.force)
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
