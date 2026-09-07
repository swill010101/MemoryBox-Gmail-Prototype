import runpy
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
M=runpy.run_path(str(ROOT/'docs/implementation/p2-i13-stage-a/prepare-eugene-t1-retirement.py'))
validate=M['validate_candidate']
GOOD={'state':'stopped','stale':False,'training_key':'T1','person_id':'b67708d8-0262-404d-a230-2cc99900cea4','annotation_active':True,'retired':False,'outcomes':[{'key':'H1'},{'key':'O1'},{'key':'U1-clear'}]}
class RetirementPreflight(unittest.TestCase):
    def test_exact_current_t1_is_eligible(self):
        self.assertEqual(validate(GOOD)['training_key'],'T1')
    def test_stale_or_shared_or_changed_candidate_rejected(self):
        for change in ({'stale':True},{'training_key':'T2'},{'retired':True},{'outcomes':[{'key':'N1'}]}):
            row=dict(GOOD);row.update(change)
            with self.assertRaises(RuntimeError): validate(row)
