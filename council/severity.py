"""Transparent, untuned demonstration score; hard stops cannot be voted away."""
import math

WEIGHTS = {'confirmed': 10, 'exfiltration': 15, 'sensitive_data': 10,
           'lateral_spread': 12, 'identity_compromise': 10, 'privileged_identity': 20,
           'ransomware': 25, 'critical_asset': 15}


def assess(impact, deadlines=(), reasons=(), threshold=75):
    if type(threshold) is not int or not 1 <= threshold <= 100:
        raise ValueError('Threshold must be an integer between 1 and 100')
    for key in WEIGHTS:
        if type(impact.get(key, False)) is not bool:
            raise ValueError('Severity flags must be trusted booleans')
    factors = {k: weight for k, weight in WEIGHTS.items() if impact.get(k, False)}
    for key in ('affected_hosts', 'data_records'):
        value = impact.get(key, 0)
        if type(value) is not int or value < 0 or not math.isfinite(value):
            raise ValueError('Invalid severity count: ' + key)
    if impact.get('confirmed'):
        factors['host_count'] = min(10, max(0, impact.get('affected_hosts', 0) - 1) * 2)
        factors['record_volume'] = min(10, impact.get('data_records', 0) // 10000 * 2)
    active = [d['hours_remaining'] for d in deadlines
              if d.get('status') != 'not_triggered' and d.get('hours_remaining') is not None]
    if active and min(active) < 24:
        factors['clock_pressure'] = 10
    score = min(100, sum(factors.values()))
    band = 'CRITICAL' if score >= 75 else 'HIGH' if score >= 50 else 'MEDIUM' if score >= 25 else 'LOW'
    stops = list(dict.fromkeys(reasons))
    if score >= threshold:
        reason = f'Severity {score} meets human threshold {threshold}'
        if reason not in stops:
            stops.append(reason)
    return {'score': score, 'band': band, 'threshold': threshold, 'factors': factors,
            'human_required': bool(stops), 'hard_stop_reasons': stops,
            'calibration': 'Synthetic demonstration weights, not a validated clinical/legal/security risk scale'}