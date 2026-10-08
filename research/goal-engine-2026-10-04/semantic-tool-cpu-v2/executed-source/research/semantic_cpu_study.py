"""Separate finite-guarded CPU protocol; never replaces the failed MPS study."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn

from research import relevance_study as common
from research import semantic_study as analysis
from specialist.numerical import NonFiniteTrainingError, finite_update

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'research/goal-engine-2026-10-04/semantic-tool-v1'
OUT=ROOT/'research/goal-engine-2026-10-04/semantic-tool-cpu-v2'


def prepare():
    old=json.loads((OLD/'protocol.json').read_text())
    assert not (OLD/'selection.json').exists() and not list(OLD.glob('*/final.json'))
    protocol=copy.deepcopy(old);protocol.pop('sha256')
    protocol.update(schema='semantic-tool-p1-cpu/0.2',device='cpu',
                    numerical_policy='finite scalar loss, all gradients before update, parameters/optimizer after update; abort run on first invalid value',
                    prior_failed_protocol_sha256=old['sha256'],
                    change_scope='new CPU cached/native trajectories and finite guards; not an isolated explanation of MPS NaN',
                    latency_comparison='not measured: all candidates CPU/cache; remote/control operational costs differ')
    names=['research/semantic_cpu_study.py','research/semantic_study.py','research/semantic_corpus.py',
           'research/relevance_study.py','research/head_objective_study.py','specialist/numerical.py',
           'specialist/model.py','specialist/checkpoint.py','bakeoff/adapters.py']
    protocol['sources']={n:common.sha(ROOT/n) for n in names}
    OUT.mkdir(exist_ok=True)
    for split,meta in protocol['data'].items():
        source=OLD/f'{split}.jsonl';assert common.sha(source)==meta['sha256']
        target=OUT/source.name
        if target.exists():assert target.read_bytes()==source.read_bytes()
        else:target.write_bytes(source.read_bytes())
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    common.write_once(OUT/'protocol.json',protocol)
    for name,expected in protocol['sources'].items():
        target=OUT/'executed-source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert common.sha(target)==expected
        else:target.write_bytes((ROOT/name).read_bytes())
    return protocol


def train_one(protocol,cache,arm,seed):
    target=OUT/f'{arm}-{seed}'
    if (target/'validation.json').exists():return
    if target.exists():raise ValueError('Partial/failing run exists; no silent retry')
    target.mkdir();common.write_once(target/'started.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed))
    random.seed(seed);torch.manual_seed(seed)
    if arm=='frozen':
        model=common.RelevanceHead(cache['parent_state']);common.matched_reset_head(model,seed)
        optimizer=torch.optim.AdamW(model.parameters(),lr=protocol['learning_rate'],weight_decay=.01)
    else:
        model,_=common.load_parent('cpu',True);common.matched_reset_head(model,seed)
        optimizer=torch.optim.AdamW([
            dict(params=[p for n,p in model.named_parameters() if n.startswith('encoder.') and p.requires_grad],lr=protocol['encoder_learning_rate']),
            dict(params=[p for n,p in model.named_parameters() if not n.startswith('encoder.')],lr=protocol['learning_rate'])],weight_decay=.01)
    training=cache['splits']['train'];order=list(range(len(training['rows'])));history=[]
    for epoch in range(1,protocol['epochs']+1):
        model.train()
        if arm!='frozen':model.encoder.eval()
        random.shuffle(order);total=0.;began=time.perf_counter()
        for offset in range(0,len(order),protocol['batch_size']):
            indices=order[offset:offset+protocol['batch_size']];batch=[training['rows'][i] for i in indices]
            if arm=='frozen':logits=model([training['features'][i] for i in indices])
            else:
                encoded,_=common.encode_uncut(model,batch,protocol);logits=model(encoded)
            labels=torch.tensor([r['label'] for r in batch],dtype=torch.float32)
            loss=nn.functional.binary_cross_entropy_with_logits(logits,labels)
            try:finite_update(loss,model,optimizer)
            except NonFiniteTrainingError as exc:
                common.write_once(target/'failure.json',dict(protocol_sha256=protocol['sha256'],stage=exc.stage,
                    parameters=list(exc.names),epoch=epoch,batch_offset=offset,completed_epochs=len(history),admission=False))
                raise
            total+=float(loss.detach())*len(batch)
            if offset%320==0:print(arm,seed,epoch,offset,'/',len(order),flush=True)
        item=dict(epoch=epoch,loss=total/len(order),seconds=time.perf_counter()-began)
        history.append(item);common.write_once(target/f'epoch-{epoch}.json',item)
    state=copy.deepcopy(cache['parent_state']);validation=common.read_rows(OUT/'validation.jsonl')
    if arm=='frozen':
        state.update(model.state_dict());scores=common.feature_scores(model,cache['splits']['validation'])
    else:
        state.update({n:v.detach().cpu().clone() for n,v in model.state_dict().items() if n in state})
        scores=common.native_scores(model,validation,protocol)
    scores=analysis.attach(scores,validation)
    invalid=[r for r in scores if r['score'] is None or not math.isfinite(r['score'])]
    if invalid:
        common.write_once(target/'failure.json',dict(stage='validation_scores',invalid_ids=[r['id'] for r in invalid],admission=False))
        raise NonFiniteTrainingError('validation_scores')
    threshold=analysis.threshold_for(scores);torch.save(state,target/'weights.pt')
    common.write_once(target/'config.json',dict(model_id='answerdotai/ModernBERT-base',pooling='line-attn',unfreeze_last_n=2,
        max_len=512,temperature=1.,task='semantic-tool-measurement-relevance',seed=seed,
        backbone_revision='8949b909ec900327062f0ebf497f51aef5e6f0c8'))
    common.write_once(target/'training_meta.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed,
        epochs_completed=len(history),history=history,encoder_adapted=arm=='last-two',weights_sha256=common.sha(target/'weights.pt'),
        numerical_guards_applied=True,device='cpu'))
    common.write_once(target/'validation.json',dict(rows=scores,threshold=threshold,metrics=analysis.metrics(scores,threshold)))
    print('validation',arm,seed,analysis.metrics(scores,threshold),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['prepare','cache','train','final','baselines','summarize'])
    args=parser.parse_args();protocol=prepare();torch.set_num_threads(protocol['threads'])
    # Reuse the fingerprinted score/analysis functions with an explicit run root.
    # The failed protocol's prepare/train entrypoints are never invoked.
    analysis.OUT=OUT
    if args.phase=='prepare':common.coverage(OUT,protocol);print(json.dumps(protocol['data'],indent=2));return
    if args.phase=='final':analysis.final(protocol);return
    if args.phase=='baselines':analysis.baselines(protocol);return
    if args.phase=='summarize':analysis.summarize(protocol);return
    cache=common.create_cache(OUT,protocol,['train','validation'])
    if args.phase=='cache':return
    for arm in protocol['arms']:
        for seed in protocol['seeds']:train_one(protocol,cache,arm,seed)
    means={a:float(np.mean([json.loads((OUT/f'{a}-{s}/validation.json').read_text())['metrics']['auc'] for s in protocol['seeds']])) for a in protocol['arms']}
    selected=max(protocol['arms'],key=lambda a:means[a])
    common.write_once(OUT/'selection.json',dict(protocol_sha256=protocol['sha256'],selected_arm=selected,
        validation_mean_auc=means,final_used_for_selection=False))


if __name__=='__main__':main()
