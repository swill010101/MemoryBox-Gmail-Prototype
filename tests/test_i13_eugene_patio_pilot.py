import json
import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / 'docs/implementation/p2-i13-stage-a/prepare-eugene-patio-voice-pilot.py'))
load_selection = MODULE['load_selection']
validate_rows = MODULE['validate_rows']

class EugenePatioPilotProposal(unittest.TestCase):
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

    def test_exact_bounded_shape(self):
        proposal, rows = self.rows()
        result = validate_rows(proposal, rows)
        self.assertEqual(result['work_items'], 4)
        self.assertEqual(result['audio_seconds'], 49.66)
        self.assertTrue(result['patio_annotations_fresh'])

    def test_postgres_float_representation_of_first_patio_time_is_accepted(self):
        proposal, rows = self.rows()
        rows[0]['t_start'] = 15.939999999999998
        self.assertTrue(validate_rows(proposal, rows)['patio_annotations_fresh'])
    def test_patio_rows_must_remain_fresh_active_eugene(self):
        proposal, rows = self.rows()
        rows[0]['pilot_uses'] = [{'admission_id': 'old'}]
        with self.assertRaisesRegex(RuntimeError, 'fresh'):
            validate_rows(proposal, rows)
        proposal, rows = self.rows()
        rows[1]['active'] = False
        with self.assertRaisesRegex(RuntimeError, 'active'):
            validate_rows(proposal, rows)

    def test_controls_cannot_change_identity(self):
        proposal, rows = self.rows()
        rows[2]['person_id'] = 'b67708d8-0262-404d-a230-2cc99900cea4'
        with self.assertRaisesRegex(RuntimeError, 'Tom negative'):
            validate_rows(proposal, rows)
        proposal, rows = self.rows()
        rows[3]['speaker_state'] = 'person'
        with self.assertRaisesRegex(RuntimeError, 'Unknown negative'):
            validate_rows(proposal, rows)

if __name__ == '__main__':
    unittest.main()
