"""Lossless-dedup v1: measure LCC provider="rules", rules_mode="lossless" on every existing dossier set.

Offline (network guard on), no judges: each item is compacted at the pinned LCC commit, re-checked with
lcc's own verify_lossless AND with an independent check here (each replaced result's note must hold against
its kept_at result, which must be unchanged: "identical" = same lines minus the three Codex volatile header
lines; "lines a-b" = exactly those raw lines of the target), then
scored with the frozen v0-v0.5 probes (identical probe config in every protocol). Per-item records stay
under PRIVATE; the repo gets counts only.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.lossless_dedup_measure
"""
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02

LCC_PIN = dict(worktree='/Users/Master/lcc-wt-rules', commit='7b92ad2b80d6fd812ac706f3270a9ed838806514')
BENCH = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH / 'lossless-dedup-v1'
PUBLIC = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'lossless-dedup-v1'
GE = rcb.REPO / 'research' / 'goal-engine-2026-10-04'
PROBE_PROTOCOL = GE / 'real-context-bench-v0.5' / 'protocol.json'  # probes identical across v0..v0.5
SETS = {
    'claude_frozen_60': BENCH / 'real-context-v0' / 'dossiers',
    'claude_fresh_60': BENCH / 'real-context-v0' / 'fresh-dossiers',
    'claude_dev_326': BENCH / 'real-context-v0' / 'dev-dossiers',
    'codex_v04_test_60': BENCH / 'codex-heldout-v0.4' / 'dossiers',
    'codex_v05_dev_141': BENCH / 'codex-heldout-v0.5' / 'dev-dossiers',
    'codex_v05_test_60': BENCH / 'codex-heldout-v0.5' / 'dossiers',
}
# earlier counts-only results on the same dossiers: (file, arm) -> reduction_tokens / retention
PRIOR = {
    'claude_frozen_60': (GE / 'real-context-bench-v0.2' / 'score.json',
                         {'mechanical': 'mechanical', 'jev_block': 'jev_block', 'lossy_rules': 'lcc_rules_transcript'}),
    'claude_fresh_60': (GE / 'real-context-bench-v0.3' / 'score.json',
                        {'mechanical': 'mechanical', 'lossy_rules': 'lcc_rules_transcript'}),
    'codex_v04_test_60': (GE / 'real-context-bench-v0.4' / 'score.json',
                          {'mechanical': 'mechanical', 'lossy_rules': 'lcc_rules_transcript'}),
    'codex_v05_dev_141': (GE / 'real-context-bench-v0.5' / 'dev-round2.json',
                          {'mechanical': 'mechanical', 'lossy_rules': 'rules@r2-d0cb548'}),
    'codex_v05_test_60': (GE / 'real-context-bench-v0.5' / 'score.json',
                          {'mechanical': 'mechanical', 'lossy_rules': 'lcc_rules_transcript'}),
}
DEV_ITERATIONS = BENCH / 'real-context-v0' / 'dev-iterations.jsonl'  # claude dev 326: last iteration
_HEAD = re.compile(r'^(?:Chunk ID|Wall time|Process exited with code|Process running with session ID|Original token count)\b')
_VOLATILE = re.compile(r'^(?:Chunk ID|Wall time|Original token count):')


def _lines(text):
    """Independent re-implementation of the lossless comparison unit (whole lines, header-volatile out)."""
    ls = text.split('\n')
    n = 0
    while n < len(ls) and _HEAD.match(ls[n]):
        n += 1
    if n < len(ls) and ls[n] == 'Output:':
        ls = [x for x in ls[:n] if not _VOLATILE.match(x)] + ls[n:]
    return ls


def independent_check(blocks, decisions, out_text):
    """Violations found without lcc's verifier: the target must be kept unchanged in the output and the
    replaced result's note must state a claim that holds and rebuilds it."""
    res = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_result'}
    dedup = {d['id']: d for d in decisions if d.get('decision') == 'dedupe'}
    flat = rcb.collapse(out_text)
    bad = []
    for rid, d in dedup.items():
        tgt = d.get('kept_at')
        if tgt not in res or tgt in dedup:
            bad.append(f'{rid}: target {tgt} missing or itself replaced')
            continue
        if res[rid]['is_error'] != res[tgt]['is_error']:
            bad.append(f'{rid}: is_error differs from {tgt}')
        if rcb.collapse(res[tgt]['content']) not in flat:
            bad.append(f'{rid}: target {tgt} not unchanged in output')
        note, src, dst = d.get('note') or '', res[rid]['content'], res[tgt]['content']
        same = re.fullmatch(rf'\[identical output kept at {re.escape(tgt)}\]', note)
        span = re.fullmatch(rf'\[output = lines (\d+)-(\d+) of {re.escape(tgt)}\]', note)
        if same:
            ok = _lines(src) == _lines(dst)
        elif span:  # the note alone must rebuild the original: raw lines a..b (1-based) of the target
            lo, hi = int(span[1]), int(span[2])
            ok = 1 <= lo and hi <= dst.count('\n') + 1 and '\n'.join(dst.split('\n')[lo - 1:hi]) == src
        else:
            ok = False
        if not ok:
            bad.append(f'{rid}: note {note!r} does not hold against {tgt}')
        if note not in out_text:
            bad.append(f'{rid}: note not in output')
    return bad


