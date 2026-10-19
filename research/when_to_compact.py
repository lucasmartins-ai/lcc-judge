"""WHEN should LCC stash, relative to prompt-cache state? Offline study on Claude Code usage traces.

Protocol: research/when-to-compact-2026-10-19/WHEN_PROTOCOL.md (frozen before outcomes; hashes in WHEN_PROTOCOL.json).
Reads ONLY numeric / metadata fields of ~/.claude/projects/**/*.jsonl (requestId, timestamp, isSidechain, message.model,
message.usage, compact_boundary compactMetadata token counts and trigger). No message text is read into any structure,
nothing per-session is written to the repo. No network, no model calls.

    PYTHONPATH=.../lcc-main/src:$PWD ~/LCC/.venv/bin/python -m research.when_to_compact run
"""
import argparse
import glob
import json
import os
import random
import statistics
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'research' / 'when-to-compact-2026-10-19'
SEED, N_BOOT = 20261019, 2000
# Anthropic prompt-caching price multipliers on the base input price (5-minute write, 1-hour write, read).
PRICE = dict(uncached=1.0, read=0.10, w5=1.25, w1h=2.0)
TTL5, TTL1H = 300.0, 3600.0
# Reduction model from v5 cycle 2 (V5C2_RESULTS.md, stashed on 264 dev items):
RHO = 0.35          # median share of context tokens stashed removes in one pass
Q_RECALL = 4.57 / 19.0  # USED results stashed / results stashed per pass -> share of removed tokens recalled (pessimistic)
TOKENS_PER_USED = 8386129 / 264 / 4.57  # removed tokens per USED result stashed (expected removed-then-needed count)
MU = 0.03           # first mutation offset as a share of the message context (V5C2 median 0.02-0.03)
ACCEPT = dict(share_sessions_lower=0.70, ci_lower_gt=0.0)


# ---------------------------------------------------------------- parsing (metadata only)

def _ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def parse_file(path, sidechain=False):
    """One JSONL -> {'requests': [...], 'boundaries': [...]} using only numeric/metadata fields. Main-session files
    skip sidechain rows (older builds logged subagents inline); subagent files (sidechain=True) keep them."""
    reqs, order, bounds = {}, [], []
    with open(path, errors='ignore') as fh:
        for line in fh:
            if '"usage"' not in line and 'compact_boundary' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = d.get('timestamp')
            if not ts:
                continue
            if d.get('type') == 'system' and d.get('subtype') == 'compact_boundary':
                md = d.get('compactMetadata') or {}
                bounds.append(dict(uuid=d.get('uuid'), t=_ts(ts), trigger=md.get('trigger'),
                                   pre=int(md.get('preTokens') or 0), post=int(md.get('postTokens') or 0)))
                continue
            if d.get('type') != 'assistant' or bool(d.get('isSidechain')) != sidechain:
                continue
            m = d.get('message') or {}
            u = m.get('usage') or {}
            rid = d.get('requestId')
            if not rid or m.get('model') == '<synthetic>' or 'input_tokens' not in u:
                continue
            cc = u.get('cache_creation') or {}
            w = int(u.get('cache_creation_input_tokens') or 0)
            w1 = int(cc.get('ephemeral_1h_input_tokens') or 0)
            w5 = int(cc.get('ephemeral_5m_input_tokens') or 0)
            if w1 + w5 != w:  # split missing or inconsistent: count the remainder as 5-minute writes
                w5 = max(0, w - w1)
            t = _ts(ts)
            if rid not in reqs:
                order.append(rid)
                reqs[rid] = dict(rid=rid, t0=t, t1=t)
            r = reqs[rid]
            r.update(u=int(u.get('input_tokens') or 0), r=int(u.get('cache_read_input_tokens') or 0),
                     w5=w5, w1=w1, o=int(u.get('output_tokens') or 0))
            r['t0'], r['t1'] = min(r['t0'], t), max(r['t1'], t)
    out = sorted((reqs[k] for k in order), key=lambda r: r['t0'])
    return dict(requests=out, boundaries=bounds)


