"""Real-context bench v0.3: fresh test set, mechanical vs lcc_rules_transcript, plus a blind drop audit.

Protocol: research/goal-engine-2026-10-04/real-context-bench-v0.3/protocol.json. Probes, metrics and
the v0.2 rules run path are imported unchanged from research/real_context_bench.py and
research/real_context_bench_v02.py (both sha-checked here).

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v03 {sample | run --arm mechanical|lcc_rules_transcript | score | audit}

`sample` runs before the freeze (it writes the fresh sample whose sha256 the protocol pins); the
other phases refuse to run unless protocol.json, this file and fresh-sample.json match the freeze.
Everything per-item stays under PRIVATE; the repo gets counts only.
"""
import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02

BENCH_V03 = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.3'
PROTOCOL_V03 = BENCH_V03 / 'protocol.json'
PRIVATE = rcb.PRIVATE
FRESH_SAMPLE = PRIVATE / 'fresh-sample.json'
FRESH_DOSSIERS = PRIVATE / 'fresh-dossiers'
FRESH_RUNS = PRIVATE / 'fresh-runs'
AUDIT = PRIVATE / 'audit'
SEED = 20261010
N = 60
RULES = v02.ARM
ARMS = ('mechanical', RULES)
AUDIT_N, AUDIT_PER_ITEM, AUDIT_FILES = 150, 6, ('a', 'b', 'c')
CLIP_TURN, CLIP_INPUT, CLIP_OUTPUT = 1500, 1000, 3000


# --- sample (pre-freeze) --------------------------------------------------------------------------
def dev_ids(root=PRIVATE):
    ids = {p.stem for p in (root / 'dev-dossiers').glob('*.json')}
    for p in (root / 'dev-runs').glob('*.json'):
        d = json.loads(p.read_text())
        ids |= set(d) if isinstance(d, dict) else {r['id'] for r in d}
    return ids


def label_of(rid, v, extra):
    """owner_v1 > pool label (owner v2 / llm v2 pass) > labels-claude-extra; None if unlabeled."""
    if 'owner_v1' in v:
        return v['owner_v1'], v.get('confidence'), 'owner_confirmed_v1'
    if 'label' in v:
        return v['label'], v.get('confidence'), v.get('label_source')
    if rid in extra:
        return extra[rid]['label'], extra[rid].get('confidence'), extra[rid].get('label_source')
    return None


