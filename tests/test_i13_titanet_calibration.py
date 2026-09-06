import unittest
from memorybox.processing.titanet_calibration import MATCH, UNCERTAIN, decision, report

class TitaNetCalibrationTests(unittest.TestCase):
    def test_frozen_abstention_policy(self):
        self.assertEqual((UNCERTAIN, MATCH), (.30, .45))
        self.assertEqual(decision(.2999), "no_match")
        self.assertEqual(decision(.30), "uncertain")
        self.assertEqual(decision(.4499), "uncertain")
        self.assertEqual(decision(.45), "match")

    def test_public_sample_tradeoff(self):
        result = report([.377, .536, .777, .892], [-.278, .223, .307, .325])
        self.assertEqual(result["same_by_decision"], {"match": 3, "uncertain": 1, "no_match": 0})
        self.assertEqual(result["different_by_decision"], {"match": 0, "uncertain": 2, "no_match": 2})

    def test_missing_or_nonfinite_scores_rejected(self):
        for positive, negative in (([], [.1]), ([.1], []), ([float("nan")], [.1])):
            with self.assertRaises(ValueError):
                report(positive, negative)
