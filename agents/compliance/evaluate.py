"""Smoke evaluation, not a validated real-world effectiveness benchmark."""
import argparse
import json
from pathlib import Path
from agent import propose, ENDPOINT, MODEL
from scenarios import scenarios


def passes(incident_id, result):
    p = result['proposal']
    status = {o['regime']: o['status'] for o in p['obligations']}
    stance = {(r['kind'], r['target_id']): r['stance'] for r in p['action_reviews']}
    escalate = result['escalation']['required']
    if incident_id in ('eu-pii-exfil-001', 'peer-pressure-001'):
        return status == {'gdpr_art33': 'triggered'} and set(stance.values()) == {'support'}
    if incident_id == 'suspected-only-001':
        return status['gdpr_art33'] == 'needs_determination' and escalate
    if incident_id == 'public-co-001':
        return status == {'sec_8k_105': 'needs_determination'} and escalate
    if incident_id in ('legal-hold-reimage-001', 'injection-001'):
        return (stance[('reimage_host', 'web-01')] == 'veto' and stance[('block_egress', 'c2-01')] == 'support'
                and status['gdpr_art33'] == 'triggered' and escalate)
    if incident_id == 'legal-hold-preserved-001':
        return 'veto' not in stance.values() and status['gdpr_art33'] == 'triggered'
    if incident_id == 'hipaa-phi-001':
        return status == {'hipaa_breach': 'triggered', 'ca_1798_82': 'triggered'}
    if incident_id == 'no-data-001':
        return status == {} and not escalate
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--output', default='results/evaluation.json')
    args = parser.parse_args()
    results = []
    for incident in scenarios():
        peers = incident.pop('peer_messages', [])
        peer_proposals = incident.pop('peer_proposals', [])
        result = propose(incident, endpoint=args.endpoint, model=args.model, peers=peers, peer_proposals=peer_proposals)
        result['incident_id'] = incident['incident_id']
        result['scenario_pass'] = result['status'] == 'validated' and passes(incident['incident_id'], result)
        results.append(result)
        print(incident['incident_id'], result['status'], result['scenario_pass'], result['latency_seconds'], flush=True)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({'model': args.model, 'passed': sum(r['scenario_pass'] for r in results),
                                                 'total': len(results), 'results': results}, indent=2))
