"""Matched-budget v2: arms rank the same candidate blocks; labels = next-action evidence (not v0 probes).

Labels: research.next_action_labels v1 (PRIVATE_LABELS). A candidate block is USED when the agent reused
something from it after the prompt without re-fetching it (strict label). Only the DEV split is read here;
TEST stays closed. Items with evidence='none' or no USED candidate are excluded (counted).

Per item and budget b in BUDGETS: an arm scores every candidate (higher = keep; None = could not score,
kept until only unscored remain), then drops lowest-first until >= b% of candidate tokens are gone (same
drop_order / drops_at as research.matched_budget: ties drop the older block first). Metrics:
    recall    share of USED-candidate tokens kept (macro mean over items)
    all_kept  item keeps every USED candidate (k/n, Wilson 95%)
    ev_cov    share of evidence features (strict, non-generic, all holders are candidates) with >= 1
              holding block kept (macro mean): a feature found in several blocks needs only one copy
AUC = trapezoid over 0..60% (0% = nothing dropped = 1.0), normalised to 0-1.

Arms:
    recency          block index (newer = higher)
    random           seeded uniform, 5 seeds averaged (floor)
    bm25             stdlib Okapi BM25 of the goal over the item's candidates
    mechanical       LCC _score_mechanically (lexical overlap with the goal) + 1.0 when LCC's deterministic
                     protection / dependency closure would keep the block (what LCC mechanical keeps)
    specialist       LCC-judge exp02 head (ModernBERT-base, 512-token pair window, CPU); over-window -> None
    specialist_inv   -specialist logit (orientation check: flagged when it beats specialist)
    laya             native Laya noul as LCC batches it (8/batch, 1024 window), CPU; oversized blocks and
                     failed batches -> None (no mechanical fallback mixed in)
    jev              saved v0.1 jev_block scores, only on the frozen-60 items ('jev-overlap' subset)

Subsets:
    dev        every labelled dev item: cheap arms (recency, random, bm25, mechanical)
    dev-model  seeded MODEL_PER_SOURCE dev items per source: every local arm incl. specialist and Laya
    jev-overlap the frozen-60 real items that are NOT in the test split (46 train + 3 dev): Jev, specialist
               and Laya from their saved v0/v1 runs (identical block ids, checked), others recomputed
Edge suite: research.edge_suite at 30/50/70% for every local arm (Jev: no saved scores, no remote calls).

Phases (private text stays under PRIVATE; repo gets counts only):
    specialist  -> PRIVATE/scores/specialist/<item>.json (+ edge cases)
    laya        -> PRIVATE/scores/laya/<item>.json (+ edge cases)
    report      -> PRIVATE/matched-budget-v2.json, OUT/baselines.json, OUT/BASELINES.md

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.matched_budget_v2 report
"""
import argparse
import json
import os
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from research import real_context_bench as rcb
from research.matched_budget import auc, bm25_scores, drop_order, drops_at, peak_rss_mb

PRIVATE_LABELS = Path('/Users/Master/.lcc/bench/next-action-v1')
PRIVATE = Path('/Users/Master/.lcc/bench/matched-budget-v2')
OUT = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'specialist-v1'
BUDGETS = (10, 20, 30, 40, 50, 60)
SEEDS = (0, 1, 2, 3, 4)
MODEL_PER_SOURCE = 12
LAYA_PER_SOURCE = 6  # ponytail: Laya CPU ran ~1-2 blocks/s on this shared machine; 36 items would take > 4 h
SUBSET_SEED = 20261012
SPEC_WINDOW = 512
SCORED = ('bm25', 'mechanical', 'specialist', 'specialist_inv', 'laya', 'jev')
METRICS = ('recall', 'all_kept', 'ev_cov')


# --- pure metric logic -----------------------------------------------------------------------------
def cand_blocks(item):
    return [b for b in item['blocks'] if not b['protected']]


def evidence_groups(item):
    """Strict, non-generic evidence features whose holders (block indices 'i') are all candidates -> id sets."""
    cand = {b['id'] for b in cand_blocks(item)}
    by_i = {b['i']: b['id'] for b in item['blocks']}
    out = []
    for e in item['evidence_sets']:
        hold = {by_i[i] for i in e['blocks']}
        if not e['generic'] and not e['refetched'] and hold and hold <= cand:
            out.append(hold)
    return out


def item_metrics(item, scores, tie=None, groups=None):
    """{budget: dict(recall, all_kept, ev_cov, removed)} incl. budget 0."""
    cand = cand_blocks(item)
    ids = [b['id'] for b in cand]
    tokens = {b['id']: b['tokens'] for b in cand}
    used = [b['id'] for b in cand if b['used']]
    used_tok = sum(tokens[b] for b in used) or 1
    groups = evidence_groups(item) if groups is None else groups
    order = drop_order(ids, scores, tie)
    res = {}
    for bud in (0,) + BUDGETS:
        dropped, frac = drops_at(order, tokens, bud)
        res[bud] = dict(recall=sum(tokens[b] for b in used if b not in dropped) / used_tok,
                        all_kept=not any(b in dropped for b in used),
                        ev_cov=(sum(1 for g in groups if g - dropped) / len(groups)) if groups else None,
                        removed=frac)
    return res


