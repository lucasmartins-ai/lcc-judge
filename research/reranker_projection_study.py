"""One fixed scope-checked input view on exposed data; no model adaptation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import socket
import sys
import time

import torch

from research.audit_reranker_diagnostic import reduce
from research.measurement_projection import project_measurement
from research.reranker_control import PairReranker
from research.reranker_diagnostic import save_once, digest, sha

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'research/goal-engine-2026-10-04/reranker-known-control'
OUT = ROOT/'research/goal-engine-2026-10-04/measurement-projection-v1'


def prepare():
    original = json.loads((OLD/'protocol.json').read_text())
    sources = ['research/reranker_projection_study.py', 'research/reranker_control.py',
               'research/measurement_projection.py', 'research/audit_reranker_diagnostic.py',
               'research/reranker_diagnostic.py']
    protocol = dict(schema='scope-checked-measurement-view/0.1', model=original['model'],
        exposed_cohort_protocol_sha256=original['sha256'], data=original['data'],
        sources={name:sha(ROOT/name) for name in sources}, threads=8, batch_size=16,
        versions={name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','numpy']},
        device='cpu', dtype='float32', pair_window=512, repeats=3,
        recipe='Only exact caller-scope syntax + two report grammars. Check entity, remove validated structure/level/entity suffix, preserve whole natural question and measurement prose/value. UNKNOWN retains original and is not scored.',
        input_basis='different fixed model inputs from raw control; same original records/labels; not a pure same-input architecture comparison',
        threshold='greatest validation-only raw-logit threshold with >=.95 positive recall; first repeat',
        criteria=original['criteria'], training_executed=False, API_calls=0, current_default_changed=False,
        scope='exposed authored cohorts, one fixed representation diagnostic; no unseen semantic confirmation/production/P2',
        unknown_policy='UNKNOWN/KEEP; no hidden fallback score or excluded-row PASS')
    protocol['sha256'] = digest(protocol)
    save_once(OUT/'protocol.json', protocol)
    for name, expected in protocol['sources'].items():
        path = OUT/'executed-source'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            assert sha(path) == expected
        else:
            path.write_bytes((ROOT/name).read_bytes())
    for split, meta in protocol['data'].items():
        path = OUT/f'{split}.jsonl'
        if path.exists():
            assert sha(path) == meta['sha256']
        else:
            path.write_bytes((OLD/path.name).read_bytes())
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        views = [dict(id=r['id'], **project_measurement(r['objective'],r['text'])) for r in rows]
        save_once(OUT/f'{split}-views.json', dict(protocol_sha256=protocol['sha256'],rows=views))
    return protocol


def run(protocol, snapshot):
    if (OUT/'run.json').exists():
        return
    if (OUT/'started.json').exists():
        raise ValueError('Partial run needs audit before retry')
    save_once(OUT/'started.json', dict(protocol_sha256=protocol['sha256']))
    torch.set_num_threads(protocol['threads'])
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden during model study')
    socket.socket.connect = denied
    began = time.perf_counter()
    scorer = PairReranker.from_snapshot(snapshot,protocol['model'],batch_size=16,max_pair_tokens=512)
    save_once(OUT/'load.json', dict(protocol_sha256=protocol['sha256'],identity=scorer.identity,
        setup_s=time.perf_counter()-began, python=sys.version, platform=platform.platform(),socket_connect_blocked=True))
    metrics, times, results = {}, {}, {}
    threshold = None
    for split in ['validation','final']:
        data = [json.loads(line) for line in (OUT/f'{split}.jsonl').read_text().splitlines()]
        source = {r['id']:r for r in data}
        views = json.loads((OUT/f'{split}-views.json').read_text())['rows']
        eligible = [i for i,v in enumerate(views) if v['status']=='PROJECTED']
        times[split], results[split] = [], []
        for repeat in range(protocol['repeats']):
            began = time.perf_counter()
            raw = scorer.score([views[i]['objective'] for i in eligible], [views[i]['text'] for i in eligible])
            by_index = dict(zip(eligible,raw))
            scores = []
            for i, row in enumerate(data):
                score = by_index.get(i, dict(score=None, actual_tokens=0, truncated=False, window_exceeded=False,
                       submitted=False, forward_completed=False, status='UNKNOWN', error=views[i]['error']))
                scores.append(dict(id=row['id'],domain=row['domain'],report_id=row['report_id'],
                                   label=row['label'],original_input_sha256=row['content_hash'],**score))
            elapsed = time.perf_counter()-began
            if split=='validation' and repeat==0:
                if any(r['score'] is None or r['error'] for r in scores):
                    raise ValueError('Incomplete validation cannot choose a threshold')
                positives = [r['score'] for r in scores if r['label']==1]
                threshold = max(t for t in set(positives) if sum(s>=t for s in positives)/len(positives)>=.95)
                save_once(OUT/'threshold.json', dict(protocol_sha256=protocol['sha256'],threshold=threshold,
                    final_used=False,raw_validation_sha256=digest(scores)))
            result = reduce(scores,threshold,source)
            receipt = dict(protocol_sha256=protocol['sha256'],threshold=threshold,rows=scores,elapsed_pass_s=elapsed,metrics=result)
            save_once(OUT/f'{split}-{repeat}.json',receipt)
            results[split].append(receipt)
            times[split].append(elapsed)
            print(split,repeat,result,round(elapsed,3),flush=True)
        metrics[split] = results[split][0]['metrics']
    final = metrics['final']
    passed = final['n']==final['eligible'] and final['cuts']==final['errors']==0
    passed &= all(final[key.removesuffix('_min')]>=value for key,value in protocol['criteria'].items() if key.endswith('_min'))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save_once(OUT/'run.json',dict(protocol_sha256=protocol['sha256'],metrics=metrics,observed_pass_s=times,
        all_scores_identical=all([r['score'] for r in receipts[0]['rows']]==[r['score'] for r in receipt['rows']]
                                for receipts in results.values() for receipt in receipts[1:]),
        accounting=scorer.accounting,peak_process_rss_bytes=peak if sys.platform=='darwin' else peak*1024,
        final_gate_pass=bool(passed),adoption=False,API_calls=0,training_executed=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=['prepare','run'])
    parser.add_argument('--snapshot',type=Path)
    args=parser.parse_args()
    protocol=prepare()
    if args.phase=='prepare':
        print('Frozen:',protocol['sha256'])
    else:
        snapshot=args.snapshot or Path.home()/'.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L6-v2/snapshots'/protocol['model']['revision']
        run(protocol,snapshot)
