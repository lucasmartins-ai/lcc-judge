"""Stashed v1: rules_mode=stashed (LCC 4719fde) vs lossless / recoverable / lossy, same pin, same 847 dossiers.

One process per arm, lcc imported from the detached pin worktree /Users/Master/.lcc/bench/lcc-4719fde.
No workspace_root (offline dossiers: transcript proxy), like recoverable-v0.8. The stash goes to a
private bench dir (LCC_STASH_DIR), never ~/.cache. Every stashed output is re-checked by lcc's
verify_stashed AND by `independent_stash_check` below (no lcc code): each pointer must name the
sha256 of the exact original result bytes and the blob on disk must hash to it.
Private per-item rows: /Users/Master/.lcc/bench/stashed-v1. Public: counts only.

    PYTHONPATH=/Users/Master/.lcc/bench/lcc-4719fde/src:/Users/Master/Downloads/LCC-judge HF_HUB_OFFLINE=1 \\
    /Users/Master/LCC/.venv/bin/python -m research.stashed_v1 run --arm stashed|lossless|recoverable|lossy
    PYTHONPATH=/Users/Master/Downloads/LCC-judge /Users/Master/LCC/.venv/bin/python -m research.stashed_v1 summary
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research.lossless_dedup_measure import independent_check as dedupe_check
from research.recoverable_v08 import SETS

BENCH = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH / 'stashed-v1'
STASH = PRIVATE / 'stash'
PUBLIC = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'stashed-v1'
PIN = dict(worktree=str(BENCH / 'lcc-4719fde'), commit='4719fde')
ARMS = ('lossless', 'recoverable', 'lossy', 'stashed')
NOTE = re.compile(r'^\[removed: (\d+) tokens · lcc recall ([0-9a-f]{12})\]$')


def independent_stash_check(blocks, out_texts):
    """Pointer -> sha12 of the original bytes, blob present and hashing to its name. No lcc code."""
    orig = {b['tool_use_id']: b['content'] for b in blocks if b['kind'] == 'tool_result'}
    bad = []
    for tid, text in out_texts.items():
        if text == orig.get(tid):
            continue
        m = NOTE.match(text or '')
        if not m:
            continue  # lossless dedupe refs are checked by dedupe_check
        digest = hashlib.sha256(orig[tid].encode('utf-8')).hexdigest()
        blob = STASH / digest
        if not digest.startswith(m.group(2)):
            bad.append(dict(id=tid, why='sha_mismatch'))
        elif not blob.is_file() or hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
            bad.append(dict(id=tid, why='blob_missing_or_corrupt'))
    return bad


def run_item(d, arm):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript import verify_lossless
    payload = v02.rules_payload(d['blocks'])
    row = dict(id=d['id'], in_tokens=rcb.lcc_count(d['text'])[0])
    try:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=d['goal'], provider='rules',
                                                           rules_mode=arm))
    except Exception as e:  # noqa: BLE001 -- counted, never hidden
        return dict(row, error=f'{type(e).__name__}: {e}')
    out = rcb.apply_transcript(d['blocks'], r.decisions, r.messages)
    after = messages_to_payload(r.messages)
    texts = {x.id: x.text for m in r.messages for x in m.tool_results}
    if arm == 'stashed':
        from lcc.relevance.transcript_stash import verify_stashed
        lcc_viol = verify_stashed(payload, after)
        indep = independent_stash_check(d['blocks'], texts)
    elif arm == 'recoverable':
        from lcc.relevance.transcript_recoverable import verify_recoverable
        lcc_viol, indep = verify_recoverable(payload, after), []
    elif arm == 'lossless':
        lcc_viol, indep = verify_lossless(payload, after), dedupe_check(d['blocks'], r.decisions, out)
    else:
        lcc_viol, indep = [], []  # lossy makes no recovery claim
    return dict(row, out_tokens=rcb.lcc_count(out)[0], degraded=bool(r.report['degraded']),
                runtime_fail_safe=r.report.get('lossless_violations') or [],
                lcc_violations=len(lcc_viol), independent_violations=len(indep),
                stashed=r.report.get('tool_calls_stashed') or 0,
                counts=dict(Counter(x.get('decision') for x in r.decisions)))


def run_phase(arm):
    v02.check_lcc_rules(dict(worktree=PIN['worktree'], commit=subprocess.run(
        ['git', '-C', PIN['worktree'], 'rev-parse', PIN['commit']], capture_output=True, text=True,
        check=True).stdout.strip()))
    os.environ.update(rcb.load_protocol(rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
                                        / 'protocol.json')['privacy']['env'])
    os.environ['LCC_STASH_DIR'] = str(STASH)
    with rcb.network_guard():
        for name, root in SETS.items():
            out = PRIVATE / arm / name
            out.mkdir(parents=True, exist_ok=True)
            files = sorted(root.glob('*.json'))
            for f in files:
                (out / f.name).write_text(json.dumps(run_item(json.loads(f.read_text()), arm), ensure_ascii=False))
            print(arm, name, len(files), file=sys.stderr)
    print(json.dumps(dict(arm=arm, guard_trips=rcb.GUARD['trips'])))


def summary():
    res = {}
    for arm in ARMS:
        res[arm] = {}
        for name, root in SETS.items():
            rows = [json.loads(f.read_text()) for f in sorted((PRIVATE / arm / name).glob('*.json'))]
            if len(rows) != len(list(root.glob('*.json'))):
                raise SystemExit(f'{arm}/{name} incomplete')
            ok = [r for r in rows if 'error' not in r]
            ins, outs = sum(r['in_tokens'] for r in ok), sum(r['out_tokens'] for r in ok)
            res[arm][name] = dict(items=len(rows), errors=len(rows) - len(ok),
                                  degraded=sum(r['degraded'] for r in ok),
                                  runtime_fail_safe=sum(bool(r['runtime_fail_safe']) for r in ok),
                                  lcc_violations=sum(r['lcc_violations'] for r in ok),
                                  independent_violations=sum(r['independent_violations'] for r in ok),
                                  stashed=sum(r['stashed'] for r in ok), in_tokens=ins, out_tokens=outs,
                                  pooled_reduction=round(1 - outs / ins, 4) if ins else 0.0)
        tot_in = sum(v['in_tokens'] for v in res[arm].values())
        tot_out = sum(v['out_tokens'] for v in res[arm].values())
        res[arm]['all'] = dict(items=sum(v['items'] for v in res[arm].values()),
                               in_tokens=tot_in, out_tokens=tot_out, pooled_reduction=round(1 - tot_out / tot_in, 4),
                               **{k: sum(v[k] for v in res[arm].values() if isinstance(v, dict) and k in v)
                                  for k in ('errors', 'degraded', 'runtime_fail_safe', 'lcc_violations',
                                            'independent_violations', 'stashed')})
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / 'summary.json').write_text(json.dumps(dict(pin=PIN, results=res), indent=1))
    print(json.dumps({a: res[a]['all'] for a in ARMS}, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('run', 'summary'))
    ap.add_argument('--arm', choices=ARMS)
    a = ap.parse_args()
    run_phase(a.arm) if a.cmd == 'run' else summary()
