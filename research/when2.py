"""When-to-compact, part 2: keep-warm pings (P4) and fresh-session handoff (P5) for the idle-return cache problem.

Protocol: research/when-to-compact-2026-10-19/WHEN2_PROTOCOL.md (frozen before outcomes; hashes in WHEN2_PROTOCOL.json).
Reuses the frozen parser, annotator and cost model of research/when_to_compact.py (not modified). Reads only numeric /
metadata fields of ~/.claude/projects/**/*.jsonl. Writes aggregates only. No network, no model calls.

    PYTHONPATH=.../lcc-main/src:$PWD ~/LCC/.venv/bin/python -m research.when2 run
"""
import argparse
import json
from pathlib import Path

import numpy as np

from research import when_to_compact as w

OUT = w.OUT
PRICE = w.PRICE
PRICE_OUT = 5.0           # output price / base input price (INFERIDO: current Claude price sheets are 5x)
PING_FRAC = 55 / 60       # a ping fires at 55 min of a 1-hour TTL (4.58 min of a 5-minute TTL)
PING_EXTRA = 10 * PRICE['uncached'] + 1 * PRICE_OUT  # ~10 new prompt tokens + max_tokens=1, besides the prefix read
PING_EXTRA_TURN = 5000.0  # sensitivity: the ping is a real Claude Code turn (~2k written at 2.0 + ~200 output at 5.0)
H = 15696                 # handoff size = median postTokens of natural compactions (when-results.json, MEDIDO)
P5_MIN_DROP = 50000       # P5 fires only if the handoff drops >= 50k tokens
CENSOR = 4 * PING_FRAC * w.TTL1H + w.TTL1H  # end-episodes this close to the data end are censored (not charged)
GEN = ('cold', 'native', 'local', 'prebuilt')


def n_pings(g, d, k):
    """Pings fired before a return after gap g (inf = never returned): ping j at j*d while the user is still away."""
    return sum(1 for j in range(1, k + 1) if j * d < g)


def ttl_after(r):
    tw = r['w5'] + r['w1']
    s = r['w1'] / tw if tw else r['last_1h']
    return w.TTL1H if s >= 0.5 else w.TTL5


def end_ok(traces):
    """rid -> True for the last request of a trace that is not a dup, is never followed by a request in any trace
    (resume copies continue elsewhere), and ended more than CENSOR seconds before the data end."""
    followed = {r['rid'] for t in traces for r in t['requests'][:-1]}
    t_end = max(r['t1'] for t in traces for r in t['requests'])
    ok = set()
    for t in traces:
        last = t['requests'][-1]
        if not last['dup'] and last['rid'] not in followed and last['t1'] < t_end - CENSOR:
            ok.add(last['rid'])
    return ok


def warm_parts(r, prev_ctx):
    """Usage of request r had the cache still held the previous request's prefix (trace terms)."""
    c = w.ctx(r)
    rd = max(r['r'], min(prev_ctx, c - r['u']))
    tw = c - r['u'] - rd
    ow = r['w5'] + r['w1']
    s = r['w1'] / ow if ow else r['last_1h']
    return r['u'], rd, tw * (1 - s), tw * s


def deduct(u, rd, w5, w1, net):
    """Take a net removal off reads first, then writes, then uncached (the frozen study's conservative order)."""
    left = net
    rd2 = rd - min(rd, left); left -= rd - rd2
    tw = w5 + w1
    tw2 = tw - min(tw, left); left -= tw - tw2
    u2 = u - min(u, left)
    s = w1 / tw if tw else 0.0
    return u2, rd2, tw2 * (1 - s), tw2 * s


