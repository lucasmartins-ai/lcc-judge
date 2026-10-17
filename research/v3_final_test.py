"""Specialist v3: the one pre-registered final test on the post-cutoff held-out set (heldout_v3).

Protocol: research/goal-engine-2026-10-04/specialist-v1/V3_FINAL_TEST_PROTOCOL.md (pushed before the build).
This script only READS the frozen modules (specialist_v3, specialist_v2, llm_judge_arm, heldout_v3) and the
frozen model; every phase refuses to run if a pre-registered sha256 differs, or if the held-out items differ
from the build receipt. No training, tuning or model choice happens here.

    verify -> hashes + held-out manifest check
    local  -> v3, recency, BM25, mechanical, random (5 seeds) on every eligible item + cost (fresh process,
              1 thread, primary items) -> PRIVATE/local.json (per-item AUCs stay private). Runs once.
    final  -> LLM subset (Opus / Gemini caches from llm_judge_arm --set heldout), bootstrap, verdicts ->
              OUT/v3_final_test_results.json + OUT/V3_FINAL_TEST_RESULTS.md (counts / aggregates only). Runs once.

The LLM subset (llm_set) is what `llm_judge_arm --set heldout` sends: one primary item per session group,
picked with random.Random(20261016).choice over the group's sorted item ids, groups in sorted order, at most
40 (the first 40 groups in sorted order if there are more).

    PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.v3_final_test {verify|local|final}
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from research import heldout_v3 as hv
from research import matched_budget_v2 as mb
from research import specialist_v2_test as t
from research import specialist_v3 as s3

REPO = Path(__file__).resolve().parents[1]
OUT = s3.OUT
HELD = hv.PRIVATE
PRIVATE = Path('/Users/Master/.lcc/bench/v3-final-test')
RECEIPT = OUT / 'heldout-v3-receipt.json'
SEED = 20261016
BOOT = 2000
SUBSET_MAX = 40
BASELINES = ('recency', 'bm25', 'mechanical')
LLM_ARMS = ('opus', 'gemini-flash')
CALL_CAP = 2500
NI_MARGIN = -0.02
LIMITS = t.LIMITS  # median 250 ms, p90 1000 ms, peak RSS 300 MB (same as the v2 protocol)
EDGE = dict(specialist_v3=(28, 23, 20), opus=(35, 35, 35), gemini_flash=(35, 35, 34))  # stated; not re-run
FROZEN = {
    str(s3.ART / 'model.json'): '219cd798d47f39d18249597892c92f0772d7946ed59610d5b86b8500fa1b51f7',
    'research/specialist_v3.py': 'fff2c201225627dd30348c8259190790c3a17b43e8d3abea63c460c67881a21e',
    'research/specialist_v2.py': '6638809ed9b58c832ea6c36e22b88665b7857f8b2eb816dbc4935ee0c3ac01f9',
    'research/heldout_v3.py': 'ac6efb45755aff83b86edb40e0b938672d5ee54f80f8c4b5f716a87a8f243e0e',
}
# llm_judge_arm.py was frozen at e203ec94...; the protocol allows one change (the --set heldout selector).
LLM_ARM_FROZEN = 'e203ec94c405db7f53dcc6023b4e27d8e29a91715fa9d87c7f45a5926d5e19ee'
EVAL_CODE = ('research/v3_final_test.py', 'research/llm_judge_arm.py')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def code_hashes():
    return {p: sha(REPO / p) for p in EVAL_CODE}


def verify(check_items=True):
    bad = [p for p, h in FROZEN.items() if sha(REPO / p) != h]
    if bad:
        raise SystemExit(f'frozen file changed: {bad}')
    if not check_items:
        return []
    rec = json.loads(RECEIPT.read_text())
    lines = (HELD / 'manifest-heldout.txt').read_text()
    if hashlib.sha256(lines.encode()).hexdigest() != rec['sha256']['items_manifest']:
        raise SystemExit('held-out manifest differs from the receipt')
    rows = [x.split() for x in lines.splitlines()]
    bad = [i for i, h in rows if sha(HELD / 'items' / f'{i}.json') != h]
    if bad:
        raise SystemExit(f'{len(bad)} held-out items changed since the build')
    return [i for i, _ in rows]


# --- data ------------------------------------------------------------------------------------------
_TX = {}


def store(st):
    if st not in _TX:
        _TX.clear()  # ponytail: one store cached; items are iterated grouped by store
        _TX[st] = json.loads((HELD / 'texts' / f'{st}.json').read_text())
    return _TX[st]


def all_texts(it):
    s = store(it['text_store'])
    return [s.get(b['id']) or '' for b in it['blocks']]


def cand_pairs(it):
    s = store(it['text_store'])
    return [(b['id'], s[b['id']]) for b in mb.cand_blocks(it)]


def population(ids=None):
    """-> (all items, eligible, primary, exclusion counts). Primary = eligible minus content-linked."""
    ids = verify() if ids is None else ids
    items = [json.loads((HELD / 'items' / f'{i}.json').read_text()) for i in ids]
    linked = set(json.loads((HELD / 'content-linked-train-dev.json').read_text()))
    skip, eligible = Counter(), []
    for it in items:
        if it['evidence'] != 'actions':
            skip['no_agent_action'] += 1
        elif not mb.eligible(it):
            skip['no_used_candidate'] += 1
        else:
            eligible.append(it)
    key = lambda d: (d['text_store'], d['item_id'])  # noqa: E731
    eligible.sort(key=key)
    primary = [it for it in eligible if it['item_id'] not in linked]
    return items, eligible, primary, skip


def pick_subset(primary, seed=SEED, cap=SUBSET_MAX):
    """One item per session group: Random(seed).choice over the group's sorted ids, groups sorted, <= cap."""
    by = defaultdict(list)
    for it in primary:
        by[it['group']].append(it['item_id'])
    rng = random.Random(seed)
    return sorted(rng.choice(sorted(by[g])) for g in sorted(by)[:cap])


