"""Development diagnostic: explicit semantic JSON contract, not held-out evaluation."""
import hashlib
import json
from pathlib import Path
import agent
from benchmark_cases import dataset

CONTRACT = '''
JSON field meanings: assessment is a short factual incident assessment, not a
timestamp. evidence_review records your decision for EVERY observation: contain
only when the observation establishes an unauthorized threat, investigate for
unresolved authorization, and no_action for verified authorized activity.
Allowed action candidates are not findings of compromise. Explain each review
and action in one short sentence. State only supported facts. The actions array
contains selected controls, not every eligible option. Empty actions is valid.
Return this complete JSON contract, using the current incident and evidence IDs:
'''


def main():
    base = agent.SYSTEM
    results = []
    cases = [c for c in dataset((17,)) if c['family'] in
             ('remote_exploit', 'authorized_backup', 'ambiguous_alert')]
    for case in cases:
        incident = case['incident']
        agent.SYSTEM = base + CONTRACT + json.dumps(agent.decoding_schema(incident))
        result = agent.propose(incident)
        results.append({'family': case['family'], 'incident': incident,
                        'system_prompt': agent.SYSTEM, 'result': result})
        output = Path('results/contract-probe.json'); output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({'mode': 'development_diagnostic',
                          'held_out': False, 'model': agent.MODEL,
                          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          'note': 'Concurrent with outcome run; latency is not an isolated comparison.',
                          'results': results}, indent=2))
        print(case['family'], result['status'],
              [(a['kind'], a['target_id']) for a in (result.get('proposal') or {}).get('actions', [])], flush=True)


if __name__ == '__main__':
    main()
