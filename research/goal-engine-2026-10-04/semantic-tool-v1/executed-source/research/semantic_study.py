"""Finite, frozen semantic-tool P1 study; final follows validation selection."""
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
from research.semantic_corpus import build_split, verify_label

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04/semantic-tool-v1'


def metrics(rows, threshold=None):
    eligible = [r for r in rows if r['score'] is not None and math.isfinite(r['score'])
                and not r.get('truncated') and not r.get('error')]
    pos = [r['score'] for r in eligible if r['label']==1]
    neg = [r['score'] for r in eligible if r['label']==0]
    pairs = {}
    for r in eligible:
        pairs.setdefault(r['report_id'],{0:[],1:[]})[r['label']].append(r['score'])
    comparisons = [int(p>n) for pair in pairs.values() for p,n in zip(pair[1],pair[0])]
    result = dict(n=len(rows),eligible=len(eligible),cuts=sum(bool(r.get('truncated')) for r in rows),
                  errors=sum(bool(r.get('error')) for r in rows),auc=common.auc(pos,neg),
                  paired_auc=float(np.mean(comparisons)) if comparisons else None,
                  paired_reports=len(comparisons))
    if threshold is not None:
        result.update(positive_recall=float(np.mean([s>=threshold for s in pos])) if pos else None,
                      negative_rejection=float(np.mean([s<threshold for s in neg])) if neg else None)
    return result


def threshold_for(rows):
    positive = [r['score'] for r in rows if r['label']==1 and r['score'] is not None]
    if not positive:
        raise ValueError('Validation has no positive scores')
    return max(t for t in sorted(set(positive)) if np.mean([s>=t for s in positive])>=.95)


def prepare():
    sources = ['research/semantic_study.py','research/semantic_corpus.py','research/relevance_study.py',
               'research/head_objective_study.py','specialist/model.py','specialist/checkpoint.py','bakeoff/adapters.py']
    protocol = dict(schema='semantic-tool-p1/0.1',seeds=[101,202,303],epochs=3,
                    arms=['frozen','last-two'],groups_per_domain=dict(train=12,validation=4,final=8),
                    learning_rate=.0003,encoder_learning_rate=.00002,batch_size=8,frozen_batch_size=8,
                    device='mps',threads=8,max_pair_tokens=512,
                    initialization='same clean parent and matched fresh heads; parent line scorer retained',
                    supervision='authored concept-slot equality; low/high values and levels independent of label; no necessity labels',
                    selection='highest mean validation pooled AUC; tie order frozen then last-two; no final selection',
                    threshold='greatest validation-only raw-logit threshold with >=.95 positive recall',
                    quality_gate=dict(auc_min=.90,paired_auc_min=.90,positive_recall_min=.95,negative_rejection_min=.70),
                    final_scope='six withheld authored concept-pair families; shared primitive vocabulary, schemas and author, not external semantic confirmation',
                    final_used_for_selection=False,bootstrap=dict(unit='whole final family',draws=2000,seed=78112),
                    baselines=['lexical','parent','bge','laya'],baseline_device='cpu',
                    latency_comparison='not measured: candidate MPS/cache and controls CPU; timings are run cost, not intrinsic superiority',
                    encoder_dropout=False,parent_weights_sha256=common.sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
                    parent_config_sha256=common.sha(ROOT/'models/exp02e-unfreeze2/config.json'),
                    sources={n:common.sha(ROOT/n) for n in sources})
    OUT.mkdir(exist_ok=True)
    hashes,entities,data = {},{},{}
    for split,groups in protocol['groups_per_domain'].items():
        rows=build_split(split,groups)
        assert all(verify_label(r)==r['label'] for r in rows)
        hashes[split]={r['content_hash'] for r in rows};entities[split]={r['entity'] for r in rows}
        text=''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)
        path=OUT/f'{split}.jsonl'
        if path.exists():assert path.read_text()==text
        else:path.write_text(text)
        data[split]=dict(sha256=common.sha(path),n=len(rows),known=len(rows),
                         domains=sorted({r['domain'] for r in rows}))
    for a,b in [('train','validation'),('train','final'),('validation','final')]:
        assert not hashes[a]&hashes[b] and not entities[a]&entities[b]
    protocol['data']=data
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    common.write_once(OUT/'protocol.json',protocol)
    for name,expected in protocol['sources'].items():
        dest=OUT/'executed-source'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert common.sha(dest)==expected
        else:dest.write_bytes((ROOT/name).read_bytes())
    return protocol


