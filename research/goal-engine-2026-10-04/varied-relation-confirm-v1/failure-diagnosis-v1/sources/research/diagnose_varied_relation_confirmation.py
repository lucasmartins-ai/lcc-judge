"""Exposed-final error diagnosis using saved logits only, never an adoption fit.

Reuses independent receipt/math readers. Hypothetical cutoffs are diagnostic,
not deployed or copied to a candidate. No model imports, inference, tools or APIs.
"""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from research.audit_tool_relation_confirmation import load, sha
from research.audit_tool_relation_support import normalized_semantic_rows
from research.audit_tool_role_support import audited_scores, close, digest, disposition, reduce_metrics
from research.audit_varied_relation_dev import read_population
from research.detached_varied_study import now, save

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'research/goal-engine-2026-10-04/varied-relation-confirm-v1'
EVALUATION = BASE/'evaluation-v1'
DATA = BASE/'supervision-v1'
OUT = BASE/'failure-diagnosis-v1'
KEYS = ('101','202','303','scalar')
SOURCES = [
    'research/diagnose_varied_relation_confirmation.py', 'research/audit_tool_role_support.py',
    'research/audit_tool_relation_support.py', 'research/audit_varied_relation_dev.py',
    'research/audit_tool_relation_confirmation.py', 'research/audit_tool_relation_state_supervision.py',
    'research/audit_tool_relation_states.py', 'research/audit_tool_relation_weights.py',
    'research/detached_varied_study.py', 'tests/test_varied_relation_failure_diagnosis.py',
]


def strict_auc(positive, negative):
    if not positive or not negative:
        return None
    ordered = sorted(negative)
    return sum(bisect_left(ordered,p) for p in positive)/(len(positive)*len(negative))


def retention_cutoff(rows, scores, support):
    """Exact highest cutoff retaining .95 positives/contradictions in all slices."""
    if len(rows) != len(scores) or any(r['id'] != s['id'] for r,s in zip(rows,scores)):
        raise ValueError('Complete aligned diagnostic population required')
    cutoff = math.nextafter(max(s['score'] for r,s in zip(rows,scores) if r['label'] is not None),math.inf)
    for cohort in ('overall','primary','seen_control'):
        for field in ('goal_language','report_language'):
            for language in ('en','pt'):
                for contradictions in (False,True):
                    group = [s for r,s in zip(rows,scores) if r['label'] == 1 and r[field] == language
                             and (cohort == 'overall' or r['family'].startswith(cohort+':'))
                             and (not contradictions or r['fact_truth'] is False)]
                    if not group:
                        raise ValueError('Every cohort/language needs relevant and contradiction observations')
                    eligible = sorted(s['score'] for s in group if s['support_score'] < support)
                    allowance = len(group)//20
                    if len(eligible) > allowance:
                        cutoff = min(cutoff,eligible[allowance])
    return cutoff


def summary(rows, scores, thresholds, scalar=False):
    paired = list(zip(rows,scores,strict=True))
    kinds = ('positive','negative','semantic_unknown','structural_unknown')
    counts = {k:Counter() for k in kinds}
    for row,score in paired:
        kind = ('positive' if row['label'] == 1 else 'negative' if row['label'] == 0
                else 'structural_unknown' if row['unknown_kind'] == 'unbound_record' else 'semantic_unknown')
        counts[kind][disposition(score,thresholds,scalar)] += 1
    result = dict(n=len(rows),dispositions={k:{d:counts[k][d] for d in ('KEEP','DROP','UNKNOWN')} for k in kinds})
    if counts['positive'].total() and counts['negative'].total():
        result.update(reduce_metrics(normalized_semantic_rows(rows),scores,thresholds,scalar))
    else:
        n = counts['semantic_unknown'].total()
        result.update(semantic_unknown_recognition=counts['semantic_unknown']['UNKNOWN']/n if n else None,
                      unknown_drops=counts['semantic_unknown']['DROP']+counts['structural_unknown']['DROP'])
    return result


def breakdown(rows, scores, thresholds, field, scalar=False, binary_only=False):
    buckets = defaultdict(list)
    for row,score in zip(rows,scores,strict=True):
        if binary_only and row['label'] is None:
            continue
        if field == 'unknown_kind' and row['label'] is not None:
            continue
        buckets[str(row[field])].append((row,score))
    return {key:summary([r for r,s in pairs],[s for r,s in pairs],thresholds,scalar)
            for key,pairs in sorted(buckets.items())}


def prepare():
    if OUT.exists():
        raise ValueError('New immutable diagnosis destination required')
    audited = load(EVALUATION/'audit.json')
    if audited['status'] != 'PASS' or audited['seed_passes'] != [False,False,False]:
        raise ValueError('Completed independently audited negative confirmation required')
    names = [EVALUATION/'protocol.json',EVALUATION/'summary.json',EVALUATION/'process-exit.json',EVALUATION/'audit.json',
             DATA/'final.jsonl.gz',DATA/'final-views.jsonl.gz',BASE/'design-v2/protocol.json']
    names += [EVALUATION/k/name for k in KEYS for name in ('unique-scores.json','metrics.json')]
    p = dict(schema='exposed-varied-relation-failure-diagnosis/0.1',frozen_at_utc=now(),
             evaluation_protocol_sha256=audited['protocol_sha256'],sources={n:sha(ROOT/n) for n in SOURCES},
             files={str(n.relative_to(ROOT)):sha(n) for n in names},
             action='Recount all4 saved populations, error cohorts, support discrimination and explicitly final-fitted hypothetical cutoff diagnostics',
             hypothetical_cutoffs='All24 positive/contradiction query/report/cohort constraints; fixed support then all-semantic-UNKNOWN support. Neither is an adoption policy or full two-axis optimum.',
             original_thresholds_changed=False,final_exposed=True,model_forwards=0,API_calls=0,
             quality_approved=False,default_changed=False,P2_admission=False,
             scope=audited['scope'])
    p['sha256'] = digest(p)
    OUT.mkdir()
    for name,value in p['sources'].items():
        target = OUT/'sources'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write((ROOT/name).read_bytes())
        if sha(target) != value:
            raise ValueError('Source changed during freeze')
    save(OUT/'protocol.json',p)
    return p


