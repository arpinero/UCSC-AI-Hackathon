"""Replay frozen model decisions under timing/expiry perturbations; no inference."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from benchmark_cases import dataset
from outcome_benchmark import run_case, summarize


def replay(case, recorded, latency_seconds=None, ttl_minutes=None):
    attempts = iter(recorded['inference'])

    def predictor(incident, previous):
        try:
            saved = next(attempts)
        except StopIteration:
            return {'status': 'unavailable', 'latency_seconds': 0,
                    'attempts': [{'replay_error': 'No frozen response for this decision'}]}
        result = copy.deepcopy(saved['result'])
        # Never relabel old evidence as current: simulator rejects stale versions.
        if latency_seconds is not None:
            result['latency_seconds'] = latency_seconds
        if ttl_minutes is not None and result.get('proposal'):
            for action in result['proposal']['actions']:
                action['ttl_minutes'] = ttl_minutes
        return result

    return run_case(case, predictor)


def analyze(source):
    if source.get('mode') != 'model':
        raise ValueError('Sensitivity input must contain actual model results')
    cases = dataset()
    digest = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    if source['config']['dataset_sha256'] != digest:
        raise ValueError('Dataset does not match frozen model experiment')
    for name, expected in source['config']['source_hashes'].items():
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != expected:
            raise ValueError('Source changed since inference: ' + name)
    by_id = {case['case_id']: case for case in cases}
    ids = [r['incident_id'] for r in source['results']]
    if len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
        raise ValueError('Unknown or duplicate case IDs')
    variants = [('observed timing', None, None), ('instant replay', 0, None),
                ('30 second response', 30, None), ('120 second response', 120, None),
                ('240 second response', 240, None), ('1 minute TTL', None, 1),
                ('3 minute TTL', None, 3)]
    experiments = []
    for label, latency, ttl in variants:
        results = [replay(by_id[r['incident_id']], r, latency, ttl) for r in source['results']]
        if latency is None and ttl is None:
            # A replay must exactly reproduce effects before perturbations mean anything.
            for original, result in zip(source['results'], results):
                if json.dumps(original['outcomes'], sort_keys=True) != json.dumps(result['outcomes'], sort_keys=True) or original['checks'] != result['checks']:
                    raise ValueError('Observed replay diverged: ' + original['incident_id'])
        experiments.append({'label': label, 'response_seconds': latency, 'ttl_minutes': ttl,
                            'summary': summarize(results), 'results': results})
    return {'mode': 'counterfactual_replay_no_inference', 'source_config': source['config'],
            'source_completed': len(ids), 'source_planned': source['planned'],
            'limitations': ['Frozen decisions are not replanned for changed conditions.',
                            'Variants are correlated counterfactuals, not additional model tests.',
                            'Late responses retain their original telemetry version and may be rejected.',
                            'Scoring references retain their normal TTL; short TTL measures expiry harm.'],
            'experiments': experiments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('--output', required=True)
    args = parser.parse_args(); path = Path(args.source)
    report = analyze(json.loads(path.read_text()))
    report['source_file_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    lines = ['# Frozen-decision sensitivity experiment', '',
             '**Counterfactual replay only: no new model inference.**', '',
             f"Source: {report['source_completed']}/{report['source_planned']} model cases completed.", '',
             '| Perturbation | Passes / replayed | Bytes lost | New hosts | Policy rejections |',
             '|---|---:|---:|---:|---:|']
    for experiment in report['experiments']:
        s = experiment['summary']; rows = experiment['results']
        lines.append(f"| {experiment['label']} | {s['passed']}/{s['completed']} | "
                     f"{sum(r['outcomes']['bytes_lost'] for r in rows):.0f} | "
                     f"{sum(r['outcomes']['additional_hosts_compromised'] for r in rows)} | {s['policy_rejections']} |")
    lines += ['', *report['limitations']]
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