def llm_set():
    """[(item_id, goal, [(block_id, text)])] for llm_judge_arm --set heldout (candidate blocks only)."""
    _, _, primary, _ = population()
    want = set(pick_subset(primary))
    return [(it['item_id'], it['goal'], cand_pairs(it)) for it in primary if it['item_id'] in want]


# --- arms + metrics --------------------------------------------------------------------------------
def local_arms(items, judge):
    arms = defaultdict(dict)
    for it in items:
        for a, sc in mb.cheap_scores(it['goal'], cand_pairs(it), it['item_id']).items():
            arms[a][it['item_id']] = sc
        s = judge.score(it['goal'], all_texts(it))
        arms['specialist_v3'][it['item_id']] = {b['id']: s[j] for j, b in enumerate(it['blocks']) if not b['protected']}
    return arms


def boot(items, per, a, b='specialist_v3', seed=SEED, n=BOOT):
    return t.cluster_boot(items, per[b], per[a], seed=seed, n=n)


def verdict_local(bt):
    rows = {f'{a}:{k}': bt[a][k]['ci95'][0] > 0 for a in BASELINES for k in ('recall', 'all_kept')}
    return all(rows.values()), rows


def verdict_llm(b):
    """b: cluster_boot result for v3 - generalist -> per-metric verdict + headline."""
    v = {}
    for k in ('recall', 'all_kept'):
        lo = b[k]['ci95'][0]
        v[k] = 'superior' if lo > 0 else 'not inferior' if lo > NI_MARGIN else 'inferior'
    v['headline_superior'] = v['recall'] == 'superior' and v['all_kept'] in ('superior', 'not inferior')
    return v


def cost(items):
    """Fresh process, 1 thread, one item in memory: specialist_v2_test.bench with the v3 Judge and the
    held-out texts (same method as the v2 frozen test)."""
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = (t.all_texts, t.sv2.BENCH, t.PRIVATE)
    t.all_texts, t.sv2.BENCH, t.PRIVATE = all_texts, s3.V3_BENCH, PRIVATE
    try:
        return t.bench(s3.ART / 'model.json', items)
    finally:
        t.all_texts, t.sv2.BENCH, t.PRIVATE = saved


def gate_cost(c):
    return t.gate_cost(c)


def summarize(items, arms):
    curves, per, by_src, by_cat = t.evaluate_set(items, arms)
    return dict(items=len(items), groups=len({it['group'] for it in items}),
                curves={a: dict(auc=c['auc'], **{b: c[b] for b in ('10', '30', '60')}) for a, c in curves.items()},
                by_source=by_src, by_category=by_cat), per


