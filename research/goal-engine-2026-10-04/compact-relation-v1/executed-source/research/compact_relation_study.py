"""Fixed full-MiniLM adaptation; exposed development families, fresh final pairs."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import resource
import socket
import statistics
import sys
import time

import torch
from safetensors.torch import save_file, load_file
from transformers import AutoTokenizer

from research import compact_relation_corpus as corpus
from research.compact_relation_training import grouped_batches, relation_loss
from research.measurement_projection import project_measurement
from research.audit_reranker_diagnostic import reduce
from research.reranker_control import PairReranker
from research.reranker_diagnostic import digest, save_once, sha
from specialist.checkpoint import load_trained_weights
from specialist.numerical import finite_update

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/compact-relation-v1'
WEIGHTS=ROOT/'models/compact-relation-v1'
UPSTREAM=ROOT/'research/goal-engine-2026-10-04/rerank-next/upstream-manifest.json'


def snapshot_path(manifest):
    return Path.home()/'.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots'/manifest['revision']


def write_lines_once(path,rows):
    text=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
    if path.exists():
        assert path.read_text()==text, 'Frozen data changed'
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)


def prepare():
    manifest=json.loads(UPSTREAM.read_text())
    snapshot=snapshot_path(manifest)
    for name,expected in manifest['files'].items():
        assert sha(snapshot/name)==expected
    tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    data={}
    for split,groups in [('train',16),('validation',4),('final',8)]:
        rows=corpus.build_split(split,groups)
        views=[]
        for row in rows:
            view=project_measurement(row['objective'],row['text'])
            assert view['status']=='PROJECTED'
            view['id']=row['id']
            view['actual_tokens']=len(tokenizer(view['objective'],view['text'],truncation=False)['input_ids'])
            assert view['actual_tokens']<=512
            views.append(view)
        write_lines_once(OUT/f'{split}.jsonl',rows)
        write_lines_once(OUT/f'{split}-views.jsonl',views)
        data[split]=dict(n=len(rows),domains=sorted({r['domain'] for r in rows}),
                        sha256=sha(OUT/f'{split}.jsonl'),views_sha256=sha(OUT/f'{split}-views.jsonl'),
                        max_pair_tokens=max(v['actual_tokens'] for v in views))
    sources=['research/compact_relation_study.py','research/compact_relation_corpus.py',
             'research/compact_relation_training.py','research/semantic_corpus.py',
             'research/measurement_projection.py','research/reranker_control.py',
             'research/reranker_diagnostic.py','research/audit_reranker_diagnostic.py',
             'specialist/checkpoint.py','specialist/numerical.py']
    protocol=dict(schema='compact-measurement-adaptation/0.1',model=manifest,data=data,
        sources={name:sha(ROOT/name) for name in sources},
        versions={name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','numpy','safetensors']},
        arms=['bce','joint'],seeds=[101,202,303],epochs=3,groups_per_batch=2,
        optimizer=dict(name='AdamW',lr=.00002,weight_decay=.01,betas=[.9,.999],eps=1e-8),
        device='cpu',dtype='float32',threads=8,trainable='all 22,713,601 pretrained parameters; no random head reset',
        input_recipe='frozen scope-checked two-grammar question/measurement view, entity verified by code; original evidence preserved; no annotations passed to model',
        objective=dict(bce='binary_cross_entropy_with_logits',joint='0.5 BCE + 0.5 mean softplus(negative-positive) over all same-objective alternatives'),
        batch_recipe='whole original 8-row groups; sorted ids within group; random.Random(seed*100+epoch) shuffles group names; no groups split',
        numerical_guards='finite loss, gradient, parameters, optimizer state every update; any invalid run stops study without a candidate',
        threshold='greatest first validation raw-logit threshold with >=.95 positive recall',
        selection='highest mean validation pooled AUC across all three seeds; exact ties choose first arm bce; no final inspected for selection',
        criteria=dict(auc_min=.90,paired_auc_min=.90,within_objective_auc_min=.90,positive_recall_min=.95,negative_rejection_min=.70,all_rows_complete=True,all_seeds_pass=True),
        controls=['frozen upstream on identical projected inputs'],
        bootstrap=dict(unit='whole reserved final measurement family',draws=2000,seed=442413),
        scope='shared-author/schema/primitive vocabulary synthetic P1 measurement relevance; eight newly authored final pair families; previous 18 exposed families now all development, not blind/OOD/P2/production',
        API_calls=0,current_default_changed=False,allow_selective_retry=False,extra_epochs_allowed=False)
    protocol['sha256']=digest(protocol)
    save_once(OUT/'protocol.json',protocol)
    for name,expected in protocol['sources'].items():
        path=OUT/'executed-source'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            assert sha(path)==expected
        else:
            path.write_bytes((ROOT/name).read_bytes())
    return protocol


def dataset(split):
    rows=[json.loads(line) for line in (OUT/f'{split}.jsonl').read_text().splitlines()]
    views={v['id']:v for v in (json.loads(line) for line in (OUT/f'{split}-views.jsonl').read_text().splitlines())}
    return rows,views


def evaluate(scorer,split,protocol,threshold=None):
    rows,views=dataset(split)
    scorer.model.eval()
    began=time.perf_counter()
    raw=scorer.score([views[r['id']]['objective'] for r in rows],[views[r['id']]['text'] for r in rows])
    scores=[dict(id=r['id'],domain=r['domain'],report_id=r['report_id'],label=r['label'],
                 original_input_sha256=r['content_hash'],**s) for r,s in zip(rows,raw)]
    if any(r['error'] or r['score'] is None or r['truncated'] for r in scores):
        raise ValueError('Incomplete scoring cannot select or pass a candidate')
    if threshold is None:
        positive=[r['score'] for r in scores if r['label']==1]
        threshold=max(t for t in set(positive) if statistics.mean(s>=t for s in positive)>=.95)
    return dict(protocol_sha256=protocol['sha256'],rows=scores,threshold=threshold,
                metrics=reduce(scores,threshold,{r['id']:r for r in rows}),elapsed_pass_s=time.perf_counter()-began,
                nonpadding_accounting=scorer.accounting.copy())


def train_candidate(arm,seed,protocol):
    directory=OUT/f'{arm}-{seed}'
    if (directory/'training_meta.json').exists():
        raise ValueError('Unexpected existing candidate; inspect completed evidence')
    torch.manual_seed(seed)
    scorer=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=16)
    save_once(directory/'started.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed,initial_identity=scorer.identity))
    model=scorer.model
    rows,views=dataset('train')
    spec=protocol['optimizer']
    optimizer=torch.optim.AdamW(model.parameters(),lr=spec['lr'],weight_decay=spec['weight_decay'],betas=tuple(spec['betas']),eps=spec['eps'])
    history=[]
    for epoch in range(1,protocol['epochs']+1):
        model.train()
        batches=grouped_batches(rows,random.Random(seed*100+epoch),protocol['groups_per_batch'])
        losses=[]
        tokens=0
        slots=0
        began=time.perf_counter()
        for step,batch in enumerate(batches,1):
            encoded=scorer.tokenizer([views[r['id']]['objective'] for r in batch],
                [views[r['id']]['text'] for r in batch],padding=True,truncation=False,return_tensors='pt')
            assert encoded['attention_mask'].sum(1).tolist()==[views[r['id']]['actual_tokens'] for r in batch]
            assert encoded['input_ids'].shape[1]<=scorer.window
            tokens+=int(encoded['attention_mask'].sum())
            slots+=encoded['input_ids'].numel()
            loss=relation_loss(batch,model(**encoded).logits[:,0],arm)
            finite_update(loss,model,optimizer)
            losses.append(float(loss.detach()))
            if step % 48 == 0:
                print(arm,seed,'epoch',epoch,'step',step,'loss',round(statistics.mean(losses),5),flush=True)
        receipt=dict(epoch=epoch,loss=statistics.mean(losses),steps=len(batches),submitted_pairs=len(rows),
                     submitted_nonpadding_tokens=tokens,padded_token_slots=slots,seconds=time.perf_counter()-began,
                     all_updates_finite=True)
        save_once(directory/f'epoch-{epoch}.json',receipt)
        history.append(receipt)
        print(arm,seed,receipt,flush=True)
    model.eval()
    path=WEIGHTS/f'{arm}-{seed}/model.safetensors'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise ValueError('Refusing to overwrite candidate weights')
    save_file({k:v.detach().contiguous() for k,v in model.state_dict().items()},str(path))
    validation=evaluate(scorer,'validation',protocol)
    save_once(directory/'validation.json',validation)
    save_once(directory/'training_meta.json',dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed,
        epochs_completed=len(history),history=history,encoder_adapted=True,all_parameters_trainable=True,
        weights_path=str(path.relative_to(ROOT)),weights_sha256=sha(path),initial_identity=scorer.identity,
        metadata_origin='written directly by this driver after finite updates and completed validation; not reconstructed'))
    print(arm,seed,'VALIDATION',validation['metrics'],flush=True)


def gate(metrics,criteria):
    values=metrics.copy()
    values['within_objective_auc']=metrics['within_objective']['auc']
    return (metrics['n']==metrics['eligible'] and metrics['errors']==metrics['cuts']==0
            and all(values[k.removesuffix('_min')]>=v for k,v in criteria.items() if k.endswith('_min')))


def run(protocol):
    if (OUT/'summary.json').exists():
        return
    if (OUT/'started.json').exists():
        raise ValueError('Partial study requires inspection, no selective rerun')
    save_once(OUT/'started.json',dict(protocol_sha256=protocol['sha256'],python=sys.version,platform=platform.platform()))
    torch.set_num_threads(protocol['threads'])
    def denied(*args,**kwargs):
        raise RuntimeError('Network forbidden during training/inference')
    socket.socket.connect=denied
    try:
        baseline=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=16)
        baseline_val=evaluate(baseline,'validation',protocol)
        save_once(OUT/'frozen/validation.json',baseline_val)
        del baseline
        for arm in protocol['arms']:
            for seed in protocol['seeds']:
                train_candidate(arm,seed,protocol)
        means={arm:statistics.mean(json.loads((OUT/f'{arm}-{seed}/validation.json').read_text())['metrics']['auc']
                                  for seed in protocol['seeds']) for arm in protocol['arms']}
        selected=max(protocol['arms'],key=lambda arm:means[arm])
        save_once(OUT/'selection.json',dict(protocol_sha256=protocol['sha256'],selected_arm=selected,
                                          validation_mean_auc=means,final_inspected=False))
        arms={}
        for arm in protocol['arms']:
            finals=[]
            for seed in protocol['seeds']:
                directory=OUT/f'{arm}-{seed}'
                meta=json.loads((directory/'training_meta.json').read_text())
                scorer=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=16)
                path=ROOT/meta['weights_path']
                assert sha(path)==meta['weights_sha256']
                load_trained_weights(scorer.model,load_file(str(path),device='cpu'))
                threshold=json.loads((directory/'validation.json').read_text())['threshold']
                result=evaluate(scorer,'final',protocol,threshold)
                result.update(selected_before_final=selected==arm,adapted_weights_sha256=meta['weights_sha256'])
                save_once(directory/'final.json',result)
                finals.append(result)
                print(arm,seed,'FINAL',result['metrics'],flush=True)
            arms[arm]=dict(mean={k:statistics.mean(r['metrics'][k] for r in finals) for k in ['auc','paired_auc','positive_recall','negative_rejection']},
                mean_within_objective_auc=statistics.mean(r['metrics']['within_objective']['auc'] for r in finals),
                seeds_pass=[gate(r['metrics'],protocol['criteria']) for r in finals],
                all_seeds_pass=all(gate(r['metrics'],protocol['criteria']) for r in finals))
        baseline=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=16)
        baseline_final=evaluate(baseline,'final',protocol,baseline_val['threshold'])
        save_once(OUT/'frozen/final.json',baseline_final)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        save_once(OUT/'summary.json',dict(protocol_sha256=protocol['sha256'],selected_arm=selected,arms=arms,
            frozen_final=baseline_final['metrics'],selected_pass=arms[selected]['all_seeds_pass'],
            peak_study_process_rss_bytes=peak if sys.platform=='darwin' else peak*1024,
            bootstrap_intervals_computed=False,API_calls=0,adoption=False,P2_admission=False,current_default_changed=False))
    except Exception as exc:
        save_once(OUT/'failure.json',dict(protocol_sha256=protocol['sha256'],error_type=type(exc).__name__,error=str(exc),
            completed_candidates=[p.parent.name for p in OUT.glob('*/training_meta.json')],
            selective_retry_allowed=False,study_complete=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=['prepare','run'])
    args=parser.parse_args()
    protocol=prepare()
    if args.phase=='prepare':
        print('Frozen:',protocol['sha256'],protocol['data'])
    else:
        run(protocol)
