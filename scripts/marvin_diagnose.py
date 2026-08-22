#!/usr/bin/env python3
"""Diagnose why a Marvin reply might not appear in the review UI."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture.gmail_client import build_live_gmail_client  # noqa: E402
from marvin_capture.reply_extract import parse_subject_tag  # noqa: E402


def main() -> int:
    cfg = cfgmod.ensure_runtime_dirs()
    db_path = Path(cfg["sqlite_path"])
    print("=== config ===")
    print(f"sqlite_path: {db_path.resolve()}")
    print(f"raw_email_storage: {Path(cfg['raw_email_storage']).resolve()}")
    print(f"user_email: {cfg['gmail'].get('user_email')!r}")
    print(f"processed_label: {cfg['gmail'].get('processed_label')!r}")
    print(f"credentials: {Path(cfg['gmail']['credentials_file']).exists()}")
    print(f"token: {Path(cfg['gmail']['token_file']).exists()}")

    print("\n=== database ===")
    if not db_path.is_file():
        print("DB missing — prompts/responses were never written here.")
    else:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        prompts = conn.execute("SELECT id, subject, gmail_message_id, gmail_thread_id, sent_date FROM prompt").fetchall()
        responses = conn.execute(
            "SELECT id, prompt_id, received_date, substr(response_text,1,80) AS text, reviewed FROM response"
        ).fetchall()
        print(f"prompts: {len(prompts)}")
        for p in prompts:
            print(dict(p))
        print(f"responses: {len(responses)}")
        for r in responses:
            print(dict(r))
        conn.close()

    unmatched = Path(cfg["raw_email_storage"]) / "unmatched"
    print("\n=== unmatched raw mail ===")
    if unmatched.is_dir():
        files = list(unmatched.glob("*.eml"))
        print(f"{len(files)} file(s) in {unmatched.resolve()}")
        for f in files[:10]:
            print(f"  {f.name}")
    else:
        print("none")

    print("\n=== gmail search (live) ===")
    try:
        client = build_live_gmail_client(cfg)
        label = cfg["gmail"].get("processed_label") or "MB/Processed"
        label_q = label.replace("/", "-")
        queries = [
            f'in:inbox -label:{label_q} (subject:[MB- OR subject:"[MB-")',
            f"in:inbox -label:{label_q}",
            "in:inbox subject:MB-JRN",
            "in:anywhere subject:MB-JRN newer_than:2d",
        ]
        for q in queries:
            result = (
                client.service.users()
                .messages()
                .list(userId="me", q=q, maxResults=10)
                .execute()
            )
            msgs = result.get("messages") or []
            print(f"\nquery: {q}")
            print(f"  hits: {len(msgs)}")
            for m in msgs[:5]:
                meta = client.get_message_metadata(m["id"])
                tag = parse_subject_tag(meta.get("subject"))
                print(
                    json.dumps(
                        {
                            "id": m["id"],
                            "threadId": meta.get("threadId"),
                            "subject": meta.get("subject"),
                            "from": meta.get("from"),
                            "tag": tag.prompt_id if tag else None,
                            "labels": meta.get("labelIds"),
                        },
                        default=str,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        print(f"Gmail probe failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
