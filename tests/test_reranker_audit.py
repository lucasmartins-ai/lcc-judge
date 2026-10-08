import unittest

from research.audit_reranker_diagnostic import reduce


class RerankerAuditTests(unittest.TestCase):
    def test_goal_sensitivity_and_candidate_order_are_different_axes(self):
        rows = [dict(id='a1', report_id='a', label=1, score=4.),
                dict(id='a2', report_id='a', label=0, score=3.),
                dict(id='b1', report_id='b', label=0, score=5.),
                dict(id='b2', report_id='b', label=1, score=6.)]
        source = {key: {'objective': goal} for key, goal in [('a1','q1'),('b1','q1'),('a2','q2'),('b2','q2')]}
        result = reduce(rows, source=source)
        self.assertEqual(result['auc'], .75)
        self.assertEqual(result['paired_auc'], 1.)
        self.assertEqual(result['within_objective']['auc'], .5)

    def test_ties_are_not_half_credit_and_errors_are_not_scored(self):
        rows = [dict(id='p', report_id='r', label=1, score=3.),
                dict(id='n', report_id='r', label=0, score=3.),
                dict(id='bad', report_id='x', label=1, score=100., error='invalid')]
        result = reduce(rows, threshold=3.)
        self.assertEqual(result['eligible'], 2)
        self.assertEqual(result['auc'], 0.)
        self.assertEqual(result['paired_auc'], 0.)
        self.assertEqual(result['negative_rejection'], 0.)


if __name__ == '__main__':
    unittest.main()
