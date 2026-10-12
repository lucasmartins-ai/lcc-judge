"""Stdlib tests for the LCC edge-case suite (synthetic fixtures only, no network, no private files)."""
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from research import edge_cases_build as build
from research import edge_suite as es

CASES = es.load_cases()
REQUIRED_USE_CASES = [  # the owner's minimum coverage list (specialist-v1 task)
    'pasted error + later fix', 'decision reversal', 're-read after edit', 'partial reads', 'huge logs',
    'git state', 'plan / todo', 'handoff', 'approvals / short replies', 'PT/EN mixed', 'long sessions >32K',
    'secrets / redaction', 'MCP / web outputs', 'subagent outputs', 'compaction summaries', 'duplicated content',
    'stale vs fresh errors', 'file named only in goal', 'numbers / config values', 'multi-file refactors']


def case(blocks, goal='g'):
    return dict(id='t', goal=goal, blocks=[dict(id=f'b{i}', gold=g, text='x' * (4 * n)) for i, (g, n) in enumerate(blocks)])


class ScorerTest(unittest.TestCase):
    def test_must_dropped_fails_and_budget_reached(self):
        c = case([('may', 50), ('must', 10), ('may', 40)])
        self.assertTrue(es.score_case(c, {'b0': 0, 'b1': 1, 'b2': 0}, 50)['passed'])
        r = es.score_case(c, {'b0': 1, 'b1': 0, 'b2': 1}, 50)
        self.assertFalse(r['passed'])
        self.assertEqual(r['lost_must'], ['b1'])
        self.assertGreaterEqual(r['removed'], 0.5)

    def test_unscored_dropped_last_and_ties_older_first(self):
        c = case([('may', 30), ('must', 30), ('may', 40)])
        self.assertTrue(es.score_case(c, {'b0': 0.0, 'b2': 0.0}, 60)['passed'])  # b1 unscored -> kept
        self.assertFalse(es.score_case(c, {}, 31)['passed'])  # all unscored: oldest first -> b0 then b1

    def test_one_of_group_needs_one_survivor(self):
        c = case([('one:a', 20), ('may', 60), ('one:a', 20)])
        self.assertTrue(es.score_case(c, {'b0': 0, 'b1': 0.1, 'b2': 1}, 70)['passed'])
        self.assertEqual(es.score_case(c, {'b0': 0, 'b1': 1, 'b2': 0}, 30)['lost_groups'], ['one:a'])


class SuiteTest(unittest.TestCase):
    def test_fixtures_and_catalog_in_sync_with_builder(self):
        self.assertEqual(build.main(['--check']), 0)

    def test_catalog_matches_fixtures_and_md(self):
        cat = json.loads((build.OUT / 'edge_cases.json').read_text())['cases']
        self.assertEqual(sorted(c['id'] for c in cat), sorted(c['id'] for c in CASES))
        md = (build.OUT / 'EDGE_CASES.md').read_text()
        for c in cat:
            self.assertIn(f"### `{c['id']}`", md)
            self.assertTrue(all(c[k] for k in build.CATALOG_KEYS), c['id'])
            self.assertIn(c['source'], {'real-derived', 'lcc-adversarial', 'synthetic'})

    def test_required_use_cases_and_all_categories_covered(self):
        uses = ' | '.join(c['use_case'] for c in CASES)
        for u in REQUIRED_USE_CASES:
            self.assertIn(u, uses)
        cats = {c['category'] for c in CASES}
        self.assertEqual(len(cats), 13)  # every taxonomy-v2 category
        self.assertTrue(any(sum(build.tok(b['text']) for b in c['blocks']) > 32768 for c in CASES))

    def test_oracle_passes_every_case_at_every_budget(self):
        res = es.run(CASES, es.arm_scores(CASES, es.oracle))
        for bud in es.BUDGETS:
            self.assertEqual(es.summary(CASES, res)[bud]['failed'], [])

    def test_suite_separates_naive_arms(self):
        n = len(CASES)
        for arm in (es.recency, es.bm25, es.random_arm(0)):
            self.assertLess(es.summary(CASES, es.run(CASES, es.arm_scores(CASES, arm)))[50]['passed'], n)

    def test_size_alone_does_not_solve_the_suite(self):  # label review 2026-10-12, high finding
        for arm in (es.drop_largest, es.drop_smallest):
            res = es.summary(CASES, es.run(CASES, es.arm_scores(CASES, arm)))
            for bud in es.BUDGETS:
                self.assertLessEqual(res[bud]['passed'], 0.5 * len(CASES), (arm.__name__, bud))

    def test_balance_keeps_text_and_order(self):
        blocks = [dict(gold='may', role='tool', kind='tool_result', tool='Bash', is_error=False,
                       text='\n'.join(f'line {i} ' + 'x' * 30 for i in range(200))),
                  dict(gold='must', role='user', kind='text', tool=None, is_error=False, text='y' * 200)]
        out = build.balance(blocks, 'seed')
        self.assertGreater(len(out), 5)
        self.assertEqual(out[-1]['gold'], 'must')
        self.assertEqual(''.join(b['text'] for b in out[:-1]), blocks[0]['text'])
        self.assertTrue(all(b['gold'] == 'may' and b['tool'] == 'Bash' for b in out[:-1]))

    def test_fixtures_hold_no_secret_shaped_values(self):
        pat = re.compile(r'sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY')
        for c in CASES:
            for b in c['blocks']:
                self.assertIsNone(pat.search(b['text']), (c['id'], b['id']))

    def test_export_has_no_gold_and_score_cli_reads_scores(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'cases.jsonl'
            with contextlib.redirect_stdout(io.StringIO()):
                es.main(['export', '--out', str(out)])
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), len(CASES))
            self.assertNotIn('gold', json.dumps(rows))
            scores = Path(d) / 's.json'
            scores.write_text(json.dumps(es.arm_scores(CASES, es.oracle)))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(es.main(['score', '--scores', str(scores)]), 0)
            self.assertIn(f'| arm | {len(CASES)}/{len(CASES)}', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
