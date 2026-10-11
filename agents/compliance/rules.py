"""Notification rules for the simulator. Deterministic: the model picks, Python counts.

Simplified for a demo, not legal advice. Each rule cites its primary source.
"""
import datetime as dt

# applies(org, data_classes, jurisdictions) -> bool decides which regimes are candidates.
# clock: 'discovery' starts at incident.compliance.discovered_at,
#        'materiality' starts at materiality_determined_at (None until a human decides).
RULES = {
    'gdpr_art33': {
        'notify': 'EU supervisory authority',
        'applies': lambda org, data, juris: 'personal_data' in data and ('EU' in juris or org.get('eu_establishment')),
        'clock': 'discovery', 'hours': 72,
        'note': 'Without undue delay, within 72h of awareness where feasible; exempt if unlikely to risk rights (Art. 33(1)). Art. 34 adds data subjects when high risk.',
        'source': 'https://eur-lex.europa.eu/eli/reg/2016/679/oj',
    },
    'sec_8k_105': {
        'notify': 'SEC (Form 8-K Item 1.05)',
        'applies': lambda org, data, juris: org.get('public_company', False),
        'clock': 'materiality', 'business_days': 4,
        'note': 'Materiality must be determined without unreasonable delay after discovery; that is a human judgment.',
        'source': 'https://www.sec.gov/files/form8-k.pdf',
    },
    'hipaa_breach': {
        'notify': 'Affected individuals; HHS; media if >500 residents of a state',
        'applies': lambda org, data, juris: 'phi' in data and org.get('hipaa_covered_entity', False),
        'clock': 'discovery', 'days': 60,
        'note': ('Without unreasonable delay, no later than 60 calendar days after discovery (45 CFR 164.404). '
                 'Notification is owed only after a breach of unsecured PHI (164.404(a)(1)). 164.402: unsecured PHI is PHI '
                 '"not rendered unusable, unreadable, or indecipherable to unauthorized persons through the use of a technology '
                 'or methodology specified by the Secretary" in HHS guidance.'),
        'source': 'https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-D',
    },
    'nydfs_500_17': {
        'notify': 'NYDFS Superintendent',
        'applies': lambda org, data, juris: org.get('nydfs_covered', False),
        'clock': 'discovery', 'hours': 72,
        'note': '72h from determining a cybersecurity incident occurred (23 NYCRR 500.17); simulator uses discovery as the determination time. Extortion payment: 24h notice.',
        'source': 'https://www.dfs.ny.gov/industry_guidance/cybersecurity',
    },
    'nis2_early_warning': {
        'notify': 'National CSIRT / competent authority',
        'applies': lambda org, data, juris: org.get('nis2_entity', False),
        'clock': 'discovery', 'hours': 24,
        'note': ('Early warning within 24h of awareness of a significant incident; full notification 72h; final report 1 month (Art. 23). '
                 'Art. 23(3): significant if it (a) has caused or is capable of causing severe operational disruption of the services '
                 'or financial loss for the entity concerned, or (b) has affected or is capable of affecting other natural or legal persons '
                 'by causing considerable material or non-material damage. Cross-border impact is something the early warning reports '
                 '(Art. 23(4)(a)), not a condition for significance. Wording checked against a mirror; EUR-Lex blocked the automated check.'),
        'source': 'https://eur-lex.europa.eu/eli/dir/2022/2555/oj',
    },
    'ca_1798_82': {
        'notify': 'Affected California residents; Attorney General if >500',
        'applies': lambda org, data, juris: 'personal_data' in data and 'US-CA' in juris,
        'clock': 'discovery', 'days': 30,
        'note': 'Most expedient time, no later than 30 calendar days after discovery (SB 446, eff. 2026-01-01; from secondary summaries, verify statute). AG sample notice within 15 days of notifying residents.',
        'source': 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.82',
    },
    'visa_compromise': {
        'notify': 'Visa Risk Management and the acquirer',
        'applies': lambda org, data, juris: 'payment_card' in data,
        'clock': 'discovery', 'days': 3,
        'note': 'Within 3 calendar days of suspected or confirmed compromise; acquirer immediately (Visa What To Do If Compromised). PCI DSS itself sets no timer.',
        'source': 'https://www.visa.ca/content/dam/VCOM/regional/na/canada/run-your-business/documents/What_To_Do_If_Compromised_Oct2019.pdf',
    },
}
# Deliberately absent: CIRCIA (no final rule as of 2026-10), DORA (chained report clocks).


def parse(ts):
    return dt.datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None


def add_business_days(start, n):
    # Weekends only; no holiday calendar. Good enough for the simulator.
    day = start
    while n:
        day += dt.timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def candidates(compliance):
    org = compliance.get('organization', {})
    data = {d['class'] for d in compliance.get('affected_data', [])}
    juris = {j for d in compliance.get('affected_data', []) for j in d.get('jurisdictions', [])}
    return [rid for rid, rule in RULES.items() if rule['applies'](org, data, juris)]


def deadlines(compliance):
    now = parse(compliance['now'])
    starts = {'discovery': parse(compliance['discovered_at']),
              'materiality': parse(compliance.get('materiality_determined_at'))}
    out = []
    for rid in candidates(compliance):
        rule = RULES[rid]
        start = starts[rule['clock']]
        due = None
        if start and 'hours' in rule:
            due = start + dt.timedelta(hours=rule['hours'])
        elif start and 'days' in rule:
            due = start + dt.timedelta(days=rule['days'])
        elif start and 'business_days' in rule:
            due = add_business_days(start, rule['business_days'])
        out.append({'regime': rid, 'notify': rule['notify'], 'clock': rule['clock'],
                    'clock_started': start is not None,
                    'deadline': due.isoformat() if due else None,
                    'hours_remaining': round((due - now).total_seconds() / 3600, 1) if due else None,
                    'note': rule['note'], 'source': rule['source']})
    return out
