"""Additive reader and fixed-global objectives for varied-state development.

Original gzip receipts remain unchanged. Both relevance classes are balanced
after deduplication; semantic UNKNOWN has zero relevance target/gradient.
"""

import copy
import math

import torch
from torch.nn import functional as F

from research.audit_tool_relation_state_supervision import digest
from research.measurement_projection import project_measurement
from research.tool_role_policy import is_semantic_unknown


def adapt_records(rows, saved_views):
    if not rows or len(rows) != len(saved_views):
        raise ValueError('Complete aligned development receipts required')
    adapted_rows = []; adapted_views = []
    for row, saved in zip(rows, saved_views):
        if row['split'] not in ('train','validation') or row['id'] != saved['id']:
            raise ValueError('Only aligned development rows allowed')
        view = project_measurement(row['objective'], row['text'])
        if (saved['view'] != {k: view[k] for k in ('status','objective','text')}
                or row['content_hash'] != view['original_input_sha256']
                or row['projection_status'] != view['status']
                or row['projected_input_hash'] != view.get('projected_input_sha256')
                or saved['truncated'] is not False or saved['submitted_to_model'] is not False):
            raise ValueError('Changed saved strings, identities or complete projection')
        record = dict(row)
        record['report_id'] = (digest([row['group'],row['observed_role'],row['report_variant']])
                               if row['label'] is not None else row['id'])
        emitted = copy.deepcopy(saved)
        emitted['view'] = view
        adapted_rows.append(record); adapted_views.append(emitted)
    return adapted_rows, adapted_views


def balanced_loss(items, logits, counts):
    if (not isinstance(counts,(list,tuple)) or len(counts) != 3
            or any(type(c) is not int or c <= 0 for c in counts)
            or not items or logits.shape != (len(items),3)
            or any(type(i['class_id']) is not int or i['class_id'] not in (0,1,2) for i in items)):
        raise ValueError('Complete logits/classes and positive integer global deduplicated counts required')
    n = sum(counts); binary = counts[0] + counts[1]
    labels = torch.tensor([i['class_id'] for i in items], device=logits.device)
    supported = labels != 2
    relevance = F.binary_cross_entropy_with_logits(logits[:,1]-logits[:,0], (labels==1).to(logits.dtype), reduction='none')
    weights = logits.new_tensor([n/(2*counts[0]), n/(2*counts[1]), 0.])
    scope = F.binary_cross_entropy_with_logits(logits[:,2], (~supported).to(logits.dtype), reduction='none')
    scope_weights = torch.where(supported, logits.new_tensor(n/(2*binary)), logits.new_tensor(n/(2*counts[2])))
    return (relevance*weights[labels]).mean() + (scope*scope_weights).mean()


def calibrate_bilingual(rows, scores):
    """Exact order-statistic cutoff; avoids a quadratic scan of 30K validation rows."""
    if len(rows) != len(scores) or any(r['id'] != s['id'] for r,s in zip(rows,scores)):
        raise ValueError('Complete aligned validation required')
    binary = [(r,s) for r,s in zip(rows,scores) if r['label'] is not None]
    semantic = [s for r,s in zip(rows,scores) if is_semantic_unknown(r)]
    def finite(s):
        return (s['status']=='SCORED' and all(type(s.get(k)) in (int,float) and math.isfinite(s[k]) for k in ('score','support_score')))
    if not binary or not semantic or not all(finite(s) for r,s in binary) or not all(finite(s) for s in semantic):
        raise ValueError('Finite complete binary and semantic UNKNOWN scores required')
    support = min(s['support_score'] for s in semantic)
    cutoff = math.nextafter(max(s['score'] for r,s in binary), math.inf)
    for column in ('goal_language','report_language'):
        if {r[column] for r,s in binary} != {'en','pt'}:
            raise ValueError('Both query/report languages required')
        for language in ('en','pt'):
            for contradiction_only in (False,True):
                group = [(r,s) for r,s in binary if r['label']==1 and r[column]==language
                         and (not contradiction_only or r['fact_truth'] is False)]
                if not group:
                    raise ValueError('Every language needs positives and relevant contradictions')
                eligible = sorted(s['score'] for r,s in group if s['support_score'] < support)
                # Equality keeps a row, and UNKNOWN is retained. At most floor(n/20)
                # may DROP to preserve >=95% under each predeclared constraint.
                allowance = len(group)//20
                if len(eligible)>allowance:
                    cutoff = min(cutoff, eligible[allowance])
    return dict(support=support,relevance=cutoff,validation_semantic_unknown_recall=1.0,
        recipe='minimum semantic-UNKNOWN independent logit; greatest global relevance cutoff preserving .95 positive/contradiction retention in each EN/PT query and report language, strict DROP below cutoff')
