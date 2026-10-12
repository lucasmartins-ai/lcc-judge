"""Specialist v2: the one pre-registered run on the FROZEN test split (next-action labels).

Protocol: research/goal-engine-2026-10-04/specialist-v1/TEST_PROTOCOL.md + test_protocol.json, committed and
pushed before `run` opens any test item. `run` refuses to start unless every hash in test_protocol.json
matches the files on disk (model artifact, code, label inputs, edge fixtures, the frozen test manifest), and it
refuses a second run once test_results.json exists. No training, tuning or model choice happens here.

    protocol -> OUT/test_protocol.json (hashes only; test not opened)
    run      -> PRIVATE/items (test relabelled with the v2 extractor + v2 train-derived generic features),
                PRIVATE/scores, PRIVATE/test-results.json, OUT/test_results.json, OUT/TEST_RESULTS.md (counts only)

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.specialist_v2_test run
"""
import argparse
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from research import edge_suite as es
from research import matched_budget_v2 as mb
from research import specialist_v2 as sv2

REPO = Path(__file__).resolve().parents[1]
OUT = sv2.OUT
PROTOCOL = OUT / 'test_protocol.json'
V1 = Path('/Users/Master/.lcc/bench/next-action-v1')  # frozen split: items (test = 0o444), texts, windows
V2 = Path('/Users/Master/.lcc/bench/next-action-v2')  # train + dev relabel, generic features from train
PRIVATE = Path('/Users/Master/.lcc/bench/specialist-v2-test')
LCC_SRC = Path('/Users/Master/.lcc/bench/real-context-v0/lcc-main/src/lcc/relevance')
SEED = 20261012
BOOT = 2000
BASELINES = ('recency', 'bm25', 'mechanical')
EDGE_RIVALS = ('recency', 'bm25', 'mechanical', 'random', 'drop_largest', 'drop_smallest', 'specialist', 'laya')
LIMITS = dict(ms_median=250.0, ms_p90=1000.0, peak_rss_mb=300.0)
ACCEPTANCE = dict(
    population='primary = eligible test items (agent-action evidence, >= 1 USED candidate) not content-linked to any '
               'train/dev item; all_eligible reported too',
    i='specialist_v2 mean AUC (recall over 0-60% removed, and all-kept over 0-60%) above EACH of recency, BM25, '
      'mechanical on primary, AND paired bootstrap 95% CI of mean(v2 - baseline) per-item AUC with lower bound > 0 '
      f'({BOOT} resamples of session groups, seed {SEED})',
    ii='edge suite: specialist_v2 passes >= every other arm at 30, 50 and 70% (rivals: ' + ', '.join(EDGE_RIVALS)
       + '; random = mean of 5 seeds)',
    iii='cost on the primary test items, fresh process, 1 thread: median ms per item <= {ms_median}, p90 <= {ms_p90}, '
        'peak RSS MB <= {peak_rss_mb}'.format(**LIMITS),
    verdict='PASS only if i, ii and iii all hold; no retraining or tuning after the run')
CODE = ('research/specialist_v2.py', 'research/specialist_v2_test.py', 'research/matched_budget_v2.py',
        'research/matched_budget.py', 'research/next_action_labels.py', 'research/edge_suite.py',
        'research/edge_cases_build.py', 'research/real_context_bench.py')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dir_sha(d, pattern='*.json'):
    h = hashlib.sha256()
    for p in sorted(Path(d).glob(pattern)):
        h.update(f'{p.name} {sha(p)}\n'.encode())
    return h.hexdigest()


