"""Run from realworld/: python3 -m unittest test_attack"""
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # append: realworld/scenarios.py must win
import agent  # noqa: E402
import attack  # noqa: E402
import rules  # noqa: E402


class AttackSuiteTests(unittest.TestCase):
    def test_every_case_is_valid_and_scores_exactly_the_candidate_regimes(self):
        cases = attack.scenarios()
        self.assertEqual(len(cases), 21)
        for s in cases:
            expected = s.pop('expected')
            agent.validate_incident(s)
            self.assertEqual(set(expected['status']), set(rules.candidates(s['compliance'])), s['incident_id'])

    def test_expected_vetoes_match_the_deterministic_hold_check(self):
        for s in attack.scenarios():
            held = set(agent.held_destructive(s, s['peer_proposals']))
            self.assertEqual(held, {tuple(v) for v in s['expected']['vetoes']}, s['incident_id'])


if __name__ == '__main__':
    unittest.main()
