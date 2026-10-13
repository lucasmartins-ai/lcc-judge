"""Specialist v3 on synthetic data only (no private files, no models on disk, no network)."""
import math
import unittest
from collections import Counter, defaultdict

import numpy as np

from research import specialist_v2 as s2
from research import specialist_v3 as s3
from tests.test_specialist_v2 import TEXTS

C = {f: j for j, f in enumerate(s2.FEATURES)}


def toy_models(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.random((n, len(s2.FEATURES))).astype(np.float32)
    y = (X[:, 0] > 0.6).astype(np.float32)
    w = np.ones(n)
    lr = dict(s2.fit_lr(X, y, w, iters=50), alpha=0.5)
    gb = dict(s2.fit_gbdt(X, y, w, n_trees=5, depth=2), alpha=0.5)
    return lr, gb


class Floor(unittest.TestCase):
    def X(self, bg, err):
        X = np.zeros((len(bg), len(s2.FEATURES)), np.float32)
        X[:, C['bm25_goal']] = bg
        X[:, C['is_error']] = err
        return X

    def test_top_goal_and_latest_errors(self):
        X = self.X([0.0, 2.0, 1.0, 2.0, 0.0, 0.5], [1, 0, 1, 0, 1, 0])
        m = s3.floor_mask(X, k_goal=1, k_err=2)
        # bm25 tie between 1 and 3 -> the later block; the two most recent error blocks are 2 and 4
        self.assertEqual(np.flatnonzero(m).tolist(), [2, 3, 4])

    def test_no_goal_match_no_floor(self):
        X = self.X([0, 0, 0], [0, 0, 0])
        self.assertFalse(s3.floor_mask(X, 3, 3).any())
        self.assertFalse(s3.floor_mask(X[:0], 2, 2).any())


class JudgeV3(unittest.TestCase):
    def test_ensemble_plus_floor_matches_reference(self):
        lr, gb = toy_models()
        model = dict(kind='v3', members=[lr, gb], alpha=0.5, k_goal=1, k_err=1, bonus=3.0)
        j = s3.Judge(model)
        goal = 'fix parse_config_value'
        sc = np.array(j.score(goal, TEXTS))
        X = s2.featurize(goal, TEXTS)
        ref = (s2.predict(lr, X) + s2.predict(gb, X)) / 2 - 0.5 * X[:, C['log_chars']]
        ref += 3.0 * s3.floor_mask(X, 1, 1)
        np.testing.assert_allclose(sc, ref, rtol=1e-6)
        self.assertEqual(j.score(goal, []), [])
        self.assertEqual(int(s3.floor_mask(X, 0, 1).sum()), 1)  # the Traceback block
        self.assertTrue(s3.floor_mask(X, 0, 1)[5])

    def test_floor_lifts_goal_block_above_unfloored(self):
        lr, _ = toy_models()
        lr = dict(lr, beta=[0.0] * len(lr['beta']))
        j = s3.Judge(dict(kind='v3', members=[lr], alpha=0.0, k_goal=1, k_err=0, bonus=3.0))
        sc = j.score('Traceback ValueError', TEXTS)
        self.assertEqual(int(np.argmax(sc)), 5)


class LeanBm25(unittest.TestCase):
    def test_query_only_postings_equal_full_index(self):
        goal = 'fix parse_config_value raw strip'
        X = s2.featurize(goal, TEXTS)
        bodies = [s2.HEADER_RE.sub('', t).strip() for t in TEXTS]
        postings, lens = defaultdict(list), []
        for i, b in enumerate(bodies):
            ts = s2.TOKEN_RE.findall(b.lower())
            lens.append(len(ts))
            for t, f in Counter(ts).items():
                postings[t].append((i, f))
        full = s2.bm25(s2.TOKEN_RE.findall(goal.lower()), postings, lens, sum(lens) / len(lens))
        np.testing.assert_allclose(X[:, C['bm25_goal']], np.log1p(full).astype(np.float32), rtol=1e-6)
        self.assertTrue(math.isfinite(float(X.sum())))


class Bootstrap(unittest.TestCase):
    def test_group_bootstrap_ci_brackets_mean(self):
        items = [dict(item_id=str(i), group=f'g{i % 5}') for i in range(40)]
        a = {str(i): 0.8 + 0.01 * (i % 3) for i in range(40)}
        b = {str(i): 0.7 for i in range(40)}
        r = s3.group_bootstrap(items, a, b, n=200)
        self.assertEqual(r['groups'], 5)
        self.assertLessEqual(r['ci95'][0], r['mean'])
        self.assertGreaterEqual(r['ci95'][1], r['mean'])
        self.assertGreater(r['ci95'][0], 0)


if __name__ == '__main__':
    unittest.main()
