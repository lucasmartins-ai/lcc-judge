"""Stdlib-only rederivation of varied balanced conditional development receipts.

No training/scoring/policy imports, model calls or threshold refitting for use.
Optional private weights are checked against the immutable base and frozen bytes.
Audit PASS validates receipts only; development quality cannot approve adoption.
"""

import argparse
from collections import Counter,defaultdict
from bisect import bisect_left
import gzip
from datetime import datetime
import json
import math
from pathlib import Path
import random

from research.audit_tool_role_support import audited_scores,close,digest,reduce_metrics,gate
from research.audit_tool_relation_state_supervision import audit as audit_data
from research.audit_tool_relation_support import normalized_semantic_rows
from research.audit_tool_relation_weights import sha,header,frozen_hash,POSITION_BUFFER

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/varied-relation-dev-v1'


def check_independent_axes(auxiliary,raw,auxiliary_sha):
    assert raw['axis']=='independent support logit2; relevance logit1-logit0'
    assert raw['auxiliary_logits_file_sha256']==auxiliary_sha and raw['additional_model_forwards']==0
    expected_keys=set(auxiliary)|{'axis','auxiliary_logits_file_sha256','additional_model_forwards'}
    assert set(raw)==expected_keys and len(raw['rows'])==len(auxiliary['rows'])
    for name in set(auxiliary)-{'rows'}:close(raw[name],auxiliary[name])
    for left,right in zip(raw['rows'],auxiliary['rows']):
        assert set(left)==set(right)
        for name in set(right)-{'support_score'}:close(left[name],right[name])
        support=right['logits'][2] if right['status']=='SCORED' else None
        assert left['support_score']==support
    return True


def reconstruct_training(rows,views):
    assert len(rows)==len(views) and all(r['split']=='train' and r['id']==v['id'] for r,v in zip(rows,views))
    unique={};matrices=defaultdict(dict);counts=Counter()
    for row,saved in zip(rows,views):
        view=saved['view']
        if view['status']!='PROJECTED':
            assert row['label'] is None and row['unknown_kind']=='unbound_record'
            continue
        key=row['projected_input_hash'];assert key==view['projected_input_sha256']
        assert digest([view['objective'],view['text']])==key
        label=2 if row['label'] is None else row['label']
        if key not in unique:
            unique[key]=dict(input_hash=key,objective=view['objective'],text=view['text'],class_id=label,receipt_ids=[])
        else:assert (unique[key]['class_id'],unique[key]['objective'],unique[key]['text'])==(label,view['objective'],view['text'])
        unique[key]['receipt_ids'].append(row['id'])
        if row['label'] is not None:
            assert type(row['label']) is int and row['label']==int(row['requested_role']==row['observed_role'])
            group=(row['group'],row['report_variant']);slot=(row['requested_role'],row['observed_role'])
            assert slot not in matrices[group];matrices[group][slot]=key
    units=set()
    for matrix in matrices.values():
        roles=sorted({a for a,b in matrix})
        assert len(roles)==2 and set(matrix)=={(a,b) for a in roles for b in roles}
        units.add(tuple(matrix[(a,b)] for a in roles for b in roles))
    items=[unique[k] for k in sorted(unique)]
    counts.update(item['class_id'] for item in items)
    return items,[list(unit) for unit in sorted(units)],[counts[i] for i in range(3)]


def read_population(data,split):
    def load(path):
        with gzip.open(path,'rt',encoding='utf-8') as stream:return [json.loads(line) for line in stream]
    rows=load(data/f'{split}.jsonl.gz');views=load(data/f'{split}-views.jsonl.gz')
    assert len(rows)==len(views)
    for row,saved in zip(rows,views):
        assert row['split']==split and row['id']==saved['id']
        view=saved['view']
        if view['status']=='PROJECTED':
            key=digest([view['objective'],view['text']]);assert key==row['projected_input_hash']
            view['projected_input_sha256']=key
        row['report_id']=digest([row['group'],row['observed_role'],row['report_variant']]) if row['label'] is not None else row['id']
    return rows,views


