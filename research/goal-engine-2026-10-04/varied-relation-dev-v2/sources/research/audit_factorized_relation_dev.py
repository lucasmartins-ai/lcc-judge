"""Stdlib-only rederivation of exposed factorized development receipts.

No training/scoring/policy imports, model calls or threshold refitting for use.
Optional private weights are checked against the immutable base and frozen bytes.
Audit PASS validates receipts only; development quality cannot approve adoption.
"""

import argparse
from collections import Counter,defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import random

from research.audit_tool_role_support import audited_scores,close,digest,reduce_metrics,thresholds_from_validation,gate
from research.audit_tool_relation_support import normalized_semantic_rows
from research.audit_tool_relation_weights import sha,header,frozen_hash,POSITION_BUFFER

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/factorized-relation-dev-v1'


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


def audit(out=OUT,verify_weights=False):
    p=json.loads((out/'protocol.json').read_text());assert digest({k:v for k,v in p.items() if k!='sha256'})==p['sha256']
    assert p['seed']==101 and p['epochs']==3 and p['batch_size']==16 and p['quartet_batch_size']==4
    assert p['conditional_loss_coefficient']==1. and p['evaluation']==['validation','train']
    assert p['selection_for_adoption'] is False and p['new_confirmation_required'] is True
    for name,value in p['sources'].items():assert sha(out/'sources'/name)==value
    data=out.parent/p['data_directory']
    for name,value in p['data_files'].items():assert sha(data/name)==value
    original_data=json.loads((data/'protocol.json').read_text());assert original_data['sha256']==p['source_data_protocol_sha256']
    populations={split:([json.loads(x) for x in (data/f'{split}.jsonl').read_text().splitlines()],
        [json.loads(x) for x in (data/f'{split}-views.jsonl').read_text().splitlines()]) for split in ['train','validation']}
    rows,views=populations['train'];items,units,counts=reconstruct_training(rows,views)
    assert len(items)==p['train_unique'] and digest(items)==p['train_unique_items_sha256']
    assert len(units)==p['train_unique_quartets'] and digest(units)==p['train_quartets_sha256']
    assert counts==p['train_class_counts']
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
        if split=='validation':close(thresholds['thresholds'],thresholds_from_validation(normalized,raw['rows']))
        reduced=reduce_metrics(normalized,raw['rows'],thresholds['thresholds'])
        languages={}
        for language in ['en','pt']:
            selected=[(r,s) for r,s in zip(normalized,raw['rows']) if r['goal_language']==language]
            languages[language]=reduce_metrics([r for r,s in selected],[s for r,s in selected],thresholds['thresholds'])
        outcome=dict(protocol_sha256=p['sha256'],metrics=reduced,by_language=languages,
            passes_point_criteria=gate(reduced,p['criteria']) and all(gate(m,p['criteria']) for m in languages.values()),
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
        model_forwards_by_audit=0,scope='Exposed original train/validation only; independent-axis math, source/data/input/step/calibration/epoch receipts. Not fresh confirmation, loss-gradient replay, production or LCC utility certification.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--verify-weights',action='store_true');args=parser.parse_args()
    print(json.dumps(audit(args.out,args.verify_weights),indent=2))
