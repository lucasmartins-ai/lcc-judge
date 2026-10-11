"""Recoverable-mode DEV re-measure at the v0.6-review fix (LCC f1c5ff7) + 90-record DEV audit packets.

DEV sets only: the two v1 DEV sets plus the spent v0.6 Hermes TEST dossiers (now DEV). Never opens v0.7 TEST.
Runs rules_mode="recoverable" (and lossless as the baseline) at the pinned commit, re-checks every output with
lcc's verify_recoverable AND the independent check below (no lcc code), and draws a 90-record audit stratified
by pointer kind (30 each when available) into two 45-record packet files, each alone in its own judge folder.
Packets are the v0.6 / v1 DEV packet field for field (research/real_context_bench_v06_test.packet).

    PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \\
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python -m research.recoverable_dev_v2 {run|audit}
"""
import argparse
import json
import os
import random
import re
import shlex
import sys
from collections import Counter
from pathlib import Path

from research import real_context_bench as rcb
from research import real_context_bench_v02 as v02
from research import real_context_bench_v03 as v03
from research import real_context_bench_v06_test as v06t
from research import recoverable_dev_measure as rdm
from research.lossless_dedup_measure import independent_check as dedupe_check

LCC_PIN = dict(worktree='/Users/Master/lcc-wt-rules', commit='f1c5ff7')
BENCH = Path('/Users/Master/.lcc/bench')
PRIVATE = BENCH / 'heldout-v0.7'
RUNS = PRIVATE / 'dev-runs'
PUBLIC = rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'recoverable-dev-v2'
SETS = {
    'claude_dev_326': BENCH / 'real-context-v0' / 'dev-dossiers',
    'codex_v05_dev_141': BENCH / 'codex-heldout-v0.5' / 'dev-dossiers',
    'hermes_v06_spent_60': BENCH / 'heldout-v0.6' / 'dossiers',  # spent TEST, used as DEV from here on
}
MODES = ('lossless', 'recoverable')
KINDS = ('file_whole', 'file_range', 'command')
AUDIT_PER_KIND, AUDIT_CAP, AUDIT_SEED = 30, 3, 20261011
NUMBERED = re.compile(r'^\s*(\d+)[\t→|]')


# --- independent check v2 (no lcc code): cwd-aware pointers, ranges, later writes, duplicate ids -----------
def _own_cwd(use):
    v = rdm._input(use).get('workdir') or rdm._input(use).get('cwd')
    return v if isinstance(v, str) and v else None


def _cmd_args(cmd):
    try:
        a = shlex.split(cmd)
    except ValueError:
        return None
    return a


def _later_write(use):
    """Conservative: a later call that may write anything (not a plain read)."""
    if use['tool_name'] in ('Read', 'view', 'read_file', 'NotebookRead', 'Grep', 'Glob', 'search_files', 'skill_view'):
        return False
    cmd = rdm._cmd(use)
    if cmd is not None:
        return not rdm._read_only(cmd)
    return bool(rdm._WRITE_TOOLS.search(use['tool_name'])) or use['tool_name'] in ('execute_code', 'exec')


