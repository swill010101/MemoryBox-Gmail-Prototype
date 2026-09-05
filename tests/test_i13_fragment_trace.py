"""Read-only trace tests and reproduction using actual pure grouping functions."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from memorybox.recognition import constants
from memorybox.providers.video.merge import merge_presence_spans, RawDetection

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("trace_source",ROOT/"docs/implementation/p2-i13-stage-a/trace-source-fragments.py")
trace=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(trace)


def pure(relative,name):
    tree=ast.parse((ROOT/relative).read_text(encoding="utf-8"))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace=dict(vars(constants))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),node],type_ignores=[])),relative,"exec"),namespace)
    return namespace[name]


def reproduce():
    sample=pure("memorybox/recognition/frames.py","sample_times")
    group=pure("memorybox/recognition/observations.py","group_assigned_into_ranges")
    times=sample(1105.104)
    observations=[{"id":str(i),"person_id":"synthetic-person","review_state":"assigned","t_sec":t,"match_score":0.9} for i,t in enumerate(times)]
    ranges=group(observations)
    return {"source_duration_for_cadence":1105.104,"synthetic_all_samples_assigned":True,
            "sample_count":len(times),"sample_gap_sec":times[1]-times[0],"last_sample_sec":times[-1],
            "native_group_gap_sec":constants.RANGE_GAP_SEC,"native_ranges":len(ranges),
            "range_durations_sec":sorted({r["end_sec"]-r["start_sec"] for r in ranges}),
            "limits":"Actual pure sampler/grouper, synthetic observations; no media/models/runtime. Not proof that these are the 15 live entries."}


class FragmentTraceTests(unittest.TestCase):
    def test_sampler_grouper_cadence_mismatch_reproduced(self):
        result=reproduce()
        self.assertEqual(result["sample_gap_sec"],10)
        self.assertEqual(result["native_group_gap_sec"],8)
        self.assertEqual(result["native_ranges"],result["sample_count"])
        self.assertEqual(result["range_durations_sec"],[0.5])

    def test_worker_groups_by_candidate_not_displayed_person(self):
        same=[RawDetection("same",i*10,i*10+1) for i in range(15)]
        different=[RawDetection(str(i),i*10,i*10+1) for i in range(15)]
        self.assertEqual(len(merge_presence_spans(same)),1)
        self.assertEqual(len(merge_presence_spans(different)),15)

    def test_export_omits_other_sources_and_sensitive_fields(self):
        with tempfile.TemporaryDirectory(prefix="i13-trace-test-") as tmp:
            root=Path(tmp).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            p=root/"detections.json"
            p.write_text(json.dumps({"detections":[{"video_external_id":trace.VID,"t_sec":1,"label":"private","embedding":[1,2]}, {"video_external_id":"other","t_sec":2}]}),encoding="utf-8")
            result=trace.derived_trace(p)
            self.assertEqual(result["source_rows"],1)
            self.assertNotIn("label",result["rows"][0])
            self.assertNotIn("embedding",result["rows"][0])

    def test_summary_preserves_person_partition_and_short_range_counts(self):
        rows=[{"person_id":"a","start_sec":0,"end_sec":0.5},{"person_id":"b","start_sec":0,"end_sec":100}]
        out=trace.temporal_summary(rows)
        self.assertEqual(out["a"]["durations_at_most_2_sec"],1)
        self.assertEqual(out["b"]["durations_at_most_2_sec"],0)


if __name__=="__main__":unittest.main()
