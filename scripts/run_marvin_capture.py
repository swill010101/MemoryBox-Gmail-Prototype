#!/usr/bin/env python3
"""Run Marvin Capture review UI (and optional background poll loop).

  python scripts/run_marvin_capture.py
  python scripts/run_marvin_capture.py --poll
  python scripts/run_marvin_capture.py --fake
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.service import (  # noqa: E402
    get_gmail_client,
    poll_once,
    send_daily_journal_if_due,
)
from marvin_capture.whisper_client import process_pending_transcriptions  # noqa: E402


def worker_loop(cfg: dict, *, fake: bool, stop: threading.Event) -> None:
    log = logging.getLogger("marvin.worker")
    interval = int(cfg.get("polling_interval_seconds") or 300)
    while not stop.is_set():
        try:
            with store.db_session(cfg["sqlite_path"]) as conn:
                client = get_gmail_client(cfg, fake=fake)
                send_daily_journal_if_due(conn, client, cfg)
                results = poll_once(conn, client, cfg)
                tx = process_pending_transcriptions(conn, cfg["whisper"])
                if results or tx:
                    log.info("poll: %s captures, %s transcriptions", len(results), len(tx))
        except Exception:  # noqa: BLE001
            log.exception("worker iteration failed")
        stop.wait(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Marvin Capture review UI")
    parser.add_argument("--poll", action="store_true", help="Run background poll/send worker")
    parser.add_argument("--fake", action="store_true", help="Use FakeGmailClient")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = cfgmod.ensure_runtime_dirs()
    if args.fake:
        cfg["use_fake_gmail"] = True

    stop = threading.Event()
    thread = None
    if args.poll:
        thread = threading.Thread(
            target=worker_loop,
            args=(cfg,),
            kwargs={"fake": args.fake, "stop": stop},
            daemon=True,
        )
        thread.start()

    import uvicorn

    host = args.host or cfg["review_ui"]["host"]
    port = args.port or int(cfg["review_ui"]["port"])
    try:
        uvicorn.run(
            "marvin_capture.app:app",
            host=host,
            port=port,
            reload=False,
            app_dir=str(ROOT / "application"),
        )
    finally:
        stop.set()
        if thread:
            thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
