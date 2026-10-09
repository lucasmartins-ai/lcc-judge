"""Real-context bench v0.4: Codex held-out set, mechanical vs lcc_rules_transcript@8997be6, plus a
two-judge blind drop/trim audit.

Protocol: research/goal-engine-2026-10-04/real-context-bench-v0.4/protocol.json. Probes, metrics,
render and the rules run path are imported unchanged from research/real_context_bench.py,
real_context_bench_v02.py and real_context_bench_v03.py (all sha-checked). Codex contexts come
from research/codex_context.py.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v04 {sample | run --arm mechanical|lcc_rules_transcript | score | audit}

`sample` runs before the freeze. If a drawn candidate has no taxonomy-v2 label it writes
PRIVATE/to-label.jsonl and stops; labels go to PRIVATE/labels-llm-v2.jsonl (marked LLM) and
`sample` is re-run. The other phases refuse to run unless protocol.json, the frozen code files
and sample.json match the freeze. Everything per-item stays under PRIVATE; the repo gets counts only.
"""
import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from research import codex_context as cc
from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03

BENCH_V04 = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.4'
PROTOCOL_V04 = BENCH_V04 / 'protocol.json'
PRIVATE = Path('/Users/Master/.lcc/bench/codex-heldout-v0.4')
PRIOR = rcb.PRIVATE  # every earlier bench set (v0, v0.1-v0.3, dev split) lives here
REQUEST_LOG = Path.home() / '.lcc' / 'request-log'
IMPORTED = REQUEST_LOG / 'imported' / 'codex.jsonl'
TAXONOMY_LABELS = REQUEST_LOG / 'taxonomy-v1'
LLM_LABELS = 'labels-llm-v2.jsonl'
LLM_SOURCE = 'llm_v04_codex_v2_rules'
RULESET_PREFIX = '4e99ffac1f9f'
SEED = 20261011
N, PER_SESSION = 60, 2
RULES = v02.ARM
ARMS = ('mechanical', RULES)
AUDIT_N, AUDIT_PER_ITEM = 150, 3
FILES = ('f1', 'f2', 'f3')
JUDGES = {'A': ('f1', 'f2'), 'B': ('f2', 'f3'), 'C': ('f3', 'f1')}
CLIP_TURN, CLIP_INPUT, CLIP_OUTPUT = v03.CLIP_TURN, v03.CLIP_INPUT, v03.CLIP_OUTPUT
LCC_NOTE = re.compile(r'\n?\[\.\.\. lcc: (\d+) chars of this tool result dropped; re-run .*? for the rest \.\.\.\]\n?')


# --- sample (pre-freeze) --------------------------------------------------------------------------
def _jl(path):
    p = Path(path)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def prior_keys(root=PRIOR):
    """Every session_hash and path value in any JSON/JSONL file under the earlier benches' root."""
    found = dict(session_hash=set(), path=set())

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
        for doc in (_jl(p) if p.suffix == '.jsonl' else [json.loads(p.read_text())]):
            walk(doc)
    return found


def labels(root=PRIVATE):
    """Owner verdicts on a v2 label > the taxonomy-v2 LLM pass > this bench's LLM labels."""
    out = {}
    for p in sorted(glob.glob(str(TAXONOMY_LABELS / 'labels-v2-*.jsonl'))):
        for d in _jl(p):
            out[d['id']] = dict(label=d['label'], confidence=d.get('confidence'), label_source='llm_v2_pass')
    for d in json.loads((TAXONOMY_LABELS / 'owner-judgments.json').read_text()):
        if d['id'] in out and d['proposed'] == out[d['id']]['label']:  # judged the v2 label (not a v1 one)
            out[d['id']] = dict(label=d['owner_label'], confidence='high',
                                label_source='owner_confirmed_v2' if d['owner_verdict'] == 'right' else 'owner_corrected_v2')
    for d in _jl(Path(root) / LLM_LABELS):
        out.setdefault(d['id'], dict(label=d['label'], confidence=d.get('confidence'), label_source=LLM_SOURCE))
    return out


