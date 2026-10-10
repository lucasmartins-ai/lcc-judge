"""Recoverable-mode DEV measure + DEV audit packets (DEV sets only; never opens a TEST set).

Owner decision 2026-10-10: removing an old tool output is fine when the agent can get it back by
re-reading a file or re-running a read-only command. This runs LCC provider="rules" in all three
rules modes (lossless, recoverable, lossy) at the same pinned commit on the two already-used DEV sets,
re-checks every recoverable output with lcc's verify_recoverable AND an independent check here, and
draws a 100-record blind audit of the `replace` decisions with the NEW judging question (JUDGE_TEXT).

The bench has no workspace snapshot from prompt time (today's disk is not the disk the agent saw), so
recoverable runs with workspace_root=None: recoverability_check = "transcript_proxy".

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.recoverable_dev_measure {run|audit}
"""
import argparse
import json
import os
import random
import re
import shlex
import statistics
import sys
from collections import Counter
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03
from research import real_context_bench_v04 as v04
from research.lossless_dedup_measure import independent_check as dedupe_check

LCC_PIN = dict(worktree='/Users/Master/lcc-wt-rules', commit='1bc2005')  # expanded to the full sha at run time
BENCH = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH / 'recoverable-dev-v1'
PUBLIC = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'recoverable-dev-v1'
SETS = {  # already used for policy work; the held-out TEST sets are never read here
    'claude_dev_326': BENCH / 'real-context-v0' / 'dev-dossiers',
    'codex_v05_dev_141': BENCH / 'codex-heldout-v0.5' / 'dev-dossiers',
}
MODES = ('lossless', 'recoverable', 'lossy')
AUDIT_N, AUDIT_CAP, AUDIT_SEED = 100, 3, 20261010
CLIP_OUTPUT = 3000
JUDGE_TEXT = (
    "You see a user request sent to a coding agent, the last few conversation turns before it, and one "
    "earlier tool call (tool, tool_input). A context-compaction step removed that call's output from the "
    "agent's context and left only recovery_pointer in its place: this is exactly what the agent now sees "
    "where the output was. removed_output shows the output that was removed (head and tail if long; "
    "removed_output_chars is its full length). The agent can follow the pointer at any time: re-read the "
    "named file (or line range) or re-run the named command, and it will get whatever that returns NOW, "
    "not necessarily what it returned then. Judge only from what is shown: to handle this request "
    "correctly, would the agent plausibly need information in removed_output that it could NOT get back "
    "by following the pointer? Answer needed when the removed content was needed and following the pointer "
    "would plausibly not return it (for example the file or repository state was changed afterwards and the "
    "old content itself matters, or the pointer does not identify how to get it back). Answer not_needed "
    "when the removed content is not needed for this request, or when following the pointer would give the "
    "agent what it needs. Answer unsure when the shown context is not enough to tell. Give one sentence of "
    "reason specific to this record (what the removed output holds and why it is or is not needed and "
    "recoverable). A generic reason reused across records is invalid. Do not guess what policy made the "
    "choice. Output one JSON line per record: {\"audit_id\": ..., \"verdict\": "
    "\"needed\"|\"not_needed\"|\"unsure\", \"reason\": ...}."
)

# --- independent check (no lcc code): every replace must be a pointer to its own call's file or command --
_META = re.compile(r'[|;&<>`$\n\\()]')
_READ_PROGS = {'ls', 'pwd', 'wc', 'cat', 'head', 'nl', 'grep', 'egrep', 'fgrep', 'tree', 'tail', 'rg', 'find', 'sed'}
_WRITE_TOOLS = re.compile(r'edit|write|patch|notebook|create|delete|move|rename', re.I)
_WRITE_CMD = re.compile(r'(>|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btouch\b|\bgit\s+(checkout|switch|reset|stash|'
                        r'restore|pull|merge|rebase|apply|am|cherry-pick|revert|clean|mv|rm)\b|apply_patch|'
                        r'\bpython|\bnode\b|\bnpm\b|\bpnpm\b|\bbun\b|\bperl\b|\bruby\b)')
_PATHTOK = re.compile(r'[\w./~@+-]*[\w~@+-]')  # path-like tokens; suffix match on '/' boundaries
FILE_PTR = re.compile(r'^\[removed: re-read (.+?)(?: \(lines (\d+)-(\d+)\))? to recover\]$')
CMD_PTR = re.compile(r'^\[removed: re-run `(.+)` to recover\]$', re.S)