def bilingual_thresholds(rows,scores):
    binary=[(r,s) for r,s in zip(rows,scores) if r['label'] is not None]
    semantic=[s for r,s in zip(rows,scores) if r['label'] is None and r['unknown_kind']!='unbound_record']
    support=min(s['support_score'] for s in semantic)
    candidates={s['score'] for r,s in binary}
    candidates|={math.nextafter(min(candidates),-math.inf),math.nextafter(max(candidates),math.inf)}
    constraints=[]
    for field in ['goal_language','report_language']:
        for lang in ['en','pt']:
            for only_contradictions in [False,True]:
                group=[s for r,s in binary if r['label']==1 and r[field]==lang and (not only_contradictions or r['fact_truth'] is False)]
                assert group
                eligible=sorted(s['score'] for s in group if s['support_score']<support)
                constraints.append((len(group),eligible))
    # Independently inspect the complete candidate set with strict DROP semantics.
    accepted=[v for v in candidates if all((n-bisect_left(values,v))/n>=.95 for n,values in constraints)]
    return dict(support=support,relevance=max(accepted),validation_semantic_unknown_recall=1.0,
        recipe='minimum semantic-UNKNOWN independent logit; greatest global relevance cutoff preserving .95 positive/contradiction retention in each EN/PT query and report language, strict DROP below cutoff')


def pinned_data_path(out,protocol,override=None):
    data=out.parent/protocol['data_directory'] if override is None else Path(override)
    for name,value in protocol['data_files'].items():assert sha(data/name)==value
    return data


