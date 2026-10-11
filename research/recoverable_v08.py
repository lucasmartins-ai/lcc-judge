"""Recoverable v0.8: the v0.7-review fix (LCC 4c39161) is a subset of the v0.7 pin (653eeae), on every dossier set.

Each pin runs in its own process (both import `lcc`), from its own clean worktree:
    old     653eeae  /Users/Master/.lcc/bench/lcc-653eeae (detached)   rules_mode=recoverable (its defaults)
    new     4c39161  /Users/Master/lcc-wt-rules                         rules_mode=recoverable (command pointers off)
    new_cmd 4c39161  /Users/Master/lcc-wt-rules                         same + allow_command_pointers=True
    new_lossless     4c39161, rules_mode=lossless (baseline for what recoverable adds; not part of the subset proof)
No workspace_root (dossiers are offline: transcript proxy). Every output is re-checked with lcc's
verify_recoverable of that pin AND research.recoverable_check_v4 + the dedupe check (no lcc code).
`compare` proves per item: replaced tool_use_ids at new (and new_cmd) are a subset of those at old.
Private per-item rows: /Users/Master/.lcc/bench/recoverable-v0.8. Public: counts only.

    PYTHONPATH=<pin src>:/Users/Master/Downloads/LCC-judge HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \\
    /Users/Master/LCC/.venv/bin/python -m research.recoverable_v08 run --pin old|new|new_cmd
    PYTHONPATH=/Users/Master/Downloads/LCC-judge /Users/Master/LCC/.venv/bin/python -m research.recoverable_v08 compare
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v06_test as v06t
from research.lossless_dedup_measure import independent_check as dedupe_check
from research.recoverable_check_v4 import independent_check_v4

BENCH = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH / 'recoverable-v0.8'
PUBLIC = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'recoverable-v0.8'
PINS = {
    'old': dict(worktree=str(BENCH / 'lcc-653eeae'), commit='653eeae', allow_command_pointers=None),
    'new': dict(worktree='/Users/Master/lcc-wt-rules', commit='4c39161', allow_command_pointers=None),
    'new_cmd': dict(worktree='/Users/Master/lcc-wt-rules', commit='4c39161', allow_command_pointers=True),
    'new_lossless': dict(worktree='/Users/Master/lcc-wt-rules', commit='4c39161', allow_command_pointers=None,
                         mode='lossless'),  # baseline only: what recoverable adds over lossless
}
SETS = {  # spent / TEST sets are only read here; nothing is written next to them
    'claude_frozen_60': BENCH / 'real-context-v0' / 'dossiers',
    'claude_fresh_60': BENCH / 'real-context-v0' / 'fresh-dossiers',
    'claude_dev_326': BENCH / 'real-context-v0' / 'dev-dossiers',
    'codex_v04_test_60': BENCH / 'codex-heldout-v0.4' / 'dossiers',
    'codex_v05_dev_141': BENCH / 'codex-heldout-v0.5' / 'dev-dossiers',
    'codex_v05_test_60': BENCH / 'codex-heldout-v0.5' / 'dossiers',
    'hermes_v06_test_60_spent': BENCH / 'heldout-v0.6' / 'dossiers',
    'hermes_v07_test_80_spent': BENCH / 'heldout-v0.7' / 'dossiers',
}
KINDS = ('file_whole', 'file_range', 'command')


def _full(commit, wt):
    return subprocess.run(['git', '-C', wt, 'rev-parse', commit], capture_output=True, text=True,
                          check=True).stdout.strip()


def run_item(d, allow_cmd, mode='recoverable'):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript import verify_lossless
    from lcc.relevance.transcript_recoverable import verify_recoverable
    payload = v02.rules_payload(d['blocks'])
    kw = {} if allow_cmd is None else dict(allow_command_pointers=allow_cmd)
    row = dict(id=d['id'], in_tokens=rcb.lcc_count(d['text'])[0])
    try:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=d['goal'], provider='rules',
                                                           rules_mode=mode, **kw))
    except Exception as e:  # noqa: BLE001 -- counted, never hidden
        return dict(row, error=f'{type(e).__name__}: {e}')
    out = rcb.apply_transcript(d['blocks'], r.decisions, r.messages)
    return dict(row, out_tokens=rcb.lcc_count(out)[0], degraded=bool(r.report['degraded']),
                recoverability_check=r.report.get('recoverability_check'),
                runtime_fail_safe=r.report['lossless_violations'],
                verify_recoverable=(verify_recoverable if mode == 'recoverable' else verify_lossless)(
                    payload, messages_to_payload(r.messages), **kw),
                independent=(independent_check_v4(d['blocks'], r.decisions, out)
                             + dedupe_check(d['blocks'], r.decisions, out)),
                replaced={x['id']: v06t.pointer_kind(x) for x in r.decisions if x.get('decision') == 'replace'},
                keep_reason={x['id']: x.get('reason') for x in r.decisions if x.get('decision') == 'keep'},
                counts=dict(Counter(x.get('decision') for x in r.decisions)))


def run_phase(pin):
    p = PINS[pin]
    v02.check_lcc_rules(dict(worktree=p['worktree'], commit=_full(p['commit'], p['worktree'])))
    os.environ.update(rcb.load_protocol(rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5'
                                        / 'protocol.json')['privacy']['env'])
    res = {}
    with rcb.network_guard():
        for name, root in SETS.items():
            out = PRIVATE / pin / name
            out.mkdir(parents=True, exist_ok=True)
            n = 0
            for f in sorted(root.glob('*.json')):
                (out / f.name).write_text(json.dumps(run_item(json.loads(f.read_text()), p['allow_command_pointers'],
                                                              p.get('mode', 'recoverable')),
                                                     ensure_ascii=False))
                n += 1
            res[name] = n
            print(pin, name, n, file=sys.stderr)
    return dict(pin=pin, commit=_full(p['commit'], p['worktree']), items=res, guard_trips=rcb.GUARD['trips'])


def _load(pin, name):
    rows = [json.loads(f.read_text()) for f in sorted((PRIVATE / pin / name).glob('*.json'))]
    return {r['id']: r for r in rows}


def _side(rows):
    ok = [r for r in rows if 'error' not in r]
    ins, outs = sum(r['in_tokens'] for r in ok), sum(r['out_tokens'] for r in ok)
    reps = Counter(k for r in ok for k in r['replaced'].values())
    return dict(errors=len(rows) - len(ok),
                violations=dict(verify_recoverable=sum(len(r['verify_recoverable']) for r in ok),
                                independent_v4=sum(len(r['independent']) for r in ok),
                                runtime_fail_safe=sum(bool(r['runtime_fail_safe']) for r in ok)),
                items_with_violation=sum(bool(r['verify_recoverable'] or r['independent'] or r['runtime_fail_safe'])
                                         for r in ok),
                degraded=sum(r['degraded'] for r in ok),
                replaced=sum(reps.values()), replaced_by_kind={k: reps[k] for k in KINDS},
                items_with_pointer=sum(bool(r['replaced']) for r in ok),
                in_tokens=ins, out_tokens=outs, pooled_reduction=round(1 - outs / ins, 4) if ins else 0.0)


def _compare(name, new_pin):
    old, new = _load('old', name), _load(new_pin, name)
    if set(old) != set(new) or len(old) != len(list((SETS[name]).glob('*.json'))):
        raise SystemExit(f'{name}: item sets differ between pins or are incomplete')
    viol, removed, removed_kind, token_mismatch = [], Counter(), Counter(), 0
    for rid in sorted(old):
        o, n = old[rid], new[rid]
        if 'error' in o or 'error' in n:
            continue
        token_mismatch += o['in_tokens'] != n['in_tokens']
        extra = set(n['replaced']) - set(o['replaced'])
        if extra:
            viol.append(dict(item=rid, extra=len(extra)))
        for tid in set(o['replaced']) - set(n['replaced']):
            removed[n['keep_reason'].get(tid) or 'dedupe_lossless'] += 1  # keep|dedupe|replace only
            removed_kind[o['replaced'][tid]] += 1
    return dict(items=len(old), subset_violations=len(viol), subset_violation_items=viol,
                in_token_mismatch=token_mismatch, old=_side(list(old.values())), new=_side(list(new.values())),
                removed_by_fix=sum(removed.values()), removed_by_reason=dict(removed.most_common()),
                removed_by_kind={k: removed_kind[k] for k in KINDS})


def compare_phase():
    out = dict(schema='recoverable-v0.8/1',
               pins={k: dict(commit=_full(v['commit'], v['worktree']), mode=v.get('mode', 'recoverable'),
                             allow_command_pointers=v['allow_command_pointers']) for k, v in PINS.items()},
               worktrees=dict(old='detached worktree of LCC at 653eeae (outside ~/LCC)',
                              new='feat/transcript-rules-policy (PR #45)'),
               workspace_root=None, checker='research.recoverable_check_v4.independent_check_v4 + dedupe check',
               comparisons={})
    lossless = {name: _side(list(_load('new_lossless', name).values())) for name in SETS}
    out['lossless_new'] = dict(sets={k: dict(pooled_reduction=v['pooled_reduction'], errors=v['errors'],
                                             violations=dict(verify_lossless=v['violations']['verify_recoverable'],
                                                             **{x: v['violations'][x] for x in
                                                                ('independent_v4', 'runtime_fail_safe')}))
                                     for k, v in lossless.items()},
                               pooled_reduction=round(1 - sum(v['out_tokens'] for v in lossless.values())
                                                      / sum(v['in_tokens'] for v in lossless.values()), 4))
    for new_pin in ('new', 'new_cmd'):
        sets = {name: _compare(name, new_pin) for name in SETS}
        keys = ('in_tokens', 'out_tokens')
        pooled = {side: {k: sum(s[side][k] for s in sets.values()) for k in keys} for side in ('old', 'new')}
        out['comparisons'][new_pin] = dict(
            sets=sets,
            totals=dict(items=sum(s['items'] for s in sets.values()),
                        subset_violations=sum(s['subset_violations'] for s in sets.values()),
                        removed_by_fix=sum(s['removed_by_fix'] for s in sets.values()),
                        removed_by_reason=dict(sum((Counter(s['removed_by_reason']) for s in sets.values()),
                                                   Counter()).most_common()),
                        **{f'{side}_{k}': sum(s[side][k] for s in sets.values())
                           for side in ('old', 'new') for k in ('replaced', 'errors', 'items_with_violation')},
                        new_violations={k: sum(s['new']['violations'][k] for s in sets.values())
                                        for k in ('verify_recoverable', 'independent_v4', 'runtime_fail_safe')},
                        old_violations={k: sum(s['old']['violations'][k] for s in sets.values())
                                        for k in ('verify_recoverable', 'independent_v4', 'runtime_fail_safe')},
                        pooled_reduction={side: round(1 - v['out_tokens'] / v['in_tokens'], 4)
                                          for side, v in pooled.items()}))
    (PRIVATE / 'summary.json').write_text(json.dumps(out, indent=1))
    for c in out['comparisons'].values():  # public: counts only, no item ids
        for s in c['sets'].values():
            s.pop('subset_violation_items')
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / 'summary.json').write_text(json.dumps(out, indent=1) + '\n')
    return {k: v['totals'] for k, v in out['comparisons'].items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('run', 'compare'))
    ap.add_argument('--pin', choices=tuple(PINS))
    a = ap.parse_args(argv)
    json.dump(run_phase(a.pin) if a.phase == 'run' else compare_phase(), sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
