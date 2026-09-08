"""Publish reviewed manifest-scoped allowlist after founder preview sign-off.

Updates memorybox/recognition/data/legacy_hvrt_fragment_allowlist.json only.
Does not delete source evidence, observations or media.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST = ROOT / "memorybox/recognition/data/legacy_hvrt_fragment_allowlist.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="inventory-legacy-hvrt-fragments.json path")
    parser.add_argument("--reference", required=True, help="Founder review reference string")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    inv = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    proposed = inv.get("proposed_allowlist_extensions") or []
    if not proposed:
        print(json.dumps({"ok": False, "error": "inventory has no proposed_allowlist_extensions"}))
        return 2
    payload = {
        "policy": "i13-legacy-hvrt-fragment-v1",
        "manifest_id": inv.get("manifest_id", "p2-i13-flightsim-22"),
        "review_reference": args.reference,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "limits": "Manifest-scoped presentation reconciliation only. Not archive-wide.",
        "approved_source_runs": [
            {
                "video_external_id": row["video_external_id"],
                "processing_run_id": row["processing_run_id"],
                "relative_path": row.get("relative_path"),
                "moment_count": row.get("moment_count"),
            }
            for row in proposed
        ],
    }
    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "would_write": str(ALLOWLIST), "payload": payload}, indent=2))
        return 0
    ALLOWLIST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "written": str(ALLOWLIST), "pair_count": len(payload["approved_source_runs"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
