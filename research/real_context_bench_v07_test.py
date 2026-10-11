"""Real-context bench v0.7 TEST: mechanical vs LCC rules lossless vs LCC rules recoverable on the 80 held-out
Hermes items, plus the two-judge blind recoverability audit of the recoverable arm's `replace` decisions.

Protocol: research/goal-engine-2026-10-04/real-context-bench-v0.7/protocol.json (frozen, committed and pushed
before TEST dossiers exist). Every phase re-checks the freeze (protocol sha, frozen code files, private
test-sample.json / labels sha, judging text == JUDGE_TEXT). This is research/real_context_bench_v06_test.py with:
- v0.7 private root, sample (research/real_context_bench_v07_heldout) and pinned LCC commit;
- independent check v3 = research.recoverable_dev_v2.independent_check_v2 + no pointer to a system temp path;
- audit sample stratified by pointer kind (stratified_select), files f1/f2/f3 dealt per kind;
- the v0.7 judging text and labels (research/real_context_bench_v07_audit).
Packets, probes, render, aggregation code paths are imported unchanged.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v07_test {dossiers | run --arm A | score | audit | rejudge | audit-score}
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

from research import hermes_context as hc
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03
from research import real_context_bench_v04 as v04
from research import real_context_bench_v05 as v05
from research import real_context_bench_v06_test as v06t
from research import real_context_bench_v07_audit as v07a
from research import real_context_bench_v07_heldout as v07h
from research.lossless_dedup_measure import independent_check as dedupe_check
from research.recoverable_dev_v2 import independent_check_v2

BENCH = v07h.BENCH_V07
PROTOCOL = BENCH / 'protocol.json'
PRIVATE = v07h.PRIVATE
DOSSIERS = PRIVATE / 'dossiers'
MODES = v06t.MODES
ARMS = v06t.ARMS
REC = v07a.ARM
FILES, JUDGES = v07a.FILES, v07a.JUDGES
KINDS = ('file_whole', 'file_range', 'command')
JUDGE_TEXT = (
    'Blind auditor for a context compactor. Each record: a user request to a coding agent, the last turns, an '
    'earlier tool call whose output was REMOVED and replaced by the recovery pointer shown. Question: to correctly '
    'do what the user asked now, does the agent need the removed content AND would it be unable to get it back by '
    'following the pointer (re-read / re-run, in the stated directory), given what happened later in the session '
    'as far as you can tell? Answer needed_unrecoverable / ok / unsure, with a specific 5-15 word reason per '
    'record, unique, no quotes from the data.')
# Independent of lcc's own regex: a temp dir path not glued to a preceding path segment.
TEMP = re.compile(r'(?<![\w.~-])(?:/private)?/(?:tmp|var/tmp|var/folders|dev/shm)(?=/|\b)')


def load_protocol():
    proto = rcb.load_protocol(PROTOCOL)  # checks protocol.json.sha256
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.7 freeze: refusing to run')
    for name, want in proto['sample']['private_files_sha256'].items():
        if rcb.sha256_file(PRIVATE / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    if proto['audit']['judging']['instructions'] != JUDGE_TEXT:
        raise SystemExit('judging text differs from the frozen v0.7 text: refusing to run')
    ins = PRIVATE / 'audit' / 'instructions.txt'
    if ins.exists() and ins.read_text() != JUDGE_TEXT:
        raise SystemExit(f'{ins} differs from the frozen judging text: refusing to run')
    return proto


def _sample():
    return json.loads((PRIVATE / 'test-sample.json').read_text())


def _dossiers(sample):
    built = json.loads((PRIVATE / 'dossiers-receipt.json').read_text())
    if v05._digest(DOSSIERS) != built['digest_sha256']:
        raise SystemExit('dossiers/ changed since they were built: refusing to run')
    return [json.loads((DOSSIERS / f"{it['id']}.json").read_text()) for it in sample['items']]


def dossiers_phase():
    """Build the TEST dossiers once, after the freeze."""
    proto = load_protocol()
    DOSSIERS.mkdir(exist_ok=True)
    if any(DOSSIERS.glob('*.json')):
        raise SystemExit(f'{DOSSIERS} already holds dossiers: built once')
    items = _sample()['items']
    prior = v07h.prior_keys()
    overlap = {k: len({it[k] for it in items} & prior[k]) for k in v07h.KEYS}
    overlap['raw_sid_in_prior_path'] = sum(any(it['sid'] in p for p in prior['path']) for it in items)
    assert len(items) == proto['sample']['n'] and not any(overlap.values()), overlap
    rl = rcb.load_request_log(v04.RULESET_PREFIX)
    clean = hc._importer()._hermes_clean
    con = hc.connect()
    sizes, bad_id, empty = [], 0, 0
    try:
        for it in items:
            d = hc.build_dossier(it, con, rl.redact, rcb.render, clean)
            bad_id += not d['id_ok']
            empty += not d['blocks']
            sizes.append(sum(len(b['content'].encode()) for b in d['blocks'] if b['kind'] != 'image'))
            (DOSSIERS / f"{it['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
    finally:
        con.close()
    if bad_id or empty:
        raise SystemExit(f'{bad_id} id mismatches, {empty} empty contexts')
    out = dict(built=len(sizes), id_mismatch=bad_id, empty_context=empty, prior_overlap=overlap,
               digest_sha256=v05._digest(DOSSIERS),
               visible_bytes=dict(median=sorted(sizes)[len(sizes) // 2], max=max(sizes), sum=sum(sizes)))
    (PRIVATE / 'dossiers-receipt.json').write_text(json.dumps(out, indent=1))
    return out


def independent_check_v3(blocks, decisions, out_text):
    """research.recoverable_dev_v2.independent_check_v2 + no pointer names a system temp path (no lcc code)."""
    bad = independent_check_v2(blocks, decisions, out_text)
    for d in decisions:  # the pointer names the path or command and the cwd
        if d.get('decision') == 'replace' and TEMP.search(d.get('note') or ''):
            bad.append(f"{d['id']}: pointer to a system temp path")
    return bad


def verify(dossier, mode, res, out_text):
    """lcc's own verifier AND the independent bench checks (no lcc code) on one compaction."""
    from lcc.relevance import messages_to_payload
    from lcc.relevance.transcript import verify_lossless
    from lcc.relevance.transcript_recoverable import verify_recoverable
    payload, after = v02.rules_payload(dossier['blocks']), messages_to_payload(res.messages)
    lcc_v = (verify_recoverable if mode == 'recoverable' else verify_lossless)(payload, after)
    ind = dedupe_check(dossier['blocks'], res.decisions, out_text)
    ind += independent_check_v3(dossier['blocks'], res.decisions, out_text)  # also catches stray replaces
    return dict(lcc=lcc_v, independent=ind, runtime_fail_safe=res.report.get('lossless_violations'))


