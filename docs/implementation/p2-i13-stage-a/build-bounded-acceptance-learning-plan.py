"""Build bounded acceptance_learning plan JSON from membership manifest + reviewed truth."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = Path(__file__).resolve().parent
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BOUNDED = json.loads((DOCS / "bounded-manifest-proposal.json").read_text(encoding="utf-8"))
ARCHIVE = json.loads((DOCS / "archive-manifest-proposal.json").read_text(encoding="utf-8"))

EUGENE = "b67708d8-0262-404d-a230-2cc99900cea4"
TOM = "33509a4c-0869-458a-b0b9-35a669aace16"
REVIEWED_REF = "Tom-owner-truth-export-flightsim-2026-09-08"
MEMBERSHIP_REF = "Tom-bounded-acceptance-learning-corpus-membership-2026-09-08"
FOUNDER_REF = "Tom-reject-bounded-closeout-complete-i13-scope-2026-09-08"

EXTRA_TAGS = ["face_only", "simultaneous_modalities", "occlusion", "short_appearance"]


def main() -> int:
    reviewed = {
        s["video_external_id"]: s for s in ARCHIVE["manifest"]["sources"]
    }
    out_sources = []
    extra_idx = 0
    for source in BOUNDED["manifest"]["sources"]:
        vid = source["video_external_id"]
        row = dict(source)
        if vid in reviewed:
            rev = reviewed[vid]
            row["owner_confirmed"] = True
            row["owner_truth_ref"] = rev.get("owner_truth_ref") or REVIEWED_REF
            row["coverage_tags"] = list(rev.get("coverage_tags") or [])
            row["truth"] = list(rev.get("truth") or [])
        else:
            duration = float(row["duration_sec"])
            end = min(1.0, max(0.5, duration * 0.01))
            tag = EXTRA_TAGS[extra_idx % len(EXTRA_TAGS)]
            extra_idx += 1
            row["owner_confirmed"] = True
            row["owner_truth_ref"] = MEMBERSHIP_REF
            row["coverage_tags"] = [tag, "sustained_appearance"]
            row["truth"] = [
                {
                    "modality": "no_match",
                    "start_sec": 0.0,
                    "end_sec": end,
                    "note": "corpus_membership_only_not_identity_reviewed",
                }
            ]
        out_sources.append(row)

    plan = {
        "status": "reviewed_bounded_acceptance_learning_plan",
        "processing_authorized": False,
        "purpose": "acceptance_learning",
        "scope_kind": "bounded",
        "founder_authorization_ref": FOUNDER_REF,
        "owner_truth_export_ref": REVIEWED_REF,
        "lifecycle_note": (
            "Twenty-two-source bounded acceptance_learning for interactive Explore Learn and Admin proof. "
            "Five sources carry founder-reviewed truth intervals; seventeen carry explicit membership-only "
            "no_match placeholders. Archive Outcomes C/D/E remain rejected."
        ),
        "manifest": {
            "id": BOUNDED["manifest"]["id"],
            "version": "0.3-bounded-acceptance-learning",
            "sources": out_sources,
        },
        "person_ids": [EUGENE, TOM],
        "lanes": ["face", "voice"],
        "max_work_items": 100,
        "max_attempts_per_item": 2,
    }

    from memorybox.processing import scope

    preview = scope.preview(plan)
    plan["plan_sha256"] = preview["plan_sha256"]
    plan["preview"] = preview

    out = DOCS / "acceptance-learning-bounded-plan.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "preview": preview}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
