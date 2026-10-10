"""Real-context bench v0.6: held-out TEST set from Hermes sessions no earlier bench has touched.

Candidates: human Hermes prompts (research.import_agent_requests.hermes rules, via
research/hermes_context.py) whose same-session context holds >= 1 assistant turn and >= 1 tool
result (the rules policy acts only on tool results). Sessions or prompts that share a session_hash,
path or id with ANY JSON/JSONL file under ~/.lcc/bench (every earlier set) are excluded and zero
overlap is asserted. Draw: <= 2 per session (seed 20261013), then equal allocation over taxonomy-v2
strata (labels by the v0.5 precedence, then v0.6 LLM labels marked llm_v06_hermes_v2_rules;
low-confidence labels are not sampled), N <= 60. Same draw helpers as v0.4/v0.5.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    /Users/Master/LCC/.venv/bin/python -m research.real_context_bench_v06_heldout {sample | receipt}

`sample` writes PRIVATE/test-sample.json (or PRIVATE/to-label.jsonl and stops when a drawn
candidate has no label; labels go to PRIVATE/labels-llm-v2.jsonl). TEST dossiers are NOT built.
`receipt` writes the repo receipt: counts and sha256s only.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from research import hermes_context as hc
from research import real_context_bench as rcb
from research import real_context_bench_v04 as v04
from research import real_context_bench_v05 as v05

BENCH_V06 = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.6'
BENCH_ROOT = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH_ROOT / 'heldout-v0.6'
LLM_SOURCE = 'llm_v06_hermes_v2_rules'
SEED = 20261013
N, PER_SESSION = 60, 2
KEYS = ('session_hash', 'path', 'id')
CODE = ('research/hermes_context.py', 'research/real_context_bench_v06_heldout.py', 'tests/test_hermes_context.py')


def prior_keys(root=BENCH_ROOT, skip=PRIVATE):
    """Every session_hash / path / id string in any JSON/JSONL file under root (skip excluded)."""
    found = {k: set() for k in KEYS}

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in found and isinstance(v, str):
                    found[k].add(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for p in sorted(Path(root).rglob('*.json*')):
        if skip in p.parents or p.suffix not in ('.json', '.jsonl'):
            continue
        for doc in (v04._jl(p) if p.suffix == '.jsonl' else [json.loads(p.read_text())]):
            walk(doc)
    return found


def labels():
    out = v05.labels()
    for d in v04._jl(PRIVATE / v04.LLM_LABELS):
        out.setdefault(d['id'], dict(label=d['label'], confidence=d.get('confidence'), label_source=LLM_SOURCE))
    return out


def sample_phase():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rl = rcb.load_request_log(v04.RULESET_PREFIX)
    salt = (v04.REQUEST_LOG / '.salt').read_bytes()
    clean = hc._importer()._hermes_clean
    idx = hc.index_prompts(hc.ROOT, rl.redact, rl.MAX_GOAL_CHARS)
    imported = {d['id']: d for d in v04._jl(v04.REQUEST_LOG / 'imported' / 'hermes.jsonl')}
    db = str(hc.ROOT / 'state.db')
    con, cache, rows, sh_mismatch, unlocated = hc.connect(), {}, {}, 0, 0
    try:
        for rid in sorted(idx):
            v = idx[rid]
            sh = rl.session_hash(f"hermes:{v['sid']}", salt)
            sh_mismatch += rid in imported and imported[rid]['session_hash'] != sh
            if v['sid'] not in cache:
                cache[v['sid']] = hc.session_rows(con, v['sid'])
            pr = hc.prompt_row(cache[v['sid']], v['ts'], v['goal'], clean)
            if pr is None:
                unlocated += 1
                continue
            n_asst, n_res = hc.counts(hc.render_blocks(hc.context_rows(cache[v['sid']], pr['timestamp'])))
            rows[rid] = dict(id=rid, sid=v['sid'], ts=pr['timestamp'], path=f"{db}#{v['sid']}", session_hash=sh,
                             ctx_assistant=n_asst, ctx_tool_results=n_res)
    finally:
        con.close()
    if sh_mismatch:
        raise SystemExit(f'{sh_mismatch} session hashes differ from imported/hermes.jsonl')
    prior = prior_keys()
    raw_sids_in_prior_paths = sum(any(r['sid'] in p for p in prior['path']) for r in rows.values())
    in_prior = {r['id'] for r in rows.values() if r['session_hash'] in prior['session_hash']
                or r['path'] in prior['path'] or r['id'] in prior['id']}
    by_session = defaultdict(list)
    for r in rows.values():
        if r['ctx_assistant'] >= 1 and r['ctx_tool_results'] >= 1 and r['id'] not in in_prior:
            by_session[r['session_hash']].append(r['id'])
    drawn = v04.draw_per_session(by_session, SEED, PER_SESSION)
    lab = labels()
    missing = [rid for rid in drawn if rid not in lab]
    if missing:
        (PRIVATE / 'to-label.jsonl').write_text(''.join(
            json.dumps(dict(id=rid, goal=rl.redact(idx[rid]['goal'])[:rl.MAX_GOAL_CHARS]), ensure_ascii=False) + '\n'
            for rid in missing))
        raise SystemExit(f'{len(missing)} drawn candidates have no v2 label: label to-label.jsonl into {v04.LLM_LABELS}')
    strata = defaultdict(list)
    for rid in drawn:
        if lab[rid]['confidence'] != 'low':
            strata[lab[rid]['label']].append(rid)
    ids = v04.allocate(strata, SEED, N)
    items = [dict(rows[rid], category=lab[rid]['label'], label_source=lab[rid]['label_source'],
                  confidence=lab[rid]['confidence']) for rid in ids]
    c = v04._count
    overlap = dict(session_hash=len({it['session_hash'] for it in items} & prior['session_hash']),
                   path=len({it['path'] for it in items} & prior['path']),
                   id=len({it['id'] for it in items} & prior['id']),
                   raw_sid_in_prior_path=sum(any(it['sid'] in p for p in prior['path']) for it in items))
    assert not any(overlap.values()), f'sample overlaps an earlier bench set: {overlap}'
    stats = dict(indexed=len(idx), imported_hermes=len(imported), unlocated=unlocated, mapped=len(rows),
                 with_assistant_and_tool_result=sum(r['ctx_assistant'] >= 1 and r['ctx_tool_results'] >= 1
                                                    for r in rows.values()),
                 excluded_prior=len(in_prior), raw_sids_in_prior_paths=raw_sids_in_prior_paths,
                 eligible_sessions=len(by_session), eligible_prompts=sum(map(len, by_session.values())),
                 drawn=len(drawn), drawn_label_sources=c(lab[r]['label_source'] for r in drawn),
                 drawn_low_confidence=sum(lab[r]['confidence'] == 'low' for r in drawn),
                 eligible_per_stratum={k: len(v) for k, v in sorted(strata.items())},
                 sampled=len(items), sampled_per_stratum=c(it['category'] for it in items),
                 sampled_label_sources=c(it['label_source'] for it in items),
                 sampled_sessions=len({it['session_hash'] for it in items}),
                 max_per_session=max(c(it['session_hash'] for it in items).values()),
                 prior_overlap=overlap, prior_keys={k: len(v) for k, v in prior.items()})
    (PRIVATE / 'test-sample.json').write_text(json.dumps(dict(seed=SEED, n=N, stats=stats, items=items), indent=1))
    return stats


def receipt():
    s = json.loads((PRIVATE / 'test-sample.json').read_text())
    out = dict(schema='real-context-bench-heldout/0.6', source='hermes', seed=s['seed'], n_max=s['n'],
               per_session_max=PER_SESSION, eligibility='same-session context with >= 1 assistant turn and >= 1 tool result',
               label_precedence='owner v2 > taxonomy-v2 LLM pass > v0.4/v0.5 LLM labels > ' + LLM_SOURCE + ' (LLM, marked)',
               stats=s['stats'], test_dossiers_built=0, policy_tuning_reads_before_receipt=0,
               sha256={'test-sample.json': rcb.sha256_file(PRIVATE / 'test-sample.json'),
                       v04.LLM_LABELS: rcb.sha256_file(PRIVATE / v04.LLM_LABELS)
                       if (PRIVATE / v04.LLM_LABELS).exists() else None},
               code_sha256={f: rcb.sha256_file(rcb.REPO / f) for f in CODE})
    BENCH_V06.mkdir(parents=True, exist_ok=True)
    (BENCH_V06 / 'heldout-receipt.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('sample', 'receipt'))
    a = ap.parse_args()
    json.dump(sample_phase() if a.phase == 'sample' else receipt(), sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