def draw_per_session(by_session, seed, cap=PER_SESSION):
    """For each session (sorted), shuffle its sorted eligible ids with one Random(seed); keep the first cap."""
    rng = random.Random(seed)
    out = []
    for sh in sorted(by_session):
        ids = sorted(by_session[sh])
        rng.shuffle(ids)
        out += ids[:cap]
    return out


def allocate(strata, seed, n):
    """Equal allocation: Random(seed) shuffles each stratum's sorted ids (alphabetical strata), then
    one id per stratum per round, alphabetical, until n or every stratum is empty."""
    rng = random.Random(seed)
    order = {}
    for k in sorted(strata):
        ids = sorted(strata[k])
        rng.shuffle(ids)
        order[k] = ids
    picked, rnd = [], 0
    while len(picked) < n and any(len(v) > rnd for v in order.values()):
        for k in sorted(order):
            if len(picked) < n and len(order[k]) > rnd:
                picked.append(order[k][rnd])
        rnd += 1
    return picked


def sample_phase(root=PRIVATE):
    rl = rcb.load_request_log(RULESET_PREFIX)
    salt = (REQUEST_LOG / '.salt').read_bytes()
    imported = {d['id']: d for d in _jl(IMPORTED)}
    paths = glob.glob(str(cc.ROOT / 'sessions' / '**' / 'rollout-*.jsonl'), recursive=True)
    idx = cc.index_prompts(paths, rl.redact, rl.MAX_GOAL_CHARS)
    prior = prior_keys()
    cache, rows, sh_mismatch = {}, {}, 0
    for rid in sorted(set(idx) & set(imported)):
        v = idx[rid]
        sh = imported[rid]['session_hash']
        sh_mismatch += rl.session_hash(f"codex:{v['sid']}", salt) != sh
        if v['path'] not in cache:
            cache[v['path']] = cc.read_rollout(v['path'])
        n_asst = cc.assistant_turns(cc.context_items(cache[v['path']], v['index']))
        rows[rid] = dict(id=rid, path=v['path'], index=v['index'], session_hash=sh, ctx_assistant=n_asst)
    if sh_mismatch:
        raise SystemExit(f'{sh_mismatch} session hashes differ from imported/codex.jsonl')
    in_prior = {r['id'] for r in rows.values() if r['session_hash'] in prior['session_hash'] or r['path'] in prior['path']}
    by_session = defaultdict(list)
    for r in rows.values():
        if r['ctx_assistant'] >= 1 and r['id'] not in in_prior:
            by_session[r['session_hash']].append(r['id'])
    drawn = draw_per_session(by_session, SEED)
    lab = labels(root)
    missing = [rid for rid in drawn if rid not in lab]
    if missing:
        (root / 'to-label.jsonl').write_text(''.join(json.dumps(dict(id=rid, goal=imported[rid]['goal']), ensure_ascii=False)
                                                    + '\n' for rid in missing))
        raise SystemExit(f'{len(missing)} drawn candidates have no v2 label: label to-label.jsonl into {LLM_LABELS}')
    strata = defaultdict(list)
    for rid in drawn:
        if lab[rid]['confidence'] != 'low':
            strata[lab[rid]['label']].append(rid)
    ids = allocate(strata, SEED, N)
    items = [dict(rows[rid], category=lab[rid]['label'], label_source=lab[rid]['label_source'],
                  confidence=lab[rid]['confidence']) for rid in ids]
    sessions = {it['session_hash'] for it in items}
    overlap = dict(session_hash=len(sessions & prior['session_hash']),
                   path=len({it['path'] for it in items} & prior['path']),
                   prior_codex_paths=sum('/.codex/' in p for p in prior['path']))
    assert not any(overlap.values()), f'sample overlaps an earlier bench set: {overlap}'
    stats = dict(indexed=len(idx), imported=len(imported), mapped=len(rows),
                 with_assistant_turn=sum(r['ctx_assistant'] >= 1 for r in rows.values()),
                 excluded_prior_session=len(in_prior), eligible_sessions=len(by_session),
                 drawn=len(drawn), drawn_label_sources=_count(lab[r]['label_source'] for r in drawn),
                 drawn_low_confidence=sum(lab[r]['confidence'] == 'low' for r in drawn),
                 eligible_per_stratum={k: len(v) for k, v in sorted(strata.items())},
                 sampled=len(items), sampled_per_stratum=_count(it['category'] for it in items),
                 sampled_label_sources=_count(it['label_source'] for it in items),
                 sampled_sessions=len(sessions), max_per_session=max(_count(it['session_hash'] for it in items).values()),
                 prior_overlap=overlap, prior_keys=dict(session_hash=len(prior['session_hash']), path=len(prior['path'])))
    (root / 'sample.json').write_text(json.dumps(dict(seed=SEED, n=N, stats=stats, items=items), indent=1))
    (root / 'dossiers').mkdir(exist_ok=True)
    sizes, bad_id, empty = [], 0, 0
    for it in items:
        d = cc.build_dossier(it, rl.redact, rcb.render)
        bad_id += not d['id_ok']
        empty += not d['blocks']
        sizes.append(sum(len(b['content'].encode()) for b in d['blocks'] if b['kind'] != 'image'))
        (root / 'dossiers' / f"{it['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
    return dict(stats, dossiers=len(sizes), id_mismatch=bad_id, empty_context=empty,
                visible_bytes=dict(median=sorted(sizes)[len(sizes) // 2], max=max(sizes), sum=sum(sizes)))


_count = v03._count


# --- frozen phases --------------------------------------------------------------------------------
def load_protocol_v04(path=PROTOCOL_V04):
    proto = rcb.load_protocol(path)  # checks protocol.json.sha256
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.4 freeze: refusing to run')
    for name, want in proto['sample']['private_files_sha256'].items():
        if rcb.sha256_file(PRIVATE / name) != want:
            raise SystemExit(f'{name} does not match its pinned sha256: refusing to run')
    if dossiers_digest() != proto['sample']['dossiers_digest_sha256']:
        raise SystemExit('dossiers/ differ from the frozen digest: refusing to run')
    return proto


def dossiers_digest(root=PRIVATE):
    """sha256 over the sorted 'name sha256' lines of every dossier file."""
    lines = ''.join(f'{p.name} {rcb.sha256_file(p)}\n' for p in sorted((root / 'dossiers').glob('*.json')))
    return hashlib.sha256(lines.encode()).hexdigest()


def _dossiers(sample):
    return [json.loads((PRIVATE / 'dossiers' / f"{it['id']}.json").read_text()) for it in sample['items']]


def run_phase(arm):
    proto = load_protocol_v04()
    if arm not in ARMS:
        raise SystemExit(f'{arm!r} is not a v0.4 arm')
    os.environ.update(proto['privacy']['env'])
    v02.check_lcc_rules(proto['pins']['lcc_rules'])  # both arms run on the pinned rules commit
    sample = json.loads((PRIVATE / 'sample.json').read_text())
    out = PRIVATE / 'runs' / arm
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.4 runs each arm once (no retries)')
    counts = defaultdict(int)
    with rcb.network_guard():
        mech = rcb.make_runner('mechanical')[0] if arm == 'mechanical' else None
        for d in _dossiers(sample):
            rec = rcb.run_item(arm, d, mech or v03.make_rules_runner(d), rcb.lcc_count, proto['per_item_timeout_s'])
            counts[rec['status']] += 1
            (out / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=arm, items=len(sample['items']), status=dict(counts), guard_trips=rcb.GUARD['trips'])


def score_phase(public=True):
    proto = load_protocol_v04()
    dossiers = _dossiers(json.loads((PRIVATE / 'sample.json').read_text()))
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
    score.update(schema='real-context-bench-score/0.4', protocol_sha256=rcb.sha256_file(PROTOCOL_V04),
                 verdict_v04=v02.verdict(score['arms'][RULES], score['arms']['mechanical']),
                 decisions=v03._decision_counts(recs[RULES].values()))
    (PRIVATE / 'score.json').write_text(json.dumps(score, ensure_ascii=False, indent=1))
    if public:
        (BENCH_V04 / 'score.json').write_text(json.dumps(rcb.counts_only(score), indent=1) + '\n')
    return rcb.counts_only(score)


# --- audit packets --------------------------------------------------------------------------------
def strip_note(s):
    return LCC_NOTE.sub('\n[...]\n', s or '')


def split_trim(original, trimmed):
    """(kept_head, removed_middle, kept_tail) of a trimmed result; the LCC note is not returned."""
    m = LCC_NOTE.search(trimmed or '')
    if not m:
        raise ValueError('trimmed text carries no lcc note')
    head, tail = trimmed[:m.start()], trimmed[m.end():]
    removed = original[len(head):len(original) - len(tail)]
    if not (original.startswith(head) and original.endswith(tail) and len(removed) == int(m.group(1))):
        raise ValueError('trimmed text is not head + note + tail of the original')
    return head, removed, tail


def packet(aid, dossier, use, res, decision, trimmed):
    clean = lambda s, n: strip_note(v03.clip(strip_note(s), n))  # noqa: E731
    p = dict(audit_id=aid, request=strip_note(dossier['goal']),
             recent_turns=[dict(t, text=clean(t['text'], CLIP_TURN)) for t in v03.last_turns(dossier['blocks'])],
             tool=use['tool_name'], tool_input=clean(use['content'], CLIP_INPUT))
    original = res['content'] if res else ''
    if decision == 'drop':
        p.update(change='removed', original_output=clean(original, CLIP_OUTPUT), original_output_chars=len(original))
    else:
        head, removed, tail = split_trim(original, trimmed)
        p.update(change='shortened', original_output_chars=len(original), kept_head=strip_note(head),
                 kept_tail=strip_note(tail), removed_middle=clean(removed, CLIP_OUTPUT), removed_middle_chars=len(removed))
    return p


def audit_phase():
    proto = load_protocol_v04()
    spec = proto['audit']
    sample = json.loads((PRIVATE / 'sample.json').read_text())
    runs, per_item = {}, {}
    for it in sample['items']:
        r = json.loads((PRIVATE / 'runs' / RULES / f"{it['id']}.json").read_text())
        runs[it['id']] = r
        ids = [d['id'] for d in r.get('decisions') or () if d['decision'] in ('drop', 'trim')]
        if ids:
            per_item[it['id']] = ids
    picked = v03.audit_select(per_item, spec['seed'], spec['n'], spec['max_per_item'])
    out = PRIVATE / 'audit'
    out.mkdir(exist_ok=True)
    if any(out.glob('*.jsonl')):
        raise SystemExit(f'{out} already holds packets: the audit sample is drawn once')
    packets, keys = [], []
    for i, (rid, tid) in enumerate(picked, 1):
        d = json.loads((PRIVATE / 'dossiers' / f'{rid}.json').read_text())
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next((b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid), None)
        dec = next(x for x in runs[rid]['decisions'] if x['id'] == tid)
        aid = f'D{i:03d}'
        packets.append(packet(aid, d, use, res, dec['decision'], runs[rid].get('trimmed_results', {}).get(tid)))
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
    return dict(population=sum(map(len, per_item.values())), items_with_candidates=len(per_item),
                population_by_decision=_count(x['decision'] for r in runs.values() for x in r.get('decisions') or ()
                                              if x['decision'] in ('drop', 'trim')),
                sampled=len(packets), sampled_by_decision=_count(k['decision'] for k in keys),
                sampled_items=len({k['item'] for k in keys}),
                max_per_item=max(_count(k['item'] for k in keys).values()) if keys else 0,
                files={f: len(rows) for f, rows in files.items()})


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
