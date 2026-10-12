"""Synthetic checks for the one-shot test runner: group bootstrap, gates and TEST_RESULTS.md render.
No private files, no test items, no models."""
import random
import unittest

from research import specialist_v2_test as t


def item(iid, group, source, used):
    blocks = [dict(id=f'{iid}b{i}', i=i, tokens=10, used=u, protected=False) for i, u in enumerate(used)]
    return dict(item_id=iid, group=group, source=source, category='debug', evidence='actions', blocks=blocks,
                evidence_sets=[])


class RunnerTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(0)
        self.items = [item(f'i{k}', f'g{k // 2}', ('claude', 'codex')[k % 2], [rng.random() < 0.3 for _ in range(9)] + [True])
                      for k in range(20)]
        good = {it['item_id']: {b['id']: float(b['used']) + 0.01 * b['i'] for b in it['blocks']} for it in self.items}
        flat = {it['item_id']: {b['id']: float(b['i']) for b in it['blocks']} for it in self.items}
        self.arms = dict(specialist_v2=good, recency=flat, bm25=flat, mechanical=flat,
                         **{f'random_s{s}': flat for s in range(5)})

    def test_bootstrap_and_gates(self):
        curves, per, by_src, by_cat = t.evaluate_set(self.items, self.arms)
        self.assertEqual(set(by_src), {'claude', 'codex'})
        self.assertEqual(by_cat['debug']['n'], 20)
        boot = {a: t.cluster_boot(self.items, per['specialist_v2'], per[a], n=200) for a in t.BASELINES}
        self.assertGreater(boot['recency']['recall']['ci95'][0], 0)
        ok, rows = t.gate_beats(boot, curves)
        self.assertTrue(ok, rows)
        same = t.cluster_boot(self.items, per['recency'], per['recency'], n=50)
        self.assertEqual(same['recall'], dict(mean=0.0, ci95=[0.0, 0.0]))
        self.assertFalse(t.gate_beats({a: same for a in t.BASELINES}, curves)[0])
        edge = {a: {b: dict(passed=20) for b in ('30', '50', '70')} for a in t.EDGE_RIVALS if a != 'laya'}
        edge['specialist_v2'] = {b: dict(passed=20) for b in ('30', '50', '70')}
        self.assertTrue(t.gate_edge(edge)[0])  # ties pass (>=)
        edge['mechanical']['70']['passed'] = 21
        self.assertFalse(t.gate_edge(edge)[0])
        self.assertFalse(t.gate_cost(dict(ms_median=10, ms_p90=10, peak_rss_mb=301))[0])

    def test_render(self):
        curves, per, by_src, by_cat = t.evaluate_set(self.items, self.arms)
        boot = {a: t.cluster_boot(self.items, per['specialist_v2'], per[a], n=50) for a in t.BASELINES}
        block = dict(items=20, curves=curves, by_source=by_src, by_category=by_cat, bootstrap=boot)
        edge = {a: {b: dict(passed=1, n=35, failed=['x']) for b in ('30', '50', '70')} for a in ('specialist_v2', 'bm25')}
        cost = dict(items=20, blocks_median=10, blocks_max=10, ms_median=1.0, ms_p90=2.0, ms_max=3.0, over_1s=0,
                    ms_median_250_600_blocks=None, n_250_600_blocks=0, peak_rss_mb=70.0, load_ms=5, model_file_kb=4,
                    load_avg_1m=1.0)
        res = dict(protocol_sha256='0' * 64, primary=block, all_eligible=block, edge_suite=edge, cost=cost,
                   counts=dict(test_items=20, excluded={}, eligible=20, fork_linked_to_train_or_dev=0,
                               fork_linked_by_split={}, primary=20, primary_groups=10, primary_per_source={},
                               primary_candidates=200, primary_used=40),
                   specialist_v1_subset=dict(items=20, curves=curves, bootstrap_vs_v1=boot['bm25']),
                   jev_test_overlap=dict(items=0),
                   acceptance=dict(i_beats_baselines=dict(ok=True, rows={'bm25:recall': True}),
                                   ii_edge=dict(ok=True, rows={'30': dict(v2=1, best_other=1, ok=True)}),
                                   iii_cost=t.gate_cost(cost)[1] and dict(ok=True, rows=t.gate_cost(cost)[1]),
                                   verdict='PASS'))
        md = t.render_md(res)
        self.assertLess(md.index('## Limits'), md.index('## Verdict'))
        self.assertIn('INFERIDO', md)
        self.assertIn('**PASS**', md)


if __name__ == '__main__':
    unittest.main()
