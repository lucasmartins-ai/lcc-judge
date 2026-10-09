"""Real-context bench v0.3: aggregate the blind drop-audit verdicts (after all files were judged).

Reads private_root/audit/{key,verdicts-*}.jsonl and the private rules run, writes
private_root/audit/audit-score.json (with case ids) and a counts-only audit-summary.json
next to protocol.json. Runs offline; no LCC import needed.

    python3 -m research.real_context_bench_v03_audit
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from research.real_context_bench import wilson

PRIVATE = Path('/Users/Master/.lcc/bench/real-context-v0')
AUDIT = PRIVATE / 'audit'
HERE = Path(__file__).resolve().parent / 'goal-engine-2026-10-04' / 'real-context-bench-v0.3'
BAD = ('needed', 'unsure')


def jl(p):
    return [json.loads(x) for x in open(p) if x.strip()]


def rule_of(k):
    return f"{k['decision']}:{k['reason'].split(':')[0]}"


def tool_of(k):
    # ponytail: MCP tool names collapsed so the repo copy names no connected service
    return 'mcp' if k['tool'].startswith('mcp__') else k['tool']


def rates(vs):
    c = Counter(vs)
    n, bad, nd = len(vs), c['needed'] + c['unsure'], c['needed'] + c['not_needed']
    return dict(judged=n, needed=c['needed'], not_needed=c['not_needed'], unsure=c['unsure'],
                primary_false_drop=dict(k=bad, rate=round(bad / n, 4) if n else None, wilson95=wilson(bad, n)),
                secondary_needed_excl_unsure=dict(k=c['needed'], n=nd, rate=round(c['needed'] / nd, 4) if nd else None,
                                                  wilson95=wilson(c['needed'], nd)),
                unsure_rate=round(c['unsure'] / n, 4) if n else None)


def split(key, verdict, by):
    g = defaultdict(list)
    for aid, v in verdict.items():
        g[by(key[aid])].append(v)
    return {k: rates(vs) for k, vs in sorted(g.items())}


def main():
    proto = json.loads((HERE / 'protocol.json').read_text())
    key = {k['audit_id']: k for k in jl(AUDIT / 'key.jsonl')}
    file_ids = {f: [r['audit_id'] for r in jl(AUDIT / f'drops-{f}.jsonl')] for f in 'abc'}
    judges = {f: {r['audit_id']: r['verdict'] for r in jl(AUDIT / f'verdicts-{f}.jsonl')} for f in 'abc'}

    # join every key row to the private rules run decision (item, tool_use_id) and check it agrees
    mismatch = 0
    for k in key.values():
        run = json.loads((PRIVATE / 'fresh-runs' / 'lcc_rules_transcript' / f"{k['item']}.json").read_text())
        d = next((d for d in run['decisions'] if d['id'] == k['tool_use_id']), None)
        mismatch += not (d and d['decision'] == k['decision'] and d['reason'] == k['reason'])
    assert mismatch == 0, f'{mismatch} key rows disagree with the run decisions'

    # which judge covered which packet file (realised routing, not the planned one)
    coverage = {j: [f for f, ids in file_ids.items() if set(ids) <= set(vs)] for j, vs in judges.items()}
    # assemblies over all 150: conservative = any judge flags it; full = the one judge that saw all 150;
    # per_file = one judge per packet file, preferring a judge that saw only that file
    conservative = {a: ('needed' if any(j.get(a) == 'needed' for j in judges.values()) else
                        'unsure' if any(j.get(a) == 'unsure' for j in judges.values()) else 'not_needed')
                    for a in key}
    full = next(vs for vs in judges.values() if set(vs) == set(key))
    per_file = {}
    for f, ids in file_ids.items():
        j = min((j for j in judges if f in coverage[j]), key=lambda j: len(judges[j]))
        per_file.update({a: judges[j][a] for a in ids})
    overlap = [a for a in key if sum(a in vs for vs in judges.values()) > 1]
    agree = sum(len({vs[a] for vs in judges.values() if a in vs}) == 1 for a in overlap)

    primary = rates(list(conservative.values()))
    up = primary['primary_false_drop']['wilson95'][1]
    acc = dict(rule=proto['audit']['acceptance'], upper_wilson95=up, threshold=0.10,
               result='PASS' if up <= 0.10 else 'FAIL',
               note='k = 7 is the largest count that passes at n = 150; the result sits on the boundary')
    pop = Counter(rule_of(k) for k in key.values())
    summary = dict(
        schema='real-context-bench/0.3-audit', protocol_sha256=(HERE / 'protocol.json.sha256').read_text().split()[0],
        population_sampled=len(key), sampled_by_rule=dict(sorted(pop.items())), key_run_join_mismatches=mismatch,
        judging_as_run=dict(
            planned='one judge per file (a, b, c), each given only its own 50',
            realised={j: dict(records=len(vs), packet_files=coverage[j]) for j, vs in judges.items()},
            deviation='judge a received drops.jsonl (all 150); judges b and c received drops-a and drops-b; '
                      'drops-c was judged only by judge a. No judge saw key.jsonl.',
            double_judged=len(overlap), agreement_on_double_judged=agree),
        primary_assembly='conservative: a record counts as needed/unsure if any judge said so',
        primary=primary, acceptance=acc,
        sensitivity=dict(single_judge_all_150=rates(list(full.values())),
                         one_judge_per_file=rates(list(per_file.values()))),
        by_decision=split(key, conservative, lambda k: k['decision']),
        by_rule=split(key, conservative, rule_of),
        by_tool=split(key, conservative, tool_of),
    )
    (HERE / 'audit-summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    flagged = [dict(audit_id=a, item=key[a]['item'], tool_use_id=key[a]['tool_use_id'], rule=rule_of(key[a]),
                    tool=key[a]['tool'], verdicts={j: vs.get(a) for j, vs in judges.items() if a in vs})
               for a, v in sorted(conservative.items()) if v in BAD]
    (AUDIT / 'audit-score.json').write_text(json.dumps(dict(summary, flagged=flagged), indent=1) + '\n')
    print(json.dumps(dict(primary=primary['primary_false_drop'], acceptance=acc['result'],
                          sensitivity={k: v['primary_false_drop'] for k, v in summary['sensitivity'].items()},
                          flagged=[(f['audit_id'], f['rule'], f['verdicts']) for f in flagged]), indent=1))


if __name__ == '__main__':
    main()
