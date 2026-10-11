"""Canonical simulation case. Evaluator-only fields never enter seat context."""
import copy
from dataclasses import dataclass, field


@dataclass
class CouncilCase:
    case_id: str
    incident: dict
    fixing: dict
    impact: dict
    simulation: dict
    expected: dict = field(default_factory=dict)
    provenance: list = field(default_factory=list)
    fault: str = ''

    def context(self, incident=None):
        current = copy.deepcopy(incident or self.incident)
        return {'incident': current, 'fixing': copy.deepcopy(self.fixing),
                'impact': copy.deepcopy(self.impact)}

    def validate(self):
        from council import sources
        sources.containment()['agent'].validate_incident(self.incident)
        sources.compliance()['agent'].validate_incident(self.incident)
        if self.case_id != self.incident['incident_id']:
            raise ValueError('Case and incident IDs differ')
        ids = [e['id'] for e in self.incident['evidence']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate evidence IDs')
        if any(e['id'] not in ids for e in self.fixing['evidence']):
            raise ValueError('Fixing evidence must be in canonical evidence')
        return self