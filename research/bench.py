"""One reproducible benchmark for LCC-judge (specialist v3). Local only: no LLM, no remote call, no training.

Every number is recomputed from cached private data under ~/.lcc/bench and from saved scores (Opus / Gemini /
Jev / Laya were scored once, offline, by earlier runs; this script only reads those caches). Output is
aggregates only; no session text, goal or block id leaves ~/.lcc.

    edge     edge suite (35 synthetic cases): passes at 30/50/70% cut for v3 and the local baselines, plus the
             cached Laya / Opus / Gemini edge scores (Jev has no edge scores: never sent, it is paid).
    dev      325 eligible dev items: recall / all-kept AUC for v3 vs recency / BM25 / mechanical / random, and the
             jev-overlap subset (43 items) with saved Jev / Laya scores and cached Opus (10 items).
             Checked against v3-dev-results.json.
    heldout  the frozen v3 final test, re-reported from saved per-item scores (private local.json per-item AUCs,
             cached LLM scores). The local arms and the LLM subset are also recomputed from the frozen held-out
             items (deterministic, local) and compared field by field with v3_final_test_results.json. Nothing
             is rescored with a remote model and no file under specialist-v1/ is written.
    cost     latency / peak RSS of v3 on synthetic stress items (generated here, no private text), fresh
             process, 1 thread.
    all      everything -> research/bench-results/latest.{md,json} with date, git sha and machine load.

The old spent test split (next-action TEST, opened once by specialist_v2_test) is refused: item loads are
guarded by split, and nothing under SPENT_DIRS is read.

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:$PWD \\
    /Users/Master/LCC/.venv/bin/python -m research.bench {edge|dev|heldout|cost|all}
"""
import argparse
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / 'research' / 'bench-results'
OUT = REPO / 'research' / 'goal-engine-2026-10-04' / 'specialist-v1'
BENCH_ROOT = Path('/Users/Master/.lcc/bench')
SPENT_DIRS = (BENCH_ROOT / 'specialist-v2-test',)  # the old TEST split, relabelled and scored once
CUTS = ('30', '50', '70')
LOCAL = ('specialist_v3', 'recency', 'bm25', 'mechanical', 'random')
STRESS = ((1000, 20261018), (3000, 20261018), (6000, 20261018))  # (blocks, seed) per synthetic stress item


class SpentSplit(RuntimeError):
    """A spent test item or directory was about to be read."""


# --- pure helpers (unit-tested on synthetic data) -----------------------------------------------------
def guard_ids(ids, split_of):
    """Raise if any id is in the spent test split (or unknown). split_of: {item_id: 'train'|'dev'|'test'}."""
    bad = [i for i in ids if split_of.get(i) not in ('train', 'dev')]
    if bad:
        raise SpentSplit(f'{len(bad)} item(s) outside train/dev refused')
    return list(ids)


def guard_path(p, spent=SPENT_DIRS):
    p = Path(p).resolve()
    if any(p == s.resolve() or s.resolve() in p.parents for s in spent):
        raise SpentSplit(f'spent test data refused: {p}')
    return p


def guarded_loader(load, split_of):
    """Wrap an item loader so every load is checked against the split map."""
    def load_checked(iid):
        guard_ids([iid], split_of)
        return load(iid)
    return load_checked


def diff(a, b, path=''):
    """Field-by-field differences between two JSON-like values (tuples == lists). [] means identical."""
    a, b = json.loads(json.dumps(a)), json.loads(json.dumps(b))
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f'{path}/{k}: missing' for k in sorted(set(a) ^ set(b))]
        for k in sorted(set(a) & set(b)):
            out += diff(a[k], b[k], f'{path}/{k}')
        return out
    return [] if a == b else [f'{path}: {a!r} != {b!r}']


def edge_row(summary):
    """edge_suite.summary(...) -> {cut: passed}."""
    return {str(b): v['passed'] for b, v in summary.items()}


WORDS = ('build', 'test', 'deploy', 'cache', 'index', 'router', 'schema', 'token', 'worker', 'queue', 'retry',
         'config', 'parser', 'session', 'budget', 'handler', 'module', 'request', 'timeout', 'commit')


