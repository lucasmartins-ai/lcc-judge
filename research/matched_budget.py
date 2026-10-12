"""Matched-budget v1: every arm ranks the SAME candidate blocks of the frozen 60 real items, then each
arm drops its lowest-scored candidates until >= b% of candidate tokens are removed, b in BUDGETS. The
frozen v0 probes score what is left. Retention differences are then due to ranking, not to how much each
arm chose to drop.

Candidate set: LCC block mode on the pinned worktree splits the dossier text with split_blocks(MECH_KW)
and marks some blocks 'protected' in report.decisions (source == 'protected': blocks shorter than
min_block_chars). Block mode has no recent-turn protection (that is transcript mode). The saved
mechanical, specialist and jev_block runs have identical block ids and protected sets; the candidates
are all non-protected blocks. Protected blocks are always kept.

Arms (score: higher = keep; None = the arm could not score that block = kept until only unscored
candidates remain, which is what the arm does live):
    jev        saved runs/jev_block decision scores (v0.1, no new calls)
    specialist saved runs/specialist ranking logits (512-token window; longer blocks UNKNOWN -> None)
    laya       LCC provider='laya' run offline now (phase `laya`); oversized/failed blocks -> None
    mechanical saved runs/mechanical decision scores (lexical overlap)
    bm25       stdlib Okapi BM25 of the goal against the item's candidates
    recency    block index (newer = higher)
    random     seeded uniform, 5 seeds, retention averaged (floor)
Ties drop the older block first, for every arm.

Phases (PRIVATE text stays under PRIVATE; the repo gets counts only):
    laya    run Laya over the 60 dossiers -> PRIVATE/runs/laya_block/<id>.json + _meta.json (RSS)
    rss     peak RSS of the specialist on one median item -> PRIVATE/runs/specialist/_rss.json
    score   curves -> PRIVATE/matched-budget-v1.json and OUT/{curves.json,RESULTS.md}

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.matched_budget score
"""
import argparse
import json
import math
import os
import random
import re
import resource
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from research import real_context_bench as rcb

PRIVATE = rcb.PRIVATE
OUT = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'matched-budget-v1'
BUDGETS = (10, 20, 30, 40, 50, 60)
SEEDS = (0, 1, 2, 3, 4)
SAVED = {'jev': 'jev_block', 'specialist': 'specialist', 'mechanical': 'mechanical'}
ARMS = ('jev', 'specialist', 'laya', 'mechanical', 'bm25', 'recency', 'random')
SCORED = ('jev', 'specialist', 'laya', 'mechanical', 'bm25')  # arms whose scores can tie
LAYA_DIR = Path.home() / '.cache' / 'huggingface' / 'hub' / 'models--convaiinnovations--laya-multilingual'
ModernBERT = rcb.HF_HOME / 'hub' / 'models--answerdotai--ModernBERT-base'


def peak_rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1 << 20 if sys.platform == 'darwin' else 1 << 10), 1)  # bytes on macOS, KiB on Linux


# --- pure ranking / budget logic --------------------------------------------------------------------
def candidates(decisions):
    return [d['id'] for d in decisions if d['source'] != 'protected']


def saved_scores(arm, rec, cand):
    if arm == 'specialist':
        lg = {i['id']: i['logit'] for i in rec['specialist_ranking']['items'] if i['status'] == 'SCORED'}
        return {b: lg.get(b) for b in cand}
    # laya as LCC runs it live: a batch over Laya's window is scored mechanically by LCC itself; an
    # oversized single block ('fallback', kept fail-safe) stays unscored
    want = {'jev': ('jev',), 'mechanical': ('mechanical',), 'laya': ('laya', 'mechanical')}[arm]
    sc = {d['id']: d['score'] for d in rec['decisions'] if d['source'] in want}
    return {b: sc.get(b) for b in cand}


def tied_share(scores):
    c = Counter(v for v in scores.values() if v is not None)
    return sum(n for n in c.values() if n > 1)


