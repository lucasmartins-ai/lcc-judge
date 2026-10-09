"""Dev-split loop for LCC's offline transcript policy (compact_transcript provider="rules").

The frozen real-context sample (PRIVATE/sample.json, 60 ids) is the test set: this script never
opens PRIVATE/dossiers/ or PRIVATE/runs/. It builds dev dossiers from the rest of pool.json with
the frozen harness's own dossier builder, then scores two arms with the harness's probes:

    mechanical  compact_context(provider='mechanical', MECH_KW)   -- block mode, the v0 baseline
    rules       compact_transcript(provider='rules')               -- the policy under development

Dev = pool ids not in the sample, mapped, >= 1 assistant record, labeled (owner_v1 > pool label >
labels-claude-extra), confidence != low, and from a session that has no sample item (no
same-session leakage into the test set).

    PYTHONPATH=<lcc worktree>/src:/Users/Master/Downloads/LCC-judge HF_HUB_OFFLINE=1 \\
        /Users/Master/LCC/.venv/bin/python -m research.transcript_rules_dev {build | eval --note '...'}

Outputs stay private: PRIVATE/dev-dossiers/, PRIVATE/dev-runs/, and one counts-only line per
iteration in PRIVATE/dev-iterations.jsonl.
"""
import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone

from research import real_context_bench as rcb

PRIVATE = rcb.PRIVATE
DEV_DOSSIERS = PRIVATE / 'dev-dossiers'
DEV_RUNS = PRIVATE / 'dev-runs'
ITERATIONS = PRIVATE / 'dev-iterations.jsonl'


def dev_items(pool, sample, extra):
    test_ids = {it['id'] for it in sample['items']}
    test_sessions = {it['session_hash'] for it in sample['items']}
    out = []
    for rid, v in sorted(pool.items()):
        if rid in test_ids or v['session_hash'] in test_sessions or not v.get('mapped'):
            continue
        if v.get('ctx_assistant', 0) < 1:
            continue
        if 'owner_v1' in v:
            label, conf, src = v['owner_v1'], v.get('confidence'), 'owner_v1'
        elif 'label' in v:
            label, conf, src = v['label'], v.get('confidence'), v.get('label_source')
        elif rid in extra:
            label, conf, src = extra[rid]['label'], extra[rid].get('confidence'), extra[rid].get('label_source')
        else:
            continue
        if conf == 'low':
            continue
        out.append(dict(id=rid, category=label, label_source=src, confidence=conf, path=v['path'],
                        uuid=v['uuid'], session_hash=v['session_hash']))
    return out


def build_phase():
    proto = rcb.load_protocol()
    sample = rcb.load_sample(PRIVATE, proto)  # sha-checked; read for its ids/sessions only
    pool = json.loads((PRIVATE / 'pool.json').read_text())
    extra = {}
    for line in (PRIVATE / 'labels-claude-extra.jsonl').read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            extra[d['id']] = d
    rl = rcb.load_request_log(proto['pins']['request_log_ruleset_sha256_prefix'])
    DEV_DOSSIERS.mkdir(exist_ok=True)
    built, failed, empty = 0, 0, 0
    for item in dev_items(pool, sample, extra):
        try:
            d = rcb.build_dossier(item, rl.redact)
        except (KeyError, OSError, ValueError):
            failed += 1
            continue
        if not d['blocks']:
            empty += 1
            continue
        (DEV_DOSSIERS / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False))
        built += 1
    return dict(built=built, failed=failed, empty=empty)


def run_mechanical(d):
    from lcc.relevance import RelevanceCompactionRequest, compact_context
    res = compact_context(RelevanceCompactionRequest(text=d['text'], question=d['goal'], provider='mechanical',
                                                     **rcb.MECH_KW))
    return res.compacted_text


def payload_for(blocks, mode):
    """'harness': rcb.transcript_payload exactly (it does not forward is_error).
    'is_error': the same payload plus each result's is_error flag, as a Claude Code transcript has it."""
    payload = rcb.transcript_payload(blocks)
    if mode == 'is_error':
        errors = {b['tool_use_id'] for b in blocks if b['kind'] == 'tool_result' and b['is_error']}
        for m in payload:
            for r in m['toolResults']:
                if r['tool_use_id'] in errors:
                    r['is_error'] = True
    return payload


def run_rules(d, payload_mode='harness', **kw):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript
    res = compact_transcript(TranscriptCompactionRequest(
        payload=payload_for(d['blocks'], payload_mode), question=d['goal'], provider='rules', **kw))
    return rcb.apply_transcript(d['blocks'], res.decisions, res.messages), res.report


