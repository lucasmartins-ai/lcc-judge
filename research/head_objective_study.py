"""Bounded frozen-encoder objective study; source/splits freeze before inference.

Cache encoder line representations once, then train small heads with three matched
seeds. New synthetic text seeds are withheld from the training loader; generator
families and authored templates remain known. No P2/counterfactual labels are used.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/head-objectives'
KINDS=['pos','neg_decoy','neg_unrelated']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    from specialist.corpus import build_split
    sources=['research/head_objective_study.py','specialist/model.py','specialist/checkpoint.py','specialist/corpus.py']
    protocol=dict(schema='frozen-head-objectives/0.1',seeds=[101,202,303],epochs=3,learning_rate=.0003,
        batch_size=32,encoder_batch_size=8,max_pair_tokens=2048,device='mps',threads=8,
        arms=['bce','pairwise','joint'],encoder_frozen=True,
        validation_seed=442378,final_eval_seed=442379,new_items_per_domain=120,
        selection='highest validation mean(J,D), averaged over three seeds; no OOD or probe selection',
        criteria=dict(normalization_delta_J_min=.03,normalization_CI_low_positive=True,normalization_max_D_loss=.01,
                      candidate_D_min=.70,candidate_D_gain_CI_low_positive=True,candidate_max_J_loss=.02),
        metric='strict pooled P(pos > noise); bootstrap whole domain/objective groups',
        calibration='none; logits/rank scores are not necessity probabilities',
        evaluation_scope='fresh synthetic texts in known generator families; diagnostic, not external confirmation',
        parent_weights_sha256=sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
        parent_config_sha256=sha(ROOT/'models/exp02e-unfreeze2/config.json'),
        train_sha256=sha(ROOT/'data/exp02e/train.jsonl'),
        sources={name:sha(ROOT/name) for name in sources})
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==protocol,'Protocol changed; use a new study'
    else:path.write_text(json.dumps(protocol,indent=2)+'\n')
    for name,expected in protocol['sources'].items():
        dest=OUT/'executed-source'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==expected
        else:dest.write_bytes((ROOT/name).read_bytes())
    old_hashes=set()
    for split in ['train','val','ood']:
        old_hashes.update(json.loads(s)['content_hash'] for s in (ROOT/f'data/exp02e/{split}.jsonl').read_text().splitlines())
    for split,kind,seed in [('validation','val',protocol['validation_seed']),('final','ood',protocol['final_eval_seed'])]:
        path=OUT/f'{split}.jsonl'
        items=build_split(kind,protocol['new_items_per_domain'],seed=seed)
        assert not (old_hashes & {r['content_hash'] for r in items}),'New eval overlaps old data'
        encoded=''.join(json.dumps(r)+'\n' for r in items)
        if path.exists():assert path.read_text()==encoded
        else:path.write_text(encoded)
    return protocol


def occupied_line_representations(hidden,line_ids):
    """Exact masked means; drop unoccupied IDs rather than inventing empty lines."""
    result=[]
    for h,ids in zip(hidden,line_ids):
        valid=ids>=0
        values=ids[valid]
        if not len(values):result.append(h.new_zeros((0,h.shape[-1])));continue
        unique,inverse=torch.unique(values,sorted=True,return_inverse=True)
        sums=h.new_zeros((len(unique),h.shape[-1]))
        sums.scatter_add_(0,inverse[:,None].expand(-1,h.shape[-1]),h[valid])
        counts=torch.bincount(inverse,minlength=len(unique)).to(h.dtype)
        result.append(sums/counts[:,None])
    return result


def build_cache(protocol):
    from specialist.model import SpecialistHead
    from specialist.checkpoint import load_trained_weights
    cache_path=OUT/'line-features.pt';meta_path=OUT/'cache-manifest.json'
    if cache_path.exists():
        meta=json.loads(meta_path.read_text())
        assert meta['protocol_sha256']==protocol['sha256'] and meta['sha256']==sha(cache_path)
        return torch.load(cache_path,map_location='cpu',weights_only=True)
    cfg=json.loads((ROOT/'models/exp02e-unfreeze2/config.json').read_text())
    model=SpecialistHead(pooling='line-attn',unfreeze_last_n=2,local_files_only=True).to(protocol['device']).eval()
    load_trained_weights(model,torch.load(ROOT/'models/exp02e-unfreeze2/weights.pt',map_location='cpu',weights_only=True))
    model.requires_grad_(False)
    cache={'splits':{},'head':copy.deepcopy(model.head).cpu().state_dict(),
           'line_score':copy.deepcopy(model.line_score).cpu().state_dict(),'temperature':cfg['temperature']}
    metadata={}
    for split,path in [('train',ROOT/'data/exp02e/train.jsonl'),('validation',OUT/'validation.jsonl'),('final',OUT/'final.jsonl')]:
        items=[json.loads(s) for s in path.read_text().splitlines()];features=[];lengths=[];start=time.perf_counter()
        for offset in range(0,len(items),protocol['encoder_batch_size']):
            batch=items[offset:offset+protocol['encoder_batch_size']]
            objs=[r['objective'] for r in batch];texts=[r['text'] for r in batch]
            actual=[len(model.tokenizer(o,t,truncation=False)['input_ids']) for o,t in zip(objs,texts)]
            assert max(actual)<=protocol['max_pair_tokens'],'Input would be truncated'
            lengths.extend(actual)
            enc=model.encode(objs,texts,max_len=protocol['max_pair_tokens'])
            ids=enc.pop('line_ids').to(protocol['device'])
            with torch.inference_mode():
                hidden=model.encoder(**{k:v.to(protocol['device']) for k,v in enc.items()}).last_hidden_state
                features.extend(r.cpu().clone() for r in occupied_line_representations(hidden,ids))
            if offset%400==0:print(f'{split} features {offset}/{len(items)}',flush=True)
        cache['splits'][split]={'items':items,'features':features}
        metadata[split]=dict(n=len(items),data_sha256=sha(path),tokens_min=min(lengths),tokens_max=max(lengths),
                             truncated=0,seconds=time.perf_counter()-start)
    torch.save(cache,cache_path)
    meta_path.write_text(json.dumps(dict(protocol_sha256=protocol['sha256'],sha256=sha(cache_path),splits=metadata),indent=2)+'\n')
    return cache


class FeatureHeads(nn.Module):
    def __init__(self,cache):
        super().__init__()
        def head():return nn.Sequential(nn.Linear(768,256),nn.GELU(),nn.Dropout(.1),nn.Linear(256,1))
        self.line_score=head();self.judge=head();self.detect=head()
        self.line_score.load_state_dict(cache['line_score']);self.judge.load_state_dict(cache['head'])
    def forward(self,features):
        lengths=[len(f) for f in features];maximum=max(lengths)
        hidden=torch.zeros(len(features),maximum,768)
        mask=torch.ones(len(features),maximum,dtype=torch.bool)
        for i,f in enumerate(features):hidden[i,:len(f)]=f;mask[i,:len(f)]=False
        attention=self.line_score(hidden).squeeze(-1).masked_fill(mask,torch.finfo(hidden.dtype).min).softmax(-1)
        pooled=(hidden*attention[:,:,None]).sum(1)
        return self.judge(pooled).squeeze(-1),self.detect(pooled).squeeze(-1)


def objective_loss(j,d,items,arm):
    kinds=[r['kind'] for r in items]
    labels=torch.tensor([float(k=='pos') for k in kinds])
    if arm=='joint':
        related=torch.tensor([float(k!='neg_unrelated') for k in kinds])
        masked=related
        judge=(nn.functional.binary_cross_entropy_with_logits(j,labels,reduction='none')*masked).sum()/masked.sum().clamp(min=1)
        return judge+nn.functional.binary_cross_entropy_with_logits(d,related)
    loss=nn.functional.binary_cross_entropy_with_logits(j,labels)
    if arm=='pairwise':
        pairs=[]
        for domain in sorted({r['domain'] for r in items}):
            pos=[i for i,r in enumerate(items) if r['domain']==domain and r['kind']=='pos']
            neg=[i for i,r in enumerate(items) if r['domain']==domain and r['kind']!='pos']
            if pos and neg:pairs.append(nn.functional.softplus(1+j[neg][None,:]-j[pos][:,None]).mean())
        if pairs:loss=loss+torch.stack(pairs).mean()
    return loss


def score(model,split,arm):
    model.eval();rows=[]
    with torch.inference_mode():
        for offset in range(0,len(split['items']),64):
            items=split['items'][offset:offset+64];j,d=model(split['features'][offset:offset+64])
            # Product is only a ranking score, not a calibrated joint probability.
            values=(torch.sigmoid(j)*torch.sigmoid(d)) if arm=='joint' else j
            rows.extend(dict(id=r['id'],domain=r['domain'],objective=r['objective'],kind=r['kind'],
                             score=float(v),judge_logit=float(a),detect_logit=float(b))
                        for r,v,a,b in zip(items,values,j,d))
    return rows


def metrics(rows):
    def auc(a,b):return float(np.mean(np.array(a)[:,None]>np.array(b)[None,:]))
    pos=[r['score'] for r in rows if r['kind']=='pos']
    return {family:auc(pos,[r['score'] for r in rows if r['kind']==kind]) for family,kind in [('J','neg_decoy'),('D','neg_unrelated')]}


def train(protocol,cache,arm,seed):
    target=OUT/f'{arm}-{seed}';target.mkdir(exist_ok=True)
    if (target/'validation.json').exists():return
    assert not (target/'weights.pt').exists(),'Incomplete trained state: inspect; do not silently retrain'
    random.seed(seed);torch.manual_seed(seed)
    model=FeatureHeads(cache)
    opt=torch.optim.AdamW(model.parameters(),lr=protocol['learning_rate'],weight_decay=.01)
    split=cache['splits']['train'];indices=list(range(len(split['items'])));history=[]
    for epoch in range(1,protocol['epochs']+1):
        model.train();random.shuffle(indices);total=0;start=time.perf_counter()
        for offset in range(0,len(indices),protocol['batch_size']):
            chosen=indices[offset:offset+protocol['batch_size']]
            items=[split['items'][i] for i in chosen]
            j,d=model([split['features'][i] for i in chosen]);loss=objective_loss(j,d,items,arm)
            opt.zero_grad();loss.backward();opt.step();total+=float(loss.detach())*len(items)
        history.append(dict(epoch=epoch,loss=total/len(indices),seconds=time.perf_counter()-start))
    torch.save(model.state_dict(),target/'weights.pt')
    (target/'training_meta.json').write_text(json.dumps(dict(protocol_sha256=protocol['sha256'],seed=seed,
        arm=arm,epochs_completed=len(history),history=history,encoder_frozen=True,heads_trained_on='train only'),indent=2)+'\n')
    rows=score(model,cache['splits']['validation'],arm)
    (target/'validation.json').write_text(json.dumps(dict(metrics=metrics(rows),rows=rows),indent=2)+'\n')
    print(arm,seed,metrics(rows),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['cache','train','final'],default='cache')
    args=parser.parse_args();protocol=freeze();torch.set_num_threads(protocol['threads'])
    cache=build_cache(protocol)
    if args.phase=='cache':return
    for arm in protocol['arms']:
        for seed in protocol['seeds']:train(protocol,cache,arm,seed)
    means={arm:np.mean([list(json.loads((OUT/f'{arm}-{seed}/validation.json').read_text())['metrics'].values())
                       for seed in protocol['seeds']]) for arm in protocol['arms']}
    selection=dict(selected_arm=max(means,key=means.get),validation_means=means,
                   protocol_sha256=protocol['sha256'],ood_used_for_selection=False)
    frozen=OUT/'selection.json'
    if frozen.exists():assert json.loads(frozen.read_text())==selection
    else:frozen.write_text(json.dumps(selection,indent=2)+'\n')
    if args.phase!='final':return
    result={}
    for arm in ['parent']+protocol['arms']:
        result[arm]={}
        for seed in ([protocol['seeds'][0]] if arm=='parent' else protocol['seeds']):
            torch.manual_seed(seed);model=FeatureHeads(cache)
            if arm!='parent':model.load_state_dict(torch.load(OUT/f'{arm}-{seed}/weights.pt',weights_only=True))
            rows=score(model,cache['splits']['final'],arm)
            result[arm][str(seed)]={'metrics':metrics(rows),'rows':rows}
    (OUT/'final-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({a:{s:v['metrics'] for s,v in seeds.items()} for a,seeds in result.items()},indent=2))


if __name__=='__main__':main()
