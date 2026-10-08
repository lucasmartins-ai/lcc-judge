"""Independent compact-relation audit from archived annotations and raw receipts."""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics

from research.audit_reranker_diagnostic import digest, sha, reduce
from research.audit_reranker_projection import equal

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT/'research/goal-engine-2026-10-04/compact-relation-v1'


def literal(path, name):
    return next(ast.literal_eval(n.value) for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def audit(out, prepare_only=False, verify_weights=False):
    protocol = json.loads((out/'protocol.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='sha256'}) == protocol['sha256']
    for name, expected in protocol['sources'].items():
        assert sha(out/'executed-source'/name) == expected
    banks = literal(out/'executed-source/research/semantic_corpus.py','FAMILIES')
    reserved = literal(out/'executed-source/research/compact_relation_corpus.py','RESERVED_FAMILIES')
    assert len(banks) == 18 and len(reserved) == 8 and not set(banks)&set(reserved)
    data, views, entities, hashes, projected = {}, {}, {}, {}, {}
    for split, meta in protocol['data'].items():
        assert sha(out/f'{split}.jsonl') == meta['sha256']
        assert sha(out/f'{split}-views.jsonl') == meta['views_sha256']
        records = [json.loads(line) for line in (out/f'{split}.jsonl').read_text().splitlines()]
        saved_views = [json.loads(line) for line in (out/f'{split}-views.jsonl').read_text().splitlines()]
        assert len(records) == len(saved_views) == len({r['id'] for r in records}) == meta['n']
        data[split] = {r['id']:r for r in records}
        views[split] = {v['id']:v for v in saved_views}
        assert list(data[split]) == list(views[split])
        family_bank = reserved if split=='final' else banks
        assert sorted({r['domain'] for r in records}) == meta['domains'] == sorted(family_bank)
        entities[split] = {r['entity'] for r in records}
        hashes[split] = {r['content_hash'] for r in records}
        projected[split] = {v['projected_input_sha256'] for v in saved_views}
        groups = defaultdict(list)
        reports = defaultdict(list)
        for row in records:
            assert row['label'] == int(row['requested_slot']==row['semantic_slot']) and type(row['label']) is int
            suffix = f" Report evidence for {row['entity']}; ordinary and unusual values both count."
            assert row['objective'] in [q+suffix for q in family_bank[row['domain']][row['requested_slot']][0]]
            if row['text'].startswith('{'):
                body = json.loads(row['text'])
                assert set(body)=={'entity','level','measurement','value'} and body['entity']==row['entity']
                assert body['level'] in ['INFO','WARN','ERROR']
                measurement, value = body['measurement'],body['value']
            else:
                prefix = f"Tool report {row['entity']} ["
                assert row['text'].startswith(prefix) and row['text'].endswith('.')
                level, remainder = row['text'][len(prefix):].split(']: ',1)
                assert level in ['INFO','WARN','ERROR']
                measurement, numeric = remainder[:-1].rsplit(': ',1)
                value = int(numeric)
            assert measurement in family_bank[row['domain']][row['semantic_slot']][1]
            assert type(value) is int and (0<=value<20 if row['numeric_band']==0 else 100<=value<500)
            assert row['evidence_span']==[0,len(row['text'])]
            assert row['content_hash']==digest([row['objective'],row['text']])
            view = views[split][row['id']]
            assert view['status']=='PROJECTED' and view['error'] is None and view['drop_authorized'] is False
            assert view['original_text']==row['text'] and view['original_input_sha256']==row['content_hash']
            assert view['objective']==row['objective'][:-len(suffix)] and view['text']==f'{measurement}: {value}.'
            assert view['projected_input_sha256']==digest([view['objective'],view['text']])
            assert 0<view['actual_tokens']<=512
            assert 'semantic_slot' not in view['text'] and 'GROUND TRUTH' not in view['text']
            groups[row['group']].append(row)
            reports[row['report_id']].append(row)
        for rows in groups.values():
            assert len(rows)==8 and {r['label'] for r in rows}=={0,1}
            for question in {r['objective'] for r in rows}:
                alternatives = [r for r in rows if r['objective']==question]
                assert len(alternatives)==4 and sum(r['label'] for r in alternatives)==2
                for band in [0,1]:
                    assert sorted(r['label'] for r in alternatives if r['numeric_band']==band)==[0,1]
        for pair in reports.values():
            assert len(pair)==2 and pair[0]['text']==pair[1]['text'] and {r['label'] for r in pair}=={0,1}
    for a,b in [('train','validation'),('train','final'),('validation','final')]:
        assert not entities[a]&entities[b] and not hashes[a]&hashes[b] and not projected[a]&projected[b]
    preparation = dict(protocol_sha256=protocol['sha256'],archived_sources_annotations_views_verified=True,
        data_counts={s:m['n'] for s,m in protocol['data'].items()},domains_reserved=True,
        entities_original_inputs_projected_inputs_disjoint=True,
        projected_unique_counts={s:len(v) for s,v in projected.items()},
        token_counts='saved tokenizer counts; no tokenizer/model reexecution in stdlib audit',
        scope='shared schema/author synthetic P1 contract; final pair families reserved before training, not external blind evidence',
        model_calls_during_audit=0,API_calls_during_audit=0)
    if prepare_only:
        return preparation
    def verify_scores(receipt, split):
        assert receipt['protocol_sha256']==protocol['sha256']
        assert [r['id'] for r in receipt['rows']]==list(data[split])
        for row in receipt['rows']:
            source=data[split][row['id']]
            view=views[split][row['id']]
            for key in ['domain','report_id','label']:
                assert row[key]==source[key]
            assert row['original_input_sha256']==source['content_hash']
            assert row['input_sha256']==view['projected_input_sha256'] and row['actual_tokens']==view['actual_tokens']
            assert not row['truncated'] and not row['window_exceeded'] and row['error'] is None
            assert row['submitted'] and row['forward_completed'] and row['status']=='SCORED'
            assert type(row['score']) in (int,float) and math.isfinite(row['score'])
        result=reduce(receipt['rows'],receipt['threshold'],data[split])
        equal(result,receipt['metrics'])
        return result
    summary=json.loads((out/'summary.json').read_text())
    selection=json.loads((out/'selection.json').read_text())
    assert summary['protocol_sha256']==selection['protocol_sha256']==protocol['sha256']
    assert selection['final_inspected'] is False
    validations,finals,gates,training_seconds={},{},{},0.
    family_metrics={}
    def passed(metrics):
        values=metrics.copy()
        values['within_objective_auc']=metrics['within_objective']['auc']
        return (metrics['n']==metrics['eligible'] and metrics['errors']==metrics['cuts']==0
                and all(values[k.removesuffix('_min')]>=v for k,v in protocol['criteria'].items() if k.endswith('_min')))
    for arm in protocol['arms']:
        validations[arm],finals[arm],gates[arm],family_metrics[arm]=[],[],[],{}
        for seed in protocol['seeds']:
            directory=out/f'{arm}-{seed}'
            meta=json.loads((directory/'training_meta.json').read_text())
            assert meta['protocol_sha256']==protocol['sha256'] and meta['arm']==arm and meta['seed']==seed
            assert meta['epochs_completed']==protocol['epochs']==len(meta['history'])
            assert meta['all_parameters_trainable'] and meta['encoder_adapted']
            assert meta['metadata_origin'].startswith('written directly')
            assert meta['initial_identity']['revision']==protocol['model']['revision']
            for index, epoch in enumerate(meta['history'],1):
                equal(epoch,json.loads((directory/f'epoch-{index}.json').read_text()))
                assert epoch['epoch']==index and math.isfinite(epoch['loss']) and epoch['all_updates_finite']
                assert epoch['submitted_pairs']==protocol['data']['train']['n'] and epoch['steps']==144
                assert epoch['submitted_nonpadding_tokens']==sum(v['actual_tokens'] for v in views['train'].values())
                assert epoch['padded_token_slots']>=epoch['submitted_nonpadding_tokens'] and epoch['seconds']>0
                training_seconds+=epoch['seconds']
            if verify_weights:
                assert sha(ROOT/meta['weights_path'])==meta['weights_sha256']
            validation=json.loads((directory/'validation.json').read_text())
            vm=verify_scores(validation,'validation')
            positive=[r['score'] for r in validation['rows'] if r['label']==1]
            assert validation['threshold']==max(t for t in set(positive) if statistics.mean(s>=t for s in positive)>=.95)
            validations[arm].append(vm['auc'])
            final=json.loads((directory/'final.json').read_text())
            assert final['threshold']==validation['threshold']
            assert final['adapted_weights_sha256']==meta['weights_sha256']
            assert final['selected_before_final']==(arm==selection['selected_arm'])
            fm=verify_scores(final,'final')
            finals[arm].append(final)
            gates[arm].append(passed(fm))
            family_metrics[arm][seed]={domain:reduce([r for r in final['rows'] if r['domain']==domain],final['threshold'],data['final'])
                                      for domain in protocol['data']['final']['domains']}
        means={k:statistics.mean(f['metrics'][k] for f in finals[arm]) for k in ['auc','paired_auc','positive_recall','negative_rejection']}
        equal(means,summary['arms'][arm]['mean'])
        assert statistics.mean(f['metrics']['within_objective']['auc'] for f in finals[arm])==summary['arms'][arm]['mean_within_objective_auc']
        assert gates[arm]==summary['arms'][arm]['seeds_pass'] and all(gates[arm])==summary['arms'][arm]['all_seeds_pass']
    means={arm:statistics.mean(values) for arm,values in validations.items()}
    equal(means,selection['validation_mean_auc'])
    selected=max(protocol['arms'],key=lambda arm:means[arm])
    assert selected==selection['selected_arm']==summary['selected_arm']
    assert all(gates[selected])==summary['selected_pass'] and summary['adoption'] is False
    baseline_val=json.loads((out/'frozen/validation.json').read_text())
    baseline_final=json.loads((out/'frozen/final.json').read_text())
    verify_scores(baseline_val,'validation')
    assert baseline_final['threshold']==baseline_val['threshold']
    baseline=verify_scores(baseline_final,'final')
    equal(baseline,summary['frozen_final'])
    draws=[]
    rng=random.Random(protocol['bootstrap']['seed'])
    domains=protocol['data']['final']['domains']
    for _ in range(protocol['bootstrap']['draws']):
        choices=rng.choices(domains,k=len(domains))
        draws.append(statistics.mean(reduce([r for d in choices for r in final['rows'] if r['domain']==d])['auc'] for final in finals[selected]))
    draws.sort()
    def percentile(p):
        point=(len(draws)-1)*p
        low=int(point)
        return draws[low]+(draws[min(low+1,len(draws)-1)]-draws[low])*(point-low)
    return dict(**preparation,schema='compact-measurement-adaptation-audit/0.1',
        raw_metrics_epochs_selection_threshold_gates_verified=True,training_seconds_from_epochs=training_seconds,
        selected_arm=selected,selected_pass=all(gates[selected]),seeds_pass=gates,
        selected_final_mean=summary['arms'][selected]['mean'],frozen_final=baseline,
        selected_auc_family_bootstrap_95=[percentile(.025),percentile(.975)],
        bootstrap_scope='eight authored family clusters, descriptive; not independent population bounds',
        weights_sha256_verified=verify_weights,family_metrics=family_metrics,
        source_attribution='archived fingerprints and direct receipts, not external temporal attestation or training reexecution',
        adoption=False,P2_admission=False,current_default_changed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=DEFAULT)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--verify-weights',action='store_true')
    args=parser.parse_args()
    result=audit(args.out,args.prepare_only,args.verify_weights)
    target='preparation-audit.json' if args.prepare_only else ('audit-weights.json' if args.verify_weights else 'audit.json')
    (args.out/target).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='family_metrics'},indent=2))