def _input(use):
    try:
        v = json.loads(use['content'])
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _cmd(use):
    v = _input(use)
    c = v.get('command', v.get('cmd'))
    if isinstance(c, list) and len(c) == 3 and c[1] in ('-c', '-lc'):
        return c[2]
    return shlex.join(c) if isinstance(c, list) else c if isinstance(c, str) else None


def _read_only(cmd):
    if not cmd or _META.search(cmd):
        return False
    try:
        a = shlex.split(cmd)
    except ValueError:
        return False
    prog = a[0].rsplit('/', 1)[-1] if a else ''
    if prog == 'git':
        return len(a) > 1 and a[1] in ('status', 'diff', 'log', 'show') and not any(x.startswith('--output') for x in a)
    if prog == 'find':
        return not {'-exec', '-execdir', '-delete', '-ok', '-okdir'} & set(a)
    if prog == 'sed':
        return len(a) == 4 and a[1] == '-n'
    return prog in _READ_PROGS or (len(a) == 2 and a[1] in ('--version', '-V', 'version'))


def _writes_path(use, path):
    """A later call that may have changed `path` (conservative: names it and is not a plain read)."""
    toks = set(_PATHTOK.findall(use['content'].replace('\\n', '\n')))
    if not any(t == path or t.endswith('/' + path) or path.endswith('/' + t) for t in toks):
        return False
    if use['tool_name'] in ('Read', 'view', 'read_file', 'NotebookRead', 'Grep', 'Glob'):
        return False
    cmd = _cmd(use)
    if cmd is not None:
        return not _read_only(cmd) and bool(_WRITE_CMD.search(cmd))
    return bool(_WRITE_TOOLS.search(use['tool_name']))


def independent_replace_check(blocks, decisions, out_text):
    uses = [b for b in blocks if b['kind'] == 'tool_use']
    res = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_result'}
    pos = {b['tool_use_id']: i for i, b in enumerate(uses)}
    flat = rcb.collapse(out_text)
    bad = []
    for b in blocks:  # texts and tool inputs never change
        if b['kind'] in ('text', 'tool_use') and b['content'].strip() and rcb.collapse(b['content']) not in flat:
            bad.append(f"{b.get('tool_use_id') or b['m']}: {b['kind']} changed or missing")
    for d in decisions:
        if d.get('decision') != 'replace':
            continue
        rid, note = d['id'], d.get('note') or ''
        use = uses[pos[rid]] if rid in pos else None
        if use is None or rid not in res:
            bad.append(f'{rid}: no call/result')
            continue
        if res[rid]['is_error']:
            bad.append(f'{rid}: error result replaced')
        if note not in out_text:
            bad.append(f'{rid}: pointer not in output')
        if len(note) >= len(res[rid]['content']):
            bad.append(f'{rid}: pointer not shorter')
        if (m := CMD_PTR.match(note)):
            if m[1] != _cmd(use) or not _read_only(m[1]):
                bad.append(f'{rid}: command pointer not its own read-only command')
        elif (m := FILE_PTR.match(note)):
            path = m[1]
            own = _input(use).get('file_path') or _input(use).get('path')
            cmd = _cmd(use)
            if path != own and not (cmd and _read_only(cmd) and shlex.split(cmd)[-1] == path):
                bad.append(f'{rid}: file pointer names another path')
            if any(_writes_path(u, path) for u in uses[pos[rid] + 1:]):
                bad.append(f'{rid}: file {path} possibly written later')
        else:
            bad.append(f'{rid}: not a recovery pointer: {note[:60]!r}')
    return bad


# --- run ------------------------------------------------------------------------------------------
def run_item(dossier):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript_recoverable import verify_recoverable
    payload = v02.rules_payload(dossier['blocks'])
    in_tok = rcb.lcc_count(dossier['text'])[0]
    row = dict(id=dossier['id'], category=dossier['category'], in_tokens=in_tok, modes={})
    for mode in MODES:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=dossier['goal'],
                                                           provider='rules', rules_mode=mode))
        out = rcb.apply_transcript(dossier['blocks'], r.decisions, r.messages)
        m = dict(out_tokens=rcb.lcc_count(out)[0], degraded=r.report['degraded'],
                 counts=dict(Counter(d.get('decision') for d in r.decisions)))
        if mode == 'recoverable':
            m.update(recoverability_check=r.report.get('recoverability_check'),
                     runtime_fail_safe=r.report['lossless_violations'],
                     verify_recoverable=verify_recoverable(payload, messages_to_payload(r.messages)),
                     independent=independent_replace_check(dossier['blocks'], r.decisions, out)
                     + dedupe_check(dossier['blocks'], r.decisions, out),
                     replaced=[dict(id=d['id'], note=d['note'], kind=d['recover']['kind'],
                                    ranged=bool(d['recover'].get('lines')), chars=d.get('chars'),
                                    tool=next(b['tool_name'] for b in dossier['blocks']
                                              if b['kind'] == 'tool_use' and b['tool_use_id'] == d['id']))
                               for d in r.decisions if d.get('decision') == 'replace'],
                     keep_reasons=dict(Counter(d.get('reason') for d in r.decisions if d.get('decision') == 'keep')))
        row['modes'][mode] = m
    return row


