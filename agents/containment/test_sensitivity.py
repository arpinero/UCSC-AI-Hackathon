import unittest
from benchmark_cases import dataset, reference_proposal
from outcome_benchmark import run_case
from sensitivity_benchmark import replay, analyze


class SensitivityTests(unittest.TestCase):
    def fixture(self, family):
        case = next(c for c in dataset((17,)) if c['family'] == family)
        def predictor(incident, previous):
            refs = case['reference']
            for update in case['updates']:
                if incident['telemetry_version'] >= update['incident']['telemetry_version']:
                    refs = update['reference']
            return {'status': 'validated', 'proposal': reference_proposal(case, incident, refs),
                    'latency_seconds': 20, 'attempts': []}
        return case, run_case(case, predictor)

    def test_observed_replay_reproduces_effects(self):
        case, source = self.fixture('destination_rotation')
        self.assertEqual(replay(case, source)['outcomes'], source['outcomes'])

    def test_delay_increases_exfiltration(self):
        case, source = self.fixture('exfiltration')
        fast = replay(case, source, 0); slow = replay(case, source, 120)
        self.assertGreater(slow['outcomes']['bytes_lost'], fast['outcomes']['bytes_lost'])

    def test_expiry_allows_later_spread(self):
        case, source = self.fixture('lateral_smb')
        self.assertEqual(replay(case, source)['outcomes']['additional_hosts_compromised'], 0)
        self.assertGreater(replay(case, source, ttl_minutes=1)['outcomes']['additional_hosts_compromised'], 0)

    def test_late_replay_does_not_relabel_stale_evidence(self):
        case, source = self.fixture('destination_rotation')
        self.assertGreater(replay(case, source, 240)['outcomes']['policy_rejections'], 0)

    def test_missing_frozen_update_response_fails(self):
        case, source = self.fixture('destination_rotation')
        source['inference'] = source['inference'][:1]
        self.assertFalse(replay(case, source)['scenario_pass'])

    def test_reference_input_is_not_model_evidence(self):
        with self.assertRaisesRegex(ValueError, 'actual model'):
            analyze({'mode': 'reference'})


if __name__ == '__main__':
    unittest.main()
