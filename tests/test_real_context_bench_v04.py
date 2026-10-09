"""Stdlib-only tests for the v0.4 sampler, audit packets and the two-judge aggregation (no lcc, no network)."""
import json
import tempfile
import unittest
from pathlib import Path

from research import real_context_bench_v04 as v04
from research import real_context_bench_v04_audit as au

NOTE = '[... lcc: {n} chars of this tool result dropped; re-run exec_command for the rest ...]'


def lcc_trim(text, head=300, tail=300):  # mirrors lcc.relevance.transcript._trimmed_result_text
    t = text[-tail:]
    return f'{text[:head]}\n{NOTE.format(n=len(text) - head - tail)}\n{t}'


def blk(m, kind, content, role='user', tool=None, tid=None):
    return dict(m=m, role=role, kind=kind, tool_name=tool, tool_use_id=tid, is_error=False, content=content)


class SampleTests(unittest.TestCase):
    def test_draw_per_session_caps_and_is_seeded(self):
        by = {'s1': ['a', 'b', 'c', 'd'], 's2': ['e'], 's3': ['f', 'g']}
        got = v04.draw_per_session(by, seed=7)
        self.assertEqual(got, v04.draw_per_session(by, seed=7))
        self.assertEqual(len(got), 5)
        self.assertLessEqual(sum(x in 'abcd' for x in got), 2)

    def test_allocate_is_equal_round_robin(self):
        strata = {'x': [f'x{i}' for i in range(10)], 'y': ['y0', 'y1'], 'z': [f'z{i}' for i in range(10)]}
        got = v04.allocate(strata, seed=1, n=9)
        self.assertEqual(len(got), 9)
        self.assertEqual(sum(g.startswith('y') for g in got), 2)
        self.assertEqual(sorted(sum(g.startswith(k) for g in got) for k in 'xz'), [3, 4])
        self.assertEqual(got, v04.allocate(strata, seed=1, n=9))
        self.assertEqual(len(v04.allocate(strata, seed=1, n=100)), 22)


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.orig = 'H' * 300 + 'MIDDLE-STATUS-LINE ' * 200 + 'T' * 300
        self.trimmed = lcc_trim(self.orig)
        self.d = dict(goal='why did it fail?', blocks=[
            blk(0, 'text', 'hello'), blk(1, 'text', 'ran it', 'assistant'),
            blk(2, 'tool_use', '{"cmd": "make"}', 'assistant', 'exec_command', 'c1'),
            blk(3, 'tool_result', self.orig, 'user', 'exec_command', 'c1'), blk(4, 'text', 'done', 'assistant')])

    def test_split_trim_returns_removed_middle(self):
        head, removed, tail = v04.split_trim(self.orig, self.trimmed)
        self.assertEqual((head, tail), ('H' * 300, 'T' * 300))
        self.assertEqual(removed, 'MIDDLE-STATUS-LINE ' * 200)
        with self.assertRaises(ValueError):
            v04.split_trim(self.orig, 'no note here')
        with self.assertRaises(ValueError):
            v04.split_trim('X' + self.orig[1:], self.trimmed)

    def test_trim_packet_shows_middle_and_kept_without_lcc_marker(self):
        p = v04.packet('D001', self.d, self.d['blocks'][2], self.d['blocks'][3], 'trim', self.trimmed)
        s = json.dumps(p)
        self.assertNotIn('lcc:', s)
        self.assertEqual(p['change'], 'shortened')
        self.assertIn('MIDDLE-STATUS-LINE', p['removed_middle'])
        self.assertLessEqual(len(p['removed_middle']), v04.CLIP_OUTPUT + 60)
        self.assertEqual(p['removed_middle_chars'], len('MIDDLE-STATUS-LINE ' * 200))
        self.assertEqual((p['kept_head'], p['kept_tail']), ('H' * 300, 'T' * 300))
        self.assertNotIn('original_output', p)
        self.assertEqual([t['text'] for t in p['recent_turns']], ['hello', 'ran it', 'done'])

    def test_drop_packet_and_note_stripping_everywhere(self):
        d = dict(self.d, goal='see ' + NOTE.format(n=5))
        p = v04.packet('D002', d, self.d['blocks'][2], self.d['blocks'][3], 'drop', None)
        self.assertEqual(p['change'], 'removed')
        self.assertEqual(p['original_output_chars'], len(self.orig))
        self.assertLessEqual(len(p['original_output']), v04.CLIP_OUTPUT + 60)
        self.assertNotIn('lcc:', json.dumps(p))
        for k in ('decision', 'reason', 'rule', 'arm', 'source', 'item', 'category'):
            self.assertNotIn(k, p)


