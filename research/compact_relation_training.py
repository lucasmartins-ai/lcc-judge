"""Finite, query-grouped training helpers for a compact measurement ranker."""
from __future__ import annotations

from collections import defaultdict

import torch
from torch.nn import functional as F


def grouped_batches(rows, rng, groups_per_batch=2):
    if type(groups_per_batch) is not int or groups_per_batch < 1:
        raise ValueError('Positive batch group count required')
    groups = defaultdict(list)
    for row in rows:
        groups[row['group']].append(row)
    names = sorted(groups)
    rng.shuffle(names)
    return [[row for name in names[i:i+groups_per_batch] for row in sorted(groups[name],key=lambda r:r['id'])]
            for i in range(0,len(names),groups_per_batch)]


def relation_loss(rows, logits, arm):
    if arm not in ['bce','joint','rank-only'] or logits.shape != (len(rows),):
        raise ValueError('Known objective and matching single logits required')
    if any(type(r['label']) is not int or r['label'] not in [0,1] for r in rows):
        raise ValueError('Binary supervision required')
    labels = logits.new_tensor([r['label'] for r in rows])
    bce = F.binary_cross_entropy_with_logits(logits,labels)
    if arm == 'bce':
        return bce
    queries = defaultdict(lambda:{0:[],1:[]})
    for i,row in enumerate(rows):
        queries[row['objective']][row['label']].append(i)
    terms = []
    for indices in queries.values():
        if not indices[0] or not indices[1]:
            raise ValueError('Whole question alternatives required for ranking loss')
        positive, negative = logits[indices[1]],logits[indices[0]]
        terms.append(F.softplus(negative[None,:]-positive[:,None]).mean())
    ranking = torch.stack(terms).mean()
    return ranking if arm == 'rank-only' else (bce+ranking)*.5
