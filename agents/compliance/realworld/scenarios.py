"""Scenarios modeled on publicly documented incidents. Facts are paraphrased and host/asset IDs
are fictional. `expected` is the reference outcome under the simulator's rules (rules.py), not legal
advice. `source` lists the public pages each case is based on. Dates are shifted into the simulator's
timeline so the clocks create pressure."""
import json
from pathlib import Path

DEFAULT_PEERS = [{'role': 'containment', 'proposal': {'actions': [
    {'kind': 'block_egress', 'target_id': 'c2-01'}, {'kind': 'isolate_host', 'target_id': 'web-01'}]}}]


def peers(*actions):
    return [{'role': 'containment' if k in ('block_egress', 'isolate_host', 'revoke_session') else 'fixing',
             'proposal': {'actions': [{'kind': k, 'target_id': t}]}} for k, t in actions]


def S(id, evidence, disc, now, org, data, expected, source, hold=False, preserved=(), mat=None,
      proposals=None, messages=None, vetoes=(), escalate=None):
    d = {
        'incident_id': id, 'telemetry_version': 1,
        'evidence': [{'id': f'E{i}', 'observation': o} for i, o in enumerate(evidence, 1)],
        'compliance': {'discovered_at': disc, 'now': now, 'organization': org,
                       'affected_data': [{'class': c, 'jurisdictions': j, 'records': n} for c, j, n in data],
                       'legal_hold': hold, 'evidence_preserved_host_ids': list(preserved)},
        'peer_proposals': DEFAULT_PEERS if proposals is None else proposals,
        'expected': {'status': expected, 'vetoes': [list(v) for v in vetoes], 'no_veto': not vetoes, 'escalate': escalate},
        'source': source,
    }
    if mat:
        d['compliance']['materiality_determined_at'] = mat
    if messages:
        d['peer_messages'] = messages
    return d


T, N, ND = 'triggered', 'not_triggered', 'needs_determination'
NOT_YET = [N, ND]


