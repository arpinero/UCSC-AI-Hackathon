import unittest
from agent import validate_incident
from mitre_eval import dataset, score

class MitreEvaluationTests(unittest.TestCase):
    def test_fixture_validity_and_counterfactuals(self):
        cases = dataset()
        self.assertEqual(len(cases), 21)
        for _, _, incident, _ in cases:
            validate_incident(incident)
        for i in range(0, 20, 2):
            confirmed, authorized = cases[i], cases[i + 1]
            self.assertEqual(confirmed[2]['evidence'][0]['actionable_for'],
                             authorized[2]['evidence'][0]['actionable_for'])
            self.assertNotIn('expected', confirmed[2])

    def test_rejection_is_not_effectiveness_success(self):
        self.assertFalse(score('authorized', [], {'status': 'rejected'}))

    def test_false_positive_and_missing_chain_control_fail(self):
        result = {'status': 'validated', 'proposal': {'actions': [
            {'kind': 'block_egress', 'target_id': 'c2-01'}]}}
        self.assertFalse(score('authorized', [], result))
        self.assertFalse(score('chain', [('block_egress', 'c2-01'), ('restrict_lateral', 'web-01')], result))
        self.assertTrue(score('confirmed', [('block_egress', 'c2-01')], result))

if __name__ == '__main__':
    unittest.main()
