"""Single-pass baseline: same case and safety gates, no peer negotiation."""
import time
from council import sources
from council.protocol import compliance_state
from council.seats import (ModelClient, mock_containment, fixing_plan, mock_compliance,
                           forensic_position, review_peers, validate_fixing)
from council.severity import assess


def run(case, mode='mock', client=None, threshold=75, response_seconds=30):
    case.validate()
    context = case.context()
    context['preservation_confirmed'] = context['fixing']['host_id'] in context['incident']['compliance']['evidence_preserved_host_ids']
    client = client or ModelClient()
    start = time.monotonic()
    containment, fixing, compliance, forensic = {}, {}, {}, {}
    deadlines, reasons = [], []
    sim = sources.containment()['simulator'].Simulator(case.simulation)
    try:
        if case.fault == 'unavailable':
            raise RuntimeError('Simulated single-agent unavailable')
        if mode == 'mock':
            containment = mock_containment(context)
            fixing = fixing_plan(context, True)
            compliance = mock_compliance(context, review_peers(containment, fixing, context))
            forensic = forensic_position(context, containment, fixing)
        else:
            # Fair baseline: same validators, the same incident-bound Containment schema the council's
            # Containment seat is given, and the same single validated retry. Only negotiation differs.
            contract = {'containment': sources.containment()['agent'].decoding_schema(context['incident']),
                        'fixing': {'reason': 'rationale', 'verdict': 'propose|defer', 'actions':
                                   [{'kind': '|'.join(sources.fixing()['fixing_scenarios'].KINDS),
                                     'target_id': 'known ID', 'evidence_ids': ['known ID'], 'reason': 'why'}]},
                        'compliance': sources.compliance()['agent'].SCHEMA,
                        'forensics': {'stance': 'support|object', 'evidence_ids': ['known ID'],
                                      'reason': 'why', 'timeline': []}}
            view = context
            for attempt in (1, 2):
                combined = client.complete('single-agent', view, contract)
                try:
                    containment = sources.containment()['agent'].validate_proposal(combined['containment'], context['incident'])
                    fixing = combined['fixing']
                    validate_fixing(fixing, context)
                    compliance = sources.compliance()['agent'].validate_proposal(
                        combined['compliance'], context['incident'], review_peers(containment, fixing, context))
                    break
                except (ValueError, KeyError, TypeError) as exc:
                    if attempt == 2:
                        raise
                    view = dict(context, validation_error='Your previous reply was rejected: ' + str(exc)
                                + '. Reply again, obeying the policy limits and using only supplied IDs.')
            forensic = combined['forensics']
        validate_fixing(fixing, context)
        peers = review_peers(containment, fixing, context)
        deadlines, escalation = compliance_state(compliance, context['incident'], peers)
        reasons.extend(escalation['reasons'])
        if forensic.get('stance') not in ('support', 'object') or not forensic.get('evidence_ids') or not set(forensic['evidence_ids']) <= {e['id'] for e in context['incident']['evidence']}:
            raise ValueError('Invalid baseline forensic evidence')
        if forensic['stance'] == 'object' or any(r['stance'] != 'support' for r in compliance['action_reviews']):
            reasons.append('Single-pass plan has unresolved objections')
        if case.fault == 'deadlock':
            reasons.append('Injected unresolved single-pass disagreement')
        severity = assess(case.impact, deadlines, reasons, threshold)
        if not severity['human_required']:
            sim.advance(response_seconds if mode == 'mock' else min(time.monotonic() - start, case.simulation['horizon_seconds']))
            if not sim.apply(containment):
                raise ValueError('Baseline rejected by simulator')
            # Deliberately no extra inference calls or mid-stream revisions.
            for update in case.simulation.get('updates', []):
                sim.advance(max(sim.time, update['at']))
                sim.update(update['incident'])
            sim.advance(case.simulation['horizon_seconds'])
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, RuntimeError, OSError) as exc:
        reasons.append('Baseline seat/validation failure: ' + str(exc))
    severity = assess(case.impact, deadlines, reasons, threshold)
    return {'case_id': case.case_id, 'mode': mode, 'baseline': 'single-pass-no-negotiation',
            'status': 'ESCALATED' if severity['human_required'] else 'ACCEPTED_SINGLE_PASS_SIMULATION',
            'severity': severity, 'human_alert': {'required': severity['human_required'], 'reasons': severity['hard_stop_reasons']},
            'containment': containment, 'fixing': fixing, 'compliance': compliance, 'forensics': forensic,
            'deadlines': deadlines, 'outcomes': sim.snapshot(), 'rounds': 1,
            'latency_seconds': round(time.monotonic() - start, 4),
            'notice': 'Mock baseline is a deterministic single-pass policy, not a measured single-model comparison'}