def run_phase(arm):
    proto = load_protocol()
    if arm not in ARMS:
        raise SystemExit(f'{arm!r} is not a v0.7 arm')
    os.environ.update(proto['privacy']['env'])
    v02.check_lcc_rules(proto['pins']['lcc_rules'])  # every arm runs on the pinned commit
    dossiers = _dossiers(_sample())
    out = PRIVATE / 'runs' / arm
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.7 runs each arm once (no retries)')
    counts, viol = defaultdict(int), Counter()
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for d in dossiers:
            box = {}
            runner = mech or v06t.make_rules_runner(d, MODES[arm], box)
            rec = rcb.run_item(arm, d, runner, rcb.lcc_count, proto['per_item_timeout_s'])
            if arm in MODES and rec['status'] == 'ok':
                rec['verify'] = verify(d, MODES[arm], box['res'], rec['output'])
                viol.update(lcc=len(rec['verify']['lcc']), independent=len(rec['verify']['independent']),
                            runtime_fail_safe=bool(rec['verify']['runtime_fail_safe']))
            counts[rec['status']] += 1
            (out / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(dossiers), status=dict(counts), violations=dict(viol), guard_trips=rcb.GUARD['trips'])


def score_phase():
    """v0.6 score phase on the v0.7 paths; schema label 0.7."""
    load_protocol()
    saved = (v06t.PROTOCOL, v06t.PRIVATE, v06t.BENCH, v06t.DOSSIERS, v06t.load_protocol, v06t._sample, v06t._dossiers)
    v06t.PROTOCOL, v06t.PRIVATE, v06t.BENCH, v06t.DOSSIERS = PROTOCOL, PRIVATE, BENCH, DOSSIERS
    v06t.load_protocol, v06t._sample, v06t._dossiers = load_protocol, _sample, _dossiers
    try:
        v06t.score_phase()
    finally:
        (v06t.PROTOCOL, v06t.PRIVATE, v06t.BENCH, v06t.DOSSIERS, v06t.load_protocol, v06t._sample,
         v06t._dossiers) = saved
    for p in (PRIVATE / 'score.json', BENCH / 'score.json'):
        s = json.loads(p.read_text())
        s['schema'], s['verdict_v07'] = 'real-context-bench-score/0.7', s.pop('verdict_v06')
        p.write_text(json.dumps(s, ensure_ascii=False, indent=1) + ('\n' if p.parent == BENCH else ''))
    return json.loads((BENCH / 'score.json').read_text())


