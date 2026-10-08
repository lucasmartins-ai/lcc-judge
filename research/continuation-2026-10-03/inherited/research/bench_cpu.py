"""CPU latency and memory benchmark for LCC-judge under requirement M8.

Requirements (docs/02-model-requirements.md):
- M8: whole-dossier scoring <= 43 s on CPU; per-block p50 warm < 50 ms.
- M9: resident memory (RSS) within budget.
- M6: offline, local CPU inference with no network / MPS dependencies.

Usage:
    /Users/Master/LCC/.venv/bin/python research/bench_cpu.py --model-dir models/exp02c-line-attn
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import time
from typing import Any

import torch
from specialist.model import SpecialistHead


def get_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS ru_maxrss is in bytes
    return usage.ru_maxrss / (1024 * 1024)


def benchmark_cpu(model_dir: str, num_warmup: int = 5, num_runs: int = 30) -> dict[str, Any]:
    rss_start = get_rss_mb()
    
    cfg_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Missing config.json in {model_dir}")
    cfg = json.load(open(cfg_path))
    
    t0_load = time.perf_counter()
    model = SpecialistHead(
        model_id=cfg["model_id"],
        freeze_encoder=True,
        pooling=cfg.get("pooling", "line-attn"),
        max_positions=cfg.get("max_positions"),
    )
    weights_path = os.path.join(model_dir, "weights.pt")
    if os.path.exists(weights_path):
        sd = torch.load(weights_path, map_location="cpu")
        model.load_state_dict(sd, strict=False)
    model.eval()
    t_load_s = time.perf_counter() - t0_load
    
    rss_loaded = get_rss_mb()
    model_rss_mb = rss_loaded - rss_start
    
    # Warmup
    dummy_obj = "Diagnose latency spike in checkout-service"
    dummy_block = "2026-10-03T12:00:00Z [ERROR] connection pool timeout active=20 idle=0"
    for _ in range(num_warmup):
        _ = model.prob(dummy_obj, dummy_block, max_len=512, device="cpu")
        
    # Per-block latency by sequence length
    block_sizes = [64, 128, 256, 512, 1024]
    per_size_metrics = {}
    
    for size in block_sizes:
        # Generate block with approx `size` tokens
        filler_lines = [
            f"service=checkout-api host=node-{i} metric_requests={i*10} error_count=0 status=200 latency_ms=12"
            for i in range(max(1, size // 15))
        ]
        block_text = "\n".join(filler_lines)
        
        latencies_ms = []
        for _ in range(num_runs):
            t0 = time.perf_counter()
            _ = model.prob(dummy_obj, block_text, max_len=size, device="cpu")
            latencies_ms.append((time.perf_counter() - t0) * 1000)
            
        latencies_ms.sort()
        p50 = statistics.median(latencies_ms)
        p90 = latencies_ms[int(len(latencies_ms) * 0.90)]
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
        
        per_size_metrics[f"{size}_tokens"] = {
            "p50_ms": round(p50, 2),
            "p90_ms": round(p90, 2),
            "p95_ms": round(p95, 2),
            "min_ms": round(latencies_ms[0], 2),
            "max_ms": round(latencies_ms[-1], 2),
            "mean_ms": round(statistics.mean(latencies_ms), 2),
        }
        
    # Reference dossier simulation (100 blocks, typical LCC session dossier)
    # Blocks average ~350 tokens (total ~35,000 tokens)
    dossier_blocks = [
        "\n".join([f"line {j}: timestamp=2026-10-03T12:{j%60:02d}:00Z msg=service event payload active=1" for j in range(25)])
        for _ in range(100)
    ]
    t0_dossier = time.perf_counter()
    for blk in dossier_blocks:
        _ = model.prob(dummy_obj, blk, max_len=512, device="cpu")
    total_dossier_s = time.perf_counter() - t0_dossier
    
    # Assess compliance against M8 (<50 ms p50 warm per block, <=43 s per dossier)
    p50_256 = per_size_metrics["256_tokens"]["p50_ms"]
    m8_per_block_pass = p50_256 < 50.0
    m8_dossier_pass = total_dossier_s <= 43.0
    m8_compliant = m8_per_block_pass and m8_dossier_pass
    
    result = {
        "model_dir": model_dir,
        "device": "cpu",
        "load_time_s": round(t_load_s, 2),
        "rss_delta_mb": round(model_rss_mb, 2),
        "total_rss_mb": round(rss_loaded, 2),
        "per_block_latency": per_size_metrics,
        "reference_dossier": {
            "blocks_count": 100,
            "avg_block_tokens": 350,
            "total_time_s": round(total_dossier_s, 2),
            "throughput_blocks_per_s": round(100 / total_dossier_s, 1),
        },
        "m8_evaluation": {
            "per_block_target": "<50 ms p50",
            "per_block_p50_256_ms": p50_256,
            "per_block_pass": m8_per_block_pass,
            "dossier_target": "<= 43.0 s",
            "dossier_measured_s": round(total_dossier_s, 2),
            "dossier_pass": m8_dossier_pass,
            "overall_m8_compliant": m8_compliant,
        },
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark CPU inference for LCC-judge")
    ap.add_argument("--model-dir", required=True, help="Directory containing config.json and weights.pt")
    ap.add_argument("--out", default="research/bench-cpu.json", help="Output JSON path")
    args = ap.parse_args()
    
    res = benchmark_cpu(args.model_dir)
    print(json.dumps(res, indent=2))
    with open(args.out, "w") as f:
        json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
