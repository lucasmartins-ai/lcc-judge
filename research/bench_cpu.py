"""Offline CPU reference: measured HF lengths, no silent truncation, both M8 targets.

Run as a module: python -m research.bench_cpu --model-dir models/exp02e-unfreeze2
This is a synthetic 66K-token scoring workload, not an end-to-end LCC integration.
M9 is reported as fp32 peak process RSS; int8 deployment is not certified here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import sys
import time
from pathlib import Path
from typing import Any
import torch
import transformers
from specialist.model import SpecialistHead


def get_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024 if sys.platform == 'darwin' else 1024)


def assess_m8(per_block_p50_ms: float, dossier_s: float, context_tokens: int,
              truncated: int) -> dict:
    representative = context_tokens >= 66000 and truncated == 0
    block_pass = per_block_p50_ms < 50.0
    dossier_pass = dossier_s <= 43.0 and representative
    return dict(per_block_target_ms=50.0, per_block_p50_ms=per_block_p50_ms,
                per_block_pass=block_pass, dossier_target_s=43.0,
                dossier_measured_s=dossier_s, dossier_context_tokens=context_tokens,
                truncated=truncated, representative_workload=representative,
                dossier_pass=dossier_pass, overall_m8_compliant=block_pass and dossier_pass)


def make_reference_block(model, objective: str, target_context_tokens: int) -> str:
    line = 'service=checkout-api host=node-1 status=200 active=1 elapsed_ms=12\n'
    count = max(1, target_context_tokens // len(model.tokenizer(line, add_special_tokens=False)['input_ids']))
    block = line * count
    while len(model.tokenizer(block, add_special_tokens=False)['input_ids']) < target_context_tokens:
        block += ' ok'
    return block


def benchmark_cpu(model_dir: str, num_warmup: int = 5, num_runs: int = 15) -> dict[str, Any]:
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    cfg = json.loads(Path(model_dir, 'config.json').read_text())
    weights = Path(model_dir, 'weights.pt')
    rss_start = get_rss_mb()
    t0_load = time.perf_counter()
    model = SpecialistHead(model_id=cfg['model_id'], pooling=cfg.get('pooling', 'line-attn'))
    missing, unexpected = model.load_state_dict(torch.load(weights, map_location='cpu'), strict=False)
    if unexpected or any(not key.startswith('encoder.') for key in missing):
        raise ValueError('Checkpoint head is incomplete')
    model.temperature = cfg.get('temperature', 1.0)
    model.eval()
    t_load = time.perf_counter() - t0_load
    objective = 'Diagnose latency spike in checkout-service'
    window = min(8192, model.encoder.config.max_position_embeddings)
    dossier = [make_reference_block(model, objective, 660) for _ in range(100)]
    lengths = [len(model.tokenizer(objective, b, truncation=False)['input_ids']) for b in dossier]
    context_lengths = [len(model.tokenizer(b, add_special_tokens=False)['input_ids']) for b in dossier]
    truncated = sum(n > window for n in lengths)
    if truncated:
        raise ValueError('Reference dossier exceeds the window; refuse truncated timing')
    # First forwards in this process: report scoring and model-load contribution separately.
    t0 = time.perf_counter()
    for block in dossier:
        model.prob(objective, block, max_len=window, device='cpu')
    dossier_s = time.perf_counter() - t0
    representative = dossier[0]
    for _ in range(num_warmup):
        model.prob(objective, representative, max_len=window, device='cpu')
    sizes = [64, 128, 256, 512, 660, 1024]
    metrics = {}
    for size in sizes:
        block = make_reference_block(model, objective, size)
        actual = len(model.tokenizer(objective, block, truncation=False)['input_ids'])
        if actual > window:
            raise ValueError('Per-block case would be truncated')
        samples = []
        for _ in range(num_runs):
            start = time.perf_counter()
            model.prob(objective, block, max_len=window, device='cpu')
            samples.append((time.perf_counter()-start)*1000)
        samples.sort()
        metrics[str(size)] = dict(context_tokens=len(model.tokenizer(block, add_special_tokens=False)['input_ids']),
                                  actual_input_tokens=actual, truncated=False,
                                  p50_ms=statistics.median(samples), p95_ms=samples[int((len(samples)-1)*.95)],
                                  samples_ms=samples)
    peak = get_rss_mb()
    return dict(
        model_dir=model_dir, device='cpu', dtype='float32', model_load_s=t_load,
        peak_process_rss_mb=peak, peak_rss_increase_mb=peak-rss_start,
        memory_assessment=dict(under_1gib_peak=peak <= 1024, int8_footprint_tested=False),
        protocol=dict(platform=platform.platform(), python=platform.python_version(), torch=torch.__version__,
                      transformers=transformers.__version__, threads=torch.get_num_threads(),
                      warmup=num_warmup, repetitions=num_runs, max_len=window,
                      workload='synthetic 100 blocks, >=660 context HF tokens each; no caching',
                      weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                      config_sha256=hashlib.sha256(Path(model_dir, 'config.json').read_bytes()).hexdigest(),
                      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        per_block_latency=metrics,
        reference_dossier=dict(blocks=100, context_tokens=sum(context_lengths),
                               actual_input_tokens=sum(lengths), max_input_tokens=max(lengths),
                               truncated=truncated, scoring_s=dossier_s,
                               load_plus_scoring_s=t_load+dossier_s,
                               note='Sum includes model load and first-forward scoring; excludes fixture generation. End-to-end integration not measured.'),
        m8_evaluation=assess_m8(metrics['660']['p50_ms'], t_load+dossier_s, sum(context_lengths), truncated),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--out', default='research/bench-cpu.json')
    parser.add_argument('--runs', type=int, default=15)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error('--runs must be >=2')
    result = benchmark_cpu(args.model_dir, num_runs=args.runs)
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'per_block_latency'}, indent=2))


if __name__ == '__main__':
    main()