def _red(rows, mode):
    ins = [r['in_tokens'] for r in rows]
    outs = [r['modes'][mode]['out_tokens'] for r in rows]
    each = [1 - o / i for i, o in zip(ins, outs) if i]
    return dict(pooled=round(1 - sum(outs) / sum(ins), 4), median_item=round(statistics.median(each), 4),
                max_item=round(max(each), 4), items_reduced=sum(e > 0 for e in each))


def summarize(rows):
    rec = [r['modes']['recoverable'] for r in rows]
    reps = [x for m in rec for x in m['replaced']]
    ll = [r['modes']['lossless']['out_tokens'] for r in rows]
    rv = [r['modes']['recoverable']['out_tokens'] for r in rows]
    return dict(
        n=len(rows),
        violations=dict(verify_recoverable=sum(len(m['verify_recoverable']) for m in rec),
                        independent=sum(len(m['independent']) for m in rec),
                        runtime_fail_safe=sum(bool(m['runtime_fail_safe']) for m in rec)),
        degraded={k: sum(bool(r['modes'][k]['degraded']) for r in rows) for k in MODES},
        recoverability_check=dict(Counter(m['recoverability_check'] for m in rec)),
        reduction_tokens={k: _red(rows, k) for k in MODES},
        recoverable_extra_vs_lossless=dict(
            pooled_tokens_saved=sum(ll) - sum(rv), share_of_lossless_out=round(1 - sum(rv) / sum(ll), 4),
            median_item=round(statistics.median([1 - b / a for a, b in zip(ll, rv) if a]), 4)),
        decisions={k: dict(sum((Counter(r['modes'][k]['counts']) for r in rows), Counter())) for k in MODES},
        pointers=dict(total=len(reps), items_with_pointer=sum(bool(m['replaced']) for m in rec),
                      by_kind=dict(Counter(('file_range' if x['ranged'] else 'file_whole') if x['kind'] == 'file'
                                           else 'command' for x in reps)),
                      by_tool=dict(Counter(x['tool'] for x in reps).most_common()),
                      by_program=dict(Counter(_prog(x) for x in reps).most_common()),
                      replaced_chars=sum(x['chars'] or 0 for x in reps)),
        recoverable_keep_reasons=dict(sum((Counter(m['keep_reasons']) for m in rec), Counter()).most_common()))


def _prog(x):
    if x['kind'] == 'file' and x['tool'] in ('Read', 'view', 'read_file', 'NotebookRead'):
        return x['tool']
    m = CMD_PTR.match(x['note'])
    try:
        a = shlex.split(m[1]) if m else []
    except ValueError:
        a = []
    return (' '.join(a[:2]) if a[:1] == ['git'] else a[0]) if a else x['tool']


def pin():
    import subprocess
    full = subprocess.run(['git', '-C', LCC_PIN['worktree'], 'rev-parse', LCC_PIN['commit']], capture_output=True,
                          text=True, check=True).stdout.strip()
    p = dict(LCC_PIN, commit=full)
    v02.check_lcc_rules(p)
    return p