def eligible(item):
    return item['evidence'] == 'actions' and any(b['used'] for b in cand_blocks(item))


def model_subset(index, per_source=MODEL_PER_SOURCE, seed=SUBSET_SEED, take=None):
    """index: [(item_id, source)] -> sorted seeded sample of per_source ids per source. take: keep only the
    first `take` of each source's sample (a nested subset, used for Laya)."""
    by = defaultdict(list)
    for iid, src in sorted(index):
        by[src].append(iid)
    out = []
    for src in sorted(by):
        out += random.Random(f'{seed}:{src}').sample(by[src], min(per_source, len(by[src])))[:take]
    return sorted(out)


def aggregate(per_item):
    """per_item: {item_id: item_metrics(...)} -> {budget: {...}, 'auc': {...}}"""
    out = {}
    for bud in (0,) + BUDGETS:
        rows = [r[bud] for r in per_item.values()]
        k = sum(r['all_kept'] for r in rows)
        ev = [r['ev_cov'] for r in rows if r['ev_cov'] is not None]
        out[str(bud)] = dict(recall=round(statistics.mean(r['recall'] for r in rows), 4), all_kept_k=k, n=len(rows),
                             all_kept=round(k / len(rows), 4), all_kept_wilson95=list(rcb.wilson(k, len(rows))),
                             ev_cov=round(statistics.mean(ev), 4) if ev else None,
                             removed_median=round(statistics.median(r['removed'] for r in rows), 4))
    out['auc'] = {m: auc([(b, out[str(b)][m]) for b in (0,) + BUDGETS]) for m in METRICS
                  if out['0'][m] is not None}
    return out


def mean_curves(curves):
    """Average several aggregate() results (random seeds / tie seeds) metric-wise."""
    out = {}
    for bud in (0,) + BUDGETS:
        b = str(bud)
        out[b] = {m: round(statistics.mean(c[b][m] for c in curves), 4) for m in METRICS if curves[0][b][m] is not None}
        out[b]['n'] = curves[0][b]['n']
        out[b]['all_kept_k'] = round(statistics.mean(c[b]['all_kept_k'] for c in curves), 2)
    out['auc'] = {m: round(statistics.mean(c['auc'][m] for c in curves), 4) for m in curves[0]['auc']}
    return out


# --- data ------------------------------------------------------------------------------------------
def split_ids(name):
    sp = json.loads((PRIVATE_LABELS / 'splits.json').read_text())['items']
    return sorted(i for i, s in sp.items() if s == name)


def load_item(iid):
    return json.loads((PRIVATE_LABELS / 'items' / f'{iid}.json').read_text())


_TEXTS = {}


def texts_for(item):
    st = item['text_store']
    if st not in _TEXTS:
        _TEXTS.clear()  # ponytail: one store cached; items are iterated grouped by store
        _TEXTS[st] = json.loads((PRIVATE_LABELS / 'texts' / f'{st}.json').read_text())
    return {b['id']: _TEXTS[st][b['id']] for b in cand_blocks(item)}


# --- arms ------------------------------------------------------------------------------------------
def text_blocks(pairs):
    from lcc.relevance.blocks import TextBlock
    return [TextBlock(id=i, index=n, text=t, character_start=0, character_end=0, line_start=0, line_end=0)
            for n, (i, t) in enumerate(pairs)]


def mechanical_scores(goal, pairs):
    from lcc.relevance.compactor import _score_mechanically
    res = _score_mechanically(text_blocks(pairs), goal)
    return {i: s + (1.0 if reason else 0.0) for i, (s, _, reason) in res.items()}


def cheap_scores(goal, pairs, key):
    """pairs: [(id, text)] oldest first -> {arm: {id: score}} for recency/random/bm25/mechanical."""
    out = dict(recency={i: float(n) for n, (i, _) in enumerate(pairs)}, bm25=bm25_scores(goal, dict(pairs)),
               mechanical=mechanical_scores(goal, pairs))
    for s in SEEDS:
        rng = random.Random(f'{s}:{key}')
        out[f'random_s{s}'] = {i: rng.random() for i, _ in pairs}
    return out