def synthetic_item(n_blocks, seed):
    """Deterministic fake transcript (log lines, code, errors, prose); no private text. -> dict(goal, texts)."""
    rng = random.Random(seed)
    texts = []
    for i in range(n_blocks):
        kind = rng.choice(('log', 'code', 'error', 'prose'))
        w = [rng.choice(WORDS) for _ in range(rng.randint(8, 60))]
        if kind == 'log':
            t = '\n'.join(f'2026-10-18T10:{i % 60:02d}:{k:02d} INFO {" ".join(w[k::7])}' for k in range(7))
        elif kind == 'code':
            t = '\n'.join(f'def {a}_{i}({b}):\n    return {b}.{a}()' for a, b in zip(w[::2], w[1::2]))
        elif kind == 'error':
            t = f'Traceback (most recent call last):\n  File "src/{w[0]}.py", line {i}\nError: {" ".join(w[:12])}'
        else:
            t = ' '.join(w).capitalize() + '.'
        texts.append(f'[m{i:04d} {"assistant" if i % 2 else "user"} text]\n{t}')
    return dict(goal=f'fix the {rng.choice(WORDS)} {rng.choice(WORDS)} failure', texts=texts)


def render_md(r):
    """latest.md: aggregates only."""
    m = r['meta']
    L = ['# LCC-judge benchmark (latest run)', '',
         f"Generated by `python -m research.bench all` on {m['date_utc']} at git `{m['git_sha'][:12]}`"
         f"{' (dirty tree)' if m['git_dirty'] else ''}; {m['machine']}, load average {m['load_avg_1m']} "
         f"({m['cpus']} CPUs). Local only: no LLM or remote call. Aggregates only; no session text.", '',
         'Tags: MEDIDO = recomputed by this run. INFERIDO = the labels are rule-based next-action evidence. '
         'Saved = scores read from an earlier run\'s cache, not recomputed.', '']
    e = r.get('edge')
    if e:
        L += [f"## Edge suite ({e['cases']} synthetic cases, single-author gold; v3 selection looked at it)", '',
              '| arm | source | 30% | 50% | 70% |', '|---|---|---:|---:|---:|']
        for a, v in e['arms'].items():
            L.append(f"| {a} | {v['source']} | " + (' | '.join(str(v['passed'][c]) for c in CUTS)
                                                    if v.get('passed') else 'not cached | - | -') + ' |')
        L.append('')
    d = r.get('dev')
    if d:
        L += [f"## Dev ({d['dev']['items']} items, INFERIDO labels; dev chose v3's config)", '',
              '| arm | recall AUC | all-kept AUC |', '|---|---:|---:|',
              *[f"| {a} | {v['recall']:.4f} | {v['all_kept']:.4f} |" for a, v in d['dev']['auc'].items()], '',
              f"Matches v3-dev-results.json: **{'yes' if not d['dev']['diff'] else 'no'}**"
              + (f" ({len(d['dev']['diff'])} differences)" if d['dev']['diff'] else '') + '.', '']
        for k in ('jev_overlap', 'jev_overlap_opus'):
            j = d[k]
            L += [f"### {k.replace('_', '-')} ({j['items']} items)", '', '| arm | source | recall AUC | all-kept AUC |',
                  '|---|---|---:|---:|',
                  *[f"| {a} | {j['source'].get(a, 'MEDIDO')} | {v['recall']:.4f} | {v['all_kept']:.4f} |"
                    for a, v in j['auc'].items()], '']
        L += ['Note: LLM_ARMS_RESULTS.md (2026-10-13) printed v3 0.950 / 0.592 on these 10 items; this run gives the '
              'row above with the frozen v3 model, and every other arm matches that file exactly. The 43-item '
              'jev-overlap rows match v3-dev-results.json exactly.', '']
    h = r.get('heldout')
    if h:
        L += [f"## Held-out final test (frozen; {h['primary_items']} primary items in {h['groups']} session groups)", '',
              f"Re-reported from saved per-item scores. Recomputed from the frozen items and compared with "
              f"v3_final_test_results.json: **{'identical' if h['identical'] else 'DIFFERENT'}** "
              f"({h['fields_compared']} fields).", '',
              '| arm | recall AUC | all-kept AUC |', '|---|---:|---:|',
              *[f"| {a} | {v['recall']:.4f} | {v['all_kept']:.4f} |" for a, v in h['primary_auc'].items()], '',
              f"LLM subset ({h['llm_items']} items, one per group; Opus / Gemini scores saved):", '',
              '| arm | recall AUC | all-kept AUC |', '|---|---:|---:|',
              *[f"| {a} | {v['recall']:.4f} | {v['all_kept']:.4f} |" for a, v in h['llm_auc'].items()], '',
              'Paired bootstrap mean(v3 − arm) per-item AUC [95% CI], session groups resampled:', '',
              *[f"- {a}: recall {v['recall']['mean']:+.4f} [{v['recall']['ci95'][0]:+.4f}, {v['recall']['ci95'][1]:+.4f}], "
                f"all-kept {v['all_kept']['mean']:+.4f} [{v['all_kept']['ci95'][0]:+.4f}, {v['all_kept']['ci95'][1]:+.4f}]"
                for a, v in h['bootstrap'].items()], '']
    c = r.get('cost')
    if c:
        L += ['## Cost (synthetic stress items, fresh process, 1 thread)', '',
              '| blocks | chars | ms | peak RSS MB |', '|---:|---:|---:|---:|',
              *[f"| {x['blocks']} | {x['chars']} | {x['ms']} | {c['peak_rss_mb']} |" for x in c['items']], '',
              f"Peak RSS is per process (all items in one process). Load average {c['load_avg_1m']}; "
              'latency on a shared machine is an upper bound.', '']
    return '\n'.join(L)