def fingerprint():
    """Everything the test run depends on. None of it is a test item."""
    receipt = json.loads((OUT / 'labels-receipt.json').read_text())
    return dict(
        model=dict(path=str(sv2.ART / 'model.json'), sha256=sha(sv2.ART / 'model.json')),
        code={c: sha(REPO / c) for c in CODE},
        lcc_mechanical={f: sha(LCC_SRC / f) for f in ('compactor.py', 'blocks.py')},
        labels=dict(generic_features_v2=sha(V2 / 'generic-features.json'), splits_v2=sha(V2 / 'splits.json'),
                    splits_v1=sha(V1 / 'splits.json'), labels_receipt=sha(OUT / 'labels-receipt.json'),
                    test_items_manifest=receipt['sha256']['test']['items_manifest'],
                    test_texts_manifest=receipt['sha256']['test']['texts_manifest']),
        edge=dict(fixtures=dir_sha(es.FIX),
                  specialist_v1_scores=sha(mb.PRIVATE / 'scores' / 'specialist' / '_edge.json'),
                  laya_scores=sha(mb.PRIVATE / 'scores' / 'laya' / '_edge.json')))


def protocol_phase():
    if PROTOCOL.exists():
        raise SystemExit(f'{PROTOCOL} exists: the protocol is frozen')
    fp = fingerprint()
    doc = dict(schema='specialist-v2/test-protocol', created='2026-10-12', seed=SEED, bootstrap_resamples=BOOT,
               arms=['specialist_v2', *BASELINES, 'random', 'specialist_v1 (seeded subset)'],
               baselines=list(BASELINES), edge_rivals=list(EDGE_RIVALS), limits=LIMITS,
               budgets_pct=list(mb.BUDGETS), edge_budgets_pct=[30, 50, 70], acceptance=ACCEPTANCE,
               jev='not run on test (paid remote calls); the Jev comparison stays on jev-overlap dev and needs an '
                   'owner-approved paid run on test. Saved v0.1 Jev scores of frozen-60 dossiers that fall in test '
                   'are reported descriptively only.', fingerprint=fp)
    PROTOCOL.write_text(json.dumps(doc, indent=1) + '\n')
    return doc


def verify():
    """Hashes now == pre-registered hashes, and the frozen test items are byte-identical to the manifest."""
    want = json.loads(PROTOCOL.read_text())['fingerprint']
    now = fingerprint()
    if now != want:
        bad = [k for k in want if want[k] != now[k]]
        raise SystemExit(f'fingerprint mismatch in {bad}: refusing to run on test')
    lines = (V1 / 'manifest-test.txt').read_text()
    if hashlib.sha256(lines.encode()).hexdigest() != want['labels']['test_items_manifest']:
        raise SystemExit('test manifest changed since the freeze')
    bad = [i for i, h in (x.split() for x in lines.splitlines()) if sha(V1 / 'items' / f'{i}.json') != h]
    if bad:
        raise SystemExit(f'{len(bad)} frozen test items changed since the freeze')
    return [x.split()[0] for x in lines.splitlines()]


# --- labels: the v2 extractor on test (same code path as relabel_phase) ------------------------------------
def relabel_test(test_ids):
    from research import next_action_labels as nal
    out = PRIVATE / 'items'
    out.mkdir(parents=True, exist_ok=True)
    generic = {tuple(x) for x in json.loads((V2 / 'generic-features.json').read_text())}
    by_store = defaultdict(list)
    todo = [i for i in test_ids if not (out / f'{i}.json').exists()]
    for iid in todo:
        by_store[json.loads((V1 / 'items' / f'{iid}.json').read_text())['text_store']].append(iid)
    for store, iids in sorted(by_store.items()):
        texts = json.loads((V1 / 'texts' / f'{store}.json').read_text())
        windows = json.loads((V1 / 'windows' / f'{store}.json').read_text())
        for iid in iids:
            it = nal.relabel_item(json.loads((V1 / 'items' / f'{iid}.json').read_text()), texts, windows[iid])
            it = nal.apply_generic(it, generic)
            (out / f'{iid}.json').write_text(json.dumps(it, ensure_ascii=False))


def slim(it):
    return dict(item_id=it['item_id'], group=it['group'], blocks=[
        dict(id=b['id'], chars=b['chars'], protected=b['protected']) for b in it['blocks']
        if not b['protected'] and b['chars'] >= 200])


