"""Real-context bench v0.5, DEV only: run mechanical and the rules policy on the DEV dossiers, score
them with the v0.4 probes, and build drop/trim audit packets. Never opens TEST.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v05_dev {run --tag T [--arm mechanical] | score --tag T | audit --tag T --out DIR}

DEV is for policy work, so runs may be repeated: each tag is a directory under PRIVATE/dev-runs and
records the rules worktree commit it ran on. Unlabelled DEV items (category None) are scored with the
UNKNOWN probes. Probes, render, packets and audit selection are the v0.4 code, imported unchanged.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v03 as v03
from research import real_context_bench_v04 as v04
from research import real_context_bench_v05 as v05

DEV = v05.PRIVATE / 'dev-dossiers'
RUNS = v05.PRIVATE / 'dev-runs'
RULES = v04.RULES
WORKTREE = Path('/Users/Master/lcc-wt-rules')
AUDIT_N, AUDIT_PER_ITEM = 100, 3


def dossiers():
    return [json.loads(p.read_text()) for p in sorted(DEV.glob('*.json'))]


def lcc_state():
    import lcc
    git = lambda *a: subprocess.run(['git', '-C', str(WORKTREE), *a], capture_output=True, text=True,  # noqa: E731
                                    check=True).stdout.strip()
    return dict(lcc_file=lcc.__file__, commit=git('rev-parse', 'HEAD'),
                dirty=bool(git('status', '--porcelain', '--untracked-files=no')))


def run_phase(tag, arm):
    state = lcc_state()
    if WORKTREE.resolve() not in Path(state['lcc_file']).resolve().parents:
        raise SystemExit(f"lcc imported from {state['lcc_file']}, not {WORKTREE}")
    out = RUNS / tag
    out.mkdir(parents=True, exist_ok=True)
    (out / 'meta.json').write_text(json.dumps(dict(state, arm=arm), indent=1))
    counts = {}
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for d in dossiers():
            rec = rcb.run_item(arm, d, mech or v03.make_rules_runner(d), rcb.lcc_count, 600)
            counts[rec['status']] = counts.get(rec['status'], 0) + 1
            (out / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(tag=tag, arm=arm, commit=state['commit'], dirty=state['dirty'], status=counts,
                guard_trips=rcb.GUARD['trips'])


def score_phase(tag):
    proto = rcb.load_protocol(v04.PROTOCOL_V04)
    ds = [dict(d, category=d['category'] or 'UNKNOWN') for d in dossiers()]
    recs = {name: {d['id']: json.loads((RUNS / t / f"{d['id']}.json").read_text()) for d in ds}
            for name, t in (('mechanical', 'mechanical'), (RULES, tag))}
    score = rcb.aggregate(ds, recs, proto)
    score['decisions'] = v03._decision_counts(recs[RULES].values())
    score['meta'] = json.loads((RUNS / tag / 'meta.json').read_text())
    (RUNS / tag / 'score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1))
    pick = ('items', 'retention_item', 'retention_probe', 'reduction_tokens', 'reduction_bytes', 'failures', 'guard_trips')
    return dict(n=len(ds), arms={a: {k: v[k] for k in pick} for a, v in score['arms'].items()},
                decisions=score['decisions'], meta=score['meta'])


def audit_phase(tag, out, seed):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.jsonl')):
        raise SystemExit(f'{out} already holds packets: the audit sample is drawn once')
    runs, per_item, ds = {}, {}, {d['id']: d for d in dossiers()}
    for rid in ds:
        r = json.loads((RUNS / tag / f'{rid}.json').read_text())
        runs[rid] = r
        ids = [x['id'] for x in r.get('decisions') or () if x['decision'] in ('drop', 'trim')]
        if ids:
            per_item[rid] = ids
    picked = v03.audit_select(per_item, seed, AUDIT_N, AUDIT_PER_ITEM)
    packets, keys = [], []
    for i, (rid, tid) in enumerate(picked, 1):
        d = ds[rid]
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next((b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid), None)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'R{i:03d}'
        packets.append(v04.packet(aid, d, use, res, dec['decision'], runs[rid].get('trimmed_results', {}).get(tid)))
        keys.append(dict(audit_id=aid, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         decision=dec['decision'], reason=dec.get('reason'), is_error=bool(res and res['is_error']),
                         file='g1' if i <= AUDIT_N // 2 else 'g2'))
    dump = lambda p, rows: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))  # noqa: E731
    dump(out / 'key.jsonl', keys)  # unblinding key: never shown to judges
    for f in ('g1', 'g2'):
        dump(out / f'{f}.jsonl', [p for p, k in zip(packets, keys) if k['file'] == f])
    pop = [x for r in runs.values() for x in r.get('decisions') or () if x['decision'] in ('drop', 'trim')]
    return dict(tag=tag, seed=seed, population=len(pop), population_by_rule=v03._count(
                    f"{x['decision']}:{(x.get('reason') or '').split(':')[0]}" for x in pop),
                items_with_candidates=len(per_item), sampled=len(packets),
                sampled_by_rule=v03._count(f"{k['decision']}:{(k['reason'] or '').split(':')[0]}" for k in keys),
                sampled_items=len({k['item'] for k in keys}),
                files={f: str(out / f'{f}.jsonl') for f in ('g1', 'g2')}, key=str(out / 'key.jsonl'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('run', 'score', 'audit'))
    ap.add_argument('--tag', required=True)
    ap.add_argument('--arm', default=RULES, choices=('mechanical', RULES))
    ap.add_argument('--out')
    ap.add_argument('--seed', type=int, default=1001)
    a = ap.parse_args(argv)
    res = (run_phase(a.tag, a.arm) if a.phase == 'run' else score_phase(a.tag) if a.phase == 'score'
           else audit_phase(a.tag, a.out, a.seed))
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
