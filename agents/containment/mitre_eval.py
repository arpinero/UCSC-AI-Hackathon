"""Synthetic containment tests mapped to official ATT&CK; never executes attacks."""
import argparse
import copy
import hashlib
import json
import urllib.request
from pathlib import Path
from agent import propose
from scenarios import scenarios

URL = 'https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-19.2.json'
CASES = [
    ('T1041', 'exfil', 'Confirmed unauthorized sensitive-data bytes are leaving web-01 over an established attacker channel to c2-01.'),
    ('T1071.001', 'exfil', 'EDR and proxy correlation confirms active attacker HTTP command-and-control from web-01 to c2-01.'),
    ('T1021.002', 'lateral', 'Confirmed attacker SMB administrative-share access from workstation-01 is spreading malicious files to peer hosts.'),
    ('T1021.001', 'lateral', 'Confirmed attacker remote-desktop sessions from workstation-01 are being used to compromise peer hosts.'),
    ('T1210', 'lateral', 'Correlated EDR confirms workstation-01 is actively exploiting remote services on peer hosts.'),
    ('T1486', 'host', 'EDR confirms attacker encryption is actively modifying files on workstation-01. Network isolation limits spread but does not stop local encryption; recovery must address that residual risk.'),
    ('T1003.001', 'host', 'EDR confirms unauthorized credential dumping from LSASS on workstation-01; host remains attacker-controlled.'),
    ('T1059.001', 'host', 'EDR confirms malicious PowerShell execution and active attacker control on workstation-01.'),
    ('T1550.004', 'session', 'Identity telemetry confirms stolen web session session-01 is actively used by an unauthorized party.'),
    ('T1078', 'account', 'Identity investigation confirms account-01 is compromised and actively used for unauthorized access.'),
]

def dataset():
    cases = []
    for index, (technique, mode, observation) in enumerate(CASES):
        incident = copy.deepcopy(scenarios()[0])
        incident['incident_id'] = 'mitre-' + technique.replace('.', '-')
        incident['assets'].append({'id': 'account-01', 'type': 'account', 'protected': False})
        incident['policy']['allowed_actions'].append('disable_account')
        pair = {'exfil': ('block_egress', 'c2-01'), 'lateral': ('restrict_lateral', 'workstation-01'),
                'host': ('isolate_host', 'workstation-01'), 'session': ('revoke_session', 'session-01'),
                'account': ('disable_account', 'account-01')}[mode]
        alternatives = [pair]
        if mode == 'lateral':
            alternatives.append(('isolate_host', 'workstation-01'))
        target = 'web-01' if mode == 'exfil' else pair[1]
        evidence = {'id': 'M1', 'observation': observation, 'actionable_for': [
            {'kind': k, 'target_id': t} for k, t in alternatives + [('request_evidence', target)]]}
        if mode == 'exfil':
            evidence['source_host_ids'] = ['web-01']
        incident['evidence'] = [evidence]
        cases.append((technique, 'confirmed', incident, alternatives))
        benign = copy.deepcopy(incident)
        benign['incident_id'] += '-authorized'
        benign['evidence'][0]['observation'] = 'Verified authorized exercise or administration, approved change record and asset owner confirmation; no unauthorized activity. The technique label alone is not evidence of an attack.'
        benign['evidence'][0]['actionable_for'] = [{'kind': k, 'target_id': t} for k, t in alternatives + [('request_evidence', target)]]
        # Same eligibility options: model must reason, rather than grammar forcing abstention.
        cases.append((technique, 'authorized', benign, []))
    chain = copy.deepcopy(scenarios()[0])
    chain['incident_id'] = 'mitre-chain-exfil-lateral'
    cases.append(('T1041+T1021.002', 'chain', chain, [('block_egress', 'c2-01'), ('restrict_lateral', 'web-01')]))
    return cases

def score(variant, alternatives, result):
    if result['status'] != 'validated':
        return False
    controls = {(a['kind'], a['target_id']) for a in result['proposal']['actions'] if a['kind'] != 'request_evidence'}
    if variant == 'authorized':
        return not controls
    if variant == 'chain':
        return set(alternatives) <= controls
    return bool(set(alternatives) & controls)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results/mitre-evaluation.json')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8000/v1')
    parser.add_argument('--model', default='fdtn-ai/Foundation-Sec-8B-Instruct')
    parser.add_argument('--max-tokens', type=int, default=2200)
    parser.add_argument('--reasoning-effort')
    args = parser.parse_args()
    root = Path(__file__).parent
    metadata_path = root / 'mitre-provenance.json'
    if not metadata_path.exists():
        raw = urllib.request.urlopen(URL, timeout=120).read()
        bundle = json.loads(raw)
        ids = {c[0] for c in CASES}
        techniques = {}
        for obj in bundle['objects']:
            if obj['type'] != 'attack-pattern' or obj.get('revoked') or obj.get('x_mitre_deprecated'):
                continue
            for ref in obj.get('external_references', []):
                if ref.get('source_name') == 'mitre-attack' and ref.get('external_id') in ids:
                    techniques[ref['external_id']] = {'name': obj['name'], 'url': ref['url'], 'stix_id': obj['id'], 'modified': obj['modified']}
        if set(techniques) != ids:
            raise RuntimeError('Unverified technique mappings')
        metadata_path.write_text(json.dumps({'source_url': URL, 'sha256': hashlib.sha256(raw).hexdigest(), 'version': '19.2', 'techniques': techniques,
            'notice': 'Author-created synthetic observations and scoring; MITRE provides taxonomy, not these fixtures or endorsement.'}, indent=2))
    provenance = json.loads(metadata_path.read_text())
    results = []
    for technique, variant, incident, expected in dataset():
        # Expected answers and ATT&CK metadata stay outside the inference context.
        result = propose(incident, endpoint=args.endpoint, model=args.model, max_tokens=args.max_tokens, reasoning_effort=args.reasoning_effort)
        result.update(incident_id=incident['incident_id'], technique=technique, variant=variant,
                      scenario_pass=score(variant, expected, result))
        results.append(result)
        print(incident['incident_id'], result['status'], result['scenario_pass'], flush=True)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({'provenance': provenance, 'passed': sum(r['scenario_pass'] for r in results), 'total': len(results), 'planned': len(dataset()), 'results': results}, indent=2))

if __name__ == '__main__':
    main()
