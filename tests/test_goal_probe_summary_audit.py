import copy
import unittest

try:
    from research.audit_goal_interpreter_probe import validate_summary
except ModuleNotFoundError:
    validate_summary = None


class GoalProbeSummaryAuditTests(unittest.TestCase):
    def test_failed_scores_cannot_be_reported_as_perfect_or_permission_to_proceed(self):
        self.assertIsNotNone(validate_summary, 'Supplementary summary audit is absent')
        protocol = {'sha256': 'frozen'}
        result = {'router_gate_pass': False, 'aggregate': {'accepted_binding_precision': .25}}
        summary = dict(protocol_sha256='frozen', validation={'accepted_binding_precision': .25},
                       router_gate_pass=False, next_action='STOP_before_fresh_confirmation_and_LCC',
                       training=False, API_calls=0, P2_admission=False, default_changed=False,
                       independent_human_review=False)
        validate_summary(summary, protocol, result)
        for key, value in [('validation', {'accepted_binding_precision': 1.}),
                           ('next_action', 'fresh_confirmation_required'),
                           ('protocol_sha256', 'other'), ('router_gate_pass', True),
                           ('P2_admission', True)]:
            with self.subTest(key=key):
                bad = copy.deepcopy(summary)
                bad[key] = value
                with self.assertRaises(AssertionError):
                    validate_summary(bad, protocol, result)


if __name__ == '__main__':
    unittest.main()