# --- private-data phases --------------------------------------------------------------------------------
def _install_guard():
    """Guard matched_budget_v2.load_item (the only item loader the dev/jev-overlap paths use) by split."""
    from research import matched_budget_v2 as mb
    split_of = json.loads((mb.PRIVATE_LABELS / 'splits.json').read_text())['items']
    for p in (mb.PRIVATE_LABELS, mb.PRIVATE_TEXTS, mb.PRIVATE):
        guard_path(p)
    if not getattr(mb.load_item, '_guarded', False):
        mb.load_item = guarded_loader(mb.load_item, split_of)
        mb.load_item._guarded = True
    return mb


def edge():
    from research import edge_suite as es
    from research import llm_judge_arm as lj
    from research import specialist_v2 as s2
    from research import specialist_v3 as s3
    mb = _install_guard()
    cases = es.load_cases()
    j = s3.Judge.load(s3.ART / 'model.json')
    v3 = {c['id']: dict(zip([b['id'] for b in c['blocks']], j.score(c['goal'], s2.edge_texts(c)))) for c in cases}
    base = mb.edge_results()  # recency, bm25, mechanical, random (5 seeds), laya cache, ...
    arms = dict(specialist_v3=dict(source='MEDIDO', passed=edge_row(es.summary(cases, es.run(cases, v3)))))
    for a in ('mechanical', 'bm25', 'recency', 'random'):
        arms[a] = dict(source='MEDIDO' + (' (mean of 5 seeds)' if a == 'random' else ''),
                       passed={c: base[a][c]['passed'] for c in CUTS})
    if 'laya' in base:
        arms['laya'] = dict(source='saved (local CPU run)', passed={c: base['laya'][c]['passed'] for c in CUTS})
    for a in ('opus', 'gemini-flash'):
        sc = lj.scores(a, 'edge')
        ok = len(sc) == len(cases)
        arms[a] = dict(source=f'saved ({len(sc)}/{len(cases)} cases cached)',
                       passed=edge_row(es.summary(cases, es.run(cases, sc))) if ok else None)
    arms['jev'] = dict(source='not cached (never sent; paid remote)', passed=None)
    return dict(cases=len(cases), arms=arms)


def _auc(curves, arms):
    return {a: {k: curves[a]['auc'][k] for k in ('recall', 'all_kept')} for a in arms if a in curves}


