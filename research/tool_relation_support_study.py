"""Bounded multilingual classifier/tail adaptation on direct-record tool tasks.

Retains the scalar ranking prior, preserves all frozen encoder parameters, and
counts every semantic UNKNOWN category. No final selection, selective retries,
production/P2/default changes or implicit native ModernBERT substitution.
"""

import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import resource
import socket
import statistics
import sys
import time

import torch
from safetensors.torch import load_file,save_file

from research.audit_tool_relation_supervision import audit as audit_data
from research.reranker_control import PairReranker
from research.tool_relation_adaptation import configure_adaptation,frozen_parameter_sha256
from research.tool_role_policy import calibrate,metrics,passes
from research.tool_role_training import training_items,class_weights,classification_loss
from specialist.checkpoint import load_trained_weights
from specialist.numerical import finite_update

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/goal-engine-2026-10-04'
OUT=BASE/'tool-relation-support-v1'
DATA=BASE/'tool-relations-grounded-v1/supervision-v1'
WEIGHTS=ROOT/'models/tool-relation-support-v1'
UPSTREAM=BASE/'semantic-next/upstream/artifacts.json'
SOURCES=['research/tool_relation_support_study.py','research/tool_relation_adaptation.py',
    'research/ranking_support_initialization.py','research/tool_role_training.py','research/tool_role_policy.py',
    'research/reranker_control.py','research/audit_tool_relation_support.py','research/audit_tool_role_support.py',
    'research/audit_tool_relation_supervision.py','research/audit_tool_relations.py',
    'specialist/checkpoint.py','specialist/numerical.py']


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def save_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as target:
        target.write(json.dumps(value,indent=2,allow_nan=False)+'\n')


def snapshot_path(manifest):
    return Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/manifest['revision']


def dataset(split):
    rows=[json.loads(line) for line in (DATA/f'{split}.jsonl').read_text().splitlines()]
    views=[json.loads(line) for line in (DATA/f'{split}-views.jsonl').read_text().splitlines()]
    return rows,views


def numeric_batch(encoded,lengths,window):
    if encoded['input_ids'].shape[1]>window or encoded['attention_mask'].sum(1).tolist()!=lengths:
        raise ValueError('Complete pair window or attention-mask accounting changed')
    return int(encoded['attention_mask'].sum()),encoded['input_ids'].numel()