def simulate2(trace, pol, ends, rho=w.RHO, q=w.Q_RECALL, mu=w.MU, ping_extra=PING_EXTRA, h=H, gen='cold',
              frac=PING_FRAC):
    """Cost of the trace's own (non-dup) requests plus policy overheads (pings, handoff generation).
    pol: dict(K=pings per idle episode, p1=stash on cold return, p5=handoff on cold return)."""
    reqs = trace['requests']
    k, p1, p5 = pol.get('K', 0), pol.get('p1', False), pol.get('p5', False)
    b0 = w.ctx(reqs[0])
    st = dict(cost=0.0, base=0.0, n=0, pings=0, ping_episodes=0, rescues=0, passes=0, handoffs=0, removed=0.0,
              dropped=0.0, overhead=0.0, ctx=0.0, ctx_base=0.0)
    seg, anchor, keep, gross, net = None, 0.0, 0.0, 0.0, 0.0
    prev_c2 = 0.0
    for i, r in enumerate(reqs):
        if r['seg'] != seg:
            seg, anchor, keep, gross, net = r['seg'], r['seg_base'], r['seg_base'], 0.0, 0.0
        c = w.ctx(r)
        b = w.cost(r['u'], r['r'], r['w5'], r['w1'])
        over, kept, cold, nk, pre = 0.0, False, False, 0, False
        g = r['gap']
        if g is not None:
            ttl = r['ttl']
            d = frac * ttl
            nk = n_pings(g, d, k)
            over += nk * (PRICE['read'] * prev_c2 + ping_extra)
            kept = nk > 0 and ttl < g <= nk * d + ttl
            cold = g > ttl and not kept
            if p5 and gen == 'prebuilt' and g > (k + 1) * d and prev_c2 - (b0 + h) >= P5_MIN_DROP:
                over += PRICE['read'] * prev_c2 + PRICE_OUT * h
                pre = True
        wp = w.write_price(r, r['last_1h'])
        cur = c - net
        if p5 and cold and not r['seg_start'] and cur - (b0 + h) >= P5_MIN_DROP and (gen != 'prebuilt' or pre):
            c2 = b0 + h
            over += {'cold': cur * PRICE['uncached'], 'native': cur * wp, 'local': 0.0, 'prebuilt': 0.0}[gen]
            over += 0.0 if gen in ('local', 'prebuilt') else PRICE_OUT * h
            rd = min(r['r'], b0)  # system / tools may still be cached from other sessions; the rest is new
            u = min(r['u'], c2)
            x = u * PRICE['uncached'] + rd * PRICE['read'] + max(0.0, c2 - rd - u) * wp
            if not r['dup']:
                st['handoffs'] += 1
                st['dropped'] += cur - c2
            anchor, keep, gross, net = c, c2, 0.0, c - c2
        elif p1 and cold and not r['seg_start'] and rho * max(0.0, c - anchor) - gross > 0:
            msg = max(0.0, c - anchor)
            new = rho * msg - gross
            m = keep + mu * msg
            c2 = c - net - new
            rd = min(r['r'], m)
            u = min(r['u'], c2)
            x = u * PRICE['uncached'] + rd * PRICE['read'] + max(0.0, c2 - rd - u) * wp + q * new * wp
            gross += new
            net += (1 - q) * new
            if not r['dup']:
                st['passes'] += 1
                st['removed'] += new
        else:
            parts = warm_parts(r, w.ctx(reqs[i - 1])) if kept and not r['seg_start'] else (r['u'], r['r'], r['w5'], r['w1'])
            x = w.cost(*deduct(*parts, net))
            c2 = c - net
        prev_c2 = c2
        if r['dup']:
            continue
        st['n'] += 1
        st['cost'] += x + over
        st['base'] += b
        st['overhead'] += over
        st['pings'] += nk
        st['ping_episodes'] += nk > 0
        st['rescues'] += kept
        st['ctx'] += c2
        st['ctx_base'] += c
    last = reqs[-1]
    if last['rid'] in ends:  # the user never came back to this prefix: every ping (and a prebuilt handoff) is wasted
        over = k *(PRICE['read'] * prev_c2 + ping_extra)
        if p5 and gen == 'prebuilt' and prev_c2 - (b0 + h) >= P5_MIN_DROP:
            over += PRICE['read'] * prev_c2 + PRICE_OUT * h
        st['cost'] += over
        st['overhead'] += over
        st['pings'] += k
        st['ping_episodes'] += k > 0
    st['saving'] = st['base'] - st['cost']
    st['needed'] = st['removed'] / w.TOKENS_PER_USED
    return st


POLICIES = {'P0': {}, 'P1': dict(p1=True)}
for _k in (1, 2, 4):
    POLICIES[f'P4_K{_k}'] = dict(K=_k)
POLICIES['P5'] = dict(p5=True)
for _k in (1, 2, 4):
    POLICIES[f'P1+P4_K{_k}'] = dict(K=_k, p1=True)
POLICIES['P1+P5'] = dict(p1=True, p5=True)
for _k in (1, 2, 4):  # exploratory: all three levers
    POLICIES[f'P1+P4_K{_k}+P5'] = dict(K=_k, p1=True, p5=True)

SENS = {
    'ping_turn': dict(ping_extra=PING_EXTRA_TURN),
    'lead50': dict(frac=50 / 60),
    'H30k': dict(h=30000),
    'gen_native': dict(gen='native'),
    'gen_local': dict(gen='local'),
    'gen_prebuilt': dict(gen='prebuilt'),
    'rho0.15_q0.5': dict(rho=0.15, q=0.5),
}
ACCEPT = dict(share_touched_lower=0.70, ci_lower_gt=0.0)


