"""Compose teammate fixtures without exposing their answer keys to seats."""
import copy
from council import sources
from council.case import CouncilCase


def empty_compliance():
    return {'now': '2026-10-11T16:00:00Z', 'discovered_at': '2026-10-10T20:00:00Z',
            'organization': {}, 'affected_data': [], 'legal_hold': False,
            'evidence_preserved_host_ids': []}


def impact_from(incident):
    """Synthetic observations, not a production telemetry classifier."""
    text = ' '.join(e['observation'].split('\nUntrusted')[0] for e in incident['evidence']).lower()
    authorized = 'verified authorized' in text or 'signed backup job' in text
    confirmed = not authorized and any(s in text for s in
        ('confirms', 'confirmed', 'owner denied', 'owner denial', 'attacker control'))
    hosts = {h for e in incident['evidence'] for h in e.get('source_host_ids', [])}
    critical = any(a.get('critical') and a['id'] in hosts for a in incident['assets'])
    data = incident['compliance'].get('affected_data', [])
    return {'confirmed': confirmed, 'exfiltration': confirmed and any(s in text for s in
                ('bytes are leaving', 'outbound', 'download', 'transferred files')),
            'sensitive_data': confirmed and bool(data),
            'lateral_spread': confirmed and any(s in text for s in ('spreading', 'remote', 'peer hosts')),
            'identity_compromise': confirmed and any(s in text for s in ('credential', 'session', 'account-01 is compromised', 'unauthorized active use')),
            'privileged_identity': confirmed and 'domain administrator' in text,
            'ransomware': confirmed and any(s in text for s in ('encryption', 'encrypted')),
            'critical_asset': confirmed and (critical or 'dispatch scheduling' in text),
            'affected_hosts': max(1, len(hosts)) if confirmed else 0,
            'data_records': sum(d.get('records', 0) for d in data) if confirmed else 0}


def attach_fixing(incident, technique, variant):
    module = sources.fixing()['fixing_scenarios']
    fix, truth = module.build(technique, variant)
    fix['incident_id'] = incident['incident_id']
    fix['telemetry_version'] = incident['telemetry_version']
    hosts = [a for a in incident['assets'] if a['type'] == 'host']
    host = next((a['id'] for a in hosts if a['id'] == fix['host_id']), hosts[0]['id'])
    old = fix['host_id']
    fix['host_id'] = host
    fix['hosts'] = [{'id': a['id'], 'critical': a.get('critical', False)} for a in hosts]
    for e in fix['evidence']:
        e['observation'] = e['observation'].replace(old, host)
        e['actionable_for'] = []
        e['source_host_ids'] = [host]
    incident['evidence'].extend(copy.deepcopy(fix['evidence']))
    return fix, truth


def fixture_simulation(incident, technique, variant):
    """A small network replay for the MITRE fixtures; outcomes remain synthetic."""
    malicious = variant != 'authorized'
    events = []
    hosts = [a['id'] for a in incident['assets'] if a['type'] == 'host']
    for e in incident['evidence']:
        for pair in e.get('actionable_for', []):
            kind, target = pair['kind'], pair['target_id']
            if not malicious:
                continue
            if kind == 'block_egress':
                events.append({'kind': 'exfil', 'source': e['source_host_ids'][0],
                               'destination': target, 'at': 0, 'until': 600, 'rate': 25000})
            elif kind == 'restrict_lateral':
                events.append({'kind': 'spread', 'source': target,
                               'target': next(h for h in hosts if h != target), 'at': 150})
            elif kind in ('revoke_session', 'disable_account'):
                events.append({'kind': 'identity', 'session': target if kind == 'revoke_session' else None,
                               'account': target if kind == 'disable_account' else None, 'at': 150})
    if malicious and technique == 'T1486':
        events.append({'kind': 'local_damage', 'source': 'workstation-01', 'at': 0, 'until': 600, 'rate': 2})
    return {'incident': copy.deepcopy(incident), 'truth': 'malicious' if malicious else 'benign',
            'events': events, 'dependencies': [], 'updates': [],
            'initial_compromised': hosts if malicious else [], 'horizon_seconds': 600}