def load(root):
    """Traces with cross-file dedupe: a request (or boundary) already seen in an earlier file is kept for gap / context
    reconstruction but flagged dup and excluded from every count and cost."""
    files = glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True)
    parsed = []
    for f in files:
        sub = f'{os.sep}subagents{os.sep}' in f
        p = parse_file(f, sidechain=sub)
        if p['requests']:
            p['subagent'] = sub
            parsed.append(p)
    # copies made by resume / fork carry the original timestamps: ties go to the file that ends first (the original)
    parsed.sort(key=lambda p: (p['requests'][0]['t0'], p['requests'][-1]['t1']))
    seen_r, seen_b = set(), set()
    for p in parsed:
        for r in p['requests']:
            r['dup'] = r['rid'] in seen_r
            seen_r.add(r['rid'])
        for b in p['boundaries']:
            b['dup'] = b['uuid'] in seen_b
            seen_b.add(b['uuid'])
    return parsed


# ---------------------------------------------------------------- per-request cost model

def ctx(r):
    return r['u'] + r['r'] + r['w5'] + r['w1']


def cost(u, rd, w5, w1):
    return u * PRICE['uncached'] + rd * PRICE['read'] + w5 * PRICE['w5'] + w1 * PRICE['w1h']


def write_price(r, last_1h_share):
    w = r['w5'] + r['w1']
    s = r['w1'] / w if w else last_1h_share
    return s * PRICE['w1h'] + (1 - s) * PRICE['w5']


def annotate(trace):
    """Adds gap (s since the previous request ended), segment index (natural compaction boundaries), ttl (s, from the
    newest write's 5m/1h mix before this request) and seg_base (first context of the segment) to each request."""
    reqs = trace['requests']
    bts = sorted(b['t'] for b in trace['boundaries'])
    seg, bi, last_1h, base = 0, 0, 0.0, None
    for i, r in enumerate(reqs):
        new_seg = False
        while bi < len(bts) and bts[bi] <= r['t0']:
            bi += 1
            seg += 1
            new_seg = True
        r['gap'] = None if i == 0 else max(0.0, r['t0'] - reqs[i - 1]['t1'])
        r['ttl'] = TTL1H if last_1h >= 0.5 else TTL5
        r['last_1h'] = last_1h
        r['seg'] = seg
        if i == 0 or new_seg:
            base = ctx(r)
            r['seg_start'] = True
        else:
            r['seg_start'] = False
        r['seg_base'] = base
        w = r['w5'] + r['w1']
        if w:
            last_1h = r['w1'] / w
    return trace


# ---------------------------------------------------------------- policies

def trigger(policy, r, removable):
    """Does the policy stash right before request r? removable = new tokens a pass would remove now (gross)."""
    if r['seg_start'] or r['gap'] is None or removable <= 0:
        return False
    kind, thr = policy.get('kind'), policy.get('min_removable', 0)
    if removable < thr:
        return False
    if kind == 'P0' or kind == 'P2':  # P2: stashed never removes the newest outputs (preserve_recent) -> tail empty
        return False
    if kind == 'P1':
        return r['gap'] > r['ttl']
    if kind == 'P1_5m':
        return r['gap'] > TTL5
    if kind == 'warm':  # naive: stash as soon as removable >= threshold, whatever the cache state
        return True
    raise ValueError(kind)


