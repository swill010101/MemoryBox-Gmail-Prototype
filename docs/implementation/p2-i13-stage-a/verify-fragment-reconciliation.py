"""Post-correction read-only verification for legacy HVRT fragment reconciliation gate."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybox.recognition.fragment_reconciliation import (  # noqa: E402
    approved_source_runs,
    load_allowlist,
    preview_projection,
)


def main() -> int:
    inv_path = os.environ.get("MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON", "").strip()
    if not inv_path:
        print(json.dumps({"ok": False, "error": "Set MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON"}))
        return 2
    inv = json.loads(Path(inv_path).read_text(encoding="utf-8"))
    eligible = [r for r in inv.get("rows", []) if r.get("eligible_for_reconciliation")]
    preview = preview_projection(eligible)
    allowlist = load_allowlist()
    checks = {
        "allowlist_loaded": bool(allowlist.get("approved_source_runs")),
        "review_reference_present": bool(str(allowlist.get("review_reference") or "").strip()),
        "manifest_scoped_only": allowlist.get("manifest_id") == "p2-i13-flightsim-22",
        "no_archive_claim": "archive" not in json.dumps(allowlist).lower(),
        "suppression_non_negative": preview["suppressed_duplicate_presentations"] >= 0,
        "moments_preserved": preview["retained_moment_rows"] == preview["eligible_fragment_rows"],
        "cards_reduced": preview["after_source_cards"] <= preview["before_gallery_cards"],
        "approved_pairs": len(approved_source_runs()),
    }
    report = {
        "ok": all(checks.values()),
        "read_only": True,
        "checks": checks,
        "preview": preview,
        "live_gallery_proof_required": "Owner verifies representative Gallery/retrieval on FlightSim after deploy",
        "limits": "Does not exercise rendered UI; attach browser-fragment-proof.json and owner notes for acceptance",
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
