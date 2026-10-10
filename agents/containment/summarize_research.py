"""Summarize preserved local experiment files without hiding failed attempts."""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / 'research' / 'raw'
RUNS = {
    'evaluation.json': ('Foundation initial serving integration', 8, '79b3899', 'Schema/template defects; not a model-quality baseline'),
    'evaluation-final.json': ('Foundation template/schema correction', 8, 'c2d09a2', 'Development smoke; launch hash was not recorded'),
    'evaluation-verified.json': ('Foundation constrained-action smoke', 8, '57e66a4', 'Development smoke; missed a lateral control'),
    'mitre-evaluation.json': ('Foundation preliminary MITRE', 21, '1e39865', 'Stopped early after failures'),
    'evaluation-release.json': ('Foundation evidence-review smoke', 8, '1e39865', 'Development run'),
    'challenge-evaluation.json': ('Foundation initial challenge', 6, 'f9f681e', 'Development run; prompts subsequently changed'),
    'mitre-revised.json': ('Foundation revised MITRE', 21, '8a63d31', 'Fixed prompt/validator; single run'),
    'smoke-revised.json': ('Foundation revised smoke', 8, '8a63d31', 'Fixed prompt/validator; single run'),
    'challenge-revised.json': ('Foundation revised challenge', 6, 'eeaf3b1', 'Foundation inference unchanged by native-adapter additions'),
    'mitre-qwen.json': ('Qwen incompatible OpenAI adapter', 21, '84b1815', 'Stopped; integration failure, not a valid quality comparison'),
    'mitre-qwen-native.json': ('Qwen generic-contract native MITRE', 21, 'eeaf3b1', 'Stopped to prioritize incident-bound prompt'),
    'challenge-qwen.json': ('Qwen generic-contract challenge', 6, 'f4f08d7', 'Stopped; protected-target failure retained'),
    'mitre-qwen-bounded.json': ('Qwen incident-bound MITRE', 21, 'cb873aa', 'Final candidate; single run'),
    'challenge-qwen-bounded.json': ('Qwen incident-bound challenge', 6, 'cb873aa', 'Final candidate; reused failed challenge is development data'),
    'mitre-qwen-policy.json': ('Qwen policy-filtered MITRE', 21, '2888860', 'Final policy-filtered candidate; single run'),
    'challenge-qwen-policy.json': ('Qwen policy-filtered challenge', 6, '2888860', 'Final policy-filtered candidate; reused challenges are development data'),
    'mitre-foundation-policy.json': ('Foundation policy-filtered MITRE', 21, '2888860', 'Same policy-filtered input and validator as Qwen'),
    'challenge-foundation-policy.json': ('Foundation policy-filtered challenge', 6, '2888860', 'Same policy-filtered input and validator as Qwen'),
    'smoke-foundation-policy.json': ('Foundation policy-filtered smoke', 8, '2888860', 'Regression suite'),
    'smoke-qwen-policy.json': ('Qwen policy-filtered smoke', 8, '2888860', 'Regression suite'),
}

def main():
    summaries = []
    lines = ['# Containment research results', '',
             'Synthetic planning tests; no real attack execution, production certification, or proof of perfect inference. See RESEARCH.md for methods and confounds.', '',
             '| Run | Passes / completed / planned | Complete | Median seconds | Failures |',
             '|---|---|---|---|---|']
    for filename, (name, planned, revision, note) in RUNS.items():
        path = RAW / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        results = data['results']
        failures = [{'incident_id': r.get('incident_id'), 'status': r['status'],
                     'errors': [a.get('validation_error') or a.get('transport_error') for a in r['attempts'] if a.get('validation_error') or a.get('transport_error')]}
                    for r in results if not r['scenario_pass']]
        groups = {}
        for variant in {r.get('variant', 'smoke/challenge') for r in results}:
            subset = [r for r in results if r.get('variant', 'smoke/challenge') == variant]
            groups[variant] = {'passed': sum(r['scenario_pass'] for r in subset), 'total': len(subset)}
        summary = {'run': name, 'raw_file': 'research/raw/' + filename,
                   'inference_revision': revision, 'revision_note': 'Based on dispatch/source history; initial runs did not record source hashes at launch.',
                   'note': note, 'passed': sum(r['scenario_pass'] for r in results),
                   'completed': len(results), 'planned': planned, 'complete': len(results) == planned,
                   'median_latency_seconds': round(statistics.median(r['latency_seconds'] for r in results), 2),
                   'correction_cases': sum(len(r['attempts']) > 1 for r in results), 'groups': groups, 'failures': failures}
        summaries.append(summary)
        failure_names = ', '.join(f['incident_id'] for f in failures) or 'None'
        lines.append(f"| {name} | {summary['passed']} / {len(results)} / {planned} | {summary['complete']} | {summary['median_latency_seconds']} | {failure_names} |")
    lines += ['', 'Every rejection/unavailable response counts as a failed task. Partial runs are not full benchmark scores. Raw files retain all attempts and errors.', '',
              'Foundation uses Q8 weights and llama.cpp; Qwen uses Q4_K_M and Ollama with a larger output budget and explicit incident-bound schema text. These compare configured systems under a shared validator, with runtime/prompt/quantization confounds. No statistical superiority claim is warranted.']
    (ROOT / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'verification.json').write_text(json.dumps({'unit_tests_passed': 59, 'unit_test_scope': 'Local and ASUS device source tests, including simulator, checkpoint and sensitivity tests; 2026-10-10', 'runs': summaries}, indent=2))

if __name__ == '__main__':
    main()
