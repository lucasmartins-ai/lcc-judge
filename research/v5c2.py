"""v5 cycle 2: can a ranker (v3 / v5) choose WHAT `stashed` removes better than stashed's own rules, on tool outputs only?

Protocol: research/goal-engine-2026-10-04/specialist-v1/V5C2_PROTOCOL.md (frozen before any scoring; file hashes in
V5C2_PROTOCOL.json). Only tool-result blocks are scored: in LCC's tool-call mode user / assistant text and call inputs
never change, so tool outputs are the only thing any arm can remove.

Phases (private rows stay under ~/.lcc/bench/v5c2; the repo gets aggregates only):
    stash   (lcc pin 4719fde on PYTHONPATH) per dev item: rebuild the transcript from its LCC blocks, run
            rules_mode=stashed (natural cut) and lossy (protection reasons) -> PRIV/stash/<item>.json
    score   (lcc-main on PYTHONPATH, as v3/v5 select) every arm at stashed's matched budget -> PRIV/rows, results
    edge    dev-edge v2 restricted to tool-output gold, fixed 30/50/70% cuts of tool-output tokens (descriptive)
    bench   latency / RSS of v5c2 and v3 in the same run (fresh process, 1 thread, the dev items)
    model   writes the frozen v5c2 model file (before the protocol commit)

    PYTHONPATH=~/.lcc/bench/lcc-4719fde/src:. ~/LCC/.venv/bin/python -m research.v5c2 stash
    PYTHONPATH=~/.lcc/bench/real-context-v0/lcc-main/src:. ~/LCC/.venv/bin/python -m research.v5c2 score|edge|bench
"""
import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'research' / 'goal-engine-2026-10-04' / 'specialist-v1'
PRIV = Path.home() / '.lcc/bench/v5c2'
PIN = dict(worktree=str(Path.home() / '.lcc/bench/lcc-4719fde'), commit='4719fde')
SEED = 20261019
N_BOOT = 2000
CACHE_READ, CACHE_WRITE = 0.10, 1.25  # LCC compactor._CACHE_READ_FACTOR / _CACHE_WRITE_FACTOR
CT_EPS = 0.5  # cache-aware tie-break: scores in the same 0.5-logit bucket drop the LATER result first
ARMS = ('stashed', 'v3', 'v5c2', 'v5c2_ct', 'recency', 'bm25', 'mechanical')
CANDIDATES = ('v5c2', 'v5c2_ct', 'v3')  # arms that may replace stashed's choice (acceptance rule)
PROTECT_KEEP = ('kept_default', 'trim_guard_')  # lossy keeps without a hard protection: still stash-safe
HDR_SPLIT = re.compile(r'\n\n(\[m(\d{4,}) (user|assistant) ([a-z_]+)(?: ([^\]\n]*))?\])(?:\n|$)')
LEAD = re.compile(r'\[m(\d{4,}) (user|assistant) ([a-z_]+)(?: ([^\]\n]*))?\](?:\n|$)')


# --- transcript rebuild (pure) ----------------------------------------------------------------------------
class Rebuild(ValueError):
    pass


def rebuild(blocks, texts):
    """LCC blocks (item['blocks'] rows with src=[lo, hi] dossier indices) + their texts -> dossier blocks
    [dict(j, m, role, kind, tool, content, is_error, parts=[block idx])]. Blocks that continue a dossier block are
    joined with a blank line (the split point); a block spanning several dossier blocks is cut at its inner render
    headers, which must be exactly hi - lo. Raises Rebuild when the text does not fit the src map."""
    out, cur = [], -1
    for i, (b, t) in enumerate(zip(blocks, texts)):
        lo, hi = b['src']
        pieces = [t]
        if hi > lo:
            cuts = [m for m in HDR_SPLIT.finditer(t)]
            if len(cuts) != hi - lo:
                raise Rebuild(f'block {i}: {len(cuts)} inner headers for src {lo}-{hi}')
            pieces, last = [], 0
            for m in cuts:
                pieces.append(t[last:m.start()])
                last = m.start() + 2
            pieces.append(t[last:])
        for k, piece in enumerate(pieces):
            j = lo + k
            if j > cur:
                h = LEAD.match(piece)
                if not h or j != cur + 1:
                    raise Rebuild(f'block {i}: dossier block {j} has no header')
                out.append(dict(j=j, m=int(h.group(1)), role=h.group(2), kind=h.group(3), tool=h.group(4) or None,
                                content=piece[h.end():], is_error=b['is_error'], parts=[i]))
                cur = j
            else:
                out[-1]['content'] += '\n\n' + piece
                out[-1]['parts'].append(i)
                out[-1]['is_error'] = out[-1]['is_error'] or b['is_error']
    return out


