import runpy
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
M=runpy.run_path(str(ROOT/'docs/implementation/p2-i13-stage-a/inspect-eugene-reprocessing-candidates.py'))
classify=M['classify']
BASE={'annotation_id':'a','version_id':'v','provider_key':'hvrt','source_id':'s','t_start':1,'t_end':3,'words':4,'reason':'Owner review','retired':False,'pilot_uses':[]}
class EugeneReprocessCandidates(unittest.TestCase):
    def test_unused_active_annotation_is_fresh(self):
        self.assertTrue(classify(dict(BASE))['eligible_fresh_reference'])
    def test_owner_excluded_source_is_not_fresh(self):
        row=dict(BASE);row['source_id']='vid-c57dbd21f993f6d1'
        self.assertFalse(classify(row)['eligible_fresh_reference'])
    def test_retired_or_previously_used_reference_is_not_fresh(self):
        for change in ({'retired':True},{'pilot_uses':[{'admission_id':'old','key':'H1','role':'held_out'}]}):
            row=dict(BASE);row.update(change)
            self.assertFalse(classify(row)['eligible_fresh_reference'])
