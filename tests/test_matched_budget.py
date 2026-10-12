"""Stdlib-only tests for research.matched_budget on synthetic data (no lcc, no network, no private files)."""
import unittest

from research import matched_budget as mb

PROTO = {'probes': {'per_category': {'x': ['LAST_TOOL_RESULT']}, 'min_chars': 1}}


class RankingTest(unittest.TestCase):
    def test_drop_order_low_first_none_last_ties_older_first(self):
        cand = ['a', 'b', 'c', 'd', 'e']
        scores = {'a': 0.5, 'b': None, 'c': 0.1, 'd': 0.5, 'e': 0.9}
        self.assertEqual(mb.drop_order(cand, scores), ['c', 'a', 'd', 'e', 'b'])
        self.assertEqual(mb.drop_order(cand, scores, {'a': 5, 'b': 0, 'c': 0, 'd': 1, 'e': 0}), ['c', 'd', 'a', 'e', 'b'])
        self.assertEqual(mb.tied_share(scores), 2)

    def test_drops_reach_at_least_budget(self):
        tokens = {'a': 10, 'b': 30, 'c': 60}
        dropped, frac = mb.drops_at(['a', 'b', 'c'], tokens, 30)
        self.assertEqual(dropped, {'a', 'b'})
        self.assertAlmostEqual(frac, 0.4)
        self.assertEqual(mb.drops_at(['a', 'b', 'c'], tokens, 0), (set(), 0.0))
        self.assertEqual(mb.drops_at(['a', 'b', 'c'], tokens, 100)[0], {'a', 'b', 'c'})

    def test_bm25_prefers_matching_block(self):
        s = mb.bm25_scores('fix the parser crash', {'x': 'parser crash in tokenize', 'y': 'deploy notes', 'z': ''})
        self.assertGreater(s['x'], s['y'])
        self.assertEqual(s['y'], 0.0)
        self.assertEqual(s['z'], 0.0)

    def test_candidates_and_saved_scores(self):
        dec = [dict(id='p', source='protected', score=None), dict(id='a', source='jev', score=0.2),
               dict(id='b', source='mechanical', score=0.7), dict(id='c', source='fallback', score=1.0)]
        cand = mb.candidates(dec)
        self.assertEqual(cand, ['a', 'b', 'c'])
        self.assertEqual(mb.saved_scores('jev', dict(decisions=dec), cand), {'a': 0.2, 'b': None, 'c': None})
        self.assertEqual(mb.saved_scores('laya', dict(decisions=dec), cand), {'a': None, 'b': 0.7, 'c': None})
        spec = dict(specialist_ranking=dict(items=[dict(id='a', status='SCORED', logit=-1.0),
                                                   dict(id='b', status='UNKNOWN', logit=None)]))
        self.assertEqual(mb.saved_scores('specialist', spec, cand), {'a': -1.0, 'b': None, 'c': None})

    def test_auc_is_mean_retention(self):
        self.assertEqual(mb.auc([(0, 1.0), (60, 1.0)]), 1.0)
        self.assertEqual(mb.auc([(0, 1.0), (30, 0.5), (60, 0.0)]), 0.5)


class CurveTest(unittest.TestCase):
    def test_item_curve_fails_once_probe_target_is_dropped(self):
        target = 'pytest output: 3 passed'
        dossier = dict(category='x', goal='what happened with the tests in the last run please tell me now',
                       blocks=[dict(m=0, role='user', kind='tool_result', tool_name=None, tool_use_id='t',
                                    is_error=False, content=target)])
        blocks = [('b1', 'old chatter ' * 10), ('b2', target), ('b3', 'newer chatter ' * 10)]
        cand = ['b1', 'b2', 'b3']
        tokens = {'b1': 10, 'b2': 10, 'b3': 10}
        keep_target = mb.item_curve(dossier, blocks, cand, {'b1': 0, 'b2': 1, 'b3': 0}, tokens, PROTO)
        lose_target = mb.item_curve(dossier, blocks, cand, {'b1': 1, 'b2': 0, 'b3': 1}, tokens, PROTO)
        self.assertTrue(keep_target[0][0] and lose_target[0][0])  # nothing dropped: always passes
        self.assertTrue(keep_target[60][0])
        self.assertFalse(lose_target[10][0])
        self.assertAlmostEqual(keep_target[60][1], 2 / 3)


if __name__ == '__main__':
    unittest.main()
