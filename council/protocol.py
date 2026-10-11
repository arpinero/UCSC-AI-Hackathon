"""Bounded peer deliberation. Router applies agreed gates, never majority voting."""
import copy
import time
from council import sources
from council.seats import Seats, review_peers
from council.severity import assess


def compliance_state(proposal, incident, peers):
    modules = sources.compliance()
    clocks = modules['rules'].deadlines(incident['compliance'])
    statuses = {o['regime']: o['status'] for o in proposal['obligations']}
    enriched = [dict(c, status=statuses[c['regime']]) for c in clocks]
    escalation = modules['agent'].escalation(proposal, clocks, incident, peers)
    return enriched, escalation


def run(case, seats=None, max_rounds=3, threshold=75, response_seconds=30):
    if type(max_rounds) is not int or max_rounds < 1 or max_rounds > 10:
        raise ValueError('Round limit must be 1..10')
    if not isinstance(response_seconds, (int, float)) or not 0 <= response_seconds <= 120:
        raise ValueError('Synthetic response latency must be 0..120 seconds')
    case.validate()
    seats = seats or Seats()
    started = time.monotonic()
    sim = sources.containment()['simulator'].Simulator(case.simulation)
    incident = copy.deepcopy(case.incident)
    transcript, receipts, reasons, decisions = [], [], [], []
    deadlines, forensic, compliance, containment, fixing = [], {}, {}, {}, {}
    total_rounds = 0
    deferred = False
    recovery_state = {'artifacts': {a['id']: 'unchanged' for a in case.fixing['artifacts']},
                      'files': {f['id']: f['status'] for f in case.fixing['files']}}

    def message(round_number, role, stance, proposal):
        transcript.append({'sequence': len(transcript) + 1, 'round': round_number,
                           'telemetry_version': incident['telemetry_version'],
                           'role': role, 'stance': stance, 'proposal': copy.deepcopy(proposal)})

    updates = [None] + sorted(case.simulation.get('updates', []), key=lambda u: u['at'])
    try:
        for update in updates:
            phase_start = time.monotonic()
            if update:
                # Live inference can run past the update time; never move the clock backwards.
                sim.advance(max(sim.time, update['at']))
                preserved = incident['compliance']['evidence_preserved_host_ids']
                incident = copy.deepcopy(update['incident'])
                # New telemetry doesn't undo evidence already captured earlier in this run.
                incident['compliance']['evidence_preserved_host_ids'] = sorted(
                    set(preserved) | set(incident['compliance']['evidence_preserved_host_ids']))
                sim.update(incident)
                message(0, 'telemetry', 'revision', {'at': update['at'], 'evidence_ids': [e['id'] for e in incident['evidence']]})
            context = case.context(incident)
            context['fixing']['telemetry_version'] = incident['telemetry_version']
            context['preservation_confirmed'] = context['fixing']['host_id'] in incident['compliance']['evidence_preserved_host_ids']
            context['peer_messages'] = []
            if case.fault == 'unavailable':
                raise RuntimeError('Simulated seat unavailable')
            containment = seats.containment(context, [])
            fixing = seats.fixing(context, False)
            for round_number in range(1, max_rounds + 1):
                total_rounds += 1
                context['peer_messages'] = transcript[-8:]
                peers = review_peers(containment, fixing, context)
                forensic = seats.forensics(context, containment, fixing)
                compliance = seats.compliance(context, peers)
                deadlines, escalation = compliance_state(compliance, incident, peers)
                message(round_number, 'containment', 'propose', containment)
                message(round_number, 'fixing', 'propose', fixing)
                message(round_number, 'forensics', forensic['stance'], forensic)
                reviews = compliance['action_reviews']
                compliance_stance = 'veto' if any(r['stance'] == 'veto' for r in reviews) else 'object' if any(r['stance'] == 'object' for r in reviews) else 'support'
                message(round_number, 'compliance', compliance_stance, compliance)
                # Pre-agreed rule (code, not a model): a plain objection is satisfied once the condition it
                # can legally rest on is met: no legal hold, host evidence preserved, capture receipt on record.
                # Vetoes, deadline/materiality/human-request escalations and the severity gate are unaffected.
                capture_done = any(r['kind'] == 'simulated_evidence_capture' and r['host_id'] == context['fixing']['host_id']
                                   for r in receipts)
                if (compliance_stance == 'object' and not incident['compliance']['legal_hold']
                        and context['preservation_confirmed'] and capture_done and not escalation['reasons']):
                    objections = [{'kind': r['kind'], 'target_id': r['target_id'], 'reason': r['reason']}
                                  for r in reviews if r['stance'] == 'object']
                    message(round_number, 'router', 'objection_satisfied',
                            {'rule': 'No legal hold, host preserved, capture receipt recorded: plain objections do not block',
                             'objections': objections})
                    compliance_stance = 'support'
                # Negotiable legal-hold conflict must be revised to a deferral. Other
                # code-required human determinations remain binding immediately.
                nonnegotiable = [r for r in escalation['reasons'] if not r.startswith('legal hold:')]
                if nonnegotiable:
                    reasons.extend(nonnegotiable)
                    break
                current_severity = assess(context['impact'], deadlines, threshold=threshold)
                if current_severity['human_required']:
                    reasons.extend(current_severity['hard_stop_reasons'])
                    break
                if case.fault == 'deadlock':
                    forensic['stance'] = 'object'
                    message(round_number, 'forensics', 'object', {'reason': 'Injected persistent disagreement for acceptance test', 'evidence_ids': forensic['evidence_ids']})
                # A deferral with no legal hold, Compliance approval, and nothing yet captured is premature:
                # run the capture and let Fixing re-propose instead of accepting "nothing restored".
                premature_defer = (fixing.get('verdict') == 'defer' and not incident['compliance']['legal_hold']
                                   and not context['preservation_confirmed']
                                   and context['fixing']['compliance']['status'] == 'approved'
                                   and round_number < max_rounds)
                if forensic['stance'] == 'support' and compliance_stance == 'support' and not premature_defer:
                    votes = {}
                    for role in ('containment', 'fixing'):
                        vote = seats.vote(role, context, containment, fixing)
                        votes[role] = vote['stance']
                        message(round_number, role, vote['stance'], vote)
                    if any(v != 'support' for v in votes.values()):
                        if round_number == max_rounds:
                            reasons.append('Council deadlock: author seat objects to final shared plan')
                            break
                        containment = seats.containment(context, transcript[-8:])
                        context['peer_messages'] = transcript[-8:]
                        fixing = seats.fixing(context, True)
                        continue
                    # Skip recovery already executed before a telemetry update.
                    done = lambda a: (recovery_state['files'].get(a['target_id']) == 'restored_clean'
                                      or recovery_state['artifacts'].get(a['target_id'], 'unchanged') != 'unchanged')
                    controls = [a for a in fixing['actions'] if a['kind'] in sources.fixing()['fixing_scenarios'].CONTROL_KINDS and not done(a)]
                    if controls and (not context['preservation_confirmed'] or context['fixing']['compliance']['status'] != 'approved'):
                        raise ValueError('Recovery execution lacks preservation / approval')
                    decisions.append({'telemetry_version': incident['telemetry_version'], 'round': round_number,
                                      'votes': {r: 'support' for r in ('containment', 'forensics', 'compliance', 'fixing')},
                                      'containment': copy.deepcopy(containment), 'fixing': copy.deepcopy(fixing)})
                    delay = response_seconds if seats.mode == 'mock' else time.monotonic() - phase_start
                    sim.advance(min(case.simulation['horizon_seconds'], sim.time + max(0, delay)))
                    if not sim.apply(containment):
                        raise ValueError('Simulator rejected accepted containment')
                    if controls:
                        receipts.append({'kind': 'simulated_restoration', 'host_id': context['fixing']['host_id'],
                                         'at_seconds': sim.time, 'actions': copy.deepcopy(controls),
                                         'verification': 'Fixture-based synthetic state change; no real system touched'})
                        for control in controls:
                            kind, target = control['kind'], control['target_id']
                            if kind == 'restore_from_backup':
                                recovery_state['files'][target] = 'restored_clean'
                            else:
                                recovery_state['artifacts'][target] = {'remove_artifact': 'removed',
                                    'reenable_service': 'enabled', 'disable_account': 'disabled'}[kind]
                        if any(a['kind'] == 'remove_artifact' and a['target_id'] == 'bin-ransom' for a in controls):
                            for event in sim.case['events']:
                                if event['kind'] == 'local_damage':
                                    event['until'] = min(event['until'], sim.time)
                    deferred = any(a['kind'] in ('defer_restore', 'request_compliance_review') for a in fixing['actions'])
                    break
                if round_number == max_rounds:
                    reasons.extend(escalation['reasons'])
                    reasons.append('Council deadlock: unanimous acceptance not reached within round cap')
                    break
                # Capture is a synthetic read-only tool receipt, not an LLM claim.
                # Existing hold fixtures intentionally keep their uncompleted imaging.
                if not incident['compliance']['legal_hold'] and not context['preservation_confirmed']:
                    receipt = {'kind': 'simulated_evidence_capture', 'host_id': context['fixing']['host_id'],
                               'evidence_ids': [e['id'] for e in incident['evidence']],
                               'at_seconds': sim.time, 'verification': 'Simulation receipt only'}
                    receipts.append(receipt)
                    # Make the capture visible to every seat; otherwise a live Fixing model only sees
                    # Compliance's earlier "capture first" objection and defers forever.
                    message(round_number, 'tool', 'receipt', receipt)
                    context['preservation_confirmed'] = True
                    context['incident']['compliance']['evidence_preserved_host_ids'].append(context['fixing']['host_id'])
                    incident = copy.deepcopy(context['incident'])
                peer_messages = [{'role': 'forensics', **forensic}, {'role': 'compliance', 'stance': compliance_stance, 'proposal': compliance}]
                containment = seats.containment(context, peer_messages)
                context['peer_messages'] = transcript[-8:]
                fixing = seats.fixing(context, True)
            if reasons:
                break
        if not reasons:
            sim.advance(case.simulation['horizon_seconds'])
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, RuntimeError, OSError) as exc:
        reasons.append('Seat/validation failure: ' + str(exc))
    severity = assess(case.impact, deadlines, reasons, threshold)
    status = 'ESCALATED' if severity['human_required'] else 'CONTAINED_RECOVERY_DEFERRED' if deferred else 'RESOLVED_SIMULATION'
    outcome = sim.snapshot()
    residual = []
    if outcome['local_files_damaged']:
        residual.append('Local encryption caused simulated damage; network isolation alone cannot stop local execution')
    if deferred:
        residual.append('Recovery deferred; evidence preservation or legal-hold release still required')
    if case.impact['confirmed'] and any(not f['latest_backup_clean'] for f in case.fixing['files']):
        residual.append('Files with contaminated backups were not restored; clean recovery source required')
        if status == 'RESOLVED_SIMULATION':
            status = 'CONTAINED_PARTIAL_RECOVERY'
    if any(e.get('decision') == 'investigate' for e in containment.get('evidence_review', [])) and status == 'RESOLVED_SIMULATION':
        status = 'INVESTIGATION_PENDING'
        residual.append('Authorization/telemetry remains uncertain; evidence requested')
    return {'case_id': case.case_id, 'mode': seats.mode, 'status': status,
            'severity': severity, 'human_alert': {'required': severity['human_required'], 'reasons': severity['hard_stop_reasons']},
            'rounds': total_rounds, 'latency_seconds': round(time.monotonic() - started, 4),
            'synthetic_response_seconds': response_seconds if seats.mode == 'mock' else None,
            'decisions': decisions, 'containment': containment, 'fixing': fixing,
            'compliance': compliance, 'forensics': forensic, 'deadlines': deadlines,
            'transcript': transcript, 'tool_receipts': receipts, 'outcomes': outcome,
            'recovery_state': recovery_state,
            'residual_risks': residual, 'provenance': case.provenance,
            'notice': 'Simulation only. No real containment/restoration or legal notifications. Mock mode is not LLM performance.'}