import unittest

from research.diagnose_varied_relation_confirmation import retention_cutoff, strict_auc


class FailureDiagnosisTests(unittest.TestCase):
    def test_strict_ties_and_all_cohort_language_retention_constraints(self):
        self.assertEqual(strict_auc([1.,2.],[1.,2.]), .25)
        rows, scores = [], []
        for family in ('primary:a:b','seen_control:a:c'):
            for goal in ('en','pt'):
                for report in ('en','pt'):
                    for i in range(40):
                        row = dict(id=str(len(rows)),family=family,goal_language=goal,
                                   report_language=report,label=1,fact_truth=i % 2 == 0)
                        rows.append(row)
                        scores.append(dict(id=row['id'],score=float(i//2),support_score=-1.))
        cutoff = retention_cutoff(rows,scores,0.)
        self.assertEqual(cutoff, 1.)
        for family in ('primary:a:b','seen_control:a:c'):
            group = [s for r,s in zip(rows,scores) if r['family'] == family]
            self.assertGreaterEqual(sum(s['score'] >= cutoff for s in group)/len(group), .95)
        # Two low-ranked relevant rows abstain rather than DROP: ties remain KEEP.
        for row,score in zip(rows,scores):
            if score['score'] == 0.:
                score['support_score'] = 1.
        self.assertEqual(retention_cutoff(rows,scores,0.), 2.)
        with self.assertRaises(ValueError):
            retention_cutoff(rows,scores[:-1],0.)


if __name__ == '__main__':
    unittest.main()