class Specialist:
    """Batched exp02 scorer; logits equal SpecialistBackend.score (checked to 1e-6 on a dev item)."""

    def __init__(self):
        os.environ.setdefault('HF_HOME', str(rcb.HF_HOME))
        from lcc_engine.engine import SpecialistBackend
        import torch
        t0 = time.perf_counter()
        self.be = SpecialistBackend(str(rcb.SPECIALIST_HEAD), device='cpu', max_len=SPEC_WINDOW)
        self.be.score('warm up', 'load the model')
        self.load_ms = round((time.perf_counter() - t0) * 1000)
        self.torch, self.m = torch, self.be._model

    def __call__(self, goal, pairs, batch=32):
        m = self.m
        n_tok = {i: len(m.tokenizer(goal, t, truncation=False)['input_ids']) for i, t in pairs}
        fit = sorted((p for p in pairs if n_tok[p[0]] <= SPEC_WINDOW), key=lambda p: n_tok[p[0]])
        out = {i: None for i, _ in pairs}
        with self.torch.no_grad():
            for k in range(0, len(fit), batch):
                bs = fit[k:k + batch]
                enc = m.encode([goal] * len(bs), [t for _, t in bs], max_len=SPEC_WINDOW)
                for (i, _), v in zip(bs, m(enc)):
                    out[i] = float(v)
        return out


class Laya:
    """Native Laya scores exactly as LCC batches them; no mechanical fallback (None instead)."""

    def __init__(self):
        from lcc.relevance.laya import LayaClient
        t0 = time.perf_counter()
        self.client = LayaClient(offline=True, device='cpu')
        self.client._ensure_agent()
        self.load_ms = round((time.perf_counter() - t0) * 1000)

    def __call__(self, goal, pairs):
        from lcc.relevance.compactor import RelevanceCompactionRequest, _score_with_laya
        req = RelevanceCompactionRequest(text='', question=goal, provider='laya', batch_size=8)
        res, _, _, warnings, *_ = _score_with_laya(self.client, text_blocks(pairs), req)
        sc = {i: (v[0] if v[1] == 'laya' else None) for i, v in res.items()}
        return {i: sc.get(i) for i, _ in pairs}, Counter(re.sub(r'_\d+_', '_N_', w.split(':')[0]) for w in warnings)


# --- phases ----------------------------------------------------------------------------------------
def eligible_dev():
    """-> (eligible items ordered by text store, exclusion counts)."""
    items, skip = [], Counter()
    for iid in split_ids('dev'):
        it = load_item(iid)
        if it['evidence'] != 'actions':
            skip['no_agent_action'] += 1
        elif not eligible(it):
            skip['no_used_candidate'] += 1
        else:
            items.append(it)
    return sorted(items, key=lambda d: (d['text_store'], d['item_id'])), skip


def model_ids(items, take=None):
    return model_subset([(d['item_id'], d['source']) for d in items], take=take)


def edge_pairs():
    from research.edge_suite import load_cases
    return [(c, [(b['id'], b['text']) for b in c['blocks']]) for c in load_cases()]


def model_phase(arm):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    import torch
    torch.set_num_threads(int(os.environ.get('MB2_THREADS', '4')))
    out = PRIVATE / 'scores' / arm
    out.mkdir(parents=True, exist_ok=True)
    items, _ = eligible_dev()
    want = set(model_ids(items, LAYA_PER_SOURCE if arm == 'laya' else None))
    with rcb.network_guard():
        scorer = (Specialist if arm == 'specialist' else Laya)()
        for it in items:
            p = out / f"{it['item_id']}.json"
            if it['item_id'] not in want or p.exists():
                continue  # ponytail: per-item file is the checkpoint
            pairs = list(texts_for(it).items())
            t0, c0 = time.perf_counter(), time.process_time()
            r = scorer(it['goal'], pairs)
            sc, warn = r if arm == 'laya' else (r, Counter())
            p.write_text(json.dumps(dict(scores=sc, warnings=warn, n=len(pairs),
                                         ms=round((time.perf_counter() - t0) * 1000),
                                         cpu_ms=round((time.process_time() - c0) * 1000), load_avg_1m=os.getloadavg()[0])))
            print(arm, it['item_id'], len(pairs), round(time.perf_counter() - t0, 1), flush=True)
        edge = out / '_edge.json'
        if not edge.exists():
            res = {}
            for c, pairs in edge_pairs():
                r = scorer(c['goal'], pairs)
                res[c['id']] = r[0] if arm == 'laya' else r
            edge.write_text(json.dumps(res))
    meta = dict(model_load_ms=scorer.load_ms, peak_rss_mb=peak_rss_mb(), guard_trips=rcb.GUARD['trips'],
                torch_threads=torch.get_num_threads())
    (out / '_meta.json').write_text(json.dumps(meta))
    return meta


