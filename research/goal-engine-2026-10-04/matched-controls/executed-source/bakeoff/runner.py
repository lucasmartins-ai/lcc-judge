"""Runner for the Sprint 2 encoder bake-off.

Usage (from the workspace root, with the LCC venv python):

    /Users/Master/LCC/.venv/bin/python -m bakeoff.runner --device cpu
    /Users/Master/LCC/.venv/bin/python -m bakeoff.runner --models ModernBERT-base,laya-multilingual

Outputs: bakeoff/results/results.json + bakeoff/results/RESULTS.md
Metric: AUC(d) = P(score(fact@d) > score(noise@d)) over all case pairs.
Effective context = largest depth with AUC >= 0.90.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import math
import os
import statistics
from dataclasses import asdict
from collections import Counter
from pathlib import Path

from .adapters import default_roster
from .probes import CASES, build_grid, count_tokens

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
AUC_BAR = 0.90
DEFAULT_DEPTHS = [0, 64, 256, 512, 1024, 2048, 4096, 8192]


def auc_fact_vs_noise(fact_scores: list[float], noise_scores: list[float]) -> float:
    wins = ties = 0
    for f in fact_scores:
        for n in noise_scores:
            if f > n:
                wins += 1
            elif f == n:
                ties += 1
    total = len(fact_scores) * len(noise_scores)
    # The gate is P(fact > noise), so ties are not wins.
    return wins / total if total else 0.5


def run(models_filter: list[str] | None, depths: list[int], device: str,
        cases_filter: list[str] | None = None) -> dict:
    # build only the filtered cases — with 62+ cases the full deep grid costs
    # real time to generate on every batched invocation (v1.2 expansion)
    selected = None
    if cases_filter:
        selected = [c for c in CASES if c.case_id in cases_filter]
        if not selected:
            raise SystemExit(f"no grid blocks matched cases {cases_filter}")
    grid = build_grid(depths, cases=selected)
    if not grid:
        raise SystemExit(f"no grid blocks matched cases {cases_filter}")
    roster = default_roster(device)
    if models_filter:
        roster = [m for m in roster if m.name in models_filter]
        if not roster:
            raise SystemExit(f"no models matched {models_filter}")

    rows: list[dict] = []
    model_meta: dict[str, dict] = {}

    import time
    import uuid
    root = Path(__file__).resolve().parents[1]
    code_files = ['bakeoff/runner.py','bakeoff/adapters.py','bakeoff/probes.py',
                  'specialist/model.py','specialist/checkpoint.py']
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in code_files}
    source_sha = hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()

    for model in roster:
        print(f"== {model.name} (load ...)", flush=True)
        try:
            model.load()
        except Exception as exc:
            model_meta[model.name] = {"error": f"load failed: {type(exc).__name__}: {exc}"[:200]}
            print(f"   LOAD FAILED: {exc}", flush=True)
            continue
        run_id = f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        checkpoint = getattr(model,'model_dir',None)
        checkpoint_sha = hashlib.sha256((Path(checkpoint)/'weights.pt').read_bytes()).hexdigest() if checkpoint else None
        config_sha = hashlib.sha256((Path(checkpoint)/'config.json').read_bytes()).hexdigest() if checkpoint else None
        model_meta[model.name] = {
            "declared_window": model.declared_window,
            "params_m": model.params_m,
            "load_s": round(model.load_s, 2),
            "rss_before_gb": round(model.rss_before, 3),
            "rss_after_load_gb": round(model.rss_after, 3),
            "device": device,
            'source_sha256':source_sha,'source_files':hashes,'run_id':run_id,
            'checkpoint_sha256':checkpoint_sha,'config_sha256':config_sha,
        }
        for block in grid:
            case = next(c for c in CASES if c.case_id == block["case_id"])
            s = model.score(case.objective, block["text"])
            rows.append({
                "model": model.name,
                "case_id": block["case_id"],
                "kind": block["kind"],
                "probe_version": block.get("probe_version", "1.2"),
                "depth_tokens": block["depth_tokens"],
                "fact_position_tokens": block["fact_position_tokens"],
                "block_tokens": block["total_tokens"],
                "actual_tokens": s.actual_tokens if s.actual_tokens is not None else block["total_tokens"],
                "score": s.value,
                "latency_ms": round(s.latency_ms, 1),
                "truncated": s.truncated,
                "device": device,
                "run_id": run_id,
                'source_sha256':source_sha,'checkpoint_sha256':checkpoint_sha,'config_sha256':config_sha,
                'input_sha256':hashlib.sha256(json.dumps([case.objective,block['text']],ensure_ascii=False).encode()).hexdigest(),
                "error": s.error,
            })
        model.close()
        print(f"   done ({len(grid)} blocks)", flush=True)

    return {"device": device, "devices": [device], "depths": depths, "model_meta": model_meta, "rows": rows}


def summarize(results: dict) -> list[dict]:
    rows = results["rows"]
    depths = results["depths"]
    summary = []
    for name, meta in results["model_meta"].items():
        if "error" in meta:
            summary.append({"model": name, "error": meta["error"]})
            continue
        entry = {"model": name, **meta, "by_depth": {}}
        exact_auc = {}
        for depth in depths:
            def scores(kind: str) -> list[float]:
                return [r["score"] for r in rows if r["model"] == name and r["depth_tokens"] == depth
                        and r["kind"] == kind and r["score"] is not None]

            fact = scores("fact")
            unrel = scores("noise_unrelated")
            decoy = scores("noise_decoy")
            lat = [r["latency_ms"] for r in rows if r["model"] == name and r["depth_tokens"] == depth
                   and r["score"] is not None]
            n_err = sum(1 for r in rows if r["model"] == name and r["depth_tokens"] == depth and r["error"])
            selected = [r for r in rows if r['model'] == name and r['depth_tokens'] == depth]
            versions = sorted({r.get('probe_version', 'unknown') for r in selected})
            counts = {'fact': len(fact), 'noise_unrelated': len(unrel), 'noise_decoy': len(decoy)}
            integrity = {}
            for family, noise_kind in [('detect','noise_unrelated'),('judge','noise_decoy')]:
                subset = [r for r in selected if r['kind'] in ('fact',noise_kind)]
                ids = {kind:Counter(r['case_id'] for r in subset if r['kind']==kind)
                       for kind in ['fact',noise_kind]}
                reasons = []
                if not ids['fact'] or ids['fact'] != ids[noise_kind]:
                    reasons.append('case_population_mismatch')
                if any(n!=1 for values in ids.values() for n in values.values()):
                    reasons.append('duplicate_case_kind')
                for key in ['probe_version','source_sha256','checkpoint_sha256','config_sha256','device']:
                    if len({r.get(key) for r in subset}) > 1:
                        reasons.append('mixed_'+key)
                if any(r.get('error') or r['score'] is None or not math.isfinite(r['score']) for r in subset):
                    reasons.append('missing_or_invalid_score')
                if any(r.get('truncated') for r in subset):
                    reasons.append('truncated_input')
                integrity[family] = dict(gate_eligible=not reasons,reasons=reasons,
                                         matched_cases=len(set(ids['fact'])&set(ids[noise_kind])))
            exact_auc[depth] = {
                'detect': auc_fact_vs_noise(fact, unrel) if fact and unrel else 0,
                'judge': auc_fact_vs_noise(fact, decoy) if fact and decoy else 0,
            }
            entry["by_depth"][str(depth)] = {
                "auc_detect": round(auc_fact_vs_noise(fact, unrel), 3) if fact and unrel else None,
                "auc_judge": round(auc_fact_vs_noise(fact, decoy), 3) if fact and decoy else None,
                "mean_fact": round(statistics.mean(fact), 3) if fact else None,
                "mean_unrelated": round(statistics.mean(unrel), 3) if unrel else None,
                "mean_decoy": round(statistics.mean(decoy), 3) if decoy else None,
                "p50_latency_ms": round(statistics.median(lat), 1) if lat else None,
                "errors": n_err,
                "n": len(fact),
                'n_by_kind': counts,
                'probe_versions': versions,
                'truncated': sum(bool(r['truncated']) for r in selected),
                'auc_method': 'strict pooled P(fact > noise); ties count zero',
                'cell_integrity': integrity,
            }
        for family in ("detect", "judge"):
            ok = [d for d in depths if exact_auc[d][family] >= AUC_BAR
                  and entry['by_depth'][str(d)]['cell_integrity'][family]['gate_eligible']]
            entry[f'passing_depths_{family}'] = ok
            entry[f"effective_context_{family}"] = max(ok) if ok else 0
        summary.append(entry)
    return summary


def render_report(results: dict, summary: list[dict]) -> str:
    depths = results["depths"]
    devices_list = results.get("devices") or [results.get("device", "mixed")]
    devices_str = ", ".join(sorted(set(str(d) for d in devices_list)))
    lines = [
        "# Encoder Bake-off — Results (Sprint 2)",
        "",
        f"Devices: `{devices_str}` · depths (tiktoken cl100k tokens): {depths} · "
        f"AUC bar for effective context: {AUC_BAR} · probe suite versions: "
        + ", ".join(sorted({r.get("probe_version", "1.0") for r in results["rows"]}))
        + " (cross-version cells do not qualify for the gate)",
        "",
        "Two families: AUC_detect = fact vs unrelated filler (notice the evidence block); "
        "AUC_judge = fact vs healthy lookalike (lexical differences remain in v1.2; "
        "a lexical control is required). Effective context = largest eligible depth with "
        "AUC >= bar per family. Depth 0 = control (decisive line alone). Latency is per "
        "(objective, block) score call.",
        "Gate AUC is strict P(fact > noise): ties contribute zero. Effective context uses "
        "unrounded AUC; 0 is the report sentinel when no depth passes. Historical experiment "
        "entries retain their original measurements. Compare models only on identical case IDs, "
        "probe versions and input/window settings. Older rows lack execution provenance; the "
        "device list records available metadata and does not certify legacy timings as CPU.",
        "Cells marked † are raw descriptive scores with incompatible populations/versions, "
        "duplicate rows, errors or cuts; they cannot establish effective context.",
        "",
        "## Summary",
        "",
        "| model | params (M) | window | eff.ctx detect | eff.ctx judge | "
        + " | ".join(f"D@{d}" for d in depths)
        + " | "
        + " | ".join(f"J@{d}" for d in depths)
        + " | p50 ms @256 | p50 ms @4K | load s | RSS Δ GB |",
        "|---|---|---|---|---|" + "---|" * (2 * len(depths) + 4),
    ]
    for e in summary:
        if "error" in e:
            lines.append(f"| {e['model']} | ERROR: {e['error']} |")
            continue
        bd = e["by_depth"]

        def cell(d: int, family: str) -> str:
            r = bd.get(str(d), {})
            v = r.get(f"auc_{family}")
            if v is None:
                return "—"
            n = r.get("n")
            mark = '' if r.get('cell_integrity',{}).get(family,{}).get('gate_eligible',True) else '†'
            if n is not None and n != 62:
                return f"{v:.2f}{mark} (n={n})"
            return f"{v:.2f}{mark}"

        d_cells = " | ".join(cell(d, "detect") for d in depths)
        j_cells = " | ".join(cell(d, "judge") for d in depths)
        l256 = bd.get("256", {}).get("p50_latency_ms")
        l4k = bd.get("4096", {}).get("p50_latency_ms")
        lines.append(
            f"| {e['model']} | {e['params_m']:.0f} | {e['declared_window']} | "
            f"{e['effective_context_detect']} | {e['effective_context_judge']} | "
            f"{d_cells} | {j_cells} | {l256} | {l4k} | {e['load_s']} | "
            f"{round(e['rss_after_load_gb'] - e['rss_before_gb'], 3)} |"
        )

    lines += ["", "## Per-depth detail", ""]
    for e in summary:
        if "error" in e:
            continue
        lines += [f"### {e['model']}", "",
                  "| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for d in depths:
            row = e["by_depth"][str(d)]
            n_cases = row.get("n", "—")
            lines.append(f"| {d} | {n_cases} | {row['auc_detect']} | {row['auc_judge']} | {row['mean_fact']} | "
                         f"{row['mean_unrelated']} | {row['mean_decoy']} | {row['p50_latency_ms']} | "
                         f"{row['errors']} |")
        lines.append("")

    lines += [
        "## Reading notes",
        "",
        "- `truncated` rows show where the model's tokenizer silently cut the block: the "
        "declared window is an upper bound, the curve is the truth.",
        "- Bi-encoder cosine scores dilute single facts in long blocks even before truncation; "
        "that is real effective-context loss, not a harness artifact.",
        "- The decoy family is lexical-trap-free by design: fact and decoy share vocabulary "
        "and differ only in values. A constant lexical score has strict AUC=0 because every pair ties.",
        "- Laya rows probe the *raw* model beyond LCC's production budget (LCC refuses states "
        "over 831 tokens and keeps blocks whole instead).",
        "- Depth is counted in tiktoken tokens; each model sees its own tokenizer's count.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated adapter names (default: all)")
    ap.add_argument("--depths", default=",".join(str(d) for d in DEFAULT_DEPTHS))
    ap.add_argument("--cases", help="comma-separated case ids (default: all) — batch deep curves")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--fresh", action="store_true", help="discard previously saved model results")
    args = ap.parse_args()

    depths = [int(x) for x in args.depths.split(",") if x.strip()]
    models_filter = [m.strip() for m in args.models.split(",")] if args.models else None
    cases_filter = [c.strip() for c in args.cases.split(",")] if args.cases else None

    results = run(models_filter, depths, args.device, cases_filter)
    out_path = os.path.join(RESULTS_DIR, "results.json")
    if not args.fresh and os.path.exists(out_path):
        with open(out_path) as f:
            prior = json.load(f)
        rerun = set(results["model_meta"])
        rerun_cells = {(r["depth_tokens"], r["case_id"]) for r in results["rows"]}
        merged = {
            **prior,
            "devices": sorted(set(prior.get("devices", [prior.get("device", "cpu")]) + [args.device])),
            "depths": sorted(set(prior.get("depths", []) + depths)),
            "model_meta": {**prior.get("model_meta", {}), **results["model_meta"]},
            # drop stale rows only for (model, depth, case) cells re-run in this
            # invocation — cell-granular so long/deep curves build in batches
            "rows": [r for r in prior.get("rows", [])
                     if not (r["model"] in rerun and (r["depth_tokens"], r["case_id"]) in rerun_cells)]
                   + results["rows"],
        }
        results = merged
    summary = summarize(results)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({**results, "summary": summary}, f, indent=2)
    report = render_report(results, summary)
    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
