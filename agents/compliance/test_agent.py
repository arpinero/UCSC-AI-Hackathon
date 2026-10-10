import copy
import io
import json
import unittest
from unittest.mock import patch
import rules
from agent import validate_proposal, escalation, propose, decoding_schema
from scenarios import scenarios, CONTAINMENT, FIXING


def by_id(incident_id):
    s = next(s for s in scenarios() if s['incident_id'] == incident_id)
    return s, s.pop('peer_proposals', [])


def review(kind, target, stance='support', evidence='E1'):
    return {'kind': kind, 'target_id': target, 'stance': stance, 'evidence_ids': [evidence], 'reason': 'r'}


class RulesTests(unittest.TestCase):
    def test_gdpr_72h_from_discovery(self):
        incident, _ = by_id('eu-pii-exfil-001')
        [clock] = rules.deadlines(incident['compliance'])
        self.assertEqual(clock['regime'], 'gdpr_art33')
        self.assertEqual(clock['deadline'], '2026-10-12T09:00:00+00:00')
        self.assertEqual(clock['hours_remaining'], 42.0)

    def test_sec_clock_waits_for_materiality(self):
        incident, _ = by_id('public-co-001')
        [clock] = rules.deadlines(incident['compliance'])
        self.assertFalse(clock['clock_started'])
        self.assertIsNone(clock['deadline'])

    def test_sec_four_business_days_skip_weekend(self):
        c = by_id('public-co-001')[0]['compliance']
        c['materiality_determined_at'] = '2026-10-09T12:00:00Z'  # Friday
        [clock] = rules.deadlines(c)
        self.assertEqual(clock['deadline'], '2026-10-15T12:00:00+00:00')  # Thursday

    def test_candidates(self):
        self.assertEqual(rules.candidates(by_id('hipaa-phi-001')[0]['compliance']), ['hipaa_breach', 'ca_1798_82'])
        self.assertEqual(rules.candidates(by_id('no-data-001')[0]['compliance']), [])
        c = by_id('no-data-001')[0]['compliance']
        c['affected_data'] = [{'class': 'payment_card', 'jurisdictions': ['US-NY']}]
        self.assertEqual(rules.candidates(c), ['visa_compromise'])


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.incident, self.peers = by_id('legal-hold-reimage-001')
        self.proposal = {'incident_id': 'legal-hold-reimage-001', 'telemetry_version': 1, 'assessment': 'a',
            'obligations': [{'regime': 'gdpr_art33', 'status': 'triggered', 'confidence_pct': 90,
                             'evidence_ids': ['E1', 'E2'], 'reason': 'EU customer data exfiltrated.'}],
            'action_reviews': [review('block_egress', 'c2-01'), review('restrict_lateral', 'web-01'),
                               review('reimage_host', 'web-01', 'veto'), review('restore_files', 'web-01', 'veto')],
            'preservation_requests': ['Image web-01 memory and disk first.'], 'request_human': False,
            'uncertainties': [], 'peer_responses': []}

    def reject(self, mutate, incident=None):
        p = copy.deepcopy(self.proposal)
        mutate(p)
        with self.assertRaises(ValueError):
            validate_proposal(p, incident or self.incident, self.peers)

    def test_valid(self):
        validate_proposal(self.proposal, self.incident, self.peers)

    def test_stale(self):
        self.reject(lambda p: p.update(telemetry_version=2))

    def test_missing_regime(self):
        self.reject(lambda p: p.update(obligations=[]))

    def test_determination_needs_evidence(self):
        self.reject(lambda p: p['obligations'][0].update(evidence_ids=[]))

    def test_invented_evidence(self):
        self.reject(lambda p: p['obligations'][0].update(evidence_ids=['E999']))

    def test_unreviewed_peer_action(self):
        self.reject(lambda p: p['action_reviews'].pop())

    def test_can_veto_unknown_destructive_kind(self):
        peers = [CONTAINMENT, {'role': 'fixing', 'proposal': {'actions': [{'kind': 'wipe_disk', 'target_id': 'web-01'}]}}]
        p = copy.deepcopy(self.proposal)
        p['action_reviews'] = p['action_reviews'][:2] + [review('wipe_disk', 'web-01', 'veto')]
        validate_proposal(p, self.incident, peers)

    def test_cannot_veto_containment(self):
        self.reject(lambda p: p['action_reviews'][0].update(stance='veto'))

    def test_cannot_veto_without_hold(self):
        incident = copy.deepcopy(self.incident)
        incident['compliance']['legal_hold'] = False
        self.reject(lambda p: None, incident)

    def test_cannot_veto_preserved_host(self):
        incident = copy.deepcopy(self.incident)
        incident['compliance']['evidence_preserved_host_ids'] = ['web-01']
        self.reject(lambda p: None, incident)

    def test_sec_triggered_requires_human_materiality(self):
        incident, _ = by_id('public-co-001')
        p = {**self.proposal, 'incident_id': 'public-co-001', 'action_reviews': [review('block_egress', 'c2-01', evidence='E4'), review('restrict_lateral', 'web-01', evidence='E4')],
             'obligations': [{'regime': 'sec_8k_105', 'status': 'triggered', 'confidence_pct': 90, 'evidence_ids': ['E4'], 'reason': 'r'}]}
        with self.assertRaises(ValueError):
            validate_proposal(p, incident, [CONTAINMENT])
        p['obligations'][0]['status'] = 'needs_determination'
        validate_proposal(p, incident, [CONTAINMENT])

    def test_decoding_schema_pins_regimes_and_actions(self):
        schema = decoding_schema(self.incident, self.peers)
        ob = schema['properties']['obligations']
        self.assertEqual((ob['minItems'], ob['maxItems']), (1, 1))
        self.assertEqual(ob['items']['properties']['regime']['enum'], ['gdpr_art33'])
        self.assertEqual(schema['properties']['action_reviews']['minItems'], 4)
        self.assertNotIn('enum', schema['properties']['assessment'])
        self.assertNotIn('enum', ob['items']['properties']['reason'])


