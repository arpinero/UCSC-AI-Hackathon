"""One synthetic ATT&CK T1498.001 (Direct Network Flood) case for the Sentinel demo.

Two compromised internal hosts flood an external address and saturate the shared uplink. It is derived
from the existing mitre-T1041 case, so every action stays inside Containment's existing vocabulary:
block_egress, isolate_host and request_evidence. The simulator has no packet-flood model, so the flood
is modelled as an outbound flow and its `bytes_lost` metric means flood traffic sent, not stolen data.
Author-created text; ATT&CK supplies the technique taxonomy only. Inbound DDoS filtering is out of
scope because Containment has no ingress-filter action.
"""
import copy
from council.scenarios import attach_fixing, impact_from

CASE_ID = 'mitre-T1498-001'
SOURCE = ['https://attack.mitre.org/techniques/T1498/001/', 'council/ddos.py']
FLOOD = ('Confirmed outbound flood (ATT&CK T1498.001, Direct Network Flood): workstation-01 and kiosk-02 are sending '
         'about 40,000 packets per second to victim-01, an address outside our network, and the traffic has saturated the shared internet uplink. '
         'Both hosts run the same botnet agent.')
KIOSK = 'Confirmed: kiosk-02 is the second source of the same flood and runs the same botnet agent. It is a non-critical lobby kiosk.'
BUSINESS = ('No personal, payment or regulated data is involved. The flood only consumes bandwidth, '
            'and web-01, which serves customers, is slow because the uplink is saturated.')


def build(base):
    """`base` is the existing mitre-T1041 CouncilCase; a deep copy is reshaped into the flood case."""
    case = copy.deepcopy(base)
    case.case_id = CASE_ID
    incident = case.incident
    incident['incident_id'] = CASE_ID
    incident['assets'] = [
        {'id': 'web-01', 'type': 'host', 'critical': True},
        {'id': 'workstation-01', 'type': 'host', 'critical': False},
        {'id': 'kiosk-02', 'type': 'host', 'critical': False},
        {'id': 'victim-01', 'type': 'destination', 'protected': False},
        {'id': 'collector-01', 'type': 'destination', 'protected': True},
    ]
    incident['policy']['allowed_actions'] = ['isolate_host', 'block_egress', 'request_evidence']
    incident['evidence'] = [
        {'id': 'M1', 'observation': FLOOD, 'source_host_ids': ['workstation-01', 'kiosk-02'],
         'actionable_for': [{'kind': 'block_egress', 'target_id': 'victim-01'},
                            {'kind': 'request_evidence', 'target_id': 'workstation-01'}]},
        {'id': 'M2', 'observation': KIOSK, 'source_host_ids': ['kiosk-02'],
         'actionable_for': [{'kind': 'isolate_host', 'target_id': 'kiosk-02'},
                            {'kind': 'request_evidence', 'target_id': 'kiosk-02'}]},
        {'id': 'C1', 'observation': BUSINESS, 'actionable_for': []},
    ]
    incident['compliance'] = {'now': '2026-10-11T16:00:00Z', 'discovered_at': '2026-10-11T15:00:00Z',
                              'organization': {}, 'affected_data': [], 'legal_hold': False,
                              'evidence_preserved_host_ids': []}
    # Recovery: the botnet agent is installed as a service on workstation-01 (T1543.003 fixture).
    case.fixing, truth = attach_fixing(incident, 'T1543.003', 'approved')
    case.impact = impact_from(incident)
    case.impact.update(confirmed=True, exfiltration=False, sensitive_data=False, critical_asset=False,
                       affected_hosts=2, data_records=0)
    flood = lambda source: {'kind': 'exfil', 'source': source, 'destination': 'victim-01', 'at': 0, 'until': 600, 'rate': 20000}
    case.simulation = {'incident': copy.deepcopy(incident), 'truth': 'malicious',
                       'events': [flood('workstation-01'), flood('kiosk-02')], 'dependencies': [], 'updates': [],
                       'initial_compromised': ['workstation-01', 'kiosk-02'], 'horizon_seconds': 600}
    case.expected = {'containment_alternatives': [['block_egress', 'victim-01']], 'fixing_variant': 'approved',
                     'fixing_truth': truth, 'compliance_status': {}, 'family': 'ddos'}
    case.provenance = SOURCE
    return case.validate()