def payload(dossier):
    """Dossier blocks -> compact_transcript payload; calls get ids c<j>, results pair FIFO with the oldest open call
    of the same tool (any tool if none). -> (payload, {result j: call id}, orphan result js)."""
    msgs, open_calls, res_of, orphans = {}, [], {}, []
    for d in dossier:
        m = msgs.setdefault(d['m'], dict(role=d['role'], text=[], toolUses=[], toolResults=[]))
        if d['kind'] == 'tool_use':
            try:
                inp = json.loads(d['content'])
            except ValueError:
                inp = None
            cid = f"c{d['j']}"
            m['toolUses'].append(dict(tool_use_id=cid, tool=d['tool'], input=inp if isinstance(inp, dict) else {}))
            open_calls.append((cid, d['tool']))
        elif d['kind'] == 'tool_result':
            k = next((x for x, c in enumerate(open_calls) if c[1] == d['tool']), 0 if open_calls else None)
            if k is None:
                orphans.append(d['j'])
                continue
            cid = open_calls.pop(k)[0]
            res_of[d['j']] = cid
            r = dict(tool_use_id=cid, text=d['content'])
            if d['is_error']:
                r['is_error'] = True
            m['toolResults'].append(r)
        else:
            m['text'].append(d['content'])
    pl = [dict(role=v['role'], text='\n'.join(v['text']), toolUses=v['toolUses'], toolResults=v['toolResults'])
          for _, v in sorted(msgs.items())]
    return pl, res_of, orphans


# --- matched budget + cache cost (pure) ---------------------------------------------------------------------
def drop_set(pool, score, budget, cache_tie=False):
    """pool: [(rid, tokens, first block index)]; score: {rid: float}. Drop lowest first until >= budget tokens.
    Ties (or, with cache_tie, scores in the same CT_EPS bucket): default older first; cache_tie later first."""
    if cache_tie:
        key = lambda r: (math.floor(score[r[0]] / CT_EPS), -r[2])  # noqa: E731
    else:
        key = lambda r: (score[r[0]], r[2])  # noqa: E731
    out, got = set(), 0
    for rid, tok, _ in sorted(pool, key=key):
        if got >= budget:
            break
        out.add(rid)
        got += tok
    return out


def item_metrics(it, removed, note_tokens):
    """it: dict(blocks=[(tokens, kind_is_metric, used, used_loose, rids)]) in context order, rids = frozenset of the
    result ids the block belongs to (empty for non-results; > 1 only for a block that spans results: it counts as
    removed when any of them is); removed: result ids.
    -> recall / all_kept over metric blocks, stash counts, cache cost (LCC formula)."""
    used_tok = sum(t for t, mt, u, _, _ in it['blocks'] if mt and u)
    kept_used = sum(t for t, mt, u, _, r in it['blocks'] if mt and u and not r & removed)
    used_removed = {x for t, mt, u, _, r in it['blocks'] if mt and u for x in r & removed}
    loose_removed = {x for t, mt, _, ul, r in it['blocks'] if mt and ul for x in r & removed}
    total = sum(t for t, *_ in it['blocks'])
    first, off = None, 0
    for t, _, _, _, r in it['blocks']:
        if r & removed:
            first = off
            break
        off += t
    removed_tok = sum(t for t, *_, r in it['blocks'] if r & removed)
    dropped = max(0, removed_tok - note_tokens * len(removed))
    inv = 0 if first is None else total - first
    be = round(inv * (CACHE_WRITE - CACHE_READ) / (dropped * CACHE_READ), 2) if inv and dropped else None
    return dict(recall=kept_used / used_tok if used_tok else 1.0, all_kept=not used_removed,
                used_results_stashed=len(used_removed), loose_results_stashed=len(loose_removed),
                removed_tokens=removed_tok, n_removed=len(removed), first_mutation_offset=first,
                invalidated_tokens=inv, break_even_reuses=be)