def independent_check_v2(blocks, decisions, out_text):
    uses = [b for b in blocks if b['kind'] == 'tool_use']
    ids = Counter(b['tool_use_id'] for b in uses)
    res = {b['tool_use_id']: b for b in blocks if b['kind'] == 'tool_result'}
    pos = {b['tool_use_id']: i for i, b in enumerate(uses)}
    flat = rcb.collapse(out_text)
    bad = []
    for b in blocks:
        if b['kind'] in ('text', 'tool_use') and b['content'].strip() and rcb.collapse(b['content']) not in flat:
            bad.append(f"{b.get('tool_use_id') or b['m']}: {b['kind']} changed or missing")
    for d in decisions:
        if d.get('decision') != 'replace':
            continue
        rid, note = d['id'], d.get('note') or ''
        if ids[rid] != 1 or rid not in res:
            bad.append(f'{rid}: duplicated or missing call/result')
            continue
        use, body = uses[pos[rid]], res[rid]['content']
        later = uses[pos[rid] + 1:]
        cwd = _own_cwd(use)
        if res[rid]['is_error']:
            bad.append(f'{rid}: error result replaced')
        if note not in out_text:
            bad.append(f'{rid}: pointer not in output')
        if len(note) >= len(body):
            bad.append(f'{rid}: pointer not shorter')
        cmd = rdm._cmd(use)
        if cmd is not None and note == f"[removed: re-run `{cmd}`{f' in {cwd}' if cwd else ''} to recover]":
            if not rdm._read_only(cmd):
                bad.append(f'{rid}: command not read-only')
            a = _cmd_args(cmd) or []
            paths = [x for x in a[1:] if not x.startswith('-')]
            broad = a[:1] == ['git'] or not paths or any(x in ('.', './', '..', '~', '/') for x in paths)
            for u in later:
                if _later_write(u) and (broad or rdm._writes_path(u, paths[0]) or any(p in u['content'] for p in paths)):
                    bad.append(f'{rid}: command output possibly changed by a later write')
                    break
            continue
        m = re.match(r'^\[removed: re-read (.+?)(?: \(lines (\d+)-(\d+)\))?(?: \(cwd (.+)\))? to recover\]$', note)
        if not m:
            bad.append(f'{rid}: not a recovery pointer of its own call: {note[:60]!r}')
            continue
        path, lo, hi, pcwd = m[1], m[2], m[3], m[4]
        own = rdm._input(use).get('file_path') or rdm._input(use).get('path')
        if path != own and not (cmd and rdm._read_only(cmd) and (_cmd_args(cmd) or [''])[-1] == path):
            bad.append(f'{rid}: file pointer names another path')
        if pcwd != cwd:
            bad.append(f'{rid}: pointer cwd differs from the call cwd')
        if lo is not None:
            lo, hi = int(lo), int(hi)
            nums = [int(x[1]) for ln in body.splitlines() if ln.strip() and (x := NUMBERED.match(ln))]
            if lo < 1 or hi < lo:
                bad.append(f'{rid}: empty or reversed range')
            elif nums and len(nums) == sum(bool(ln.strip()) for ln in body.splitlines()) and (nums[0], nums[-1]) != (lo, hi):
                bad.append(f'{rid}: range {lo}-{hi} differs from the numbered output {nums[0]}-{nums[-1]}')
        if any(rdm._writes_path(u, path) for u in later):
            bad.append(f'{rid}: file {path} possibly written later')
    return bad


# --- run --------------------------------------------------------------------------------------------------
def run_item(dossier):
    from lcc.relevance import TranscriptCompactionRequest, compact_transcript, messages_to_payload
    from lcc.relevance.transcript_recoverable import verify_recoverable
    payload = v02.rules_payload(dossier['blocks'])
    row = dict(id=dossier['id'], category=dossier['category'], in_tokens=rcb.lcc_count(dossier['text'])[0], modes={})
    for mode in MODES:
        r = compact_transcript(TranscriptCompactionRequest(payload=payload, question=dossier['goal'],
                                                           provider='rules', rules_mode=mode))
        out = rcb.apply_transcript(dossier['blocks'], r.decisions, r.messages)
        m = dict(out_tokens=rcb.lcc_count(out)[0], degraded=r.report['degraded'],
                 counts=dict(Counter(d.get('decision') for d in r.decisions)))
        if mode == 'recoverable':
            tools = {b['tool_use_id']: b['tool_name'] for b in dossier['blocks'] if b['kind'] == 'tool_use'}
            m.update(recoverability_check=r.report.get('recoverability_check'),
                     runtime_fail_safe=r.report['lossless_violations'],
                     verify_recoverable=verify_recoverable(payload, messages_to_payload(r.messages)),
                     independent=independent_check_v2(dossier['blocks'], r.decisions, out)
                     + dedupe_check(dossier['blocks'], r.decisions, out),
                     replaced=[dict(id=d['id'], note=d['note'], kind=v06t.pointer_kind(d), chars=d.get('chars'),
                                    tool=tools.get(d['id'])) for d in r.decisions if d.get('decision') == 'replace'],
                     keep_reasons=dict(Counter(d.get('reason') for d in r.decisions if d.get('decision') == 'keep')))
        row['modes'][mode] = m
    return row