def simulate(trace, policy, rho=RHO, q=Q_RECALL, mu=MU):
    """Cost of the trace's own (non-dup) requests under a policy. Returns dict with cost, base cost, mean context,
    passes, removed tokens, expected removed-then-needed results."""
    tot = base_tot = 0.0
    ctx_sum = ctx_base = 0.0
    n = passes = 0
    removed = 0.0
    seg, gross, net = None, 0.0, 0.0
    for r in trace['requests']:
        if r['seg'] != seg:
            seg, gross, net = r['seg'], 0.0, 0.0
        c = ctx(r)
        msg = max(0.0, c - r['seg_base'])
        new = rho * msg - gross
        b = cost(r['u'], r['r'], r['w5'], r['w1'])
        if trigger(policy, r, new):
            gross += new
            # the pass mutates the prefix at the first stashed output: system/tools + mu of the message context stay
            m = r['seg_base'] + mu * msg
            c2 = c - net - new
            rd = min(r['r'], m)
            u = min(r['u'], c2)
            w = max(0.0, c2 - rd - u)
            wp = write_price(r, r['last_1h'])
            x = u * PRICE['uncached'] + rd * PRICE['read'] + w * wp + q * new * wp  # + recalled tokens re-written once
            net += (1 - q) * new
            if not r['dup']:
                passes += 1
                removed += new
        else:
            c2 = c - net
            left = net
            rd = r['r'] - min(r['r'], left); left -= r['r'] - rd
            tw = r['w5'] + r['w1']
            w = tw - min(tw, left); left -= tw - w
            u = r['u'] - min(r['u'], left)
            s = (r['w1'] / tw) if tw else 0.0
            x = cost(u, rd, w * (1 - s), w * s)
        if r['dup']:
            continue
        n += 1
        tot += x
        base_tot += b
        ctx_sum += c2
        ctx_base += c
    return dict(n=n, cost=tot, base=base_tot, saving=base_tot - tot, ctx_mean=ctx_sum / n if n else 0.0,
                ctx_base_mean=ctx_base / n if n else 0.0, passes=passes, removed=removed,
                needed=removed / TOKENS_PER_USED)


POLICIES = {
    'P0': dict(kind='P0'),
    'P1': dict(kind='P1'),
    'P1_min10k': dict(kind='P1', min_removable=10000),
    'P1_min50k': dict(kind='P1', min_removable=50000),
    'P1_5m': dict(kind='P1_5m'),
    'P2': dict(kind='P2'),
    'warm_50k': dict(kind='warm', min_removable=50000),
}
CANDIDATES = ('P1', 'P1_min10k', 'P1_min50k', 'P1_5m')


# ---------------------------------------------------------------- stats

def quantiles(xs, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    if not xs:
        return {}
    s = sorted(xs)
    return {f'p{int(q * 100)}': s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))] for q in qs}