# --- stash phase (lcc pin) ----------------------------------------------------------------------------------
def stash_item(it, texts):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript_stash import stash_note, verify_stashed
    from lcc.token_budget import count_tokens
    try:
        dos = rebuild(it['blocks'], texts)
    except Rebuild as e:
        return dict(ok=False, why='rebuild', error=str(e)[:200])
    pl, res_of, orphans = payload(dos)
    out = {}
    for mode in ('stashed', 'lossy'):
        r = compact_transcript(TranscriptCompactionRequest(payload=pl, question=it['goal'], provider='rules',
                                                           rules_mode=mode))
        out[mode] = {d['id']: dict(decision=d.get('decision'), reason=d.get('reason'), src=d.get('source'),
                                   tokens=(d.get('stash') or {}).get('tokens')) for d in r.decisions}
        if mode == 'stashed':
            viol = verify_stashed(pl, messages_to_payload(r.messages))
            fail_safe = r.report.get('lossless_violations') or []
    if viol or fail_safe:
        return dict(ok=False, why='verify', violations=len(viol), fail_safe=len(fail_safe))
    note_tok = count_tokens(stash_note(12345, '0' * 64), 'gpt-4.1').value
    results = {}
    for d in dos:
        if d['kind'] != 'tool_result' or d['j'] in orphans:
            continue
        cid = res_of[d['j']]
        s, lo = out['stashed'].get(cid), out['lossy'].get(cid)
        results[cid] = dict(j=d['j'], parts=d['parts'], pinned=s is None or (s['reason'] or '').startswith('pinned'), stashed=bool(s and s['decision'] == 'replace'),
                            dedupe=bool(s and s['decision'] == 'dedupe'), s_reason=s and s['reason'],
                            lossy_reason=lo and lo['reason'], lossy_decision=lo and lo['decision'],
                            short=bool(s and s['reason'] == 'short_result_kept_whole'))
    return dict(ok=True, results=results, orphans=len(orphans), note_tokens=note_tok,
                dossier_blocks=len(dos))


def stash_phase(limit=None):
    from research import matched_budget_v2 as mb
    from research import real_context_bench as rcb
    from research import real_context_bench_v02 as v02
    from research import specialist_v2 as s2
    v02.check_lcc_rules(dict(worktree=PIN['worktree'], commit=subprocess.run(
        ['git', '-C', PIN['worktree'], 'rev-parse', PIN['commit']], capture_output=True, text=True,
        check=True).stdout.strip()))
    os.environ.update(rcb.load_protocol(REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
                                        / 'protocol.json')['privacy']['env'])
    os.environ['LCC_STASH_DIR'] = str(PRIV / 'stash-blobs')
    (PRIV / 'stash').mkdir(parents=True, exist_ok=True, mode=0o700)
    items, _ = mb.eligible_dev()
    c = Counter()
    with rcb.network_guard():
        for it, texts in s2.load_items([i['item_id'] for i in items][:limit]):
            p = PRIV / 'stash' / f"{it['item_id']}.json"
            if p.exists():
                c['cached'] += 1
                continue
            try:
                r = stash_item(it, texts)
            except Exception as e:  # noqa: BLE001 -- counted, never hidden
                r = dict(ok=False, why='error', error=f'{type(e).__name__}: {e}'[:300])
            p.write_text(json.dumps(r))
            c['ok' if r['ok'] else 'failed:' + r['why']] += 1
    return dict(c, guard_trips=rcb.GUARD['trips'])


# --- score phase -------------------------------------------------------------------------------------------
def model_path():
    return PRIV / 'model-v5c2.json'