# --- phases ----------------------------------------------------------------------------------------
def local_phase():
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    p = PRIVATE / 'local.json'
    if p.exists():
        raise SystemExit(f'{p} exists: the local arms run once')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    ids = verify()
    items, eligible, primary, skip = population(ids)
    judge = s3.Judge.load(s3.ART / 'model.json')
    arms = local_arms(eligible, judge)
    sub = lambda its: {a: {it['item_id']: v[it['item_id']] for it in its} for a, v in arms.items()}  # noqa: E731
    res = dict(counts=dict(items=len(items), excluded=dict(skip), eligible=len(eligible),
                           content_linked=len(eligible) - len(primary), primary=len(primary),
                           primary_groups=len({it['group'] for it in primary}),
                           primary_per_source=dict(Counter(it['source'] for it in primary)),
                           primary_candidates=sum(len(mb.cand_blocks(it)) for it in primary),
                           primary_used=sum(b['used'] for it in primary for b in mb.cand_blocks(it))))
    for name, its in (('primary', primary), ('all_eligible', eligible)):
        if not its:
            res[name] = dict(items=0)
            continue
        s, per = summarize(its, sub(its))
        s['bootstrap'] = {a: boot(its, per, a) for a in BASELINES}
        res[name] = s
        if name == 'primary':
            res['per_item_auc'] = per  # private only
    res['cost'] = cost(primary)
    res['eval_code_sha256'] = code_hashes()
    p.write_text(json.dumps(res, indent=1))
    os.chmod(p, 0o600)
    return {k: v for k, v in res.items() if k != 'per_item_auc'}


def llm_status():
    from research import llm_judge_arm as lj
    out = {}
    for a in LLM_ARMS:
        d = lj.ROOT / a / 'heldout'
        out[a] = dict(scores=lj.scores(a, 'heldout'),
                      batches_cached=sum(1 for _ in d.glob('*/batch-*.json')) if d.exists() else 0)
    return out


def final_phase(calls=None, waits=None):
    jp = OUT / 'v3_final_test_results.json'
    if jp.exists():
        raise SystemExit(f'{jp} exists: the final test is evaluated once')
    ids = verify()
    loc = json.loads((PRIVATE / 'local.json').read_text())
    _, _, primary, _ = population(ids)
    judge = s3.Judge.load(s3.ART / 'model.json')
    want = set(pick_subset(primary))
    subset = [it for it in primary if it['item_id'] in want]
    st = llm_status()
    done = {a: {it['item_id'] for it in subset if len(st[a]['scores'].get(it['item_id'], {})) == len(mb.cand_blocks(it))}
            for a in LLM_ARMS}
    both = [it for it in subset if all(it['item_id'] in done[a] for a in LLM_ARMS)]
    llm = dict(subset_items=len(subset), subset_groups=len({it['group'] for it in subset}),
               finished={a: len(done[a]) for a in LLM_ARMS}, compared_items=len(both),
               batches_cached={a: st[a]['batches_cached'] for a in LLM_ARMS}, calls=calls or {}, limit_waits=waits or {},
               call_cap=CALL_CAP)
    if both:
        arms = local_arms(both, judge)
        for a in LLM_ARMS:
            arms[a] = {it['item_id']: st[a]['scores'][it['item_id']] for it in both}
        s, per = summarize(both, arms)
        s['unscored_blocks'] = {a: sum(v is None for x in arms[a].values() for v in x.values()) for a in LLM_ARMS}
        s['bootstrap'] = {a: boot(both, per, a) for a in LLM_ARMS + BASELINES}
        s['verdict'] = {a: verdict_llm(s['bootstrap'][a]) for a in LLM_ARMS}
        llm.update(s)
    ok1, r1 = verdict_local(loc['primary']['bootstrap'])
    ok3, r3 = gate_cost(loc['cost'])
    res = dict(schema='specialist-v3/final-test', tag='INFERIDO (rule-based next-action labels)',
               protocol_sha256=sha(OUT / 'V3_FINAL_TEST_PROTOCOL.md'), frozen_sha256=FROZEN,
               llm_judge_arm_frozen_sha256=LLM_ARM_FROZEN, eval_code_sha256=loc['eval_code_sha256'],
               receipt=json.loads(RECEIPT.read_text()), counts=loc['counts'], primary=loc['primary'],
               all_eligible=loc['all_eligible'], cost=loc['cost'], llm_subset=llm,
               edge_suite_stated=dict(cuts=(30, 50, 70), **EDGE, note='repeated from the protocol, not re-run'),
               acceptance=dict(i_local_baselines=dict(ok=ok1, rows=r1),
                               ii_generalists=llm.get('verdict', 'not run: no item finished by both arms'),
                               iii_cost=dict(ok=ok3, rows=r3)))
    jp.write_text(json.dumps(res, indent=1) + '\n')
    (OUT / 'V3_FINAL_TEST_RESULTS.md').write_text(render_md(res))
    return res['acceptance']


