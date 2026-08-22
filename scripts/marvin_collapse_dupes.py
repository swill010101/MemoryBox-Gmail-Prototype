#!/usr/bin/env python3
"""Inspect + collapse duplicate Marvin Capture inbox rows.

Usage (from C:\\memorybox):
  python scripts/marvin_collapse_dupes.py
  python scripts/marvin_collapse_dupes.py --apply
  python scripts/marvin_collapse_dupes.py --apply --force-jrn
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture import db as store  # noqa: E402
from marvin_capture.db import auto_review_duplicate_bodies  # noqa: E402
from marvin_capture.reply_extract import normalize_for_dedupe  # noqa: E402


def force_collapse_jrn(conn) -> int:
    """Keep oldest unreviewed JRN; mark the rest reviewed."""
    rows = conn.execute(
        """
        SELECT r.id FROM response r
        JOIN prompt p ON p.id = r.prompt_id
        WHERE r.reviewed = 0 AND p.type = 'JRN'
        ORDER BY r.id ASC
        """
    ).fetchall()
    if len(rows) <= 1:
        return 0
    marked = 0
    for row in rows[1:]:
        store.mark_reviewed(conn, row["id"], reviewed=True)
        marked += 1
    return marked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mark newer near-duplicates reviewed (default is dry-run)",
    )
    parser.add_argument(
        "--force-jrn",
        action="store_true",
        help="With --apply: keep oldest unreviewed JRN only (nuclear)",
    )
    args = parser.parse_args()

    cfg = cfgmod.load_config()
    db_path = cfg["sqlite_path"]
    print(f"sqlite: {db_path}")
    conn = store.init_db(db_path)

    rows = conn.execute(
        """
        SELECT r.id, r.prompt_id, r.received_date, r.reviewed, r.gmail_message_id,
               r.gmail_thread_id, r.subject, length(r.response_text) AS nchars,
               substr(r.response_text, 1, 120) AS preview, r.response_text
        FROM response r
        WHERE r.reviewed = 0
        ORDER BY r.id ASC
        """
    ).fetchall()
    print(f"unreviewed inbox rows: {len(rows)}")
    for r in rows:
        print(
            f"  id={r['id']} prompt={r['prompt_id']} received={r['received_date']} "
            f"chars={r['nchars']} thread={r['gmail_thread_id']!r}"
        )
        print(f"    subject={r['subject']!r}")
        print(f"    preview={r['preview']!r}")

    by_prompt: dict[str, list] = {}
    for r in rows:
        by_prompt.setdefault(r["prompt_id"], []).append(r)
    print("\npairwise (same prompt_id):")
    for pid, group in by_prompt.items():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                na = normalize_for_dedupe(a["response_text"] or "")
                nb = normalize_for_dedupe(b["response_text"] or "")
                ratio = (
                    difflib.SequenceMatcher(None, na, nb).ratio() if (na or nb) else 0.0
                )
                same_thread = (a["gmail_thread_id"] or "") == (
                    b["gmail_thread_id"] or ""
                ) and bool(a["gmail_thread_id"])
                print(
                    f"  {pid}: id {a['id']} vs {b['id']}  ratio={ratio:.3f}  "
                    f"same_thread={same_thread}  chars={a['nchars']}/{b['nchars']}"
                )

    if not args.apply:
        marked = auto_review_duplicate_bodies(conn)
        print(f"\nDry-run only. would auto-review: {marked}")
        jrn_ids = conn.execute(
            """
            SELECT r.id FROM response r
            JOIN prompt p ON p.id = r.prompt_id
            WHERE r.reviewed = 0 AND p.type = 'JRN'
            """
        ).fetchall()
        print(f"would force-jrn mark: {max(0, len(jrn_ids) - 1)}")
        print("Re-run with --apply (optional --force-jrn) to collapse.")
        conn.rollback()
        conn.close()
        return 0

    marked = auto_review_duplicate_bodies(conn)
    forced = 0
    if args.force_jrn:
        forced = force_collapse_jrn(conn)
    conn.commit()
    left = conn.execute(
        "SELECT COUNT(*) AS c FROM response WHERE reviewed = 0"
    ).fetchone()["c"]
    print(f"\nauto-reviewed: {marked}")
    if args.force_jrn:
        print(f"force-jrn marked: {forced}")
    print(f"inbox remaining: {left}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