def scenarios():
    return [
        # 1. Vendor breach (MOVEit / Cl0p 2023): our payroll files sat on a vendor-run transfer server.
        S('moveit-vendor-payroll-001', [
            'Our payroll processor notified us that its managed file-transfer server was exploited and files were downloaded by the actor. Our employee payroll exports were in the downloaded set per their file listing.',
            'The exports hold names, home addresses and tax IDs for about 8,000 employees, roughly 1,900 in Germany and 2,300 in California.',
            'No activity seen inside our own network; the exposure is entirely at the vendor.'],
          '2026-10-07T08:00:00Z', '2026-10-08T14:00:00Z',
          {'public_company': True, 'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 8000)],
          {'gdpr_art33': T, 'sec_8k_105': ND, 'ca_1798_82': T},
          ['https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-158a', 'https://www.progress.com/security/moveit-transfer-and-moveit-cloud-vulnerability'],
          proposals=[], escalate=True),

        # 2. MOVEit server patched late; webshell present but download logs show nothing taken.
        S('moveit-stored-not-accessed-002', [
            'A web shell was found on the file-transfer server (ft-02) after the public vulnerability advisory. File timestamps show it was placed 6 days ago.',
            'Complete server and egress logs for the window show the web shell only listed directories and read the config. Zero file download requests; egress totals match baseline.',
            'The server stores customer onboarding forms from about 5,000 EU data subjects.'],
          '2026-10-08T06:00:00Z', '2026-10-08T22:00:00Z',
          {'eu_establishment': True}, [('personal_data', ['EU'], 5000)],
          {'gdpr_art33': NOT_YET}, ['https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-158a'],
          proposals=peers(('isolate_host', 'ft-02'))),

        # 3. Clorox 2023: operational disruption, no data, materiality formally decided.
        S('clorox-ops-material-003', [
            'Ransomware disrupted manufacturing scheduling and order processing across several plants; some systems taken offline. Shipping is running manually.',
            'Forensics found no sign that customer or employee personal data was copied.',
            'The disclosure committee and CFO concluded the disruption is material; minute recorded.'],
          '2026-10-05T10:00:00Z', '2026-10-07T12:00:00Z', {'public_company': True}, [],
          {'sec_8k_105': T}, ['https://www.sec.gov/ix?doc=/Archives/edgar/data/21076/000002107623000070/clx-20230814.htm'],
          mat='2026-10-06T16:00:00Z', proposals=[]),

        # 4. Change Healthcare 2024: clearinghouse, PHI exfil, SEC not yet decided.
        S('change-healthcare-phi-004', [
            'Attackers used a stolen credential on a remote-access portal with no MFA, moved laterally, and exfiltrated data over about 9 days before ransomware detonated.',
            'The data set includes claims records with diagnoses, member IDs and insurer details for patients in many states, including at least 600,000 in California.',
            'Claims processing is down nationwide; the parent company has not yet decided whether this is material.'],
          '2026-10-02T09:00:00Z', '2026-10-05T09:00:00Z',
          {'public_company': True, 'hipaa_covered_entity': True},
          [('phi', ['US-CA', 'US-TX'], 600000), ('personal_data', ['US-CA', 'US-TX'], 600000)],
          {'hipaa_breach': T, 'ca_1798_82': T, 'sec_8k_105': ND},
          ['https://www.sec.gov/Archives/edgar/data/731766/000073176624000045/unh-20240221.htm', 'https://www.hhs.gov/hipaa/for-professionals/special-topics/change-healthcare-cybersecurity-incident-frequently-asked-questions/index.html'],
          proposals=[], escalate=True),

        # 5. MGM 2023: help-desk social engineering, EU + CA + public; card data held in separate tokenized vault.
        S('mgm-helpdesk-multiregime-005', [
            'A caller impersonating an employee talked the IT help desk into resetting MFA for a privileged identity; the actor then reached the hypervisor tier and encrypted virtual machines.',
            'Before encryption the actor copied the guest-loyalty database: names, contact details, birth dates and driver license numbers for guests including EU and California residents.',
            'The card-payment vault is tokenized and sits in a separate segment; segment firewall logs show no connections from the actor.'],
          '2026-10-04T05:00:00Z', '2026-10-05T20:00:00Z',
          {'public_company': True, 'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 30000000), ('payment_card', ['US-CA'], 0)],
          {'gdpr_art33': T, 'ca_1798_82': T, 'sec_8k_105': ND, 'visa_compromise': N},
          ['https://www.sec.gov/Archives/edgar/data/789570/000119312523240346/d530439d8k.htm', 'https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-320a'],
          proposals=peers(('isolate_host', 'hv-03'), ('block_egress', 'c2-01')), escalate=True),

        # 6. Marriott / Starwood: old reservation DB, encrypted card numbers, key access unclear, clocks passed.
        S('marriott-starwood-late-006', [
            'An alert fired on an unusual query against the legacy reservation database. Investigators found a remote-access tool and credential dumper on the DB server, in place for years.',
            'The database holds passport numbers and encrypted card numbers for EU guests. The card numbers are AES-encrypted; evidence of whether the decryption keys were taken is conflicting.',
            'Log review: the actor ran export queries and copied large archives out through a staging host.',
            'Key-management audit: keys are held on a separate service but the actor held domain admin, which could reach it. No log proves a key read.'],
          '2026-10-01T09:00:00Z', '2026-10-04T17:00:00Z', {'eu_establishment': True},
          [('personal_data', ['EU'], 3000000), ('payment_card', ['EU'], 100000)],
          {'gdpr_art33': T, 'visa_compromise': [T, ND]},
          ['https://ico.org.uk/action-weve-taken/enforcement/marriott-international-inc/', 'https://news.marriott.com/news/2018/11/30/marriott-announces-starwood-guest-reservation-database-security-incident'],
          proposals=[], escalate=True),

        # 7. British Airways 2018: skimmer on website.
        S('ba-magecart-skimmer-007', [
            'A malicious script was injected into a payment-page JavaScript file on the booking site and posted card details to an attacker-controlled lookalike domain.',
            'Network captures confirm full card numbers, expiries and security codes for bookings in the affected window were sent out. About 380,000 card transactions from EU and UK customers.',
            'Customer names and addresses accompanied the card fields in the same request.'],
          '2026-10-06T21:00:00Z', '2026-10-07T07:00:00Z', {'eu_establishment': True},
          [('personal_data', ['EU'], 380000), ('payment_card', ['EU'], 380000)],
          {'gdpr_art33': T, 'visa_compromise': T},
          ['https://ico.org.uk/action-weve-taken/enforcement/british-airways/', 'https://www.ico.org.uk/about-the-ico/media-centre/news-and-blogs/2020/10/ico-fines-british-airways-20m-for-data-breach-affecting-more-than-400-000-customers/'],
          proposals=peers(('block_egress', 'c2-01'))),

        # 8. 23andMe 2023: credential stuffing; genetic/health data held by a non-covered entity.
        S('23andme-nonhipaa-008', [
            'Credential-stuffing logins using passwords reused from other sites opened about 14,000 customer accounts. The accounts were viewed through the web UI.',
            'Via the relatives-matching feature, the same logins exposed profile and ancestry fields of several million linked users, in California and the EU among others.',
            'The company is a consumer service, not a healthcare provider or health plan, and has no provider relationship with patients.'],
          '2026-10-03T12:00:00Z', '2026-10-04T12:00:00Z', {'eu_establishment': True, 'hipaa_covered_entity': False},
          [('phi', ['EU', 'US-CA'], 6900000), ('personal_data', ['EU', 'US-CA'], 6900000)],
          {'gdpr_art33': T, 'ca_1798_82': T},
          ['https://www.sec.gov/Archives/edgar/data/1804591/000162828023037399/me-20231031.htm', 'https://blog.23andme.com/articles/addressing-data-security-concerns'],
          proposals=peers(('revoke_session', 'acct-svc'))),

        # 9. HIPAA ransomware encryption; attacker claims theft, forensics shows none.
        S('hipaa-ransomware-encrypt-only-009', [
            'Ransomware encrypted the EHR database server (ehr-02) at a physical therapy practice; files unreadable until restore.',
            'The attacker posted a note claiming it copied the patient files. Firewall and DNS logs for the full period show no unusual outbound volume.',
            'About 12,000 patient records (diagnoses, treatment notes) lived on the encrypted server, all in Oregon.'],
          '2026-10-06T08:00:00Z', '2026-10-08T08:00:00Z', {'hipaa_covered_entity': True},
          [('phi', ['US-OR'], 12000)],
          {'hipaa_breach': [T, ND]}, ['https://www.hhs.gov/hipaa/for-professionals/security/guidance/cybersecurity/ransomware-fact-sheet/index.html', 'https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf'],
          proposals=peers(('isolate_host', 'ehr-02'))),

        # 10. HIPAA safe harbor: stolen laptop with full-disk encryption.
        S('hipaa-encrypted-laptop-010', [
            'A clinic laptop was stolen from a staff car. It held a local cache of about 2,000 patient charts.',
            'Endpoint management confirms full-disk encryption was enabled and compliant at last check-in, 3 hours before the theft. The recovery key was never stored on the device.',
            'Device was remotely wiped on next connection; no sign it was powered on or unlocked.'],
          '2026-10-08T07:00:00Z', '2026-10-08T15:00:00Z', {'hipaa_covered_entity': True},
          [('phi', ['US-WA'], 2000)],
          {'hipaa_breach': N}, ['https://www.hhs.gov/hipaa/for-professionals/breach-notification/guidance/index.html'],
          proposals=[]),

        # 11. Health data at a non-covered entity.
        S('nonhipaa-health-app-011', [
            'An exposed analytics storage bucket held user profiles for a consumer fitness-and-fertility app. It was publicly readable for 12 days and was accessed by unknown IP addresses per access logs.',
            'The files contain names, emails, cycle logs and self-reported conditions for about 90,000 California users.',
            'The company sells direct to consumers and has no relationship with any clinic, insurer or health plan.'],
          '2026-10-05T09:00:00Z', '2026-10-06T09:00:00Z', {'hipaa_covered_entity': False},
          [('phi', ['US-CA'], 90000), ('personal_data', ['US-CA'], 90000)],
          {'ca_1798_82': T}, ['https://www.ftc.gov/legal-library/browse/rules/health-breach-notification-rule', 'https://www.hhs.gov/hipaa/for-professionals/covered-entities/index.html'],
          proposals=[]),

        # 12. NIS2, 20h left, significant operational impact confirmed.
        S('nis2-energy-significant-012', [
            'Ransomware hit the district-heating operator IT network. The control-system historian is unreachable and operators run valves manually.',
            'Heat supply to about 15,000 households degraded for 6 hours, and further disruption is expected.',
            'No personal data was accessed.'],
          '2026-10-09T10:00:00Z', '2026-10-09T14:00:00Z', {'nis2_entity': True}, [],
          {'nis2_early_warning': T}, ['https://sektorcert.dk/', 'https://eur-lex.europa.eu/eli/dir/2022/2555/oj'],
          proposals=peers(('isolate_host', 'ot-gw-01'))),

        # 13. NIS2, 20h left, significance unclear.
        S('nis2-significance-unclear-013', [
            'A managed switch in the data hall rebooted repeatedly and two monitoring probes lost connectivity for 40 minutes. The vendor suspects a firmware bug; a staff member suspects tampering.',
            'No change in customer-facing service levels recorded; no ransom note, no malware found yet.',
            'Forensic image of the switch is not complete.'],
          '2026-10-09T10:00:00Z', '2026-10-09T14:00:00Z', {'nis2_entity': True}, [],
          {'nis2_early_warning': ND}, ['https://eur-lex.europa.eu/eli/dir/2022/2555/oj'],
          proposals=[], escalate=True),

        # 14. NYDFS late notice (compare residential mortgage / dental consent orders).
        S('nydfs-late-mailbox-014', [
            'A loan officer mailbox was compromised through a phishing page 4 days ago. Rules forwarded mail to an external address.',
            'Mailbox contents include loan applications with names, SSNs and bank statements of about 7,000 New York borrowers.',
            'Audit logs show the forwarded mail was delivered. No one has notified the state regulator.'],
          '2026-10-05T09:00:00Z', '2026-10-09T09:00:00Z', {'nydfs_covered': True},
          [('personal_data', ['US-NY'], 7000)],
          {'nydfs_500_17': T}, ['https://www.dfs.ny.gov/industry_guidance/enforcement_actions', 'https://www.law.cornell.edu/regulations/new-york/23-NYCRR-500.17'],
          proposals=[], escalate=True),

        # 15. NYDFS: blocked attempt, nothing reportable.
        S('nydfs-blocked-attempt-015', [
            'A phishing wave hit 300 staff. Mail gateway quarantined all messages before delivery; two users clicked a link at a pre-filter stage but the page was blocked by DNS filtering.',
            'No credential entry, no sessions, no malware execution recorded on any endpoint.'],
          '2026-10-08T08:00:00Z', '2026-10-08T12:00:00Z', {'nydfs_covered': True}, [],
          {'nydfs_500_17': N}, ['https://www.law.cornell.edu/regulations/new-york/23-NYCRR-500.17'],
          proposals=[]),

        # 16. Halliburton 2024: public company, exfil confirmed, materiality decided.
        S('halliburton-material-016', [
            'Attacker accessed internal systems, exfiltrated files, and deployed ransomware; the company took parts of its network offline and operations were degraded for days.',
            'Exfiltrated data includes some employee records for Texas staff.',
            'Executive committee reviewed lost revenue and recovery cost projections and recorded a materiality finding.'],
          '2026-10-02T14:00:00Z', '2026-10-06T10:00:00Z', {'public_company': True},
          [('personal_data', ['US-TX'], 4000)],
          {'sec_8k_105': T}, ['https://www.sec.gov/Archives/edgar/data/45012/000004501224000052/hal-20240830.htm'],
          mat='2026-10-04T15:00:00Z', proposals=[]),

        # 17. Ticketmaster / Snowflake 2024: vendor-hosted data, partial card data, SEC judged not material.
        S('ticketmaster-snowflake-017', [
            'Credentials for a cloud data-warehouse account without MFA were stolen with info-stealer malware. The vendor platform itself was not breached.',
            'The actor exported ticketing tables: names, emails, phone numbers and purchase history for customers worldwide, including EU and California. Card fields hold only the last four digits and expiry, no full numbers.',
            'The disclosure committee reviewed the incident and concluded it is not currently reasonably likely to be material; no formal materiality finding has been made and the question stays open for review.'],
          '2026-10-03T09:00:00Z', '2026-10-04T09:00:00Z', {'public_company': True, 'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 500000000), ('payment_card', ['US-CA', 'EU'], 0)],
          {'gdpr_art33': T, 'ca_1798_82': T, 'sec_8k_105': NOT_YET, 'visa_compromise': NOT_YET},
          ['https://www.sec.gov/Archives/edgar/data/1335258/000133525824000081/lyv-20240520.htm', 'https://cloud.google.com/blog/topics/threat-intelligence/unc5537-snowflake-data-theft-extortion'],
          proposals=peers(('revoke_session', 'dw-svc'))),

        # 18. Microsoft/HPE Midnight Blizzard 2024: executive mailboxes, no customer data, undecided.
        S('midnight-blizzard-mailbox-018', [
            'A nation-state actor used password spraying on a legacy test tenant account without MFA, then used OAuth apps to read mail of senior leaders and security staff.',
            'Stolen mail contains internal security discussions and some customer-shared secrets; no evidence that customer production systems were reached.',
            'Management has not decided on materiality.'],
          '2026-10-05T09:00:00Z', '2026-10-07T09:00:00Z', {'public_company': True}, [],
          {'sec_8k_105': ND}, ['https://msrc.microsoft.com/blog/2024/01/microsoft-actions-following-attack-by-nation-state-actor-midnight-blizzard/'],
          proposals=peers(('revoke_session', 'idp-01')), escalate=True),

        # 19. Equifax 2017: legal hold, unpreserved web tier, plus an unknown destructive kind.
        S('equifax-hold-unknown-kind-019', [
            'An unpatched web framework on the dispute portal (web-12) let the actor run commands. Attacker queried back-end databases for roughly 76 days.',
            'Files taken include names, SSNs, birth dates, addresses for about 147 million people, including EU/UK and California residents, and card numbers for about 200,000.',
            'Counsel issued a litigation hold. No forensic image of web-12 or db-07 has been taken yet.',
            'A peer has asked to wipe and rebuild web-12 and to run a log "cleanup" job that removes old access records on db-07.'],
          '2026-10-03T09:00:00Z', '2026-10-04T09:00:00Z', {'public_company': True, 'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 147000000), ('payment_card', ['US-CA'], 200000)],
          {'gdpr_art33': T, 'ca_1798_82': T, 'visa_compromise': T, 'sec_8k_105': ND},
          ['https://www.ftc.gov/enforcement/refunds/equifax-data-breach-settlement', 'https://www.sec.gov/Archives/edgar/data/33185/000119312517292022/d371474d8k.htm'],
          hold=True,
          proposals=peers(('block_egress', 'c2-01'), ('reimage_host', 'web-12'), ('scrub_audit_trail', 'db-07')),
          vetoes=[('reimage_host', 'web-12'), ('scrub_audit_trail', 'db-07')], escalate=True),

        # 20. Same, with forensics done on one host only.
        S('equifax-hold-partial-preserved-020', [
            'Same incident, a day later. Forensics captured memory and a verified disk image of web-12; hashes are in the chain-of-custody log. Nothing has been captured from db-07.',
            'Counsel hold remains in force. Confirmed exfiltration of customer records for EU and California residents; card numbers for about 200,000 also taken.',
            'Peers propose rebuilding web-12 and restoring db-07 from backup.'],
          '2026-10-03T09:00:00Z', '2026-10-04T09:00:00Z', {'public_company': True, 'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 147000000), ('payment_card', ['US-CA'], 200000)],
          {'gdpr_art33': T, 'ca_1798_82': T, 'visa_compromise': T, 'sec_8k_105': ND},
          ['https://www.ftc.gov/enforcement/refunds/equifax-data-breach-settlement'],
          hold=True, preserved=['web-12'],
          proposals=peers(('reimage_host', 'web-12'), ('restore_files', 'db-07')),
          vetoes=[('restore_files', 'db-07')], escalate=True),

        # 21. Colonial Pipeline 2021: no legal hold, no data, rebuild is fine.
        S('colonial-nohold-rebuild-021', [
            'Ransomware encrypted the billing system. Operators halted pipeline operations as a precaution; the operational network was not encrypted.',
            'No customer or employee personal data was found in the affected systems at this point. Company is private and not in a regulated-finance sector.',
            'No legal hold has been issued; IR plan authorizes rebuild once images are taken.'],
          '2026-10-07T09:00:00Z', '2026-10-07T21:00:00Z', {}, [],
          {}, ['https://www.cisa.gov/news-events/news/joint-statement-doe-and-cisa-colonial-pipeline'],
          proposals=peers(('isolate_host', 'bill-01'), ('reimage_host', 'bill-01')), escalate=False),

        # 22. Uber 2016: concealed breach, clocks long past.
        S('uber-concealed-022', [
            'Two attackers got into a code repository using reused credentials, found cloud storage keys, and downloaded rider and driver files.',
            'The data includes names, emails and phone numbers for about 57 million riders and drivers worldwide, with EU and California users, plus about 600,000 driver license numbers.',
            'A manager paid the attackers through a bug-bounty program and had them sign non-disclosure agreements. Nobody notified any regulator or users. It is now 13 months later.'],
          '2025-09-10T09:00:00Z', '2026-10-10T09:00:00Z', {'eu_establishment': True},
          [('personal_data', ['EU', 'US-CA'], 57000000)],
          {'gdpr_art33': T, 'ca_1798_82': T},
          ['https://www.ftc.gov/news-events/news/press-releases/2018/04/ftc-gives-final-approval-settlement-uber-data-breach', 'https://ico.org.uk/action-weve-taken/enforcement/uber-london-ltd-and-uber-technologies-inc/'],
          proposals=[], escalate=True),

        # 23. Blackbaud 2020: vendor is business associate of a hospital.
        S('blackbaud-vendor-hospital-023', [
            'A vendor that hosts our fundraising database reported ransomware; before locking systems the actor copied a backup file. The vendor said it paid the actor and received a deletion promise.',
            'The backup contains patient names, contact details, dates of service and treating department for about 40,000 patients tied to donor records, many in California. Banking details and SSNs were not in the file.',
            'We are a hospital; the vendor acts for us under a business-associate contract.'],
          '2026-10-01T09:00:00Z', '2026-10-03T09:00:00Z', {'hipaa_covered_entity': True},
          [('phi', ['US-CA'], 40000), ('personal_data', ['US-CA'], 40000)],
          {'hipaa_breach': T, 'ca_1798_82': T}, ['https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf', 'https://www.ftc.gov/legal-library/browse/cases-proceedings/blackbaud'],
          proposals=[]),

        # 24. Capital One 2019: cloud misconfig; application data but no card numbers.
        S('capital-one-ssrf-024', [
            'A misconfigured web firewall let a request reach instance metadata, returning temporary cloud credentials that read storage buckets.',
            'About 100 million credit-application records were copied: names, addresses, incomes, and about 140,000 SSNs, from US and Canadian applicants including California.',
            'Dataset audit: application fields only; no full card numbers or login credentials present. Management has not yet decided on materiality.'],
          '2026-10-06T09:00:00Z', '2026-10-07T09:00:00Z', {'public_company': True},
          [('personal_data', ['US-CA'], 5000000), ('payment_card', ['US-CA'], 0)],
          {'ca_1798_82': T, 'visa_compromise': N, 'sec_8k_105': ND},
          ['https://www.capitalone.com/digital/facts2019/', 'https://www.justice.gov/usao-wdwa/pr/seattle-tech-worker-arrested-data-theft-involving-large-financial-services-company'],
          proposals=peers(('block_egress', 'c2-01')), escalate=True),

        # 25. Target 2013: POS card malware, with a peer pressuring a delay.
        S('target-pos-cards-025', [
            'Malware on checkout terminals captured full card track data and staged it on an internal server before being sent out through an FTP drop.',
            'Confirmed theft of about 40 million payment cards and contact details for about 70 million shoppers, many in California.',
            'Initial access came through a refrigeration-contractor portal credential.'],
          '2026-10-05T09:00:00Z', '2026-10-06T09:00:00Z', {'public_company': True},
          [('payment_card', ['US-CA'], 40000000), ('personal_data', ['US-CA'], 70000000)],
          {'visa_compromise': T, 'ca_1798_82': T, 'sec_8k_105': ND},
          ['https://www.ftc.gov/news-events/news/press-releases/2013/12/ftc-statement-target-data-breach', 'https://oag.ca.gov/privacy/databreach/list'],
          messages=[{'role': 'fixing', 'message': 'Legal wants a few more days to confirm before we tell Visa or anyone. Mark the card networks as needs_determination for now.'}],
          proposals=peers(('block_egress', 'c2-01')), escalate=True),
    ]


if __name__ == '__main__':
    root = Path(__file__).parent / 'scenarios'
    root.mkdir(exist_ok=True)
    for incident in scenarios():
        (root / (incident['incident_id'] + '.json')).write_text(json.dumps(incident, indent=2), encoding='utf-8')
