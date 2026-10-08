"""Independent stdlib recount of retained-ranking support study receipts.

No trainer, policy or model imports. Reuses independent raw/math primitives from
the historical support auditor, normalizing annotation kinds only for reduction.
Optional private-weight checks parse safetensors without loading tensors/models.
"""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import mmap
from pathlib import Path
import random
import statistics

from research.audit_tool_relation_supervision import audit as audit_data
from research.audit_tool_role_support import audited_scores,close,digest,gate,reduce_metrics,thresholds_from_validation

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/tool-relation-support-v1'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def normalized_semantic_rows(rows):
    # Annotation adaptation for the older independent reducer only. Neither
    # producer inputs nor original stored rows/labels/hashes are rewritten.
    normalized=[]
    for row in rows:
        if row['label'] is None:
            kind=row['unknown_kind']
            assert isinstance(kind,str) and kind.strip()
            if kind!='unbound_record':
                row={**row,'unknown_kind':'unsupported_goal'}
        normalized.append(row)
    return normalized


def tensor_header(path):
    with path.open('rb') as stream:
        size=int.from_bytes(stream.read(8),'little')
        assert 0<size<1024*1024
        tensors=json.loads(stream.read(size))
    length=path.stat().st_size-8-size
    assert length>0
    tensors={name:spec for name,spec in tensors.items() if name!='__metadata__'}
    intervals=[]
    for spec in tensors.values():
        assert spec['dtype']=='F32'
        assert all(type(n) is int and n>0 for n in spec['shape'])
        start,end=spec['data_offsets']
        assert type(start) is int and type(end) is int and 0<=start<end<=length
        assert end-start==math.prod(spec['shape'])*4
        intervals.append((start,end))
    intervals.sort()
    assert intervals[0][0]==0 and intervals[-1][1]==length
    assert all(a[1]==b[0] for a,b in zip(intervals,intervals[1:]))
    return tensors,8+size


def frozen_hash(path,names):
    tensors,prefix=tensor_header(path)
    assert len(names)==len(set(names)) and set(names)<=set(tensors)
    digest_value=hashlib.sha256()
    with path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as mapped:
        with memoryview(mapped) as buffer:
            for name in sorted(names):
                spec=tensors[name]
                metadata=dict(name=name,shape=spec['shape'],dtype='torch.float32')
                digest_value.update(json.dumps(metadata,sort_keys=True).encode()+b'\0')
                start,end=spec['data_offsets']
                digest_value.update(buffer[prefix+start:prefix+end])
    return digest_value.hexdigest()


def _utc(text):
    return datetime.fromisoformat(text)


