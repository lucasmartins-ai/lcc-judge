"""Real-context bench v0.6 TEST: mechanical vs LCC rules lossless vs LCC rules recoverable on the 60 held-out
Hermes items, plus the two-judge blind recoverability audit of the recoverable arm's `replace` decisions.

Protocol: research/goal-engine-2026-10-04/real-context-bench-v0.6/protocol.json (frozen, committed and pushed
before TEST dossiers exist). Every phase re-checks the freeze (protocol sha, frozen code files, private
test-sample.json / labels sha, judging text byte-identical to the DEV text). Probes, render, aggregation and
audit selection are the v0-v0.4 code, imported unchanged; dossiers are research/hermes_context.build_dossier.
Audit aggregation: research/real_context_bench_v06_audit.py.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v06_test {dossiers | run --arm A | score | audit | rejudge | audit-score}
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

from research import hermes_context as hc
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03
from research import real_context_bench_v04 as v04
from research import real_context_bench_v05 as v05
from research import real_context_bench_v06_audit as v06a
from research import real_context_bench_v06_heldout as v06h
from research import recoverable_dev_measure as rdm
from research.lossless_dedup_measure import independent_check as dedupe_check

BENCH = v06h.BENCH_V06
PROTOCOL = BENCH / 'protocol.json'
PRIVATE = v06h.PRIVATE
DOSSIERS = PRIVATE / 'dossiers'
MODES = {'lcc_rules_lossless': 'lossless', 'lcc_rules_recoverable': 'recoverable'}
ARMS = ('mechanical', *MODES)
REC = v06a.ARM
FILES, JUDGES = v06a.FILES, v06a.JUDGES
DECISION_KEYS = ('id', 'decision', 'source', 'keep_call', 'keep_result', 'chars', 'chars_after', 'reason', 'note',
                 'kept_at', 'recover')


def load_protocol():
    proto = rcb.load_protocol(PROTOCOL)  # checks protocol.json.sha256
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.6 freeze: refusing to run')
    for name, want in proto['sample']['private_files_sha256'].items():
        if rcb.sha256_file(PRIVATE / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    if proto['audit']['judging']['instructions'] != rdm.JUDGE_TEXT:
        raise SystemExit('judging text differs from the DEV text: refusing to run')
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
    prior = v06h.prior_keys()
    overlap = {k: len({it[k] for it in items} & prior[k]) for k in v06h.KEYS}
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


def make_rules_runner(dossier, mode, box):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript

    def run(text, goal):
        res = compact_transcript(TranscriptCompactionRequest(payload=v02.rules_payload(dossier['blocks']),
                                                             question=goal, provider='rules', rules_mode=mode))
        box['res'] = res
        extra = {k: res.report.get(k) for k in (*rcb.TRANSCRIPT_KEEP, 'rules_mode', 'recoverability_check')}
        extra['decisions'] = [{k: d.get(k) for k in DECISION_KEYS} for d in res.decisions]
        return rcb.apply_transcript(dossier['blocks'], res.decisions, res.messages), extra
    return run


def verify(dossier, mode, res, out_text):
    """lcc's own verifier AND the independent bench checks (no lcc code) on one compaction."""
    from lcc.relevance import messages_to_payload
    from lcc.relevance.transcript import verify_lossless
    from lcc.relevance.transcript_recoverable import verify_recoverable
    payload, after = v02.rules_payload(dossier['blocks']), messages_to_payload(res.messages)
    lcc_v = (verify_recoverable if mode == 'recoverable' else verify_lossless)(payload, after)
    ind = dedupe_check(dossier['blocks'], res.decisions, out_text)
    ind += rdm.independent_replace_check(dossier['blocks'], res.decisions, out_text)  # also catches stray replaces
    return dict(lcc=lcc_v, independent=ind, runtime_fail_safe=res.report.get('lossless_violations'))


def run_phase(arm):
    proto = load_protocol()
    if arm not in ARMS:
        raise SystemExit(f'{arm!r} is not a v0.6 arm')
    os.environ.update(proto['privacy']['env'])
    v02.check_lcc_rules(proto['pins']['lcc_rules'])  # every arm runs on the pinned commit
    dossiers = _dossiers(_sample())
    out = PRIVATE / 'runs' / arm
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.6 runs each arm once (no retries)')
    counts, viol = defaultdict(int), Counter()
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for d in dossiers:
            box = {}
            runner = mech or make_rules_runner(d, MODES[arm], box)
            rec = rcb.run_item(arm, d, runner, rcb.lcc_count, proto['per_item_timeout_s'])
            if arm in MODES and rec['status'] == 'ok':
                rec['verify'] = verify(d, MODES[arm], box['res'], rec['output'])
                viol.update(lcc=len(rec['verify']['lcc']), independent=len(rec['verify']['independent']),
                            runtime_fail_safe=bool(rec['verify']['runtime_fail_safe']))
            counts[rec['status']] += 1
            (out / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(dossiers), status=dict(counts), violations=dict(viol), guard_trips=rcb.GUARD['trips'])


