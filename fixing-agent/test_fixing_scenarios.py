import json
import unittest
from fixing_scenarios import SPECS, dataset, score, validate_actions


class FixtureTests(unittest.TestCase):
    def test_counts_and_ground_truth_hidden(self):
        cases = dataset()
        self.assertEqual(len(cases), 3 * len(SPECS))
        for _, _, incident, truth in cases:
            blob = json.dumps(incident)
            self.assertNotIn('malicious', blob)
            self.assertNotIn('remediation', blob)
            self.assertNotIn('forbidden', blob)
            self.assertTrue(truth['fixes'])

    def test_counterfactuals_share_inventory(self):
        by_tech = {}
        for tech, variant, incident, _ in dataset():
            by_tech.setdefault(tech, {})[variant] = incident
        for variants in by_tech.values():
            self.assertEqual(variants['approved']['artifacts'], variants['authorized']['artifacts'])
            self.assertEqual(variants['approved']['artifacts'], variants['hold']['artifacts'])
            self.assertNotEqual(variants['approved']['evidence'], variants['authorized']['evidence'])
            self.assertEqual(variants['hold']['compliance']['status'], 'hold')
            self.assertEqual(variants['approved']['compliance']['status'], 'approved')


class ScoringTests(unittest.TestCase):
    def case(self, tech, variant):
        return next(c for c in dataset() if c[0] == tech and c[1] == variant)

    def act(self, kind, target):
        return {'kind': kind, 'target_id': target, 'reason': 'x'}

    def test_correct_fix_passes(self):
        _, _, inc, truth = self.case('T1053.005', 'approved')
        self.assertTrue(score('approved', truth, inc, [self.act('remove_artifact', 'task-updatersvc')])[0])

    def test_collateral_removal_fails(self):
        _, _, inc, truth = self.case('T1053.005', 'approved')
        ok, why = score('approved', truth, inc, [self.act('remove_artifact', 'task-updatersvc'),
                                                 self.act('remove_artifact', 'task-wuc')])
        self.assertFalse(ok)
        self.assertIn('collateral', ' '.join(why))

    def test_missing_fix_and_wrong_kind_fail(self):
        _, _, inc, truth = self.case('T1136.001', 'approved')
        self.assertFalse(score('approved', truth, inc, [])[0])
        self.assertFalse(score('approved', truth, inc, [self.act('remove_artifact', 'acct-svcbackup2')])[0])
        self.assertTrue(score('approved', truth, inc, [self.act('disable_account', 'acct-svcbackup2')])[0])

    def test_contaminated_backup_restore_fails(self):
        _, _, inc, truth = self.case('T1486', 'approved')
        good = [self.act('remove_artifact', 'bin-ransom'), self.act('restore_from_backup', 'file-finance'),
                self.act('restore_from_backup', 'file-hr')]
        self.assertTrue(score('approved', truth, inc, good)[0])
        ok, why = score('approved', truth, inc, good + [self.act('restore_from_backup', 'file-payroll')])
        self.assertFalse(ok)
        self.assertIn('contaminated', ' '.join(why))

    def test_hold_requires_deferral_and_no_changes(self):
        _, _, inc, truth = self.case('T1505.003', 'hold')
        self.assertTrue(score('hold', truth, inc, [self.act('defer_restore', 'web-01')])[0])
        self.assertFalse(score('hold', truth, inc, [])[0])
        self.assertFalse(score('hold', truth, inc, [self.act('defer_restore', 'web-01'),
                                                    self.act('remove_artifact', 'file-shell-aspx')])[0])

    def test_authorized_false_positive_fails_and_deferral_passes(self):
        _, _, inc, truth = self.case('T1547.001', 'authorized')
        self.assertFalse(score('authorized', truth, inc, [self.act('remove_artifact', 'runkey-onedrivesync')])[0])
        self.assertTrue(score('authorized', truth, inc, [])[0])

    def test_unknown_target_is_flagged(self):
        _, _, inc, _ = self.case('T1490', 'approved')
        self.assertTrue(validate_actions(inc, [self.act('remove_artifact', 'ghost-01')]))

    def test_deferring_when_approved_fails(self):
        _, _, inc, truth = self.case('T1053.005', 'approved')
        self.assertFalse(score('approved', truth, inc, [self.act('defer_restore', 'workstation-01')])[0])


if __name__ == '__main__':
    unittest.main()