def model_phase():
    from research import specialist_v5 as s5
    PRIV.mkdir(parents=True, exist_ok=True, mode=0o700)
    p = model_path()
    if p.exists():
        raise SystemExit(f'{p} exists: the v5c2 model is frozen')
    p.write_text(json.dumps(s5.build(3.0, cascade=True, translated_top=2)))
    return dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def block_scores(it, texts, judges):
    """{arm: [score per LCC block]} for the ranker arms (full-text scoring of every block, as live)."""
    from research import matched_budget_v2 as mb
    pairs = [(b['id'], t) for b, t in zip(it['blocks'], texts)]
    out = {a: j.score(it['goal'], texts) for a, j in judges.items()}
    out['recency'] = list(range(len(texts)))
    bm = mb.bm25_scores(it['goal'], dict(pairs))
    out['bm25'] = [bm.get(b['id'], 0.0) for b in it['blocks']]
    me = mb.mechanical_scores(it['goal'], pairs)
    out['mechanical'] = [me.get(b['id'], 0.0) for b in it['blocks']]
    return out


def score_item(it, texts, st, judges):
    """-> row: population flags + per-arm metrics at stashed's matched budget, or dict(eligible=False, why)."""
    res = st['results']
    rid_of = defaultdict(set)
    for cid, r in res.items():
        for i in r['parts']:
            rid_of[i].add(cid)
    rid_of = {i: frozenset(v) for i, v in rid_of.items()}
    tok_of = Counter({cid: sum(it['blocks'][i]['tokens'] for i in r['parts']) for cid, r in res.items()})
    stashed = {cid for cid, r in res.items() if r['stashed']}
    pool = [cid for cid, r in res.items() if not r['pinned'] and not r['dedupe'] and not r['short']
            and (r['stashed'] or r['lossy_decision'] != 'keep'
                 or (r['lossy_reason'] or '').startswith(PROTECT_KEEP))]
    dedupe = {cid for cid, r in res.items() if r['dedupe']}
    blocks = [(b['tokens'], b['kind'] == 'tool_result' and not b['protected'] and i in rid_of and not rid_of[i] & dedupe,
               b['used'], b['used_loose'], rid_of.get(i, frozenset())) for i, b in enumerate(it['blocks'])]
    view = dict(blocks=blocks)
    budget = sum(tok_of[c] for c in stashed)
    pool_set = set(pool)
    used_in_pool = any(mt and u and r & pool_set for _, mt, u, _, r in blocks)
    base = dict(item_id=it['item_id'], group=it['group'], source=it['source'], pool=len(pool), stashed=len(stashed),
                budget=budget, tool_tokens=sum(t for t, mt, *_ in blocks if mt),
                context_tokens=sum(t for t, *_ in blocks))
    if not budget:
        return dict(base, eligible=False, why='stashed_removes_nothing')
    if not used_in_pool:
        return dict(base, eligible=False, why='no_used_tool_output_in_pool')
    sc = block_scores(it, texts, judges)
    first = {c: min(r['parts']) for c, r in res.items()}
    arms = {'stashed': item_metrics(view, stashed, st['note_tokens'])}
    for a in ARMS[1:]:
        src = 'v5c2' if a == 'v5c2_ct' else a
        rs = {c: max(sc[src][i] for i in res[c]['parts']) for c in pool}
        drop = drop_set([(c, tok_of[c], first[c]) for c in pool], rs, budget, cache_tie=a == 'v5c2_ct')
        arms[a] = item_metrics(view, drop, st['note_tokens'])
    return dict(base, eligible=True, arms=arms)