def verdict(aid, v, reason):
    return dict(audit_id=aid, verdict=v, reason=reason)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'audit').mkdir()
        self.ids = [f'D{i:03d}' for i in range(1, 7)]  # f1: D001-2, f2: D003-4, f3: D005-6
        for f, ids in zip(au.FILES, (self.ids[:2], self.ids[2:4], self.ids[4:])):
            self.dump(f'{f}.jsonl', [dict(audit_id=a) for a in ids])

    def tearDown(self):
        self.tmp.cleanup()

    def dump(self, name, rows):
        (self.root / 'audit' / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def ok(self, j, aid, v='not_needed'):
        return verdict(aid, v, f'judge {j} specific reason about record {aid} output')

    def test_routing_gives_every_file_two_judges_and_one_third(self):
        for f in au.FILES:
            self.assertEqual(len(au.assigned(f)), 2)
            self.assertNotIn(au.third(f), au.assigned(f))

    def test_validity_rejects_short_repeated_and_bad_verdicts(self):
        rows = [verdict('D001', 'not_needed', 'Not needed for this request.'),
                verdict('D002', 'not_needed', 'not needed for this request'),
                verdict('D003', 'maybe', 'a long enough but invalid verdict value here'),
                verdict('D004', 'needed', 'too short'),
                verdict('D005', 'unsure', 'the removed middle had a status line the request asks about')]
        self.assertEqual(au.valid_verdicts(rows), {'D005': 'unsure'})

    def test_either_judge_flags_and_rejudge_fills_invalid(self):
        A = [self.ok('A', a) for a in self.ids[:4]]
        B = [self.ok('B', a) for a in self.ids[2:]]
        C = [self.ok('C', a) for a in self.ids[4:]] + [self.ok('C', 'D001', 'unsure')]
        C.append(verdict('D002', 'not_needed', 'generic reason repeated on purpose ok'))
        C.append(verdict('D005', 'not_needed', 'generic reason repeated on purpose ok'))  # both copies invalid
        C = [r for r in C if not (r['audit_id'] == 'D005' and 'judge C' in r['reason'])]
        for j, rows in zip('ABC', (A, B, C)):
            self.dump(f'verdicts-{j}.jsonl', rows)
        self.assertEqual(au.needs_rejudge(self.root), {'B': ['D002'], 'A': ['D005']})
        self.assertEqual(au.rejudge(self.root), {'B': 1, 'A': 1})
        self.assertTrue((self.root / 'audit' / 'rejudge-A.jsonl').exists())
        pairs, subs = au.final_pairs(self.root)
        self.assertEqual(len(pairs['D002']), 1)  # no re-judgment yet -> incomplete
        self.dump('verdicts-rejudge-B.jsonl', [self.ok('B', 'D002', 'needed')])
        self.dump('verdicts-rejudge-A.jsonl', [self.ok('A', 'D005')])
        pairs, subs = au.final_pairs(self.root)
        self.assertEqual(subs, 2)
        self.assertTrue(all(len(v) == 2 for v in pairs.values()))
        out = au.aggregate(pairs)
        self.assertEqual(out['primary_flagged']['k'], 2)  # D001 unsure (C), D002 needed (B re-judge)
        self.assertEqual(out['secondary_needed_only']['k'], 1)
        self.assertEqual(out['agreement']['pairs'], 6)
        self.assertEqual(out['agreement']['agree'], 4)

    def test_rejudge_reason_repeating_main_file_is_invalid(self):
        main = [self.ok('A', 'D001')]
        self.assertEqual(au.valid_verdicts([self.ok('A', 'D001')], main), {})

    def test_acceptance_boundary_matches_wilson(self):
        mk = lambda k, n: {f'D{i:03d}': (['unsure', 'not_needed'] if i < k else ['not_needed'] * 2) for i in range(n)}  # noqa: E731
        self.assertEqual(au.aggregate(mk(7, 150))['acceptance']['result'], 'PASS')
        self.assertEqual(au.aggregate(mk(8, 150))['acceptance']['result'], 'FAIL')
        inc = mk(7, 150)
        inc['D149'] = ['not_needed']  # incomplete counts as flagged
        self.assertEqual(au.aggregate(inc)['primary_flagged']['k'], 8)

    def test_kappa(self):
        self.assertEqual(au.kappa([('needed', 'needed'), ('not_needed', 'not_needed')]), 1.0)
        self.assertIsNone(au.kappa([]))


if __name__ == '__main__':
    unittest.main()