def prepare():
    target=OUT/'protocol.json'
    if target.exists():
        protocol=json.loads(target.read_text())
        if digest({k:v for k,v in protocol.items() if k!='sha256'})!=protocol['sha256']:
            raise ValueError('Frozen protocol changed')
        for name,expected in protocol['sources'].items():
            if sha(ROOT/name)!=expected or sha(OUT/'executed-source'/name)!=expected:
                raise ValueError('Frozen executable source drift')
        for name,expected in protocol['data_files'].items():
            if sha(DATA/name)!=expected:raise ValueError('Frozen input data drift')
        return protocol
    data_audit=audit_data(DATA,recount_tokenizer=True)
    manifest=json.loads(UPSTREAM.read_text())
    torch.set_num_threads(8)
    preflight=PairReranker.from_snapshot(snapshot_path(manifest),manifest,max_pair_tokens=512,batch_size=16)
    recipe=configure_adaptation(preflight.model,101,last_n=2)
    preflight_identity=preflight.identity
    del preflight
    rows,views=dataset('train')
    items=training_items(rows,views)
    names=['protocol.json','coverage.json','training-preparation.json']+\
        [f'{split}{suffix}' for split in ['train','validation','final'] for suffix in ['.jsonl','-views.jsonl']]
    protocol=dict(schema='tool-relation-retained-support/0.1',frozen_at_utc=now(),model=manifest,
        data_protocol_sha256=data_audit['protocol_sha256'],data_directory='tool-relations-grounded-v1/supervision-v1',
        data_files={name:sha(DATA/name) for name in names},sources={name:sha(ROOT/name) for name in SOURCES},
        data_scope='Authored direct-record claims and EN/PT goals, English captions; actual Retry/UDP/Git values. New final pair combinations/wording, all primitives/tools seen in train. Broad/derived/diagnostic goals are semantic UNKNOWN.',
        versions={name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','numpy','safetensors']},
        seeds=[101,202,303],epochs=3,batch_size=16,threads=8,device='cpu',dtype='float32',window=512,
        optimizer=dict(name='AdamW',lr=.00002,weight_decay=.01,betas=[.9,.999],eps=1e-8),
        adaptation='Classifier dense/out_proj and last2 XLM-R encoder blocks only; scalar output encoded as initial relevance margin, separate seeded UNKNOWN row. Embeddings/first10 blocks frozen and in eval mode during training.',
        preflight_identity=preflight_identity,trainability=recipe,labels=['IRRELEVANT','RELEVANT','UNKNOWN'],
        train_unique=len(items),train_class_counts=[sum(item['class_id']==i for item in items) for i in range(3)],
        train_unique_items_sha256=digest(items),global_class_weights=class_weights(items),
        objective='Globally weighted mean per-item CE after train-only dedup; no class/role/truth/binding metadata in either model string; structural UNKNOWN bypass',
        batch_recipe='Sorted unique hashes, random.Random(seed*100+epoch) shuffle; chunks16 with final partial batch',
        rng='CPU default generator seeded per candidate; fixed shuffle; UNKNOWN row uses local CPU generator; no accelerator seed mutation',
        score_axes=dict(relevance='logit1-logit0',unsupported='logit2-logsumexp(logit0,logit1)',
            reduction='Python double from persisted fp32 logits, stable logsumexp; exactly recountable'),
        calibration='Lowest score among ALL validation semantic UNKNOWN kinds; greatest global relevance cutoff retaining .95 positives/contradictions per EN/PT; no final fitting',
        criteria=dict(pooled_auc=.90,within_goal_auc=.90,positive_keep_recall=.95,contradiction_keep_recall=.95,
            negative_drop_rejection=.70,semantic_unknown_recognition=.95,structural_unknown_recognition=1.0,unknown_drops=0),
        selection='Fixed last2+classifier design, all3 seeds required; all candidate weights/global validation cutoffs frozen before any final scoring',
        controls='Original immutable multilingual scalar on identical validation/final pairs, blanket shadow UNKNOWN/KEEP without learned support authority',
        finite_guard='Every update loss/grad/parameter/optimizer-state finite; accepted-update receipts; verify frozen parameter hash each completed epoch; abort invalid study without selective retry',
        final_action='Exactly one complete original final pass per candidate and scalar control after selection',
        API_calls=0,P2_admission=False,default_changed=False,publishing=False,no_independence_interval=True)
    protocol['sha256']=digest(protocol)
    for name,expected in protocol['sources'].items():
        target_source=OUT/'executed-source'/name
        target_source.parent.mkdir(parents=True,exist_ok=True)
        with target_source.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        if sha(target_source)!=expected:raise ValueError('Source changed during freeze')
    save_new(target,protocol)
    save_new(OUT/'data-audit-before-training.json',data_audit)
    return protocol


def score_population(scorer,rows,views,protocol,path,scalar=False):
    if (len(rows)!=len(views) or any(r['id']!=v['id'] for r,v in zip(rows,views))
            or path.exists()):
        raise ValueError('Aligned complete receipts and a new score destination required')
    eligible=[]
    for index,(row,saved) in enumerate(zip(rows,views)):
        view=saved['view']
        if view['status']=='PROJECTED':
            if (digest([view['objective'],view['text']])!=row['projected_input_hash']
                    or type(saved['projected_tokens']) is not int or not 0<saved['projected_tokens']<=scorer.window):
                raise ValueError('Changed complete model input or overflow')
            eligible.append(index)
        elif view['status']!='UNKNOWN' or row['label'] is not None or row['projected_input_hash'] is not None:
            raise ValueError('Invalid structural bypass')
    results=[dict(id=row['id'],original_input_hash=row['content_hash'],input_hash=row['projected_input_hash'],
        status='UNKNOWN',score=None,support_score=None,logits=None,actual_tokens=saved['projected_tokens'],
        submitted=False,forward_completed=False,truncated=False,error=None,
        guard_reason='unsupported_record' if saved['view']['status']=='UNKNOWN' else None) for row,saved in zip(rows,views)]
    accounting=dict(counted_pairs=len(eligible),counted_tokens=sum(views[i]['projected_tokens'] for i in eligible),
        submitted_pairs=0,submitted_tokens=0,forward_completed_pairs=0,forward_completed_tokens=0,
        valid_score_pairs=0,valid_score_tokens=0)
    scorer.model.eval();began=time.perf_counter();error=None;complete=False
    try:
        for start in range(0,len(eligible),protocol['batch_size']):
            indices=eligible[start:start+protocol['batch_size']]
            batch=[views[i]['view'] for i in indices]
            if scalar:
                output=scorer.score([v['objective'] for v in batch],[v['text'] for v in batch])
                if len(output)!=len(indices):raise ValueError('Missing scalar row outputs')
                for i,score in zip(indices,output):
                    for flag,counter in [('submitted','submitted'),('forward_completed','forward_completed')]:
                        if score[flag]:
                            results[i][flag]=True;accounting[counter+'_pairs']+=1
                            accounting[counter+'_tokens']+=results[i]['actual_tokens']
                    results[i]['error']=score['error']
                    if (score['status']!='SCORED' or score['truncated'] or score['error']
                            or score['input_sha256']!=results[i]['input_hash'] or score['actual_tokens']!=results[i]['actual_tokens']):
                        raise ValueError('Incomplete/mismatched scalar output')
                    results[i].update(status='SCORED',score=score['score'])
                    accounting['valid_score_pairs']+=1;accounting['valid_score_tokens']+=results[i]['actual_tokens']
            else:
                encoded=scorer.tokenizer([v['objective'] for v in batch],[v['text'] for v in batch],
                    padding=True,truncation=False,return_tensors='pt')
                tokens,unused=numeric_batch(encoded,[results[i]['actual_tokens'] for i in indices],scorer.window)
                for i in indices:results[i]['submitted']=True
                accounting['submitted_pairs']+=len(indices);accounting['submitted_tokens']+=tokens
                with torch.inference_mode():logits=scorer.model(**encoded).logits
                for i in indices:results[i]['forward_completed']=True
                accounting['forward_completed_pairs']+=len(indices);accounting['forward_completed_tokens']+=tokens
                if logits.shape!=(len(indices),3) or not bool(torch.isfinite(logits).all()):
                    raise ValueError('Invalid/nonfinite three-class output')
                for offset,i in enumerate(indices):
                    values=logits[offset].tolist();largest=max(values[:2])
                    support=values[2]-largest-math.log(sum(math.exp(v-largest) for v in values[:2]))
                    results[i].update(status='SCORED',logits=values,
                        score=values[1]-values[0],support_score=support)
                accounting['valid_score_pairs']+=len(indices);accounting['valid_score_tokens']+=tokens
        complete=True
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        for i in eligible:
            if results[i]['submitted'] and results[i]['status']!='SCORED':results[i]['error']=error
        raise
    finally:
        raw=dict(protocol_sha256=protocol['sha256'],scalar_control=scalar,rows=results,accounting=accounting,
            elapsed_s=time.perf_counter()-began,finished_at_utc=now(),complete=complete,error=error)
        save_new(path,raw)
    return raw


def evaluate(scorer,split,protocol,directory,scalar=False,thresholds=None):
    rows,views=dataset(split)
    raw=score_population(scorer,rows,views,protocol,directory/f'{split}-scores.json',scalar)
    if scalar:thresholds=dict(support=None,relevance=None)
    elif thresholds is None:
        thresholds=calibrate(rows,raw['rows'])
        save_new(directory/'thresholds.json',dict(protocol_sha256=protocol['sha256'],thresholds=thresholds,
            final_inspected=False,frozen_at_utc=now()))
    overall=metrics(rows,raw['rows'],thresholds,scalar)
    breakdown={}
    for column,values in [('by_language',['en','pt']),
        ('by_binary_source',sorted({r['binding']['source'] for r in rows if r['label'] is not None})),
        ('by_family',sorted({r['family'] for r in rows if r['label'] is not None}))]:
        breakdown[column]={}
        for value in values:
            field='goal_language' if column=='by_language' else ('family' if column=='by_family' else None)
            paired=[(r,s) for r,s in zip(rows,raw['rows']) if
                (r[field]==value if field else r['binding']['source']==value and r['label'] is not None)]
            breakdown[column][value]=metrics([r for r,s in paired],[s for r,s in paired],thresholds,scalar)
    result=dict(protocol_sha256=protocol['sha256'],thresholds=thresholds,metrics=overall,
        **breakdown,passed=passes(overall) and all(passes(m) for m in breakdown['by_language'].values()),scalar_control=scalar)
    save_new(directory/f'{split}-metrics.json',result)
    return result


def train(seed,protocol):
    directory=OUT/f'seed-{seed}'
    # CPU-only seed: no MPS/CUDA generator is mutated by this local experiment.
    torch.random.default_generator.manual_seed(seed)
    scorer=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=protocol['batch_size'])
    recipe=configure_adaptation(scorer.model,seed,last_n=2)
    for key in ['total_parameters','trainable_parameters','frozen_parameters','trainable_names','frozen_names','frozen_parameter_sha256']:
        if recipe[key]!=protocol['trainability'][key]:raise ValueError('Actual trainability differs from frozen recipe')
    model=scorer.model;identity=dict(**scorer.identity,output_classes=3,adapted_parameters=recipe['total_parameters'],
        trainable_parameters=recipe['trainable_parameters'],initialization=recipe['initialization'])
    save_new(directory/'started.json',dict(protocol_sha256=protocol['sha256'],seed=seed,initial_identity=identity,
        trainability=recipe,started_at_utc=now()))
    rows,views=dataset('train');items=training_items(rows,views)
    if digest(items)!=protocol['train_unique_items_sha256']:raise ValueError('Changed training inputs')
    lengths={v['view']['projected_input_sha256']:v['projected_tokens'] for v in views if v['view']['status']=='PROJECTED'}
    spec=protocol['optimizer']
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=spec['lr'],
        weight_decay=spec['weight_decay'],betas=tuple(spec['betas']),eps=spec['eps'])
    history=[]
    with (directory/'accepted-updates.jsonl').open('x') as updates:
        for epoch in range(1,protocol['epochs']+1):
            model.train();model.roberta.embeddings.eval()
            for block in model.roberta.encoder.layer[:-2]:block.eval()
            order=list(items);random.Random(seed*100+epoch).shuffle(order)
            losses=[];tokens=slots=processed=0;began=time.perf_counter()
            for start in range(0,len(order),protocol['batch_size']):
                batch=order[start:start+protocol['batch_size']]
                encoded=scorer.tokenizer([i['objective'] for i in batch],[i['text'] for i in batch],
                    padding=True,truncation=False,return_tensors='pt')
                token_n,slot_n=numeric_batch(encoded,[lengths[i['input_hash']] for i in batch],scorer.window)
                try:
                    loss=classification_loss(batch,model(**encoded).logits,protocol['global_class_weights'])
                    finite_update(loss,model,optimizer)
                except Exception as exc:
                    save_new(directory/'failed-update.json',dict(protocol_sha256=protocol['sha256'],seed=seed,
                        epoch=epoch,step=len(losses)+1,completed_pairs_before_failed_update=processed,
                        error_type=type(exc).__name__,error=str(exc),epoch_complete=False,candidate_valid=False,utc=now()))
                    raise
                value=float(loss.detach());losses.append((value,len(batch)))
                processed+=len(batch);tokens+=token_n;slots+=slot_n
                updates.write(json.dumps(dict(protocol_sha256=protocol['sha256'],seed=seed,epoch=epoch,
                    step=len(losses),pair_hashes=[i['input_hash'] for i in batch],pairs=len(batch),loss=value,
                    nonpadding_tokens=token_n,padded_slots=slot_n,finite_update_accepted=True),allow_nan=False)+'\n')
                updates.flush()
                if len(losses)%50==0:
                    print(seed,'epoch',epoch,'step',len(losses),'loss',round(sum(v*n for v,n in losses)/processed,5),flush=True)
            frozen_hash=frozen_parameter_sha256(model)
            if frozen_hash!=recipe['frozen_parameter_sha256']:raise ValueError('Frozen encoder parameters changed')
            receipt=dict(protocol_sha256=protocol['sha256'],seed=seed,epoch=epoch,steps=len(losses),unique_pairs=processed,
                weighted_mean_loss=sum(v*n for v,n in losses)/processed,submitted_nonpadding_tokens=tokens,
                padded_token_slots=slots,all_updates_finite=True,frozen_parameter_sha256=frozen_hash,
                seconds=time.perf_counter()-began,finished_at_utc=now())
            save_new(directory/f'epoch-{epoch}.json',receipt);history.append(receipt)
            print(seed,'EPOCH',receipt,flush=True)
    path=WEIGHTS/f'seed-{seed}/model.safetensors';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Refusing candidate weight overwrite')
    save_file({k:v.detach().contiguous() for k,v in model.state_dict().items()},str(path))
    validation=evaluate(scorer,'validation',protocol,directory)
    save_new(directory/'training_meta.json',dict(protocol_sha256=protocol['sha256'],seed=seed,epochs_completed=len(history),
        history=history,weights_path=str(path.relative_to(ROOT)),weights_sha256=sha(path),identity=identity,trainability=recipe,
        metadata_origin='Direct accepted-update/epoch receipts after finite guards, fixed epochs and completed validation; no terminal reconstruction',
        final_inspected=False,validation_pass=validation['passed']))
    print(seed,'VALIDATION',validation['metrics'],flush=True)


