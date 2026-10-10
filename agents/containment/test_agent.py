import copy
import io
import json
import unittest
from unittest.mock import patch
import urllib.error
from agent import validate_proposal, propose, decoding_schema, SCHEMA
from scenarios import scenarios


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.incident = scenarios()[0]
        self.proposal = {'incident_id': 'exfiltration-001', 'telemetry_version': 1,
            'assessment': 'Active exfiltration.', 'actions': [{
                'kind': 'block_egress', 'target_id': 'c2-01', 'evidence_ids': ['E1'],
                'scope_host_ids': ['web-01'],
                'reason': 'Stop confirmed transfer with no full host outage.', 'ttl_minutes': 15,
                'preserve_channels': ['management', 'evidence_collector'],
                'rollback': 'Remove the destination block after verified threat removal.'}],
            'uncertainties': [], 'peer_responses': [], 'review_after_seconds': 30}

    def reject(self, mutate):
        p = copy.deepcopy(self.proposal)
        mutate(p)
        with self.assertRaises(ValueError):
            validate_proposal(p, self.incident)

    def test_valid(self):
        validate_proposal(self.proposal, self.incident)

    def test_decoding_constraints_are_independent(self):
        schema = decoding_schema(self.incident)
        props = schema['properties']
        action = props['actions']['items']['properties']
        self.assertEqual(props['incident_id']['enum'], ['exfiltration-001'])
        self.assertEqual(action['evidence_ids']['items']['enum'], ['E1', 'E2'])
        self.assertIn('c2-01', action['target_id']['enum'])
        self.assertEqual(action['scope_host_ids']['items']['enum'], ['web-01', 'workstation-01'])
        self.assertNotIn('enum', action['reason'])
        self.assertNotIn('enum', props['assessment'])
        self.assertNotIn('enum', action['preserve_channels']['items'])
        self.assertNotIn('enum', SCHEMA['properties']['incident_id'])

    def test_stale(self):
        self.reject(lambda p: p.update(telemetry_version=2))

    def test_invented_evidence(self):
        self.reject(lambda p: p['actions'][0].update(evidence_ids=['E999']))

    def test_unrelated_real_evidence(self):
        self.reject(lambda p: p['actions'][0].update(evidence_ids=['E2']))

    def test_protected_destination(self):
        self.reject(lambda p: p['actions'][0].update(target_id='collector-01'))

    def test_missing_channel(self):
        self.reject(lambda p: p['actions'][0].update(preserve_channels=['management']))

    def test_critical_isolation(self):
        self.reject(lambda p: p['actions'][0].update(kind='isolate_host', target_id='web-01'))

    def test_ttl(self):
        self.reject(lambda p: p['actions'][0].update(ttl_minutes=31))

    def test_shell_action(self):
        self.reject(lambda p: p['actions'][0].update(kind='shell'))

    def test_wrong_target_type(self):
        self.reject(lambda p: p['actions'][0].update(target_id='web-01'))

    def test_duplicate(self):
        self.reject(lambda p: p['actions'].append(copy.deepcopy(p['actions'][0])))

    def test_extra_field(self):
        self.reject(lambda p: p.update(shell='rm -rf /'))

    def test_unrelated_source_host(self):
        self.reject(lambda p: p['actions'][0].update(scope_host_ids=['workstation-01']))

    def test_global_egress_block(self):
        self.reject(lambda p: p['actions'][0].update(scope_host_ids=[]))

    def test_repair_unsupported_action(self):
        bad = copy.deepcopy(self.proposal)
        bad['actions'][0]['evidence_ids'] = ['E999']
        def response(p):
            return io.StringIO(json.dumps({'choices': [{'message': {'content': json.dumps(p)}, 'finish_reason': 'stop'}]}))
        with patch('agent.urllib.request.urlopen', side_effect=[response(bad), response(self.proposal)]) as call:
            result = propose(self.incident)
        self.assertEqual(result['status'], 'validated')
        self.assertEqual(call.call_count, 2)
        self.assertIn('validation_error', result['attempts'][0])

    def test_persistent_failure_has_no_proposal(self):
        def bad():
            return io.StringIO(json.dumps({'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}))
        with patch('agent.urllib.request.urlopen', side_effect=[bad(), bad()]):
            result = propose(self.incident)
        self.assertEqual(result['status'], 'rejected')
        self.assertIsNone(result['proposal'])

    def test_outage_has_no_proposal(self):
        with patch('agent.urllib.request.urlopen', side_effect=urllib.error.URLError('offline')):
            result = propose(self.incident)
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['proposal'])

    def test_truncated_response_has_no_proposal(self):
        def truncated():
            return io.StringIO(json.dumps({'choices': [{'message': {'content': json.dumps(self.proposal)}, 'finish_reason': 'length'}]}))
        with patch('agent.urllib.request.urlopen', side_effect=[truncated(), truncated()]):
            result = propose(self.incident)
        self.assertEqual(result['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
