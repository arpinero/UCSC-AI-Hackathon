"""Engine property checks across generated seeds. No model inference or attacks."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from benchmark_cases import dataset, reference_proposal
from outcome_benchmark import advance_updates, run_case
from simulator import Simulator


def verify(case):
    errors = []
    def predictor(incident, previous):
        refs = case['reference']
        for update in case['updates']:
            if incident['telemetry_version'] >= update['incident']['telemetry_version']:
                refs = update['reference']
        return {'status': 'validated', 'proposal': reference_proposal(case, incident, refs),
                'latency_seconds': 0, 'attempts': []}
    result = run_case(case, predictor)
    if not result['scenario_pass']:
        errors.append('Fixture response failed its declared outcome checks')
    for key in ('bytes_lost', 'additional_hosts_compromised', 'identity_abuse_events', 'local_files_damaged'):
        if result['outcomes'][key] > result['no_response'][key] + 1e-6:
            errors.append('Correct controls increased harm: ' + key)
    if result['outcomes']['local_files_damaged'] != result['no_response']['local_files_damaged']:
        errors.append('Network/identity controls incorrectly stopped local damage')
    # Physics must not depend on how a caller partitions the same elapsed time.
    whole = Simulator(case); pieces = Simulator(case)
    for engine in (whole, pieces):
        controls = reference_proposal(case)
        for action in controls['actions']:
            action['ttl_minutes'] = 3
        if not engine.apply(controls):
            errors.append('Expiry fixture failed policy validation')
    rng = random.Random(case['seed'] * 1000 + sum(map(ord, case['family'])))
    for boundary in sorted({rng.uniform(0, case['horizon_seconds']) for _ in range(23)}):
        advance_updates(pieces, boundary)
    advance_updates(pieces, case['horizon_seconds']); advance_updates(whole, case['horizon_seconds'])
    left = pieces.snapshot(); right = whole.snapshot()
    for key, value in left.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value) or value < 0:
                errors.append('Invalid metric: ' + key)
            if not math.isclose(value, right[key], rel_tol=1e-10, abs_tol=1e-6):
                errors.append('Time partition changed metric: ' + key)
        elif value != right[key]:
            errors.append('Time partition changed state/trace: ' + key)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-count', type=int, default=100)
    parser.add_argument('--output', default='results/engine-stress.json')
    args = parser.parse_args()
    if not 1 <= args.seed_count <= 10000:
        parser.error('seed-count must be 1-10000')
    cases = dataset(tuple(range(1, args.seed_count + 1)))
    failures = []
    for case in cases:
        errors = verify(case)
        if errors:
            failures.append({'case_id': case['case_id'], 'seed': case['seed'],
                             'family': case['family'], 'errors': errors})
    report = {'mode': 'engine_properties_no_inference', 'seeds': args.seed_count,
              'families': 16, 'cases_checked': len(cases), 'failures': failures,
              'checks': ['Fixture consistency', 'Controls never increase modeled attack harm',
                         'Network controls do not stop local encryption', 'Time-partition invariance with expiring controls',
                         'Finite nonnegative metrics and deterministic event traces'],
              'limitations': 'Generated correlated cases validate engine semantics, not model quality or real-world realism.',
              'source_hashes': {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                for n in ('stress_simulator.py', 'simulator.py', 'benchmark_cases.py',
                                          'outcome_benchmark.py', 'agent.py')}}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({'cases_checked': len(cases), 'failures': len(failures), 'model_calls': 0}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
