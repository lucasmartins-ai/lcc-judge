"""Fresh matched-objective triplets; transform/criteria frozen before inference."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/holdout-normalization'
KINDS=['pos','neg_decoy','neg_unrelated']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    from specialist.corpus import HOLDOUT_DOMAINS,make_item
    grid=[]
    for domain in HOLDOUT_DOMAINS:
        generated=[make_item(domain,'ood',i,seed=442383) for i in range(2000)]
        groups=defaultdict(dict)
        for row in generated:groups[row['objective']].setdefault(row['kind'],row)
        complete=sorted(k for k,v in groups.items() if set(v)==set(KINDS))
        random.Random('442383:'+domain.name).shuffle(complete)
        assert len(complete)>=16
        for index,objective in enumerate(complete[:16]):
            for kind in KINDS:
                row=dict(groups[objective][kind]);row['case_id']=f'{domain.name}-{index:02d}'
                grid.append(row)
    old=set()
    for path in list((ROOT/'data/exp02e').glob('*.jsonl'))+list((ROOT/'research/goal-engine-2026-10-04/head-objectives').glob('*.jsonl')):
        old.update(json.loads(s)['content_hash'] for s in path.read_text().splitlines())
    assert not old.intersection(r['content_hash'] for r in grid)
    study=ROOT/'research/goal-engine-2026-10-04/head-objectives'
    selection=json.loads((study/'selection.json').read_text());assert selection['selected_arm']=='bce'
    sources=['research/holdout_normalization.py','research/head_objective_study.py','specialist/corpus.py','specialist/model.py','specialist/checkpoint.py']
    protocol=dict(schema='fresh-holdout-normalization/0.1',seed=442383,
        selection='first complete kind per exact objective, then 16 shuffled objective groups per holdout domain; fixed seed',
        n_objectives=64,n_candidates=192,models=['parent','bce-101','bce-202','bce-303'],
        transform='z-score raw rank logits within all three same-objective candidates; no labels used by transform',
        bootstrap=dict(repeats=2000,seed=78105,unit='whole domain; retain all objective triplets; four domains'),
        criteria=dict(delta_J_min=.03,delta_J_ci_low_positive=True,max_D_loss=.01,quality_gate=.90),
        max_pair_hf=2048,device='mps',encoder_batch=8,
        scope='Fresh synthetic matched candidates in known holdout generator families; not independently authored semantics',
        selection_sha256=sha(study/'selection.json'),parent_sha256=sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
        selected_head_sha256={str(s):sha(study/f'bce-{s}/weights.pt') for s in [101,202,303]},
        sources={n:sha(ROOT/n) for n in sources},
        grid_sha256=hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest())
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    for name,value in [('protocol.json',protocol),('grid.json',grid)]:
        path=OUT/name;encoded=json.dumps(value,indent=2)+'\n'
        if path.exists():assert path.read_text()==encoded,'Frozen normalization changed'
        else:path.write_text(encoded)
    for name in sources:
        path=OUT/'executed-source'/name;path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes((ROOT/name).read_bytes())
        assert sha(path)==protocol['sources'][name]
    return protocol,grid


def auc(pos,neg):return float(np.mean(pos[:,None]>neg[None,:]))


def evaluate(values):return {'J':auc(values[:,0],values[:,1]),'D':auc(values[:,0],values[:,2])}


def zscore(values):
    scale=values.std(axis=1,keepdims=True)
    return (values-values.mean(axis=1,keepdims=True))/np.where(scale>0,scale,1)


def run():
    from specialist.model import SpecialistHead
    from specialist.checkpoint import load_trained_weights
    from research.head_objective_study import occupied_line_representations,FeatureHeads,score
    protocol,grid=freeze();torch.set_num_threads(8)
    raw_path=OUT/'scores.json'
    if raw_path.exists():
        saved=json.loads(raw_path.read_text());assert saved['protocol_sha256']==protocol['sha256'];models=saved['models']
    else:
        model=SpecialistHead(pooling='line-attn',unfreeze_last_n=2,local_files_only=True).to('mps').eval()
        load_trained_weights(model,torch.load(ROOT/'models/exp02e-unfreeze2/weights.pt',map_location='cpu',weights_only=True))
        model.requires_grad_(False);features=[];lengths=[];started=time.perf_counter()
        for offset in range(0,len(grid),8):
            batch=grid[offset:offset+8];objs=[r['objective'] for r in batch];texts=[r['text'] for r in batch]
            actual=[len(model.tokenizer(o,t,truncation=False)['input_ids']) for o,t in zip(objs,texts)]
            assert max(actual)<=2048;lengths.extend(actual)
            enc=model.encode(objs,texts,max_len=2048);ids=enc.pop('line_ids').to('mps')
            with torch.inference_mode():
                hidden=model.encoder(**{k:v.to('mps') for k,v in enc.items()}).last_hidden_state
                features.extend(r.cpu().clone() for r in occupied_line_representations(hidden,ids))
        cache={'head':model.head.cpu().state_dict(),'line_score':model.line_score.cpu().state_dict()}
        split={'items':grid,'features':features};models={}
        for name in protocol['models']:
            torch.manual_seed(101);head=FeatureHeads(cache)
            if name!='parent':head.load_state_dict(torch.load(ROOT/f'research/goal-engine-2026-10-04/head-objectives/{name}/weights.pt',weights_only=True))
            rows=score(head,split,'bce')
            for row,item in zip(rows,grid):row['case_id']=item['case_id']
            models[name]=rows
        raw_path.write_text(json.dumps(dict(protocol_sha256=protocol['sha256'],models=models,
            actual_hf_min=min(lengths),actual_hf_max=max(lengths),truncated=0,encoder_seconds=time.perf_counter()-started),indent=2)+'\n')
    ids=sorted({r['case_id'] for r in grid});domains=sorted({r['domain'] for r in grid})
    arrays={name:np.array([[next(r['score'] for r in rows if r['case_id']==c and r['kind']==k) for k in KINDS] for c in ids]) for name,rows in models.items()}
    groups=[np.array([i for i,c in enumerate(ids) if c.startswith(d+'-')]) for d in domains]
    result={}
    for name,values in [('parent',[arrays['parent']]),('selected_bce',[arrays[f'bce-{s}'] for s in [101,202,303]])]:
        transformed=[zscore(v) for v in values]
        before={f:float(np.mean([evaluate(v)[f] for v in values])) for f in ['J','D']}
        after={f:float(np.mean([evaluate(v)[f] for v in transformed])) for f in ['J','D']}
        rng=np.random.default_rng(78105);gains=[]
        for _ in range(2000):
            indices=np.concatenate([groups[i] for i in rng.integers(0,4,4)])
            gains.append(np.mean([evaluate(z[indices])['J']-evaluate(v[indices])['J'] for v,z in zip(values,transformed)]))
        ci=np.percentile(gains,[2.5,97.5]).tolist();delta={f:after[f]-before[f] for f in ['J','D']}
        paired={f:float(np.mean([np.mean(v[:,0]>v[:,i]) for v in values])) for f,i in [('J',1),('D',2)]}
        result[name]=dict(before=before,after=after,delta=delta,delta_J_95ci=ci,paired=paired,
            ranking_orders_unchanged_by_transform=True,
            normalization_criteria_pass=delta['J']>=.03 and ci[0]>0 and delta['D']>=-.01,
            both_quality_gates_pass=after['J']>=.90 and after['D']>=.90,
            calibrated_probabilities=False,validated_for_deployment=False)
    summary=dict(protocol_sha256=protocol['sha256'],scores_sha256=sha(raw_path),n_objectives=64,domains=domains,
                 summary=result,training_admission=False,temporal_preregistration_certified=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':run()