def group_boot(rows, arm, ref, metric, seed=SEED, n=N_BOOT):
    from research import specialist_v3 as s3
    items = [dict(item_id=r['item_id'], group=r['group']) for r in rows]
    a = {r['item_id']: float(r['arms'][arm][metric]) for r in rows}
    b = {r['item_id']: float(r['arms'][ref][metric]) for r in rows}
    return s3.group_bootstrap(items, a, b, n=n, seed=seed)


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def summarise(rows):
    ok = [r for r in rows if r.get('eligible')]
    per = {}
    for a in ARMS:
        m = [r['arms'][a] for r in ok]
        per[a] = dict(recall=round(statistics.mean(x['recall'] for x in m), 4),
                      all_kept=round(statistics.mean(x['all_kept'] for x in m), 4),
                      used_results_stashed_mean=round(statistics.mean(x['used_results_stashed'] for x in m), 3),
                      items_with_used_stashed=sum(x['used_results_stashed'] > 0 for x in m),
                      loose_results_stashed_mean=round(statistics.mean(x['loose_results_stashed'] for x in m), 3),
                      removed_tokens_sum=sum(x['removed_tokens'] for x in m),
                      removed_results_mean=round(statistics.mean(x['n_removed'] for x in m), 2),
                      first_mutation_offset_median=med([x['first_mutation_offset'] for x in m]),
                      first_mutation_share_median=med([x['first_mutation_offset'] / r['context_tokens']
                                                       for x, r in zip(m, ok) if x['first_mutation_offset'] is not None]),
                      invalidated_tokens_median=med([x['invalidated_tokens'] for x in m]),
                      invalidated_tokens_sum=sum(x['invalidated_tokens'] for x in m),
                      break_even_reuses_median=med([x['break_even_reuses'] for x in m]))
    boot = {a: {k: group_boot(ok, a, 'stashed', k) for k in ('recall', 'all_kept')} for a in ARMS[1:]}
    by_src = {s: {a: dict(n=sum(r['source'] == s for r in ok),
                          recall=round(statistics.mean(r['arms'][a]['recall'] for r in ok if r['source'] == s), 4),
                          all_kept=round(statistics.mean(r['arms'][a]['all_kept'] for r in ok if r['source'] == s), 4))
                  for a in ARMS} for s in sorted({r['source'] for r in ok})}
    return ok, per, boot, by_src


def accept(per, boot, cost):
    out = {}
    s_inv = per['stashed']['invalidated_tokens_median']
    for a in CANDIDATES:
        b = boot[a]
        ni = all(b[m]['ci95'][0] > -0.005 for m in ('recall', 'all_kept'))
        sup = any(b[m]['ci95'][0] > 0 for m in ('recall', 'all_kept'))
        cache = per[a]['invalidated_tokens_median'] <= 1.10 * s_inv
        c = (cost or {}).get('v3' if a == 'v3' else 'v5c2') or {}
        budget = bool(c) and c['ms_median'] <= 250 and c['peak_rss_mb'] <= 300
        out[a] = dict(non_inferior=ni, superior_one=sup, cache_ok=cache, budget_ok=budget,
                      replaces_stashed=ni and sup and cache and budget)
    return out