def audit(out=OUT,verify_weights=False,data_override=None):
    p=json.loads((out/'protocol.json').read_text());assert digest({k:v for k,v in p.items() if k!='sha256'})==p['sha256']
    assert p['seed'] in (101,202,303) and type(p['seed']) is int
    if p['seed']!=101:
        design=json.loads((out.parent/'design-v2/protocol.json').read_text())
        original=json.loads((out.parent.parent/'varied-relation-dev-v2/protocol.json').read_text())
        assert p['schema']=='varied-balanced-relation-independent-replication/0.1'
        assert p['confirmation_design_sha256']==design['sha256'] and p['seed'] in design['candidate_seeds']
        assert p['independent_replication_of']['protocol_sha256']==original['sha256']
        assert p['source_data_protocol_sha256']==original['source_data_protocol_sha256']
        for key in ('model','data_files','epochs','batch_size','quartet_batch_size','optimizer','objective',
                    'conditional_loss_coefficient','criteria','train_unique_items_sha256','train_quartets_sha256',
                    'declared_updates','declared_training_pairs','declared_training_nonpadding_tokens'):
            assert p[key]==original[key]
    assert p['epochs']==3 and p['batch_size']==16 and p['quartet_batch_size']==4
    assert p['conditional_loss_coefficient']==1. and p['evaluation']==['validation','train']
    assert p['selection_for_adoption'] is False and p['new_confirmation_required'] is True
    for name,value in p['sources'].items():assert sha(out/'sources'/name)==value
    data=pinned_data_path(out,p,data_override)
    original_data=json.loads((data/'protocol.json').read_text());assert original_data['sha256']==p['source_data_protocol_sha256']
    close(p['data_audit'],audit_data(data,recount_tokenizer=False))
    populations={split:read_population(data,split) for split in ['train','validation']}
    rows,views=populations['train'];items,units,counts=reconstruct_training(rows,views)
    assert len(items)==p['train_unique'] and digest(items)==p['train_unique_items_sha256']
    assert len(units)==p['train_unique_quartets'] and digest(units)==p['train_quartets_sha256']
    assert counts==p['train_class_counts']
    close(p['relevance_class_weights'],[len(items)/(2*counts[0]),len(items)/(2*counts[1]),0.])
    close(p['binary_fraction'],(counts[0]+counts[1])/len(items));close(p['unknown_fraction'],counts[2]/len(items))
    lengths={r['projected_input_hash']:v['projected_tokens'] for r,v in zip(rows,views) if r['projected_input_hash'] is not None}
    steps=[json.loads(x) for x in (out/'accepted-updates.jsonl').read_text().splitlines()]
    meta=json.loads((out/'training_meta.json').read_text());started=json.loads((out/'started.json').read_text())
    assert meta['protocol_sha256']==started['protocol_sha256']==p['sha256'] and meta['epochs_completed']==p['epochs']
    assert meta['final_inspected'] is meta['adoption'] is False and meta['development_only'] is True
    assert meta['trainability']==p['trainability']
    assert datetime.fromisoformat(p['frozen_at_utc'])<=datetime.fromisoformat(started['utc'])
    cursor=total_steps=total_pairs=total_tokens=0
    for epoch in range(1,p['epochs']+1):
        stored=json.loads((out/f'epoch-{epoch}.json').read_text());assert stored==meta['history'][epoch-1]
        assert stored['epoch']==epoch and stored['all_updates_finite'] is True and stored['protocol_sha256']==p['sha256']
        assert stored['frozen_parameter_sha256']==p['trainability']['frozen_parameter_sha256'] and stored['seconds']>0
        assert datetime.fromisoformat(started['utc'])<=datetime.fromisoformat(stored['finished_at_utc'])<=datetime.fromisoformat(meta['frozen_before_evaluation_at_utc'])
        for stage_index,stage in enumerate(['classification','conditional']):
            order=list(items if stage=='classification' else units)
            random.Random(p['seed']*1000+epoch*10+stage_index).shuffle(order)
            batch_size=p['batch_size'] if stage=='classification' else p['quartet_batch_size']
            losses=[];pair_count=token_count=slot_count=0
            for start in range(0,len(order),batch_size):
                selected=order[start:start+batch_size];step=steps[cursor];cursor+=1
                hashes=[i['input_hash'] for i in selected] if stage=='classification' else [k for unit in selected for k in unit]
                assert step['protocol_sha256']==p['sha256'] and step['epoch']==epoch and step['stage']==stage
                assert step['step']==len(losses)+1 and step['finite_update_accepted'] is True
                assert step['input_hashes']==hashes and step['pairs']==len(hashes) and step['units']==len(selected)
                assert step['quartets']==(None if stage=='classification' else selected)
                tokens=sum(lengths[k] for k in hashes);slots=max(lengths[k] for k in hashes)*len(hashes)
                assert step['nonpadding_tokens']==tokens and step['padded_slots']==slots
                assert type(step['loss']) is float and math.isfinite(step['loss']) and step['loss']>=0
                pair_count+=len(hashes);token_count+=tokens;slot_count+=slots;losses.append((step['loss'],len(selected)))
            stage_receipt=dict(steps=len(losses),units=len(order),pairs=pair_count,nonpadding_tokens=token_count,
                padded_slots=slot_count,weighted_mean_loss=sum(v*n for v,n in losses)/len(order))
            close(stored['stages'][stage],stage_receipt)
            total_steps+=len(losses);total_pairs+=pair_count;total_tokens+=token_count
    assert cursor==len(steps)
    assert total_steps==p['declared_updates'] and total_pairs==p['declared_training_pairs'] and total_tokens==p['declared_training_nonpadding_tokens']
    outcomes={};thresholds=json.loads((out/'thresholds.json').read_text())
    assert thresholds['protocol_sha256']==p['sha256'] and thresholds['final_inspected'] is False
    eval_pairs=eval_tokens=0
    for split in ['validation','train']:
        rows,views=populations[split]
        auxiliary=audited_scores(out/f'{split}-logits.json',rows,views,p,False)
        assert auxiliary['complete'] is True and auxiliary['error'] is None
        raw=json.loads((out/f'{split}-scores.json').read_text())
        check_independent_axes(auxiliary,raw,sha(out/f'{split}-logits.json'))
        normalized=normalized_semantic_rows(rows)
        if split=='validation':close(thresholds['thresholds'],bilingual_thresholds(normalized,raw['rows']))
        reduced=reduce_metrics(normalized,raw['rows'],thresholds['thresholds'])
        languages={}
        for language in ['en','pt']:
            selected=[(r,s) for r,s in zip(normalized,raw['rows']) if r['goal_language']==language]
            languages[language]=reduce_metrics([r for r,s in selected],[s for r,s in selected],thresholds['thresholds'])
        report_languages={}
        for language in ['en','pt']:
            selected=[(r,s) for r,s in zip(normalized,raw['rows']) if r['report_language']==language]
            report_languages[language]=reduce_metrics([r for r,s in selected],[s for r,s in selected],thresholds['thresholds'])
        outcome=dict(protocol_sha256=p['sha256'],metrics=reduced,by_language=languages,
            by_report_language=report_languages,
            passes_point_criteria=gate(reduced,p['criteria']) and all(gate(m,p['criteria']) for m in list(languages.values())+list(report_languages.values())),
            development_only=True,adoption=False)
        close(json.loads((out/f'{split}-metrics.json').read_text()),outcome);outcomes[split]=outcome
        eval_pairs+=raw['accounting']['valid_score_pairs'];eval_tokens+=raw['accounting']['valid_score_tokens']
    meta_time=datetime.fromisoformat(meta['frozen_before_evaluation_at_utc'])
    val_time=datetime.fromisoformat(json.loads((out/'validation-logits.json').read_text())['finished_at_utc'])
    train_time=datetime.fromisoformat(json.loads((out/'train-logits.json').read_text())['finished_at_utc'])
    assert meta_time<=val_time<=datetime.fromisoformat(thresholds['frozen_at_utc'])<=train_time
    summary=json.loads((out/'summary.json').read_text())
    assert summary['final_evaluated'] is summary['adoption'] is summary['default_changed'] is summary['P2_admission'] is False
    assert summary['API_calls']==0 and summary['new_confirmation_required'] is True
    close(summary['train_metrics'],outcomes['train']);close(summary['validation_metrics'],outcomes['validation'])
    assert summary['development_promising']==all(m['passes_point_criteria'] for m in outcomes.values())
    if verify_weights:
        recipe=p['trainability'];candidate=ROOT/meta['weights_path']
        base=Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/p['model']['revision']/'model.safetensors'
        assert sha(base)==p['model']['files']['model.safetensors'] and sha(candidate)==meta['weights_sha256']
        assert frozen_hash(candidate,recipe['frozen_names'])==frozen_hash(base,recipe['frozen_names'])==recipe['frozen_parameter_sha256']
        tensors,unused=header(candidate);parameters={n:s for n,s in tensors.items() if n!=POSITION_BUFFER}
        assert set(parameters)==set(recipe['trainable_names'])|set(recipe['frozen_names'])
        assert sum(math.prod(s['shape']) for s in parameters.values())==recipe['total_parameters']
    return dict(status='PASS',protocol_sha256=p['sha256'],private_weights_verified=verify_weights,
        accepted_updates=total_steps,training_pair_presentations=total_pairs,training_nonpadding_tokens=total_tokens,
        valid_evaluation_forwards=eval_pairs,valid_evaluation_nonpadding_tokens=eval_tokens,
        development_promising=summary['development_promising'],final_evaluated=False,adoption=False,
        model_forwards_by_audit=0,scope='Known-field author-created varied-state train/validation development; independent-axis/input/step/math/global-balance/calibration/epoch/weight receipts. Not fresh confirmation, loss-gradient replay, production or LCC utility certification.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--verify-weights',action='store_true');args=parser.parse_args()
    print(json.dumps(audit(args.out,args.verify_weights),indent=2))
