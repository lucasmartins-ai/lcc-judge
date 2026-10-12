"""Stdlib tests for matched-budget v2 metric logic (synthetic items only, no private files, no models)."""
import unittest

from research import matched_budget_v2 as m


def item(spec, sets=()):
    """spec: [(tokens, used, protected)] oldest first."""
    blocks = [dict(id=f'b{i}', i=i, tokens=t, used=u, protected=p) for i, (t, u, p) in enumerate(spec)]
    ev = [dict(blocks=[int(x[1:]) for x in b], generic=g, refetched=r) for b, g, r in sets]
    return dict(item_id='x', source='claude', evidence='actions', blocks=blocks, evidence_sets=ev)


class MetricTest(unittest.TestCase):
    def test_recall_and_all_kept(self):
        it = item([(10, True, False), (10, False, False), (20, True, False), (60, False, False)])
        keep_used = {'b0': 1.0, 'b1': 0.0, 'b2': 1.0, 'b3': 0.0}
        r = m.item_metrics(it, keep_used)
        self.assertEqual(r[0]['recall'], 1.0)
        self.assertTrue(r[60]['all_kept'])  # b1 + b3 = 70 tokens >= 60%
        rev = {k: -v for k, v in keep_used.items()}
        r = m.item_metrics(it, rev)
        self.assertFalse(r[10]['all_kept'])  # drops b0 first (tie with b2 -> older first)
        self.assertAlmostEqual(r[10]['recall'], 20 / 30)

    def test_unscored_dropped_last(self):
        it = item([(50, True, False), (50, False, False)])
        r = m.item_metrics(it, {'b0': None, 'b1': None})
        self.assertFalse(r[10]['all_kept'])  # all unscored: oldest first
        r = m.item_metrics(it, {'b0': None, 'b1': 0.0})
        self.assertTrue(r[50]['all_kept'])

    def test_protected_blocks_are_not_candidates(self):
        it = item([(100, True, True), (10, True, False), (10, False, False)])
        r = m.item_metrics(it, {'b1': 1.0, 'b2': 0.0})
        self.assertTrue(r[50]['all_kept'])
        self.assertEqual(r[50]['removed'], 0.5)

    def test_evidence_coverage_needs_one_holder(self):
        it = item([(10, True, False), (10, True, False), (10, False, False), (10, False, True)],
                  sets=[(('b0', 'b1'), False, False), (('b2',), True, False), (('b0', 'b3'), False, False),
                        (('b1',), False, True)])
        self.assertEqual(m.evidence_groups(it), [{'b0', 'b1'}])  # generic, protected holder, refetched dropped
        r = m.item_metrics(it, {'b0': 0.0, 'b1': 1.0, 'b2': 0.5})
        self.assertEqual(r[30]['ev_cov'], 1.0)  # b0 dropped, b1 survives
        self.assertFalse(r[30]['all_kept'])

    def test_eligible(self):
        self.assertTrue(m.eligible(item([(10, True, False)])))
        self.assertFalse(m.eligible(item([(10, True, True), (10, False, False)])))
        self.assertFalse(m.eligible(dict(item([(10, True, False)]), evidence='none')))

    def test_model_subset_is_seeded_and_stratified(self):
        idx = [(f'{s}{i}', s) for s in ('a', 'b') for i in range(20)]
        one = m.model_subset(idx, 3)
        self.assertEqual(one, m.model_subset(list(reversed(idx)), 3))
        self.assertEqual(sum(i.startswith('a') for i in one), 3)
        self.assertEqual(len(m.model_subset(idx[:2], 3)), 2)

    def test_aggregate_auc(self):
        it = item([(30, True, False), (70, False, False)])
        good = m.aggregate({'x': m.item_metrics(it, {'b0': 1, 'b1': 0})})
        bad = m.aggregate({'x': m.item_metrics(it, {'b0': 0, 'b1': 1})})
        self.assertEqual(good['auc']['recall'], 1.0)
        self.assertLess(bad['auc']['recall'], 0.2)
        self.assertEqual(good['10']['n'], 1)


if __name__ == '__main__':
    unittest.main()