def score_phase():
    from research import matched_budget_v2 as mb
    from research import specialist_v2 as s2
    from research import specialist_v3 as s3
    from research import specialist_v5 as s5
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    judges = {'v3': s3.Judge.load(), 'v5c2': s5.Judge.load(model_path())}
    items, skip = mb.eligible_dev()
    rows, c = [], Counter()
    (PRIV / 'rows').mkdir(parents=True, exist_ok=True, mode=0o700)
    for it, texts in s2.load_items([i['item_id'] for i in items]):
        st = json.loads((PRIV / 'stash' / f"{it['item_id']}.json").read_text())
        if not st['ok']:
            c['stash_failed:' + st['why']] += 1
            continue
        r = score_item(it, texts, st, judges)
        rows.append(r)
        c['eligible' if r['eligible'] else r['why']] += 1
        (PRIV / 'rows' / f"{it['item_id']}.json").write_text(json.dumps(r))
    ok, per, boot, by_src = summarise(rows)
    cost_p = OUT / 'v5c2-bench.json'
    cost = json.loads(cost_p.read_text()) if cost_p.exists() else None
    res = dict(schema='v5c2/results', protocol='V5C2_PROTOCOL.md', dev_items=len(items), excluded_dev=dict(skip),
               population=dict(c), groups=len({r['group'] for r in ok}),
               pool_results_median=med([r['pool'] for r in ok]), stashed_results_median=med([r['stashed'] for r in ok]),
               budget_share_of_tool_tokens_median=med([r['budget'] / r['tool_tokens'] for r in ok]),
               budget_share_of_context_median=med([r['budget'] / r['context_tokens'] for r in ok]),
               arms=per, vs_stashed=boot, by_source=by_src, cost=cost and {k: cost[k] for k in ('v5c2', 'v3', 'load_avg')},
               acceptance=accept(per, boot, cost and {'v5c2': cost['v5c2'], 'v3': cost['v3']}))
    (OUT / 'v5c2-results.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


# --- edge (dev-edge v2, tool-output gold only; descriptive) -----------------------------------------------------
def edge_case_pass(case, scores, budget_pct):
    """Tool-result blocks are the only candidates; drop lowest (ties older first) until >= budget% of tool-output
    tokens. PASS iff every tool-result 'must' survives and every one:<g> group made only of tool results keeps one."""
    from research.edge_cases_build import tok
    tool = [b for b in case['blocks'] if b['kind'] == 'tool_result']
    total = sum(tok(b['text']) for b in tool)
    order = sorted(range(len(tool)), key=lambda k: (scores[tool[k]['id']], k))
    dropped, got = set(), 0
    for k in order:
        if got >= budget_pct / 100 * total:
            break
        dropped.add(tool[k]['id'])
        got += tok(tool[k]['text'])
    groups = defaultdict(list)
    for b in case['blocks']:
        if b['gold'].startswith('one:'):
            groups[b['gold']].append(b)
    lost_group = any(all(b['kind'] == 'tool_result' for b in g) and all(b['id'] in dropped for b in g)
                     for g in groups.values())
    lost_must = any(b['gold'] == 'must' and b['id'] in dropped for b in tool)
    return not (lost_must or lost_group)


def edge_phase():
    from research import edge_suite as es
    from research import edge_v2 as e2
    from research import matched_budget_v2 as mb
    from research import specialist_v2 as s2
    from research import specialist_v3 as s3
    from research import specialist_v5 as s5
    cases = [c for c in e2.load_dev() if any(b['kind'] == 'tool_result' and (b['gold'] == 'must' or b['gold'].startswith('one:'))
                                             for b in c['blocks'])]
    judges = {'v3': s3.Judge.load(), 'v5c2': s5.Judge.load(model_path())}
    out = {a: [0, 0, 0] for a in ('v3', 'v5c2', 'recency', 'bm25', 'mechanical')}
    by_type = defaultdict(lambda: {a: [0, 0, 0] for a in out})
    for c in cases:
        ids = [b['id'] for b in c['blocks']]
        sc = {a: dict(zip(ids, j.score(c['goal'], s2.edge_texts(c)))) for a, j in judges.items()}
        sc['recency'] = es.recency(c)
        sc['bm25'] = es.bm25(c)
        sc['mechanical'] = mb.mechanical_scores(c['goal'], [(b['id'], b['text']) for b in c['blocks']])
        for a in out:
            for k, bud in enumerate((30, 50, 70)):
                p = edge_case_pass(c, sc[a], bud)
                out[a][k] += p
                by_type[c.get('edge_type', 'general')][a][k] += p
    n_type = Counter(c.get('edge_type', 'general') for c in cases)
    return dict(n=len(cases), passes_30_50_70=out, by_type={t: dict(n=n_type[t], **v) for t, v in sorted(by_type.items())})


def bench_phase():
    from research import matched_budget_v2 as mb
    from research import specialist_v3 as s3
    from research import specialist_v5 as s5
    items, _ = mb.eligible_dev()
    la0 = os.getloadavg()
    v5 = s5.bench(model_path(), items)
    v3 = s3.bench(s3.ART / 'model.json', items)
    res = dict(note='fresh process, 1 thread, the 325 eligible dev items, v5c2 then v3 in the same run',
               load_avg=dict(before=[round(x, 1) for x in la0], after=[round(x, 1) for x in os.getloadavg()]),
               v5c2=v5, v3=v3)
    (OUT / 'v5c2-bench.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('model', 'stash', 'score', 'edge', 'bench'))
    ap.add_argument('--limit', type=int)
    a = ap.parse_args(argv)
    if a.phase == 'stash':
        out = stash_phase(a.limit)
    elif a.phase == 'model':
        out = model_phase()
    elif a.phase == 'score':
        out = score_phase()
    elif a.phase == 'edge':
        out = edge_phase()
        (OUT / 'v5c2-edge.json').write_text(json.dumps(out, indent=1) + '\n')
    else:
        out = bench_phase()
    print(json.dumps(out, indent=1, default=str)[:8000])


if __name__ == '__main__':
    sys.exit(main())
