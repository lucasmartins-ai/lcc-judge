"""One fixed generic-report score subtraction on exposed compact-study cohorts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import statistics
import time

import torch
from safetensors.torch import load_file

from research.audit_reranker_diagnostic import reduce
from research.reranker_control import PairReranker
from research.reranker_diagnostic import digest, sha, save_once
from specialist.checkpoint import load_trained_weights

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'research/goal-engine-2026-10-04/compact-relation-v1'
OUT=ROOT/'research/goal-engine-2026-10-04/report-prior-diagnostic-v1'
REFERENCE='Report the observed measurement and its value.'


def prepare():
    original=json.loads((OLD/'protocol.json').read_text())
    selected=json.loads((OLD/'selection.json').read_text())
    arm=selected['selected_arm']
    sources=['research/report_prior_study.py','research/reranker_control.py',
             'research/audit_reranker_diagnostic.py','research/reranker_diagnostic.py','specialist/checkpoint.py']
    bases={seed:{split:sha(OLD/f'{arm}-{seed}/{split}.json') for split in ['validation','final']}
           for seed in original['seeds']}
    weights={seed:json.loads((OLD/f'{arm}-{seed}/training_meta.json').read_text())['weights_sha256'] for seed in original['seeds']}
    protocol=dict(schema='generic-report-control/0.1',base_protocol_sha256=original['sha256'],model=original['model'],
        selected_by_original_validation=arm,seeds=original['seeds'],weights_sha256=weights,
        base_receipt_sha256=bases,data=original['data'],criteria=original['criteria'],
        reference_question=REFERENCE,recipe='raw goal/report logit minus raw fixed-reference/report logit, coefficient1; no fitted query/label offsets',
        unique_reference_recipe='one forward per original report_id; identical control input reused for the two original goals; labels/slots never passed to model',
        sources={name:sha(ROOT/name) for name in sources},device='cpu',dtype='float32',threads=8,batch_size=16,pair_window=512,
        scope='now-exposed compact-study cohorts, diagnostic only; no new transfer confirmation or probability interpretation',
        threshold='greatest normalized validation threshold with >=.95 positive recall',
        training_executed=False,base_inference_reexecuted=False,API_calls=0,coefficient_tuning_allowed=False,
        adoption=False,current_default_changed=False)
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


def run(protocol):
    if (OUT/'summary.json').exists():
        return
    if (OUT/'started.json').exists():
        raise ValueError('Partial diagnostic needs inspection, no selective retry')
    save_once(OUT/'started.json',dict(protocol_sha256=protocol['sha256']))
    torch.set_num_threads(protocol['threads'])
    def denied(*args,**kwargs):
        raise RuntimeError('Network forbidden during model control')
    socket.socket.connect=denied
    arm=protocol['selected_by_original_validation']
    final_metrics=[]
    for seed in protocol['seeds']:
        manifest=protocol['model']
        snapshot=Path.home()/'.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots'/manifest['revision']
        scorer=PairReranker.from_snapshot(snapshot,manifest,batch_size=protocol['batch_size'])
        meta=json.loads((OLD/f'{arm}-{seed}/training_meta.json').read_text())
        path=ROOT/meta['weights_path']
        assert sha(path)==meta['weights_sha256']==protocol['weights_sha256'][str(seed)]
        load_trained_weights(scorer.model,load_file(str(path),device='cpu'))
        threshold=None
        for split in ['validation','final']:
            source=[json.loads(line) for line in (OLD/f'{split}.jsonl').read_text().splitlines()]
            views={v['id']:v for v in (json.loads(line) for line in (OLD/f'{split}-views.jsonl').read_text().splitlines())}
            by_id={r['id']:r for r in source}
            base_path=OLD/f'{arm}-{seed}/{split}.json'
            assert sha(base_path)==protocol['base_receipt_sha256'][str(seed)][split]
            base=json.loads(base_path.read_text())
            reports={}
            for row in source:
                text=views[row['id']]['text']
                if row['report_id'] in reports:
                    assert reports[row['report_id']]==text
                else:
                    reports[row['report_id']]=text
            ids=list(reports)
            began=time.perf_counter()
            controls=scorer.score([REFERENCE]*len(ids),list(reports.values()))
            elapsed=time.perf_counter()-began
            control_by_id=dict(zip(ids,controls))
            if any(c['error'] or c['score'] is None for c in controls):
                raise ValueError('Incomplete reference inputs cannot calibrate a threshold')
            normalized=[]
            for row in base['rows']:
                control=control_by_id[row['report_id']]
                normalized.append(dict(**{k:v for k,v in row.items() if k!='score'},
                    score=row['score']-control['score'],base_raw_score=row['score'],reference_raw_score=control['score'],
                    reference_input_sha256=control['input_sha256'],base_forward_preexisting=True))
            if split=='validation':
                positive=[r['score'] for r in normalized if r['label']==1]
                threshold=max(t for t in set(positive) if statistics.mean(s>=t for s in positive)>=.95)
            metrics=reduce(normalized,threshold,by_id)
            result=dict(protocol_sha256=protocol['sha256'],seed=seed,split=split,rows=normalized,
                reference_rows=[dict(report_id=id,**value) for id,value in zip(ids,controls)],threshold=threshold,
                metrics=metrics,base_metrics=base['metrics'],reference_pass_s=elapsed,
                cumulative_reference_accounting=scorer.accounting.copy(),new_reference_pair_forwards=len(ids))
            save_once(OUT/f'{seed}/{split}.json',result)
            print(seed,split,metrics,flush=True)
            if split=='final':
                final_metrics.append(metrics)
    gates=[]
    for metrics in final_metrics:
        values=metrics.copy();values['within_objective_auc']=metrics['within_objective']['auc']
        gates.append(metrics['eligible']==metrics['n'] and metrics['cuts']==metrics['errors']==0 and
            all(values[k.removesuffix('_min')]>=v for k,v in protocol['criteria'].items() if k.endswith('_min')))
    save_once(OUT/'summary.json',dict(protocol_sha256=protocol['sha256'],selected_arm=arm,
        mean={k:statistics.mean(m[k] for m in final_metrics) for k in ['auc','paired_auc','positive_recall','negative_rejection']},
        mean_within_objective_auc=statistics.mean(m['within_objective']['auc'] for m in final_metrics),
        seeds_pass=gates,all_seeds_pass=all(gates),training_executed=False,base_inference_reexecuted=False,
        API_calls=0,adoption=False,scope=protocol['scope']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['prepare','run'])
    args=parser.parse_args();protocol=prepare()
    if args.phase=='prepare':
        print('Frozen:',protocol['sha256'])
    else:
        run(json.loads((OUT/'protocol.json').read_text()))
