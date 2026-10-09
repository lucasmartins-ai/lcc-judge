"""Real-context bench v0.4: validate and aggregate the two-judge blind audit (rule fixed before judging).

Routing (protocol.json audit.judging): f1 = D001-D050, f2 = D051-D100, f3 = D101-D150;
judge A sees f1+f2, B sees f2+f3, C sees f3+f1, so each record has two assigned judges and one
third judge (f1 -> B, f2 -> C, f3 -> A).

A verdict is valid iff its verdict is needed / not_needed / unsure and its reason, normalized
(casefold, non-alphanumerics -> space, whitespace collapsed), has >= MIN_WORDS words and is not
repeated: a normalized reason that a judge gives on two or more records is generic, and every
copy is invalid. A missing verdict is invalid. Each invalid assigned verdict is re-judged by the
record's third judge (`rejudge` writes those packets); the re-judgment must be valid by the same
rule (repetition counted over that judge's main and re-judge files). A record that still lacks two valid verdicts counts as
flagged ("incomplete").

Primary: a record is flagged iff either final verdict is needed or unsure (or it is incomplete);
false-drop rate = flagged / n with Wilson 95%; PASS iff the upper bound <= 0.10.
Secondary: needed-only (either final verdict needed) / n with Wilson 95%; inter-judge agreement
(raw and Cohen's kappa over the complete pairs); unsure rate; splits by decision, rule and tool.

    python3 -m research.real_context_bench_v04_audit rejudge   # after verdicts-{A,B,C}.jsonl exist
    python3 -m research.real_context_bench_v04_audit score     # after verdicts-rejudge-*.jsonl, if any
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from research.real_context_bench import wilson

PRIVATE = Path('/Users/Master/.lcc/bench/codex-heldout-v0.4')
HERE = Path(__file__).resolve().parent / 'goal-engine-2026-10-04' / 'real-context-bench-v0.4'
OUTCOMES = ('needed', 'not_needed', 'unsure')
BAD = ('needed', 'unsure')
MIN_WORDS = 5
FILES = ('f1', 'f2', 'f3')
JUDGES = {'A': ('f1', 'f2'), 'B': ('f2', 'f3'), 'C': ('f3', 'f1')}
THRESHOLD = 0.10


def jl(p):
    p = Path(p)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def norm(reason):
    return ' '.join(re.sub(r'[^\w]+', ' ', str(reason or '').casefold()).split())


def assigned(file):
    return tuple(j for j, fs in JUDGES.items() if file in fs)


def third(file):
    return next(j for j, fs in JUDGES.items() if file not in fs)


def valid_verdicts(rows, also=()):
    """{audit_id: verdict} for the valid rows of one judge file (rule in the module doc). `also`: that
    judge's other rows whose reasons count for repetition (a re-judge file is checked against the
    judge's main file too)."""
    reasons = Counter(norm(r.get('reason')) for r in [*rows, *also])
    seen, out = Counter(r.get('audit_id') for r in rows), {}
    for r in rows:
        n = norm(r.get('reason'))
        if (r.get('verdict') in OUTCOMES and len(n.split()) >= MIN_WORDS and reasons[n] == 1
                and seen[r.get('audit_id')] == 1):
            out[r['audit_id']] = r['verdict']
    return out


def file_of(root):
    return {p['audit_id']: f for f in FILES for p in jl(root / 'audit' / f'{f}.jsonl')}


def needs_rejudge(root=PRIVATE):
    """{third judge: [audit_id, ...]} for each assigned verdict that is missing or invalid."""
    files = file_of(root)
    valid = {j: valid_verdicts(jl(root / 'audit' / f'verdicts-{j}.jsonl')) for j in JUDGES}
    out = defaultdict(list)
    for aid, f in sorted(files.items()):
        for j in assigned(f):
            if aid not in valid[j] and aid not in out[third(f)]:
                out[third(f)].append(aid)
    return dict(out)


def rejudge(root=PRIVATE):
    packets = {p['audit_id']: p for f in FILES for p in jl(root / 'audit' / f'{f}.jsonl')}
    todo = needs_rejudge(root)
    for j, ids in todo.items():
        (root / 'audit' / f'rejudge-{j}.jsonl').write_text(
            ''.join(json.dumps(packets[a], ensure_ascii=False) + '\n' for a in ids))
    return {j: len(ids) for j, ids in todo.items()}


def final_pairs(root=PRIVATE):
    """{audit_id: [verdict, ...]} (two valid verdicts, or fewer when incomplete) and the substitutions."""
    files = file_of(root)
    valid = {j: valid_verdicts(jl(root / 'audit' / f'verdicts-{j}.jsonl')) for j in JUDGES}
    re_valid = {j: valid_verdicts(jl(root / 'audit' / f'verdicts-rejudge-{j}.jsonl'),
                                  jl(root / 'audit' / f'verdicts-{j}.jsonl')) for j in JUDGES}
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
    return dict(n=n, needed=c['needed'], unsure=c['unsure'], incomplete=c['incomplete'], not_needed=c['not_needed'],
                primary_flagged=dict(k=bad, rate=round(bad / n, 4) if n else None, wilson95=[lo, hi]),
                secondary_needed_only=dict(k=c['needed'], rate=round(c['needed'] / n, 4) if n else None,
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
        for name, by in (('by_decision', lambda k: k['decision']),
                         ('by_rule', lambda k: f"{k['decision']}:{(k.get('reason') or '').split(':')[0]}"),
                         ('by_tool', lambda k: 'mcp' if k['tool'].startswith('mcp__') else k['tool'])):
            g = defaultdict(list)
            for a, f in flags.items():
                g[by(key[a])].append(f)
            out[name] = {k: rates(v) for k, v in sorted(g.items())}
    return out


def check_key(root, key):
    """Every key row must match the private rules run decision (item, tool_use_id)."""
    bad = 0
    for k in key.values():
        run = json.loads((root / 'runs' / 'lcc_rules_transcript' / f"{k['item']}.json").read_text())
        d = next((d for d in run['decisions'] if d['id'] == k['tool_use_id']), None)
        bad += not (d and d['decision'] == k['decision'] and d.get('reason') == k.get('reason'))
    return bad


def score(root=PRIVATE, public=HERE):
    key = {k['audit_id']: k for k in jl(root / 'audit' / 'key.jsonl')}
    mismatch = check_key(root, key)
    if mismatch:
        raise SystemExit(f'{mismatch} key rows disagree with the run decisions')
    pending = needs_rejudge(root)
    pairs, subs = final_pairs(root)
    summary = dict(schema='real-context-bench/0.4-audit', key_run_join_mismatches=mismatch,
                   rejudge_requested={j: len(v) for j, v in pending.items()}, rejudge_substituted=subs,
                   **aggregate(pairs, key))
    flagged = [dict(audit_id=a, item=key[a]['item'], tool_use_id=key[a]['tool_use_id'], decision=key[a]['decision'],
                    reason=key[a].get('reason'), tool=key[a]['tool'], verdicts=vs)
               for a, vs in sorted(pairs.items()) if flag(vs) != 'not_needed']
    (root / 'audit' / 'audit-score.json').write_text(json.dumps(dict(summary, flagged=flagged), indent=1) + '\n')
    if public:
        (Path(public) / 'audit-summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('phase', choices=('rejudge', 'score'))
    a = ap.parse_args(argv)
    json.dump(rejudge() if a.phase == 'rejudge' else score(), sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