def run(protocol):
    if (OUT/'started.json').exists():raise ValueError('Inspect existing execution; no selective restart')
    save_new(OUT/'started.json',dict(protocol_sha256=protocol['sha256'],utc=now(),python=sys.version,platform=platform.platform()))
    torch.set_num_threads(protocol['threads']);original_connect=socket.socket.connect
    def denied(*args,**kwargs):raise RuntimeError('No network during training/evaluation')
    socket.socket.connect=denied
    try:
        scalar=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=protocol['batch_size'])
        evaluate(scalar,'validation',protocol,OUT/'frozen',scalar=True);del scalar
        for seed in protocol['seeds']:train(seed,protocol)
        calibration={str(s):json.loads((OUT/f'seed-{s}/thresholds.json').read_text()) for s in protocol['seeds']}
        weights={str(s):json.loads((OUT/f'seed-{s}/training_meta.json').read_text())['weights_sha256'] for s in protocol['seeds']}
        save_new(OUT/'selection.json',dict(protocol_sha256=protocol['sha256'],fixed_candidate='retained multilingual last2+classifier',
            seeds=protocol['seeds'],weights_sha256=weights,calibration=calibration,final_inspected=False,frozen_at_utc=now()))
        finals=[]
        for seed in protocol['seeds']:
            directory=OUT/f'seed-{seed}';meta=json.loads((directory/'training_meta.json').read_text())
            scorer=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=protocol['batch_size'])
            configure_adaptation(scorer.model,seed,last_n=2)
            path=ROOT/meta['weights_path']
            if sha(path)!=meta['weights_sha256']:raise ValueError('Candidate weight identity changed')
            load_trained_weights(scorer.model,load_file(str(path),device='cpu'))
            if frozen_parameter_sha256(scorer.model)!=protocol['trainability']['frozen_parameter_sha256']:
                raise ValueError('Loaded candidate changed frozen encoder')
            final=evaluate(scorer,'final',protocol,directory,thresholds=calibration[str(seed)]['thresholds'])
            finals.append(final);print(seed,'FINAL',final['metrics'],flush=True);del scorer
        scalar=PairReranker.from_snapshot(snapshot_path(protocol['model']),protocol['model'],batch_size=protocol['batch_size'])
        control=evaluate(scalar,'final',protocol,OUT/'frozen',scalar=True)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        summary=dict(protocol_sha256=protocol['sha256'],seed_passes=[r['passed'] for r in finals],all_seeds_pass=all(r['passed'] for r in finals),
            mean={key:statistics.mean(r['metrics'][key] for r in finals) for key in ['pooled_auc','within_goal_auc','positive_keep_recall',
                'contradiction_keep_recall','negative_drop_rejection','semantic_unknown_recognition']},
            unknown_drops=[r['metrics']['unknown_drops'] for r in finals],frozen_final=control['metrics'],
            peak_study_process_rss_bytes=peak if sys.platform=='darwin' else peak*1024,
            API_calls=0,P2_admission=False,default_changed=False,adoption=False,finished_at_utc=now())
        save_new(OUT/'summary.json',summary);return summary
    except Exception as exc:
        save_new(OUT/'failure.json',dict(protocol_sha256=protocol['sha256'],error_type=type(exc).__name__,error=str(exc),
            study_complete=False,selective_retry_allowed=False,completed_candidates=[p.parent.name for p in OUT.glob('*/training_meta.json')],utc=now()))
        raise
    finally:socket.socket.connect=original_connect


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    protocol=prepare()
    print(json.dumps(run(protocol) if args.action=='run' else dict(protocol_sha256=protocol['sha256'],train_unique=protocol['train_unique'],
        total_parameters=protocol['trainability']['total_parameters'],trainable_parameters=protocol['trainability']['trainable_parameters']),indent=2))