def summarize(rows):
    rec = [r['modes']['recoverable'] for r in rows]
    reps = [x for m in rec for x in m['replaced']]
    return dict(
        n=len(rows),
        violations=dict(verify_recoverable=sum(len(m['verify_recoverable']) for m in rec),
                        independent=sum(len(m['independent']) for m in rec),
                        runtime_fail_safe=sum(bool(m['runtime_fail_safe']) for m in rec)),
        degraded={k: sum(bool(r['modes'][k]['degraded']) for r in rows) for k in MODES},
        recoverability_check=dict(Counter(m['recoverability_check'] for m in rec)),
        reduction_tokens={k: rdm._red(rows, k) for k in MODES},
        decisions={k: dict(sum((Counter(r['modes'][k]['counts']) for r in rows), Counter())) for k in MODES},
        pointers=dict(total=len(reps), items_with_pointer=sum(bool(m['replaced']) for m in rec),
                      by_kind={k: sum(x['kind'] == k for x in reps) for k in KINDS},
                      by_tool=dict(Counter(x['tool'] for x in reps).most_common()),
                      replaced_chars=sum(x['chars'] or 0 for x in reps)),
        recoverable_keep_reasons=dict(sum((Counter(m['keep_reasons']) for m in rec), Counter()).most_common()))


def run_phase():
    import subprocess
    full = subprocess.run(['git', '-C', LCC_PIN['worktree'], 'rev-parse', LCC_PIN['commit']], capture_output=True,
                          text=True, check=True).stdout.strip()
    p = dict(LCC_PIN, commit=full)
    v02.check_lcc_rules(p)
    proto = rcb.load_protocol(rcb.REPO / 'research' / 'goal-engine-2026-10-04' / 'real-context-bench-v0.5' / 'protocol.json')
    os.environ.update(proto['privacy']['env'])
    out = dict(schema='recoverable-dev-measure/2', lcc=dict(p, branch='feat/transcript-rules-policy', pr=45),
               workspace_root=None, sets={})
    with rcb.network_guard():
        for name, root in SETS.items():
            (RUNS / name).mkdir(parents=True, exist_ok=True)
            rows = []
            for f in sorted(root.glob('*.json')):
                d = json.loads(f.read_text())
                r = run_item(dict(d, category=d['category'] or 'UNKNOWN'))
                (RUNS / name / f.name).write_text(json.dumps(r, ensure_ascii=False))
                rows.append(r)
            out['sets'][name] = summarize(rows)
            print(name, out['sets'][name]['violations'], file=sys.stderr)
    out['pooled_dev'] = summarize([json.loads(f.read_text()) for n in SETS for f in sorted((RUNS / n).glob('*.json'))])
    out['guard_trips'] = rcb.GUARD['trips']
    (RUNS / 'summary.json').write_text(json.dumps(out, indent=1))
    PUBLIC.mkdir(parents=True, exist_ok=True)
    pub = json.loads(json.dumps(out))
    for s in [*pub['sets'].values(), pub['pooled_dev']]:
        s['pointers'].pop('by_tool')  # tool names stay private; counts only
    (PUBLIC / 'summary.json').write_text(json.dumps(pub, indent=1) + '\n')
    return {k: dict(violations=v['violations'], reduction=v['reduction_tokens']['recoverable'],
                    pointers=v['pointers']['by_kind'])
            for k, v in [*out['sets'].items(), ('pooled_dev', out['pooled_dev'])]}


