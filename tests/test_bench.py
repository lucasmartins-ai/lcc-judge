"""research.bench pure parts on synthetic data (no private files, no model, no CLI)."""
import tempfile
import unittest
from pathlib import Path

from research import bench as b


class Guards(unittest.TestCase):
    def test_spent_split_ids_refused(self):
        split = {'a': 'train', 'b': 'dev', 'c': 'test'}
        self.assertEqual(b.guard_ids(['a', 'b'], split), ['a', 'b'])
        with self.assertRaises(b.SpentSplit):
            b.guard_ids(['a', 'c'], split)
        with self.assertRaises(b.SpentSplit):
            b.guard_ids(['unknown'], split)

    def test_guarded_loader_checks_before_loading(self):
        seen = []
        load = b.guarded_loader(lambda i: seen.append(i) or i, {'a': 'dev', 'c': 'test'})
        self.assertEqual(load('a'), 'a')
        with self.assertRaises(b.SpentSplit):
            load('c')
        self.assertEqual(seen, ['a'])

    def test_spent_dir_refused(self):
        with tempfile.TemporaryDirectory() as d:
            spent = (Path(d) / 'spent',)
            b.guard_path(Path(d) / 'other' / 'x.json', spent)
            for p in (Path(d) / 'spent', Path(d) / 'spent' / 'items' / 'x.json'):
                with self.assertRaises(b.SpentSplit):
                    b.guard_path(p, spent)


class Pure(unittest.TestCase):
    def test_diff(self):
        self.assertEqual(b.diff({'a': (1, 2), 'b': {'c': 0.5}}, {'a': [1, 2], 'b': {'c': 0.5}}), [])
        self.assertEqual(b.diff({'a': 1, 'b': {'c': 0.5}}, {'b': {'c': 0.6}}), ['/a: missing', '/b/c: 0.5 != 0.6'])

    def test_synthetic_item_deterministic_and_shaped(self):
        x, y = b.synthetic_item(50, 7), b.synthetic_item(50, 7)
        self.assertEqual(x, y)
        self.assertEqual(len(x['texts']), 50)
        self.assertNotEqual(x, b.synthetic_item(50, 8))
        self.assertTrue(x['goal'].startswith('fix the '))

    def test_edge_row(self):
        self.assertEqual(b.edge_row({30: dict(passed=3, n=5), 50: dict(passed=2, n=5)}), {'30': 3, '50': 2})

    def test_render_md_aggregates_only(self):
        auc = {'specialist_v3': dict(recall=0.9, all_kept=0.4), 'bm25': dict(recall=0.8, all_kept=0.3)}
        ci = dict(recall=dict(mean=0.1, ci95=[0.05, 0.15]), all_kept=dict(mean=0.1, ci95=[-0.01, 0.2]))
        r = dict(meta=dict(date_utc='2026-10-18T00:00:00Z', git_sha='0' * 40, git_dirty=False, machine='m', cpus=1,
                           load_avg_1m=1.0),
                 edge=dict(cases=2, arms=dict(specialist_v3=dict(source='MEDIDO', passed={'30': 2, '50': 1, '70': 0}),
                                              jev=dict(source='not cached', passed=None))),
                 dev=dict(dev=dict(items=3, auc=auc, diff=[]),
                          jev_overlap=dict(items=2, auc=auc, source={}), jev_overlap_opus=dict(items=1, auc=auc, source={})),
                 heldout=dict(primary_items=3, groups=2, identical=True, fields_compared=6, primary_auc=auc, llm_items=2,
                              llm_auc=auc, bootstrap=dict(bm25=ci)),
                 cost=dict(items=[dict(blocks=10, chars=100, ms=5)], peak_rss_mb=50.0, load_avg_1m=1.0))
        md = b.render_md(r)
        for s in ('| specialist_v3 | MEDIDO | 2 | 1 | 0 |', 'not cached', 'Matches v3-dev-results.json: **yes**',
                  '**identical**', 'bm25: recall +0.1000 [+0.0500, +0.1500]', '| 10 | 100 | 5 | 50.0 |'):
            self.assertIn(s, md)


if __name__ == '__main__':
    unittest.main()