TOKEN_RE = re.compile(r'\w+')


def bm25_scores(query, docs, k1=1.5, b=0.75):
    """docs: {id: text}. IDF over this item's candidates only."""
    toks = {i: [t.lower() for t in TOKEN_RE.findall(t)] for i, t in docs.items()}
    n = len(toks) or 1
    avg = sum(map(len, toks.values())) / n or 1
    df = Counter(t for ts in toks.values() for t in set(ts))
    q = [t.lower() for t in TOKEN_RE.findall(query)]
    out = {}
    for i, ts in toks.items():
        tf, s = Counter(ts), 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(ts) / avg))
        out[i] = s
    return out


def drop_order(cand, scores, tie=None):
    """Lowest score first; None (unscored) last; ties: older (earlier in cand) first, or by `tie` rank."""
    pos = tie or {b: i for i, b in enumerate(cand)}
    return sorted(cand, key=lambda b: (scores.get(b) is None, scores.get(b) or 0.0, pos[b]))


def drops_at(order, tokens, budget_pct):
    total = sum(tokens[b] for b in order)
    need, removed, out = total * budget_pct / 100, 0, set()
    for b in order:
        if removed >= need:
            break
        out.add(b)
        removed += tokens[b]
    return out, (removed / total if total else 0.0)


def auc(points):
    """points: [(budget_pct, rate)] incl. 0. Trapezoid area normalised to [0, 1] (= mean retention)."""
    pts = sorted(points)
    area = sum((x1 - x0) * (y0 + y1) / 2 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))
    return round(area / (pts[-1][0] - pts[0][0]), 4)


def item_curve(dossier, blocks, cand, scores, tokens, proto, tie=None):
    """{budget: (pass|None, removed_frac)} for one arm on one item (budget 0 included)."""
    order = drop_order(cand, scores, tie)
    res = {}
    for bud in (0,) + BUDGETS:
        dropped, frac = drops_at(order, tokens, bud)
        out = '\n\n'.join(t for bid, t in blocks if bid not in dropped)
        res[bud] = (rcb.score_item(dossier, dict(status='ok', output=out), proto)['item_pass'], frac)
    return res


# --- phases ---------------------------------------------------------------------------------------
def _setup():
    proto = rcb.load_protocol()
    sample = rcb.load_sample(PRIVATE, proto)
    os.environ.update(proto['privacy']['env'])
    rcb.check_lcc(proto)
    return proto, [it['id'] for it in sample['items']]


def laya_phase():
    from lcc.relevance import RelevanceCompactionRequest, compact_context
    from lcc.relevance.laya import LayaClient
    _, ids = _setup()
    out = PRIVATE / 'runs' / 'laya_block'
    out.mkdir(parents=True, exist_ok=True)
    base = peak_rss_mb()
    with rcb.network_guard():
        t0 = time.perf_counter()
        client = LayaClient(offline=True)
        client._ensure_agent()
        load_ms = round((time.perf_counter() - t0) * 1000)
        after_load = peak_rss_mb()
        for rid in ids:
            if (out / f'{rid}.json').exists() and 'cpu_ms' in json.loads((out / f'{rid}.json').read_text()):
                continue  # resumable; ponytail: per-item file is the checkpoint
            d = json.loads((PRIVATE / 'dossiers' / f'{rid}.json').read_text())
            t0, c0 = time.perf_counter(), time.process_time()
            res = compact_context(RelevanceCompactionRequest(text=d['text'], question=d['goal'], provider='laya',
                                                             client=client, **rcb.MECH_KW))
            rep = rcb._report(res)
            rec = dict(id=rid, latency_ms=round((time.perf_counter() - t0) * 1000),
                       cpu_ms=round((time.process_time() - c0) * 1000), load_avg_1m=os.getloadavg()[0], provider_used=rep['provider_used'],
                       degraded=rep['degraded'], calls=rep['calls'], decisions=rep['decisions'],
                       warnings=[re.sub(r'_\d+_', '_N_', w.split(':')[0]) for w in res.report.warnings])
            (out / f'{rid}.json').write_text(json.dumps(rec))
            print(rid, rec['latency_ms'], rec['provider_used'], flush=True)
    meta = dict(model=client.model, model_load_ms=load_ms, rss_mb_before_load=base, rss_mb_after_load=after_load,
                peak_rss_mb=peak_rss_mb(), guard_trips=rcb.GUARD['trips'])
    (out / '_meta.json').write_text(json.dumps(meta))
    return meta