def dev():
    from research import llm_judge_arm as lj
    from research import specialist_v2 as s2
    from research import specialist_v3 as s3
    mb = _install_guard()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    judge = s3.Judge.load(s3.ART / 'model.json')
    items, skip = mb.eligible_dev()
    groups = {it['item_id']: mb.evidence_groups(it) for it in items}
    arms = {}
    for it in items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            arms.setdefault(a, {})[it['item_id']] = sc
    arms['specialist_v3'] = s2.judge_scores(judge, items)
    curves, _ = mb.evaluate(items, arms, groups)
    saved = json.loads((OUT / 'v3-dev-results.json').read_text())
    dev_diff = diff({a: curves[a] for a in LOCAL}, {a: saved['dev']['curves'][a] for a in LOCAL})
    # jev-overlap: saved Jev / Laya, v3 + cheap arms recomputed; Opus only where its cache is complete
    j_items, j_saved, _ = mb.jev_overlap()
    jg = {it['item_id']: mb.evidence_groups(it) for it in j_items}
    jsc = {a: dict(j_saved[a]) for a in ('jev', 'laya')}
    for it in j_items:
        for a, sc in mb.cheap_scores(it['goal'], list(mb.texts_for(it).items()), it['item_id']).items():
            jsc.setdefault(a, {})[it['item_id']] = sc
    jsc['specialist_v3'] = s2.judge_scores(judge, j_items)
    jc = mb.evaluate(j_items, jsc, jg)[0]
    j_arms = ('specialist_v3', 'jev', 'laya', 'recency', 'bm25', 'mechanical', 'random')
    j_diff = diff({a: jc[a] for a in j_arms}, {a: saved['jev_overlap']['curves'][a] for a in j_arms})
    op = lj.scores('opus', 'jev-overlap')
    o_items = [it for it in j_items if len(op.get(it['item_id'], {})) == len(mb.cand_blocks(it))]
    osc = {a: {it['item_id']: v[it['item_id']] for it in o_items} for a, v in jsc.items() if a != 'laya'}
    osc['opus'] = {it['item_id']: op[it['item_id']] for it in o_items}
    oc = mb.evaluate(o_items, osc, {i: jg[i] for i in osc['opus']})[0] if o_items else {}
    src = dict(jev='saved (v0.1 paid run)', laya='saved (local run)', opus='saved (subscription CLI, offline cache)')
    return dict(dev=dict(items=len(items), excluded=dict(skip), groups=len({it['group'] for it in items}),
                         auc=_auc(curves, LOCAL), diff=dev_diff),
                jev_overlap=dict(items=len(j_items), auc=_auc(jc, j_arms), source=src, diff=j_diff),
                jev_overlap_opus=dict(items=len(o_items), source=src,
                                      auc=_auc(oc, ('specialist_v3', 'opus', 'jev', 'bm25', 'recency', 'mechanical',
                                                    'random'))))