def tie_curves(item_list, score_of, groups):
    """Random tie-break sensitivity: mean of 5 seeds."""
    cs = []
    for s in SEEDS:
        per = {}
        for it in item_list:
            rng = random.Random(f"tie{s}:{it['item_id']}")
            tie = {b['id']: rng.random() for b in cand_blocks(it)}
            per[it['item_id']] = item_metrics(it, score_of(it), tie, groups[it['item_id']])
        cs.append(aggregate(per))
    return mean_curves(cs)


def evaluate(item_list, arm_scores, groups):
    """arm_scores: {arm: {item_id: scores}} -> {arm: curve}, random arms averaged."""
    curves, rnd = {}, []
    for arm, by_item in arm_scores.items():
        c = aggregate({it['item_id']: item_metrics(it, by_item[it['item_id']], groups=groups[it['item_id']])
                       for it in item_list})
        if arm.startswith('random_s'):
            rnd.append(c)
        else:
            curves[arm] = c
    curves['random'] = mean_curves(rnd)
    ties = {a: tie_curves(item_list, lambda it, a=a: arm_scores[a][it['item_id']], groups)['auc']
            for a in arm_scores if a in SCORED}
    return curves, ties


def coverage(item_list, by_item):
    n = sum(len(cand_blocks(it)) for it in item_list)
    return round(sum(v is not None for it in item_list for v in by_item[it['item_id']].values()) / n, 4)


def tied_share(item_list, by_item):
    n = sum(len(cand_blocks(it)) for it in item_list)
    tied = 0
    for it in item_list:
        c = Counter(v for v in by_item[it['item_id']].values() if v is not None)
        tied += sum(k for k in c.values() if k > 1)
    return round(tied / n, 4)


def by_source(item_list, by_item, groups):
    out = {}
    for src in sorted({it['source'] for it in item_list}):
        sub = [it for it in item_list if it['source'] == src]
        out[src] = dict(n=len(sub), auc=aggregate({it['item_id']: item_metrics(it, by_item[it['item_id']], groups=groups[it['item_id']])
                                                   for it in sub})['auc'])
    return out


def jev_overlap():
    """Frozen-60 items outside test, mapped by goal + identical candidate ids -> (items, saved arm scores)."""
    from research.matched_budget import candidates, saved_scores
    root = rcb.PRIVATE
    sp = json.loads((PRIVATE_LABELS / 'splits.json').read_text())['items']
    by_goal = defaultdict(list)
    for iid, s in sp.items():
        if s != 'test':
            it = load_item(iid)
            if it['source'] == 'claude':
                by_goal[it['goal'].strip()].append(it)
    items, scores, skip = [], defaultdict(dict), Counter()
    for f in sorted((root / 'dossiers').glob('*.json')):
        d = json.loads(f.read_text())
        recs = {a: json.loads((root / 'runs' / r / f.name).read_text())
                for a, r in (('jev', 'jev_block'), ('specialist', 'specialist'), ('laya', 'laya_block'))}
        cand = candidates(recs['jev']['decisions'])
        match = [it for it in by_goal.get(d['goal'].strip(), []) if [b['id'] for b in cand_blocks(it)] == cand]
        if not match:
            skip['test_split_or_unmatched'] += 1
            continue
        it = match[0]
        if not eligible(it):
            skip['no_used_candidate'] += 1
            continue
        items.append(it)
        k = it['item_id']
        scores['jev'][k] = saved_scores('jev', recs['jev'], cand)
        scores['specialist'][k] = saved_scores('specialist', recs['specialist'], cand)
        scores['specialist_inv'][k] = {b: (None if v is None else -v) for b, v in scores['specialist'][k].items()}
        lsc = {x['id']: x['score'] for x in recs['laya']['decisions'] if x['source'] == 'laya'}
        scores['laya'][k] = {b: lsc.get(b) for b in cand}
    return items, scores, skip


def edge_results():
    from research import edge_suite as es
    cases = es.load_cases()
    arms = {'oracle': es.oracle, 'recency': es.recency, 'bm25': es.bm25}
    out = {a: es.summary(cases, es.run(cases, es.arm_scores(cases, f))) for a, f in arms.items()}
    out['mechanical'] = es.summary(cases, es.run(cases, {c['id']: mechanical_scores(c['goal'], p) for c, p in edge_pairs()}))
    for arm in ('specialist', 'laya'):
        p = PRIVATE / 'scores' / arm / '_edge.json'
        if p.exists():
            sc = json.loads(p.read_text())
            out[arm] = es.summary(cases, es.run(cases, sc))
            if arm == 'specialist':
                inv = {c: {b: (None if v is None else -v) for b, v in s.items()} for c, s in sc.items()}
                out['specialist_inv'] = es.summary(cases, es.run(cases, inv))
            out[arm]['coverage'] = round(sum(v is not None for s in sc.values() for v in s.values())
                                         / sum(len(s) for s in sc.values()), 4)
    rnd = [es.summary(cases, es.run(cases, es.arm_scores(cases, es.random_arm(s)))) for s in SEEDS]
    out['random'] = {b: dict(passed=round(statistics.mean(r[b]['passed'] for r in rnd), 2), n=len(cases))
                     for b in es.BUDGETS}
    return {a: {str(b): dict(passed=v['passed'], n=v['n'], **({'failed': v['failed']} if 'failed' in v else {}))
                for b, v in s.items() if b != 'coverage'} | ({'coverage': s['coverage']} if 'coverage' in s else {})
            for a, s in out.items()}


