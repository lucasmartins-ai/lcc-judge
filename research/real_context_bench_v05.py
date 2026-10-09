"""Real-context bench v0.5: session-disjoint DEV/TEST split of held-out Codex sessions.

Candidates use the v0.4 logic unchanged (research/real_context_bench_v04.py, research/codex_context.py):
imported human Codex prompts mapped to a rollout position, with >= 1 assistant message before them.
Sessions that share a session_hash or path with ANY file under ~/.lcc/bench (v0, v0.1-v0.3, the
v0.4 sample and its dossiers) are excluded; zero overlap is asserted. The remaining sessions are
shuffled (seed 20261012) and halved: DEV (first half) for policy work, TEST (second half) held out.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.real_context_bench_v05 split

`split` writes PRIVATE/split.json, PRIVATE/test-sample.json (<= 60, <= 2 per session, equal
allocation over taxonomy-v2 strata, labels by the v0.4 precedence) and DEV dossiers (<= 150,
<= 2 per session). TEST dossiers are NOT built here. If a drawn TEST candidate has no label it
writes PRIVATE/to-label.jsonl and stops; labels go to PRIVATE/labels-llm-v2.jsonl. The repo gets
counts and sha256s only (split-receipt.json).
"""
import glob
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from research import codex_context as cc
from research import real_context_bench as rcb
from research import real_context_bench_v04 as v04

BENCH_V05 = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
BENCH_ROOT = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH_ROOT / 'codex-heldout-v0.5'
LLM_SOURCE = 'llm_v05_codex_v2_rules'
SEED = 20261012
N, PER_SESSION, DEV_CAP = 60, 2, 150


def prior_keys():
    """session_hash/path values in every earlier bench dir under ~/.lcc/bench (all but v0.5)."""
    out = dict(session_hash=set(), path=set())
    for d in sorted(BENCH_ROOT.iterdir()):
        if d.is_dir() and d != PRIVATE:
            for k, v in v04.prior_keys(d).items():
                out[k] |= v
    return out


def labels():
    """v0.4 precedence (owner v2 > taxonomy-v2 LLM pass > v0.4 LLM labels), then v0.5 LLM labels."""
    out = v04.labels(v04.PRIVATE)
    for d in v04._jl(PRIVATE / v04.LLM_LABELS):
        out.setdefault(d['id'], dict(label=d['label'], confidence=d.get('confidence'), label_source=LLM_SOURCE))
    return out


