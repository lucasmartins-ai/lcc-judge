"""Real-context bench v0.6: validate and aggregate the two-judge blind recoverability audit.

Copied from research/real_context_bench_v04_audit.py (frozen v0.4/v0.5 aggregation) and adapted ONLY to
the v0.6 judging question, its verdict labels and its isolated judge folders:

- The judging text (protocol.json audit.judging.instructions, byte-identical to the DEV text in
  research/recoverable_dev_measure.JUDGE_TEXT) asks whether the agent would plausibly need removed
  information it could NOT get back by following the recovery pointer. Its labels are needed /
  not_needed / unsure; here `needed` means needed AND unrecoverable and is reported as
  `needed_unrecoverable`.
- Packets: root/audit/f1.jsonl, f2.jsonl, f3.jsonl. Judge X works in root/judge-X/ (only its two
  packet files) and writes root/judge-X/verdicts-X.jsonl. Re-judge packets go to root/rejudge-X/
  (only rejudge-X.jsonl), answers to root/rejudge-X/verdicts-rejudge-X.jsonl.
- The unblinding key must match a `replace` decision (same note) of the recoverable arm's run.
- Splits are by pointer kind and by tool (the v0.4 decision/rule splits do not exist here).

Validity, re-judging, flagging, Wilson, acceptance and agreement are the v0.4 code unchanged:
routing f1 -> A,C; f2 -> A,B; f3 -> B,C (third judge: f1 -> B, f2 -> C, f3 -> A). A verdict is valid iff
its verdict is one of the labels and its reason, normalized (casefold, non-alphanumerics -> space,
whitespace collapsed), has >= MIN_WORDS words and is not repeated by that judge (every copy of a
repeated reason is invalid); a missing verdict is invalid. Each invalid assigned verdict is re-judged
by the record's third judge; a record still lacking two valid verdicts is flagged ("incomplete").

Primary: a record is flagged iff either final verdict is needed (needed_unrecoverable) or unsure, or it
is incomplete; flagged / n with Wilson 95%; PASS iff the upper bound <= 0.10.
Secondary: needed_unrecoverable-only / n with Wilson 95%; agreement (raw, Cohen's kappa); unsure rate.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from research.real_context_bench import wilson

OUTCOMES = ('needed', 'not_needed', 'unsure')  # the labels of the frozen judging text
BAD = ('needed', 'unsure')
MIN_WORDS = 5
FILES = ('f1', 'f2', 'f3')
JUDGES = {'A': ('f1', 'f2'), 'B': ('f2', 'f3'), 'C': ('f3', 'f1')}
THRESHOLD = 0.10
ARM = 'lcc_rules_recoverable'


def jl(p):
    p = Path(p)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def norm(reason):
    return ' '.join(re.sub(r'[^\w]+', ' ', str(reason or '').casefold()).split())


def assigned(file):
    return tuple(j for j, fs in JUDGES.items() if file in fs)


def third(file):
    return next(j for j, fs in JUDGES.items() if file not in fs)


def verdicts_path(root, j):
    return Path(root) / f'judge-{j}' / f'verdicts-{j}.jsonl'


def rejudge_dir(root, j):
    return Path(root) / f'rejudge-{j}'


def valid_verdicts(rows, also=()):
    """{audit_id: verdict} for the valid rows of one judge file. `also`: that judge's other rows whose
    reasons count for repetition (a re-judge file is checked against the judge's main file too)."""
    reasons = Counter(norm(r.get('reason')) for r in [*rows, *also])
    seen, out = Counter(r.get('audit_id') for r in rows), {}
    for r in rows:
        n = norm(r.get('reason'))
        if (r.get('verdict') in OUTCOMES and len(n.split()) >= MIN_WORDS and reasons[n] == 1
                and seen[r.get('audit_id')] == 1):
            out[r['audit_id']] = r['verdict']
    return out


def file_of(root):
    return {p['audit_id']: f for f in FILES for p in jl(Path(root) / 'audit' / f'{f}.jsonl')}


def needs_rejudge(root):
    """{third judge: [audit_id, ...]} for each assigned verdict that is missing or invalid."""
    files = file_of(root)
    valid = {j: valid_verdicts(jl(verdicts_path(root, j))) for j in JUDGES}
    out = defaultdict(list)
    for aid, f in sorted(files.items()):
        for j in assigned(f):
            if aid not in valid[j] and aid not in out[third(f)]:
                out[third(f)].append(aid)
    return dict(out)


def rejudge(root):
    packets = {p['audit_id']: p for f in FILES for p in jl(Path(root) / 'audit' / f'{f}.jsonl')}
    todo = needs_rejudge(root)
    for j, ids in todo.items():
        d = rejudge_dir(root, j)
        d.mkdir(parents=True, exist_ok=True)
        (d / f'rejudge-{j}.jsonl').write_text(''.join(json.dumps(packets[a], ensure_ascii=False) + '\n' for a in ids))
    return {j: len(ids) for j, ids in todo.items()}


def final_pairs(root):
    """{audit_id: [verdict, ...]} (two valid verdicts, or fewer when incomplete) and the substitutions."""
    files = file_of(root)
    valid = {j: valid_verdicts(jl(verdicts_path(root, j))) for j in JUDGES}
    re_valid = {j: valid_verdicts(jl(rejudge_dir(root, j) / f'verdicts-rejudge-{j}.jsonl'),
                                  jl(verdicts_path(root, j))) for j in JUDGES}
    pairs, subs = {}, 0
    for aid, f in files.items():
        vs = [valid[j][aid] for j in assigned(f) if aid in valid[j]]
        if len(vs) < 2 and aid in re_valid[third(f)]:
            vs.append(re_valid[third(f)][aid])
            subs += 1
        pairs[aid] = vs
    return pairs, subs


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in OUTCOMES) / (n * n)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else None


