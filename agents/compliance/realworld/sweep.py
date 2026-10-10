"""Run the real-world suite across every local Ollama model, one at a time.

Keeps polling for newly pulled models until --until-empty finds nothing new.
A model with schema failures on the OpenAI-compatible path is retried on the
native /api/chat path. Results: results/sweep/<model>__<api>.json + summary.md.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

import evaluate  # realworld/evaluate.py (puts the agent on sys.path)

OUT = Path(__file__).parent / 'results' / 'sweep'
SKIP = {'nemotron-3-super:latest', 'nomic-embed-text:latest'}  # 86 GB; embeddings


def local_models():
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags') as r:
        return sorted(m['name'] for m in json.load(r)['models'] if m['name'] not in SKIP)


def run(model, api):
    os.environ['COMPLIANCE_API'] = api
    import agent
    importlib.reload(agent)
    evaluate.propose = agent.propose
    summary = evaluate.run(model, argparse.Namespace(endpoint=agent.ENDPOINT))
    path = OUT / f"{model.replace('/', '_').replace(':', '_')}__{api}.json"
    path.write_text(json.dumps(summary, indent=2))
    subprocess.run(['ollama', 'stop', model], capture_output=True)
    return summary


def write_summary():
    rows = []
    for f in OUT.glob('*.json'):
        s = json.loads(f.read_text())
        model, api = f.stem.rsplit('__', 1)
        rows.append((s['scenario_pass_rate'], s['regime_accuracy'], model, api, s))
    lines = ['| model | api | pass | regime acc | schema valid | first try | mean s |', '|---|---|---|---|---|---|---|']
    for _, _, model, api, s in sorted(rows, key=lambda r: (-r[0], -r[1], r[4]['mean_latency_seconds'])):
        lines.append(f"| {model} | {api} | {s['scenario_pass_rate']:.0%} | {s['regime_accuracy']:.0%} | "
                     f"{s['schema_valid_rate']:.0%} | {s['first_attempt_rate']:.0%} | {s['mean_latency_seconds']:.1f} |")
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    done = {f.stem for f in OUT.glob('*.json')}
    idle = 0
    while idle < 3:  # stop after ~30 min with nothing new to test
        todo = [m for m in local_models() if f"{m.replace('/', '_').replace(':', '_')}__openai" not in done]
        if not todo:
            idle += 1
            time.sleep(600)
            continue
        idle = 0
        model = todo[0]
        s = run(model, 'openai')
        done.add(f"{model.replace('/', '_').replace(':', '_')}__openai")
        if s['schema_valid_rate'] < 1:
            run(model, 'native')
        write_summary()
        print('SUMMARY UPDATED', model, flush=True)