# --- report ----------------------------------------------------------------------------------------
def _bt(v):
    return (f"recall {v['recall']['mean']:+.4f} [{v['recall']['ci95'][0]:+.4f}, {v['recall']['ci95'][1]:+.4f}], "
            f"all-kept {v['all_kept']['mean']:+.4f} [{v['all_kept']['ci95'][0]:+.4f}, {v['all_kept']['ci95'][1]:+.4f}]")


def _auc_table(curves, arms):
    L = ['| arm | recall AUC | all-kept AUC | recall @30% | all-kept @30% | recall @60% | all-kept @60% |',
         '|---|---:|---:|---:|---:|---:|---:|']
    for a in arms:
        if a in curves:
            c = curves[a]
            L.append(f"| {a} | {c['auc']['recall']:.4f} | {c['auc']['all_kept']:.4f} | {c['30']['recall']:.4f} | "
                     f"{c['30']['all_kept']:.4f} | {c['60']['recall']:.4f} | {c['60']['all_kept']:.4f} |")
    return L


def _split_table(rows, arms, label):
    L = [f'| {label} | n | ' + ' | '.join(f'{a} recall / all-kept' for a in arms) + ' |',
         '|---' * (2 + len(arms)) + '|']
    for k, v in rows.items():
        L.append(f"| {k} | {v['n']} | " + ' | '.join(f"{v[a]['recall']:.3f} / {v[a]['all_kept']:.3f}" for a in arms) + ' |')
    return L


