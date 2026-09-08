import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / 'docs/implementation/p2-i13-stage-a/prepare-eugene-reprocessing-voice-pilot.py'))
load_selection = MODULE['load_selection']
validate_rows = MODULE['validate_rows']


class EugeneReprocessingPilotProposal(unittest.TestCase):
    def rows(self):
        proposal = load_selection()
        result = []
        for span in proposal['selections']:
            row = {
                'annotation_id': span['annotation_id'], 'version_id': span['version_id'],
                'source_id': span['source_id'], 'provider_key': span['provider_key'],
                't_start': span['start'], 't_end': span['end'], 'active': True,
                'retired': False, 'pilot_uses': [], 'speaker_state': 'person',
                'person_id': 'b67708d8-0262-404d-a230-2cc99900cea4',
            }
            if span['key'] == 'T2-as-Eugene-negative':
                row.update(person_id='33509a4c-0869-458a-b0b9-35a669aace16')
            if span['key'] == 'N1-TV-announcer-unknown':
                row.update(person_id=None, speaker_state='unknown')
            result.append(row)
        return proposal, result

    def test_bom_encoded_selection_is_loadable(self):
        self.assertEqual(load_selection()['selections'][0]['key'], 'R1-gs2-fresh')

    def test_exact_bounded_shape(self):
        proposal, rows = self.rows()
        result = validate_rows(proposal, rows)
        self.assertEqual(result['work_items'], 4)
        self.assertEqual(result['audio_seconds'], 39.52)
        self.assertTrue(result['gs2_annotations_fresh'])

    def test_gs2_rows_must_remain_fresh_active_eugene(self):
        proposal, rows = self.rows()
        rows[0]['pilot_uses'] = [{'admission_id': 'old'}]
        with self.assertRaisesRegex(RuntimeError, 'fresh'):
            validate_rows(proposal, rows)


if __name__ == '__main__':
    unittest.main()
