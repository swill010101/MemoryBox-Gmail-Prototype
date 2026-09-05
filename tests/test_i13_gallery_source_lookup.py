import importlib.util
from pathlib import Path
import unittest
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("source_lookup",ROOT/"docs/implementation/p2-i13-stage-a/identify-gallery-sources.py")
lookup=importlib.util.module_from_spec(spec);spec.loader.exec_module(lookup)

class LookupTests(unittest.TestCase):
    def test_fixed_scope_valid_and_unique(self):
        self.assertEqual(len(lookup.IDS),47)
        self.assertEqual(len(set(map(UUID,lookup.IDS))),47)

    def test_group_sources_and_report_unmatched_without_inventing_files(self):
        rows=[dict(id=lookup.IDS[0],video_provider_key="hvrt",video_external_id="a",start_sec=.5),
              dict(id=lookup.IDS[1],video_provider_key="hvrt",video_external_id="a",start_sec=10.5),
              dict(id=lookup.IDS[2],video_provider_key="hvrt",video_external_id="b",start_sec=.5)]
        result=lookup.summarize(rows,[dict(provider_key="hvrt",video_external_id="a",relative_path="synthetic.mp4",duration_sec=20)])
        self.assertEqual(result["matched_card_ids"],3)
        self.assertEqual(len(result["unmatched_card_ids"]),44)
        self.assertEqual(len(result["sources"]),2)
        self.assertEqual(len(result["sources"][0]["moments"]),2)
        self.assertEqual(result["sources"][0]["manifest_filename"],"synthetic.mp4")
        self.assertIsNone(result["sources"][1]["manifest_filename"])
        self.assertFalse(result["sources"][1]["in_manifest"])

    def test_unrequested_or_wrong_provider_rejected(self):
        for mid,provider in [(str(UUID(int=1)),"hvrt"),(lookup.IDS[0],"immich")]:
            with self.assertRaises(ValueError):
                lookup.summarize([dict(id=mid,video_provider_key=provider,video_external_id="a")],[])

if __name__=="__main__":unittest.main()
