"""Run one simulated incident or the complete suite, without a UI."""
import argparse
import json
from council.protocol import run
from council.report import save
from council.scenarios import dataset
from council.seats import ModelClient, Seats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('mock', 'live'), default='mock')
    parser.add_argument('--case')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--output', default='reports')
    parser.add_argument('--threshold', type=int, default=75)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--response-seconds', type=float, default=30)
    parser.add_argument('--model')
    parser.add_argument('--endpoint')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--cache-dir')
    args = parser.parse_args()
    cases = dataset()
    if args.list:
        for case in cases:
            print(case.case_id, case.expected.get('family', ''), case.provenance)
        return
    if args.case:
        cases = [c for c in cases if c.case_id == args.case]
        if not cases:
            parser.error('Unknown case ID; use --list')
    seats = Seats(args.mode, ModelClient(args.endpoint, args.model, args.timeout, args.cache_dir))
    for case in cases:
        result = run(case, seats, args.rounds, args.threshold, args.response_seconds)
        path = save(result, args.output)
        print(json.dumps({'case_id': case.case_id, 'status': result['status'],
                          'severity': result['severity']['score'], 'report': str(path)}), flush=True)
        if result['human_alert']['required']:
            print('HUMAN REQUIRED: ' + '; '.join(result['human_alert']['reasons']), flush=True)


if __name__ == '__main__':
    main()