def _row(d, out, proto):
    s = rcb.score_item(d, dict(status='ok', output=out), proto)
    collapsed = rcb.collapse(out)
    every = {}  # stricter view: all 8 probes on every item, whatever its category
    for name in proto['probes']['defs']:
        targets = rcb.probe_targets(name, d['blocks'], d['goal'], proto['probes']['min_chars'])
        every[name] = None if targets is None else all(rcb.collapse(t) in collapsed for t in targets)
    return dict(id=d['id'], category=d['category'], item_pass=s['item_pass'], probes=s['probes'],
                all_probes=every, in_tokens=rcb.lcc_count(d['text'])[0], out_tokens=rcb.lcc_count(out)[0])


def _summary(rows):
    scored = [r['item_pass'] for r in rows if r['item_pass'] is not None]
    ins = sum(r['in_tokens'] for r in rows)
    outs = sum(r['out_tokens'] for r in rows)
    each = [1 - r['out_tokens'] / r['in_tokens'] for r in rows if r['in_tokens']]
    probe_fail = {}
    for r in rows:
        for name, v in r['probes'].items():
            if v is False:
                probe_fail[name] = probe_fail.get(name, 0) + 1
    every = {}
    for r in rows:
        for name, v in r['all_probes'].items():
            if v is not None:
                k, n = every.get(name, (0, 0))
                every[name] = (k + v, n + 1)
    return dict(items=len(rows), retention_item=dict(k=sum(scored), n=len(scored)),
                all_probes_pass={name: dict(k=k, n=n) for name, (k, n) in sorted(every.items())},
                reduction_tokens=dict(pooled=round(1 - outs / ins, 4) if ins else None,
                                      median_item=round(statistics.median(each), 4) if each else None),
                probe_failures=dict(sorted(probe_fail.items())))


def eval_phase(note, rules_kw, payload_mode='harness'):
    import lcc
    proto = rcb.load_protocol()
    paths = sorted(DEV_DOSSIERS.glob('*.json'))
    DEV_RUNS.mkdir(exist_ok=True)
    mech_cache = DEV_RUNS / 'mechanical.json'
    mech = json.loads(mech_cache.read_text()) if mech_cache.exists() else {}
    mech_rows, rules_rows, errors = [], [], 0
    reasons = {}
    t0 = time.perf_counter()
    with rcb.network_guard():
        for p in paths:
            d = json.loads(p.read_text())
            if d['id'] not in mech:
                mech[d['id']] = _row(d, run_mechanical(d), proto)
            mech_rows.append(mech[d['id']])
            try:
                out, report = run_rules(d, payload_mode, **rules_kw)
            except Exception as exc:  # an arm error fails every applicable probe, as in the harness
                errors += 1
                print(f"{d['id']}: {type(exc).__name__}: {exc}", file=sys.stderr)
                rules_rows.append(dict(_row(d, '', proto), out_tokens=rcb.lcc_count(d['text'])[0]))
                continue
            for dec in report['decisions']:
                rule = dec['reason'].split(':')[0]
                reasons[rule] = reasons.get(rule, 0) + 1
            rules_rows.append(_row(d, out, proto))
    mech_cache.write_text(json.dumps(mech))
    (DEV_RUNS / 'rules-last.json').write_text(json.dumps(rules_rows))
    m, r = _summary(mech_rows), _summary(rules_rows)
    rate = lambda s: s['retention_item']['k'] / s['retention_item']['n']  # noqa: E731
    line = dict(at=datetime.now(timezone.utc).isoformat(timespec='seconds'), note=note, rules_kw=rules_kw,
                payload=payload_mode,
                lcc_file=lcc.__file__, dossiers=len(paths), mechanical=m, rules=r, rules_errors=errors,
                decision_reasons=dict(sorted(reasons.items())), guard_trips=rcb.GUARD['trips'],
                seconds=round(time.perf_counter() - t0, 1),
                target=dict(retention_ge_mechanical=rate(r) >= rate(m),
                            pooled_reduction_ge_020=(r['reduction_tokens']['pooled'] or 0) >= 0.20))
    with ITERATIONS.open('a') as fh:
        fh.write(json.dumps(line) + '\n')
    return line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='phase', required=True)
    sub.add_parser('build')
    e = sub.add_parser('eval')
    e.add_argument('--note', required=True)
    e.add_argument('--kw', default='{}', help='extra TranscriptCompactionRequest kwargs as JSON')
    e.add_argument('--payload', choices=('harness', 'is_error'), default='harness')
    a = ap.parse_args(argv)
    res = build_phase() if a.phase == 'build' else eval_phase(a.note, json.loads(a.kw), a.payload)
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