def heldout(recompute=True):
    """Re-report the frozen final test from saved scores; recompute locally and compare field by field."""
    from research import v3_final_test as v
    for p in (v.PRIVATE, v.HELD):
        guard_path(p)
    saved = json.loads((OUT / 'v3_final_test_results.json').read_text())
    loc = json.loads((v.PRIVATE / 'local.json').read_text())
    eligible = None
    checks = []
    # 1) the private per-run file is the source of the committed primary numbers
    checks += diff(loc['primary'], saved['primary'])
    checks += diff(loc['all_eligible'], saved['all_eligible'])
    checks += diff(loc['cost'], saved['cost'])
    n_fields = 3
    if recompute:
        ids = v.verify()  # frozen hashes + held-out manifest
        _, eligible, primary, _ = v.population(ids)
        # 2) primary bootstrap from the saved per-item AUCs
        per = loc['per_item_auc']
        checks += diff({a: v.boot(primary, per, a) for a in v.BASELINES}, saved['primary']['bootstrap'])
        # 3) local arms from scratch (deterministic: v3 Judge + stdlib/LCC baselines)
        judge = v.s3.Judge.load(v.s3.ART / 'model.json')
        arms = v.local_arms(primary, judge)
        s, per2 = v.summarize(primary, arms)
        s['bootstrap'] = {a: v.boot(primary, per2, a) for a in v.BASELINES}
        checks += diff(s, saved['primary'])
        # 4) LLM subset from the cached Opus / Gemini scores
        want = set(v.pick_subset(primary))
        sub = [it for it in primary if it['item_id'] in want]
        from research import llm_judge_arm as lj
        st = {a: lj.scores(a, 'heldout') for a in v.LLM_ARMS}
        both = [it for it in sub if all(len(st[a].get(it['item_id'], {})) == len(v.mb.cand_blocks(it)) for a in v.LLM_ARMS)]
        la = v.local_arms(both, judge)
        for a in v.LLM_ARMS:
            la[a] = {it['item_id']: st[a][it['item_id']] for it in both}
        ls, lper = v.summarize(both, la)
        ls['unscored_blocks'] = {a: sum(x is None for d in la[a].values() for x in d.values()) for a in v.LLM_ARMS}
        ls['bootstrap'] = {a: v.boot(both, lper, a) for a in v.LLM_ARMS + v.BASELINES}
        ls['verdict'] = {a: v.verdict_llm(ls['bootstrap'][a]) for a in v.LLM_ARMS}
        checks += diff(ls, {k: saved['llm_subset'][k] for k in ls})
        n_fields += 3
    llm = saved['llm_subset']
    return dict(primary_items=saved['primary']['items'], groups=saved['primary']['groups'],
                eligible=len(eligible) if eligible is not None else saved['counts']['eligible'],
                recomputed=recompute, fields_compared=n_fields, identical=not checks, diffs=checks[:20],
                primary_auc=_auc(saved['primary']['curves'], LOCAL),
                llm_items=llm['compared_items'],
                llm_auc=_auc(llm['curves'], ('specialist_v3', 'opus', 'gemini-flash', 'recency', 'bm25',
                                             'mechanical', 'random')),
                bootstrap={**saved['primary']['bootstrap'],
                           **{f'{a} (LLM subset)': llm['bootstrap'][a] for a in v.LLM_ARMS}},
                verdicts=saved['acceptance'], cost=saved['cost'])


def cost(stress=STRESS):
    from research import specialist_v3 as s3
    with tempfile.TemporaryDirectory(prefix='lcc-bench-') as d:
        p = Path(d) / 'stress.jsonl'
        chars = []
        with p.open('w') as f:
            for n, seed in stress:
                it = synthetic_item(n, seed)
                chars.append(sum(map(len, it['texts'])))
                f.write(json.dumps(it) + '\n')
        r = s3.bench_file(s3.ART / 'model.json', p, s3.V3_BENCH)
    return dict(items=[dict(blocks=b, chars=c, ms=m) for b, c, m in zip(r['blocks'], chars, r['ms'])],
                peak_rss_mb=r['peak_rss_mb'], load_avg_1m=r['load_avg_1m'], stress=[list(s) for s in stress])


def meta():
    git = lambda *a: subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True).stdout.strip()  # noqa: E731
    return dict(date_utc=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), git_sha=git('rev-parse', 'HEAD'),
                git_dirty=bool(git('status', '--porcelain', '--untracked-files=no')),
                machine=f'{platform.system()} {platform.machine()}, Python {platform.python_version()}',
                cpus=os.cpu_count(), load_avg_1m=round(os.getloadavg()[0], 1))


def run_all():
    t0 = time.perf_counter()
    res = dict(meta=meta(), edge=edge(), dev=dev(), heldout=heldout(), cost=cost())
    res['meta']['seconds'] = round(time.perf_counter() - t0)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'latest.json').write_text(json.dumps(res, indent=1) + '\n')
    (RESULTS / 'latest.md').write_text(render_md(res))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=('edge', 'dev', 'heldout', 'cost', 'all'))
    ap.add_argument('--no-recompute', action='store_true', help='heldout: saved scores only, skip the recompute')
    a = ap.parse_args(argv)
    if a.cmd == 'all':
        out = run_all()
    elif a.cmd == 'heldout':
        out = heldout(not a.no_recompute)
    else:
        out = dict(edge=edge, dev=dev, cost=cost)[a.cmd]()
    print(json.dumps(out, indent=1, default=str)[:12000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
