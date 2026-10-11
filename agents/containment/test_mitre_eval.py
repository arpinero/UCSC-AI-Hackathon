import unittest
from agent import validate_incident
import copy
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import mitre_eval
from mitre_eval import dataset, score

class MitreEvaluationTests(unittest.TestCase):
    def test_resume_preserves_completed_failures_and_successes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run.json'
            prefix = [{'incident_id': dataset()[0][2]['incident_id'], 'status': 'rejected', 'scenario_pass': False},
                      {'incident_id': dataset()[1][2]['incident_id'], 'status': 'validated', 'scenario_pass': True,
                       'model': 'fdtn-ai/Foundation-Sec-8B-Instruct'}]
            output.write_text(json.dumps({'results': prefix}))
            result = {'status': 'validated', 'model': 'fdtn-ai/Foundation-Sec-8B-Instruct', 'proposal': {'actions': []}}
            with patch('sys.argv', ['mitre_eval.py', '--resume', '--output', str(output)]), \
                 patch('mitre_eval.propose', side_effect=lambda *a, **k: copy.deepcopy(result)) as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                mitre_eval.main()
            saved = json.loads(output.read_text())
            self.assertEqual(saved['results'][:2], prefix)
            self.assertEqual(call.call_count, 19)
            self.assertTrue(saved['resume_notes'][0]['legacy_checkpoint_without_config'])

    def test_resume_rejects_configuration_change(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run.json'
            output.write_text(json.dumps({'results': [], 'config': {'model': 'changed'}}))
            with patch('sys.argv', ['mitre_eval.py', '--resume', '--output', str(output)]), self.assertRaises(RuntimeError):
                mitre_eval.main()
    def test_invalid_policy_and_evidence_types_are_rejected_before_inference(self):
        incident = dataset()[0][2]
        mutations = [lambda i: i['policy'].update(allow_critical_isolation='false'),
                     lambda i: i['policy'].update(max_ttl_minutes=True),
                     lambda i: i['policy'].update(required_preserve_channels=['unavailable']),
                     lambda i: i['evidence'][0].update(id=42),
                     lambda i: i['evidence'][0].update(source_host_ids=['unknown'])]
        for mutate in mutations:
            candidate = copy.deepcopy(incident)
            mutate(candidate)
            with self.assertRaises(ValueError):
                validate_incident(candidate)
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