def attach(scores, originals):
    lookup={r['id']:r for r in originals}
    for score in scores:
        score['report_id']=lookup[score['id']]['report_id']
    return scores


def train_one(protocol,cache,arm,seed):
    target=OUT/f'{arm}-{seed}'
    if (target/'validation.json').exists():return
    if target.exists():raise ValueError('Partial training run; inspect before any retry')
    target.mkdir()
    common.write_once(target/'started.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed))
    random.seed(seed);torch.manual_seed(seed)
    if arm=='frozen':
        model=common.RelevanceHead(cache['parent_state']);common.matched_reset_head(model,seed)
        optimizer=torch.optim.AdamW(model.parameters(),lr=protocol['learning_rate'],weight_decay=.01)
    else:
        model,_=common.load_parent(protocol['device'],True);common.matched_reset_head(model,seed)
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
            labels=torch.tensor([r['label'] for r in batch],dtype=torch.float32,device=logits.device)
            loss=nn.functional.binary_cross_entropy_with_logits(logits,labels)
            optimizer.zero_grad();loss.backward();optimizer.step()
            total+=float(loss.detach().cpu())*len(batch)
            if offset%320==0:print(arm,seed,epoch,offset,'/',len(order),flush=True)
        item=dict(epoch=epoch,loss=total/len(order),seconds=time.perf_counter()-began)
        history.append(item);common.write_once(target/f'epoch-{epoch}.json',item)
    state=copy.deepcopy(cache['parent_state'])
    validation=common.read_rows(OUT/'validation.jsonl')
    if arm=='frozen':
        state.update(model.state_dict());scores=common.feature_scores(model,cache['splits']['validation'])
    else:
        state.update({n:v.detach().cpu().clone() for n,v in model.state_dict().items() if n in state})
        scores=common.native_scores(model,validation,protocol)
    scores=attach(scores,validation);threshold=threshold_for(scores)
    torch.save(state,target/'weights.pt')
    common.write_once(target/'config.json',dict(model_id='answerdotai/ModernBERT-base',pooling='line-attn',unfreeze_last_n=2,
        max_len=512,temperature=1.,task='semantic-tool-measurement-relevance',seed=seed,
        backbone_revision='8949b909ec900327062f0ebf497f51aef5e6f0c8'))
    common.write_once(target/'training_meta.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed,
        epochs_completed=len(history),history=history,encoder_adapted=arm=='last-two',weights_sha256=common.sha(target/'weights.pt')))
    common.write_once(target/'validation.json',dict(rows=scores,threshold=threshold,metrics=metrics(scores,threshold)))
    print('validation',arm,seed,metrics(scores,threshold),flush=True)


def final(protocol):
    selection=json.loads((OUT/'selection.json').read_text())
    cache=common.create_cache(OUT,protocol,['final']);originals=cache['splits']['final']['rows']
    for arm in protocol['arms']:
        for seed in protocol['seeds']:
            target=OUT/f'{arm}-{seed}'
            if (target/'final.json').exists():continue
            state=torch.load(target/'weights.pt',weights_only=True,map_location='cpu')
            threshold=json.loads((target/'validation.json').read_text())['threshold']
            if arm=='frozen':
                model=common.RelevanceHead(state);model.load_state_dict({n:v for n,v in state.items() if not n.startswith('encoder.')})
                scores=common.feature_scores(model,cache['splits']['final'])
            else:
                from specialist.checkpoint import load_trained_weights
                model,_=common.load_parent(protocol['device'],False);load_trained_weights(model,state)
                scores=common.native_scores(model,originals,protocol)
            scores=attach(scores,originals)
            common.write_once(target/'final.json',dict(rows=scores,threshold=threshold,metrics=metrics(scores,threshold),
                selected_before_final=selection['selected_arm']==arm))
            print('final',arm,seed,metrics(scores,threshold),flush=True)