def boot_ci(xs, seed=SEED, n=N_BOOT):
    rng = random.Random(seed)
    k = len(xs)
    means = sorted(sum(xs[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return [means[int(0.025 * n)], means[int(0.975 * n) - 1]]


# ---------------------------------------------------------------- descriptive

def describe(traces):
    main = [t for t in traces if not t['subagent']]
    sub = [t for t in traces if t['subagent']]

    def mix(ts):
        w5 = sum(r['w5'] for t in ts for r in t['requests'] if not r['dup'])
        w1 = sum(r['w1'] for t in ts for r in t['requests'] if not r['dup'])
        rd = sum(r['r'] for t in ts for r in t['requests'] if not r['dup'])
        u = sum(r['u'] for t in ts for r in t['requests'] if not r['dup'])
        n = sum(1 for t in ts for r in t['requests'] if not r['dup'])
        return dict(requests=n, w5_tokens=w5, w1h_tokens=w1, share_1h_of_writes=w1 / (w1 + w5) if w1 + w5 else None,
                    read_tokens=rd, uncached_tokens=u, cost_base_eq=cost(u, rd, w5, w1),
                    write_share_of_cost=(w5 * PRICE['w5'] + w1 * PRICE['w1h']) / cost(u, rd, w5, w1) if n else None)

    gaps, post_gap = [], {'gt5m': [], 'gt1h': [], 'gt_ttl': []}
    for t in main:
        for r in t['requests']:
            if r['dup'] or r['gap'] is None or r['seg_start']:
                continue
            gaps.append(r['gap'])
            c = ctx(r)
            for key, lim in (('gt5m', TTL5), ('gt1h', TTL1H), ('gt_ttl', r['ttl'])):
                if r['gap'] > lim:
                    post_gap[key].append(dict(read_share=r['r'] / c if c else 0.0, w=r['w5'] + r['w1'],
                                              wcost=r['w5'] * PRICE['w5'] + r['w1'] * PRICE['w1h'], ctx=c))
    sessions_with = {k: sum(1 for t in main if any(not r['dup'] and r['gap'] is not None and not r['seg_start']
                                                     and r['gap'] > (lim if lim else r['ttl']) for r in t['requests']))
                     for k, lim in (('gt5m', TTL5), ('gt1h', TTL1H), ('gt_ttl', None))}
    total_cost = sum(cost(r['u'], r['r'], r['w5'], r['w1']) for t in main for r in t['requests'] if not r['dup'])

    def gap_block(rows):
        return dict(n=len(rows), cold_share=sum(1 for x in rows if x['read_share'] < 0.5) / len(rows) if rows else None,
                    rewrite_tokens=quantiles([x['w'] for x in rows]), rewrite_tokens_sum=sum(x['w'] for x in rows),
                    rewrite_cost_share_of_total=sum(x['wcost'] for x in rows) / total_cost if total_cost else None,
                    ctx=quantiles([x['ctx'] for x in rows]))

    comp = []
    for t in main:
        reqs = t['requests']
        for b in t['boundaries']:
            if b['dup']:
                continue
            before = [r for r in reqs if r['t1'] <= b['t']]
            after = [r for r in reqs if r['t0'] > b['t']]
            if not before:
                continue
            prev = before[-1]
            gap = b['t'] - prev['t1']
            first = after[0] if after else None
            pw = prev['w1'] + prev['w5']
            is_1h = (prev['w1'] > prev['w5']) if pw else prev['ttl'] == TTL1H
            wp = PRICE['w1h'] if is_1h else PRICE['w5']
            warm = gap <= (TTL1H if is_1h else TTL5)
            comp.append(dict(trigger=b['trigger'], gap=gap, ttl_1h=is_1h, cold=not warm, pre=b['pre'],
                             post=b['post'],
                             summarizer_input_cost=b['pre'] * (PRICE['read'] if warm else wp),
                             first_after_write=(first['w5'] + first['w1']) if first else None,
                             first_after_read=first['r'] if first else None,
                             first_after_cost=cost(first['u'], first['r'], first['w5'], first['w1']) if first else None))
    cdesc = dict(n=len(comp), triggers={k: sum(1 for c in comp if c['trigger'] == k) for k in ('auto', 'manual')},
                 cold_share=sum(c['cold'] for c in comp) / len(comp) if comp else None,
                 cold_share_5m_rule=sum(c['gap'] > TTL5 for c in comp) / len(comp) if comp else None,
                 ttl_1h_share=sum(c['ttl_1h'] for c in comp) / len(comp) if comp else None,
                 gap_s=quantiles([c['gap'] for c in comp]), pre_tokens=quantiles([c['pre'] for c in comp]),
                 post_tokens=quantiles([c['post'] for c in comp]),
                 first_after_write=quantiles([c['first_after_write'] for c in comp if c['first_after_write'] is not None]),
                 first_after_read=quantiles([c['first_after_read'] for c in comp if c['first_after_read'] is not None]),
                 summarizer_input_cost_est=quantiles([c['summarizer_input_cost'] for c in comp]),
                 compaction_cost_est_sum=sum(c['summarizer_input_cost'] + (c['first_after_cost'] or 0) for c in comp),
                 compaction_cost_share_of_total=(sum(c['summarizer_input_cost'] + (c['first_after_cost'] or 0)
                                                     for c in comp) / total_cost) if total_cost else None)
    return dict(
        sessions_main=sum(1 for t in main if any(not r['dup'] for r in t['requests'])),
        traces_subagent=len(sub),
        ttl_mix=dict(main=mix(main), subagent=mix(sub)),
        idle_gaps=dict(n=len(gaps), quantiles_s=quantiles(gaps),
                       share_gt_5m=sum(g > TTL5 for g in gaps) / len(gaps) if gaps else None,
                       share_gt_1h=sum(g > TTL1H for g in gaps) / len(gaps) if gaps else None,
                       sessions_with=sessions_with,
                       after_gap=dict((k, gap_block(v)) for k, v in post_gap.items())),
        compactions=cdesc,
        total_cost_base_eq=total_cost)


# ---------------------------------------------------------------- simulation table

def evaluate(traces, rho=RHO, q=Q_RECALL, mu=MU):
    main = [t for t in traces if not t['subagent'] and any(not r['dup'] for r in t['requests'])]
    base = [simulate(t, POLICIES['P0'], rho, q, mu) for t in main]
    res = {}
    for name, pol in POLICIES.items():
        rows = [simulate(t, pol, rho, q, mu) for t in main]
        sav = [r['saving'] for r in rows]
        touched = [r for r in rows if r['passes']]
        lower = sum(1 for r in touched if r['saving'] > 0)
        tot_base = sum(r['base'] for r in rows)
        res[name] = dict(
            sessions=len(rows), sessions_touched=len(touched),
            share_touched_lower=lower / len(touched) if touched else None,
            share_all_lower=lower / len(rows) if rows else None,
            mean_saving=statistics.fmean(sav), ci95=boot_ci(sav),
            total_saving_share=sum(sav) / tot_base if tot_base else 0.0,
            passes=sum(r['passes'] for r in rows), removed_tokens=sum(r['removed'] for r in rows),
            expected_needed_results=sum(r['needed'] for r in rows),
            ctx_mean_reduction=1 - (sum(r['ctx_mean'] * r['n'] for r in rows) /
                                    sum(r['ctx_base_mean'] * r['n'] for r in rows)) if rows else 0.0,
            needed_vs_P0=sum(r['needed'] for r in rows) - sum(r['needed'] for r in base))
        a = res[name]
        a['cost_gate'] = bool(a['share_touched_lower'] is not None and a['share_touched_lower'] >= ACCEPT['share_sessions_lower']
                              and a['ci95'][0] > ACCEPT['ci_lower_gt'])
        a['harm_gate'] = a['needed_vs_P0'] <= 0
    return res


def run(root, out):
    traces = [annotate(t) for t in load(root)]
    desc = describe(traces)
    primary = evaluate(traces)
    sens = {}
    for label, kw in (('rho0.15', dict(rho=0.15)), ('q0.5', dict(q=0.5)), ('mu0.10', dict(mu=0.10)),
                      ('rho0.15_q0.5', dict(rho=0.15, q=0.5))):
        sens[label] = {k: dict(mean_saving=v['mean_saving'], ci95=v['ci95'], share_touched_lower=v['share_touched_lower'],
                               cost_gate=v['cost_gate'], total_saving_share=v['total_saving_share'])
                       for k, v in evaluate(traces, **kw).items() if k in CANDIDATES + ('warm_50k',)}
    verdict = {k: dict(cost_gate=primary[k]['cost_gate'], harm_gate=primary[k]['harm_gate'],
                       recommended=primary[k]['cost_gate'] and primary[k]['harm_gate'],
                       conditional_opt_in=primary[k]['cost_gate'] and not primary[k]['harm_gate']
                       and all(s[k]['cost_gate'] for s in sens.values()))
               for k in CANDIDATES}
    doc = dict(schema='when-to-compact/results', protocol='WHEN_PROTOCOL.md', seed=SEED, n_boot=N_BOOT, price=PRICE,
               model=dict(rho=RHO, q_recall=Q_RECALL, tokens_per_used=TOKENS_PER_USED, mu=MU),
               descriptive=desc, simulation=primary, sensitivity=sens, verdict=verdict)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'when-results.json').write_text(json.dumps(doc, indent=1, default=float) + '\n')
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run'])
    ap.add_argument('--root', default=str(Path.home() / '.claude' / 'projects'))
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    doc = run(a.root, Path(a.out))
    print(json.dumps(dict(verdict=doc['verdict'], sessions=doc['descriptive']['sessions_main']), indent=1))


if __name__ == '__main__':
    main()