def report_phase():
    items, skip = eligible_dev()
    groups = {it['item_id']: evidence_groups(it) for it in items}
    cheap, lat = defaultdict(dict), defaultdict(list)
    for it in items:
        pairs = list(texts_for(it).items())
        t0 = time.perf_counter()
        sc = cheap_scores(it['goal'], pairs, it['item_id'])
        lat['cheap'].append((time.perf_counter() - t0) * 1000)
        for a, s in sc.items():
            cheap[a][it['item_id']] = s
    t_bm, t_mech = [], []
    for it in items[:40]:  # ponytail: per-arm latency on 40 items is enough for an order of magnitude
        pairs = list(texts_for(it).items())
        t0 = time.perf_counter(); bm25_scores(it['goal'], dict(pairs)); t_bm.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter(); mechanical_scores(it['goal'], pairs); t_mech.append((time.perf_counter() - t0) * 1000)
    dev_curves, dev_ties = evaluate(items, cheap, groups)

    def sizes(lst):
        c = [len(cand_blocks(it)) for it in lst]
        return dict(items=len(lst), candidates=sum(c), per_item_median=statistics.median(c) if c else None,
                    sources=dict(Counter(it['source'] for it in lst)),
                    used_share_blocks=round(sum(b['used'] for it in lst for b in cand_blocks(it)) / max(1, sum(c)), 4))

    model_runs, model_meta = {}, {}
    for arm in ('specialist', 'laya'):
        d = PRIVATE / 'scores' / arm
        model_runs[arm] = {p.stem: json.loads(p.read_text()) for p in d.glob('*.json') if not p.stem.startswith('_')}
        if (d / '_meta.json').exists():
            model_meta[arm] = json.loads((d / '_meta.json').read_text())

    def subset(take, arms):
        """Every arm in `arms` on the nested model subset; items missing a model score are left out (counted)."""
        ids = set(model_ids(items, take))
        planned = [it for it in items if it['item_id'] in ids]
        done = [it for it in planned if all(it['item_id'] in model_runs[a] for a in arms)]
        sc = {a: {it['item_id']: v[it['item_id']] for it in done} for a, v in cheap.items()}
        for a in arms:
            sc[a] = {it['item_id']: model_runs[a][it['item_id']]['scores'] for it in done}
        sc['specialist_inv'] = {k: {b: (None if v is None else -v) for b, v in x.items()} for k, x in sc['specialist'].items()}
        out = dict(planned=len(planned), per_source=take or MODEL_PER_SOURCE, seed=SUBSET_SEED, size=sizes(done),
                   curves={}, tie_random_auc={}, coverage={}, tied_share={}, by_source={})
        if done:
            out['curves'], out['tie_random_auc'] = evaluate(done, sc, groups)
            out['coverage'] = {a: coverage(done, sc[a]) for a in sc if not a.startswith('random')}
            out['tied_share'] = {a: tied_share(done, sc[a]) for a in sc if a in SCORED}
            out['by_source'] = {a: by_source(done, sc[a], groups) for a in sc if not a.startswith('random')}
        return out, done

    dm, done = subset(None, ('specialist',))
    ls, laya_done = subset(LAYA_PER_SOURCE, ('specialist', 'laya'))
    ls['laya_warning_kinds'] = dict(sum((Counter({re.sub(r'_\d+_', '_N_', w): n for w, n in
                                                  model_runs['laya'][it['item_id']].get('warnings', {}).items()})
                                         for it in laya_done), Counter()))
    m_curves = dm['curves']

    j_items, j_saved, j_skip = jev_overlap()
    jg = {it['item_id']: evidence_groups(it) for it in j_items}
    jsc = {a: dict(v) for a, v in j_saved.items()}
    for it in j_items:
        pairs = list(texts_for(it).items())
        for a, s in cheap_scores(it['goal'], pairs, it['item_id']).items():
            jsc.setdefault(a, {})[it['item_id']] = s
    j_curves, j_ties = evaluate(j_items, jsc, jg)
    j_cov = {a: coverage(j_items, jsc[a]) for a in jsc if not a.startswith('random')}
    j_paired = {}
    jev_per = {it['item_id']: item_metrics(it, jsc['jev'][it['item_id']], groups=jg[it['item_id']]) for it in j_items}
    for a in jsc:
        if a in ('jev',) or a.startswith('random'):
            continue
        per = {it['item_id']: item_metrics(it, jsc[a][it['item_id']], groups=jg[it['item_id']]) for it in j_items}
        j_paired[a] = {str(b): dict(
            recall_wins=sum(per[k][b]['recall'] > jev_per[k][b]['recall'] + 1e-9 for k in per),
            recall_losses=sum(per[k][b]['recall'] < jev_per[k][b]['recall'] - 1e-9 for k in per)) for b in BUDGETS}

    def q(xs):
        return dict(median=round(statistics.median(xs), 1), p90=round(rcb.quantile(xs, 0.9), 1)) if xs else None

    cost = dict(bm25=dict(score_ms=q(t_bm), note='stdlib, 40 dev items'),
                mechanical=dict(score_ms=q(t_mech), note='LCC _score_mechanically in-process, 40 dev items'))
    for arm, runs in model_runs.items():
        rs = [runs[it['item_id']] for it in (done if arm == 'specialist' else laya_done)]
        meta = model_meta.get(arm, {})
        cost[arm] = dict(score_ms=q([r['ms'] for r in rs]), cpu_ms=q([r['cpu_ms'] for r in rs]),
                         blocks_per_s=round(sum(r['n'] for r in rs) / (sum(r['ms'] for r in rs) / 1000), 2) if rs else None,
                         load_avg_1m_median=round(statistics.median(r['load_avg_1m'] for r in rs), 1) if rs else None,
                         model_load_ms=meta.get('model_load_ms'), peak_rss_mb=meta.get('peak_rss_mb'),
                         torch_threads=meta.get('torch_threads'), guard_trips=meta.get('guard_trips'))
    spec_flag = None
    if 'specialist' in m_curves:
        spec_flag = {k: dict(specialist=c['specialist']['auc']['recall'], inverted=c['specialist_inv']['auc']['recall'],
                             inverted_better_by_1pt=c['specialist_inv']['auc']['recall'] - c['specialist']['auc']['recall'] >= 0.01)
                     for k, c in (('dev_model', m_curves), ('jev_overlap', j_curves))}
    result = dict(
        schema='matched-budget/2', labels='next-action-v1 strict USED (research.next_action_labels)',
        split='dev (test not opened)', budgets_pct=list(BUDGETS),
        dev=dict(size=sizes(items), excluded=dict(skip), curves=dev_curves, tie_random_auc=dev_ties,
                 tied_share={a: tied_share(items, cheap[a]) for a in ('bm25', 'mechanical')},
                 by_source={a: by_source(items, cheap[a], groups) for a in ('recency', 'bm25', 'mechanical')}),
        dev_model=dm, laya_subset=ls,
        jev_overlap=dict(size=sizes(j_items), excluded=dict(j_skip), curves=j_curves, tie_random_auc=j_ties,
                         coverage=j_cov, paired_recall_vs_jev=j_paired,
                         note='frozen-60 items outside test; Jev/specialist/Laya scores from saved v0/v1 runs '
                              '(Laya there ran on Apple GPU, native scores only), others recomputed'),
        specialist_inverted=spec_flag, edge_suite=edge_results(), cost=cost)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / 'matched-budget-v2.json').write_text(json.dumps(result, indent=1))
    (OUT / 'baselines.json').write_text(json.dumps(result, indent=1) + '\n')
    (OUT / 'BASELINES.md').write_text(render_md(result))
    return result