def fork_links(test_items):
    """Test items content-linked (next_action_labels.content_links: copied prefixes) to any train/dev item."""
    from research import next_action_labels as nal
    sp = json.loads((V2 / 'splits.json').read_text())['items']
    rows = [slim(json.loads((V2 / 'items' / f'{i}.json').read_text())) for i in sorted(sp)]
    rows += [slim(it) for it in test_items]
    test = {it['item_id'] for it in test_items}
    linked = defaultdict(set)
    for a, b in nal.content_links(rows):
        if (a in test) != (b in test):
            t, o = (a, b) if a in test else (b, a)
            linked[t].add(sp[o])
    return linked


# --- metrics -------------------------------------------------------------------------------------------
def per_item_auc(it, scores, groups):
    m = mb.item_metrics(it, scores, groups=groups)
    return {k: mb.auc([(b, float(m[b][k])) for b in (0,) + mb.BUDGETS]) for k in ('recall', 'all_kept')}


def cluster_boot(items, a_auc, b_auc, seed=SEED, n=BOOT):
    """Paired bootstrap of mean(a - b) resampling session groups (items of a drawn group all come along).
    -> {metric: dict(mean, ci95)}."""
    by_g = defaultdict(list)
    for it in items:
        by_g[it['group']].append(it['item_id'])
    gs = sorted(by_g)
    rng = random.Random(seed)
    out = {}
    for k in ('recall', 'all_kept'):
        d = {g: [a_auc[i][k] - b_auc[i][k] for i in by_g[g]] for g in gs}
        stats = []
        for _ in range(n):
            xs = [x for g in (rng.choice(gs) for _ in gs) for x in d[g]]
            stats.append(sum(xs) / len(xs))
        stats.sort()
        allx = [x for g in gs for x in d[g]]
        out[k] = dict(mean=round(sum(allx) / len(allx), 4),
                      ci95=[round(stats[int(0.025 * n)], 4), round(stats[int(0.975 * n) - 1], 4)])
    return out


def gate_beats(boot, curves):
    """(i): v2 aggregate AUC above each baseline AND paired CI lower bound > 0, for recall and all-kept."""
    rows = {}
    for a in BASELINES:
        for k in ('recall', 'all_kept'):
            rows[f'{a}:{k}'] = (curves['specialist_v2']['auc'][k] > curves[a]['auc'][k]) and boot[a][k]['ci95'][0] > 0
    return all(rows.values()), rows


def gate_edge(edge):
    rows = {}
    for b in ('30', '50', '70'):
        best = max(edge[a][b]['passed'] for a in EDGE_RIVALS if a in edge)
        rows[b] = dict(v2=edge['specialist_v2'][b]['passed'], best_other=best, ok=edge['specialist_v2'][b]['passed'] >= best)
    return all(r['ok'] for r in rows.values()), rows


def gate_cost(c):
    rows = {k: dict(value=c[k], limit=v, ok=c[k] <= v) for k, v in LIMITS.items()}
    return all(r['ok'] for r in rows.values()), rows


# --- arms ----------------------------------------------------------------------------------------------
def all_texts(it):
    st = it['text_store']
    if mb._TEXTS.get(st) is None:
        mb._TEXTS.clear()
        mb._TEXTS[st] = json.loads((V1 / 'texts' / f'{st}.json').read_text())
    return [mb._TEXTS[st].get(b['id']) or '' for b in it['blocks']]


