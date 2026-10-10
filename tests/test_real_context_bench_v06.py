"""Stdlib-only tests for the v0.6 recoverability audit: packets, file split, judge isolation and the
two-judge aggregation copied from v0.4 (no lcc, no network)."""
import json
import tempfile
import unittest
from pathlib import Path

from research import real_context_bench_v04_audit as v04a
from research import real_context_bench_v06_audit as au
from research import real_context_bench_v06_test as t6
from research import recoverable_dev_measure as rdm


def blk(m, kind, content, role='user', tool=None, tid=None):
    return dict(m=m, role=role, kind=kind, tool_name=tool, tool_use_id=tid, is_error=False, content=content)


def verdict(aid, v, reason):
    return dict(audit_id=aid, verdict=v, reason=reason)


class PacketTests(unittest.TestCase):
    def test_packet_matches_dev_fields_and_is_blind(self):
        d = dict(goal='fix the header', blocks=[
            blk(0, 'text', 'hello'), blk(1, 'tool_use', '{"path": "a.py"}', 'assistant', 'read_file', 'c1'),
            blk(2, 'tool_result', 'X' * 9000, 'user', 'read_file', 'c1'), blk(3, 'text', 'done', 'assistant')])
        p = t6.packet('R001', d, d['blocks'][1], d['blocks'][2], '[removed: re-read a.py to recover]')
        self.assertEqual(list(p), ['audit_id', 'request', 'recent_turns', 'tool', 'tool_input', 'recovery_pointer',
                                   'removed_output', 'removed_output_chars'])
        self.assertEqual(p['removed_output_chars'], 9000)
        self.assertLessEqual(len(p['removed_output']), rdm.CLIP_OUTPUT + 60)
        for k in ('item', 'category', 'reason', 'pointer_kind', 'decision', 'rule'):
            self.assertNotIn(k, p)

    def test_file_split_is_thirds_and_50_each_at_150(self):
        for n in (150, 7, 2, 1):
            idx = [t6.file_index(i, n) for i in range(n)]
            self.assertEqual(idx, sorted(idx))
            self.assertTrue(all(0 <= x <= 2 for x in idx))
        self.assertEqual([[t6.file_index(i, 150) for i in range(150)].count(f) for f in range(3)], [50, 50, 50])

    def test_pointer_kind(self):
        self.assertEqual(t6.pointer_kind(dict(recover=dict(kind='file', lines=[1, 9]))), 'file_range')
        self.assertEqual(t6.pointer_kind(dict(recover=dict(kind='file'))), 'file_whole')
        self.assertEqual(t6.pointer_kind(dict(recover=dict(kind='command'))), 'command')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'audit').mkdir()
        self.ids = [f'R{i:03d}' for i in range(1, 7)]  # f1: R001-2, f2: R003-4, f3: R005-6
        for f, ids in zip(au.FILES, (self.ids[:2], self.ids[2:4], self.ids[4:])):
            (self.root / 'audit' / f'{f}.jsonl').write_text(''.join(json.dumps(dict(audit_id=a)) + '\n' for a in ids))

    def tearDown(self):
        self.tmp.cleanup()

    def dump(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def ok(self, j, aid, v='not_needed'):
        return verdict(aid, v, f'judge {j} specific reason about record {aid} output')

    def test_same_validity_flag_and_rates_as_v04(self):
        self.assertEqual((au.OUTCOMES, au.FILES, au.JUDGES, au.MIN_WORDS, au.THRESHOLD),
                         (v04a.OUTCOMES, v04a.FILES, v04a.JUDGES, v04a.MIN_WORDS, v04a.THRESHOLD))
        rows = [verdict('R001', 'not_needed', 'Not needed for this request.'),
                verdict('R002', 'not_needed', 'not needed for this request'),
                verdict('R003', 'needed_unrecoverable', 'a long enough but invalid verdict value here'),
                verdict('R004', 'needed', 'too short'),
                verdict('R005', 'unsure', 'the removed listing had a status line the request asks about')]
        self.assertEqual(au.valid_verdicts(rows), {'R005': 'unsure'})
        self.assertEqual(au.valid_verdicts(rows), v04a.valid_verdicts(rows))
        mk = lambda k, n: {f'R{i:03d}': (['unsure', 'not_needed'] if i < k else ['not_needed'] * 2) for i in range(n)}  # noqa: E731
        for k in (0, 7, 8, 20):
            a, b = au.aggregate(mk(k, 150)), v04a.aggregate(mk(k, 150))
            self.assertEqual(a['acceptance'], b['acceptance'])
            self.assertEqual(a['primary_flagged'], b['primary_flagged'])
            self.assertEqual(a['secondary_needed_unrecoverable_only'], b['secondary_needed_only'])
        self.assertEqual(au.aggregate(mk(7, 150))['acceptance']['result'], 'PASS')
        self.assertEqual(au.aggregate(mk(8, 150))['acceptance']['result'], 'FAIL')

    def test_either_judge_flags_and_rejudge_uses_isolated_folders(self):
        A = [self.ok('A', a) for a in self.ids[:4]]
        B = [self.ok('B', a) for a in self.ids[2:]]
        C = [self.ok('C', a) for a in self.ids[4:]] + [self.ok('C', 'R001', 'unsure')]
        C.append(verdict('R002', 'not_needed', 'generic reason repeated on purpose ok'))
        C.append(verdict('R005', 'not_needed', 'generic reason repeated on purpose ok'))  # both copies invalid
        C = [r for r in C if not (r['audit_id'] == 'R005' and 'judge C' in r['reason'])]
        for j, rows in zip('ABC', (A, B, C)):
            self.dump(au.verdicts_path(self.root, j), rows)
        self.assertEqual(au.needs_rejudge(self.root), {'B': ['R002'], 'A': ['R005']})
        self.assertEqual(au.rejudge(self.root), {'B': 1, 'A': 1})
        self.assertEqual([p.name for p in au.rejudge_dir(self.root, 'A').iterdir()], ['rejudge-A.jsonl'])
        pairs, _ = au.final_pairs(self.root)
        self.assertEqual(len(pairs['R002']), 1)  # no re-judgment yet -> incomplete
        self.dump(au.rejudge_dir(self.root, 'B') / 'verdicts-rejudge-B.jsonl', [self.ok('B', 'R002', 'needed')])
        self.dump(au.rejudge_dir(self.root, 'A') / 'verdicts-rejudge-A.jsonl', [self.ok('A', 'R005')])
        pairs, subs = au.final_pairs(self.root)
        self.assertEqual(subs, 2)
        out = au.aggregate(pairs)
        self.assertEqual(out['primary_flagged']['k'], 2)  # R001 unsure (C), R002 needed (B re-judge)
        self.assertEqual(out['needed_unrecoverable'], 1)
        self.assertEqual(out['secondary_needed_unrecoverable_only']['k'], 1)
        self.assertEqual((out['agreement']['pairs'], out['agreement']['agree']), (6, 4))

    def test_key_must_match_a_replace_with_the_same_pointer(self):
        run = self.root / 'runs' / au.ARM
        run.mkdir(parents=True)
        (run / 'i1.json').write_text(json.dumps(dict(decisions=[dict(id='c1', decision='replace', note='[p]')])))
        key = {'R001': dict(item='i1', tool_use_id='c1', recovery_pointer='[p]')}
        self.assertEqual(au.check_key(self.root, key), 0)
        key['R001']['recovery_pointer'] = '[other]'
        self.assertEqual(au.check_key(self.root, key), 1)


if __name__ == '__main__':
    unittest.main()
