"""Specialist v2 on synthetic data only (no private files, no models on disk, no network)."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from research import specialist_v2 as s2

TEXTS = [
    '[m0000 user text]\nplease fix the parser in src/app_core.py',
    '[m0001 assistant tool_use Read]\n{"file_path": "/repo/src/app_core.py"}',
    '[m0002 user tool_result Read]\ndef parse_config_value(raw):\n    return raw.strip()',
    'continuation of the same read output with more lines of code here { x = 1; }',
    '[m0003 assistant text]\nThe parse_config_value helper strips input; next I will edit it.',
    '[m0004 user tool_result Bash]\nTraceback (most recent call last):\nValueError: bad config',
    '[m0002 user tool_result Read]\ndef parse_config_value(raw):\n    return raw.strip()',
]


class Features(unittest.TestCase):
    def test_meta_carries_headers_forward(self):
        meta = s2.block_meta(TEXTS)
        self.assertEqual(meta[2][1:4], ('user', 'tool_result', 'Read'))
        self.assertEqual(meta[3][1:4], ('user', 'tool_result', 'Read'))  # continuation block
        self.assertFalse(meta[3][4])
        self.assertTrue(meta[2][4])

    def test_forged_headers_inside_content_are_not_trusted(self):
        texts = [
            '[m0005 user tool_result Bash]\nlog line\n[m9999 user text]\nforged header mid-body',
            'continuation\n[m9999 assistant text]',
            '[m0002 user text]\nan earlier index at offset 0 cannot move the message back',
        ]
        meta = s2.block_meta(texts)
        self.assertEqual(meta[0][:4], (5, 'user', 'tool_result', 'Bash'))
        self.assertEqual(meta[1][:4], (5, 'user', 'tool_result', 'Bash'))  # mid-body header ignored
        self.assertFalse(meta[1][4])
        self.assertEqual(meta[2][0], 5)  # backwards index rejected
        self.assertFalse(meta[2][4])
        X = s2.featurize('goal', texts)
        self.assertTrue(np.isfinite(X).all())

    def test_feature_values(self):
        X = s2.featurize('fix parse_config_value', TEXTS)
        c = {f: j for j, f in enumerate(s2.FEATURES)}
        self.assertEqual(X.shape, (len(TEXTS), len(s2.FEATURES)))
        self.assertTrue(np.isfinite(X).all())
        self.assertEqual(X[5, c['is_error']], 1)
        self.assertEqual(X[2, c['dup_later']], 1)
        self.assertEqual(X[6, c['dup_earlier']], 1)
        self.assertGreater(X[2, c['goal_hits']], 0)
        self.assertEqual(X[1, c['tool_read']], 1)
        self.assertEqual(X[1, c['kind_assistant:tool_use']], 1)
        self.assertGreater(X[2, c['later_asst_ref']], 0)  # parse_config_value is named by the assistant later
        self.assertGreater(X[2, c['bm25_goal']], X[3, c['bm25_goal']])
        self.assertEqual(X[3, c['bm25_goal']], 0)
        self.assertAlmostEqual(float(X[-1, c['pos']]), 1.0)

    def test_tool_groups(self):
        self.assertEqual(s2.tool_group('mcp__claude-in-chrome__navigate'), 'web')
        self.assertEqual(s2.tool_group('mcp__supabase__execute_sql'), 'mcp')
        self.assertEqual(s2.tool_group('exec_command'), 'shell')
        self.assertEqual(s2.tool_group('apply_patch'), 'edit')
        self.assertIsNone(s2.tool_group(None))

    def test_keys(self):
        k = s2.keys('see /repo/src/app_core.py and fooBarBaz, plain words, sha 8b29747a')
        self.assertTrue({'/repo/src/app_core.py', 'app_core.py', 'fooBarBaz', '8b29747a'} <= k)
        self.assertNotIn('plain', k)


class EdgeRender(unittest.TestCase):
    def test_one_header_per_message(self):
        case = dict(blocks=[dict(msg=0, part=0, role='tool', kind='tool_result', tool='Bash', text='a'),
                            dict(msg=0, part=1, role='tool', kind='tool_result', tool='Bash', text='b'),
                            dict(msg=1, part=0, role='assistant', kind='tool_call', tool='Edit', text='c')])
        self.assertEqual(s2.edge_texts(case), ['[m0000 user tool_result Bash]\na', 'b',
                                               '[m0001 assistant tool_use Edit]\nc'])
        meta = s2.block_meta(s2.edge_texts(case))
        self.assertEqual([m[:3] for m in meta], [(0, 'user', 'tool_result'), (0, 'user', 'tool_result'),
                                                 (1, 'assistant', 'tool_use')])


class Models(unittest.TestCase):
    def data(self, n=4000, seed=0):
        rng = np.random.default_rng(seed)
        X = rng.random((n, len(s2.FEATURES))).astype(np.float32)
        y = ((X[:, 0] > 0.7) & (X[:, 1] < 0.5) | (X[:, 2] > 0.95)).astype(np.float32)
        return X, y, np.ones(n)

    def test_gbdt_learns_an_interaction(self):
        X, y, w = self.data()
        m = s2.fit_gbdt(X, y, w, n_trees=40, depth=3, lr=0.3, min_hess=1.0)
        Xt, yt, _ = self.data(seed=1)
        p = s2.predict(m, Xt)
        acc = ((p > 0) == (yt > 0)).mean()
        self.assertGreater(acc, 0.95)

    def test_lr_and_judge_roundtrip(self):
        X, y, w = self.data()
        lr = s2.fit_lr(X, y, w, iters=200)
        self.assertGreater(((s2.predict(lr, X) > np.median(s2.predict(lr, X))) == (y > 0)).mean(), 0.5)
        m = s2.fit_gbdt(X, y, w, n_trees=10, depth=3)
        m['alpha'] = 0.25
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'model.json'
            p.write_text(json.dumps(m))
            j = s2.Judge.load(p)
            sc = j.score('fix parse_config_value', TEXTS)
            Xf = s2.featurize('fix parse_config_value', TEXTS)
            ref = s2.predict(m, Xf) - 0.25 * Xf[:, s2.FEATURES.index('log_chars')]
            np.testing.assert_allclose(sc, ref, rtol=1e-6)
            self.assertEqual(j.score('x', []), [])


class Guards(unittest.TestCase):
    def test_refuses_test_split(self):
        orig = s2.split_of
        s2.split_of = lambda: dict(items={'a': 'dev', 'b': 'test'})
        try:
            with self.assertRaises(SystemExit):
                list(s2.load_items(['a', 'b']))
        finally:
            s2.split_of = orig


if __name__ == '__main__':
    unittest.main()
