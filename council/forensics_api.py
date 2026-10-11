"""Optional adapter for Andrew's frozen v1 API. No edits to his branch required."""
import hashlib
import json
from council.seats import local_url, post


class ForensicsAPI:
    def __init__(self, url, timeout=120):
        self.url = local_url(url)
        self.timeout = timeout
        self.incidents = set()
        self.evidence = set()
        self.rounds = {}

    def position(self, context, containment, fixing):
        incident = context['incident']
        incident_id = incident['incident_id']
        hosts = [a['id'] for a in incident['assets'] if a['type'] == 'host']
        # The composite fixtures lack wall-clock event times. Explicitly use
        # simulated discovery time and disclose that limitation in raw_data.
        timestamp = incident['compliance']['discovered_at']
        if incident_id not in self.incidents:
            post(self.url + '/incidents', {'incident_id': incident_id, 'scenario_id': incident_id,
                'created_at': timestamp, 'severity': 'MEDIUM', 'affected_hosts': hosts,
                'initial_description': 'Synthetic council intrusion; initial severity placeholder, scoring owned by council policy',
                'current_status': 'OPEN'}, self.timeout)
            self.incidents.add(incident_id)
        mapping = {}
        for e in incident['evidence']:
            # Containment updates reuse IDs for changed observations. Andrew's
            # contract forbids this: map content-addressed immutable IDs back.
            digest = hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()[:16]
            evidence_id = 'EV-' + digest
            mapping[evidence_id] = e['id']
            key = (incident_id, evidence_id)
            if key not in self.evidence:
                post(self.url + '/evidence', {'evidence_id': evidence_id, 'incident_id': incident_id,
                    'source': 'council synthetic fixture', 'event_type': 'synthetic_observation',
                    'timestamp': e.get('timestamp', timestamp),
                    'host_id': (e.get('source_host_ids') or hosts)[0],
                    'description': e['observation'],
                    'raw_data': {'original_id': e['id'], 'telemetry_version': incident['telemetry_version'],
                                 'timestamp_is_simulated_placeholder': 'timestamp' not in e},
                    'collected_at': timestamp, 'collection_tool': 'synthetic_fixture_adapter'}, self.timeout)
                self.evidence.add(key)
        round_number = self.rounds.get(incident_id, 0) + 1
        self.rounds[incident_id] = round_number
        findings = post(self.url + '/investigations', {'request_id': f'REQ-{incident_id}-{round_number}',
            'incident_id': incident_id, 'round': round_number,
            'question': 'Correlate supplied evidence, preserve evidence, and trace attacker; report uncertainty.',
            'available_evidence_ids': list(mapping), 'requested_by': 'council-router'}, self.timeout)['findings']
        position = post(self.url + '/proposals', {'incident_id': incident_id, 'round': round_number,
            'proposal': {'containment': containment, 'fixing': fixing,
                         'preservation_confirmed': context.get('preservation_confirmed', False)}}, self.timeout)['position']
        cited = set(findings['cited_evidence_ids']) | set(position['supporting_evidence_ids']) | set(position['opposing_evidence_ids'])
        if not cited or not cited <= set(mapping):
            raise ValueError('Forensics API returned missing/unknown evidence citations')
        if position['position'] not in ('SUPPORT', 'OPPOSE', 'ABSTAIN'):
            raise ValueError('Forensics API returned invalid position')
        timeline = []
        for event in findings['timeline']:
            if not set(event['evidence_ids']) <= set(mapping):
                raise ValueError('Forensics timeline contains unknown evidence')
            timeline.append({'evidence_ids': [mapping[eid] for eid in event['evidence_ids']],
                             'timestamp': event['timestamp'], 'observation': event['description']})
        return {'stance': 'support' if position['position'] == 'SUPPORT' else 'object',
                'evidence_ids': sorted({mapping[eid] for eid in cited}), 'reason': position['reasoning'],
                'timeline': timeline, 'api_findings': findings, 'api_position': position,
                'adapter_notice': 'Fixture timestamps are simulated placeholders; immutable API IDs are content-addressed'}