"""Reproducible synthetic council vs single-pass comparison; atomic checkpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from council import baseline
from council import sources
from council.protocol import run
from council.report import atomic_json, save
from council.scenarios import dataset
from council.seats import ModelClient, Seats


def metrics(case, result):
    actions = result.get('containment', {}).get('actions', [])
    pairs = {(a['kind'], a['target_id']) for a in actions if a['kind'] != 'request_evidence'}
    alternatives = case.expected.get('containment_alternatives')
    containment_pass = None
    if alternatives is not None:
        containment_pass = bool(pairs & {tuple(p) for p in alternatives}) if alternatives else not pairs
    fixing = result.get('fixing', {}).get('actions')
    fixing_pass, fixing_reasons = (False, ['Missing fixing proposal']) if fixing is None else sources.fixing()['fixing_scenarios'].score(
        case.expected['fixing_variant'], case.expected['fixing_truth'], case.fixing, fixing)
    expected = case.expected.get('compliance_status')
    actual = {o['regime']: o['status'] for o in result.get('compliance', {}).get('obligations', [])}
    compliance_pass = None if expected is None else set(actual) == set(expected) and all(
        actual[k] in v if isinstance(v, list) else actual[k] == v for k, v in expected.items())
    citation_ids = result.get('forensics', {}).get('evidence_ids', [])
    all_ids = {e['id'] for e in case.incident['evidence']}
    return {'containment_fixture_pass': containment_pass, 'fixing_fixture_pass': fixing_pass,
            'fixing_reasons': fixing_reasons, 'compliance_fixture_pass': compliance_pass,
            'forensic_citation_coverage': len(set(citation_ids) & all_ids) / len(all_ids),
            'human_required': result['human_alert']['required'],
            'expected_human_check': None if 'human_required' not in case.expected else result['human_alert']['required'] == case.expected['human_required'],
            'consensus': bool(result.get('decisions')), 'rounds': result['rounds'],
            'outcome_horizon_complete': result['outcomes']['simulated_seconds'] == case.simulation['horizon_seconds'],
            'outcomes': {k: result['outcomes'][k] for k in ('bytes_lost', 'additional_hosts_compromised',
                'identity_abuse_events', 'local_files_damaged', 'service_disruption_seconds', 'evidence_gap_seconds', 'false_positive_controls', 'policy_rejections')}}


def summarize(rows, side):
    values = [r[side + '_metrics'] for r in rows]
    summary = {'completed': len(values), 'escalations': sum(v['human_required'] for v in values),
               'consensus_cases': sum(v['consensus'] for v in values)}
    for key in ('containment_fixture_pass', 'fixing_fixture_pass', 'compliance_fixture_pass', 'expected_human_check'):
        scored = [v[key] for v in values if v[key] is not None]
        summary[key] = {'passed': sum(scored), 'total': len(scored)}
    completed = [v for v in values if v['outcome_horizon_complete']]
    summary['full_horizon_cases'] = len(completed)
    summary['mean_rounds'] = sum(v['rounds'] for v in values) / max(1, len(values))
    summary['mean_forensic_citation_coverage'] = sum(v['forensic_citation_coverage'] for v in values) / max(1, len(values))
    # Escalated partial traces are never counted as zero-loss success.
    summary['full_horizon_outcome_totals'] = {k: sum(v['outcomes'][k] for v in completed)
        for k in ('bytes_lost', 'additional_hosts_compromised', 'identity_abuse_events', 'local_files_damaged', 'false_positive_controls')}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('mock', 'live'), default='mock')
    parser.add_argument('--output', default='results/council-mock.json')
    parser.add_argument('--reports', default='reports')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--model')
    parser.add_argument('--endpoint')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--cache-dir')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    cases = dataset()[:args.limit]
    client = ModelClient(args.endpoint, args.model, args.timeout, args.cache_dir)
    seats = Seats(args.mode, client)
    code_hash = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
    fixture_hash = hashlib.sha256(json.dumps([c.__dict__ for c in cases], sort_keys=True).encode()).hexdigest()
    config = {'mode': args.mode, 'model': client.model if args.mode == 'live' else None,
              'endpoint': client.endpoint if args.mode == 'live' else None,
              'containment_url': seats.containment_url, 'compliance_url': seats.compliance_url,
              'forensics_url': os.environ.get('COUNCIL_FORENSICS_URL'),
              'fixing_endpoint': seats.fixing_client.endpoint, 'fixing_model': seats.fixing_client.model,
              'code_sha256': code_hash, 'dataset_sha256': fixture_hash, 'planned': len(cases),
              'threshold': 75, 'max_rounds': 3, 'synthetic_response_seconds': 30, 'timeout': args.timeout}
    path = Path(args.output).resolve()
    rows = []
    if args.resume and path.exists():
        saved = json.loads(path.read_text())
        if saved['config'] != config:
            parser.error('Resume configuration/code/dataset differs; use a new output')
        rows = saved['results']
        if [r['case_id'] for r in rows] != [c.case_id for c in cases[:len(rows)]]:
            parser.error('Checkpoint is not a valid case prefix')
    for case in cases[len(rows):]:
        council = run(case, seats)
        single = baseline.run(case, args.mode, client)
        save(council, args.reports)
        rows.append({'case_id': case.case_id, 'council': council, 'baseline': single,
                     'council_metrics': metrics(case, council), 'baseline_metrics': metrics(case, single)})
        payload = {'config': config, 'results': rows,
                   'summary': {s: summarize(rows, s) for s in ('council', 'baseline')},
                   'limitations': ['Synthetic and correlated fixtures; not production attack detection.',
                     'Mock policies are hand-written and tuned to fixture vocabulary, not LLM intelligence.',
                     'Single-pass baseline does not process updates; this measures protocol differences, not equal-compute superiority.',
                     'Escalated traces are partial and excluded from full-horizon loss totals.',
                     'Severity weights are uncalibrated; no escalation precision/recall claimed without independent labels.',
                     'Forensic citation coverage measures IDs, not factual quality or chain-of-custody assurance.']}
        atomic_json(path, payload)
        print(case.case_id, council['status'], 'single:', single['status'], flush=True)
    table = ['# Council baseline results', '', f'Mode: **{args.mode}**. Completed {len(rows)}/{len(cases)}.', '',
             'Mock results are integration checks, not multi-model performance claims.', '',
             '| Metric | Council | Single-pass |', '|---|---:|---:|']
    for key in summarize(rows, 'council'):
        table.append('| ' + key + ' | ' + json.dumps(summarize(rows, 'council')[key]) + ' | ' + json.dumps(summarize(rows, 'baseline')[key]) + ' |')
    paired = [r for r in rows if r['council_metrics']['outcome_horizon_complete'] and r['baseline_metrics']['outcome_horizon_complete']]
    table.extend(['', f'Paired full-horizon cases: {len(paired)}. Only compare network loss on this shared subset.',
                  'Raw full-horizon totals above cover different case sets and must not be interpreted as relative effectiveness.', '',
                  '## Limitations', *['- ' + text for text in json.loads(path.read_text())['limitations']]])
    path.with_suffix('.md').write_text('\n'.join(table) + '\n')


if __name__ == '__main__':
    main()