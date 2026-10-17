"""v3 final test runner on synthetic items only (no private files, no models, no CLI)."""
import random
import unittest

from research import llm_judge_arm as lj
from research import v3_final_test as v


def item(iid, group, source, used):
    blocks = [dict(id=f'{iid}b{i}', i=i, tokens=10, used=u, protected=False) for i, u in enumerate(used)]
    return dict(item_id=iid, group=group, source=source, category='debug', evidence='actions', blocks=blocks,
                evidence_sets=[])


class Runner(unittest.TestCase):
    def setUp(self):
        rng = random.Random(0)
        self.items = [item(f'i{k:02d}', f'g{k // 2}', ('claude', 'codex')[k % 2],
                           [rng.random() < 0.3 for _ in range(9)] + [True]) for k in range(20)]
        good = {it['item_id']: {b['id']: float(b['used']) + 0.01 * b['i'] for b in it['blocks']} for it in self.items}
        flat = {it['item_id']: {b['id']: float(b['i']) for b in it['blocks']} for it in self.items}
        half = {i: {b: (None if n % 2 else s) for n, (b, s) in enumerate(d.items())} for i, d in good.items()}
        self.arms = dict(specialist_v3=good, recency=flat, bm25=flat, mechanical=flat, opus=good,
                         **{'gemini-flash': half}, **{f'random_s{s}': flat for s in range(5)})

    def test_subset_one_per_group_seeded_capped(self):
        s = v.pick_subset(self.items)
        self.assertEqual(len(s), 10)
        self.assertEqual(len({int(i[1:]) // 2 for i in s}), 10)  # one per group
        self.assertEqual(s, v.pick_subset(self.items))
        self.assertNotEqual(s, v.pick_subset(self.items, seed=1))
        self.assertEqual(len(v.pick_subset(self.items, cap=3)), 3)
        self.assertEqual({int(i[1:]) // 2 for i in v.pick_subset(self.items, cap=3)}, {0, 1, 2})

    def test_verdicts(self):
        b = lambda r, a: dict(recall=dict(mean=0, ci95=[r, 1]), all_kept=dict(mean=0, ci95=[a, 1]))  # noqa: E731
        self.assertEqual(v.verdict_llm(b(0.01, -0.01)), dict(recall='superior', all_kept='not inferior',
                                                              headline_superior=True))
        self.assertEqual(v.verdict_llm(b(-0.019, -0.02))['recall'], 'not inferior')
        self.assertEqual(v.verdict_llm(b(-0.019, -0.02))['all_kept'], 'inferior')
        self.assertFalse(v.verdict_llm(b(0.0, 0.5))['headline_superior'])  # lower bound must be > 0
        ok, rows = v.verdict_local({a: b(0.01, 0.01) for a in v.BASELINES})
        self.assertTrue(ok)
        self.assertFalse(v.verdict_local({**{a: b(0.01, 0.01) for a in v.BASELINES}, 'bm25': b(0.01, 0.0)})[0])

    def test_summary_bootstrap_and_render(self):
        s, per = v.summarize(self.items, self.arms)
        self.assertEqual(s['groups'], 10)
        bt = {a: v.boot(self.items, per, a, n=200) for a in v.BASELINES + v.LLM_ARMS}
        self.assertGreater(bt['recency']['recall']['ci95'][0], 0)
        self.assertEqual(bt['opus']['recall'], dict(mean=0.0, ci95=[0.0, 0.0]))
        s['bootstrap'] = {a: bt[a] for a in v.BASELINES}
        llm = dict(s, subset_items=10, subset_groups=10, finished={'opus': 10, 'gemini-flash': 10}, compared_items=10,
                   batches_cached={'opus': 20, 'gemini-flash': 20}, calls={}, limit_waits={}, call_cap=v.CALL_CAP,
                   unscored_blocks={'opus': 0, 'gemini-flash': 100}, bootstrap=bt,
                   verdict={a: v.verdict_llm(bt[a]) for a in v.LLM_ARMS})
        cost = dict(items=20, blocks_median=10, blocks_max=10, ms_median=1.0, ms_p90=2.0, ms_max=3.0, over_1s=0,
                    peak_rss_mb=70.0, load_ms=5, model_file_kb=4, load_avg_1m=1.0)
        res = dict(protocol_sha256='0' * 64, frozen_sha256=v.FROZEN, llm_judge_arm_frozen_sha256=v.LLM_ARM_FROZEN,
                   eval_code_sha256={'research/v3_final_test.py': 'x'},
                   receipt=dict(items=30, groups=12, per_source={'claude': 30}, sha256=dict(items_manifest='f' * 64)),
                   counts=dict(excluded={}, eligible=20, content_linked=0, primary=20, primary_groups=10,
                               primary_per_source={'claude': 10, 'codex': 10}, primary_candidates=200, primary_used=60),
                   primary=s, all_eligible=dict(items=0), cost=cost, llm_subset=llm,
                   edge_suite_stated=dict(cuts=(30, 50, 70), **v.EDGE),
                   acceptance=dict(i_local_baselines=dict(zip(('ok', 'rows'), v.verdict_local(s['bootstrap']))),
                                   ii_generalists=llm['verdict'],
                                   iii_cost=dict(zip(('ok', 'rows'), v.gate_cost(cost)))))
        md = v.render_md(res)
        self.assertIn('Local baselines', md)
        self.assertIn('v3 vs gemini-flash', md)
        self.assertNotIn('b0', md)  # no block ids / per-item rows in the report


class LlmSet(unittest.TestCase):
    def test_heldout_is_a_choice_and_routes_to_llm_set(self):
        calls = []
        orig = v.llm_set
        v.llm_set = lambda: calls.append(1) or [('i', 'g', [('b', 't')])]
        try:
            self.assertEqual(lj.load_set('heldout'), [('i', 'g', [('b', 't')])])
        finally:
            v.llm_set = orig
        self.assertEqual(calls, [1])


if __name__ == '__main__':
    unittest.main()
