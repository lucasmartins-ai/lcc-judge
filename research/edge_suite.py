"""LCC edge-case suite: does an arm keep the MUST-KEEP evidence at a fixed drop budget?

Fixtures: tests/fixtures/edge_cases/<id>.json (synthetic, built by research.edge_cases_build). Each case has a
goal and ordered blocks (oldest first) with gold "must" | "may" | "one:<group>".

An arm is any judge that gives each block a score (higher = keep; null = could not score). Per case, the
suite drops the lowest-scored blocks (ties older first, unscored last; same rule as research.matched_budget)
until >= budget% of the case's tokens are removed. PASS iff every "must" block survives and every one:<group>
keeps at least one block. Tokens = ceil(chars / 4) (stdlib, no tokenizer).

    python3 -m research.edge_suite baselines [--budget 50]            # recency, bm25, random, oracle
    python3 -m research.edge_suite score --scores arm.json [--name x]  # {case_id: {block_id: score|null}}
    python3 -m research.edge_suite export --out cases.jsonl            # goal + blocks (no gold) for an arm

Stdlib only; no network.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from research.edge_cases_build import FIX, tok
from research.matched_budget import bm25_scores, drop_order, drops_at

BUDGETS = (30, 50, 70)


def load_cases(path=FIX):
    return [json.loads(p.read_text()) for p in sorted(Path(path).glob('*.json'))]


def score_case(case, scores, budget=50):
    """-> dict(pass, lost_must, lost_groups, removed). scores: {block_id: float|None}; missing = None."""
    ids = [b['id'] for b in case['blocks']]
    tokens = {b['id']: tok(b['text']) for b in case['blocks']}
    dropped, removed = drops_at(drop_order(ids, {i: scores.get(i) for i in ids}), tokens, budget)
    groups = defaultdict(list)
    for b in case['blocks']:
        if b['gold'].startswith('one:'):
            groups[b['gold']].append(b['id'])
    lost_must = [b['id'] for b in case['blocks'] if b['gold'] == 'must' and b['id'] in dropped]
    lost_groups = [g for g, m in groups.items() if set(m) <= dropped]
    return dict(passed=not lost_must and not lost_groups, lost_must=lost_must, lost_groups=lost_groups,
                removed=round(removed, 4))


def run(cases, scores_by_case, budgets=BUDGETS):
    """-> {budget: {case_id: result}}. A case absent from scores_by_case counts as all-unscored."""
    return {bud: {c['id']: score_case(c, scores_by_case.get(c['id'], {}), bud) for c in cases} for bud in budgets}


# --- reference arms -------------------------------------------------------------------------------------
def recency(case):
    return {b['id']: float(i) for i, b in enumerate(case['blocks'])}


def bm25(case):
    return bm25_scores(case['goal'], {b['id']: b['text'] for b in case['blocks']})


def oracle(case):
    seen, out = set(), {}
    for b in case['blocks']:  # one:<g>: keep the first member, the rest are tied with may-drop + 0.5
        g = b['gold']
        out[b['id']] = 1.0 if g == 'must' or (g.startswith('one:') and g not in seen) else (0.5 if g != 'may' else 0.0)
        seen.add(g)
    return out


def random_arm(seed):
    def arm(case):
        rng = random.Random(f'{seed}:{case["id"]}')
        return {b['id']: rng.random() for b in case['blocks']}
    return arm


def arm_scores(cases, fn):
    return {c['id']: fn(c) for c in cases}


# --- reporting -------------------------------------------------------------------------------------------
def summary(cases, res):
    """{budget: {'pass': k, 'n': n, 'by_category': {cat: [k, n]}, 'by_source': {...}, 'failed': [ids]}}"""
    out = {}
    for bud, per in res.items():
        cat, src = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
        for c in cases:
            ok = per[c['id']]['passed']
            for d, key in ((cat, c['category']), (src, c['source'])):
                d[key][0] += ok
                d[key][1] += 1
        out[bud] = dict(passed=sum(r['passed'] for r in per.values()), n=len(per), by_category=dict(cat),
                        by_source=dict(src), failed=sorted(i for i, r in per.items() if not r['passed']))
    return out


def table(cases, arms):
    """arms: {name: results}. Markdown table of pass k/n per budget."""
    head = '| arm | ' + ' | '.join(f'{b}%' for b in BUDGETS) + ' |\n|---|' + '---|' * len(BUDGETS)
    rows = [f'| {name} | ' + ' | '.join(f"{s[b]['passed']}/{s[b]['n']}" for b in BUDGETS) + ' |'
            for name, s in ((n, summary(cases, r)) for n, r in arms.items())]
    return '\n'.join([head] + rows)


def baselines(cases):
    arms = {'oracle': run(cases, arm_scores(cases, oracle)),
            'recency': run(cases, arm_scores(cases, recency)),
            'bm25': run(cases, arm_scores(cases, bm25))}
    seeds = [run(cases, arm_scores(cases, random_arm(s))) for s in range(5)]
    arms['random(seed 0)'] = seeds[0]
    mean = {b: sum(summary(cases, s)[b]['passed'] for s in seeds) / 5 for b in BUDGETS}
    return arms, mean


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('baselines')
    b.add_argument('--fixtures', default=str(FIX))
    s = sub.add_parser('score')
    s.add_argument('--scores', required=True)
    s.add_argument('--name', default='arm')
    s.add_argument('--fixtures', default=str(FIX))
    s.add_argument('--json', action='store_true', help='print per-case results as JSON')
    e = sub.add_parser('export')
    e.add_argument('--out', required=True)
    e.add_argument('--fixtures', default=str(FIX))
    a = ap.parse_args(argv)
    cases = load_cases(a.fixtures)
    if a.cmd == 'baselines':
        arms, mean = baselines(cases)
        print(table(cases, arms))
        print('random mean of 5 seeds: ' + ', '.join(f'{b}% {mean[b]:.1f}/{len(cases)}' for b in BUDGETS))
        for name, r in arms.items():
            print(f'{name} failed @50%: ' + (', '.join(summary(cases, r)[50]['failed']) or '-'))
    elif a.cmd == 'score':
        res = run(cases, json.loads(Path(a.scores).read_text()))
        print(table(cases, {a.name: res}))
        print(f'failed @50%: ' + (', '.join(summary(cases, res)[50]['failed']) or '-'))
        if a.json:
            print(json.dumps(dict(summary=summary(cases, res), cases=res), indent=1))
    else:
        with open(a.out, 'w') as f:
            for c in cases:
                f.write(json.dumps(dict(id=c['id'], goal=c['goal'],
                                        blocks=[{k: v for k, v in bl.items() if k != 'gold'} for bl in c['blocks']]),
                                   ensure_ascii=False) + '\n')
        print(f'wrote {len(cases)} cases to {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