# --- audit ------------------------------------------------------------------------------------------------
def audit_phase():
    out = PRIVATE / 'dev-audit'
    judges = [PRIVATE / 'dev-judge-1', PRIVATE / 'dev-judge-2']
    if any(out.glob('*.jsonl')) or any(j.exists() for j in judges):
        raise SystemExit('dev audit packets already exist: the sample is drawn once')
    rows, pools = {}, {k: {} for k in KINDS}
    for name in SETS:
        for f in sorted((RUNS / name).glob('*.json')):
            r = json.loads(f.read_text())
            key = f'{name}/{r["id"]}'
            rows[key] = r
            for x in r['modes']['recoverable']['replaced']:
                pools[x['kind']].setdefault(key, []).append(x['id'])
    total = AUDIT_PER_KIND * len(KINDS)
    picked = {k: v03.audit_select(pools[k], AUDIT_SEED + i, AUDIT_PER_KIND, AUDIT_CAP) for i, k in enumerate(KINDS)}
    short = total - sum(map(len, picked.values()))
    spare = {k: [p for p in v03.audit_select(pools[k], AUDIT_SEED + i, 10 ** 6, AUDIT_CAP) if p not in set(picked[k])]
             for i, k in enumerate(KINDS)}
    while short > 0 and any(spare.values()):  # a kind short of 30: fill round-robin from kinds with spares
        for k in KINDS:
            if short > 0 and spare[k]:
                picked[k].append(spare[k].pop(0))
                short -= 1
    rng = random.Random(AUDIT_SEED)
    groups = ([], [])
    for k in KINDS:  # stratified split: alternate each kind's shuffled picks between g1 and g2
        ps = picked[k][:]
        rng.shuffle(ps)
        for i, p in enumerate(ps):
            groups[i % 2].append((k, p))
    if len(groups[0]) != len(groups[1]):  # odd kind counts: move one to balance 45/45
        big, small = sorted(groups, key=len, reverse=True)
        while len(big) - len(small) > 1:
            small.append(big.pop())
    packets, keys = {}, []
    n = 0
    for g, recs in zip(('g1', 'g2'), groups):
        rng.shuffle(recs)
        packets[g] = []
        for kind, (key, tid) in recs:
            n += 1
            name, rid = key.split('/')
            d = json.loads((SETS[name] / f'{rid}.json').read_text())
            use = next(b for b in d['blocks'] if b['kind'] == 'tool_use' and b['tool_use_id'] == tid)
            res = next(b for b in d['blocks'] if b['kind'] == 'tool_result' and b['tool_use_id'] == tid)
            rep = next(x for x in rows[key]['modes']['recoverable']['replaced'] if x['id'] == tid)
            aid = f'D{n:03d}'
            packets[g].append(v06t.packet(aid, d, use, res, rep['note']))
            keys.append(dict(audit_id=aid, file=g, set=name, item=rid, category=d['category'], tool_use_id=tid,
                             tool=use['tool_name'], recovery_pointer=rep['note'], pointer_kind=kind))
    out.mkdir(parents=True, exist_ok=True)
    dump = lambda p, rs: p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rs))  # noqa: E731
    dump(out / 'key.jsonl', keys)  # unblinding key: never shown to judges
    for g in packets:
        dump(out / f'{g}.jsonl', packets[g])
    (out / 'instructions.txt').write_text(rdm.JUDGE_TEXT)
    for g, jd in zip(('g1', 'g2'), judges):  # isolated judge folders: only that judge's packet file
        jd.mkdir()
        (jd / f'{g}.jsonl').write_bytes((out / f'{g}.jsonl').read_bytes())
    blob = [json.dumps(p, ensure_ascii=False) for ps in packets.values() for p in ps]
    return dict(seed=AUDIT_SEED, population={k: sum(map(len, pools[k].values())) for k in KINDS},
                sampled=len(keys), per_file={g: len(ps) for g, ps in packets.items()},
                sampled_by_kind=dict(Counter(k['pointer_kind'] for k in keys)),
                by_kind_per_file={g: dict(Counter(k['pointer_kind'] for k in keys if k['file'] == g)) for g in packets},
                sampled_by_set=dict(Counter(k['set'] for k in keys)),
                max_per_item=max(Counter((k['set'], k['item']) for k in keys).values()),
                lcc_marker_packets=sum('[... lcc:' in b for b in blob),
                judge_folders={str(j): sorted(p.name for p in j.iterdir()) for j in judges},
                key=str(out / 'key.jsonl'), instructions=str(out / 'instructions.txt'),
                sha256={p.name: rcb.sha256_file(p) for p in sorted(out.glob('*.jsonl'))})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('run', 'audit'))
    a = ap.parse_args(argv)
    json.dump(run_phase() if a.phase == 'run' else audit_phase(), sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
