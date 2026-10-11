"""Offline safety and protocol regression suite. No model or GPU required."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from council import baseline, sources
from council.evaluate import metrics
from council.protocol import run
from council.report import save
from council.scenarios import dataset
from council.seats import Seats, ModelClient, local_url, validate_fixing, fixing_plan
from council.severity import assess


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = dataset()
        cls.by_id = {c.case_id: c for c in cls.cases}

    def test_schema_and_ground_truth_separation(self):
        for case in self.cases:
            with self.subTest(case=case.case_id):
                case.validate()
                encoded = json.dumps(case.context())
                for forbidden in ('fixing_truth', 'expected_alternatives', 'reference', 'expected', 'fault'):
                    self.assertNotIn('"' + forbidden + '"', encoded)

    def test_all_four_seats_accept_before_execution(self):
        result = run(self.by_id['mitre-T1041'])
        self.assertFalse(result['human_alert']['required'])
        self.assertTrue(result['decisions'])
        self.assertEqual(result['decisions'][0]['votes'], {r: 'support' for r in ('containment', 'forensics', 'compliance', 'fixing')})
        self.assertTrue(any(m['role'] == 'compliance' and m['stance'] == 'object' for m in result['transcript']))
        captures = [r for r in result['tool_receipts'] if r['kind'] == 'simulated_evidence_capture']
        self.assertTrue(captures)
        self.assertTrue(any(r['kind'] == 'simulated_restoration' for r in result['tool_receipts']))

    def test_containment_forensic_disagreement_and_revision(self):
        case = next(c for c in self.cases if c.expected.get('family') == 'exfiltration')
        result = run(case)
        self.assertTrue(any(m['role'] == 'forensics' and m['stance'] == 'object' for m in result['transcript']))
        self.assertEqual(result['containment']['actions'][0]['kind'], 'block_egress')
        self.assertEqual(result['outcomes']['additional_hosts_compromised'], 0)

    def test_authorized_no_false_positive(self):
        for case in self.cases:
            if case.expected['fixing_variant'] == 'authorized' and case.simulation['truth'] == 'benign':
                result = run(case)
                self.assertFalse(result['human_alert']['required'], case.case_id)
                self.assertEqual(result['outcomes']['false_positive_controls'], 0)
                self.assertEqual(result['fixing']['actions'], [])

    def test_legal_hold_veto_then_deferral(self):
        result = run(self.by_id['mitre-T1021-002'])
        self.assertEqual(result['status'], 'CONTAINED_RECOVERY_DEFERRED')
        self.assertTrue(any(m['role'] == 'compliance' and m['stance'] == 'veto' for m in result['transcript']))
        self.assertEqual(result['fixing']['actions'][0]['kind'], 'defer_restore')
        self.assertFalse(any(r['kind'] == 'simulated_restoration' for r in result['tool_receipts']))

    def test_binding_compliance_escalation(self):
        result = run(self.by_id['mitre-T1003-001'])
        self.assertTrue(result['human_alert']['required'])
        self.assertTrue(any('materiality' in r for r in result['human_alert']['reasons']))
        self.assertFalse(result['decisions'])

    def test_extreme_and_failure_cases_escalate(self):
        for identifier in ('council-critical-impact', 'council-deadline-passed', 'council-seat-outage', 'council-unresolved-debate'):
            result = run(self.by_id[identifier])
            self.assertEqual(result['status'], 'ESCALATED', identifier)
            self.assertFalse(result['decisions'])
            self.assertFalse(any(r['kind'] == 'simulated_restoration' for r in result['tool_receipts']))
        self.assertGreaterEqual(run(self.by_id['council-critical-impact'])['severity']['score'], 75)

    def test_live_unavailable_does_not_fallback(self):
        seats = Seats('live')
        with patch('council.seats.post', side_effect=OSError('offline')):
            result = run(self.by_id['mitre-T1041'], seats)
        self.assertEqual(result['mode'], 'live')
        self.assertTrue(result['human_alert']['required'])
        self.assertFalse(result['decisions'])

    def test_update_requires_new_consensus(self):
        case = next(c for c in self.cases if c.expected.get('family') == 'destination_rotation')
        result = run(case)
        self.assertFalse(result['human_alert']['required'])
        self.assertEqual([d['telemetry_version'] for d in result['decisions']], [1, 2])
        targets = [d['containment']['actions'][0]['target_id'] for d in result['decisions']]
        self.assertNotEqual(targets[0], targets[1])
        self.assertTrue(any(e['type'] == 'authority_withdrawn' for e in result['outcomes']['trace']))

    def test_unknown_evidence_and_contaminated_restore_rejected(self):
        case = self.by_id['mitre-T1486']
        context = case.context()
        proposal = fixing_plan(context)
        proposal['actions'][0]['evidence_ids'] = ['invented']
        with self.assertRaises(ValueError):
            validate_fixing(proposal, context)
        proposal = {'reason': 'test', 'verdict': 'propose', 'actions': [{'kind': 'restore_from_backup',
            'target_id': 'file-payroll', 'evidence_ids': ['F1'], 'reason': 'bad backup'}]}
        with self.assertRaises(ValueError):
            validate_fixing(proposal, context)

    def test_prefix_artifact_ids_do_not_match(self):
        case = next(c for c in self.cases if c.fixing['artifacts'][0]['type'] == 'local_account' and c.expected['fixing_variant'] == 'approved')
        proposal = fixing_plan(case.context())
        self.assertEqual([a['target_id'] for a in proposal['actions']], ['acct-svcbackup2'])

    def test_stale_containment_rejected(self):
        result = run(self.by_id['mitre-T1041'])
        proposal = copy.deepcopy(result['containment'])
        proposal['telemetry_version'] += 1
        with self.assertRaises(ValueError):
            sources.containment()['agent'].validate_proposal(proposal, self.by_id['mitre-T1041'].incident)

    def test_report_and_alert_are_saved(self):
        result = run(self.by_id['council-critical-impact'])
        result['case_id'] = '../../unsafe/id'
        with tempfile.TemporaryDirectory() as directory:
            path = save(result, directory)
            self.assertEqual(path.parent, Path(directory).resolve())
            self.assertEqual(json.loads(path.read_text())['status'], 'ESCALATED')
            self.assertTrue(path.with_suffix('.md').exists())
            self.assertEqual(len(list((Path(directory) / 'alerts').glob('*.json'))), 1)
            result['human_alert']['required'] = False
            save(result, directory)
            self.assertEqual(len(list((Path(directory) / 'alerts').glob('*.json'))), 0)

    def test_baseline_same_case_without_negotiation(self):
        case = next(c for c in self.cases if c.expected.get('family') == 'exfiltration')
        single = baseline.run(case)
        council = run(case)
        self.assertEqual(single['case_id'], council['case_id'])
        self.assertEqual(single['rounds'], 1)
        self.assertTrue(single['human_alert']['required'])
        self.assertFalse(council['human_alert']['required'])
        self.assertFalse(metrics(case, single)['outcome_horizon_complete'])

    def test_all_cases_have_no_unexpected_runtime_failures(self):
        for case in self.cases:
            result = run(case)
            failures = [r for r in result['human_alert']['reasons'] if 'failure' in r]
            self.assertEqual(bool(failures), case.fault == 'unavailable', (case.case_id, failures))

    def test_loopback_only(self):
        for url in ('https://example.com', 'http://127.0.0.1.evil.com', 'http://user@localhost', 'file:///tmp/secret'):
            with self.assertRaises(ValueError):
                local_url(url)
        self.assertEqual(local_url('http://127.0.0.1:8000/v1/'), 'http://127.0.0.1:8000/v1')

    def test_invalid_configuration(self):
        for value in (0, -1, 101, True):
            with self.assertRaises(ValueError):
                assess({}, threshold=value)
        with self.assertRaises(ValueError):
            run(self.cases[0], max_rounds=0)
        with self.assertRaises(ValueError):
            assess({'confirmed': 'true'})

    def test_model_cache_uses_model_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            client = ModelClient(cache_dir=directory)
            response = {'done': True, 'done_reason': 'stop', 'message': {'content': '{"stance":"support"}'}}
            with patch('council.seats.post', return_value=response) as transport:
                self.assertEqual(client.complete('forensics', {'evidence': 1}, {}), {'stance': 'support'})
                client.complete('forensics', {'evidence': 1}, {})
                client.complete('forensics', {'evidence': 2}, {})
                self.assertEqual(transport.call_count, 2)

    def test_simulated_recovery_state(self):
        result = run(self.by_id['mitre-T1486'])
        self.assertEqual(result['recovery_state']['files']['file-finance'], 'restored_clean')
        self.assertEqual(result['recovery_state']['files']['file-payroll'], 'encrypted')
        self.assertEqual(result['recovery_state']['artifacts']['bin-backupcli'], 'unchanged')
        held = run(self.by_id['mitre-T1021-002'])
        self.assertTrue(all(s == 'unchanged' for s in held['recovery_state']['artifacts'].values()))

    def test_forensics_api_preserves_immutable_evidence_ids(self):
        from council.forensics_api import ForensicsAPI
        context = self.by_id['mitre-T1041'].context()
        requests = []

        def transport(url, body, timeout):
            requests.append((url, copy.deepcopy(body)))
            if url.endswith('/investigations'):
                ids = body['available_evidence_ids']
                return {'findings': {'cited_evidence_ids': ids, 'timeline': []}}
            if url.endswith('/proposals'):
                return {'position': {'position': 'SUPPORT', 'supporting_evidence_ids': [],
                                     'opposing_evidence_ids': [], 'reasoning': 'safe'}}
            return {}

        api = ForensicsAPI('http://127.0.0.1:8747')
        with patch('council.forensics_api.post', side_effect=transport):
            first = api.position(context, {}, {})
            context['incident']['evidence'][0]['observation'] += ' New observation.'
            context['incident']['telemetry_version'] += 1
            second = api.position(context, {}, {})
        self.assertEqual(first['evidence_ids'], second['evidence_ids'])
        sends = [body for url, body in requests if url.endswith('/evidence')]
        self.assertEqual(len(sends), len(context['incident']['evidence']) + 1)
        ids = [body['evidence_id'] for body in sends if body['raw_data']['original_id'] == 'M1']
        self.assertEqual(len(set(ids)), 2)


if __name__ == '__main__':
    unittest.main()