# ---------------------------------------------------------------- stats (paired session bootstrap)

def _idx(n):
    return np.random.default_rng(w.SEED).integers(0, n, size=(w.N_BOOT, n))


def ci(idx, xs):
    m = np.sort(np.asarray(xs, float)[idx].mean(axis=1))
    return [float(m[int(0.025 * w.N_BOOT)]), float(m[int(0.975 * w.N_BOOT) - 1])]


def ci_ratio(idx, num, den):
    nu, de = np.asarray(num, float)[idx].sum(axis=1), np.asarray(den, float)[idx].sum(axis=1)
    m = np.sort(nu / np.maximum(de, 1))
    return [float(m[int(0.025 * w.N_BOOT)]), float(m[int(0.975 * w.N_BOOT) - 1])]


# ---------------------------------------------------------------- return-gap distribution and break-even

def describe2(main, ends, frac=PING_FRAC, ping_extra=PING_EXTRA):
    """Idle episodes = gap before a non-dup, non-segment-start request, plus uncensored session ends (gap = inf)."""
    eps = []
    for t in main:
        reqs = t['requests']
        for i, r in enumerate(reqs):
            if r['dup'] or r['gap'] is None or r['seg_start']:
                continue
            p = reqs[i - 1]
            ben = 0.0
            if r['gap'] > r['ttl']:
                ben = w.cost(r['u'], r['r'], r['w5'], r['w1']) - w.cost(*warm_parts(r, w.ctx(p)))
            eps.append(dict(g=r['gap'], ttl=r['ttl'], pc=w.ctx(p), ben=ben))
        if reqs[-1]['rid'] in ends:
            eps.append(dict(g=float('inf'), ttl=ttl_after(reqs[-1]), pc=w.ctx(reqs[-1]), ben=0.0))
    one_h = [e for e in eps if e['ttl'] == w.TTL1H]
    d = frac * w.TTL1H
    idle = [e for e in one_h if e['g'] > d]  # a first ping would fire
    bins = [('(55m,60m] warm anyway', d, w.TTL1H)] + [
        (f'({j - 1}D+T, {j}D+T] rescued by ping {j}', (j - 1) * d + w.TTL1H, j * d + w.TTL1H) for j in (1, 2, 3, 4)]
    dist = {name: sum(1 for e in idle if lo < e['g'] <= hi) for name, lo, hi in bins}
    dist['later than 4D+T (returned)'] = sum(1 for e in idle if 4 * d + w.TTL1H < e['g'] < float('inf'))
    dist['never (session end)'] = sum(1 for e in idle if e['g'] == float('inf'))
    ping_cost = [PRICE['read'] * e['pc'] + ping_extra for e in idle]
    bens = [e['ben'] for e in one_h if w.TTL1H < e['g'] < float('inf')]
    p_star = (sum(ping_cost) / len(ping_cost)) / (sum(bens) / len(bens)) if bens and ping_cost else None
    # per-episode ratio: a ping pays when P(rescue) > 0.1 * prefix / (benefit of a warm return); ratio of means above
    hazard = {}
    for j in (1, 2, 3, 4):
        fired = [e for e in idle if e['g'] > j * d]
        hit = [e for e in fired if (j - 1) * d + w.TTL1H < e['g'] <= j * d + w.TTL1H]
        hazard[f'ping{j}'] = dict(fired=len(fired), rescued=len(hit), p=len(hit) / len(fired) if fired else None)
    gaps_5m = [e['g'] for e in eps if 300 < e['g'] < float('inf')]
    return dict(
        episodes=len(eps), session_ends=sum(1 for e in eps if e['g'] == float('inf')),
        episodes_ttl_1h=len(one_h), episodes_ttl_5m=len(eps) - len(one_h),
        returned_gap_gt_5m_quantiles_s=w.quantiles(gaps_5m),
        returned_gap_gt_1h_quantiles_s=w.quantiles([g for g in gaps_5m if g > w.TTL1H]),
        idle_gt_55m=dict(n=len(idle), bins=dist, shares={k: v / len(idle) for k, v in dist.items()} if idle else {}),
        marginal_ping_rescue=hazard,
        ping_cost_mean=sum(ping_cost) / len(ping_cost) if ping_cost else None,
        warm_return_benefit=dict(n=len(bens), mean=sum(bens) / len(bens) if bens else None,
                                 quantiles=w.quantiles(bens)),
        break_even_return_prob_empirical=p_star,
        break_even_return_prob_analytic=PRICE['read'] / (PRICE['w1h'] - PRICE['read']))


# ---------------------------------------------------------------- evaluation

