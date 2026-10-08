"""Development objectives separating conditional relevance from scope support.

IRRELEVANT/RELEVANT logits retain the existing scalar-margin initialization.
UNKNOWN has an independent binary support logit, without a three-class softmax
denominator. Unsupported goals have no relevance target. An optional quartet
loss tests both report ordering within a goal and goal ordering within a report.
These are objectives, not calibrated probabilities or evidence of LCC utility.
"""

from collections import defaultdict
import math

import torch
from torch.nn import functional as F


def factorized_loss(items, logits, binary_fraction, unknown_fraction):
    if (logits.ndim != 2 or logits.shape != (len(items), 3) or not items
            or any(type(i['class_id']) is not int or i['class_id'] not in (0, 1, 2) for i in items)
            or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1
                   for v in (binary_fraction,unknown_fraction))
            or not math.isclose(binary_fraction+unknown_fraction,1.,rel_tol=0.,abs_tol=1e-12)):
        raise ValueError('Complete three-axis inputs and fixed global binary/UNKNOWN fractions required')
    labels=torch.tensor([i['class_id'] for i in items],device=logits.device)
    supported=labels!=2
    relevance=F.binary_cross_entropy_with_logits(logits[:,1]-logits[:,0],
        (labels==1).to(logits.dtype),reduction='none')
    relevance=(relevance*supported.to(logits.dtype)/binary_fraction).mean()
    scope=F.binary_cross_entropy_with_logits(logits[:,2],(~supported).to(logits.dtype),reduction='none')
    support_weights=torch.where(supported,logits.new_tensor(1/(2*binary_fraction)),
                                logits.new_tensor(1/(2*unknown_fraction)))
    return relevance+(scope*support_weights).mean()


def conditional_loss(logits):
    if logits.ndim!=3 or logits.shape[1:]!=(4,3) or logits.shape[0]==0:
        raise ValueError('Nonempty ordered 2x2 direct-record quartets required')
    score=logits[:,:,1]-logits[:,:,0]
    # Slots AA/AB/BA/BB: within goals, then within reports. Strict diagonal wins.
    differences=torch.stack([score[:,0]-score[:,1],score[:,3]-score[:,2],
                             score[:,0]-score[:,2],score[:,3]-score[:,1]],dim=1)
    return F.softplus(-differences).mean()


def training_quartets(rows,views):
    if (len(rows)!=len(views) or not rows
            or any(r['split']!='train' or r['id']!=v['id'] for r,v in zip(rows,views))):
        raise ValueError('Only complete aligned training receipts allowed')
    groups=defaultdict(list)
    content={}
    for row,saved in zip(rows,views):
        if row['label'] is None:continue
        view=saved['view']
        if (type(row['label']) is not int or row['label'] not in (0,1)
                or view['status']!='PROJECTED'
                or row['projected_input_hash']!=view['projected_input_sha256']
                or row['label']!=int(row['requested_role']==row['observed_role'])):
            raise ValueError('Valid direct-record binary view required')
        key=row['projected_input_hash'];entry=(view['objective'],view['text'],row['label'])
        if key in content and content[key]!=entry:raise ValueError('Conflicting deduplicated training input')
        content[key]=entry
        groups[(row['group'],row['report_variant'])].append(row)
    unique=set()
    for group in groups.values():
        roles=sorted({r['requested_role'] for r in group})
        if len(group)!=4 or len(roles)!=2 or {r['observed_role'] for r in group}!=set(roles):
            raise ValueError('Every supervised fixture/variant needs a complete 2x2 matrix')
        slots={(r['requested_role'],r['observed_role']):r['projected_input_hash'] for r in group}
        if len(slots)!=4:raise ValueError('Duplicate/missing quartet slot')
        unique.add(tuple(slots[(requested,observed)] for requested in roles for observed in roles))
    if not unique:raise ValueError('No complete supervised quartets')
    return [list(unit) for unit in sorted(unique)]