def run():
    p = prepare()
    save(OUT/'started.json',dict(protocol_sha256=p['sha256'],utc=now()))
    evaluation = load(EVALUATION/'protocol.json')
    rows,views = read_population(DATA,'final')
    first = {}
    for row,view in zip(rows,views):
        if row['projected_input_hash'] is not None:
            first.setdefault(row['projected_input_hash'],(row,view))
    keys = sorted(first)
    unique_rows,unique_views = [first[k][0] for k in keys],[first[k][1] for k in keys]
    results = {}
    for key in KEYS:
        scalar = key == 'scalar'
        raw = audited_scores(EVALUATION/key/'unique-scores.json',unique_rows,unique_views,evaluation,scalar)
        assert raw['complete'] is True and raw['error'] is None
        lookup = {s['input_hash']:s for s in raw['rows']}
        scores = []
        for row in rows:
            saved = lookup.get(row['projected_input_hash'])
            score = dict(id=row['id'],status='UNKNOWN',score=None,support_score=None)
            if saved is not None:
                score.update(status='SCORED',score=saved['score'],support_score=None if scalar else saved['logits'][2])
            scores.append(score)
        receipt = load(EVALUATION/key/'metrics.json')
        thresholds = receipt['thresholds']
        measured = summary(rows,scores,thresholds,scalar)
        close(measured,receipt['metrics']['overall'])
        result = dict(original=measured,by_requested_role=breakdown(rows,scores,thresholds,'requested_role',scalar,True),
                      by_reported_role=breakdown(rows,scores,thresholds,'observed_role',scalar,True),
                      by_pair=breakdown(rows,scores,thresholds,'family',scalar,True),
                      by_goal_language=breakdown(rows,scores,thresholds,'goal_language',scalar),
                      by_report_language=breakdown(rows,scores,thresholds,'report_language',scalar),
                      by_intent_alias=breakdown(rows,scores,thresholds,'intent_alias',scalar),
                      by_report_caption=breakdown(rows,scores,thresholds,'report_caption',scalar),
                      by_unknown_kind=breakdown(rows,scores,thresholds,'unknown_kind',scalar))
        if not scalar:
            semantic = [s for r,s in zip(rows,scores) if r['label'] is None and r['unknown_kind'] != 'unbound_record']
            supported = [s for r,s in zip(rows,scores) if r['label'] is not None]
            result['support_pooled_auc'] = strict_auc([s['support_score'] for s in semantic],[s['support_score'] for s in supported])
            fixed = dict(support=thresholds['support'],relevance=retention_cutoff(rows,scores,thresholds['support']))
            # At fixed support, lowering relevance can prevent UNKNOWN DROP but
            # cannot increase recognition as UNKNOWN. This is exposed diagnosis.
            unsafe = [s['score'] for s in semantic if s['support_score'] < fixed['support']]
            safe = dict(fixed,relevance=min([fixed['relevance'],*unsafe]))
            all_unknown = min(s['support_score'] for s in semantic)
            refit = dict(support=all_unknown,relevance=retention_cutoff(rows,scores,all_unknown))
            result['hypothetical_final_fitted_cutoffs'] = {
                'fixed_support_retention':dict(thresholds=fixed,metrics=summary(rows,scores,fixed)),
                'fixed_support_zero_unknown_drops':dict(thresholds=safe,metrics=summary(rows,scores,safe)),
                'all_semantic_unknown_recognized':dict(thresholds=refit,metrics=summary(rows,scores,refit)),
            }
            result['hypothetical_scope'] = 'Final-fitted diagnostics only; never serving cutoffs. All-UNKNOWN forces100%recognition rather than95%; does not prove optimality among all two-axis policies.'
        save(OUT/f'{key}.json',dict(protocol_sha256=p['sha256'],candidate=key,**result,
                                  finished_at_utc=now(),model_forwards=0,original_thresholds_changed=False,quality_approved=False))
        results[key] = dict(pooled_auc=measured['pooled_auc'],support_pooled_auc=result.get('support_pooled_auc'))
        print('COMPLETE',key,results[key],flush=True)
        del raw, lookup, scores, result
    if any(sha(ROOT/name) != value for name,value in p['files'].items()):
        raise ValueError('Original evaluation evidence changed during diagnosis')
    receipt = dict(status='PASS',protocol_sha256=p['sha256'],candidates=results,
                   finished_at_utc=now(),source_scores_preserved=True,original_thresholds_changed=False,
                   hypothetical_cutoffs_final_fitted=True,model_forwards=0,API_calls=0,
                   quality_approved=False,default_changed=False,P2_admission=False,scope=p['scope'])
    save(OUT/'summary.json',receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(),indent=2,allow_nan=False))
