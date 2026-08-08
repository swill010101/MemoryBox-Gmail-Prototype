#!/usr/bin/env python3
"""Send a Marvin Capture prompt via Gmail (or --fake)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.service import get_gmail_client, send_daily_journal_if_due, send_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", action="store_true", help="Send today's journal prompt")
    parser.add_argument("--type", default="MEM", help="Prompt type e.g. MEM, JRN")
    parser.add_argument(
        "--token",
        default="",
        help="Optional legacy token (prefer tokenless [MB-TYPE] subjects)",
    )
    parser.add_argument("--headline", default="")
    parser.add_argument("--body", default="Tell me more.")
    parser.add_argument("--to", default=None)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    cfg = cfgmod.ensure_runtime_dirs()
    if args.fake:
        cfg["use_fake_gmail"] = True

    client = get_gmail_client(cfg, fake=args.fake)
    with store.db_session(cfg["sqlite_path"]) as conn:
        if args.journal:
            result = send_daily_journal_if_due(conn, client, cfg, force=True)
        else:
            result = send_prompt(
                conn,
                client,
                cfg,
                prompt_type=args.type,
                token=args.token or "",
                headline=args.headline or args.body.split("\n", 1)[0][:80],
                body=args.body,
                to=args.to,
            )
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
