"""Local manager reports and human-alert artifacts; no external disclosure."""
import hashlib
import json
import re
from pathlib import Path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def save(result, directory):
    directory = Path(directory).resolve()
    stem = re.sub(r'[^A-Za-z0-9_.-]', '_', result['case_id'])[:80]
    stem += '-' + hashlib.sha256(result['case_id'].encode()).hexdigest()[:8]
    path = directory / (stem + '.json')
    atomic_json(path, result)
    lines = ['# Cyber Incident Response Council', '',
             f"**{result['status']}** — {result['case_id']}", '',
             f"Severity: **{result['severity']['score']}/100 ({result['severity']['band']})**",
             f"Mode: **{result['mode']}**; rounds: {result['rounds']}", '', result['notice'], '',
             '## Severity contributions', json.dumps(result['severity']['factors'], indent=2), '',
             '## Human alert', *['- ' + r for r in result['human_alert']['reasons']], '',
             '## Evidence timeline', *['- ' + json.dumps(e) for e in result['forensics'].get('timeline', [])], '',
             '## Regulatory clocks (demo rules, not legal advice)', *['- ' + json.dumps(d) for d in result['deadlines']], '',
             '## Simulated actions and outcomes', '```json',
             json.dumps({'decisions': result['decisions'], 'receipts': result['tool_receipts'], 'outcomes': result['outcomes'],
                         'recovery_state': result['recovery_state']}, indent=2), '```', '',
             '## Residual risks', *['- ' + r for r in result['residual_risks']], '',
             '## Debate transcript', *[f"- R{m['round']} v{m['telemetry_version']} **{m['role']} / {m['stance']}**: " + json.dumps(m['proposal']) for m in result['transcript']]]
    markdown = path.with_suffix('.md')
    temporary = markdown.with_suffix('.md.tmp')
    temporary.write_text('\n'.join(lines) + '\n')
    temporary.replace(markdown)
    alert_path = directory / 'alerts' / (stem + '.json')
    if result['human_alert']['required']:
        atomic_json(alert_path,
                    {'case_id': result['case_id'], 'status': 'HUMAN_REQUIRED',
                     'reasons': result['human_alert']['reasons'], 'report': str(path)})
    elif alert_path.exists():
        # The same report is a latest-state artifact; clear only its own stale
        # alert when a rerun replaces it with a non-escalated result.
        alert_path.unlink()
    return path