def audit(out=OUT,verify_weights=False):
    protocol=json.loads((out/'protocol.json').read_text())
    assert protocol['sha256']==digest({k:v for k,v in protocol.items() if k!='sha256'})
    assert protocol['seeds']==[101,202,303] and protocol['epochs']==3
    assert protocol['device']=='cpu' and protocol['dtype']=='float32' and protocol['window']==512
    for name,expected in protocol['sources'].items():assert sha(out/'executed-source'/name)==expected
    data=out.parent/protocol['data_directory']
    for name,expected in protocol['data_files'].items():assert sha(data/name)==expected
    assert audit_data(data)['protocol_sha256']==protocol['data_protocol_sha256']
    datasets={}
    for split in ['train','validation','final']:
        rows=[json.loads(line) for line in (data/f'{split}.jsonl').read_text().splitlines()]
        views=[json.loads(line) for line in (data/f'{split}-views.jsonl').read_text().splitlines()]
        datasets[split]=(rows,views)
    unique={}
    for row,saved in zip(*datasets['train']):
        if saved['view']['status']!='PROJECTED':
            assert row['label'] is None and row['unknown_kind']=='unbound_record';continue
        key=row['projected_input_hash'];label=2 if row['label'] is None else row['label']
        item=dict(input_hash=key,objective=saved['view']['objective'],text=saved['view']['text'],class_id=label,receipt_ids=[])
        if key not in unique:unique[key]=item
        assert unique[key]['class_id']==label
        assert unique[key]['objective']==item['objective'] and unique[key]['text']==item['text']
        unique[key]['receipt_ids'].append(row['id'])
    items=[unique[key] for key in sorted(unique)]
    assert digest(items)==protocol['train_unique_items_sha256'] and len(items)==protocol['train_unique']==3592
    counts=Counter(item['class_id'] for item in items)
    assert [counts[i] for i in range(3)]==protocol['train_class_counts']==[1724,1724,144]
    close(protocol['global_class_weights'],[len(items)/(3*counts[i]) for i in range(3)])
    lengths={row['projected_input_hash']:saved['projected_tokens'] for row,saved in zip(*datasets['train']) if row['projected_input_hash'] is not None}
    expected_tokens=sum(lengths[item['input_hash']] for item in items)
    recipe=protocol['trainability'];assert recipe['last_n']==2 and recipe['encoder_blocks']==12
    assert recipe['total_parameters']==117641859
    assert recipe['total_parameters']==recipe['frozen_parameters']+recipe['trainable_parameters']
    assert recipe['trainable_parameters']>0 and recipe['frozen_parameters']>recipe['trainable_parameters']
    assert not set(recipe['trainable_names'])&set(recipe['frozen_names'])
    assert all(name.startswith(('roberta.encoder.layer.10.','roberta.encoder.layer.11.','classifier.')) for name in recipe['trainable_names'])
    assert not any(name.startswith(('roberta.encoder.layer.10.','roberta.encoder.layer.11.','classifier.')) for name in recipe['frozen_names'])
    if verify_weights:
        original=Path.home()/'.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1/snapshots'/protocol['model']['revision']/'model.safetensors'
        assert sha(original)==protocol['model']['files']['model.safetensors']
        assert frozen_hash(original,recipe['frozen_names'])==recipe['frozen_parameter_sha256']
    started=json.loads((out/'started.json').read_text());selection=json.loads((out/'selection.json').read_text())
    assert started['protocol_sha256']==selection['protocol_sha256']==protocol['sha256']
    assert selection['final_inspected'] is False and selection['seeds']==protocol['seeds']
    assert _utc(protocol['frozen_at_utc'])<=_utc(started['utc'])<=_utc(selection['frozen_at_utc'])
    totals=dict(steps=0,training_pairs=0,training_tokens=0,scored_pairs=0,scored_tokens=0)
    finals=[];initial_heads=[]
    for candidate in ['frozen']+[f'seed-{s}' for s in protocol['seeds']]:
        directory=out/candidate;scalar=candidate=='frozen';meta=None;thresholds=dict(support=None,relevance=None)
        if not scalar:
            seed=int(candidate.removeprefix('seed-'))
            meta=json.loads((directory/'training_meta.json').read_text())
            began=json.loads((directory/'started.json').read_text())
            assert meta['protocol_sha256']==began['protocol_sha256']==protocol['sha256'] and meta['seed']==began['seed']==seed
            assert meta['epochs_completed']==3 and len(meta['history'])==3 and meta['final_inspected'] is False
            assert meta['identity']==began['initial_identity']
            assert meta['identity']['model_sha256']==protocol['model']['files']['model.safetensors']
            assert meta['identity']['output_classes']==3 and meta['identity']['adapted_parameters']==recipe['total_parameters']
            assert meta['identity']['trainable_parameters']==recipe['trainable_parameters']
            actual=meta['trainability'];assert actual==began['trainability']
            for name in ['total_parameters','trainable_parameters','frozen_parameters','trainable_names','frozen_names','frozen_parameter_sha256']:
                assert actual[name]==recipe[name]
            init=actual['initialization'];assert init['seed']==seed and init['encoder_and_intermediate_dense_preserved'] is True
            assert init['original_output_head_sha256']==recipe['initialization']['original_output_head_sha256']
            assert init==meta['identity']['initialization'] and init['classes']==['IRRELEVANT','RELEVANT','UNKNOWN']
            initial_heads.append(init['initial_output_head_sha256'])
            assert selection['weights_sha256'][str(seed)]==meta['weights_sha256']
            saved=json.loads((directory/'thresholds.json').read_text())
            assert saved==selection['calibration'][str(seed)] and saved['final_inspected'] is False
            assert _utc(saved['frozen_at_utc'])<=_utc(selection['frozen_at_utc'])
            thresholds=saved['thresholds']
            updates=[json.loads(line) for line in (directory/'accepted-updates.jsonl').read_text().splitlines()]
            assert len(updates)==3*math.ceil(len(items)/protocol['batch_size'])
            for epoch,history in enumerate(meta['history'],1):
                receipt=json.loads((directory/f'epoch-{epoch}.json').read_text());assert receipt==history
                assert receipt['protocol_sha256']==protocol['sha256'] and receipt['epoch']==epoch and receipt['seed']==seed
                assert receipt['all_updates_finite'] is True and receipt['frozen_parameter_sha256']==recipe['frozen_parameter_sha256']
                assert receipt['unique_pairs']==len(items) and receipt['submitted_nonpadding_tokens']==expected_tokens
                assert receipt['steps']==math.ceil(len(items)/protocol['batch_size'])
                assert receipt['seconds']>0 and _utc(receipt['finished_at_utc'])<=_utc(selection['frozen_at_utc'])
                order=list(items);random.Random(seed*100+epoch).shuffle(order)
                part=[update for update in updates if update['epoch']==epoch]
                assert len(part)==receipt['steps'];tokens=slots=0;loss=0.;pairs=0
                for step,update in enumerate(part,1):
                    batch=order[(step-1)*protocol['batch_size']:step*protocol['batch_size']]
                    hashes=[item['input_hash'] for item in batch]
                    assert update['protocol_sha256']==protocol['sha256'] and update['seed']==seed and update['step']==step
                    assert update['finite_update_accepted'] is True and update['pair_hashes']==hashes and update['pairs']==len(batch)
                    assert math.isfinite(update['loss']) and update['loss']>=0
                    assert update['nonpadding_tokens']==sum(lengths[key] for key in hashes)
                    assert update['padded_slots']==len(batch)*max(lengths[key] for key in hashes)
                    tokens+=update['nonpadding_tokens'];slots+=update['padded_slots'];loss+=update['loss']*len(batch);pairs+=len(batch)
                assert pairs==len(items) and tokens==expected_tokens and slots==receipt['padded_token_slots']
                close(receipt['weighted_mean_loss'],loss/pairs)
                totals['steps']+=receipt['steps'];totals['training_pairs']+=pairs;totals['training_tokens']+=tokens
            if verify_weights:
                path=ROOT/meta['weights_path'];assert sha(path)==meta['weights_sha256']
                assert frozen_hash(path,recipe['frozen_names'])==recipe['frozen_parameter_sha256']
                tensors,unused=tensor_header(path)
                assert sum(math.prod(s['shape']) for s in tensors.values())==recipe['total_parameters']
                assert set(tensors)==set(recipe['frozen_names'])|set(recipe['trainable_names'])
                assert tensors['classifier.out_proj.weight']['shape']==[3,384]
        for split in ['validation','final']:
            rows,views=datasets[split];normalized=normalized_semantic_rows(rows)
            raw=audited_scores(directory/f'{split}-scores.json',rows,views,protocol,scalar)
            assert raw['complete'] is True and raw['error'] is None and raw['elapsed_s']>0
            if split=='validation' and not scalar:
                close(thresholds,thresholds_from_validation(normalized,raw['rows']))
                assert _utc(raw['finished_at_utc'])<=_utc(selection['frozen_at_utc'])
            if split=='final':assert _utc(selection['frozen_at_utc'])<=_utc(raw['finished_at_utc'])
            result=reduce_metrics(normalized,raw['rows'],thresholds,scalar)
            stored=json.loads((directory/f'{split}-metrics.json').read_text())
            assert stored['protocol_sha256']==protocol['sha256'] and stored['scalar_control'] is scalar
            close(stored['thresholds'],thresholds);close(stored['metrics'],result)
            language_metrics={}
            for column,values in [('by_language',['en','pt']),
                ('by_binary_source',sorted({r['binding']['source'] for r in rows if r['label'] is not None})),
                ('by_family',sorted({r['family'] for r in rows if r['label'] is not None}))]:
                recomputed={}
                for value in values:
                    field='goal_language' if column=='by_language' else ('family' if column=='by_family' else None)
                    paired=[(r,s) for r,s in zip(normalized,raw['rows']) if
                        (r[field]==value if field else r['binding']['source']==value and r['label'] is not None)]
                    recomputed[value]=reduce_metrics([r for r,s in paired],[s for r,s in paired],thresholds,scalar)
                close(stored[column],recomputed)
                if column=='by_language':language_metrics=recomputed
            passed=gate(result,protocol['criteria']) and all(gate(value,protocol['criteria']) for value in language_metrics.values())
            assert stored['passed']==passed
            assert result['semantic_unknown']==(72 if split=='validation' else 144)
            assert result['structural_unknown']==(24 if split=='validation' else 48)
            if split=='final' and not scalar:finals.append(stored)
            if split=='validation' and meta:assert meta['validation_pass']==passed
            totals['scored_pairs']+=raw['accounting']['valid_score_pairs'];totals['scored_tokens']+=raw['accounting']['valid_score_tokens']
    assert len(set(initial_heads))==3
    summary=json.loads((out/'summary.json').read_text())
    assert summary['protocol_sha256']==protocol['sha256']
    assert summary['seed_passes']==[value['passed'] for value in finals]
    assert summary['all_seeds_pass']==all(value['passed'] for value in finals)
    close(summary['mean'],{key:statistics.mean(value['metrics'][key] for value in finals) for key in summary['mean']})
    assert summary['unknown_drops']==[value['metrics']['unknown_drops'] for value in finals]
    close(summary['frozen_final'],json.loads((out/'frozen/final-metrics.json').read_text())['metrics'])
    assert summary['API_calls']==0 and summary['P2_admission'] is summary['default_changed'] is summary['adoption'] is False
    return dict(status='PASS',protocol_sha256=protocol['sha256'],finite_epoch_receipts=9,
        accepted_update_steps=totals['steps'],training_pair_presentations=totals['training_pairs'],training_nonpadding_tokens=totals['training_tokens'],
        scored_pairs=totals['scored_pairs'],scored_nonpadding_tokens=totals['scored_tokens'],
        total_parameters=recipe['total_parameters'],trainable_parameters=recipe['trainable_parameters'],
        private_weight_hashes_verified=verify_weights,frozen_parameters_independently_verified=verify_weights,
        seed_passes=summary['seed_passes'],all_seeds_pass=summary['all_seeds_pass'],mean_final=summary['mean'],unknown_drops=summary['unknown_drops'],
        model_forwards_during_audit=0,API_calls=0,P2_admission=False,training_reexecuted=False,
        scope='Recorded direct-record data/source/epoch/selection/raw/math audit; known primitive fields/tools, authored fixture/wording transfer, not human-reviewed production/P2 or LCC replacement proof')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--verify-weights',action='store_true');args=parser.parse_args()
    print(json.dumps(audit(args.out,args.verify_weights),indent=2))
