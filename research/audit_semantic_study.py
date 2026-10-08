"""Independent raw-score/annotation/epoch audit, stdlib by default; no API calls."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/goal-engine-2026-10-04/semantic-tool-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def reduce(rows,threshold=None):
    good=[r for r in rows if r['score'] is not None and math.isfinite(r['score']) and not r.get('truncated') and not r.get('error')]
    positive=[r['score'] for r in good if r['label']==1];negative=[r['score'] for r in good if r['label']==0]
    wins=sum(p>n for p in positive for n in negative)
    pairs=defaultdict(lambda:{0:[],1:[]})
    for r in good:pairs[r['report_id']][r['label']].append(r['score'])
    paired=[p>n for pair in pairs.values() for p,n in zip(pair[1],pair[0])]
    result=dict(n=len(rows),eligible=len(good),cuts=sum(bool(r.get('truncated')) for r in rows),errors=sum(bool(r.get('error')) for r in rows),
                auc=wins/(len(positive)*len(negative)) if positive and negative else None,
                paired_auc=statistics.mean(paired) if paired else None,paired_reports=len(paired))
    if threshold is not None:
        result.update(positive_recall=statistics.mean(s>=threshold for s in positive) if positive else None,
                      negative_rejection=statistics.mean(s<threshold for s in negative) if negative else None)
    return result


def close(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:close(a[k],b[k])
    elif a is None:assert b is None
    else:assert abs(a-b)<1e-12,(a,b)


def audit(verify_weights=False,allow_incomplete=False):
    protocol=json.loads((OUT/'protocol.json').read_text())
    assert digest({k:v for k,v in protocol.items() if k!='sha256'})==protocol['sha256']
    for name,expected in protocol['sources'].items():assert sha(OUT/'executed-source'/name)==expected
    tree=ast.parse((OUT/'executed-source/research/semantic_corpus.py').read_text())
    families=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FAMILIES' for t in n.targets))
    source_rows={};hashes={};entities={}
    for split,meta in protocol['data'].items():
        path=OUT/f'{split}.jsonl';assert sha(path)==meta['sha256']
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows)==meta['n'] and len({r['id'] for r in rows})==len(rows)
        assert sorted({r['domain'] for r in rows})==meta['domains']
        hashes[split]={r['content_hash'] for r in rows};entities[split]={r['entity'] for r in rows}
        counts=Counter();reports=defaultdict(list)
        for row in rows:
            assert row['content_hash']==digest([row['objective'],row['text']])
            assert row['label']==int(row['requested_slot']==row['semantic_slot'])
            query_bank,unused=families[row['domain']][row['requested_slot']]
            suffix=f" Report evidence for {row['entity']}; ordinary and unusual values both count."
            assert row['objective'] in [q+suffix for q in query_bank]
            meanings=families[row['domain']][row['semantic_slot']][1]
            if row['text'].startswith('{'):
                record=json.loads(row['text']);assert record['entity']==row['entity']
                assert record['measurement'] in meanings and record['level'] in ['INFO','WARN','ERROR']
            else:
                assert row['text'].startswith(f"Tool report {row['entity']} [")
                assert any(f']: {meaning}: ' in row['text'] for meaning in meanings)
            assert row['id'] not in row['objective']+row['text']
            assert 'semantic_slot' not in row['text'] and 'GROUND TRUTH' not in row['text']
            counts[(row['domain'],row['observation_status'],row['label'])]+=1
            reports[row['report_id']].append(row)
        for pair in reports.values():
            assert len(pair)==2 and {r['label'] for r in pair}=={0,1} and pair[0]['text']==pair[1]['text']
        for domain in meta['domains']:
            for state in ['healthy','anomalous']:assert counts[(domain,state,0)]==counts[(domain,state,1)]
        source_rows[split]={r['id']:r for r in rows}
    assert not set(protocol['data']['train']['domains'])&set(protocol['data']['final']['domains'])
    for a,b in [('train','validation'),('train','final'),('validation','final')]:
        assert not hashes[a]&hashes[b] and not entities[a]&entities[b]
    cover=json.loads((OUT/'coverage.json').read_text())
    for split,receipt in cover.items():
        assert receipt['n']==protocol['data'][split]['n'] and receipt['truncated']==receipt['incomplete_observations']==0
        assert receipt['max_pair_tokens']<=protocol['max_pair_tokens']
    if not (OUT/'selection.json').exists():
        assert allow_incomplete,'No validation selection; final audit is unavailable'
        runs={};finite_epochs=0;nonfinite_passes=0
        for arm in protocol['arms']:
            for seed in protocol['seeds']:
                directory=OUT/f'{arm}-{seed}'
                started=json.loads((directory/'started.json').read_text())
                assert started==dict(protocol_sha256=protocol['sha256'],arm=arm,seed=seed)
                history=[json.loads((directory/f'epoch-{e}.json').read_text()) for e in range(1,protocol['epochs']+1)]
                assert [r['epoch'] for r in history]==list(range(1,protocol['epochs']+1))
                finite=sum(math.isfinite(e['loss']) for e in history)
                finite_epochs+=finite;nonfinite_passes+=len(history)-finite
                state=dict(finite_epochs=finite,nonfinite_passes=len(history)-finite,weights_present=(directory/'weights.pt').exists())
                path=directory/'validation.json'
                if path.exists():
                    receipt=json.loads(path.read_text());raw=receipt['rows'];lookup=source_rows['validation']
                    assert len(raw)==len(lookup) and {r['id'] for r in raw}==set(lookup)
                    for r in raw:
                        assert r['input_sha256']==lookup[r['id']]['content_hash']
                        for k in ['report_id','label','domain','group','kind','observation_status']:assert r[k]==lookup[r['id']][k]
                    m=reduce(raw,receipt['threshold']);close(m,receipt['metrics'])
                    state['validation']=m
                    meta=json.loads((directory/'training_meta.json').read_text())
                    assert meta['history']==history and meta['epochs_completed']==finite==protocol['epochs']
                    if verify_weights:assert sha(directory/'weights.pt')==meta['weights_sha256']
                else:
                    assert finite<protocol['epochs'] and not (directory/'training_meta.json').exists()
                    state['validation']=None
                assert not (directory/'final.json').exists()
                runs[f'{arm}-{seed}']=state
        return dict(schema='semantic-tool-p1-incomplete-audit/0.1',
                    archived_sources_data_annotations_and_available_validation_verified=True,
                    study_status='incomplete: nonfinite last-two seed303; no selection or final inference',
                    data_counts={s:m['n'] for s,m in protocol['data'].items()},runs=runs,
                    finite_epochs=finite_epochs,nonfinite_passes=nonfinite_passes,
                    selected_arm=None,adoption=False,weights_sha256_verified=verify_weights,
                    bootstrap_intervals_rederived=False,API_calls_during_audit=0)
    selection=json.loads((OUT/'selection.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    assert selection['final_used_for_selection'] is False and selection['protocol_sha256']==protocol['sha256']
    validations={};finals={};families_metrics={};training_seconds=0.
    def verify_scores(receipt,split):
        raw=receipt['rows'];lookup=source_rows[split]
        assert len(raw)==len(lookup) and {r['id'] for r in raw}==set(lookup)
        for row in raw:
            original=lookup[row['id']]
            for key in ['report_id','label','domain','group','kind','observation_status']:assert row[key]==original[key]
            assert row['input_sha256']==original['content_hash']
            assert row['score'] is None or type(row['score']) in [float,int]
        calculated=reduce(raw,receipt.get('threshold'))
        close(calculated,receipt['metrics'])
        return calculated
    for arm in protocol['arms']:
        validations[arm]=[];finals[arm]=[];families_metrics[arm]={}
        for seed in protocol['seeds']:
            directory=OUT/f'{arm}-{seed}';meta=json.loads((directory/'training_meta.json').read_text())
            assert meta['protocol_sha256']==protocol['sha256'] and meta['epochs_completed']==protocol['epochs']
            assert meta['seed']==seed and meta['arm']==arm and meta['encoder_adapted']==(arm=='last-two')
            assert [e['epoch'] for e in meta['history']]==list(range(1,protocol['epochs']+1))
            for epoch in meta['history']:
                assert epoch==json.loads((directory/f"epoch-{epoch['epoch']}.json").read_text())
                assert math.isfinite(epoch['loss']) and epoch['seconds']>0
                training_seconds+=epoch['seconds']
            if verify_weights:assert sha(directory/'weights.pt')==meta['weights_sha256']
            validation=json.loads((directory/'validation.json').read_text());vm=verify_scores(validation,'validation')
            positives=[r['score'] for r in validation['rows'] if r['label']==1]
            chosen=max(t for t in set(positives) if statistics.mean(s>=t for s in positives)>=.95)
            assert chosen==validation['threshold'];validations[arm].append(vm['auc'])
            final=json.loads((directory/'final.json').read_text());fm=verify_scores(final,'final')
            assert final['threshold']==chosen and final['selected_before_final']==(selection['selected_arm']==arm)
            finals[arm].append(fm)
            families_metrics[arm][seed]={d:reduce([r for r in final['rows'] if r['domain']==d],chosen) for d in protocol['data']['final']['domains']}
        means={k:statistics.mean(r[k] for r in finals[arm]) for k in ['auc','paired_auc','positive_recall','negative_rejection']}
        close(means,summary['arms'][arm]['mean'])
        gates=[m['eligible']==m['n'] and m['cuts']==m['errors']==0 and all(m[k]>=v for k,v in ((key.removesuffix('_min'),value) for key,value in protocol['quality_gate'].items())) for m in finals[arm]]
        assert gates==summary['arms'][arm]['seeds_pass'] and all(gates)==summary['arms'][arm]['all_seed_gate_pass']
    means={arm:statistics.mean(values) for arm,values in validations.items()}
    close(means,selection['validation_mean_auc'])
    assert max(protocol['arms'],key=lambda a:means[a])==selection['selected_arm']==summary['selected_arm']
    controls={}
    for name in protocol['baselines']:
        receipt=json.loads((OUT/'baselines'/f'{name}.json').read_text());assert receipt['protocol_sha256']==protocol['sha256']
        controls[name]=verify_scores(receipt,'final');close(controls[name],summary['baselines'][name])
    return dict(schema='semantic-tool-p1-audit/0.1',sources_data_labels_scores_epochs_selection_verified=True,
                data_counts={s:m['n'] for s,m in protocol['data'].items()},selected_arm=selection['selected_arm'],
                selected_pass=summary['arms'][selection['selected_arm']]['all_seed_gate_pass'],
                raw_training_seconds=training_seconds,family_metrics=families_metrics,controls=controls,
                bootstrap_intervals_rederived=False,weights_sha256_verified=verify_weights,
                source_attribution='archived source fingerprints; no external temporal attestation or training reexecution',
                ground_truth='authored P1 measurement-slot contract, not human-reviewed/external/production/P2',API_calls_during_audit=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify-weights',action='store_true');parser.add_argument('--allow-incomplete',action='store_true');parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args()
    OUT=args.out
    result=audit(args.verify_weights,args.allow_incomplete);(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='family_metrics'},indent=2))
