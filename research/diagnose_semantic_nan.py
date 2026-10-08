"""Train-only numerical minimization; creates no candidate/final predictions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import time
import torch
from torch import nn
from research import relevance_study as common

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/semantic-tool-v1'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cpu','mps'],required=True)
    parser.add_argument('--max-batches',type=int,default=40);args=parser.parse_args()
    protocol=json.loads((OUT/'protocol.json').read_text());protocol['device']=args.device
    torch.set_num_threads(protocol['threads']);random.seed(303);torch.manual_seed(303)
    model,_=common.load_parent(args.device,True);common.matched_reset_head(model,303)
    optimizer=torch.optim.AdamW([
        dict(params=[p for n,p in model.named_parameters() if n.startswith('encoder.') and p.requires_grad],lr=protocol['encoder_learning_rate']),
        dict(params=[p for n,p in model.named_parameters() if not n.startswith('encoder.')],lr=protocol['learning_rate'])],weight_decay=.01)
    rows=common.read_rows(OUT/'train.jsonl');order=list(range(len(rows)));random.shuffle(order)
    model.train();model.encoder.eval();trainable={n:p for n,p in model.named_parameters() if p.requires_grad}
    target=OUT/'numerical-diagnostic';target.mkdir(exist_ok=True)
    path=target/f'{args.device}-{args.max_batches}.jsonl'
    if path.exists():raise ValueError('Preserve prior diagnostic; no overwrite')
    began=time.perf_counter()
    with path.open('x') as stream:
        for i,offset in enumerate(range(0,len(order),protocol['batch_size'])):
            if i>=args.max_batches:break
            batch=[rows[j] for j in order[offset:offset+protocol['batch_size']]]
            encoded,_=common.encode_uncut(model,batch,protocol);optimizer.zero_grad();logits=model(encoded)
            labels=torch.tensor([r['label'] for r in batch],dtype=torch.float32,device=logits.device)
            loss=nn.functional.binary_cross_entropy_with_logits(logits,labels)
            record=dict(batch=i,ids=[r['id'] for r in batch],forward_finite=bool(torch.isfinite(logits).all()),loss_finite=bool(torch.isfinite(loss)),
                        loss=float(loss.detach().cpu()),device=args.device,seed=303)
            if record['forward_finite'] and record['loss_finite']:
                loss.backward()
                bad=[n for n,p in trainable.items() if p.grad is not None and not bool(torch.isfinite(p.grad).all())]
                record['nonfinite_gradients']=bad
                record['max_absolute_gradients']={n:float(p.grad.abs().max().cpu()) for n,p in trainable.items() if p.grad is not None}
                if not bad:
                    optimizer.step()
                    record['nonfinite_parameters']=[n for n,p in trainable.items() if not bool(torch.isfinite(p).all())]
            stream.write(json.dumps(record)+'\n');stream.flush()
            print(args.device,i,record['loss_finite'],record.get('nonfinite_gradients',[]),flush=True)
            if not record['loss_finite'] or record.get('nonfinite_gradients') or record.get('nonfinite_parameters'):break
    meta=dict(scope='same seed303 first shuffled training batches; numerical diagnosis only; no candidate or final use',
              source_sha256=common.sha(Path(__file__)),original_protocol_sha256=protocol['sha256'],
              device=args.device,batches=i+1,seconds=time.perf_counter()-began,API_calls=0)
    path.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':main()