def run_item(dossier, proto):
    from lcc.relevance import (
        TranscriptCompactionRequest,
        compact_transcript,
        messages_to_payload,
    )
    from lcc.relevance.transcript import verify_lossless
    payload = v02.rules_payload(dossier['blocks'])
    t0 = time.perf_counter()
    res = compact_transcript(TranscriptCompactionRequest(payload=payload, question=dossier['goal'],
                                                         provider='rules', rules_mode='lossless'))
    latency = round((time.perf_counter() - t0) * 1000, 1)
    out = rcb.apply_transcript(dossier['blocks'], res.decisions, res.messages)
    v_lcc = verify_lossless(payload, messages_to_payload(res.messages))
    v_ind = independent_check(dossier['blocks'], res.decisions, out)
    in_tok, method = rcb.lcc_count(dossier['text'])
    out_tok = rcb.lcc_count(out)[0]
    dedup = [d for d in res.decisions if d.get('decision') == 'dedupe']
    return dict(
        id=dossier['id'], category=dossier['category'], status='ok', latency_ms=latency,
        in_tokens=in_tok, out_tokens=out_tok, in_bytes=len(dossier['text'].encode()), out_bytes=len(out.encode()),
        token_method=method, degraded=res.report['degraded'], degradation_reason=res.report['degradation_reason'],
        report_violations=res.report['lossless_violations'], verify_lossless=v_lcc, independent=v_ind,
        tool_calls_total=res.report['tool_calls_total'], deduped=len(dedup),
        dropped=res.report['tool_calls_dropped'], trimmed=res.report['tool_calls_trimmed'],
        dedupe=[dict(id=d['id'], kept_at=d.get('kept_at'), chars=d.get('chars'), note=d.get('note')) for d in dedup],
        probes=rcb.score_item(dossier, dict(status='ok', output=out), proto),
        full_probes=rcb.score_item(dossier, dict(status='ok', output=dossier['text']), proto))


def summarize(rows):
    ins, outs = [r['in_tokens'] for r in rows], [r['out_tokens'] for r in rows]
    each = [1 - o / i for i, o in zip(ins, outs) if i]
    lat = [r['latency_ms'] for r in rows]

    def ret(key):
        items = [r[key]['item_pass'] for r in rows if r[key]['item_pass'] is not None]
        probes = [v for r in rows for v in r[key]['probes'].values() if v is not None]
        return dict(item=rcb._rate(sum(items), len(items)), probe=rcb._rate(sum(probes), len(probes)))
    return dict(
        n=len(rows), violations=dict(
            verify_lossless=sum(len(r['verify_lossless']) for r in rows),
            independent=sum(len(r['independent']) for r in rows),
            runtime_fail_safe=sum(bool(r['report_violations']) for r in rows)),
        degraded=sum(bool(r['degraded']) for r in rows),
        reduction_tokens=dict(pooled=round(1 - sum(outs) / sum(ins), 4), median_item=round(statistics.median(each), 4),
                              max_item=round(max(each), 4), items_reduced=sum(e > 0 for e in each)),
        tool_calls_total=sum(r['tool_calls_total'] for r in rows), deduped=sum(r['deduped'] for r in rows),
        dropped=sum(r['dropped'] for r in rows), trimmed=sum(r['trimmed'] for r in rows),
        dedupe_kind={k: sum(1 for r in rows for d in r['dedupe'] if (d['note'] or '').startswith(p))
                     for k, p in (('identical', '[identical'), ('line_range', '[output = lines'))},
        latency_ms=dict(median=statistics.median(lat), p90=rcb.quantile(lat, 0.9), max=max(lat)),
        retention=ret('probes'), retention_full_control=ret('full_probes'))


def prior(name):
    if name == 'claude_dev_326':
        last = json.loads(DEV_ITERATIONS.read_text().strip().splitlines()[-1])
        return dict(source='private dev-iterations.jsonl (last iteration)',
                    mechanical=last['mechanical']['reduction_tokens'], lossy_rules=last['rules']['reduction_tokens'])
    path, arms = PRIOR[name]
    a = json.loads(path.read_text())['arms']
    return dict(source=str(path.relative_to(rcb.REPO)), **{k: dict(a[v]['reduction_tokens'],
                retention_item=a[v]['retention_item']['rate']) for k, v in arms.items()})


def main(argv=None):
    proto = rcb.load_protocol(PROBE_PROTOCOL)  # sha-checked
    v02.check_lcc_rules(LCC_PIN)  # lcc from the worktree, at the pinned commit, clean tree
    os.environ.update(proto['privacy']['env'])
    out = dict(schema='lossless-dedup-measure/1', lcc=dict(LCC_PIN, branch='feat/transcript-rules-policy', pr=45),
               rules_mode='lossless', probe_protocol_sha256=rcb.sha256_file(PROBE_PROTOCOL), sets={})
    with rcb.network_guard():
        for name, root in SETS.items():
            (PRIVATE / name).mkdir(parents=True, exist_ok=True)
            rows = []
            for p in sorted(root.glob('*.json')):
                d = json.loads(p.read_text())
                r = run_item(dict(d, category=d['category'] or 'UNKNOWN'), proto)  # v0.5 dev convention
                (PRIVATE / name / p.name).write_text(json.dumps(r, ensure_ascii=False))
                rows.append(r)
            out['sets'][name] = dict(summarize(rows), prior=prior(name))
            print(name, out['sets'][name]['n'], out['sets'][name]['reduction_tokens'], file=sys.stderr)
    out['guard_trips'] = rcb.GUARD['trips']
    (PRIVATE / 'summary.json').write_text(json.dumps(out, indent=1))
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / 'summary.json').write_text(json.dumps(out, indent=1) + '\n')  # counts only: no ids, no text
    json.dump({k: dict(n=v['n'], violations=v['violations'], reduction=v['reduction_tokens']) for k, v in out['sets'].items()},
              sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
