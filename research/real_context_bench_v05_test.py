"""Real-context bench v0.5 TEST: mechanical vs lcc_rules_transcript on the 60 held-out TEST items,
plus the v0.4 two-judge blind drop/trim audit.

Protocol: research/goal-engine-2026-10-04/real-context-bench-v0.5/protocol.json (frozen, committed and
pushed before TEST dossiers exist). Every phase re-checks the freeze: protocol.json sha, frozen code
files, split.json / test-sample.json / labels sha. Probes, render, the rules runner, packets and audit
selection are the v0/v0.2/v0.3/v0.4 code, imported unchanged. Aggregation is
research/real_context_bench_v04_audit.py, unchanged, called with root = PRIVATE.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v05_test {dossiers | run --arm A | score | audit | rejudge | audit-score}
"""
import argparse
import json
import os
import sys
from collections import defaultdict

from research import codex_context as cc
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03
from research import real_context_bench_v04 as v04
from research import real_context_bench_v04_audit as v04a
from research import real_context_bench_v05 as v05

BENCH = v05.BENCH_V05
PROTOCOL = BENCH / 'protocol.json'
PRIVATE = v05.PRIVATE
DOSSIERS = PRIVATE / 'dossiers'
RULES = v04.RULES
ARMS = v04.ARMS
FILES, JUDGES = v04.FILES, v04.JUDGES


