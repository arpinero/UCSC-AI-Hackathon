"""Score the compliance agent on real-world-based scenarios. Reference outcomes, not legal advice."""
import argparse
import json
import sys
from pathlib import Path

# append, not insert(0): realworld/scenarios.py must win over the parent's scenarios.py
sys.path.append(str(Path(__file__).resolve().parent.parent))
from agent import propose, ENDPOINT, MODEL  # noqa: E402
from scenarios import scenarios  # noqa: E402


def score(expected, result):
    """Return (regime_hits, regime_total, vetoes_ok, escalation_ok)."""
    exp = expected['status']
    if result['proposal'] is None:
        return 0, len(exp), False, False
    got = {o['regime']: o['status'] for o in result['proposal']['obligations']}
    hits = sum(got.get(r) in (a if isinstance(a, list) else [a]) for r, a in exp.items())
    vetoes = {(r['kind'], r['target_id']) for r in result['proposal']['action_reviews'] if r['stance'] == 'veto'}
    want = {tuple(v) for v in expected['vetoes']}
    vetoes_ok = not vetoes if expected['no_veto'] else vetoes == want
    esc = expected['escalate']
    return hits, len(exp), vetoes_ok, esc is None or result['escalation']['required'] == esc


def run(model, args):
    rows = []
    for incident in scenarios():
        expected = incident.pop('expected')
        incident.pop('source')
        peers = incident.pop('peer_messages', [])
        peer_proposals = incident.pop('peer_proposals', [])
        result = propose(incident, endpoint=args.endpoint, model=model, peers=peers, peer_proposals=peer_proposals)
        hits, total, vetoes_ok, esc_ok = score(expected, result)
        valid = result['status'] == 'validated'
        rows.append({'incident_id': incident['incident_id'], 'status': result['status'], 'regime_hits': hits,
                     'regime_total': total, 'vetoes_ok': vetoes_ok, 'escalation_ok': esc_ok,
                     'scenario_pass': valid and hits == total and vetoes_ok and esc_ok,
                     'first_attempt': valid and len(result['attempts']) == 1,
                     'latency_seconds': result['latency_seconds'], 'result': result})
        r = rows[-1]
        print(model, r['incident_id'], r['status'], f"{hits}/{total}", 'veto_ok' if vetoes_ok else 'VETO_BAD',
              'esc_ok' if esc_ok else 'ESC_BAD', 'PASS' if r['scenario_pass'] else 'FAIL', r['latency_seconds'], flush=True)
    n = len(rows)
    return {'regime_accuracy': sum(r['regime_hits'] for r in rows) / sum(r['regime_total'] for r in rows),
            'scenario_pass_rate': sum(r['scenario_pass'] for r in rows) / n,
            'schema_valid_rate': sum(r['status'] == 'validated' for r in rows) / n,
            'first_attempt_rate': sum(r['first_attempt'] for r in rows) / n,
            'mean_latency_seconds': sum(r['latency_seconds'] for r in rows) / n,
            'scenarios': n, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--model', action='append', help='repeat for several models (default: agent MODEL)')
    parser.add_argument('--output', default='results/realworld_evaluation.json')
    args = parser.parse_args()
    out = {}
    for model in args.model or [MODEL]:
        out[model] = run(model, args)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(out, indent=2))
    for model, s in out.items():
        print(f"{model}: regime {s['regime_accuracy']:.0%} pass {s['scenario_pass_rate']:.0%} valid {s['schema_valid_rate']:.0%} "
              f"first-attempt {s['first_attempt_rate']:.0%} latency {s['mean_latency_seconds']:.1f}s")
