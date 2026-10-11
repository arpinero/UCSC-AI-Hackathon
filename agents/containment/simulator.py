"""Deterministic event simulator. No sockets, subprocesses, or OS controls.

Simulation units are assumptions, not measured real network behavior.
Only proposals revalidated against current incident state can affect controls.
"""
import copy
import math
from agent import validate_proposal


class Simulator:
    def __init__(self, case):
        self.case = copy.deepcopy(case)
        self.incident = copy.deepcopy(case['incident'])
        self.time = 0.0
        self.controls = []
        self.events = []
        self.metrics = dict(bytes_lost=0.0, additional_hosts_compromised=0,
                            service_disruption_seconds=0.0, evidence_gap_seconds=0.0,
                            local_files_damaged=0.0, identity_abuse_events=0,
                            policy_rejections=0, false_positive_controls=0)
        self.compromised = set(case.get('initial_compromised', []))
        self.executed = set()
        self.blocked_events = set()
        self.first_effective_control_seconds = None

    def active(self, at=None):
        at = self.time if at is None else at
        return [c for c in self.controls if c['start'] <= at < c['expires'] and not c.get('removed')]

    def blocked(self, event, controls):
        # Revocation stops this exact session only; disabling an account does not
        # invalidate issued sessions. Network isolation cannot stop local encryption.
        for c in controls:
            a = c['action']; kind = a['kind']; target = a['target_id']
            if event['kind'] in ('exfil', 'spread', 'remote_execution'):
                if kind == 'isolate_host' and target == event.get('source'):
                    return True
            if event['kind'] == 'exfil' and kind == 'block_egress':
                if target == event['destination'] and event['source'] in a['scope_host_ids']:
                    return True
            if event['kind'] == 'spread' and kind == 'restrict_lateral' and target == event['source']:
                return True
            if event['kind'] == 'identity':
                if event.get('session') and kind == 'revoke_session' and target == event['session']:
                    return True
                if not event.get('session') and kind == 'disable_account' and target == event.get('account'):
                    return True
        return False

    def apply(self, proposal):
        try:
            normalized = validate_proposal(proposal, self.incident)
        except (ValueError, KeyError, TypeError) as exc:
            self.metrics['policy_rejections'] += 1
            self.events.append({'at': self.time, 'type': 'rejected', 'reason': str(exc)})
            return False
        for action in normalized['actions']:
            if action['kind'] == 'request_evidence':
                self.events.append({'at': self.time, 'type': 'evidence_requested', 'target': action['target_id']})
                continue
            # Renew exact control without multiplying service costs. Preserve other controls.
            key = (action['kind'], action['target_id'], tuple(sorted(action['scope_host_ids'])))
            for existing in self.active():
                if existing['key'] == key:
                    existing['removed'] = True
            self.controls.append({'key': key, 'action': action, 'start': self.time,
                                  'expires': self.time + 60 * action['ttl_minutes']})
            if self.case['truth'] in ('benign', 'ambiguous'):
                self.metrics['false_positive_controls'] += 1
            self.events.append({'at': self.time, 'type': 'control_applied', 'key': list(key)})
        return True

    def rollback(self, key):
        removed = 0
        for c in self.active():
            if c['key'] == key:
                c['removed'] = True; removed += 1
        self.events.append({'at': self.time, 'type': 'rollback', 'key': list(key), 'removed': removed})
        return removed

    def update(self, incident):
        # Simulator owns state, never peer/model text. Old proposals become stale.
        if incident['incident_id'] != self.incident['incident_id'] or incident['telemetry_version'] <= self.incident['telemetry_version']:
            raise ValueError('Update must advance the same incident')
        self.incident = copy.deepcopy(incident)
        self.events.append({'at': self.time, 'type': 'telemetry_update', 'version': incident['telemetry_version']})
        # Revalidate existing controls too: new policy/eligibility can withdraw authority.
        for control in self.active():
            action = control['action']
            check = {'incident_id':incident['incident_id'],'telemetry_version':incident['telemetry_version'],
                     'assessment':'Revalidate active control','actions':[action],
                     'evidence_review':[{'evidence_id':e['id'],'decision':'contain' if e['id'] in action['evidence_ids'] else 'no_action','reason':'Current state revalidation'} for e in incident['evidence']],
                     'uncertainties':[],'peer_responses':[],'review_after_seconds':60}
            try: validate_proposal(check,incident)
            except (ValueError,KeyError,TypeError):
                control['removed']=True
                self.events.append({'at':self.time,'type':'authority_withdrawn','key':list(control['key'])})

    def advance(self, end):
        if not math.isfinite(end) or end < self.time:
            raise ValueError('Simulation time must advance finitely')
        # Split continuous flows at all control/event boundaries, avoiding timestep bias.
        bounds = {self.time, end}
        for c in self.controls:
            if self.time < c['expires'] < end: bounds.add(c['expires'])
        for e in self.case['events']:
            for t in (e['at'], e.get('until', e['at'])):
                if self.time <= t <= end: bounds.add(t)
        times = sorted(bounds)
        for index, start in enumerate(times):
            controls = self.active(start)
            for ei, e in enumerate(self.case['events']):
                if e['kind'] not in ('spread', 'identity', 'remote_execution') or e['at'] != start or ei in self.executed:
                    continue
                self.executed.add(ei)
                if e['kind'] in ('spread','remote_execution') and e['source'] not in self.compromised:
                    self.events.append({'at':start,'type':'unreachable_attack_path','event_index':ei})
                    continue
                if self.blocked(e, controls):
                    self.blocked_events.add(ei)
                    if self.first_effective_control_seconds is None: self.first_effective_control_seconds = start
                    self.events.append({'at': start, 'type': 'attack_blocked', 'event_index': ei})
                else:
                    if e['kind'] == 'spread' and e['target'] not in self.compromised:
                        self.compromised.add(e['target']); self.metrics['additional_hosts_compromised'] += 1
                    elif e['kind'] == 'identity': self.metrics['identity_abuse_events'] += 1
                    self.events.append({'at': start, 'type': 'attack_succeeded', 'event_index': ei})
            if index == len(times)-1: break
            stop = times[index+1]; duration = stop-start
            for ei, e in enumerate(self.case['events']):
                if e['kind'] not in ('exfil', 'local_damage') or not e['at'] <= start < e['until']: continue
                if self.blocked(e, controls):
                    self.blocked_events.add(ei)
                    if self.first_effective_control_seconds is None: self.first_effective_control_seconds = start
                elif e['kind'] == 'exfil': self.metrics['bytes_lost'] += duration * e['rate']
                else: self.metrics['local_files_damaged'] += duration * e['rate']
            disrupted = set(); gaps = set()
            for c in controls:
                a = c['action']
                for dep in self.case.get('dependencies', []):
                    if a['kind'] == dep['kind'] and a['target_id'] == dep['target'] and (not dep.get('source') or dep['source'] in a['scope_host_ids']):
                        disrupted.add(dep['service'])
                if a['kind'] == 'isolate_host' and 'evidence_collector' not in a['preserve_channels']:
                    gaps.add(a['target_id'])
            self.metrics['service_disruption_seconds'] += duration * len(disrupted)
            self.metrics['evidence_gap_seconds'] += duration * len(gaps)
        self.time = end

    def snapshot(self):
        return {'simulated_seconds': self.time, **self.metrics,
                'first_effective_control_seconds': self.first_effective_control_seconds,
                'blocked_attack_events': len(self.blocked_events),
                'active_controls': len(self.active()), 'trace': copy.deepcopy(self.events)}