def load_protocol():
    proto = rcb.load_protocol(PROTOCOL)  # checks protocol.json.sha256
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.5 freeze: refusing to run')
    for name, want in proto['sample']['private_files_sha256'].items():
        if rcb.sha256_file(PRIVATE / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    return proto


def _sample():
    return json.loads((PRIVATE / 'test-sample.json').read_text())


def _dossiers(sample):
    built = json.loads((PRIVATE / 'dossiers-receipt.json').read_text())
    if v05._digest(DOSSIERS) != built['digest_sha256']:
        raise SystemExit('dossiers/ changed since they were built: refusing to run')
    return [json.loads((DOSSIERS / f"{it['id']}.json").read_text()) for it in sample['items']]


def dossiers_phase():
    """Build the TEST dossiers once, after the freeze (v0.4 build_dossier, unchanged)."""
    proto = load_protocol()
    DOSSIERS.mkdir(exist_ok=True)
    if any(DOSSIERS.glob('*.json')):
        raise SystemExit(f'{DOSSIERS} already holds dossiers: built once')
    sample = _sample()
    split = json.loads((PRIVATE / 'split.json').read_text())
    test = {s['session_hash'] for s in split['test']}
    dev = {s['session_hash'] for s in split['dev']}
    dev_paths = {p for s in split['dev'] for p in s['paths']}
    items = sample['items']
    assert len(items) == proto['sample']['n'] and all(it['session_hash'] in test for it in items)
    assert not {it['session_hash'] for it in items} & dev and not {it['path'] for it in items} & dev_paths
    assert not {it['id'] for it in items} & {p.stem for p in (PRIVATE / 'dev-dossiers').glob('*.json')}
    rl = rcb.load_request_log(v04.RULESET_PREFIX)
    sizes, bad_id, empty = [], 0, 0
    for it in items:
        d = cc.build_dossier(it, rl.redact, rcb.render)
        bad_id += not d['id_ok']
        empty += not d['blocks']
        sizes.append(sum(len(b['content'].encode()) for b in d['blocks'] if b['kind'] != 'image'))
        (DOSSIERS / f"{it['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
    if bad_id or empty:
        raise SystemExit(f'{bad_id} id mismatches, {empty} empty contexts')
    out = dict(built=len(sizes), id_mismatch=bad_id, empty_context=empty, digest_sha256=v05._digest(DOSSIERS),
               visible_bytes=dict(median=sorted(sizes)[len(sizes) // 2], max=max(sizes), sum=sum(sizes)))
    (PRIVATE / 'dossiers-receipt.json').write_text(json.dumps(out, indent=1))
    return out


def run_phase(arm):
    proto = load_protocol()
    if arm not in ARMS:
        raise SystemExit(f'{arm!r} is not a v0.5 arm')
    os.environ.update(proto['privacy']['env'])
    v02.check_lcc_rules(proto['pins']['lcc_rules'])  # both arms run on the pinned rules commit
    dossiers = _dossiers(_sample())
    out = PRIVATE / 'runs' / arm
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.5 runs each arm once (no retries)')
    counts = defaultdict(int)
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for d in dossiers:
            rec = rcb.run_item(arm, d, mech or v03.make_rules_runner(d), rcb.lcc_count, proto['per_item_timeout_s'])
            counts[rec['status']] += 1
            (out / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(dossiers), status=dict(counts), guard_trips=rcb.GUARD['trips'])


def score_phase():
    proto = load_protocol()
    dossiers = _dossiers(_sample())
    recs = {'full': {}}
    for d in dossiers:  # full control: the rendered context itself (must retain 100%)
        tok, method = rcb.lcc_count(d['text'])
        n = len(d['text'].encode())
        recs['full'][d['id']] = dict(status='ok', output=d['text'], in_bytes=n, out_bytes=n, in_tokens=tok,
                                     out_tokens=tok, token_method=method, latency_ms=None, guard_trips=0)
    for arm in ARMS:
        recs[arm] = {d['id']: json.loads(p.read_text()) for d in dossiers
                     if (p := PRIVATE / 'runs' / arm / f"{d['id']}.json").exists()}
    score = rcb.aggregate(dossiers, recs, proto)
    score.update(schema='real-context-bench-score/0.5', protocol_sha256=rcb.sha256_file(PROTOCOL),
                 verdict_v05=v02.verdict(score['arms'][RULES], score['arms']['mechanical']),
                 decisions=v03._decision_counts(recs[RULES].values()),
                 dossiers=json.loads((PRIVATE / 'dossiers-receipt.json').read_text()))
    (PRIVATE / 'score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1))
    (BENCH / 'score.json').write_text(json.dumps(rcb.counts_only(score), indent=1) + '\n')
    return rcb.counts_only(score)


def audit_phase():
    """v0.4 audit_phase with root = v0.5 PRIVATE (same selection, ids, files, packets, key, judge files)."""
    proto = load_protocol()
    spec = proto['audit']
    dossiers = {d['id']: d for d in _dossiers(_sample())}
    runs, per_item = {}, {}
    for rid in dossiers:
        r = json.loads((PRIVATE / 'runs' / RULES / f'{rid}.json').read_text())
        runs[rid] = r
        ids = [d['id'] for d in r.get('decisions') or () if d['decision'] in ('drop', 'trim')]
        if ids:
            per_item[rid] = ids
    picked = v03.audit_select(per_item, spec['seed'], spec['n'], spec['max_per_item'])
    out = PRIVATE / 'audit'
    out.mkdir(exist_ok=True)
    if any(out.glob('*.jsonl')):
        raise SystemExit(f'{out} already holds packets: the audit sample is drawn once')
    packets, keys = [], []
    for i, (rid, tid) in enumerate(picked, 1):
        d = dossiers[rid]
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next((b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid), None)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'D{i:03d}'
        packets.append(v04.packet(aid, d, use, res, dec['decision'], runs[rid].get('trimmed_results', {}).get(tid)))
        keys.append(dict(audit_id=aid, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         decision=dec['decision'], reason=dec.get('reason'), source=dec.get('source'),
                         is_error=bool(res and res['is_error']), file=FILES[min((i - 1) // 50, 2)]))
    dump = lambda p, rows: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))  # noqa: E731
    dump(out / 'key.jsonl', keys)  # unblinding key: never shown to judges
    files = {f: [p for p, k in zip(packets, keys) if k['file'] == f] for f in FILES}
    for f, rows in files.items():
        dump(out / f'{f}.jsonl', rows)
    for j, fs in JUDGES.items():
        dump(out / f'judge-{j}.jsonl', [p for f in fs for p in files[f]])
    leaks = sum('[... lcc:' in json.dumps(p, ensure_ascii=False) for p in packets)
    return dict(population=sum(map(len, per_item.values())), items_with_candidates=len(per_item),
                population_by_rule=v03._count(f"{x['decision']}:{(x.get('reason') or '').split(':')[0]}"
                                              for r in runs.values() for x in r.get('decisions') or ()
                                              if x['decision'] in ('drop', 'trim')),
                sampled=len(packets), sampled_by_decision=v03._count(k['decision'] for k in keys),
                sampled_items=len({k['item'] for k in keys}),
                max_per_item=max(v03._count(k['item'] for k in keys).values()) if keys else 0,
                lcc_marker_packets=leaks, files={f: str(out / f'{f}.jsonl') for f in FILES},
                sha256={p.name: rcb.sha256_file(p) for p in sorted(out.glob('*.jsonl'))})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('dossiers', 'run', 'score', 'audit', 'rejudge', 'audit-score'))
    ap.add_argument('--arm')
    a = ap.parse_args(argv)
    if a.phase in ('rejudge', 'audit-score'):
        load_protocol()
    res = {'dossiers': dossiers_phase, 'score': score_phase, 'audit': audit_phase,
           'rejudge': lambda: v04a.rejudge(PRIVATE),
           'audit-score': lambda: v04a.score(PRIVATE, BENCH)}.get(a.phase, lambda: run_phase(a.arm))()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