def split_sessions(sessions, seed=SEED):
    """Random(seed) shuffles the sorted session hashes; DEV = first len//2, TEST = the rest."""
    s = sorted(sessions)
    random.Random(seed).shuffle(s)
    return sorted(s[:len(s) // 2]), sorted(s[len(s) // 2:])


def split_phase():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rl = rcb.load_request_log(v04.RULESET_PREFIX)
    salt = (v04.REQUEST_LOG / '.salt').read_bytes()
    imported = {d['id']: d for d in v04._jl(v04.IMPORTED)}
    paths = glob.glob(str(cc.ROOT / 'sessions' / '**' / 'rollout-*.jsonl'), recursive=True)
    idx = cc.index_prompts(paths, rl.redact, rl.MAX_GOAL_CHARS)
    prior = prior_keys()
    cache, rows = {}, {}
    for rid in sorted(set(idx) & set(imported)):
        v, sh = idx[rid], imported[rid]['session_hash']
        assert rl.session_hash(f"codex:{v['sid']}", salt) == sh, rid
        if v['path'] not in cache:
            cache[v['path']] = cc.read_rollout(v['path'])
        rows[rid] = dict(id=rid, path=v['path'], index=v['index'], session_hash=sh,
                         ctx_assistant=cc.assistant_turns(cc.context_items(cache[v['path']], v['index'])))
    # a session is excluded if ANY of its prompts' hash or rollout path appears in an earlier bench
    bad = {r['session_hash'] for r in rows.values() if r['session_hash'] in prior['session_hash'] or r['path'] in prior['path']}
    by_session = defaultdict(list)
    for r in rows.values():
        if r['ctx_assistant'] >= 1 and r['session_hash'] not in bad:
            by_session[r['session_hash']].append(r['id'])
    paths_of = defaultdict(set)
    for r in rows.values():
        paths_of[r['session_hash']].add(r['path'])
    elig_paths = {p for sh in by_session for p in paths_of[sh]}
    overlap = dict(session_hash=len(set(by_session) & prior['session_hash']), path=len(elig_paths & prior['path']))
    assert not any(overlap.values()), f'candidates overlap an earlier bench set: {overlap}'
    dev, test = split_sessions(by_session)
    assert not set(dev) & set(test) and not {p for s in dev for p in paths_of[s]} & {p for s in test for p in paths_of[s]}
    split = dict(seed=SEED, rule='Random(seed).shuffle(sorted eligible session hashes); DEV=first len//2, TEST=rest',
                 dev=[dict(session_hash=s, paths=sorted(paths_of[s]), ids=sorted(by_session[s])) for s in dev],
                 test=[dict(session_hash=s, paths=sorted(paths_of[s]), ids=sorted(by_session[s])) for s in test])
    (PRIVATE / 'split.json').write_text(json.dumps(split, indent=1))

    # TEST sample (v0.4 draw + label + allocation rules, seed 20261012); no dossiers
    drawn = v04.draw_per_session({s: by_session[s] for s in test}, SEED, PER_SESSION)
    lab = labels()
    missing = [rid for rid in drawn if rid not in lab]
    if missing:
        (PRIVATE / 'to-label.jsonl').write_text(''.join(json.dumps(dict(id=rid, goal=imported[rid]['goal']), ensure_ascii=False)
                                                       + '\n' for rid in missing))
        raise SystemExit(f'{len(missing)} drawn TEST candidates have no v2 label: label to-label.jsonl into {v04.LLM_LABELS}')
    strata = defaultdict(list)
    for rid in drawn:
        if lab[rid]['confidence'] != 'low':
            strata[lab[rid]['label']].append(rid)
    ids = v04.allocate(strata, SEED, N)
    items = [dict({k: rows[rid][k] for k in ('id', 'path', 'index', 'session_hash', 'ctx_assistant')},
                  category=lab[rid]['label'], label_source=lab[rid]['label_source'], confidence=lab[rid]['confidence'])
             for rid in ids]
    assert {it['session_hash'] for it in items} <= set(test)
    count = v04._count
    tstats = dict(drawn=len(drawn), drawn_label_sources=count(lab[r]['label_source'] for r in drawn),
                  drawn_low_confidence=sum(lab[r]['confidence'] == 'low' for r in drawn),
                  eligible_per_stratum={k: len(v) for k, v in sorted(strata.items())},
                  sampled=len(items), sampled_per_stratum=count(it['category'] for it in items),
                  sampled_label_sources=count(it['label_source'] for it in items),
                  sampled_sessions=len({it['session_hash'] for it in items}),
                  max_per_session=max(count(it['session_hash'] for it in items).values()))
    (PRIVATE / 'test-sample.json').write_text(json.dumps(dict(seed=SEED, n=N, stats=tstats, items=items), indent=1))

    # DEV dossiers: <= 2 per session, then a seeded cap at 150 (labels attached when known)
    dev_ids = v04.draw_per_session({s: by_session[s] for s in dev}, SEED, PER_SESSION)
    if len(dev_ids) > DEV_CAP:
        dev_ids = sorted(random.Random(SEED).sample(sorted(dev_ids), DEV_CAP))
    out = PRIVATE / 'dev-dossiers'
    out.mkdir(exist_ok=True)
    assert not any(out.glob('*.json')), f'{out} already holds dossiers'
    bad_id = empty = 0
    for rid in dev_ids:
        lb = lab.get(rid, {})
        d = cc.build_dossier(dict(rows[rid], category=lb.get('label'), label_source=lb.get('label_source'),
                                  confidence=lb.get('confidence')), rl.redact, rcb.render)
        bad_id += not d['id_ok']
        empty += not d['blocks']
        (out / f'{rid}.json').write_text(json.dumps(d, ensure_ascii=False))
    receipt = dict(
        schema='real-context-bench-split/0.5', seed=SEED,
        population=dict(indexed=len(idx), imported=len(imported), mapped=len(rows),
                        with_assistant_turn=sum(r['ctx_assistant'] >= 1 for r in rows.values()),
                        sessions_with_assistant_turn=len({r['session_hash'] for r in rows.values() if r['ctx_assistant'] >= 1}),
                        excluded_prior_sessions=len(bad & {r['session_hash'] for r in rows.values() if r['ctx_assistant'] >= 1}),
                        eligible_sessions=len(by_session), eligible_prompts=sum(map(len, by_session.values()))),
        prior_keys=dict(session_hash=len(prior['session_hash']), path=len(prior['path'])),
        prior_overlap=overlap,
        split=dict(dev_sessions=len(dev), test_sessions=len(test), dev_prompts=sum(len(by_session[s]) for s in dev),
                   test_prompts=sum(len(by_session[s]) for s in test), session_overlap=0, path_overlap=0),
        test_sample=tstats,
        dev_dossiers=dict(built=len(dev_ids), sessions=len({rows[r]['session_hash'] for r in dev_ids}),
                          id_mismatch=bad_id, empty_context=empty, digest_sha256=_digest(out)),
        test_dossiers_built=0,
        sha256={'split.json': rcb.sha256_file(PRIVATE / 'split.json'),
                'test-sample.json': rcb.sha256_file(PRIVATE / 'test-sample.json')})
    if (PRIVATE / v04.LLM_LABELS).exists():
        receipt['sha256'][v04.LLM_LABELS] = rcb.sha256_file(PRIVATE / v04.LLM_LABELS)
    BENCH_V05.mkdir(parents=True, exist_ok=True)
    (BENCH_V05 / 'split-receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def _digest(folder):
    """sha256 over sorted 'name sha256' lines of the folder's dossier files (v0.4 digest rule)."""
    return hashlib.sha256(''.join(f'{p.name} {rcb.sha256_file(p)}\n' for p in sorted(folder.glob('*.json'))).encode()).hexdigest()


if __name__ == '__main__':
    if sys.argv[1:] != ['split']:
        raise SystemExit('usage: -m research.real_context_bench_v05 split')
    json.dump(split_phase(), sys.stdout, indent=1, default=str)
    print()