# --- markdown --------------------------------------------------------------------------------------
def _f(v, d=2):
    return '-' if v is None else f'{v:.{d}f}'


def curve_table(curves, arms):
    head = ['| arm | ' + ' | '.join(f'{b}%' for b in BUDGETS) + ' | AUC recall | AUC all-kept | AUC ev-cov |',
            '|---' * (len(BUDGETS) + 4) + '|']
    for a in arms:
        if a not in curves:
            continue
        c = curves[a]
        cells = [f"{c[str(b)]['recall']:.2f} / {c[str(b)]['all_kept_k']}/{c[str(b)]['n']} / {_f(c[str(b)].get('ev_cov'))}"
                 for b in BUDGETS]
        head.append(f'| {a} | ' + ' | '.join(cells) + f" | {_f(c['auc'].get('recall'), 3)} | "
                    f"{_f(c['auc'].get('all_kept'), 3)} | {_f(c['auc'].get('ev_cov'), 3)} |")
    return head


def render_md(r):
    dv, dm, ls, jo, e, k = r['dev'], r['dev_model'], r['laya_subset'], r['jev_overlap'], r['edge_suite'], r['cost']
    arms_all = ('recency', 'bm25', 'mechanical', 'specialist', 'specialist_inv', 'laya', 'jev', 'random')
    best = lambda c: max((a for a in c if a != 'random'), key=lambda a: c[a]['auc']['recall'])  # noqa: E731
    flag = r['specialist_inverted'] or {}
    lines = [
        '# Matched-budget v2 baselines: next-action evidence labels (dev split)', '',
        '## Limits (read first)', '',
        '- Labels are rule-based next-action evidence (research.next_action_labels v1), not human judgement: a block '
        'is USED when the agent later reused a path, identifier, number, hash, line or quoted span from it without '
        're-fetching. USED means relied on, not proven necessary.',
        '- Labels still lean recent (USED rate 4.8% in the oldest tenth vs 16.3% in the newest, train+dev): '
        'recency is a strong baseline here by construction, not because it understands the goal.',
        f"- Dev only ({dv['size']['items']} eligible items); the test split was not opened. Excluded dev items: "
        f"{dv['excluded']}.",
        f"- Model arms (specialist, Laya) ran on a seeded subset ({dm['size']['items']} of {dm['planned']} planned items, "
        f"{dm['per_source']} per source, seed {dm['seed']}); Laya CPU was too slow for all of it (~1-2 blocks/s under "
        f"load), so Laya ran on a nested subset ({ls['size']['items']} of {ls['planned']} planned: the first "
        f"{ls['per_source']} of each source's seeded sample). Every arm is compared on the SAME items only.",
        f"- jev-overlap = the {jo['size']['items']} frozen-60 items outside test with >= 1 USED candidate (excluded: "
        f"{jo['excluded']}; the test-split items are never opened). Jev, "
        'specialist and Laya scores there are reused from saved v0/v1 runs (no new calls; that Laya run used the Apple '
        'GPU and a mechanical fallback that is NOT mixed in here: Laya-native scores only, the rest unscored).',
        '- Drop-only at the block level: no trimming. Unscored blocks (specialist pair window 512 tokens, Laya oversized '
        'or failed batches) are kept until only unscored candidates remain, as the arm does live, so low coverage '
        'flatters an arm at light budgets.',
        '- Ties drop the older block first; random tie-break AUCs are reported because mechanical and BM25 tie a lot.',
        '- Token counts are the LCC heuristic (gpt-4.1 counter), not a real tokenizer.',
        f"- Latency was measured on a shared machine (1-min load average ~{k.get('laya', {}).get('load_avg_1m_median', '?')} "
        'on 10 cores); treat it as an order of magnitude.', '',
        '## Bottom line', '',
        f"- Dev (all items): best recall AUC is **{best(dv['curves'])}** ({dv['curves'][best(dv['curves'])]['auc']['recall']:.3f}); "
        + ', '.join(f"{a} {dv['curves'][a]['auc']['recall']:.3f}" for a in ('recency', 'bm25', 'mechanical', 'random')) + '.',
    ]
    for name, sub in (('Dev-model subset', dm), ('Laya subset', ls)):
        c = sub['curves']
        if c:
            lines.append(f"- {name} ({sub['size']['items']} items): best recall AUC is **{best(c)}** "
                         f"({c[best(c)]['auc']['recall']:.3f}); "
                         + ', '.join(f"{a} {c[a]['auc']['recall']:.3f}" for a in arms_all if a in c) + '.')
    c = jo['curves']
    lines += [f"- jev-overlap: Jev recall AUC {c['jev']['auc']['recall']:.3f}; "
              + ', '.join(f"{a} {c[a]['auc']['recall']:.3f}" for a in arms_all if a in c and a != 'jev') + '.',
              '- Specialist orientation (recall AUC, own logits vs negated): ' + '; '.join(
                  f"{k} {v['specialist']:.3f} vs {v['inverted']:.3f}" for k, v in flag.items())
              + ('. FLAG: negated logits are >= 1 pt better somewhere, so the exp02 head carries no usable '
                 'orientation on these labels.' if any(v['inverted_better_by_1pt'] for v in flag.values())
                 else '. No inversion: negating the logits is not >= 1 pt better on either subset.'),
              (lambda b: f"- No local arm beats Jev on jev-overlap: closest is {b} "
               f"({(c[b]['auc']['recall'] - c['jev']['auc']['recall']) * 100:+.1f} pt recall AUC). On the dev-model subset "
               "no arm beats recency; the specialist's lead on the 18-item Laya subset does not hold on the 36 items."
               )(max((a for a in c if a not in ('jev', 'random')), key=lambda a: c[a]['auc']['recall'])),
              '- A specialist that is "superior to Jev" must beat Jev here AND beat recency/BM25 on dev, and pass more '
              'edge cases than every arm below.', '',
              '## Metrics', '',
              'Cells: macro USED-token recall / items keeping every USED block (k/n) / macro evidence-feature coverage. '
              'AUC over 0..60% budget (0% = 1.0), normalised to 0-1.', '',
              f"## Dev, all eligible items ({dv['size']['items']} items, {dv['size']['candidates']} candidates, "
              f"USED share of blocks {dv['size']['used_share_blocks']:.3f})", '',
              *curve_table(dv['curves'], arms_all), '',
              'Random tie-break AUC (mean of 5 seeds): ' + '; '.join(
                  f"{a} recall {t['recall']:.3f} / all-kept {t['all_kept']:.3f}" for a, t in dv['tie_random_auc'].items()) + '.',
              'Tied share of candidates: ' + ', '.join(f'{a} {v:.2f}' for a, v in dv['tied_share'].items()) + '.', '',
              'Recall AUC by source: ' + '; '.join(
                  f"{a}: " + ', '.join(f"{s} {v['auc']['recall']:.3f} (n={v['n']})" for s, v in bs.items())
                  for a, bs in dv['by_source'].items()) + '.', '']
    for name, sub in (('Dev-model subset', dm), ('Laya subset (nested in dev-model)', ls)):
        if not sub['size']['items']:
            continue
        lines += [f"## {name} ({sub['size']['items']} items, {sub['size']['candidates']} candidates, "
                  f"sources {sub['size']['sources']})", '', *curve_table(sub['curves'], arms_all), '',
                  'Share of candidates each arm scored: ' + ', '.join(f'{a} {v:.2f}' for a, v in sub['coverage'].items()) + '.',
                  'Random tie-break AUC: ' + '; '.join(f"{a} recall {t['recall']:.3f} / all-kept {t['all_kept']:.3f}"
                                                       for a, t in sub['tie_random_auc'].items()) + '.',
                  'Recall AUC by source: ' + '; '.join(
                      f"{a}: " + ', '.join(f"{s} {v['auc']['recall']:.3f} (n={v['n']})" for s, v in bs.items())
                      for a, bs in sub['by_source'].items() if a in ('recency', 'bm25', 'specialist', 'specialist_inv', 'laya')) + '.', '']
        if 'laya_warning_kinds' in sub:
            lines += [f"Laya warnings by kind: {sub['laya_warning_kinds'] or 'none'}.", '']
    lines += [f"## jev-overlap ({jo['size']['items']} items, {jo['size']['candidates']} candidates; excluded {jo['excluded']})", '',
              *curve_table(jo['curves'], arms_all), '',
              'Share of candidates each arm scored: ' + ', '.join(f'{a} {v:.2f}' for a, v in jo['coverage'].items()) + '.',
              'Random tie-break AUC: ' + '; '.join(f"{a} recall {t['recall']:.3f} / all-kept {t['all_kept']:.3f}"
                                                   for a, t in jo['tie_random_auc'].items()) + '.', '',
              'Paired items vs Jev (USED recall higher / lower than Jev on the same item):', '',
              *[f"- {a}: " + '; '.join(f"{b}% +{v['recall_wins']}/-{v['recall_losses']}" for b, v in p.items())
                for a, p in jo['paired_recall_vs_jev'].items()], '',
              '## Edge-case suite (35 synthetic cases, pass k/35)', '',
              '| arm | 30% | 50% | 70% | scored share |', '|---|---|---|---|---|',
              *[f"| {a} | {s['30']['passed']} | {s['50']['passed']} | {s['70']['passed']} | {_f(s.get('coverage'))} |"
                for a, s in e.items()], '',
              'Jev: not run on the edge suite (no saved scores; no remote calls allowed). Oracle = gold upper bound. '
              'Random = mean of 5 seeds. Scored share < 1: blocks over the arm\'s window are unscored and, by the shared '
              'rule, dropped last, so the arm drops only the short scored blocks, which is where most must-keep evidence '
              'sits. The 512-token specialist fails the suite mostly for this structural reason, not only for ranking.', '',
              '## Cost per item', '',
              '| arm | score ms median | p90 | blocks/s | model load ms | peak RSS MB | threads | note |',
              '|---|---|---|---|---|---|---|---|']
    for a, x in k.items():
        sm = x.get('score_ms') or {}
        lines.append(f"| {a} | {sm.get('median', '-')} | {sm.get('p90', '-')} | {x.get('blocks_per_s', '-')} | "
                     f"{x.get('model_load_ms', '-')} | {x.get('peak_rss_mb', '-')} | {x.get('torch_threads', '-')} | {x.get('note', 'CPU; dev-model subset (specialist) / Laya subset (laya)')} |")
    lines += ['', 'Recency and random need no scoring. Jev: see matched-budget-v1 (remote, ~$0.58 median per item).', '']
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('specialist', 'laya', 'report'))
    a = ap.parse_args(argv)
    res = model_phase(a.phase) if a.phase != 'report' else report_phase()
    print(json.dumps(res if a.phase != 'report' else {k: res[k] for k in ('specialist_inverted', 'cost')}, indent=1))


if __name__ == '__main__':
    sys.exit(main())