def run_phase():
    p = pin()
    proto = rcb.load_protocol(rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5' / 'protocol.json')
    os.environ.update(proto['privacy']['env'])
    out = dict(schema='recoverable-dev-measure/1', lcc=dict(p, branch='feat/transcript-rules-policy', pr=45),
               workspace_root=None, sets={})
    with rcb.network_guard():
        for name, root in SETS.items():
            (PRIVATE / name).mkdir(parents=True, exist_ok=True)
            rows = []
            for f in sorted(root.glob('*.json')):
                d = json.loads(f.read_text())
                r = run_item(dict(d, category=d['category'] or 'UNKNOWN'))
                (PRIVATE / name / f.name).write_text(json.dumps(r, ensure_ascii=False))
                rows.append(r)
            out['sets'][name] = summarize(rows)
            print(name, out['sets'][name]['violations'], out['sets'][name]['reduction_tokens'], file=sys.stderr)
    allrows = [json.loads(f.read_text()) for n in SETS for f in sorted((PRIVATE / n).glob('*.json'))]
    out['pooled_dev'] = summarize(allrows)
    out['guard_trips'] = rcb.GUARD['trips']
    (PRIVATE / 'summary.json').write_text(json.dumps(out, indent=1))
    PUBLIC.mkdir(parents=True, exist_ok=True)
    pub = json.loads(json.dumps(out))
    for s in [*pub['sets'].values(), pub['pooled_dev']]:
        s['pointers'].pop('by_program')  # program names only; still counts, but keep the public file minimal
    (PUBLIC / 'summary.json').write_text(json.dumps(pub, indent=1) + '\n')  # counts only
    return {k: dict(violations=v['violations'], reduction=v['reduction_tokens'], pointers=v['pointers']['by_kind'])
            for k, v in [*out['sets'].items(), ('pooled_dev', out['pooled_dev'])]}


# --- audit ----------------------------------------------------------------------------------------
def audit_phase():
    out = PRIVATE / 'dev-audit'
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob('*.jsonl')):
        raise SystemExit(f'{out} already holds packets: the audit sample is drawn once')
    per_item, rows = {}, {}
    for name in SETS:
        for f in sorted((PRIVATE / name).glob('*.json')):
            r = json.loads(f.read_text())
            key = f'{name}/{r["id"]}'
            rows[key] = r
            ids = [x['id'] for x in r['modes']['recoverable']['replaced']]
            if ids:
                per_item[key] = ids
    picked = v03.audit_select(per_item, AUDIT_SEED, AUDIT_N, AUDIT_CAP)
    packets, keys = [], []
    for i, (key, tid) in enumerate(picked, 1):
        name, rid = key.split('/')
        d = json.loads((SETS[name] / f'{rid}.json').read_text())
        use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
        res = next(b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid)
        rep = next(x for x in rows[key]['modes']['recoverable']['replaced'] if x['id'] == tid)
        clean = lambda s, n: v04.strip_note(v03.clip(v04.strip_note(s), n))  # noqa: E731
        aid = f'P{i:03d}'
        packets.append(dict(audit_id=aid, request=v04.strip_note(d['goal']),
                            recent_turns=[dict(t, text=clean(t['text'], v03.CLIP_TURN)) for t in v03.last_turns(d['blocks'])],
                            tool=use['tool_name'], tool_input=clean(use['content'], v03.CLIP_INPUT),
                            recovery_pointer=rep['note'], removed_output=clean(res['content'], CLIP_OUTPUT),
                            removed_output_chars=len(res['content'])))
        keys.append(dict(audit_id=aid, set=name, item=rid, category=d['category'], tool_use_id=tid, tool=use['tool_name'],
                         pointer_kind=('file_range' if rep['ranged'] else 'file_whole') if rep['kind'] == 'file' else 'command'))
    dump = lambda p, rs: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rs))  # noqa: E731
    dump(out / 'key.jsonl', keys)  # unblinding key: never shown to judges
    for j, seed in (('A', 1), ('B', 2)):  # both judges see all 100, each in its own order
        order = packets[:]
        random.Random(AUDIT_SEED + seed).shuffle(order)
        dump(out / f'judge-{j}.jsonl', order)
    (out / 'instructions.txt').write_text(JUDGE_TEXT + '\n')
    return dict(seed=AUDIT_SEED, population=sum(map(len, per_item.values())), items_with_candidates=len(per_item),
                sampled=len(packets), sampled_items=len({k['item'] for k in keys}),
                sampled_by_set=dict(Counter(k['set'] for k in keys)),
                sampled_by_kind=dict(Counter(k['pointer_kind'] for k in keys)),
                judge_files={j: str(out / f'judge-{j}.jsonl') for j in 'AB'},
                instructions=str(out / 'instructions.txt'), key=str(out / 'key.jsonl'),
                verdicts_expected={j: str(out / f'verdicts-{j}.jsonl') for j in 'AB'})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('run', 'audit'))
    a = ap.parse_args(argv)
    json.dump(run_phase() if a.phase == 'run' else audit_phase(), sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