class EscalationTests(unittest.TestCase):
    def esc(self, proposal, incident_id, peers=None):
        incident = by_id(incident_id)[0]
        return escalation(proposal, rules.deadlines(incident['compliance']), incident, peers)

    def proposal(self, regime, status, confidence=90, reviews=(), human=False):
        return {'obligations': [{'regime': regime, 'status': status, 'confidence_pct': confidence}],
                'action_reviews': list(reviews), 'request_human': human}

    def test_confident_triggered_with_time_left_does_not_escalate(self):
        self.assertFalse(self.esc(self.proposal('gdpr_art33', 'triggered'), 'eu-pii-exfil-001')['required'])

    def test_undetermined_short_clock_escalates(self):
        e = self.esc(self.proposal('gdpr_art33', 'needs_determination'), 'suspected-only-001')
        self.assertTrue(e['required'])
        self.assertIn('12.0h left', e['reasons'][0])

    def test_low_confidence_short_clock_escalates(self):
        self.assertTrue(self.esc(self.proposal('gdpr_art33', 'triggered', 40), 'eu-pii-exfil-001')['required'])

    def test_sec_undetermined_escalates(self):
        self.assertTrue(self.esc(self.proposal('sec_8k_105', 'needs_determination'), 'public-co-001')['required'])

    def test_held_destructive_escalates_even_if_model_supports_it(self):
        p = self.proposal('gdpr_art33', 'triggered', reviews=[review('reimage_host', 'web-01', 'support')])
        e = self.esc(p, 'legal-hold-reimage-001', [FIXING])
        self.assertTrue(e['required'])
        self.assertIn('legal hold: reimage_host', e['reasons'][0])

    def test_preserved_host_does_not_escalate(self):
        p = self.proposal('gdpr_art33', 'triggered', reviews=[review('reimage_host', 'web-01', 'support')])
        self.assertFalse(self.esc(p, 'legal-hold-preserved-001', [FIXING])['required'])

    def test_unknown_kind_counts_as_destructive(self):
        peers = [{'role': 'fixing', 'proposal': {'actions': [{'kind': 'wipe_disk', 'target_id': 'web-01'}]}}]
        self.assertTrue(self.esc(self.proposal('gdpr_art33', 'triggered'), 'legal-hold-reimage-001', peers)['required'])


class TransportTests(unittest.TestCase):
    def test_unavailable(self):
        import urllib.error
        incident, peers = by_id('eu-pii-exfil-001')
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('down')):
            result = propose(incident, peer_proposals=peers)
        self.assertEqual(result['status'], 'unavailable')
        self.assertTrue(result['escalation']['required'])

    def test_rejected_twice_escalates(self):
        incident, peers = by_id('eu-pii-exfil-001')
        bad = json.dumps({'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}).encode()
        with patch('urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(bad)):
            result = propose(incident, peer_proposals=peers)
        self.assertEqual(result['status'], 'rejected')
        self.assertTrue(result['escalation']['required'])


if __name__ == '__main__':
    unittest.main()
