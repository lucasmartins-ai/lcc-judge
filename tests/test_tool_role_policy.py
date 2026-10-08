import unittest

from research.tool_role_policy import calibrate, decision, metrics, passes


def examples():
    rows, scores = [], []
    for language in ['en', 'pt']:
        for label, value, truth in [(1, 3.0, True), (1, 2.0, False), (0, -2.0, True), (0, -3.0, False)]:
            identity = f'{language}-{len(rows)}'
            rows.append(dict(id=identity, label=label, goal_language=language, fact_truth=truth,
                             objective=language, report_id=identity, unknown_kind=None))
            scores.append(dict(id=identity, score=value, support_score=-5.0, status='SCORED'))
        identity = f'{language}-unknown'
        rows.append(dict(id=identity, label=None, goal_language=language, fact_truth=True,
                         objective='unsupported', report_id=identity, unknown_kind='unsupported_goal'))
        scores.append(dict(id=identity, score=-100.0, support_score=2.0, status='SCORED'))
    return rows, scores


class ToolRolePolicyTests(unittest.TestCase):
    def test_semantic_unknown_is_retained_even_with_low_relevance(self):
        rows, scores = examples()
        thresholds = calibrate(rows, scores)
        self.assertEqual(thresholds['support'], 2.0)
        self.assertEqual(decision(scores[-1], thresholds), 'UNKNOWN')
        self.assertEqual(decision(scores[1], thresholds), 'KEEP')
        self.assertEqual(decision(scores[2], thresholds), 'DROP')
        self.assertEqual(decision(dict(status='UNKNOWN', score=None), thresholds), 'UNKNOWN')

    def test_threshold_cannot_sacrifice_portuguese_positives(self):
        rows, scores = examples()
        scores[5]['score'] = -10.0
        thresholds = calibrate(rows, scores)
        self.assertLessEqual(thresholds['relevance'], -10.0)
        scores[-1]['support_score'] = float('nan')
        with self.assertRaises(ValueError):
            calibrate(rows, scores)

    def test_strict_ties_and_missing_unknown_are_not_a_pass(self):
        rows, scores = examples()
        scores[0]['score'] = scores[2]['score']
        result = metrics(rows, scores, calibrate(rows, scores))
        self.assertLess(result['pooled_auc'], 1.0)
        self.assertFalse(passes(result))
        scores = [s for r, s in zip(rows, scores) if r['label'] is not None]
        rows = [r for r in rows if r['label'] is not None]
        with self.assertRaises(ValueError):
            calibrate(rows, scores)

    def test_all_semantic_unknown_kinds_participate_in_calibration_and_metrics(self):
        for kind in ['derived_or_multifield_goal', 'diagnosis_goal', 'broader_usefulness_goal']:
            rows,scores=examples()
            for row in rows:
                if row['label'] is None:row['unknown_kind']=kind
            thresholds=calibrate(rows,scores)
            result=metrics(rows,scores,thresholds)
            self.assertEqual(result['semantic_unknown'],2)
            self.assertEqual(result['semantic_unknown_recognition'],1.0)
            self.assertEqual(result['unknown_drops'],0)
            scores[-1]['support_score']=-10.0
            changed=metrics(rows,scores,thresholds)
            self.assertEqual(changed['unknown_drops'],1)
            self.assertEqual(changed['semantic_unknown_recognition'],.5)



if __name__ == '__main__':
    unittest.main()