def pointer_kind(d):
    r = d.get('recover') or {}
    return ('file_range' if r.get('lines') else 'file_whole') if r.get('kind') == 'file' else 'command'


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
    reps = [(r, x) for r in recs[REC].values() for x in r.get('decisions') or () if x['decision'] == 'replace']
    uses = {(d['id'], b['tool_use_id']): b['tool_name'] for d in dossiers for b in d['blocks'] if b['kind'] == 'tool_use'}
    score.update(
        schema='real-context-bench-score/0.6', protocol_sha256=rcb.sha256_file(PROTOCOL),
        verdict_v06={arm: v02.verdict(score['arms'][arm], score['arms']['mechanical']) for arm in MODES},
        decisions={arm: v03._decision_counts(recs[arm].values()) for arm in MODES},
        violations={arm: dict(lcc=sum(len(r['verify']['lcc']) for r in recs[arm].values() if 'verify' in r),
                              independent=sum(len(r['verify']['independent']) for r in recs[arm].values() if 'verify' in r),
                              runtime_fail_safe=sum(bool(r['verify']['runtime_fail_safe'])
                                                    for r in recs[arm].values() if 'verify' in r),
                              unverified=sum('verify' not in r for r in recs[arm].values()))
                    for arm in MODES},
        recoverability_check={arm: dict(Counter(r.get('recoverability_check') for r in recs[arm].values()))
                              for arm in MODES},
        pointers=dict(total=len(reps), items_with_pointer=len({r['id'] for r, _ in reps}),
                      by_kind=dict(Counter(pointer_kind(x) for _, x in reps)),
                      by_tool=dict(Counter(uses.get((r['id'], x['id'])) for r, x in reps).most_common()),
                      replaced_chars=sum(x.get('chars') or 0 for _, x in reps)),
        dossiers=json.loads((PRIVATE / 'dossiers-receipt.json').read_text()))
    (PRIVATE / 'score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1))
    public = rcb.counts_only(score)
    public['pointers']['by_tool'] = {('mcp' if (k or '').startswith('mcp__') else k): v
                                     for k, v in public['pointers']['by_tool'].items()}
    (BENCH / 'score.json').write_text(json.dumps(public, indent=1) + '\n')
    return public


def file_index(i, n):
    """0-based record i of n -> file 0..2 (thirds in pick order; 50/50/50 at n = 150)."""
    return i * 3 // n


def packet(aid, dossier, use, res, note):
    """The DEV packet (research/recoverable_dev_measure.audit_phase), field for field."""
    clean = lambda s, n: v04.strip_note(v03.clip(v04.strip_note(s), n))  # noqa: E731
    return dict(audit_id=aid, request=v04.strip_note(dossier['goal']),
                recent_turns=[dict(t, text=clean(t['text'], v03.CLIP_TURN)) for t in v03.last_turns(dossier['blocks'])],
                tool=use['tool_name'], tool_input=clean(use['content'], v03.CLIP_INPUT),
                recovery_pointer=note, removed_output=clean(res['content'], rdm.CLIP_OUTPUT),
                removed_output_chars=len(res['content']))


def audit_phase():
    proto = load_protocol()
    spec = proto['audit']
    dossiers = {d['id']: d for d in _dossiers(_sample())}
    runs, per_item = {}, {}
    for rid in dossiers:
        r = json.loads((PRIVATE / 'runs' / REC / f'{rid}.json').read_text())
        runs[rid] = r
        ids = [x['id'] for x in r.get('decisions') or () if x['decision'] == 'replace']
        if ids:
            per_item[rid] = ids
    picked = v03.audit_select(per_item, spec['seed'], spec['n'], spec['max_per_item'])
    out = PRIVATE / 'audit'
    out.mkdir(exist_ok=True)
    if any(out.glob('*.jsonl')) or any(PRIVATE.glob('judge-*')):
        raise SystemExit('audit packets already exist: the audit sample is drawn once')
    packets, keys = [], []
    for i, (rid, tid) in enumerate(picked):
        d = dossiers[rid]
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next(b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'R{i + 1:03d}'
        packets.append(packet(aid, d, use, res, dec['note']))
        keys.append(dict(audit_id=aid, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         recovery_pointer=dec['note'], pointer_kind=pointer_kind(dec), reason=dec.get('reason'),
                         file=FILES[file_index(i, len(picked))]))
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
    return dict(population=sum(map(len, per_item.values())), items_with_candidates=len(per_item),
                sampled=len(packets), sampled_items=len({k['item'] for k in keys}),
                max_per_item=max(Counter(k['item'] for k in keys).values()) if keys else 0,
                per_file={f: len(rows) for f, rows in files.items()},
                sampled_by_kind=dict(Counter(k['pointer_kind'] for k in keys)),
                sampled_by_tool=dict(Counter(k['tool'] for k in keys)),
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
           'rejudge': lambda: v06a.rejudge(PRIVATE),
           'audit-score': lambda: v06a.score(PRIVATE, BENCH)}.get(a.phase, lambda: run_phase(a.arm))()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
