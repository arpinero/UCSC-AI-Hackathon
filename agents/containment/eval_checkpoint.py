"""Atomic checkpoints retain every completed evaluation case across restarts."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import agent

def configuration(args, cases):
    return {'model': args.model, 'endpoint': args.endpoint, 'max_tokens': args.max_tokens,
            'reasoning_effort': args.reasoning_effort,
            'inference_sha256': hashlib.sha256((agent.SYSTEM + json.dumps(agent.SCHEMA, sort_keys=True) + inspect.getsource(agent.propose)).encode()).hexdigest(),
            'dataset_sha256': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()}

def load(output, config, incident_ids, resume):
    if not resume or not Path(output).exists():
        return [], []
    saved = json.loads(Path(output).read_text())
    results = saved['results']
    if saved.get('config') and saved['config'] != config:
        raise RuntimeError('Cannot resume changed inference configuration or dataset')
    if [r['incident_id'] for r in results] != incident_ids[:len(results)]:
        raise RuntimeError('Checkpoint is not the expected scenario prefix')
    if any(r.get('model') != config['model'] for r in results if r['status'] == 'validated'):
        raise RuntimeError('Checkpoint model mismatch')
    notes = saved.get('resume_notes', []) + [{'preserved_cases': len(results), 'legacy_checkpoint_without_config': 'config' not in saved,
             'note': 'All completed failures/successes preserved. Reboot/load changes affect latency comparability.'}]
    return results, notes

def save(output, data):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.json.tmp')
    with temporary.open('w') as checkpoint:
        json.dump(data, checkpoint, indent=2)
        checkpoint.flush()
        os.fsync(checkpoint.fileno())
    temporary.replace(output)
