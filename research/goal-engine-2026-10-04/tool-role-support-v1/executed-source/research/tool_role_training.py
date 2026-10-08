"""Preparation/objective for a future bounded P1+UNKNOWN compact experiment.

No candidate is trained here. Only projected question/report strings enter the
model; annotations provide supervision. Syntax UNKNOWN is retained by the guard.
"""
from __future__ import annotations

from collections import Counter

import torch
from torch.nn import functional as F


def training_items(rows, views):
    if len(rows) != len(views):
        raise ValueError('Complete matching row/view receipts required')
    unique = {}
    for row, saved in zip(rows, views):
        if row['split'] != 'train' or row['id'] != saved['id']:
            raise ValueError('Only training rows and matching view ids allowed')
        label = row['label']
        if label is not None and (type(label) is not int or label not in [0, 1]):
            raise ValueError('Binary P1 or UNKNOWN supervision required')
        view = saved['view']
        if view['status'] != 'PROJECTED':
            if label is not None:
                raise ValueError('A supervised binary row lost its complete view')
            continue
        key = view['projected_input_sha256']
        class_id = 2 if label is None else label
        item = dict(input_hash=key, objective=view['objective'], text=view['text'],
                    class_id=class_id, receipt_ids=[row['id']])
        if key in unique:
            previous = unique[key]
            if any(previous[name] != item[name] for name in ['objective', 'text', 'class_id']):
                raise ValueError('Duplicate effective inputs have conflicting content/labels')
            previous['receipt_ids'].append(row['id'])
        else:
            unique[key] = item
    return [unique[key] for key in sorted(unique)]


def class_weights(items):
    counts = Counter(item['class_id'] for item in items)
    if set(counts) != {0, 1, 2} or any(type(item['class_id']) is not int for item in items):
        raise ValueError('All three decision classes must occur in the unique training set')
    return [len(items) / (3 * counts[label]) for label in range(3)]


def classification_loss(items, logits, weights):
    if logits.shape != (len(items), 3) or len(weights) != 3:
        raise ValueError('Matching three-class logits and fixed training weights required')
    labels = torch.tensor([item['class_id'] for item in items], dtype=torch.long, device=logits.device)
    if bool((labels < 0).any()) or bool((labels > 2).any()):
        raise ValueError('Only irrelevant/relevant/UNKNOWN classes accepted')
    weight = logits.new_tensor(weights)
    if not bool(torch.isfinite(weight).all()) or not bool((weight > 0).all()):
        raise ValueError('Positive finite class weights required')
    losses = F.cross_entropy(logits, labels, reduction='none')
    # Global fixed normalization, avoiding a batch-dependent weighted denominator.
    return (losses * weight[labels]).mean()


def score_axes(logits):
    if logits.ndim != 2 or logits.shape[1] != 3:
        raise ValueError('Expected irrelevant/relevant/UNKNOWN logits')
    relevance = logits[:, 1] - logits[:, 0]
    unknown = logits[:, 2] - torch.logsumexp(logits[:, :2], dim=1)
    return relevance, unknown
