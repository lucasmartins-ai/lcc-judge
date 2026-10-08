import hashlib
import json
import unittest

from research.multilingual_ranking_diagnostic import score_views, rank_pass


class MultilingualDiagnosticTests(unittest.TestCase):
    def examples(self):
        question, report = 'Quantos bytes?', 'File size: 7.'
        digest = hashlib.sha256(json.dumps([question, report], sort_keys=True).encode()).hexdigest()
        rows = [dict(id='a', content_hash='raw', projected_input_hash=digest),
                dict(id='b', content_hash='other', projected_input_hash=None)]
        views = [dict(id='a', view=dict(status='PROJECTED', objective=question, text=report)),
                 dict(id='b', view=dict(status='UNKNOWN', error='unsupported_record'))]
        return rows, views, digest

    def test_model_receives_only_declared_strings_and_unknown_bypasses(self):
        rows, views, digest = self.examples()
        class Scorer:
            def score(self, questions, reports):
                self.inputs = questions, reports
                return [dict(input_sha256=digest, score=1.0, status='SCORED', actual_tokens=8,
                             truncated=False, window_exceeded=False, submitted=True,
                             forward_completed=True, error=None)]
        scorer = Scorer()
        scores = score_views(rows, views, scorer)
        self.assertEqual(scorer.inputs, (['Quantos bytes?'], ['File size: 7.']))
        self.assertEqual(scores[1]['status'], 'UNKNOWN')
        self.assertFalse(scores[1]['submitted'])
        self.assertIsNone(scores[1]['score'])

    def test_changed_pair_identity_is_rejected_before_inference(self):
        rows, views, digest = self.examples()
        views[0]['view']['text'] = 'Changed report'
        class NoInference:
            def score(self, *args):
                self.fail('No changed input may reach the model')
        with self.assertRaises(ValueError):
            score_views(rows, views, NoInference())

    def test_aggregate_cannot_hide_portuguese_ordering_failure(self):
        good = dict(pooled_auc=.96, within_goal_auc=.92)
        self.assertTrue(rank_pass(good, dict(en=good, pt=good)))
        self.assertFalse(rank_pass(good, dict(en=good, pt=dict(pooled_auc=.89, within_goal_auc=.91))))
        self.assertFalse(rank_pass(good, dict(en=good, pt=dict(pooled_auc=.94, within_goal_auc=None))))


if __name__ == '__main__':
    unittest.main()