def evaluate2(main, ends, idx, **kw):
    rows = {name: [simulate2(t, pol, ends, **kw) for t in main] for name, pol in POLICIES.items()}
    res = {}
    for name, rs in rows.items():
        sav = [r['saving'] for r in rs]
        touched = [r for r in rs if r['pings'] or r['passes'] or r['handoffs']]
        lower = sum(1 for r in touched if r['saving'] > 0)
        tot_base = sum(r['base'] for r in rs)
        eps = [r['ping_episodes'] for r in rs]
        a = dict(sessions=len(rs), sessions_touched=len(touched),
                 share_touched_lower=lower / len(touched) if touched else None,
                 mean_saving=float(np.mean(sav)), ci95=ci(idx, sav),
                 total_saving_share=sum(sav) / tot_base if tot_base else 0.0,
                 pings=sum(r['pings'] for r in rs), ping_episodes=sum(eps), rescues=sum(r['rescues'] for r in rs),
                 passes=sum(r['passes'] for r in rs), handoffs=sum(r['handoffs'] for r in rs),
                 overhead_share=sum(r['overhead'] for r in rs) / tot_base if tot_base else 0.0,
                 expected_needed_results=sum(r['needed'] for r in rs),
                 handoff_dropped_tokens=sum(r['dropped'] for r in rs),
                 ctx_mean_reduction=1 - sum(r['ctx'] for r in rs) / sum(r['ctx_base'] for r in rs))
        if sum(eps):
            a['saving_per_ping_episode'] = sum(sav) / sum(eps)
            a['saving_per_ping_episode_ci95'] = ci_ratio(idx, sav, eps)
        if name != 'P1':
            diff = [x - y['saving'] for x, y in zip(sav, rows['P1'])]
            a['vs_P1_mean'] = float(np.mean(diff))
            a['vs_P1_ci95'] = ci(idx, diff)
        a['cost_gate'] = bool(a['share_touched_lower'] is not None and
                              a['share_touched_lower'] >= ACCEPT['share_touched_lower'] and
                              a['ci95'][0] > ACCEPT['ci_lower_gt'])
        res[name] = a
    return res


def verdicts(primary, sens):
    out = {}
    for name in POLICIES:
        if name == 'P0':
            continue
        p = primary[name]
        robust = p['cost_gate'] and all(s[name]['cost_gate'] for s in sens.values())
        beats_p1 = name != 'P1' and p['vs_P1_ci95'][0] > 0
        if 'P5' in name:
            v = 'cost_only_candidate' if robust else 'not_recommended'  # handoff quality unmeasured
        elif 'P1' in name:
            v = 'conditional_opt_in' if robust else 'not_recommended'  # inherits P1's harm-gate failure
        else:
            v = 'recommended_cost_side' if robust else 'not_recommended'  # P4 removes nothing
        out[name] = dict(cost_gate=p['cost_gate'], robust_all_sensitivities=robust, beats_P1=beats_p1, verdict=v)
    return out


def run(root, out):
    traces = [w.annotate(t) for t in w.load(root)]
    ends = end_ok(traces)
    main = [t for t in traces if not t['subagent'] and any(not r['dup'] for r in t['requests'])]
    idx = _idx(len(main))
    desc = describe2(main, ends)
    primary = evaluate2(main, ends, idx)
    sens = {}
    for label, kw in SENS.items():
        sens[label] = {k: {f: v[f] for f in ('mean_saving', 'ci95', 'share_touched_lower', 'cost_gate',
                                              'total_saving_share') + (('vs_P1_ci95',) if 'vs_P1_ci95' in v else ())}
                       for k, v in evaluate2(main, ends, idx, **kw).items() if k != 'P0'}
    doc = dict(schema='when-to-compact/part2-results', protocol='WHEN2_PROTOCOL.md', seed=w.SEED, n_boot=w.N_BOOT,
               price=dict(PRICE, output=PRICE_OUT), params=dict(ping_frac=PING_FRAC, ping_extra=PING_EXTRA, H=H,
                                                                 p5_min_drop=P5_MIN_DROP, censor_s=CENSOR),
               sessions=len(main), descriptive=desc, simulation=primary, sensitivity=sens,
               verdict=verdicts(primary, sens))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'when2-results.json').write_text(json.dumps(doc, indent=1, default=float) + '\n')
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run'])
    ap.add_argument('--root', default=str(Path.home() / '.claude' / 'projects'))
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    doc = run(a.root, Path(a.out))
    print(json.dumps(dict(sessions=doc['sessions'], verdict=doc['verdict']), indent=1))


if __name__ == '__main__':
    main()