def render_md(r):
    yn = lambda ok: 'PASS' if ok else 'FAIL'  # noqa: E731
    c, a, k, llm = r['counts'], r['acceptance'], r['cost'], r['llm_subset']
    local = ('specialist_v3', 'recency', 'bm25', 'mechanical', 'random')
    L = ['# Specialist v3: final test on the post-cutoff held-out set', '',
         'Generated once by `python -m research.v3_final_test final` under V3_FINAL_TEST_PROTOCOL.md (sha256 '
         f"{r['protocol_sha256'][:16]}...). Counts and aggregates only; no session text. No tuning after the build.", '',
         '## Limits (read first)', '',
         '- INFERIDO: labels are rule-based next-action evidence (what the agent reused next), which favours v3\'s '
         'training target. The generalists judge generic relevance. This measures fit to the owner\'s sessions, not '
         'general reading skill.',
         f"- Small sample: {c['primary']} primary items in {c['primary_groups']} session groups; the LLM subset has "
         f"{llm['subset_items']} items (one per group). CIs are wide.",
         f"- Latency and RSS measured on a shared machine (load average {k['load_avg_1m']}).",
         '- Session groups are the resampling unit of the paired bootstrap (2000 resamples, seed 20261016).', '',
         '## Verdicts (MEDIDO on this set; interpretation INFERIDO)', '',
         f"1. Local baselines (CI lower bound > 0, both metrics, each baseline): **{yn(a['i_local_baselines']['ok'])}** — "
         + '; '.join(f'{x} {yn(v)}' for x, v in a['i_local_baselines']['rows'].items()) + '.']
    if isinstance(a['ii_generalists'], dict):
        for arm, v in a['ii_generalists'].items():
            L.append(f"2. v3 vs {arm} ({llm['compared_items']} items): recall **{v['recall']}**, all-kept "
                     f"**{v['all_kept']}**; headline \"superior\": **{'yes' if v['headline_superior'] else 'no'}** "
                     f"({_bt(llm['bootstrap'][arm])}).")
    else:
        L.append(f"2. Generalists: {a['ii_generalists']}.")
    L += ['3. Cost: **' + yn(a['iii_cost']['ok']) + '** — ' + '; '.join(
        f"{x} {v['value']} (limit {v['limit']}) {yn(v['ok'])}" for x, v in a['iii_cost']['rows'].items()) + '.', '',
          '## Population', '',
          f"- Build receipt: {r['receipt']['items']} items, {r['receipt']['groups']} groups, per source "
          f"{json.dumps(r['receipt']['per_source'])}, manifest sha256 {r['receipt']['sha256']['items_manifest'][:16]}....",
          f"- Excluded {json.dumps(c['excluded'])}; eligible {c['eligible']}; content-linked to train/dev "
          f"{c['content_linked']}; primary {c['primary']} in {c['primary_groups']} groups, per source "
          f"{json.dumps(c['primary_per_source'])}; {c['primary_candidates']} candidate blocks, {c['primary_used']} USED.", '',
          f"## Primary ({r['primary']['items']} items): all local arms", '', *_auc_table(r['primary']['curves'], local), '',
          'Paired bootstrap mean(v3 − arm) per-item AUC [95% CI]: ' + '; '.join(
              f'{b}: {_bt(v)}' for b, v in r['primary']['bootstrap'].items()) + '.', '',
          *_split_table(r['primary']['by_source'], local[:-1], 'source'), '',
          *_split_table(r['primary']['by_category'], local[:-1], 'category'), '']
    if r['all_eligible'].get('items'):
        L += [f"## All eligible ({r['all_eligible']['items']} items; secondary)", '',
              *_auc_table(r['all_eligible']['curves'], local), '',
              'Bootstrap v3 − arm: ' + '; '.join(f'{b}: {_bt(v)}' for b, v in r['all_eligible']['bootstrap'].items()) + '.', '']
    L += [f"## LLM subset ({llm['subset_items']} items, {llm['subset_groups']} groups)", '',
          f"- Finished: {json.dumps(llm['finished'])}; compared on {llm['compared_items']} items finished by both arms. "
          f"Batches cached (= successful CLI calls): {json.dumps(llm['batches_cached'])}; CLI calls made: "
          f"{json.dumps(llm['calls'])} (cap {llm['call_cap']} per arm); usage-limit waits: {json.dumps(llm['limit_waits'])}."]
    if llm.get('curves'):
        arms = ('specialist_v3', *LLM_ARMS, 'recency', 'bm25', 'mechanical', 'random')
        L += [f"- Unscored blocks (no valid answer): {json.dumps(llm['unscored_blocks'])}.", '',
              *_auc_table(llm['curves'], arms), '',
              'Paired bootstrap mean(v3 − arm) [95% CI]: ' + '; '.join(f'{b}: {_bt(v)}' for b, v in llm['bootstrap'].items())
              + '.', '', *_split_table(llm['by_source'], ('specialist_v3', *LLM_ARMS), 'source'), '',
              *_split_table(llm['by_category'], ('specialist_v3', *LLM_ARMS), 'category'), '']
    e = r['edge_suite_stated']
    L += ['## Edge suite (stated in the protocol; not a gate, not re-run)', '', '| arm | 30% | 50% | 70% |',
          '|---|---|---|---|', *[f'| {x} | ' + ' | '.join(map(str, e[x])) + ' |' for x in EDGE], '',
          '## Cost (fresh process, 1 thread, primary items)', '',
          f"- {k['items']} items (median {k['blocks_median']} blocks, max {k['blocks_max']}): median {k['ms_median']} ms, "
          f"p90 {k['ms_p90']} ms, max {k['ms_max']} ms, {k['over_1s']} over 1 s; peak RSS {k['peak_rss_mb']} MB; "
          f"load {k['load_ms']} ms; model {k['model_file_kb']} KB.", '',
          '## Code hashes', '',
          *[f'- `{p}` {h}' for p, h in r['eval_code_sha256'].items()],
          "- frozen: " + ', '.join(f'`{Path(p).name}` {h[:12]}' for p, h in r['frozen_sha256'].items())
          + f"; `llm_judge_arm.py` pre-change {r['llm_judge_arm_frozen_sha256'][:12]}.", '']
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('verify', 'local', 'final'))
    ap.add_argument('--calls', help='json {arm: CLI calls made}')
    ap.add_argument('--waits', help='json {arm: usage-limit waits}')
    a = ap.parse_args(argv)
    if a.phase == 'verify':
        out = dict(items=len(verify()), eval_code_sha256=code_hashes())
    elif a.phase == 'local':
        out = local_phase()
    else:
        out = final_phase(json.loads(a.calls) if a.calls else None, json.loads(a.waits) if a.waits else None)
    print(json.dumps(out, indent=1, default=str)[:8000])


if __name__ == '__main__':
    sys.exit(main())
