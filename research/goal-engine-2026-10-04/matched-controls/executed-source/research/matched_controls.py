"""Fresh matched-text controls. Prior probe exposure makes this exploratory.

python -m research.matched_controls --model all
Independent per-model processes share a frozen protocol and save each score.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/goal-engine-2026-10-04/matched-controls'
MODELS=['lexical','bge','gte','specialist','laya']


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adapter(name):
    from bakeoff.adapters import (LexicalAdapter,OfficialEmbeddingAdapter,
                                  TrainedJudgeAdapter,PinnedLayaAdapter)
    if name=='lexical': return LexicalAdapter()
    if name=='bge': return OfficialEmbeddingAdapter.bge()
    if name=='gte': return OfficialEmbeddingAdapter.gte()
    if name=='specialist':
        return TrainedJudgeAdapter('specialist-clean-corrected',str(ROOT/'models/exp02e-unfreeze2'),8192)
    return PinnedLayaAdapter('laya-multilingual-pinned',str(Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya-multilingual/snapshots/052592a15d198d9ad47da779604259b10b47b7aa'))


def freeze():
    from bakeoff.probes import CASES,build_grid
    files=['research/matched_controls.py','bakeoff/adapters.py','bakeoff/probes.py',
           'specialist/model.py','specialist/checkpoint.py']
    grid=build_grid([0,512],seed=130)
    protocol=dict(schema='matched-controls/0.1',depths_cl100k=[0,512],probe_version='1.2',
                  case_ids=[c.case_id for c in CASES],grid_seed=130,models=MODELS,device='cpu',threads=8,
                  metric='strict pooled P(fact > noise); ties zero',
                  gate=.9,truncated_cells_gate_eligible=False,
                  confirmatory=False,reason='Existing authored suite and training family exposure; new inference only',
                  recipe=dict(bge='normalized CLS; query-only retrieval prefix',
                              gte='normalized CLS; no prefix; author-derived buffers restored after meta loading',
                              laya='pinned multilingual; exact runtime sequence including question',
                              specialist='clean checkpoint; corrected line-attn; native RoPE'),
                  sources={n:sha(ROOT/n) for n in files},
                  checkpoint_sha256=sha(ROOT/'models/exp02e-unfreeze2/weights.pt'),
                  config_sha256=sha(ROOT/'models/exp02e-unfreeze2/config.json'),
                  grid_sha256=hashlib.sha256(json.dumps(grid,sort_keys=True).encode()).hexdigest())
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'protocol.json'
    if path.exists(): assert json.loads(path.read_text())==protocol,'Protocol changed: use a new run'
    else:path.write_text(json.dumps(protocol,indent=2)+'\n')
    return protocol,grid


def run(name):
    import torch
    from bakeoff.probes import CASES
    from bakeoff.runner import summarize
    protocol,grid=freeze()
    target=OUT/name;target.mkdir(exist_ok=True)
    result_path=target/'results.json'
    if result_path.exists():
        assert json.loads(result_path.read_text())['protocol_sha256']==protocol['sha256']
        print(name,'completed receipt preserved'); return
    raw=target/'scores.jsonl'
    assert not raw.exists(),'Partial run exists: inspect rather than silently rerun'
    torch.set_num_threads(protocol['threads'])
    model=adapter(name)
    start=time.perf_counter()
    model.load()
    checkpoint=getattr(model,'_model',None)
    meta=dict(protocol_sha256=protocol['sha256'],declared_window=model.declared_window,
              load_s=model.load_s,peak_rss_after_load_gb=model.rss_after,
              platform=platform.platform(),python=platform.python_version(),
              versions={n:importlib.metadata.version(n) for n in ['torch','transformers','laya']},
              revision=getattr(model,'revision',None),code_revision=getattr(model,'code_revision',None),
              dtype=str(next(checkpoint.parameters()).dtype) if checkpoint is not None else None,
              scope='exploratory curated probes; no downstream outcome or useful-context claim')
    rows=[]; objectives={c.case_id:c.objective for c in CASES}
    with raw.open('x') as stream:
        for block in grid:
            score=model.score(objectives[block['case_id']],block['text'])
            row={k:block[k] for k in ['case_id','kind','depth_tokens','probe_version']}
            row.update(model=name,score=score.value,latency_ms=score.latency_ms,error=score.error,
                       truncated=score.truncated,actual_tokens=score.actual_tokens,
                       input_sha256=hashlib.sha256(json.dumps([objectives[block['case_id']],block['text']],ensure_ascii=False).encode()).hexdigest(),
                       source_sha256=protocol['sha256'],device='cpu')
            rows.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
    model.close()
    result=dict(protocol_sha256=protocol['sha256'],rows=rows,depths=[0,512],model_meta={name:meta},
                total_wall_s=time.perf_counter()-start)
    result['summary']=summarize(result)
    result_path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'model':name,'n_rows':len(rows),'summary':result['summary']},indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=MODELS+['all'],default='all')
    args=parser.parse_args()
    if args.model!='all':run(args.model);return
    freeze()
    for name in MODELS:
        with (OUT/f'{name}.log').open('w') as log:
            result=subprocess.run([sys.executable,'-m','research.matched_controls','--model',name],
                                  cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        print(name,'exit',result.returncode,flush=True)
        if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
