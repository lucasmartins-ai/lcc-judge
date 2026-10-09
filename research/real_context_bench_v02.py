"""Real-context bench v0.2: one offline arm, lcc_rules_transcript, on the frozen v0 sample.

Amendment of v0.1 (research/goal-engine-2026-10-04/real-context-bench-v0.2/protocol.json). New code
path only: research/real_context_bench.py (v0/v0.1 arms, probes, scoring) is imported unchanged and
its frozen sha256 is re-checked here.

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \\
        -m research.real_context_bench_v02 {run | score}
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from research import real_context_bench as rcb

BENCH_V02 = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.2'
PROTOCOL_V02 = BENCH_V02 / 'protocol.json'
ARM = 'lcc_rules_transcript'
BASELINES = ('mechanical', 'jev_block')


def load_protocol_v02(path=PROTOCOL_V02):
    proto = rcb.load_protocol(path)  # checks protocol.json.sha256
    if rcb.sha256_file(rcb.PROTOCOL_V01) != proto['amends']['sha256']:
        raise SystemExit('v0.1 protocol.json changed since the v0.2 amendment was frozen')
    if rcb.sha256_file(rcb.PROTOCOL) != proto['amends']['v0_sha256']:
        raise SystemExit('v0 protocol.json changed since the v0.2 amendment was frozen')
    for rel, want in proto['freeze']['files_sha256'].items():
        if rcb.sha256_file(rcb.REPO / rel) != want:
            raise SystemExit(f'{rel} changed since the v0.2 freeze: refusing to run')
    return proto


def check_lcc_rules(pin):
    """lcc must import from the pinned rules worktree, at the pinned commit, with a clean tree."""
    import lcc
    src = Path(pin['worktree']) / 'src'
    if src.resolve() not in Path(lcc.__file__).resolve().parents:
        raise SystemExit(f'lcc imported from {lcc.__file__}, not {src}')
    git = lambda *a: subprocess.run(['git', '-C', pin['worktree'], *a],  # noqa: E731
                                    capture_output=True, text=True, check=True).stdout.strip()
    if git('rev-parse', 'HEAD') != pin['commit']:
        raise SystemExit('rules worktree HEAD differs from the pinned commit')
    if git('status', '--porcelain', '--untracked-files=no'):
        raise SystemExit('rules worktree has uncommitted changes')


def rules_payload(blocks):
    """The v0.1 transcript payload plus each result's is_error flag, as a Claude Code transcript has it."""
    payload = rcb.transcript_payload(blocks)
    errors = {b['tool_use_id'] for b in blocks if b['kind'] == 'tool_result' and b['is_error']}
    for m in payload:
        for r in m['toolResults']:
            if r['tool_use_id'] in errors:
                r['is_error'] = True
    return payload


def make_rules_runner(dossier):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript

    def run(text, goal):
        res = compact_transcript(TranscriptCompactionRequest(
            payload=rules_payload(dossier['blocks']), question=goal, provider='rules'))
        extra = {k: res.report.get(k) for k in rcb.TRANSCRIPT_KEEP}
        extra['decisions'] = [{k: d.get(k) for k in ('id', 'decision', 'source', 'keep_call', 'keep_result',
                                                     'chars', 'chars_after', 'reason')} for d in res.decisions]
        for kind in ('keep', 'trim', 'drop'):
            extra[f'{kind}_ids'] = [d['id'] for d in res.decisions if d.get('decision') == kind]
        return rcb.apply_transcript(dossier['blocks'], res.decisions, res.messages), extra
    return run


def run_phase(root=rcb.PRIVATE, runs='runs'):
    """One pass over the 60 frozen items, network guard on, no retries, never into a non-empty dir."""
    proto = load_protocol_v02()
    sample = rcb.load_sample(root, proto)
    os.environ.update(proto['privacy']['env'])
    check_lcc_rules(proto['pins']['lcc_rules'])
    out = root / runs / ARM
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.json')):
        raise SystemExit(f'{out} already holds a run: v0.2 runs the arm once (no retries)')
    counts = defaultdict(int)
    with rcb.network_guard():
        for it in sample['items']:
            d = json.loads((root / 'dossiers' / f"{it['id']}.json").read_text())
            rec = rcb.run_item(ARM, d, make_rules_runner(d), rcb.lcc_count, proto['per_item_timeout_s'])
            counts[rec['status']] += 1
            (out / f"{it['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
    return dict(arm=ARM, items=len(sample['items']), status=dict(counts), guard_trips=rcb.GUARD['trips'])


def verdict(cand, base):
    """Stop criterion of v0, candidate vs one baseline; guard trips are the candidate arm's own."""
    ret = (cand['retention_item']['rate'] or 0) >= (base['retention_item']['rate'] or 0)
    red = (cand['reduction_tokens']['pooled'] or 0) > (base['reduction_tokens']['pooled'] or 0)
    trips = cand['guard_trips'] == 0
    return dict(retention_ge=ret, token_reduction_gt=red, zero_guard_trips=trips, wins=ret and red and trips)


def score_phase(root=rcb.PRIVATE, runs='runs', public=True):
    proto = load_protocol_v02()
    sample = rcb.load_sample(root, proto)
    dossiers = [json.loads((root / 'dossiers' / f"{it['id']}.json").read_text()) for it in sample['items']]
    recs = {}
    for arm in rcb.LOCAL_ARMS + rcb.JEV_ARMS + (ARM,):
        recs[arm] = {}
        for d in dossiers:
            p = root / runs / arm / f"{d['id']}.json"
            if p.exists():
                recs[arm][d['id']] = json.loads(p.read_text())
    score = rcb.aggregate(dossiers, recs, proto)
    score.update(schema='real-context-bench-score/0.2', protocol_sha256=rcb.sha256_file(PROTOCOL_V02),
                 amends_sha256=proto['amends']['sha256'],
                 verdict_v02={b: verdict(score['arms'][ARM], score['arms'][b]) for b in BASELINES})
    name = 'score-v0.2.json' if runs == 'runs' else f'score-v0.2-{runs}.json'
    (root / name).write_text(json.dumps(score, ensure_ascii=False, indent=1))
    if public and runs == 'runs':
        (BENCH_V02 / 'score.json').write_text(json.dumps(rcb.counts_only(score), indent=1) + '\n')
    return rcb.counts_only(score)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('run', 'score'))
    a = ap.parse_args(argv)
    res = run_phase() if a.phase == 'run' else score_phase()
    json.dump(res, sys.stdout, indent=1, default=str)
    print()


if __name__ == '__main__':
    main()
