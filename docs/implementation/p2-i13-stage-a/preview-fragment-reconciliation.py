"""Read-only reconciliation preview for legacy HVRT fragment Gallery presentation.

Uses inventory output or live DB. Shows proposed source-card grouping, retained
moments, suppressed duplicate presentations and before/after counts. No writes.
"""
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
    if not inv_path and not os.environ.get("MEMORYBOX_DATABASE_URL", "").strip():
        print(json.dumps({"ok": False, "error": "Set MEMORYBOX_I13_FRAGMENT_INVENTORY_JSON or MEMORYBOX_DATABASE_URL"}))
        return 2
    if inv_path:
        inv = json.loads(Path(inv_path).read_text(encoding="utf-8"))
        eligible = [r for r in inv.get("rows", []) if r.get("eligible_for_reconciliation")]
    else:
        import subprocess

        proc = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).with_name("inventory-legacy-hvrt-fragments.py"))],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stdout or proc.stderr)
            return proc.returncode
        inv = json.loads(proc.stdout)
        eligible = [r for r in inv.get("rows", []) if r.get("eligible_for_reconciliation")]
    preview = preview_projection(eligible)
    allowlist = load_allowlist()
    report = {
        "ok": True,
        "read_only": True,
        "gate": "legacy-hvrt-fragment-reconciliation",
        "policy": preview["policy"],
        "current_allowlist_pairs": len(approved_source_runs()),
        "allowlist_review_reference": allowlist.get("review_reference"),
        "preview": preview,
        "founder_review_required_before_apply": True,
        "apply_procedure": "publish-fragment-allowlist.py after founder sign-off on this preview",
        "limits": [
            "Presentation-layer only; underlying face_appearance_moments unchanged",
            "Manifest-scoped; not archive-wide",
            "Meaningful timing gaps preserved as separate moments inside a source card",
        ],
    }
    out = os.environ.get("MEMORYBOX_I13_FRAGMENT_PREVIEW_OUTPUT", "").strip()
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["output_file"] = str(path)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
