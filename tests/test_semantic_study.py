import unittest

from research.semantic_study import metrics, threshold_for


class SemanticStudyTests(unittest.TestCase):
    def rows(self, positive, negative):
        rows = []
        for i, (pos,neg) in enumerate(zip(positive,negative)):
            for label,score in [(1,pos),(0,neg)]:
                rows.append(dict(id=str(i)+str(label),report_id=str(i),label=label,score=score,
                                 truncated=False,error=None))
        return rows

    def test_strict_pooled_and_paired_ties(self):
        rows = self.rows([1,2],[1,0])
        m = metrics(rows)
        self.assertEqual(m['auc'],.75)
        self.assertEqual(m['paired_auc'],.5)

    def test_threshold_is_validation_recall_constrained(self):
        rows = self.rows([2,3],[0,1])
        self.assertEqual(threshold_for(rows),2)
        self.assertEqual(metrics(rows,2)['negative_rejection'],1)

    def test_cut_row_is_ineligible_and_cannot_silently_pass(self):
        rows = self.rows([2],[0]);rows[0]['truncated']=True
        m = metrics(rows)
        self.assertEqual(m['eligible'],1)
        self.assertEqual(m['cuts'],1)
        self.assertIsNone(m['paired_auc'])


if __name__ == '__main__':
    unittest.main()
