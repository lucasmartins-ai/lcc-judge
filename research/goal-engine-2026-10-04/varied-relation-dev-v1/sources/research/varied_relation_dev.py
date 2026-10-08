"""Bounded balanced conditional development on varied actual-tool states.

Known tools/primitives/edges; no final, adoption or broad LCC usefulness claim.
Frozen sources/data and finite updates preserve complete independent receipts.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import resource
import socket
import sys
import time

import torch
from safetensors.torch import save_file

from research.factorized_relation_training import conditional_loss,training_quartets
from research.varied_relation_training import adapt_records,balanced_loss,calibrate_bilingual
from research.audit_tool_relation_state_supervision import audit as audit_data,rows as gzip_rows
from research.reranker_control import PairReranker
from research.tool_relation_adaptation import configure_adaptation,frozen_parameter_sha256
from research.tool_relation_support_study import digest,sha,save_new,now,snapshot_path,numeric_batch,score_population
from research.tool_role_policy import metrics,passes
from research.tool_role_training import training_items
from specialist.numerical import finite_update

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/goal-engine-2026-10-04'
OUT=BASE/'varied-relation-dev-v1'
DATA=BASE/'tool-relation-states-v2/supervision-v1'
WEIGHTS=ROOT/'models/varied-relation-dev-v1/model.safetensors'
SOURCES=['research/varied_relation_dev.py','research/varied_relation_training.py','research/factorized_relation_training.py',
         'research/audit_varied_relation_dev.py','research/audit_tool_relation_state_supervision.py',
         'research/audit_tool_relation_state_cohort.py','research/audit_tool_relation_states.py','research/measurement_projection.py',
         'research/audit_factorized_relation_dev.py','research/tool_relation_support_study.py',
         'research/tool_relation_adaptation.py','research/ranking_support_initialization.py',
         'research/tool_role_training.py','research/tool_role_policy.py','research/reranker_control.py',
         'research/audit_tool_role_support.py','research/audit_tool_relation_support.py',
         'research/audit_tool_relation_weights.py',
         'specialist/numerical.py','specialist/checkpoint.py']


def dataset(split):
    if split not in ('train','validation'):raise ValueError('Development populations only; no final scoring')
    rows=list(gzip_rows(DATA/f'{split}.jsonl.gz'))
    views=list(gzip_rows(DATA/f'{split}-views.jsonl.gz'))
    return adapt_records(rows,views)


def prepare():
    if (OUT/'protocol.json').exists():
        p=json.loads((OUT/'protocol.json').read_text())
        if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Protocol drift')
        for name,value in p['sources'].items():
            if sha(ROOT/name)!=value or sha(OUT/'sources'/name)!=value:raise ValueError('Executable source drift')
        for name,value in p['data_files'].items():
            if sha(DATA/name)!=value:raise ValueError('Development input drift')
        return p
    upstream=json.loads((BASE/'semantic-next/upstream/artifacts.json').read_text())
    previous=json.loads((BASE/'tool-relation-support-v1/protocol.json').read_text())
    data_audit=audit_data(DATA,recount_tokenizer=False)
    data_protocol=json.loads((DATA/'protocol.json').read_text())
    rows,views=dataset('train');items=training_items(rows,views);units=training_quartets(rows,views)
    counts=[sum(i['class_id']==c for i in items) for c in range(3)]
    torch.set_num_threads(8)
    scalar=PairReranker.from_snapshot(snapshot_path(upstream),upstream,batch_size=16)
    trainability=configure_adaptation(scalar.model,101,last_n=2);del scalar
    names=['protocol.json','coverage.json','audit.json']+[f'{split}{suffix}' for split in ['train','validation'] for suffix in ['.jsonl.gz','-views.jsonl.gz']]
    lengths={r['projected_input_hash']:v['projected_tokens'] for r,v in zip(rows,views) if r['projected_input_hash']}
    item_tokens=sum(lengths[i['input_hash']] for i in items);unit_tokens=sum(lengths[k] for u in units for k in u)
    steps_per_epoch=(len(items)+15)//16+(len(units)+3)//4
    p=dict(schema='varied-balanced-relation-development/0.1',frozen_at_utc=now(),
        model=upstream,source_data_protocol_sha256=data_protocol['sha256'],data_audit=data_audit,
        data_directory='tool-relation-states-v2/supervision-v1',data_files={name:sha(DATA/name) for name in names},
        sources={name:sha(ROOT/name) for name in SOURCES},versions={n:importlib.metadata.version(n) for n in
            ['torch','transformers','tokenizers','numpy','safetensors']},seed=101,epochs=3,device='cpu',dtype='float32',
        threads=8,batch_size=16,quartet_batch_size=4,window=512,trainability=trainability,
        train_unique=len(items),train_class_counts=counts,train_unique_items_sha256=digest(items),
        train_unique_quartets=len(units),train_quartets_sha256=digest(units),
        binary_fraction=(counts[0]+counts[1])/len(items),unknown_fraction=counts[2]/len(items),
        relevance_class_weights=[len(items)/(2*counts[0]),len(items)/(2*counts[1]),0.],
        declared_updates=3*steps_per_epoch,declared_training_pairs=3*(len(items)+4*len(units)),
        declared_training_nonpadding_tokens=3*(item_tokens+unit_tokens),
        optimizer=dict(name='AdamW',classifier_lr=.0001,encoder_tail_lr=.00002,weight_decay=.01,betas=[.9,.999],eps=1e-8),
        objective='Per epoch one unique-item pass: masked relevance BCE globally balanced separately by both deduplicated binary classes plus independent UNKNOWN-logit BCE globally balanced by support class; then one unique quartet pass of mean softplus negative relevance differences along both query and report axes.',
        quartet_slots=['AA','AB','BA','BB'],conditional_loss_coefficient=1.,
        score_axes=dict(relevance='logit1-logit0',unsupported='logit2 (independent binary support logit)',
            auxiliary='Shared inference writer also saves old coupled logsumexp axis in separate -logits.json; no additional forwards'),
        batch_recipe='Sorted unique items/quartets, Random(seed*1000+epoch*10+stageIndex) per stage, classification16pairs, conditional4quartets=16pairs; full partial batches',
        adaptation='Retained scalar prior; classifier and last2 blocks train, embeddings/first10 frozen/eval. Higher classifier LR and factorized+conditional objective change jointly; no causal attribution.',
        evaluation=['validation','train'],calibration='On development validation only, greatest global relevance cutoff preserving .95 positives/contradictions per EN/PT query AND report language; minimum independent-logit semantic UNKNOWN cutoff',
        criteria=previous['criteria'],development_promising='Both exposed train and validation satisfy all existing criteria aggregate and each EN/PT; diagnostic only, no adoption',
        limits='Actual author-created varied states, connected52edges, EN/PTquestions/reports, all18primitive fields and three tools known. No final/source/primitive/production/P2 confirmation. Existing finals excluded from scoring.',
        new_confirmation_required=True,selection_for_adoption=False,API_calls=0,P2_admission=False,default_changed=False,publishing=False)
    p['sha256']=digest(p);OUT.mkdir(parents=True,exist_ok=True)
    for name,value in p['sources'].items():
        target=OUT/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((ROOT/name).read_bytes())
        if sha(target)!=value:raise ValueError('Source changed during freeze')
    save_new(OUT/'protocol.json',p);return p


def evaluate(scorer,split,p,thresholds=None):
    rows,views=dataset(split)
    path=OUT/f'{split}-logits.json'
    auxiliary=score_population(scorer,rows,views,p,path)
    scores=[dict(s,support_score=s['logits'][2] if s['status']=='SCORED' else None) for s in auxiliary['rows']]
    raw=dict(auxiliary,rows=scores,axis='independent support logit2; relevance logit1-logit0',
             auxiliary_logits_file_sha256=sha(path),additional_model_forwards=0)
    save_new(OUT/f'{split}-scores.json',raw)
    if thresholds is None:
        thresholds=calibrate_bilingual(rows,scores)
        save_new(OUT/'thresholds.json',dict(protocol_sha256=p['sha256'],thresholds=thresholds,
            calibration_data='Development validation only, both query/report languages',independent_scope_axis=True,frozen_at_utc=now(),final_inspected=False))
    overall=metrics(rows,scores,thresholds);by_language={}
    for language in ['en','pt']:
        paired=[(r,s) for r,s in zip(rows,scores) if r['goal_language']==language]
        by_language[language]=metrics([r for r,s in paired],[s for r,s in paired],thresholds)
    by_report_language={}
    for language in ['en','pt']:
        paired=[(r,s) for r,s in zip(rows,scores) if r['report_language']==language]
        by_report_language[language]=metrics([r for r,s in paired],[s for r,s in paired],thresholds)
    result=dict(protocol_sha256=p['sha256'],metrics=overall,by_language=by_language,by_report_language=by_report_language,
        passes_point_criteria=passes(overall) and all(passes(m) for m in list(by_language.values())+list(by_report_language.values())),
        development_only=True,adoption=False)
    save_new(OUT/f'{split}-metrics.json',result)
    print(split,'METRICS',json.dumps(result),flush=True)
    return result,thresholds


def run(p):
    if (OUT/'started.json').exists() or WEIGHTS.exists():raise ValueError('No overwrite/selective restart of development study')
    save_new(OUT/'started.json',dict(protocol_sha256=p['sha256'],utc=now(),python=sys.version,platform=platform.platform()))
    torch.set_num_threads(p['threads']);torch.random.default_generator.manual_seed(p['seed'])
    original_connect=socket.socket.connect
    def denied(*args,**kwargs):raise RuntimeError('Network disabled during development training/evaluation')
    socket.socket.connect=denied
    try:
        scorer=PairReranker.from_snapshot(snapshot_path(p['model']),p['model'],batch_size=p['batch_size'])
        recipe=configure_adaptation(scorer.model,p['seed'],last_n=2)
        if recipe!=p['trainability']:raise ValueError('Preflight/trainability drift')
        model=scorer.model;rows,views=dataset('train')
        items=training_items(rows,views);units=training_quartets(rows,views)
        if digest(items)!=p['train_unique_items_sha256'] or digest(units)!=p['train_quartets_sha256']:
            raise ValueError('Changed unique training populations')
        keyed={i['input_hash']:i for i in items}
        lengths={v['view']['projected_input_sha256']:v['projected_tokens'] for v in views if v['view']['status']=='PROJECTED'}
        groups=[dict(params=[v for n,v in model.named_parameters() if v.requires_grad and n.startswith('classifier.')],
                     lr=p['optimizer']['classifier_lr']),
                dict(params=[v for n,v in model.named_parameters() if v.requires_grad and not n.startswith('classifier.')],
                     lr=p['optimizer']['encoder_tail_lr'])]
        optimizer=torch.optim.AdamW(groups,weight_decay=p['optimizer']['weight_decay'],
            betas=tuple(p['optimizer']['betas']),eps=p['optimizer']['eps'])
        history=[]
        with (OUT/'accepted-updates.jsonl').open('x') as updates:
            for epoch in range(1,p['epochs']+1):
                model.train();model.roberta.embeddings.eval()
                for block in model.roberta.encoder.layer[:-2]:block.eval()
                epoch_began=time.perf_counter();stages={}
                for stage_index,stage in enumerate(['classification','conditional']):
                    order=list(items if stage=='classification' else units)
                    random.Random(p['seed']*1000+epoch*10+stage_index).shuffle(order)
                    batch_size=p['batch_size'] if stage=='classification' else p['quartet_batch_size']
                    total_pairs=total_tokens=total_slots=0;losses=[]
                    for start in range(0,len(order),batch_size):
                        selected=order[start:start+batch_size]
                        batch=selected if stage=='classification' else [keyed[k] for unit in selected for k in unit]
                        encoded=scorer.tokenizer([i['objective'] for i in batch],[i['text'] for i in batch],
                            padding=True,truncation=False,return_tensors='pt')
                        tokens,slots=numeric_batch(encoded,[lengths[i['input_hash']] for i in batch],scorer.window)
                        logits=model(**encoded).logits
                        loss=(balanced_loss(batch,logits,p['train_class_counts']) if stage=='classification'
                              else conditional_loss(logits.reshape(len(selected),4,3))*p['conditional_loss_coefficient'])
                        finite_update(loss,model,optimizer);value=float(loss.detach())
                        total_pairs+=len(batch);total_tokens+=tokens;total_slots+=slots;losses.append((value,len(selected)))
                        updates.write(json.dumps(dict(protocol_sha256=p['sha256'],epoch=epoch,stage=stage,step=len(losses),
                            input_hashes=[i['input_hash'] for i in batch],quartets=selected if stage=='conditional' else None,
                            pairs=len(batch),units=len(selected),loss=value,nonpadding_tokens=tokens,
                            padded_slots=slots,finite_update_accepted=True),allow_nan=False)+'\n');updates.flush()
                        if len(losses)%100==0:print('epoch',epoch,stage,'step',len(losses),'loss',round(value,5),flush=True)
                    stages[stage]=dict(steps=len(losses),units=len(order),pairs=total_pairs,nonpadding_tokens=total_tokens,
                        padded_slots=total_slots,weighted_mean_loss=sum(v*n for v,n in losses)/len(order))
                frozen=frozen_parameter_sha256(model)
                if frozen!=p['trainability']['frozen_parameter_sha256']:raise ValueError('Frozen encoder drift')
                receipt=dict(protocol_sha256=p['sha256'],epoch=epoch,stages=stages,all_updates_finite=True,
                    frozen_parameter_sha256=frozen,seconds=time.perf_counter()-epoch_began,finished_at_utc=now())
                save_new(OUT/f'epoch-{epoch}.json',receipt);history.append(receipt)
                print('EPOCH',json.dumps(receipt),flush=True)
        WEIGHTS.parent.mkdir(parents=True,exist_ok=True)
        save_file({n:v.detach().contiguous() for n,v in model.state_dict().items()},str(WEIGHTS))
        save_new(OUT/'training_meta.json',dict(protocol_sha256=p['sha256'],seed=p['seed'],epochs_completed=len(history),
            history=history,trainability=recipe,weights_path=str(WEIGHTS.relative_to(ROOT)),weights_sha256=sha(WEIGHTS),
            metadata_origin='Direct accepted-update and completed finite epoch receipts; no terminal reconstruction',
            frozen_before_evaluation_at_utc=now(),final_inspected=False,development_only=True,adoption=False))
        validation,thresholds=evaluate(scorer,'validation',p)
        train,unused=evaluate(scorer,'train',p,thresholds)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        summary=dict(protocol_sha256=p['sha256'],development_promising=train['passes_point_criteria'] and validation['passes_point_criteria'],
            train_metrics=train,validation_metrics=validation,final_evaluated=False,new_confirmation_required=True,
            peak_study_process_rss_bytes=peak if sys.platform=='darwin' else peak*1024,
            API_calls=0,P2_admission=False,default_changed=False,adoption=False,finished_at_utc=now())
        save_new(OUT/'summary.json',summary);return summary
    except Exception as exc:
        save_new(OUT/'failure.json',dict(protocol_sha256=p['sha256'],error_type=type(exc).__name__,error=str(exc),
            study_complete=False,selective_retry_allowed=False,utc=now()))
        raise
    finally:socket.socket.connect=original_connect


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    args=parser.parse_args();protocol=prepare()
    print(json.dumps(run(protocol) if args.action=='run' else dict(protocol_sha256=protocol['sha256'],
        unique_items=protocol['train_unique'],unique_quartets=protocol['train_unique_quartets']),indent=2))
