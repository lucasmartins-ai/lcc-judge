"""Stdlib-only tests for v0.7: the label-only adaptation of the v0.6 aggregation, the kind-stratified audit
sample, the file deal, the temp-path check and the frozen judging text (no lcc, no network)."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from research import real_context_bench_v06_audit as v06a
from research import real_context_bench_v07_audit as au
from research import real_context_bench_v07_test as t7

TO_V07 = {'needed': 'needed_unrecoverable', 'not_needed': 'ok', 'unsure': 'unsure'}
TEXT = ('Blind auditor for a context compactor. Each record: a user request to a coding agent, the last turns, an '
        'earlier tool call whose output was REMOVED and replaced by the recovery pointer shown. Question: to correctly '
        'do what the user asked now, does the agent need the removed content AND would it be unable to get it back by '
        'following the pointer (re-read / re-run, in the stated directory), given what happened later in the session '
        'as far as you can tell? Answer needed_unrecoverable / ok / unsure, with a specific 5-15 word reason per '
        'record, unique, no quotes from the data.')


def write_tree(root, rows_by_judge, relabel):
    (root / 'audit').mkdir(parents=True)
    ids = [f'R{i:03d}' for i in range(1, 7)]
    for f, part in zip(au.FILES, (ids[:2], ids[2:4], ids[4:])):
        (root / 'audit' / f'{f}.jsonl').write_text(''.join(json.dumps(dict(audit_id=a)) + '\n' for a in part))
    for j, rows in rows_by_judge.items():
        p = au.verdicts_path(root, j)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(''.join(json.dumps(dict(r, verdict=relabel.get(r['verdict'], r['verdict']))) + '\n' for r in rows))


class AggregationTests(unittest.TestCase):
    def test_constants_equal_v06_except_labels(self):
        self.assertEqual(tuple(TO_V07[x] for x in v06a.OUTCOMES), au.OUTCOMES)
        self.assertEqual(tuple(TO_V07[x] for x in v06a.BAD), au.BAD)
        self.assertEqual((au.FILES, au.JUDGES, au.MIN_WORDS, au.THRESHOLD, au.ARM),
                         (v06a.FILES, v06a.JUDGES, v06a.MIN_WORDS, v06a.THRESHOLD, v06a.ARM))

    def test_same_results_as_v06_on_relabelled_inputs(self):
        r = lambda j, a, v: dict(audit_id=a, verdict=v, reason=f'judge {j} specific reason for record {a} here')  # noqa: E731
        rows = {'A': [r('A', 'R001', 'not_needed'), r('A', 'R002', 'needed'), r('A', 'R003', 'unsure'),
                      dict(audit_id='R004', verdict='not_needed', reason='too short')],
                'B': [r('B', a, 'not_needed') for a in ('R003', 'R004', 'R005', 'R006')],
                'C': [r('C', 'R005', 'not_needed'), r('C', 'R001', 'unsure')]}
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            write_tree(Path(a), rows, {})
            write_tree(Path(b), rows, TO_V07)
            self.assertEqual(v06a.needs_rejudge(a), au.needs_rejudge(b))
            p6, s6 = v06a.final_pairs(a)
            p7, s7 = au.final_pairs(b)
            self.assertEqual(({k: [TO_V07[x] for x in v] for k, v in p6.items()}, s6), (p7, s7))
            g6, g7 = v06a.aggregate(p6), au.aggregate(p7)
            g6['ok'] = g6.pop('not_needed')
            self.assertEqual(g6, g7)
        self.assertEqual(g7['primary_flagged']['k'], 5)  # R001, R003 unsure; R002, R004, R006 incomplete

    def test_threshold_7_of_150(self):
        mk = lambda k: {f'R{i:03d}': (['unsure', 'ok'] if i < k else ['ok', 'ok']) for i in range(150)}  # noqa: E731
        self.assertEqual(au.aggregate(mk(7))['acceptance']['result'], 'PASS')
        self.assertEqual(au.aggregate(mk(8))['acceptance']['result'], 'FAIL')
        self.assertEqual(au.flag(['ok', 'needed_unrecoverable']), 'needed_unrecoverable')


class SelectionTests(unittest.TestCase):
    def test_balanced_when_population_allows(self):
        pools = {k: {f'{k}{i}': [f't{j}' for j in range(4)] for i in range(40)} for k in t7.KINDS}
        got = t7.stratified_select(pools, 20261014, 150, 3)
        self.assertEqual([len(got[k]) for k in t7.KINDS], [50, 50, 50])

    def test_shortfall_filled_from_other_kinds_and_cap_is_global(self):
        pools = {'file_whole': {f'i{i}': ['a', 'b', 'c', 'd'] for i in range(40)},
                 'file_range': {f'i{i}': ['e', 'f'] for i in range(40)},
                 'command': {'i0': ['g', 'h']}}
        got = t7.stratified_select(pools, 1, 150, 3)
        n = {k: len(v) for k, v in got.items()}
        self.assertEqual(n['command'], 2)
        self.assertEqual(sum(n.values()), 120)  # 40 items x cap 3
        per_item = Counter(item for v in got.values() for item, _ in v)
        self.assertLessEqual(max(per_item.values()), 3)
        self.assertEqual(len({(k, x) for k, v in got.items() for x in v}), 120)
        self.assertEqual(got, t7.stratified_select(pools, 1, 150, 3))  # deterministic

    def test_deal_files_balanced_per_kind(self):
        picked = {'file_whole': [(f'a{i}', 't') for i in range(60)], 'file_range': [(f'b{i}', 't') for i in range(88)],
                  'command': [('c0', 't'), ('c1', 't')]}
        dealt = t7.deal_files(picked, 7)
        self.assertEqual([f for *_, f in dealt], sorted(f for *_, f in dealt))  # R001.. in f1, f2, f3 order
        self.assertEqual(Counter(f for *_, f in dealt), {'f1': 50, 'f2': 50, 'f3': 50})
        for k in t7.KINDS:
            c = Counter(f for kk, *_, f in dealt if kk == k)
            self.assertLessEqual(max(c.values()) - min(c.get(f, 0) for f in au.FILES), 1)


class CheckTests(unittest.TestCase):
    def test_temp_pointer_is_flagged(self):
        blocks = [dict(m=0, role='user', kind='text', tool_name=None, tool_use_id=None, is_error=False, content='go')]
        for note, bad in (('[removed: re-read /tmp/x.log to recover]', True),
                          ('[removed: re-run `ls` in /private/var/folders/x to recover]', True),
                          ('[removed: re-read a.py (cwd /tmp) to recover]', True),
                          ('[removed: re-read /repo/tmp/x.py to recover]', False)):
            self.assertEqual(bool(t7.TEMP.search(note)), bad, note)
        self.assertEqual(t7.independent_check_v3(blocks, [], 'go'), [])

    def test_judging_text_is_frozen(self):
        self.assertEqual(t7.JUDGE_TEXT, TEXT)


if __name__ == '__main__':
    unittest.main()