def dataset():
    cases = []
    techniques = list(sources.fixing()['fixing_specs'].SPECS)
    for index, regulatory in enumerate(sources.compliance_attack().scenarios()):
        fixture = list(sources.containment_fixtures().values())[index]
        incident = copy.deepcopy(fixture['incident'])
        incident['compliance'] = copy.deepcopy(regulatory['compliance'])
        for e in regulatory['evidence']:
            if e['id'] not in {x['id'] for x in incident['evidence']}:
                record = copy.deepcopy(e)
                record.setdefault('actionable_for', [])
                incident['evidence'].append(record)
        variant = 'authorized' if fixture['variant'] == 'authorized' else 'approved'
        if incident['compliance']['legal_hold'] and not incident['compliance']['evidence_preserved_host_ids']:
            variant = 'hold'
        technique = fixture['technique'] if fixture['technique'] in techniques else techniques[(index // 2) % len(techniques)]
        fix, truth = attach_fixing(incident, technique, variant)
        expected = {'containment_alternatives': fixture['expected_alternatives'],
                    'fixing_variant': variant, 'fixing_truth': truth,
                    'compliance_status': regulatory['expected']['status']}
        cases.append(CouncilCase(incident['incident_id'], incident, fix, impact_from(incident),
            fixture_simulation(incident, fixture['technique'], fixture['variant']), expected,
            ['containment/mitre-fixtures.json', 'compliance/realworld/attack.py', 'fixing-agent/fixing_scenarios.py']).validate())
    modules = sources.load_group([sources.CONTAINMENT_DIR], ['agent', 'benchmark_cases'])
    for index, simulation in enumerate(modules['benchmark_cases'].dataset(seeds=(17, 29))):
        incident = copy.deepcopy(simulation['incident'])
        incident['compliance'] = empty_compliance()
        variant = 'authorized' if simulation['truth'] != 'malicious' else 'approved'
        technique = 'T1486' if simulation['family'] == 'ransomware' else techniques[index % len(techniques)]
        fix, truth = attach_fixing(incident, technique, variant)
        simulation = copy.deepcopy(simulation)
        simulation['incident'] = copy.deepcopy(incident)
        for update in simulation['updates']:
            update['incident']['compliance'] = copy.deepcopy(incident['compliance'])
            update['incident']['evidence'].extend(copy.deepcopy(fix['evidence']))
        cases.append(CouncilCase(incident['incident_id'], incident, fix, impact_from(incident), simulation,
            {'fixing_variant': variant, 'fixing_truth': truth, 'family': simulation['family']},
            ['containment/benchmark_cases.py', 'fixing-agent/fixing_scenarios.py']).validate())
    for name, base, fault in [('critical-impact', 10, ''), ('deadline-passed', 0, ''), ('seat-outage', 0, 'unavailable'),
                              ('unresolved-debate', 0, 'deadlock')]:
        case = copy.deepcopy(cases[base])
        case.case_id = 'council-' + name
        case.incident['incident_id'] = case.case_id
        case.fixing['incident_id'] = case.case_id
        case.simulation['incident'] = copy.deepcopy(case.incident)
        case.fault = fault
        if name == 'deadline-passed':
            case.incident['compliance']['now'] = '2026-10-14T16:00:00Z'
            case.simulation['incident'] = copy.deepcopy(case.incident)
        if name == 'critical-impact':
            evidence = {'id': 'CRIT1', 'observation': 'Confirmed ransomware on critical dispatch host; stolen domain administrator credentials and lateral compromise of eight hosts.',
                        'actionable_for': [], 'source_host_ids': ['workstation-01']}
            case.incident['evidence'].append(evidence)
            case.simulation['incident'] = copy.deepcopy(case.incident)
            case.impact = impact_from(case.incident)
            case.impact['affected_hosts'] = 8
        case.expected['human_required'] = True
        cases.append(case.validate())
    return cases