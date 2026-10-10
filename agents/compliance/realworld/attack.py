"""Containment's 21 ATT&CK fixtures (mitre-fixtures.json, copied from the `containment` branch at
df5f359) with a compliance block added to each. Containment's expected action is the
containment peer proposal. A few confirmed cases add a Recovery peer that proposes a destructive
step under legal hold, because none of Containment's kinds are destructive and the veto would never
fire otherwise. Organizations and data are fictional; `expected` follows rules.py, not legal advice.
Authorized variants keep the same organization and data, so the right answer is that nothing is
triggered yet."""
import copy
import json
from pathlib import Path

from scenarios import S, T, ND, NOT_YET

NOW = '2026-10-11T16:00:00Z'
DISC = '2026-10-10T20:00:00Z'  # 20h before NOW: every clock still has time left

ORGS = {
    'retail_eu': ({'eu_establishment': True}, [('personal_data', ['EU'], 40000)]),
    'merchant': ({}, [('payment_card', ['US'], 25000)]),
    'clinic': ({'hipaa_covered_entity': True}, [('phi', ['US-CA'], 9000), ('personal_data', ['US-CA'], 9000)]),
    'public_saas': ({'public_company': True}, []),
    'bank_ny': ({'nydfs_covered': True}, []),
    'grid_nis2': ({'nis2_entity': True, 'eu_establishment': True}, []),
    'retail_eu_public': ({'eu_establishment': True, 'public_company': True}, [('personal_data', ['EU'], 60000)]),
}


def recovery(kind, target):
    return {'role': 'recovery', 'proposal': {'actions': [{'kind': kind, 'target_id': target}]}}


# technique -> (org, compliance-relevant fact, expected statuses, extras for the confirmed variant)
CASES = {
    'T1041': ('retail_eu', 'web-01 hosts the customer database. The outbound stream matches an export of the customer table: names, emails and order history for about 40,000 EU residents.',
              {'gdpr_art33': T}, {}),
    'T1071.001': ('merchant', 'web-01 is the checkout server and processes card numbers in memory. The attacker has had control for 5 days; no card data exfiltration confirmed yet.',
                  {'visa_compromise': [T, ND]}, {}),
    'T1021.002': ('clinic', 'From workstation-01 the attacker copied the EHR export folder: 3,100 patient records with names and diagnoses, all California patients.',
                  {'hipaa_breach': T, 'ca_1798_82': T},
                  {'hold': True, 'recovery': ('reimage_host', 'workstation-01'), 'vetoes': [('reimage_host', 'workstation-01')], 'escalate': True}),
    'T1021.001': ('public_saas', 'The compromised hosts run internal build tooling. No customer data is stored there; releases are paused while they are rebuilt.',
                  {'sec_8k_105': ND}, {'escalate': True}),
    'T1210': ('bank_ny', 'The attacker has reached three internal servers, including the loan-processing system, which is degraded and running at half capacity.',
              {'nydfs_500_17': [T, ND]}, {}),
    'T1486': ('grid_nis2', 'Encryption halted the dispatch scheduling system for 6 hours; field crews were dispatched by phone. Forensics captured a full disk image of workstation-01 before any change.',
              {'nis2_early_warning': T},
              {'hold': True, 'preserved': ['workstation-01'], 'recovery': ('reimage_host', 'workstation-01')}),
    'T1003.001': ('public_saas', 'Dumped credentials include two domain administrator accounts. No customer systems accessed so far.',
                  {'sec_8k_105': ND}, {'escalate': True}),
    'T1059.001': ('merchant', 'workstation-01 is a back-office laptop outside the card environment; network segmentation was verified by the last PCI assessment and no card systems were reached.',
                  {'visa_compromise': NOT_YET}, {}),
    'T1550.004': ('clinic', 'session-01 belongs to a billing clerk. Audit logs show the attacker viewed and downloaded 220 patient billing records with diagnosis codes, all California patients.',
                  {'hipaa_breach': T, 'ca_1798_82': [T, ND]},
                  {'hold': True, 'recovery': ('reimage_host', 'web-01'), 'vetoes': [('reimage_host', 'web-01')], 'escalate': True}),
    'T1078': ('retail_eu', 'account-01 was used to download the newsletter subscriber list: email addresses of about 15,000 EU residents.',
              {'gdpr_art33': T}, {}),
    'T1041+T1021.002': ('retail_eu_public', 'The transferred files are the customer table: names, emails and addresses for about 60,000 EU residents.',
                        {'gdpr_art33': T, 'sec_8k_105': ND},
                        {'hold': True, 'recovery': ('reimage_host', 'web-01'), 'vetoes': [('reimage_host', 'web-01')], 'escalate': True}),
}

SOURCE = ['https://attack.mitre.org/techniques/', 'agents/containment/mitre-provenance.json (containment branch)']


def scenarios():
    out = []
    for f in json.loads((Path(__file__).parent / 'mitre-fixtures.json').read_text(encoding='utf-8')):
        org_key, fact, expected, extra = CASES[f['technique']]
        org, data = ORGS[org_key]
        authorized = f['variant'] == 'authorized'
        inc = copy.deepcopy(f['incident'])
        alt = f['expected_alternatives']
        proposals = [{'role': 'containment', 'proposal': {'actions': [{'kind': alt[0][0], 'target_id': alt[0][1]}]}}] if alt else []
        if authorized:
            expected = {r: NOT_YET for r in expected}
            extra = {}
        else:
            if 'recovery' in extra:
                proposals.append(recovery(*extra['recovery']))
        s = S(inc['incident_id'], [], DISC, NOW, org, data, expected, SOURCE,
              hold=extra.get('hold', False), preserved=extra.get('preserved', ()), proposals=proposals,
              vetoes=extra.get('vetoes', ()), escalate=extra.get('escalate'))
        s['telemetry_version'] = inc['telemetry_version']
        s['evidence'] = inc['evidence'] + ([] if authorized else [{'id': 'C1', 'observation': fact}])
        s['assets'] = inc['assets']
        out.append(s)
    return out
