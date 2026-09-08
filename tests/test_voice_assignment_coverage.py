import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "docs/implementation/p2-i13-stage-a/inspect-voice-assignment-coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("inspect_voice_assignment_coverage", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VoiceAssignmentCoverageTests(unittest.TestCase):
    def test_canonical_eight_covers_all_categories_without_conflicts(self):
        mod = _load()
        report = mod.build_report(db_active=None)
        self.assertTrue(report["ok"])
        self.assertEqual(report["training_held_out_conflicts"], [])
        self.assertEqual(report["missing_categories"], [])
        self.assertEqual(report["smallest_next_pilot"], "none_required")
        self.assertFalse(report["additional_annotation_required"])
        self.assertEqual(len(report["assignments"]), 8)
        categories = {row["category"] for row in report["category_coverage"]}
        self.assertEqual(categories, set(mod.CATEGORIES))

    def test_each_category_has_current_pilot_evidence(self):
        mod = _load()
        report = mod.build_report(db_active=None)
        for row in report["category_coverage"]:
            self.assertTrue(row["satisfied"])
            self.assertTrue(row["current_pilot_evidence"])


if __name__ == "__main__":
    unittest.main()
