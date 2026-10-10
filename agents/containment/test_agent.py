import copy
import io
import json
import unittest
from unittest.mock import patch
import urllib.error
from agent import validate_proposal, propose, decoding_schema, SCHEMA
from scenarios import scenarios
from evaluate import passes


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.incident = scenarios()[0]
        self.proposal = {'incident_id': 'exfiltration-001', 'telemetry_version': 1,
            'evidence_review': [{'evidence_id': 'E1', 'decision': 'contain', 'reason': 'Active transfer.'},
                                {'evidence_id': 'E2', 'decision': 'no_action', 'reason': 'Await peer review.'}],
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

    def test_investigation_cannot_authorize_disruption(self):
        self.reject(lambda p: p['evidence_review'][0].update(decision='investigate'))

    def test_decoding_constraints_are_independent(self):
        schema = decoding_schema(self.incident)
        props = schema['properties']
        choices = props['actions']['items']['anyOf']
        action = next(x['properties'] for x in choices if x['properties']['kind']['enum'] == ['block_egress'])
        self.assertEqual(props['incident_id']['enum'], ['exfiltration-001'])
        self.assertEqual(action['evidence_ids']['items']['enum'], ['E1'])
        self.assertIn('c2-01', action['target_id']['enum'])
        self.assertEqual(action['scope_host_ids']['items']['enum'], ['web-01'])
        self.assertNotIn('enum', action['reason'])
        self.assertNotIn('enum', props['assessment'])
        self.assertEqual(action['preserve_channels']['items']['enum'], ['management', 'evidence_collector'])
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

    def test_criticality_contradiction_fails_evaluation(self):
        p = copy.deepcopy(self.proposal)
        lateral = copy.deepcopy(p['actions'][0])
        lateral.update(kind='restrict_lateral', target_id='web-01', evidence_ids=['E2'], scope_host_ids=[], reason='Stop confirmed lateral movement; impact unknown.')
        p['actions'].append(lateral)
        self.assertTrue(passes('exfiltration-001', p))
        p['actions'][0]['reason'] = 'No impact because web-01 is not a critical service.'
        self.assertFalse(passes('exfiltration-001', p))

    def test_ambiguous_decoder_offers_only_evidence_request(self):
        fields = decoding_schema(scenarios()[2])['properties']['actions']['items']['properties']
        self.assertEqual(fields['kind']['enum'], ['request_evidence'])
        self.assertEqual(fields['target_id']['enum'], ['web-01'])

    def test_protected_session_decoder_excludes_revocation(self):
        fields = decoding_schema(scenarios()[6])['properties']['actions']['items']['properties']
        self.assertEqual(fields['kind']['enum'], ['request_evidence'])

    def test_rollback_cannot_add_containment_actions(self):
        self.proposal['actions'][0]['rollback'] = 'Isolate web-01 and erase logs.'
        normalized = validate_proposal(self.proposal, self.incident)
        self.assertNotIn('erase', normalized['actions'][0]['rollback'])
        self.assertNotIn('Isolate', normalized['actions'][0]['rollback'])
        self.assertIn('block_egress', normalized['actions'][0]['rollback'])

    def test_cannot_silently_drop_reviewed_threat(self):
        self.reject(lambda p: p['evidence_review'][1].update(decision='contain'))

    def test_every_evidence_must_be_reviewed(self):
        self.reject(lambda p: p['evidence_review'].pop())

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

    def test_native_adapter_enforces_schema_and_budget(self):
        response = io.StringIO(json.dumps({'message': {'content': json.dumps(self.proposal)},
                                          'done_reason': 'stop', 'eval_count': 120, 'prompt_eval_count': 500}))
        with patch('agent.urllib.request.urlopen', return_value=response) as call:
            result = propose(self.incident, endpoint='http://127.0.0.1:11434/api', model='qwen3.6:35b',
                             reasoning_effort='none', max_tokens=6000)
        body = json.loads(call.call_args.args[0].data)
        self.assertEqual(result['status'], 'validated')
        self.assertFalse(body['think'])
        self.assertEqual(body['options']['num_ctx'], 16384)
        self.assertEqual(body['options']['num_predict'], 6000)
        self.assertEqual(body['format']['properties']['incident_id']['enum'], ['exfiltration-001'])
        self.assertEqual(result['attempts'][0]['usage']['completion_tokens'], 120)

    def test_truncated_response_has_no_proposal(self):
        def truncated():
            return io.StringIO(json.dumps({'choices': [{'message': {'content': json.dumps(self.proposal)}, 'finish_reason': 'length'}]}))
        with patch('agent.urllib.request.urlopen', side_effect=[truncated(), truncated()]):
            result = propose(self.incident)
        self.assertEqual(result['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