def bench(model_path, items):
    """Fresh process, 1 thread, every primary item (one in memory at a time): sv2.BENCH."""
    PRIVATE.mkdir(parents=True, exist_ok=True)
    # Fresh name, created 0600 atomically (no truncating a stale file, no following a symlink).
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='bench-items-', suffix='.jsonl', dir=PRIVATE)  # private: test block text, owner-only and always removed
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, 'w') as f:
            for it in items:
                f.write(json.dumps(dict(goal=it['goal'], texts=all_texts(it)), ensure_ascii=False) + '\n')
        path = os.pathsep.join([str(REPO)] + [p for p in sys.path if p.endswith('src')])
        env = dict(os.environ, PYTHONPATH=path, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   VECLIB_MAXIMUM_THREADS='1')
        r = json.loads(subprocess.run([sys.executable, '-c', sv2.BENCH, str(model_path), str(tmp)], env=env,
                                      check=True, capture_output=True, text=True).stdout)
    finally:
        tmp.unlink(missing_ok=True)
    ms, nb = [x[1] for x in r['rows']], [x[0] for x in r['rows']]
    q = lambda xs, p: sorted(xs)[max(0, -(-int(p * 1000) * len(xs) // 1000) - 1)]  # noqa: E731
    near = [m for b, m in r['rows'] if 250 <= b <= 600]
    return dict(items=len(ms), blocks_median=statistics.median(nb), blocks_max=max(nb),
                ms_median=round(statistics.median(ms), 1), ms_p90=round(q(ms, 0.9), 1), ms_max=round(max(ms), 1),
                ms_median_250_600_blocks=round(statistics.median(near), 1) if near else None, n_250_600_blocks=len(near),
                over_1s=sum(m > 1000 for m in ms), load_ms=round(r['load_ms']), peak_rss_mb=round(r['peak_rss_mb'], 1),
                load_avg_1m=round(os.getloadavg()[0], 1), model_file_kb=round(Path(model_path).stat().st_size / 1024))


def specialist_v1_scores(items):
    """Old specialist (exp02 ModernBERT head) on the seeded subset; per-item cache (resumable)."""
    d = PRIVATE / 'scores' / 'specialist_v1'
    d.mkdir(parents=True, exist_ok=True)
    todo = [it for it in items if not (d / f"{it['item_id']}.json").exists()]
    if todo:
        import torch
        torch.set_num_threads(4)
        from research import real_context_bench as rcb
        with rcb.network_guard():
            sp = mb.Specialist()
            for it in todo:
                sc = sp(it['goal'], list(mb.texts_for(it).items()))
                (d / f"{it['item_id']}.json").write_text(json.dumps(sc))
                print('v1', it['item_id'], flush=True)
    return {it['item_id']: json.loads((d / f"{it['item_id']}.json").read_text()) for it in items}


def jev_test_overlap(items):
    """Frozen-60 dossiers that landed in TEST with saved v0.1 Jev scores (no new calls). Descriptive only."""
    from research import real_context_bench as rcb
    from research.matched_budget import candidates, saved_scores
    by_goal = defaultdict(list)
    for it in items:
        if it['source'] == 'claude':
            by_goal[it['goal'].strip()].append(it)
    out, sc = [], {}
    for f in sorted((rcb.PRIVATE / 'dossiers').glob('*.json')):
        d = json.loads(f.read_text())
        rec = json.loads((rcb.PRIVATE / 'runs' / 'jev_block' / f.name).read_text())
        cand = candidates(rec['decisions'])
        m = [it for it in by_goal.get(d['goal'].strip(), []) if [b['id'] for b in mb.cand_blocks(it)] == cand]
        if m:
            out.append(m[0])
            sc[m[0]['item_id']] = saved_scores('jev', rec, cand)
    return out, sc


def render_md(r):
    """TEST_RESULTS.md: counts and metrics only (no session text), limits first."""
    arms = ('specialist_v2', 'recency', 'bm25', 'mechanical', 'random', 'specialist_v1', 'jev')
    c, a = r['counts'], r['acceptance']
    yn = lambda ok: 'PASS' if ok else 'FAIL'  # noqa: E731
    L = ['# Specialist v2: frozen test results (next-action labels)', '',
         'Generated once by `python -m research.specialist_v2_test run` under the pre-registered TEST_PROTOCOL.md / '
         'test_protocol.json (sha256 ' + r['protocol_sha256'][:16] + '...). Counts and metrics only, no session text. '
         'No retraining or tuning after this run.', '',
         '## Limits (read first)', '',
         '- INFERIDO: the labels are rule-based next-action evidence (the v2 extractor, applied to test for the first '
         'time in this run), not human judgement. They lean recent and drop evidence the goal itself names; '
         'a high score means "keeps what the agent reused next", not "keeps what a person would keep".',
         '- Model choices (target, size penalty, LR over GBDT) were made on dev and looked at the edge suite; the '
         'edge suite is synthetic, single-author gold, 35 cases, so criterion ii is not held-out evidence.',
         '- Jev did not run on test (paid remote calls). The Jev comparison stays on jev-overlap dev; beating Jev on '
         'test needs an owner-approved paid run. The jev_test_overlap row below (if any) uses saved v0.1 scores.',
         '- Latency and RSS were measured on a shared, loaded machine (load average '
         f"{r['cost']['load_avg_1m']} on 10 cores); treat them as an upper bound.",
         '- Session groups, not items, are the independent unit: the bootstrap resamples groups.', '',
         '## Verdict', '',
         f"- Overall: **{a['verdict']}** (i {yn(a['i_beats_baselines']['ok'])}, ii {yn(a['ii_edge']['ok'])}, "
         f"iii {yn(a['iii_cost']['ok'])}).",
         '- (i) v2 vs baselines on primary (AUC above and CI lower bound > 0): ' + '; '.join(
             f"{k} {yn(v)}" for k, v in a['i_beats_baselines']['rows'].items()) + '.',
         '- (ii) edge: ' + '; '.join(f"{b}% v2 {v['v2']} vs best other {v['best_other']} {yn(v['ok'])}"
                                     for b, v in a['ii_edge']['rows'].items()) + '.',
         '- (iii) cost: ' + '; '.join(f"{k} {v['value']} (limit {v['limit']}) {yn(v['ok'])}"
                                      for k, v in a['iii_cost']['rows'].items()) + '.', '',
         '## Counts', '',
         f"- Test items {c['test_items']}; excluded {json.dumps(c['excluded'])}; eligible {c['eligible']}; "
         f"content-linked to train/dev {c['fork_linked_to_train_or_dev']} {json.dumps(c['fork_linked_by_split'])}.",
         f"- Primary: {c['primary']} items in {c['primary_groups']} session groups, per source "
         f"{json.dumps(c['primary_per_source'])}; {c['primary_candidates']} candidate blocks, {c['primary_used']} USED.", '']
    for name in ('primary', 'all_eligible'):
        x = r[name]
        L += [f"## {name} ({x['items']} items)", '', *mb.curve_table(x['curves'], arms), '',
              'Paired bootstrap, mean(v2 - baseline) per-item AUC [95% CI], groups resampled: ' + '; '.join(
                  f"{b}: recall {v['recall']['mean']:+.4f} [{v['recall']['ci95'][0]:+.4f}, {v['recall']['ci95'][1]:+.4f}], "
                  f"all-kept {v['all_kept']['mean']:+.4f} [{v['all_kept']['ci95'][0]:+.4f}, {v['all_kept']['ci95'][1]:+.4f}]"
                  for b, v in x['bootstrap'].items()) + '.', '',
              '| source | n | ' + ' | '.join(f'{z} recall / all-kept' for z in ('specialist_v2', *BASELINES)) + ' |',
              '|---' * (2 + 1 + len(BASELINES)) + '|',
              *[f"| {k} | {v['n']} | " + ' | '.join(f"{v[z]['recall']:.3f} / {v[z]['all_kept']:.3f}"
                                                   for z in ('specialist_v2', *BASELINES)) + ' |'
                for k, v in x['by_source'].items()], '',
              '| category | n | ' + ' | '.join(f'{z} recall / all-kept' for z in ('specialist_v2', *BASELINES)) + ' |',
              '|---' * (2 + 1 + len(BASELINES)) + '|',
              *[f"| {k} | {v['n']} | " + ' | '.join(f"{v[z]['recall']:.3f} / {v[z]['all_kept']:.3f}"
                                                   for z in ('specialist_v2', *BASELINES)) + ' |'
                for k, v in x['by_category'].items()], '']
    v1 = r['specialist_v1_subset']
    L += [f"## Old specialist (v1) subset ({v1['items']} primary items, seeded 12 per source)", '',
          *mb.curve_table(v1['curves'], arms), '',
          'Paired bootstrap v2 - v1: ' + ', '.join(f"{k} {v['mean']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]"
                                                  for k, v in v1['bootstrap_vs_v1'].items()) + '.', '']
    jo = r['jev_test_overlap']
    L += [f"## Jev, saved v0.1 scores on frozen-60 dossiers in test ({jo['items']} items; descriptive)", '']
    L += [*mb.curve_table(jo['curves'], arms), ''] if jo['items'] else ['- none matched.', '']
    e = r['edge_suite']
    L += ['## Edge suite (35 synthetic cases)', '', '| arm | 30% | 50% | 70% |', '|---|---|---|---|',
          *[f"| {k} | {s['30']['passed']} | {s['50']['passed']} | {s['70']['passed']} |" for k, s in e.items()], '',
          'v2 fails @50%: ' + (', '.join(e['specialist_v2']['50'].get('failed', [])) or '-') + '.', '']
    k = r['cost']
    L += ['## Cost (fresh process, numpy + LCC mechanical pass, 1 thread)', '',
          f"- {k['items']} items (median {k['blocks_median']} blocks, max {k['blocks_max']}): median {k['ms_median']} ms, "
          f"p90 {k['ms_p90']} ms, max {k['ms_max']} ms, {k['over_1s']} items over 1 s; "
          f"{k['ms_median_250_600_blocks']} ms median on the {k['n_250_600_blocks']} items with 250-600 blocks; "
          f"peak RSS {k['peak_rss_mb']} MB; load {k['load_ms']} ms; model {k['model_file_kb']} KB.", '']
    return '\n'.join(L)


# --- run -----------------------------------------------------------------------------------------------
def evaluate_set(items, arms):
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    curves, _ = mb.evaluate(items, arms, groups)
    named = [a for a in arms if not a.startswith('random_s')]
    per = {a: {it['item_id']: per_item_auc(it, arms[a][it['item_id']], groups[it['item_id']]) for it in items}
           for a in named}
    by_src = {}
    for src in sorted({it['source'] for it in items}):
        sub = [it for it in items if it['source'] == src]
        by_src[src] = dict(n=len(sub), **{a: {k: round(statistics.mean(per[a][it['item_id']][k] for it in sub), 4)
                                              for k in ('recall', 'all_kept')} for a in named})
    by_cat = {}
    for cat in sorted({it.get('category') or 'unlabelled' for it in items}):
        sub = [it for it in items if (it.get('category') or 'unlabelled') == cat]
        by_cat[cat] = dict(n=len(sub), **{a: {k: round(statistics.mean(per[a][it['item_id']][k] for it in sub), 4)
                                              for k in ('recall', 'all_kept')} for a in named})
    return curves, per, by_src, by_cat


def run_phase():
    if (OUT / 'test_results.json').exists():
        raise SystemExit('test_results.json exists: the test split is evaluated once')
    test_ids = verify()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    relabel_test(test_ids)
    items_all = [json.loads((PRIVATE / 'items' / f'{i}.json').read_text()) for i in test_ids]
    skip = Counter()
    eligible = []
    for it in items_all:
        if it['evidence'] != 'actions':
            skip['no_agent_action'] += 1
        elif not mb.eligible(it):
            skip['no_used_candidate'] += 1
        else:
            eligible.append(it)
    linked = fork_links(items_all)
    primary = sorted((it for it in eligible if not linked.get(it['item_id'])), key=lambda d: (d['text_store'], d['item_id']))
    eligible.sort(key=lambda d: (d['text_store'], d['item_id']))
    judge = sv2.Judge.load(sv2.ART / 'model.json')
    arms = defaultdict(dict)
    for it in eligible:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            arms[a][it['item_id']] = sc
        s = judge.score(it['goal'], all_texts(it))
        arms['specialist_v2'][it['item_id']] = {b['id']: s[j] for j, b in enumerate(it['blocks']) if not b['protected']}
    sub = lambda its: {a: {it['item_id']: v[it['item_id']] for it in its} for a, v in arms.items()}  # noqa: E731
    res = dict(schema='specialist-v2/test', protocol_sha256=sha(PROTOCOL),
               labels='next-action-v2 extractor applied to the frozen test split; generic features from v2 train groups',
               counts=dict(test_items=len(items_all), excluded=dict(skip), eligible=len(eligible),
                           fork_linked_to_train_or_dev=sum(1 for it in eligible if linked.get(it['item_id'])),
                           fork_linked_by_split=dict(Counter(s for it in eligible for s in linked.get(it['item_id'], ()))),
                           primary=len(primary), primary_groups=len({it['group'] for it in primary}),
                           primary_per_source=dict(Counter(it['source'] for it in primary)),
                           primary_candidates=sum(len(mb.cand_blocks(it)) for it in primary),
                           primary_used=sum(b['used'] for it in primary for b in mb.cand_blocks(it))))
    for name, its in (('primary', primary), ('all_eligible', eligible)):
        curves, per, by_src, by_cat = evaluate_set(its, sub(its))
        boot = {a: cluster_boot(its, per['specialist_v2'], per[a]) for a in BASELINES}
        res[name] = dict(items=len(its), curves=curves, by_source=by_src, by_category=by_cat, bootstrap=boot)
    # old specialist: seeded 12 per source of the primary items (~30 s per item on CPU)
    v1_ids = set(mb.model_ids(primary))
    v1_items = [it for it in primary if it['item_id'] in v1_ids]
    v1 = specialist_v1_scores(v1_items)
    sa = sub(v1_items)
    sa['specialist_v1'] = v1
    curves, per, by_src, _ = evaluate_set(v1_items, sa)
    res['specialist_v1_subset'] = dict(items=len(v1_items), curves=curves, by_source=by_src,
                                       bootstrap_vs_v1=cluster_boot(v1_items, per['specialist_v2'], per['specialist_v1']))
    # Jev: saved v0.1 scores on frozen-60 dossiers that fell in test (descriptive; no remote calls)
    j_items, j_sc = jev_test_overlap(eligible)
    if j_items:
        ja = sub(j_items)
        ja['jev'] = j_sc
        res['jev_test_overlap'] = dict(items=len(j_items), curves=evaluate_set(j_items, ja)[0])
    else:
        res['jev_test_overlap'] = dict(items=0)
    # edge suite + cost
    cases = es.load_cases()
    edge = mb.edge_results()
    sc = {c['id']: dict(zip([b['id'] for b in c['blocks']], judge.score(c['goal'], sv2.edge_texts(c)))) for c in cases}
    sm = es.summary(cases, es.run(cases, sc))
    edge['specialist_v2'] = {str(b): dict(passed=v['passed'], n=v['n'], failed=v['failed']) for b, v in sm.items()}
    res['edge_suite'] = edge
    res['cost'] = bench(sv2.ART / 'model.json', primary)
    ok1, r1 = gate_beats(res['primary']['bootstrap'], res['primary']['curves'])
    ok2, r2 = gate_edge(edge)
    ok3, r3 = gate_cost(res['cost'])
    res['acceptance'] = dict(i_beats_baselines=dict(ok=ok1, rows=r1), ii_edge=dict(ok=ok2, rows=r2),
                             iii_cost=dict(ok=ok3, rows=r3), verdict='PASS' if ok1 and ok2 and ok3 else 'FAIL')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / 'test-results.json').write_text(json.dumps(res, indent=1))
    (OUT / 'test_results.json').write_text(json.dumps(res, indent=1) + '\n')
    (OUT / 'TEST_RESULTS.md').write_text(render_md(res))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('protocol', 'run'))
    a = ap.parse_args(argv)
    out = protocol_phase() if a.phase == 'protocol' else run_phase()
    print(json.dumps(out if a.phase == 'protocol' else dict(counts=out['counts'], acceptance=out['acceptance']),
                     indent=1)[:6000])


if __name__ == '__main__':
    sys.exit(main())