def sample_phase(root=PRIVATE):
    proto0 = rcb.load_protocol()
    frozen = rcb.load_sample(root, proto0)  # sha-checked v0 files
    pool = json.loads((root / 'pool.json').read_text())
    extra = {}
    for line in (root / 'labels-claude-extra.jsonl').read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            extra[d['id']] = d
    test_ids, dev = {it['id'] for it in frozen['items']}, dev_ids(root)
    left = {rid: v for rid, v in pool.items() if rid not in test_ids and rid not in dev and v.get('mapped')}
    unlabeled = [rid for rid, v in left.items() if v.get('ctx_assistant', 0) >= 1 and label_of(rid, v, extra) is None]
    if unlabeled:  # ponytail: none at freeze time; label them (taxonomy-v2 rules, marked LLM) before sampling
        raise SystemExit(f'{len(unlabeled)} candidates have no label: label them first')
    ids, eligible = rcb.allocate(left, extra, SEED, N)
    items = []
    for rid in ids:
        v = pool[rid]
        label, conf, src = label_of(rid, v, extra)
        items.append(dict(id=rid, category=label, label_source=src, confidence=conf, path=v['path'],
                          uuid=v['uuid'], session_hash=v['session_hash']))
    test_sessions = {it['session_hash'] for it in frozen['items']}
    stats = dict(pool=len(pool), excluded_frozen_60=len(test_ids), excluded_dev=len(dev & set(pool)),
                 candidates=len(left), eligible=sum(eligible.values()), eligible_per_stratum=eligible,
                 sampled=len(items), sampled_per_stratum=_count(it['category'] for it in items),
                 sampled_label_sources=_count(it['label_source'] for it in items),
                 sampled_in_frozen_60_sessions=sum(it['session_hash'] in test_sessions for it in items),
                 sampled_sessions=len({it['session_hash'] for it in items}))
    FRESH_SAMPLE.write_text(json.dumps(dict(seed=SEED, n=N, stats=stats, items=items), indent=1))
    rl = rcb.load_request_log(proto0['pins']['request_log_ruleset_sha256_prefix'])
    FRESH_DOSSIERS.mkdir(exist_ok=True)
    sizes, bad_id, empty = [], 0, 0
    for item in items:
        d = rcb.build_dossier(item, rl.redact)
        bad_id += not d['id_ok']
        empty += not d['blocks']
        sizes.append(sum(len(b['content'].encode()) for b in d['blocks'] if b['kind'] != 'image'))
        (FRESH_DOSSIERS / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
    return dict(stats, dossiers=len(sizes), id_mismatch=bad_id, empty_context=empty,
                visible_bytes=dict(median=sorted(sizes)[len(sizes) // 2], max=max(sizes), sum=sum(sizes)))


def _count(xs):
    out = defaultdict(int)
    for x in xs:
        out[x] += 1
    return dict(sorted(out.items()))


# --- frozen phases --------------------------------------------------------------------------------
def load_protocol_v03(path=PROTOCOL_V03):
    proto = rcb.load_protocol(path)  # checks protocol.json.sha256
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.3 freeze: refusing to run')
    for name, want in proto['sample']['private_files_sha256'].items():
        if rcb.sha256_file(PRIVATE / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    return proto


def make_rules_runner(dossier):
    """v0.2 rules run path, plus each trimmed result's text (needed for the audit packet)."""
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript

    def run(text, goal):
        res = compact_transcript(TranscriptCompactionRequest(
            payload=v02.rules_payload(dossier['blocks']), question=goal, provider='rules'))
        extra = {k: res.report.get(k) for k in rcb.TRANSCRIPT_KEEP}
        extra['decisions'] = [{k: d.get(k) for k in ('id', 'decision', 'source', 'keep_call', 'keep_result',
                                                     'chars', 'chars_after', 'reason')} for d in res.decisions]
        for kind in ('keep', 'trim', 'drop'):
            extra[f'{kind}_ids'] = [d['id'] for d in res.decisions if d.get('decision') == kind]
        trimmed = set(extra['trim_ids'])
        extra['trimmed_results'] = {r.id: r.text for m in res.messages for r in m.tool_results if r.id in trimmed}
        return rcb.apply_transcript(dossier['blocks'], res.decisions, res.messages), extra
    return run


def run_phase(arm, root=PRIVATE):
    proto = load_protocol_v03()
    if arm not in ARMS:
        raise SystemExit(f'{arm!r} is not a v0.3 arm')
    os.environ.update(proto['privacy']['env'])
    v02.check_lcc_rules(proto['pins']['lcc_rules'])  # both arms run on the pinned rules commit
    sample = json.loads(FRESH_SAMPLE.read_text())
    out = FRESH_RUNS / arm
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.3 runs each arm once (no retries)')
    counts = defaultdict(int)
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for it in sample['items']:
            d = json.loads((FRESH_DOSSIERS / f"{it['id']}.json").read_text())
            runner = mech or make_rules_runner(d)
            rec = rcb.run_item(arm, d, runner, rcb.lcc_count, proto['per_item_timeout_s'])
            counts[rec['status']] += 1
            (out / f"{it['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(sample['items']), status=dict(counts), guard_trips=rcb.GUARD['trips'])


def score_phase(public=True):
    proto = load_protocol_v03()
    sample = json.loads(FRESH_SAMPLE.read_text())
    dossiers = [json.loads((FRESH_DOSSIERS / f"{it['id']}.json").read_text()) for it in sample['items']]
    recs = {'full': {}}
    for d in dossiers:  # full control: the rendered context itself (sanity: must retain 100%)
        tok, method = rcb.lcc_count(d['text'])
        n = len(d['text'].encode())
        recs['full'][d['id']] = dict(status='ok', output=d['text'], in_bytes=n, out_bytes=n, in_tokens=tok,
                                     out_tokens=tok, token_method=method, latency_ms=None, guard_trips=0)
    for arm in ARMS:
        recs[arm] = {d['id']: json.loads(p.read_text()) for d in dossiers
                     if (p := FRESH_RUNS / arm / f"{d['id']}.json").exists()}
    score = rcb.aggregate(dossiers, recs, proto)
    score.update(schema='real-context-bench-score/0.3', protocol_sha256=rcb.sha256_file(PROTOCOL_V03),
                 verdict_v03=v02.verdict(score['arms'][RULES], score['arms']['mechanical']),
                 decisions=_decision_counts(recs[RULES].values()))
    (PRIVATE / 'fresh-score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1))
    if public:
        (BENCH_V03 / 'score.json').write_text(json.dumps(rcb.counts_only(score), indent=1) + '\n')
    return rcb.counts_only(score)


def _decision_counts(recs):
    out = defaultdict(int)
    for r in recs:
        for d in r.get('decisions') or ():
            out[f"{d['decision']}:{(d.get('reason') or '').split(':')[0]}"] += 1
    return dict(sorted(out.items()))


# --- drop audit -----------------------------------------------------------------------------------
def clip(s, n):
    """Head and tail of s within n chars, with the cut marked."""
    s = s or ''
    if len(s) <= n:
        return s
    h = n // 2
    return f'{s[:h]}\n[... {len(s) - n} chars omitted ...]\n{s[len(s) - (n - h):]}'


def audit_select(per_item, seed=SEED, n=AUDIT_N, cap=AUDIT_PER_ITEM):
    """per_item: {item id: [tool_use_id, ...]} of drop/trim decisions. Each item's decisions are
    shuffled and capped; items are visited in shuffled order, one pick per item per round."""
    rng = random.Random(seed)
    queues = {}
    for rid in sorted(per_item):
        ids = sorted(per_item[rid])
        rng.shuffle(ids)
        queues[rid] = ids[:cap]
    order = sorted(queues)
    rng.shuffle(order)
    picked, rnd = [], 0
    while len(picked) < n and any(len(q) > rnd for q in queues.values()):
        for rid in order:
            if len(picked) < n and len(queues[rid]) > rnd:
                picked.append((rid, queues[rid][rnd]))
        rnd += 1
    rng.shuffle(picked)
    return picked


def last_turns(blocks, k=3):
    turns = {}
    for b in blocks:
        if b['kind'] == 'text' and b['role'] in ('user', 'assistant') and b['content'].strip():
            turns.setdefault(b['m'], dict(role=b['role'], parts=[]))['parts'].append(b['content'])
    return [dict(role=t['role'], text=clip('\n'.join(t['parts']), CLIP_TURN)) for _, t in sorted(turns.items())[-k:]]


def audit_phase():
    proto = load_protocol_v03()
    spec = proto['audit']
    sample = json.loads(FRESH_SAMPLE.read_text())
    runs, per_item = {}, {}
    for it in sample['items']:
        r = json.loads((FRESH_RUNS / RULES / f"{it['id']}.json").read_text())
        runs[it['id']] = r
        ids = [d['id'] for d in r.get('decisions') or () if d['decision'] in ('drop', 'trim')]
        if ids:
            per_item[it['id']] = ids
    picked = audit_select(per_item, spec['seed'], spec['n'], spec['max_per_item'])
    AUDIT.mkdir(exist_ok=True)
    packets, keys = [], []
    for i, (rid, tid) in enumerate(picked, 1):
        d = json.loads((FRESH_DOSSIERS / f'{rid}.json').read_text())
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next((b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid), None)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'D{i:03d}'
        trimmed = runs[rid].get('trimmed_results', {}).get(tid) if dec['decision'] == 'trim' else None
        packets.append(dict(audit_id=aid, request=d['goal'], recent_turns=last_turns(d['blocks']),
                            tool=use['tool_name'], tool_input=clip(use['content'], CLIP_INPUT),
                            original_output=clip(res['content'] if res else '', CLIP_OUTPUT),
                            original_output_chars=len(res['content']) if res else 0,
                            shortened_output=None if trimmed is None else clip(trimmed, CLIP_OUTPUT)))
        keys.append(dict(audit_id=aid, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         decision=dec['decision'], reason=dec.get('reason'), source=dec.get('source'),
                         is_error=bool(res and res['is_error']), file=AUDIT_FILES[(i - 1) // (spec['n'] // 3)]))
    dump = lambda p, rows: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))  # noqa: E731
    dump(AUDIT / 'drops.jsonl', packets)
    dump(AUDIT / 'key.jsonl', keys)  # unblinding key: never shown to judges
    size = spec['n'] // 3
    for j, name in enumerate(AUDIT_FILES):
        dump(AUDIT / f'drops-{name}.jsonl', packets[j * size:(j + 1) * size])
    return dict(population=sum(map(len, per_item.values())), items_with_candidates=len(per_item),
                population_by_decision=_count(x['decision'] for r in runs.values() for x in r.get('decisions') or ()
                                              if x['decision'] in ('drop', 'trim')),
                sampled=len(packets), sampled_by_decision=_count(k['decision'] for k in keys),
                sampled_items=len({k['item'] for k in keys}),
                max_per_item=max(_count(k['item'] for k in keys).values()) if keys else 0,
                files={name: size for name in AUDIT_FILES})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('sample', 'run', 'score', 'audit'))
    ap.add_argument('--arm')
    a = ap.parse_args(argv)
    res = {'sample': sample_phase, 'score': score_phase, 'audit': audit_phase}.get(a.phase, lambda: run_phase(a.arm))()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