def stratified_select(pools, seed, n, cap):
    """pools: {kind: {item: [tool_use_id, ...]}} -> {kind: [(item, tool_use_id), ...]}.

    Each kind's candidates are ordered by v03.audit_select(seed + kind index, cap). Kinds take turns, one pick
    each, up to an equal quota (n // 3, remainder to the earlier kinds); a kind short of its quota leaves the
    rest to the other kinds, which keep taking turns until n or nothing is left. No item gives more than
    `cap` records in total (over all kinds)."""
    queues = {k: v03.audit_select(pools.get(k, {}), seed + i, 10 ** 9, cap) for i, k in enumerate(KINDS)}
    quota = {k: n // len(KINDS) + (i < n % len(KINDS)) for i, k in enumerate(KINDS)}
    per_item, picked = Counter(), {k: [] for k in KINDS}
    total = lambda: sum(map(len, picked.values()))  # noqa: E731

    def take(k):
        while queues[k]:
            item, tid = queues[k].pop(0)
            if per_item[item] < cap:
                per_item[item] += 1
                picked[k].append((item, tid))
                return True
        return False
    for limit in (quota, None):
        moved = True
        while moved and total() < n:
            moved = False
            for k in KINDS:
                if total() < n and (limit is None or len(picked[k]) < limit[k]) and take(k):
                    moved = True
    return picked


def deal_files(picked, seed):
    """[(kind, item, tool_use_id, file)] in audit-id order: each kind's picks are dealt f1, f2, f3, f1, ...
    with one counter running over all kinds (files differ by at most 1), then each file is shuffled."""
    files = {f: [] for f in FILES}
    i = 0
    for k in KINDS:
        for item, tid in picked[k]:
            files[FILES[i % 3]].append((k, item, tid))
            i += 1
    rng = random.Random(seed)
    out = []
    for f in FILES:
        rng.shuffle(files[f])
        out += [(k, item, tid, f) for k, item, tid in files[f]]
    return out


def audit_phase():
    proto = load_protocol()
    spec = proto['audit']
    dossiers = {d['id']: d for d in _dossiers(_sample())}
    runs, pools = {}, {k: {} for k in KINDS}
    for rid in dossiers:
        r = json.loads((PRIVATE / 'runs' / REC / f'{rid}.json').read_text())
        runs[rid] = r
        for x in r.get('decisions') or ():
            if x['decision'] == 'replace':
                pools[v06t.pointer_kind(x)].setdefault(rid, []).append(x['id'])
    picked = stratified_select(pools, spec['seed'], spec['n'], spec['max_per_item'])
    out = PRIVATE / 'audit'
    out.mkdir(exist_ok=True)
    if any(out.glob('*.jsonl')) or any(PRIVATE.glob('judge-*')):
        raise SystemExit('audit packets already exist: the audit sample is drawn once')
    packets, keys = [], []
    for i, (kind, rid, tid, f) in enumerate(deal_files(picked, spec['seed'])):
        d = dossiers[rid]
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next(b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'R{i + 1:03d}'
        packets.append(v06t.packet(aid, d, use, res, dec['note']))
        keys.append(dict(audit_id=aid, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         recovery_pointer=dec['note'], pointer_kind=kind, reason=dec.get('reason'), file=f))
    dump = lambda p, rows: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))  # noqa: E731
    dump(out / 'key.jsonl', keys)  # unblinding key: never shown to judges
    files = {f: [p for p, k in zip(packets, keys) if k['file'] == f] for f in FILES}
    for f, rows in files.items():
        dump(out / f'{f}.jsonl', rows)
    (out / 'instructions.txt').write_text(spec['judging']['instructions'])  # byte-identical, no newline added
    for j, fs in JUDGES.items():  # isolated judge folders: only the judge's two packet files
        jd = PRIVATE / f'judge-{j}'
        jd.mkdir()
        for f in fs:
            (jd / f'{f}.jsonl').write_bytes((out / f'{f}.jsonl').read_bytes())
    blob = [json.dumps(p, ensure_ascii=False) for p in packets]
    return dict(population={k: sum(map(len, pools[k].values())) for k in KINDS},
                items_with_candidates=len({r for k in KINDS for r in pools[k]}),
                sampled=len(packets), sampled_items=len({k['item'] for k in keys}),
                max_per_item=max(Counter(k['item'] for k in keys).values()) if keys else 0,
                per_file={f: len(rows) for f, rows in files.items()},
                sampled_by_kind={k: sum(x['pointer_kind'] == k for x in keys) for k in KINDS},
                by_kind_per_file={f: dict(Counter(k['pointer_kind'] for k in keys if k['file'] == f)) for f in FILES},
                sampled_by_tool=dict(Counter('mcp' if k['tool'].startswith('mcp__') else k['tool'] for k in keys)),
                lcc_marker_packets=sum('[... lcc:' in b for b in blob),
                key_field_packets=sum(any(f in p for f in ('item', 'category', 'reason', 'pointer_kind', 'rule'))
                                      for p in packets),
                judge_folders={j: sorted(p.name for p in (PRIVATE / f'judge-{j}').iterdir()) for j in JUDGES},
                sha256={p.name: rcb.sha256_file(p) for p in sorted(out.glob('*.jsonl'))},
                instructions_sha256=rcb.sha256_file(out / 'instructions.txt'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('dossiers', 'run', 'score', 'audit', 'rejudge', 'audit-score'))
    ap.add_argument('--arm')
    a = ap.parse_args(argv)
    if a.phase in ('rejudge', 'audit-score'):
        load_protocol()
    res = {'dossiers': dossiers_phase, 'score': score_phase, 'audit': audit_phase,
           'rejudge': lambda: v07a.rejudge(PRIVATE),
           'audit-score': lambda: v07a.score(PRIVATE, BENCH)}.get(a.phase, lambda: run_phase(a.arm))()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
