"""Specialist v3: v2's two frozen models averaged, plus a small rule floor; same features, leaner memory.

Why: the v2 frozen test failed the edge suite at 50/70% cut (it leans on recency and on identifier-dense
blocks, and gives goal match, errors and LCC's protection almost no weight, because the next-action labels
drop goal-shared evidence by construction) and peak RSS (307.7 MB > 300). v3 changes three things:

- Score = mean of the shipped LR and the GBDT alternative (both frozen v2 models, trained on train only),
  minus the same size penalty (alpha 0.5 x log chars).
- Rule floor: + BONUS for the K_GOAL blocks with the highest BM25 match to the goal (BM25 > 0) and for the
  K_ERR most recent blocks with an error marker. The floor touches at most K_GOAL + K_ERR blocks per item,
  so it protects goal-named and fresh-failure evidence without re-ranking the rest.
- Memory: specialist_v2.featurize now runs LCC's mechanical pass first and keeps BM25 postings only for the
  query terms (bit-identical features; checked against the cached dev features).

The floor settings come from select_phase: a small grid chosen before looking at results, rule = max dev
recall AUC + 0.25 x all-kept AUC subject to (a) dev recall and all-kept AUC >= v2 and (b) edge pass counts
strictly above every other arm at 30/50/70%. (b) uses the edge suite, so the v3 edge counts are NOT
held-out evidence; see V3_DEV_RESULTS.md.

Inference contract unchanged: Judge.load(path).score(goal, texts) -> [float], higher = keep.

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.specialist_v3 {select|eval}
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from research import specialist_v2 as s2

ART = Path('/Users/Master/.lcc/bench/specialist-v3')
OUT = s2.OUT
SEED = 20261013
BG, ERR, LC = (s2.FEATURES.index(f) for f in ('bm25_goal', 'is_error', 'log_chars'))
GRID = dict(members=('lr', 'gbdt', 'ens'), k_goal=(1, 2, 3), k_err=(0, 1, 2, 3), bonus=(3.0,))


def floor_mask(X, k_goal, k_err):
    """Rows of one item that get the floor: top-k_goal by BM25 vs goal (> 0; ties -> later block) and the
    k_err most recent error-marked blocks."""
    n = len(X)
    m = np.zeros(n, bool)
    if k_goal and n:
        bg = X[:, BG]
        top = np.lexsort((np.arange(n), bg))[::-1][:k_goal]
        m[top[bg[top] > 0]] = True
    if k_err:
        m[np.flatnonzero(X[:, ERR] > 0)[-k_err:]] = True
    return m


class Judge:
    """model json: {kind: 'v3', members: [model, ...], alpha, k_goal, k_err, bonus}."""

    def __init__(self, model):
        self.model = model
        self.members = [s2.Judge(m) for m in model['members']]

    @classmethod
    def load(cls, path=None):
        return cls(json.loads(Path(path or ART / 'model.json').read_text()))

    def raw(self, X):
        out = np.zeros(len(X))
        for j in self.members:
            if j.model['kind'] == 'lr':
                out += s2.predict(j.model, X)
            else:
                s = np.full(len(X), j.model['base'])
                r = np.arange(len(X))
                for flat in j.trees:
                    s += s2._walk(flat, X, r)
                out += s
        return out / len(self.members)

    def score_x(self, X):
        m = self.model
        return (self.raw(X) - m['alpha'] * X[:, LC] + m['bonus'] * floor_mask(X, m['k_goal'], m['k_err'])).tolist()

    def score(self, goal, texts):
        if not texts:
            return []
        return self.score_x(s2.featurize(goal, texts))


def build(members, k_goal, k_err, bonus):
    """v3 model dict from the frozen v2 model files."""
    files = dict(lr=['model.json'], gbdt=['model-gbdt.json'], ens=['model.json', 'model-gbdt.json'])[members]
    ms = [json.loads((s2.ART / f).read_text()) for f in files]
    assert all(m['alpha'] == 0.5 for m in ms)
    return dict(kind='v3', members=ms, member_files=files, alpha=0.5, k_goal=k_goal, k_err=k_err, bonus=bonus)


# --- selection (dev features + edge suite) -------------------------------------------------------------
def edge_counts(cases, judge):
    from research import edge_suite as es
    sc = {c['id']: dict(zip([b['id'] for b in c['blocks']], judge.score(c['goal'], s2.edge_texts(c)))) for c in cases}
    return es.summary(cases, es.run(cases, sc))


def other_edge_best():
    """Best pass count per cut over every other arm (saved baselines + specialist v2 / v2 GBDT)."""
    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    cases = es.load_cases()
    other = mb.edge_results()
    for name, f in (('specialist_v2', 'model.json'), ('specialist_v2_gbdt', 'model-gbdt.json')):
        other[name] = {str(b): v for b, v in edge_counts(cases, s2.Judge.load(s2.ART / f)).items()}
    return other, {b: max(s[b]['passed'] for a, s in other.items() if a != 'oracle') for b in ('30', '50', '70')}


def select_phase():
    from itertools import product

    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    ART.mkdir(parents=True, exist_ok=True)
    D = np.load(s2.ART / 'features-dev.npz')
    X, rows_item = D['X'], D['item']
    items, _ = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    spans = defaultdict(list)
    for r, iid in enumerate(rows_item):
        spans[iid].append(r)
    cases = es.load_cases()
    _, best_other = other_edge_best()

    def dev_auc(j):
        sc = np.zeros(len(X))
        for rs in spans.values():  # dev rows = candidate blocks of one item, in block order
            sc[rs] = j.score_x(X[rs])
        return s2.curve(items, s2.item_scores(items, D, sc), groups)['auc']

    v2 = dev_auc(Judge(build('lr', 0, 0, 0.0)))
    log = []
    for mem, kg, ke, bo in product(*GRID.values()):
        j = Judge(build(mem, kg, ke, bo))
        e = edge_counts(cases, j)
        r = dict(members=mem, k_goal=kg, k_err=ke, bonus=bo, **dev_auc(j),
                 edge={str(b): e[b]['passed'] for b in es.BUDGETS})
        r['ok'] = (r['recall'] >= v2['recall'] and r['all_kept'] >= v2['all_kept']
                   and all(r['edge'][b] > best_other[b] for b in r['edge']))
        log.append(r)
        print(r, flush=True)
    ok = [r for r in log if r['ok']]
    pick = max(ok, key=s2.pick_key) if ok else None
    out = dict(rule='max dev recall AUC + 0.25 x all-kept AUC s.t. dev recall and all-kept >= v2 and edge > best '
                    'other arm at 30/50/70%', grid=GRID, v2_dev=v2, edge_best_other=best_other, pick=pick, log=log)
    (ART / 'select-log.json').write_text(json.dumps(out, indent=1))
    if pick:
        (ART / 'model.json').write_text(json.dumps(build(pick['members'], pick['k_goal'], pick['k_err'], pick['bonus'])))
    return dict(pick=pick, v2_dev=v2, edge_best_other=best_other, n_ok=len(ok))


# --- eval ---------------------------------------------------------------------------------------------
def group_bootstrap(items, a, b, n=2000, seed=SEED):
    """Paired bootstrap over session groups: mean over items of (a - b) [95% CI]. a, b: {item_id: value}."""
    by = defaultdict(list)
    for it in items:
        by[it['group']].append(a[it['item_id']] - b[it['item_id']])
    gs = sorted(by)
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        d = [x for g in (rng.choice(gs) for _ in gs) for x in by[g]]
        stats.append(sum(d) / len(d))
    stats.sort()
    allv = [x for g in gs for x in by[g]]
    return dict(mean=round(sum(allv) / len(allv), 4), ci95=[round(stats[int(0.025 * n)], 4),
                                                            round(stats[int(0.975 * n) - 1], 4)], groups=len(gs))


V3_BENCH = s2.BENCH.replace('from research.specialist_v2 import Judge', 'from research.specialist_v3 import Judge')


def bench(model_path, items):
    """Same method as the v2 test protocol (fresh process, 1 thread, one item in memory), v3 Judge."""
    orig = s2.BENCH
    s2.BENCH = V3_BENCH
    try:
        return s2.bench(model_path, items, n=len(items))
    finally:
        s2.BENCH = orig


def bench_file(model_path, path, code):
    """BENCH code on a private jsonl (stress items): per-item blocks / ms and peak RSS."""
    import os
    import subprocess
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path(__file__).resolve().parent.parent)]
                                                      + [p for p in sys.path if p.endswith('src')]),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    r = json.loads(subprocess.run([sys.executable, '-c', code, str(model_path), str(path)], env=env,
                                  check=True, capture_output=True, text=True).stdout)
    return dict(blocks=[x[0] for x in r['rows']], ms=[round(x[1]) for x in r['rows']],
                peak_rss_mb=round(r['peak_rss_mb'], 1), load_avg_1m=round(os.getloadavg()[0], 1))


def eval_phase():
    import os

    from research import edge_suite as es
    from research import matched_budget_v2 as mb
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    judge = Judge.load(ART / 'model.json')
    v2, v2g = s2.Judge.load(s2.ART / 'model.json'), s2.Judge.load(s2.ART / 'model-gbdt.json')
    items, skip = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    arms = defaultdict(dict)
    for it in items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            arms[a][it['item_id']] = sc
    for name, j in (('specialist_v3', judge), ('specialist_v2', v2), ('specialist_v2_gbdt', v2g)):
        arms[name] = s2.judge_scores(j, items)
    curves, _ = mb.evaluate(items, arms, groups)
    per = {a: {it['item_id']: mb.item_metrics(it, arms[a][it['item_id']], groups=groups[it['item_id']]) for it in items}
           for a in ('specialist_v3', 'specialist_v2', 'recency', 'bm25', 'mechanical')}
    auc = {a: {m: {k: mb.auc([(0, 1.0)] + [(b, float(per[a][k][b][m])) for b in mb.BUDGETS]) for k in per[a]}
               for m in ('recall', 'all_kept')} for a in per}
    boot = {f'v3-{a}': {m: group_bootstrap(items, auc['specialist_v3'][m], auc[a][m]) for m in ('recall', 'all_kept')}
            for a in ('specialist_v2', 'recency', 'bm25', 'mechanical')}
    by_src = {a: mb.by_source(items, arms[a], groups) for a in ('specialist_v3', 'specialist_v2', 'recency', 'bm25',
                                                                 'mechanical')}
    # jev-overlap (v2 models never trained on these lineage groups)
    j_items, j_saved, j_skip = mb.jev_overlap()
    jg = {it['item_id']: mb.evidence_groups(it) for it in j_items}
    jsc = {a: dict(v) for a, v in j_saved.items()}
    for it in j_items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            jsc.setdefault(a, {})[it['item_id']] = sc
    jsc['specialist_v3'] = s2.judge_scores(judge, j_items)
    jsc['specialist_v2'] = s2.judge_scores(v2, j_items)
    j_curves = mb.evaluate(j_items, jsc, jg)[0]
    # edge suite, per cut and per category
    cases = es.load_cases()
    edge, _ = other_edge_best()
    edge['specialist_v3'] = {str(b): v for b, v in edge_counts(cases, judge).items()}
    cat_arms = dict(mechanical={c['id']: mb.mechanical_scores(c['goal'], p) for c, p in mb.edge_pairs()},
                    bm25=es.arm_scores(cases, es.bm25))
    edge_cat = {a: {str(b): v['by_category'] for b, v in es.summary(cases, es.run(cases, sc)).items()}
                for a, sc in cat_arms.items()}
    edge_cat.update({a: {b: edge[a][b]['by_category'] for b in ('30', '50', '70')}
                     for a in ('specialist_v3', 'specialist_v2')})
    for a in edge:
        for b in edge[a]:
            if isinstance(edge[a][b], dict):
                edge[a][b] = {k: v for k, v in edge[a][b].items() if k in ('passed', 'n', 'failed')}
    # cost: dev items (protocol method) + private stress items (largest dev items concatenated)
    cost = dict(dev_v3=bench(ART / 'model.json', items), dev_v2=s2.bench(s2.ART / 'model.json', items, n=len(items)))
    for p in sorted(ART.glob('stress*.jsonl')):
        cost[f'{p.stem}_v3'] = bench_file(ART / 'model.json', p, V3_BENCH)
        cost[f'{p.stem}_v2'] = bench_file(s2.ART / 'model.json', p, s2.BENCH)
    sel = json.loads((ART / 'select-log.json').read_text())
    res = dict(schema='specialist-v3/dev', labels='next-action-v2 strict USED, dev split only (test not opened)',
               model={k: v for k, v in judge.model.items() if k != 'members'}, select=dict(
                   rule=sel['rule'], pick=sel['pick'], v2_dev=sel['v2_dev'], edge_best_other=sel['edge_best_other'],
                   grid=sel['grid'], n_configs=len(sel['log']), n_ok=sum(r['ok'] for r in sel['log'])),
               dev=dict(items=len(items), excluded=dict(skip), curves=curves, bootstrap_groups=boot, by_source=by_src),
               jev_overlap=dict(items=len(j_items), excluded=dict(j_skip), curves=j_curves),
               edge_suite=edge, edge_by_category=edge_cat, cost=cost)
    (ART / 'dev-results.json').write_text(json.dumps(res, indent=1))
    (OUT / 'v3-dev-results.json').write_text(json.dumps(res, indent=1) + '\n')
    return {k: res[k] for k in ('model', 'cost')}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('select', 'eval'))
    a = ap.parse_args(argv)
    out = select_phase() if a.phase == 'select' else eval_phase()
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == '__main__':
    sys.exit(main())
