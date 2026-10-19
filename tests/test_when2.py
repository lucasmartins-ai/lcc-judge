"""when2 (keep-warm / handoff) on synthetic traces only (no private data)."""
import unittest

from research import when2 as w2
from research import when_to_compact as w

Q = w.Q_RECALL
PING = 0.1 * 100000 + w2.PING_EXTRA  # one ping on a 100k prefix


def req(t, u=0, r=0, w5=0, w1=0, rid=None):
    return dict(rid=rid or f'r{t}', t0=float(t), t1=float(t), u=u, r=r, w5=w5, w1=w1, o=0, dup=False)


def trace(reqs, bounds=()):
    return w.annotate(dict(requests=list(reqs), boundaries=[dict(t=float(b), dup=False) for b in bounds],
                           subagent=False))


def idle(gap, tail=()):
    """1-hour TTL session: 100k prefix, then a return after `gap` seconds that re-writes 95k (cold in the trace)."""
    return trace([req(0, w1=10000), req(10, r=10000, w1=90000), req(10 + gap, r=10000, w1=95000)] + list(tail))


def sim(t, name, ends=frozenset(), **kw):
    return w2.simulate2(t, w2.POLICIES[name], ends, **kw)


class KeepWarm(unittest.TestCase):
    def test_pings_counted_while_user_is_away(self):
        self.assertEqual(w2.n_pings(float('inf'), 3300, 4), 4)
        self.assertEqual(w2.n_pings(3300, 3300, 1), 0)
        self.assertEqual(w2.n_pings(9000, 3300, 4), 2)

    def test_rescued_return_reads_instead_of_rewriting(self):
        s = sim(idle(5400), 'P4_K1')
        # actual 0.1*10k + 2.0*95k; warm: 0.1*100k + 2.0*5k; minus one ping
        self.assertAlmostEqual(s['saving'], 191000 - 20000 - PING, places=6)
        self.assertEqual((s['pings'], s['rescues'], s['ping_episodes']), (1, 1, 1))

    def test_ping_wasted_when_back_before_expiry_or_after_window(self):
        self.assertAlmostEqual(sim(idle(3420), 'P4_K1')['saving'], -PING, places=6)
        self.assertAlmostEqual(sim(idle(9000), 'P4_K1')['saving'], -PING, places=6)
        self.assertAlmostEqual(sim(idle(9000), 'P4_K2')['saving'], 171000 - 2 * PING, places=6)

    def test_session_end_pays_every_ping(self):
        t = idle(5400)
        ends = {t['requests'][-1]['rid']}
        s = sim(t, 'P4_K2', ends)
        end_ping = 0.1 * 105000 + w2.PING_EXTRA
        self.assertAlmostEqual(s['saving'], 171000 - PING - 2 * end_ping, places=6)
        self.assertEqual(s['ping_episodes'], 2)

    def test_p1_matches_frozen_study_and_combo_adds_pings(self):
        for t in (idle(4000), idle(5400, tail=[req(5420, r=105000, w1=1000)]),
                  trace([req(0, w5=10000), req(10, r=10000, w5=90000), req(410, r=10000, w5=95000),
                         req(420, r=105000, w5=1000), req(900, r=10000, w5=96000)])):
            self.assertAlmostEqual(sim(t, 'P1')['saving'], w.simulate(t, w.POLICIES['P1'])['saving'], places=6)
        # gap beyond the K=1 window: P1 still fires, plus a wasted ping
        self.assertAlmostEqual(sim(idle(9000), 'P1+P4_K1')['saving'], 66500 * (1 - Q) - PING, places=6)
        # gap inside the window: kept warm, P1 does not fire
        s = sim(idle(5400), 'P1+P4_K1')
        self.assertEqual(s['passes'], 0)
        self.assertAlmostEqual(s['saving'], 191000 - 20000 - PING, places=6)


class Handoff(unittest.TestCase):
    def t(self):
        return idle(5400, tail=[req(5420, r=105000, w1=1000)])

    def test_handoff_cost_cold_generation(self):
        s = sim(self.t(), 'P5')
        h = w2.H
        gen = 105000 * 1.0 + 5.0 * h
        trig = 0.1 * 10000 + 2.0 * h  # b0 = 10k read, handoff written at 2.0
        later = 12500 - (0.1 * (105000 - (105000 - 10000 - h)) + 2000)
        self.assertEqual(s['handoffs'], 1)
        self.assertAlmostEqual(s['saving'], 191000 - gen - trig + later, places=6)
        self.assertAlmostEqual(s['dropped'], 105000 - 10000 - h, places=6)

    def test_local_generation_and_small_context_skip(self):
        s = sim(self.t(), 'P5', gen='local')
        h = w2.H
        self.assertAlmostEqual(s['saving'], 191000 - (1000 + 2.0 * h) + 12500 - (0.1 * (10000 + h) + 2000), places=6)
        small = trace([req(0, w1=10000), req(10, r=10000, w1=40000), req(5410, r=10000, w1=45000)])
        self.assertEqual(sim(small, 'P5')['handoffs'], 0)  # drop < 50k

    def test_p1_p5_prefers_handoff_when_large(self):
        s = sim(self.t(), 'P1+P5')
        self.assertEqual((s['handoffs'], s['passes']), (1, 0))


class Episodes(unittest.TestCase):
    def test_end_ok_skips_resumed_and_censored(self):
        a = idle(5400)
        b = trace([dict(req(10 + 5400), rid=a['requests'][-1]['rid'], dup=True), req(30000, r=10, w1=10)])
        late = trace([req(31000, w1=5), req(31010, r=5, w1=5)])
        ends = w2.end_ok([a, b, late])
        self.assertEqual(ends, set())  # a's last is followed in b; b's and late's ends are inside CENSOR
        far = trace([req(100000, w1=5)])
        self.assertEqual(w2.end_ok([a, b, far]), {b['requests'][-1]['rid']})

    def test_describe_bins_and_break_even(self):
        ts = [idle(5400), idle(3420), idle(20000)]
        ends = {ts[0]['requests'][-1]['rid']}
        d = w2.describe2(ts, ends)
        bins = d['idle_gt_55m']['bins']
        self.assertEqual(bins['(55m,60m] warm anyway'], 1)
        self.assertEqual(bins['(0D+T, 1D+T] rescued by ping 1'], 1)
        self.assertEqual(bins['later than 4D+T (returned)'], 1)
        self.assertEqual(bins['never (session end)'], 1)
        self.assertAlmostEqual(d['break_even_return_prob_analytic'], 0.1 / 1.9)
        self.assertEqual(d['marginal_ping_rescue']['ping1'], dict(fired=4, rescued=1, p=0.25))


if __name__ == '__main__':
    unittest.main()
