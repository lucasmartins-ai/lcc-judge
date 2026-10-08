"""Supplemental fresh-process memory/cold/warm checks; never calls an API.

The completed outcome protocol is unchanged. Measurements use one fixed, exposed
task at each budget and do not estimate a deployment latency distribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/goal-engine-2026-10-04/observation-lcc-pilot'
LCC = Path('/Users/Master/LCC')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(profile, budget):
    started = time.perf_counter()
    sys.path.insert(0, str(LCC / 'src'))
    grid = json.loads((OUT / 'grid.json').read_text())
    cell = next(c for c in grid if c['budget_cl100k'] == budget)
    setup = time.perf_counter()
    if profile == 'observations':
        from lcc_engine.observations import ObservationEngine, ObservationRequest
        from lcc.relevance.observations import compact_observations
        engine = ObservationEngine()
        request = ObservationRequest(**cell['request'])
    elif profile == 'laya':
        from research.lcc_pareto import LayaClient
        from lcc.relevance.compactor import RelevanceCompactionRequest, compact_context
        client = LayaClient()
        request = RelevanceCompactionRequest(
            text=cell['text'], question=cell['objective'], provider='laya', client=client,
            threshold=.4, min_block_chars=80, max_block_chars=3000,
            trim_head_chars=0, batch_size=1, max_workers=1, deterministic_protection=True,
            enable_sufficiency=False, enable_semantic_verify=False,
            marker=False)
    setup_s = time.perf_counter() - setup
    times, hashes = [], []
    for _ in range(3):
        began = time.perf_counter()
        if profile == 'full':
            output = cell['text']
        elif profile == 'observations':
            output = compact_observations(cell['text'], request, engine=engine,
                                          min_block_chars=80, max_block_chars=3000).compacted_text
        else:
            output = compact_context(request).compacted_text
        times.append(time.perf_counter() - began)
        hashes.append(hashlib.sha256(output.encode()).hexdigest())
    expected = json.loads((OUT / profile / cell['task_id'] / str(budget) / 'compilation.json').read_text())
    assert len(set(hashes)) == 1 and hashes[0] == expected['output_sha256']
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return dict(profile=profile, budget_cl100k=budget, task_id=cell['task_id'],
                setup_s=setup_s, first_compile_s=times[0], warm_compile_s=times[1:],
                warm_compile_s_median=statistics.median(times[1:]),
                process_elapsed_s=time.perf_counter() - started,
                process_peak_rss_bytes=peak if sys.platform == 'darwin' else peak * 1024,
                output_sha256=hashes[0], API_calls=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['full', 'observations', 'laya'])
    parser.add_argument('--budget', type=int, choices=[8192, 32768])
    args = parser.parse_args()
    if args.profile:
        print(json.dumps(measure(args.profile, args.budget)))
        return
    target = OUT / 'local-process-cost-v1'
    target.mkdir(exist_ok=True)
    sources = [Path(__file__).resolve(), ROOT/'research/lcc_pareto.py', ROOT/'bakeoff/adapters.py',
               ROOT/'lcc_engine/observations.py', LCC/'src/lcc/relevance/observations.py',
               LCC/'src/lcc/relevance/compactor.py', LCC/'src/lcc/relevance/blocks.py']
    protocol = dict(schema='supplemental-local-path-cost/0.1',
                    scope='one exposed task per budget, each in a fresh process; sequential three passes; no API or population inference',
                    grid_sha256=sha(OUT/'grid.json'), sources={str(p):sha(p) for p in sources},
                    historical_outcome_protocol_unchanged=True, externally_attested=False)
    encoded = json.dumps(protocol, indent=2)+'\n'
    path = target/'protocol.json'
    if path.exists():
        assert path.read_text() == encoded
    else:
        path.write_text(encoded)
    results = []
    for budget in [8192,32768]:
        for profile in ['full','observations','laya']:
            path = target/f'{profile}-{budget}.json'
            if path.exists():
                results.append(json.loads(path.read_text()));continue
            run = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--profile',profile,'--budget',str(budget)],
                                 capture_output=True,text=True,timeout=240,cwd=ROOT)
            (target/f'{profile}-{budget}.stderr.log').write_text(run.stderr)
            assert run.returncode == 0, run.stderr
            result = json.loads(run.stdout.strip().splitlines()[-1])
            path.write_text(json.dumps(result,indent=2)+'\n');results.append(result)
            print(profile,budget,result['process_peak_rss_bytes'],flush=True)
    (target/'summary.json').write_text(json.dumps(dict(protocol=protocol,measurements=results),indent=2)+'\n')


if __name__ == '__main__':
    main()