def flag(vs):
    return 'incomplete' if len(vs) < 2 else 'needed' if 'needed' in vs else 'unsure' if 'unsure' in vs else 'not_needed'


def rates(flags):
    c, n = Counter(flags), len(flags)
    bad = c['needed'] + c['unsure'] + c['incomplete']
    lo, hi = wilson(bad, n)
    nlo, nhi = wilson(c['needed'], n)
    return dict(n=n, needed_unrecoverable=c['needed'], unsure=c['unsure'], incomplete=c['incomplete'],
                not_needed=c['not_needed'],
                primary_flagged=dict(k=bad, rate=round(bad / n, 4) if n else None, wilson95=[lo, hi]),
                secondary_needed_unrecoverable_only=dict(k=c['needed'], rate=round(c['needed'] / n, 4) if n else None,
                                                         wilson95=[nlo, nhi]))


def aggregate(pairs, key=None):
    """pairs: {audit_id: [final verdicts]}; key: {audit_id: key row} for the unblinded splits."""
    flags = {a: flag(vs) for a, vs in pairs.items()}
    out = rates(list(flags.values()))
    up = out['primary_flagged']['wilson95'][1]
    out['acceptance'] = dict(upper_wilson95=up, threshold=THRESHOLD,
                             result='PASS' if up is not None and up <= THRESHOLD else 'FAIL')
    complete = [tuple(vs) for vs in pairs.values() if len(vs) == 2]
    verdicts = [v for vs in pairs.values() for v in vs]
    out['agreement'] = dict(pairs=len(complete), agree=sum(a == b for a, b in complete),
                            raw=round(sum(a == b for a, b in complete) / len(complete), 4) if complete else None,
                            cohen_kappa=kappa(complete))
    out['unsure_verdict_rate'] = round(verdicts.count('unsure') / len(verdicts), 4) if verdicts else None
    if key:
        for name, by in (('by_pointer_kind', lambda k: k['pointer_kind']),
                         ('by_tool', lambda k: 'mcp' if k['tool'].startswith('mcp__') else k['tool'])):
            g = defaultdict(list)
            for a, f in flags.items():
                g[by(key[a])].append(f)
            out[name] = {k: rates(v) for k, v in sorted(g.items())}
    return out


def check_key(root, key):
    """Every key row must match a `replace` decision with the same note in the recoverable run."""
    bad = 0
    for k in key.values():
        run = json.loads((Path(root) / 'runs' / ARM / f"{k['item']}.json").read_text())
        d = next((d for d in run['decisions'] if d['id'] == k['tool_use_id']), None)
        bad += not (d and d['decision'] == 'replace' and d.get('note') == k.get('recovery_pointer'))
    return bad


def score(root, public=None):
    root = Path(root)
    key = {k['audit_id']: k for k in jl(root / 'audit' / 'key.jsonl')}
    mismatch = check_key(root, key)
    if mismatch:
        raise SystemExit(f'{mismatch} key rows disagree with the run decisions')
    pending = needs_rejudge(root)
    pairs, subs = final_pairs(root)
    summary = dict(schema='real-context-bench/0.6-audit', key_run_join_mismatches=mismatch,
                   rejudge_requested={j: len(v) for j, v in pending.items()}, rejudge_substituted=subs,
                   **aggregate(pairs, key))
    flagged = [dict(audit_id=a, item=key[a]['item'], tool_use_id=key[a]['tool_use_id'], tool=key[a]['tool'],
                    pointer_kind=key[a]['pointer_kind'], verdicts=vs)
               for a, vs in sorted(pairs.items()) if flag(vs) != 'not_needed']
    (root / 'audit' / 'audit-score.json').write_text(json.dumps(dict(summary, flagged=flagged), indent=1) + '\n')
    if public:
        (Path(public) / 'audit-summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    return summary
