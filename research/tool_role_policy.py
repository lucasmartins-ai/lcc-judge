"""Declared support/relevance policy and strict P1 metrics, without model inputs."""
from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
import math


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def is_semantic_unknown(row):
    kind = row['unknown_kind']
    return row['label'] is None and isinstance(kind, str) and bool(kind.strip()) and kind != 'unbound_record'


def decision(score, thresholds, shadow=False):
    if shadow or score['status'] != 'SCORED' or not _finite(score.get('score')) or not _finite(score.get('support_score')):
        return 'UNKNOWN'
    if score['support_score'] >= thresholds['support']:
        return 'UNKNOWN'
    return 'KEEP' if score['score'] >= thresholds['relevance'] else 'DROP'


def calibrate(rows, scores):
    if len(rows) != len(scores) or any(r['id'] != s['id'] for r, s in zip(rows, scores)):
        raise ValueError('Complete aligned validation scores required')
    binary = [(r, s) for r, s in zip(rows, scores) if r['label'] is not None]
    semantic = [s for r, s in zip(rows, scores) if is_semantic_unknown(r)]
    if (not binary or not semantic or any(s['status'] != 'SCORED' or not _finite(s['score'])
            or not _finite(s.get('support_score')) for r, s in binary)
            or any(s['status'] != 'SCORED' or not _finite(s.get('support_score')) for s in semantic)):
        raise ValueError('Finite binary and semantic UNKNOWN validation required')
    support = min(s['support_score'] for s in semantic)
    values = {s['score'] for r, s in binary}
    values.add(math.nextafter(min(values), -math.inf))
    values.add(math.nextafter(max(values), math.inf))
    languages = sorted({r['goal_language'] for r, s in binary})
    constraints = []
    for language in languages:
        positive = [s for r, s in binary if r['goal_language'] == language and r['label'] == 1]
        contradiction = [s for r, s in binary if r['goal_language'] == language and r['label'] == 1 and r['fact_truth'] is False]
        if not positive or not contradiction:
            raise ValueError('Each validation language needs positives and relevant contradictions')
        constraints.extend([positive, contradiction])
    def acceptable(cutoff):
        thresholds = dict(support=support, relevance=cutoff)
        return all(sum(decision(s, thresholds) != 'DROP' for s in group) / len(group) >= .95 for group in constraints)
    relevance = max(value for value in values if acceptable(value))
    return dict(support=support, relevance=relevance, validation_semantic_unknown_recall=1.0,
                recipe='minimum semantic-UNKNOWN support margin; greatest global relevance cutoff meeting .95 positive/contradiction keep recall in each language')


def metrics(rows, scores, thresholds, shadow=False):
    if len(rows) != len(scores) or any(r['id'] != s['id'] for r, s in zip(rows, scores)):
        raise ValueError('Aligned complete cohort required')
    pairs = list(zip(rows, scores))
    binary = [(r, s) for r, s in pairs if r['label'] is not None]
    positive = [(r, s) for r, s in binary if r['label'] == 1]
    negative = [(r, s) for r, s in binary if r['label'] == 0]
    if not positive or not negative or any(s['status'] != 'SCORED' or not _finite(s['score']) for r, s in binary):
        raise ValueError('Every binary row must have a finite score')
    sorted_negative = sorted(s['score'] for r, s in negative)
    wins = sum(bisect_left(sorted_negative, s['score']) for r, s in positive)
    queries = defaultdict(lambda: [[], []])
    reports = defaultdict(lambda: [[], []])
    for row, score in binary:
        queries[row['objective']][row['label']].append(score['score'])
        reports[row['report_id']][row['label']].append(score['score'])
    def contrast(groups):
        wins = comparisons = 0
        for negatives, positives in groups.values():
            wins += sum(p > n for p in positives for n in negatives)
            comparisons += len(positives) * len(negatives)
        return dict(wins=wins, comparisons=comparisons, auc=wins / comparisons if comparisons else None)
    within = contrast(queries)
    goal_axis = contrast(reports)
    semantic = [(r, s) for r, s in pairs if is_semantic_unknown(r)]
    structural = [(r, s) for r, s in pairs if r['unknown_kind'] == 'unbound_record']
    contradictions = [(r, s) for r, s in positive if r['fact_truth'] is False]
    def rate(group, wanted):
        return sum(wanted(decision(s, thresholds, shadow)) for r, s in group) / len(group) if group else None
    return dict(n=len(rows), binary=len(binary), positive=len(positive), negative=len(negative),
                pooled_wins=wins, pooled_comparisons=len(positive) * len(negative), pooled_auc=wins / (len(positive) * len(negative)),
                within_goal=within, within_goal_auc=within['auc'], same_report_goal=goal_axis,
                positive_keep_recall=rate(positive, lambda d: d != 'DROP'),
                contradiction_keep_recall=rate(contradictions, lambda d: d != 'DROP'),
                negative_drop_rejection=rate(negative, lambda d: d == 'DROP'),
                binary_unknown_rate=rate(binary, lambda d: d == 'UNKNOWN'),
                semantic_unknown=len(semantic), structural_unknown=len(structural),
                semantic_unknown_recognition=rate(semantic, lambda d: d == 'UNKNOWN'),
                structural_unknown_recognition=rate(structural, lambda d: d == 'UNKNOWN'),
                unknown_drops=sum(decision(s, thresholds, shadow) == 'DROP' for r, s in semantic + structural),
                control_shadow=shadow)


def passes(result):
    return (result['pooled_auc'] >= .90 and result['within_goal_auc'] is not None and result['within_goal_auc'] >= .90
            and result['positive_keep_recall'] is not None and result['positive_keep_recall'] >= .95
            and result['contradiction_keep_recall'] is not None and result['contradiction_keep_recall'] >= .95
            and result['negative_drop_rejection'] is not None and result['negative_drop_rejection'] >= .70
            and result['semantic_unknown_recognition'] is not None and result['semantic_unknown_recognition'] >= .95
            and result['structural_unknown_recognition'] == 1.0 and result['unknown_drops'] == 0)
