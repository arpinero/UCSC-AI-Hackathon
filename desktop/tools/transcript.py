"""Write a readable Markdown transcript from a council report JSON or a Sentinel run journal (.jsonl).

Usage: python3 desktop/tools/transcript.py REPORT.json|RUN.jsonl [-o OUT.md]
Only recorded data is printed. Nothing is inferred or added.
"""
import argparse
import json
from pathlib import Path


def short(value, limit=700):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + ' ...'


def summarize(proposal):
    if not isinstance(proposal, dict):
        return short(proposal)
    lines = []
    for key in ('assessment', 'reason', 'summary', 'rationale', 'verdict', 'stance'):
        if proposal.get(key):
            lines.append(f'{key}: {short(proposal[key], 500)}')
    actions = proposal.get('actions') or []
    if actions:
        lines.append('actions: ' + '; '.join(f"{a.get('kind')} -> {a.get('target_id')}" for a in actions))
    for review in proposal.get('action_reviews') or []:
        lines.append(f"review {review.get('kind')} -> {review.get('target_id')}: {review.get('stance')} ({short(review.get('reason', ''), 160)})")
    return '\n'.join('  ' + line for line in lines) or '  ' + short(proposal)


def from_report(report):
    out = [f"# Sentinel incident transcript: {report['case_id']}", '',
           f"Mode: **{report.get('mode')}**. Status: **{report.get('status')}**. Rounds: {report.get('rounds')}. "
           f"Elapsed: {report.get('latency_seconds')} s.", '', f"> {report.get('notice', '')}", '']
    sev = report.get('severity') or {}
    out += ['## Severity and escalation', '',
            f"Score {sev.get('score')} ({sev.get('band')}), human threshold {sev.get('threshold')}. "
            f"Human required: **{(report.get('human_alert') or {}).get('required')}**."]
    reasons = (report.get('human_alert') or {}).get('reasons') or sev.get('hard_stop_reasons') or []
    out += [f'- {r}' for r in reasons] + ['', '## Deliberation', '']
    for m in report.get('transcript', []):
        out += [f"**{m['sequence']}. Round {m['round']}, {m['role']}: {m['stance']}**", '', summarize(m.get('proposal')), '']
    out += ['## Votes', '']
    for d in report.get('decisions', []):
        out.append(f"- Round {d['round']}: " + ', '.join(f'{k} {v}' for k, v in d['votes'].items()))
    out += ['', '## Simulated actions and receipts', '']
    for r in report.get('tool_receipts', []):
        detail = r.get('actions') or r.get('evidence_ids') or ''
        out.append(f"- {r['kind']} on {r.get('host_id')} at t+{r.get('at_seconds')} s: {short(detail, 300)} ({r.get('verification')})")
    outcome = report.get('outcomes') or {}
    out += ['', '## Simulated outcome', '']
    for key in ('simulated_seconds', 'first_effective_control_seconds', 'blocked_attack_events', 'bytes_lost',
                'additional_hosts_compromised', 'service_disruption_seconds', 'false_positive_controls', 'policy_rejections'):
        out.append(f'- {key}: {outcome.get(key)}')
    for event in outcome.get('trace', []):
        out.append(f"- t+{event.get('at')} s: {event.get('type')} {short(event.get('key') or event.get('reason') or '', 200)}")
    out += ['', f"Recovery state: {short(report.get('recovery_state'), 400)}", '', '## Residual risks', '']
    out += [f'- {r}' for r in report.get('residual_risks', [])] or ['- none recorded']
    return out


def from_journal(events):
    first = next(e for e in events if e['type'] == 'incident')['data']
    out = [f"# Sentinel run transcript: {first['case_id']}", '', f"Mode: **{first['mode']}**. {first.get('notice', '')}", '', '## Timeline', '']
    for e in events:
        t, d = e['type'], e['data']
        if t == 'agent_started':
            line = f"{d['role']} started ({d['operation']})"
        elif t == 'agent_finished':
            line = f"{d['role']} finished in {d.get('seconds')} s\n{summarize(d.get('proposal'))}"
        elif t == 'agent_failed':
            line = f"{d['role']} FAILED: {d.get('error')}"
        elif t == 'approval_requested':
            line = f"Human checkpoint requested (approval {d['id']})"
        elif t == 'human_decision':
            line = f"Human decision: **{d['decision']}**. Reason written by the reviewer: {d['reason']}"
        elif t == 'approval_expired':
            line = 'Approval expired'
        elif t == 'completed':
            line = f"Completed with status {d.get('status')}, severity {(d.get('severity') or {}).get('score')}"
        elif t == 'error':
            line = f"ERROR: {d.get('message')}"
        else:
            continue
        out += [f"- `{e['time'][11:19]}` {line}", '']
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    path = Path(args.source)
    if path.suffix == '.jsonl':
        lines = from_journal([json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()])
    else:
        lines = from_report(json.loads(path.read_text(encoding='utf-8')))
    text = '\n'.join(lines) + '\n'
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