def baselines(protocol):
    assert (OUT/'selection.json').exists(),'Select on validation before final controls'
    from bakeoff.adapters import LexicalAdapter,OfficialEmbeddingAdapter,PinnedLayaAdapter
    originals=common.read_rows(OUT/'final.jsonl')
    for name in protocol['baselines']:
        path=OUT/'baselines'/f'{name}.json'
        if path.exists():continue
        path.parent.mkdir(exist_ok=True);partial=path.with_suffix('.jsonl')
        if partial.exists():raise ValueError('Partial baseline; inspect before retry')
        if name=='parent':
            cache=common.create_cache(OUT,protocol,['final']);model=common.RelevanceHead(cache['parent_state'])
            model.load_state_dict({n:v for n,v in cache['parent_state'].items() if not n.startswith('encoder.')})
            scores=attach(common.feature_scores(model,cache['splits']['final']),originals)
        else:
            adapter=(LexicalAdapter() if name=='lexical' else OfficialEmbeddingAdapter.bge() if name=='bge' else
                     PinnedLayaAdapter('laya-pinned',str(Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya-multilingual/snapshots/052592a15d198d9ad47da779604259b10b47b7aa')))
            adapter.load();scores=[]
            with partial.open('x') as stream:
                for i,row in enumerate(originals):
                    value=adapter.score(row['objective'],row['text'])
                    score=common.record(row,value.value,truncated=value.truncated,error=value.error,actual_tokens=value.actual_tokens,latency_ms=value.latency_ms)
                    score['report_id']=row['report_id'];scores.append(score);stream.write(json.dumps(score)+'\n');stream.flush()
                    if i%96==0:print('baseline',name,i,'/',len(originals),flush=True)
            adapter.close()
        common.write_once(path,dict(protocol_sha256=protocol['sha256'],rows=scores,metrics=metrics(scores)))
        print(name,metrics(scores),flush=True)


def summarize(protocol):
    selection=json.loads((OUT/'selection.json').read_text())
    result=dict(protocol_sha256=protocol['sha256'],selected_arm=selection['selected_arm'],arms={},baselines={},adoption=False)
    for arm in protocol['arms']:
        receipts=[json.loads((OUT/f'{arm}-{seed}/final.json').read_text()) for seed in protocol['seeds']]
        keys=['auc','paired_auc','positive_recall','negative_rejection']
        means={k:float(np.mean([r['metrics'][k] for r in receipts])) for k in keys}
        gates=[r['metrics']['eligible']==r['metrics']['n'] and r['metrics']['errors']==r['metrics']['cuts']==0 and
               all(r['metrics'][k]>=protocol['quality_gate'][k+'_min'] for k in keys) for r in receipts]
        domains=sorted({r['domain'] for r in receipts[0]['rows']});rng=np.random.default_rng(protocol['bootstrap']['seed']);draws=[]
        for _ in range(protocol['bootstrap']['draws']):
            chosen=rng.choice(domains,len(domains),replace=True)
            draws.append(float(np.mean([metrics([r for d in chosen for r in receipt['rows'] if r['domain']==d])['auc'] for receipt in receipts])))
        result['arms'][arm]=dict(mean=means,seeds_pass=gates,all_seed_gate_pass=all(gates),
                                pooled_auc_family_bootstrap_95=np.percentile(draws,[2.5,97.5]).tolist())
    for name in protocol['baselines']:
        result['baselines'][name]=json.loads((OUT/'baselines'/f'{name}.json').read_text())['metrics']
    result['scope']='six authored held-out pair families; no external/human/P2 or deployment reliability claim'
    common.write_once(OUT/'summary.json',result);print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['prepare','cache','train','final','baselines','summarize'])
    args=parser.parse_args();protocol=prepare();torch.set_num_threads(protocol['threads'])
    if args.phase=='prepare':common.coverage(OUT,protocol);print(json.dumps(protocol['data'],indent=2));return
    if args.phase=='final':final(protocol);return
    if args.phase=='baselines':baselines(protocol);return
    if args.phase=='summarize':summarize(protocol);return
    cache=common.create_cache(OUT,protocol,['train','validation'])
    if args.phase=='cache':return
    for arm in protocol['arms']:
        for seed in protocol['seeds']:train_one(protocol,cache,arm,seed)
    means={a:float(np.mean([json.loads((OUT/f'{a}-{s}/validation.json').read_text())['metrics']['auc'] for s in protocol['seeds']])) for a in protocol['arms']}
    selected=max(protocol['arms'],key=lambda a:means[a])
    common.write_once(OUT/'selection.json',dict(protocol_sha256=protocol['sha256'],selected_arm=selected,
                                             validation_mean_auc=means,final_used_for_selection=False))


if __name__=='__main__':main()
