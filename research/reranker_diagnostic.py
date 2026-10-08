"""Frozen known-cohort diagnostic of the pinned ranking-pretrained MiniLM."""
from __future__ import annotations

import argparse
import hashlib
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

from research.reranker_control import PairReranker
from research import semantic_study as metrics_source

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'research/goal-engine-2026-10-04/semantic-tool-cpu-v2'
OUT=ROOT/'research/goal-engine-2026-10-04/reranker-known-control'
UPSTREAM=ROOT/'research/goal-engine-2026-10-04/rerank-next/upstream-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def save_once(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    if path.exists():assert path.read_text()==text,'Frozen evidence changed'
    else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)


def prepare():
    manifest=json.loads(UPSTREAM.read_text());OUT.mkdir(exist_ok=True)
    source_names=['research/reranker_diagnostic.py','research/reranker_control.py',
                  'research/semantic_study.py','research/relevance_study.py']
    protocol=dict(schema='compact-reranker-diagnostic/0.1',model=manifest,
                  batch_size=16,threads=8,device='cpu',dtype='float32',pair_window=512,repeats=3,
                  data={split:dict(sha256=sha(OLD/f'{split}.jsonl'),n=384) for split in ['validation','final']},
                  sources={name:sha(ROOT/name) for name in source_names},
                  versions={name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','numpy']},
                  input_recipe='unchanged objective/report strings; no markers/annotations; raw single pair logit, eval, no truncation, local files only',
                  threshold='greatest validation-only raw-logit threshold with >=.95 positive recall; first repeat',
                  criteria=dict(auc_min=.90,paired_auc_min=.90,positive_recall_min=.95,negative_rejection_min=.70,all_rows_complete=True),
                  candidate_choice='MiniLM-L6 fixed before this diagnostic; no choice by cohort outcomes',
                  scope='now-exposed authored semantic cohorts; diagnostic not independent transfer/production/P2',
                  bootstrap=dict(unit='whole exposed final family',draws=2000,seed=442409),
                  current_default_changed=False,training_executed=False,API_calls=0,
                  performance_scope='whole repeated pair-scoring passes including tokenization; setup excludes interpreter/global imports; no matched architecture latency claim')
    protocol['sha256']=digest(protocol);save_once(OUT/'protocol.json',protocol)
    for split in protocol['data']:
        dest=OUT/f'{split}.jsonl';source=OLD/dest.name
        if dest.exists():assert sha(dest)==sha(source)
        else:dest.write_bytes(source.read_bytes())
    for name,expected in protocol['sources'].items():
        dest=OUT/'executed-source'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==expected
        else:dest.write_bytes((ROOT/name).read_bytes())
    return protocol


def row_scores(rows,raw):
    return [dict(id=r['id'],group=r['group'],report_id=r['report_id'],domain=r['domain'],label=r['label'],
                 observation_status=r['observation_status'],**score) for r,score in zip(rows,raw)]


def gate(metrics,criteria):
    return metrics['n']==metrics['eligible'] and metrics['cuts']==metrics['errors']==0 and all(metrics[k]>=v for k,v in (
        (k.removesuffix('_min'),v) for k,v in criteria.items() if k.endswith('_min')))


def run(protocol,snapshot):
    if (OUT/'run.json').exists():return
    if (OUT/'started.json').exists():raise ValueError('Partial run; inspect before any retry')
    save_once(OUT/'started.json',dict(protocol_sha256=protocol['sha256'],phase='inference'))
    torch.set_num_threads(protocol['threads'])
    def denied(*args,**kwargs):raise RuntimeError('Network forbidden during inference')
    socket.socket.connect=denied
    began=time.perf_counter()
    scorer=PairReranker.from_snapshot(snapshot,protocol['model'],batch_size=protocol['batch_size'],max_pair_tokens=protocol['pair_window'])
    setup_s=time.perf_counter()-began
    results={};times={};threshold=None
    for split in ['validation','final']:
        rows=[json.loads(line) for line in (OUT/f'{split}.jsonl').read_text().splitlines()]
        results[split]=[];times[split]=[]
        for repeat in range(protocol['repeats']):
            start=time.perf_counter();raw=scorer.score([r['objective'] for r in rows],[r['text'] for r in rows])
            scores=row_scores(rows,raw);elapsed=time.perf_counter()-start
            if split=='validation' and repeat==0:
                if any(r['error'] or r['score'] is None for r in scores):raise ValueError('Incomplete validation; threshold cannot be chosen')
                threshold=metrics_source.threshold_for(scores)
                save_once(OUT/'threshold.json',dict(protocol_sha256=protocol['sha256'],threshold=threshold,
                    final_used=False,raw_validation_sha256=digest(scores)))
            receipt=dict(protocol_sha256=protocol['sha256'],rows=scores,threshold=threshold,
                         elapsed_pass_s=elapsed,metrics=metrics_source.metrics(scores,threshold))
            save_once(OUT/f'{split}-{repeat}.json',receipt)
            results[split].append(receipt);times[split].append(elapsed)
            print(split,repeat,receipt['metrics'],round(elapsed,3),flush=True)
    identical=all([r['score'] for r in group[0]['rows']]==[r['score'] for r in repeat['rows']]
                  for group in results.values() for repeat in group[1:])
    saved=results['final'][0]['rows'];domains=sorted({r['domain'] for r in saved});rng=random.Random(protocol['bootstrap']['seed']);boot=[]
    for _ in range(protocol['bootstrap']['draws']):
        choices=rng.choices(domains,k=len(domains));sample=[r for d in choices for r in saved if r['domain']==d]
        boot.append(metrics_source.metrics(sample)['auc'])
    boot.sort()
    def percentile(p):
        position=(len(boot)-1)*p;low=int(position);high=min(low+1,len(boot)-1)
        return boot[low]+(boot[high]-boot[low])*(position-low)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report=dict(protocol_sha256=protocol['sha256'],model=scorer.identity,setup_s=setup_s,
                final_metrics=results['final'][0]['metrics'],validation_metrics=results['validation'][0]['metrics'],
                all_repetitions_identical=identical,all_repetitions_gate_pass=all(gate(r['metrics'],protocol['criteria']) for r in results['final']),
                final_auc_family_bootstrap_95=[percentile(.025),percentile(.975)],
                accounting=scorer.accounting,passes=times,
                warm_pair_pass_s_median=statistics.median(t for group in times.values() for t in group[1:]),
                peak_process_rss_bytes=peak if sys.platform=='darwin' else peak*1024,
                environment=dict(python=sys.version,platform=platform.platform(),socket_connect_blocked=True),
                adoption=False,calibrated_probability=False,P2_admission=False)
    save_once(OUT/'run.json',report);print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['prepare','run'])
    parser.add_argument('--snapshot',type=Path);args=parser.parse_args();protocol=prepare()
    if args.phase=='prepare':print('frozen',protocol['sha256']);return
    snapshot=args.snapshot or Path.home()/'.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots'/protocol['model']['revision']
    run(protocol,snapshot)


if __name__=='__main__':main()