def rss_phase():
    """Peak RSS of the specialist arm (same runner as v0) on the item with the median candidate count."""
    _, ids = _setup()
    os.environ['HF_HOME'] = str(rcb.HF_HOME)
    sizes = sorted((len(candidates(json.loads((PRIVATE / 'runs' / 'specialist' / f'{i}.json').read_text())['decisions'])), i)
                   for i in ids)
    rid = sizes[len(sizes) // 2][1]
    base = peak_rss_mb()
    with rcb.network_guard():
        runner, load_ms = rcb.make_runner('specialist')
        d = json.loads((PRIVATE / 'dossiers' / f'{rid}.json').read_text())
        t0 = time.perf_counter()
        runner(d['text'], d['goal'])
    meta = dict(item_candidates=sizes[len(sizes) // 2][0], latency_ms=round((time.perf_counter() - t0) * 1000),
                model_load_ms=load_ms, rss_mb_before_load=base, peak_rss_mb=peak_rss_mb(), guard_trips=rcb.GUARD['trips'])
    (PRIVATE / 'runs' / 'specialist' / '_rss.json').write_text(json.dumps(meta))
    return meta


def dir_mb(*paths):
    seen, total = set(), 0
    for p in paths:
        for root, _, files in os.walk(p):
            for f in files:
                real = os.path.realpath(os.path.join(root, f))
                if real not in seen and os.path.isfile(real):
                    seen.add(real)
                    total += os.path.getsize(real)
    return round(total / (1 << 20), 1)


def _load(arm, rid):
    p = PRIVATE / 'runs' / ('laya_block' if arm == 'laya' else SAVED[arm]) / f'{rid}.json'
    return json.loads(p.read_text())


def score_phase():
    proto, ids = _setup()
    count = lambda s: rcb.lcc_count(s)[0]  # noqa: E731
    from lcc.relevance.blocks import split_blocks
    per = {a: {} for a in ARMS[:-1]}
    per.update({f'random_s{s}': {} for s in SEEDS})
    per.update({f'{a}~tie{s}': {} for a in SCORED for s in SEEDS})
    ties = Counter()
    coverage, lat, usd, cand_sizes = Counter(), {a: [] for a in ARMS}, [], []
    for rid in ids:
        d = json.loads((PRIVATE / 'dossiers' / f'{rid}.json').read_text())
        blocks = [(b.id, b.text) for b in split_blocks(d['text'], min_block_chars=rcb.MECH_KW['min_block_chars'],
                                                        max_block_chars=rcb.MECH_KW['max_block_chars'])]
        recs = {a: _load(a, rid) for a in ('jev', 'specialist', 'mechanical', 'laya')}
        cand = candidates(recs['mechanical']['decisions'])
        if {b for b, _ in blocks} != {x['id'] for x in recs['mechanical']['decisions']}:
            raise SystemExit(f'{rid}: re-split block ids differ from the saved run')
        for a in ('jev', 'specialist', 'laya'):
            if candidates(recs[a]['decisions']) != cand:
                raise SystemExit(f'{rid}: {a} candidate set differs from mechanical')
        text = dict(blocks)
        tokens = {b: count(text[b]) for b in cand}
        cand_sizes.append(len(cand))
        scores = {a: saved_scores(a, recs[a], cand) for a in ('jev', 'specialist', 'laya', 'mechanical')}
        t0 = time.perf_counter()
        scores['bm25'] = bm25_scores(d['goal'], {b: text[b] for b in cand})
        lat['bm25'].append((time.perf_counter() - t0) * 1000)
        scores['recency'] = {b: i for i, b in enumerate(cand)}
        for s in SEEDS:
            rng = random.Random(f'{s}:{rid}')
            scores[f'random_s{s}'] = {b: rng.random() for b in cand}
        for a, sc in scores.items():
            coverage[a] += sum(v is not None for v in sc.values())
            per[a][rid] = item_curve(d, blocks, cand, sc, tokens, proto)
        for a in SCORED:
            ties[a] += tied_share(scores[a])
            for s in SEEDS:  # sensitivity: break ties at random instead of oldest-first
                rng = random.Random(f'tie{s}:{rid}')
                per[f'{a}~tie{s}'][rid] = item_curve(d, blocks, cand, scores[a], tokens, proto,
                                                     {b: rng.random() for b in cand})
        coverage['laya_native'] += sum(x['source'] == 'laya' for x in recs['laya']['decisions'])
        for a in ('jev', 'specialist', 'mechanical', 'laya'):
            lat[a].append(recs[a]['latency_ms'])
        usd.append(recs['jev']['jev_meter']['cost_usd'])
    n_cand = sum(cand_sizes)

    def curve(arm):
        rows = per[arm]
        out = {}
        for bud in (0,) + BUDGETS:
            vals = [r[bud][0] for r in rows.values() if r[bud][0] is not None]
            out[bud] = dict(k=sum(vals), n=len(vals), removed_median=round(statistics.median(r[bud][1] for r in rows.values()), 4))
        return out

    curves = {a: curve(a) for a in per}
    rnd = {}
    for bud in (0,) + BUDGETS:
        ks = [curves[f'random_s{s}'][bud]['k'] for s in SEEDS]
        rnd[bud] = dict(k=round(statistics.mean(ks), 2), n=curves['random_s0'][bud]['n'], seed_k=ks,
                        removed_median=round(statistics.median(curves[f'random_s{s}'][bud]['removed_median'] for s in SEEDS), 4))
    tie_random = {}
    for a in SCORED:
        tie_random[a] = {str(bud): round(statistics.mean(curves[f'{a}~tie{s}'][bud]['k'] for s in SEEDS)
                                         / curves[a][bud]['n'], 4) for bud in (0,) + BUDGETS}
        tie_random[a]['auc'] = auc([(int(b), v) for b, v in tie_random[a].items()])
    curves = {a: curves[a] for a in ARMS[:-1]} | {'random': rnd}
    for a, c in curves.items():
        for bud, v in c.items():
            v['rate'] = round(v['k'] / v['n'], 4)
            v['wilson95'] = list(rcb.wilson(round(v['k']), v['n']))
        c['auc'] = auc([(bud, v['rate']) for bud, v in c.items()])
    paired = {}
    for a in ARMS[:-1]:
        if a == 'jev':
            continue
        paired[a] = {bud: dict(
            arm_only=sum(1 for r in per[a] if per[a][r][bud][0] is True and per['jev'][r][bud][0] is False),
            jev_only=sum(1 for r in per[a] if per[a][r][bud][0] is False and per['jev'][r][bud][0] is True))
            for bud in BUDGETS}
    laya_meta = json.loads((PRIVATE / 'runs' / 'laya_block' / '_meta.json').read_text())
    spec_rss = json.loads((PRIVATE / 'runs' / 'specialist' / '_rss.json').read_text())
    q = lambda xs: dict(median=round(statistics.median(xs), 1), p90=round(rcb.quantile(xs, 0.9), 1))  # noqa: E731
    cost = dict(
        jev=dict(latency_ms=q(lat['jev']), peak_rss_mb=None, model_mb=None,
                 usd_per_item=dict(median=round(statistics.median(usd), 4), mean=round(statistics.mean(usd), 4),
                                   total=round(sum(usd), 2)), note='remote API; saved v0.1 ledger, serial requests'),
        specialist=dict(latency_ms=q(lat['specialist']), peak_rss_mb=spec_rss['peak_rss_mb'],
                        model_mb=dir_mb(rcb.SPECIALIST_HEAD, ModernBERT), usd_per_item=0,
                        model_load_ms=spec_rss['model_load_ms'],
                        note=f"RSS from one median item ({spec_rss['item_candidates']} candidates); CPU"),
        laya=dict(latency_ms=q(lat['laya']), peak_rss_mb=laya_meta['peak_rss_mb'], model_mb=dir_mb(LAYA_DIR),
                  usd_per_item=0, model_load_ms=laya_meta['model_load_ms'],
                  cpu_ms=q([_load('laya', r)['cpu_ms'] for r in ids]),
                  load_avg_1m_median=round(statistics.median(_load('laya', r)['load_avg_1m'] for r in ids), 1),
                  note=f"{laya_meta['model']}; device auto = Apple GPU (MPS) on this Mac; machine shared with other jobs ({os.cpu_count()} cores)"),
        mechanical=dict(latency_ms=q(lat['mechanical']), peak_rss_mb=None, model_mb=0, usd_per_item=0,
                        note='saved v0 latency (whole compact_context call)'),
        bm25=dict(latency_ms=q(lat['bm25']), peak_rss_mb=None, model_mb=0, usd_per_item=0,
                  note='scoring only, stdlib'),
        recency=dict(latency_ms=None, peak_rss_mb=None, model_mb=0, usd_per_item=0, note='no scoring'),
        random=dict(latency_ms=None, peak_rss_mb=None, model_mb=0, usd_per_item=0, note='no scoring'))
    laya_warn = Counter(w for rid in ids for w in _load('laya', rid)['warnings'])
    result = dict(schema='matched-budget/1', n_items=len(ids), budgets_pct=list(BUDGETS),
                  candidates=dict(blocks=n_cand, per_item_median=statistics.median(cand_sizes)),
                  coverage={a: round(coverage[a] / n_cand, 4) for a in ('jev', 'specialist', 'laya', 'laya_native', 'mechanical', 'bm25')},
                  tied_share={a: round(ties[a] / n_cand, 4) for a in SCORED},
                  tie_random_rates=tie_random,
                  laya_warning_kinds=dict(laya_warn), laya_guard_trips=laya_meta['guard_trips'],
                  curves={a: {str(k): v for k, v in c.items()} for a, c in curves.items()},
                  paired_vs_jev={a: {str(k): v for k, v in p.items()} for a, p in paired.items()}, cost=cost)
    (PRIVATE / 'matched-budget-v1.json').write_text(json.dumps(dict(result, per_item={
        a: {r: {str(b): v for b, v in c.items()} for r, c in per[a].items()} for a in per if '~' not in a}), indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'curves.json').write_text(json.dumps(result, indent=1) + '\n')
    (OUT / 'RESULTS.md').write_text(render_md(result))
    return result


def vs_jev_line(arm, curves, rate=lambda c, a, b: c[a][b]['rate']):
    parts = []
    for bud in BUDGETS:
        dlt = round((rate(curves, arm, str(bud)) - rate(curves, 'jev', str(bud))) * 100, 1)
        parts.append(f"{bud}%: {'+' if dlt > 0 else ''}{dlt} pt" + (' (tie)' if dlt == 0 else ''))
    d_auc = round((curves[arm]['auc'] - curves['jev']['auc']) * 100, 1)
    word = 'above' if d_auc > 0 else 'below' if d_auc < 0 else 'level with'
    return f"- **{arm}** is {word} Jev overall (AUC {d_auc:+} pt): " + '; '.join(parts) + '.'


def render_md(r):
    c, k = r['curves'], r['cost']
    rows = ['| arm | ' + ' | '.join(f'{b}%' for b in r['budgets_pct']) + ' | AUC |', '|---' * (len(r['budgets_pct']) + 2) + '|']
    for a in ARMS:
        cells = [f"{c[a][str(b)]['k']}/{c[a][str(b)]['n']} ({c[a][str(b)]['rate']:.2f}, {c[a][str(b)]['wilson95'][0]:.2f}-{c[a][str(b)]['wilson95'][1]:.2f})"
                 for b in r['budgets_pct']]
        rows.append(f'| {a} | ' + ' | '.join(cells) + f" | {c[a]['auc']:.3f} |")
    fmt = lambda v: '-' if v is None else str(v)  # noqa: E731
    cost_rows = ['| arm | latency median ms | latency p90 ms | peak RSS MB | model on disk MB | $ per item | note |',
                 '|---|---|---|---|---|---|---|']
    for a in ARMS:
        x = k[a]
        lat = x['latency_ms'] or {}
        usd = x['usd_per_item']
        usd = f"{usd['median']} median / {usd['mean']} mean" if isinstance(usd, dict) else usd
        note = x['note'] + (f"; model load {x['model_load_ms']} ms" if x.get('model_load_ms') else '')
        if x.get('cpu_ms'):
            note += (f"; process CPU time median {x['cpu_ms']['median']} ms / p90 {x['cpu_ms']['p90']} ms; "
                     f"1-min load average median {x['load_avg_1m_median']}")
        cost_rows.append(f"| {a} | {fmt(lat.get('median'))} | {fmt(lat.get('p90'))} | {fmt(x['peak_rss_mb'])} | "
                         f"{fmt(x['model_mb'])} | {usd} | {note} |")
    paired = [f"- {a}: " + '; '.join(f"{b}% +{v['arm_only']}/-{v['jev_only']}" for b, v in p.items())
              for a, p in r['paired_vs_jev'].items()]
    removed = '; '.join(f"{a} " + '/'.join(f"{c[a][str(b)]['removed_median']:.2f}" for b in r['budgets_pct']) for a in ARMS)
    return '\n'.join([
        '# Matched-budget v1: every arm ranks the same candidate blocks', '',
        '## Limits (read first)', '',
        f"- {r['n_items']} real items only; Wilson 95% intervals are wide (about +-12 pt at mid rates).",
        '- Probes are proxies (latest assistant turn, last tool result, task state, named refs, ...): they reward keeping '
        'recent blocks and do not measure whether an answer would actually be correct.',
        '- Jev scores are reused from the v0.1 run (no new calls); Jev saw the same blocks and goal.',
        '- Token counts are LCC heuristic (approximate:heuristic), not a real tokenizer.',
        '- Drop-only: no trimming, so arms differ only by ranking. Unscored blocks (specialist window 512, Laya '
        'single block over its window) are kept until only unscored candidates remain, as the arm would do live. Laya '
        'batches that overflow its 1024-token window are scored mechanically by LCC itself, so the laya arm is Laya as '
        'LCC runs it (laya_native = share Laya itself scored).',
        '- Ties drop the older block first for every arm. Random = mean of 5 seeds (k is a mean). A random '
        'tie-break sensitivity is reported below because it changes the mechanical arm a lot.',
        '- Latency is not like-for-like: Jev and specialist (CPU) come from their earlier saved runs; Laya ran now with '
        'LCC default device selection, which picks the Apple GPU (MPS) here, on a machine shared with other heavy jobs '
        '(browser GPU processes, load average shown below). Laya wall latency is not a clean CPU number; a CPU-only, '
        'idle-machine Laya timing is still missing.', '',
        '## Bottom line', '',
        f"- Recency alone (keep the newest blocks) has the best curve (AUC {c['recency']['auc']:.3f} vs Jev "
        f"{c['jev']['auc']:.3f}); these probes mostly check recent material, so this says more about the probes than "
        'about relevance. No arm in this table beats recency.',
        f"- With ties broken fairly (random), the only local ranker level with Jev is stdlib BM25 (AUC "
        f"{r['tie_random_rates']['bm25']['auc']:.3f} vs {r['tie_random_rates']['jev']['auc']:.3f}); Laya is "
        f"{(r['tie_random_rates']['jev']['auc'] - r['tie_random_rates']['laya']['auc']) * 100:.1f} pt below, the "
        f"LCC-judge specialist {(r['tie_random_rates']['jev']['auc'] - r['tie_random_rates']['specialist']['auc']) * 100:.1f} pt "
        f"below and under the random floor ({c['random']['auc']:.3f}).",
        '- Laya beats Jev only at the lightest budget (10%) and falls behind from 20% on.', '',
        '## Setup', '',
        f"- Candidates: {r['candidates']['blocks']} blocks (median {r['candidates']['per_item_median']} per item) = every "
        'block LCC block mode did not mark protected (protected = shorter than min_block_chars=40; block mode has no '
        'recent-turn protection). Same split (max_block_chars=6000) and same protected set in every saved run, checked per item.',
        "- Share of candidates each arm actually scored: " + ', '.join(f'{a} {v:.2f}' for a, v in r['coverage'].items()) + '.',
        f"- Laya warnings by kind: {r['laya_warning_kinds'] or 'none'}; network guard trips during the Laya run: {r['laya_guard_trips']}.",
        '- Budget b: drop lowest-scored candidates until >= b% of candidate tokens are removed. Median share actually '
        f"removed per arm (10..60%): {removed}.", '',
        '## Item retention k/n (rate, Wilson 95%) by budget', '', *rows, '',
        'AUC = area under retention vs budget from 0% to 60% (0% = nothing dropped), normalised to 0-1.', '',
        '## Tie sensitivity', '',
        'Share of candidates whose score equals another candidate\'s in the same item: '
        + ', '.join(f'{a} {v:.2f}' for a, v in r['tied_share'].items()) + '. Mechanical gives most blocks the same '
        'score (0.0), so its oldest-first tie-break makes it behave like recency. Same table, ties broken at random '
        '(mean of 5 seeds, rate):', '',
        '| arm | ' + ' | '.join(f'{b}%' for b in r['budgets_pct']) + ' | AUC |', '|---' * (len(r['budgets_pct']) + 2) + '|',
        *[f'| {a} | ' + ' | '.join(f"{t[str(b)]:.2f}" for b in r['budgets_pct']) + f" | {t['auc']:.3f} |"
          for a, t in r['tie_random_rates'].items()], '',
        '## Against Jev, in plain words', '',
        'Main table (ties oldest-first):', '',
        *[vs_jev_line(a, c) for a in ARMS if a != 'jev'], '',
        'Ties broken at random (Jev also re-broken at random):', '',
        *[vs_jev_line(a, r['tie_random_rates'], lambda c, x, b: c[x][b]) for a in SCORED if a != 'jev'], '',
        'Paired items vs Jev per budget (+items only this arm keeps / -items only Jev keeps):', '', *paired, '',
        '## Cost per item', '', *cost_rows, '',
        'Latency is the whole compaction call per item from each arm\'s own run (Jev: serial HTTP, concurrency 1). '
        'Peak RSS is the process maximum (includes Python + the loaded model). Model size counts weights, tokenizer and '
        'config on disk. Jev $ is the API-reported usage from the saved ledger.', ''])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('laya', 'rss', 'score'))
    a = ap.parse_args(argv)
    res = dict(laya=laya_phase, rss=rss_phase, score=score_phase)[a.phase]()
    print(json.dumps({k: v for k, v in res.items() if k not in ('curves', 'paired_vs_jev')}, indent=1))


if __name__ == '__main__':
    main()
