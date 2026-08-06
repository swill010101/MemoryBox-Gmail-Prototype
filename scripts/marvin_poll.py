#!/usr/bin/env python3
"""Poll Gmail once and process Marvin Capture replies."""
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
from marvin_capture.service import get_gmail_client, poll_once  # noqa: E402
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--no-transcribe", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    cfg = cfgmod.ensure_runtime_dirs()
    if args.fake:
        cfg["use_fake_gmail"] = True

    client = get_gmail_client(cfg, fake=args.fake)
    with store.db_session(cfg["sqlite_path"]) as conn:
        results = poll_once(conn, client, cfg)
        tx = []
        if not args.no_transcribe:
            tx = process_pending_transcriptions(conn, cfg["whisper"])
        print(json.dumps({"processed": results, "transcriptions": tx}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
