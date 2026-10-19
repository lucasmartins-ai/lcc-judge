"""when_to_compact on synthetic traces only (no private data)."""
import json
import os
import tempfile
import unittest

from research import when_to_compact as w


def req(t, u=0, r=0, w5=0, w1=0, rid=None):
    return dict(rid=rid or f'r{t}', t0=float(t), t1=float(t), u=u, r=r, w5=w5, w1=w1, o=0, dup=False)


def trace(reqs, bounds=()):
    return w.annotate(dict(requests=list(reqs), boundaries=[dict(t=float(b), dup=False) for b in bounds],
                           subagent=False))


Q = w.Q_RECALL


class Simulate(unittest.TestCase):
    def cold(self, w1=False):
        k = 'w1' if w1 else 'w5'
        return trace([req(0, **{k: 10000}), req(10, r=10000, **{k: 90000}),
                      req(410, r=10000, **{k: 95000}), req(420, r=105000, **{k: 1000})])

    def test_p0_and_p2_are_identity(self):
        t = self.cold()
        for p in ('P0', 'P2'):
            s = w.simulate(t, w.POLICIES[p])
            self.assertAlmostEqual(s['saving'], 0.0)
            self.assertEqual(s['passes'], 0)

    def test_cold_stash_saves_the_rewrite_and_later_reads(self):
        s = w.simulate(self.cold(), w.POLICIES['P1'])
        new = 0.35 * 95000
        expect = new * 1.25 * (1 - Q) + 0.10 * (1 - Q) * new
        self.assertEqual(s['passes'], 1)
        self.assertAlmostEqual(s['saving'], expect, places=6)
        self.assertLess(s['ctx_mean'], s['ctx_base_mean'])

    def test_one_hour_ttl_does_not_trigger_p1_at_400s_but_p1_5m_does_and_loses_when_warm(self):
        warm = trace([req(0, w1=10000), req(10, r=10000, w1=90000), req(410, r=100000, w1=5000),
                      req(420, r=105000, w1=1000)])
        self.assertEqual(w.simulate(warm, w.POLICIES['P1'])['passes'], 0)
        s = w.simulate(warm, w.POLICIES['P1_5m'])
        self.assertEqual(s['passes'], 1)
        self.assertLess(s['saving'], 0)  # mid-prefix mutation on a warm 1h cache: rewrite at 2.0x

    def test_cold_1h_rewrite_priced_at_two(self):
        t = trace([req(0, w1=10000), req(10, r=10000, w1=90000), req(4000, r=10000, w1=95000)])
        s = w.simulate(t, w.POLICIES['P1'])
        self.assertAlmostEqual(s['saving'], 0.35 * 95000 * 2.0 * (1 - Q), places=6)

    def test_threshold_and_boundary_reset(self):
        t = self.cold()
        self.assertEqual(w.simulate(t, w.POLICIES['P1_min50k'])['passes'], 0)
        # a boundary between the gap request and the next resets the removal: request 4 gets no read saving
        tb = trace(t['requests'], bounds=[415])
        s = w.simulate(tb, w.POLICIES['P1'])
        self.assertAlmostEqual(s['saving'], 0.35 * 95000 * 1.25 * (1 - Q), places=6)

    def test_second_pass_only_removes_new_growth(self):
        t = trace([req(0, w5=10000), req(10, r=10000, w5=90000), req(410, r=10000, w5=95000),
                   req(420, r=105000, w5=1000), req(900, r=10000, w5=96000)])
        s = w.simulate(t, w.POLICIES['P1'])
        self.assertEqual(s['passes'], 2)
        self.assertAlmostEqual(s['removed'], 0.35 * 96000, places=6)

    def test_dup_requests_are_not_counted(self):
        t = self.cold()
        t['requests'][0]['dup'] = True
        self.assertEqual(w.simulate(t, w.POLICIES['P0'])['n'], 3)


class Parse(unittest.TestCase):
    def test_parse_and_cross_file_dedupe(self):
        def a(rid, ts, side=False, model='claude-x', **u):
            usage = dict(input_tokens=u.get('u', 1), cache_read_input_tokens=u.get('r', 0),
                         cache_creation_input_tokens=u.get('w', 0), output_tokens=5,
                         cache_creation=dict(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=u.get('w', 0)))
            return dict(type='assistant', requestId=rid, timestamp=ts, isSidechain=side,
                        message=dict(model=model, usage=usage, content=[{'type': 'text', 'text': 'secret'}]))
        b = dict(type='system', subtype='compact_boundary', uuid='b1', timestamp='2026-10-01T00:10:00Z',
                 compactMetadata=dict(trigger='manual', preTokens=900, postTokens=50))
        f1 = [a('A', '2026-10-01T00:00:00Z', w=100), a('A', '2026-10-01T00:00:05Z', w=100),
              a('S', '2026-10-01T00:00:06Z', side=True), a('Z', '2026-10-01T00:00:07Z', model='<synthetic>'), b,
              a('B', '2026-10-01T00:20:00Z', r=100)]
        f2 = [a('A', '2026-10-01T00:00:00Z', w=100), a('C', '2026-10-01T01:00:00Z', r=100)]
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'p'))
            for name, rows in (('p/one.jsonl', f1), ('p/two.jsonl', f2)):
                with open(os.path.join(d, name), 'w') as fh:
                    fh.write('\n'.join(json.dumps(x) for x in rows) + '\n')
            os.makedirs(os.path.join(d, 'p', 'subagents'))
            with open(os.path.join(d, 'p', 'subagents', 'agent.jsonl'), 'w') as fh:
                fh.write(json.dumps(a('X', '2026-10-01T02:00:00Z', side=True, w=7)) + '\n')
            traces = w.load(d)
        sub = [t for t in traces if t['subagent']]
        self.assertEqual([r['rid'] for t in sub for r in t['requests']], ['X'])
        traces = [t for t in traces if not t['subagent']]
        self.assertEqual(len(traces), 2)
        one = next(t for t in traces if t['boundaries'])
        self.assertEqual([r['rid'] for r in one['requests']], ['A', 'B'])
        self.assertEqual(one['requests'][0]['t1'] - one['requests'][0]['t0'], 5)
        self.assertEqual(one['requests'][0]['w1'], 100)
        self.assertEqual(one['boundaries'][0]['pre'], 900)
        two = next(t for t in traces if t is not one)
        self.assertEqual([r['dup'] for r in two['requests']], [True, False])
        self.assertNotIn('secret', json.dumps(traces))
        w.annotate(one)
        self.assertEqual([r['seg'] for r in one['requests']], [0, 1])
        self.assertTrue(one['requests'][1]['seg_start'])
        self.assertEqual(one['requests'][1]['ttl'], w.TTL1H)


if __name__ == '__main__':
    unittest.main()
