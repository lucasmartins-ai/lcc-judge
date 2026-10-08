# 05 — Benchmark Strategy (v0)

Status: Sprint 0. Baselines and metrics are defined **before** any training. Numbers
come from runs, never from declarations. Every empirical claim carries: dataset class +
N, config, commit sha, reproduction command (MSI methodology). Quality and cost are
always reported together — **reduction without a paired quality measure is a failure**.

## 1. Baselines (all must run before the first specialist trains)

| ID | Baseline | Role | Notes |
|---|---|---|---|
| BL1 | deterministic LCC (`--provider mechanical`) | floor: lexical, unbounded context, $0 | `-26/-58/-65%` reduction at 100% category recall on canonical corpora (measured) |
| BL2 | Laya shipped checkpoints | local learned baseline | keeps ~everything (0.0% reduction); 512/1024 window |
| BL3 | `laya-lcc-relevance-v1` (local fine-tune) | adapted-encoder proxy (Track A lesson) | strong in-domain, fails OOD (6/6 false drops) |
| BL4 | Jev (remote, 32K) | strongest current judge | −52% at XL, 100% category recall; 2 false drops on 12-block ablation; paid |
| BL5 | general encoder + linear heads (ModernBERT-class, 8K) | generic-representation baseline | Sprint 2 bake-off |
| BL6 | adapted long-context encoder (Track B) | candidate backbone | Sprint 2 |
| BL7 | native architecture (Track C) | candidate backbone | Sprint 4+ only if gated |
| BL8 | general LLM prompted judge (small + frontier) | upper-reference for judgment quality | cost/latency recorded, not a deployment option |

Every baseline runs the **same** frozen sets through the **same** harness.

## 2. Context decision metrics (mandatory)

| Metric | Definition | Why |
|---|---|---|
| **critical recall** | required-critical blocks kept / required-critical blocks | the safety metric |
| **false critical drop rate** | required-critical blocks lost / required-critical blocks (existing LCC `false_drop_rate`) | the catastrophe metric |
| category recall | evidence categories preserved per task | LCC precedent (100% bar) |
| context reduction | tokens removed / tokens in | efficiency side of the pair |
| context retained | companion of reduction | honesty |
| dependency preservation | kept set closed over required dependency links | severed link = wrong answer |
| sufficiency accuracy | set-level sufficiency vs replay truth (S1) | Stage 4 |
| restoration rate | blocks restored / blocks dropped (plus budget pressure) | measures judge error load on the safety net |
| abstention quality | risk-coverage curve: error rate at coverage levels; abstain calibration | fail-closed economy |
| calibration (ECE, Brier) | per head | uncertainty must be meaningful |

Pairing rule: every report row shows **quality metric + cost metric** together.

## 3. Cost / resource metrics

```text
latency p50/p95 (CPU, fixed reference machine, pinned thread count)
RAM resident
model size on disk (fp32 / int8 / int4)
tokens processed per second (and per block class)
$ per 1K blocks (for paid baselines only)
```

Reference machine: one pinned laptop class recorded in each report; relative numbers
carry the machine id.

## 4. Long-context probe suite (effective context, not declared context)

Construction (frozen in Sprint 1):

1. **Placement probes**: single critical fact at 2K / 8K / 16K / 24K / 32K / 48K / 64K
   in realistic filler (tool traces, logs, code). Score = decision correctness at that
   depth. Curve = effective context utilization.
2. **Multi-hop triads**: evidence A @2K + dependency B @31K + qualifier C @61K where the
   correct decision requires all three (e.g., A alone suggests DROP, C flips it to KEEP).
3. **Lost-in-the-middle stress**: conflicting cues at window edges vs center.
4. **Block-metadata probes**: same content, different provenance/protected metadata;
   decision should follow the typed semantics.

Primary outputs: `effective_context_utilization@depth` per model, and the honest
"32K accepted ≠ 32K used" comparison. Gate for Sprint 5: if 32K shows no utilization
gain over 8K, stop and diagnose before any 64K work.

## 5. MSI metrics (only when corresponding heads exist)

```text
routing accuracy
false de-escalation rate        <- the dangerous one (cheap route, wrong answer)
unnecessary escalation rate     <- the cost one
model calls avoided
reasoning budget saved
verification prediction accuracy
task success @ matched cost
cost @ matched task success
```

Escalation-precedent ceilings (cognitive-triage-benchmark): escalation miss ≤ 2% on
high-stakes class; quality preservation ≥ 97% of baseline. MSI-Bench rows inherit that
discipline.

## 6. Principal metric (the one that matters)

```text
NOT:  maximum compression
BUT:  minimum resource usage at matched outcome quality
```

Reporting form: for each system, the cheapest configuration that reaches the frozen
outcome-quality bar (e.g., 100% critical recall on D8, or matched success rate on
replayed tasks), then compare cost at that point; and conversely quality at matched
cost. Pareto frontier plots: quality vs latency / RAM / reduction — per model tier.

## 7. Protocol rules

1. Pre-registration: metrics, splits, and thresholds frozen in Sprint 1, before any
   specialist training. Threshold changes afterwards are recorded as new policy versions.
2. Selector/verifier independence: the verifier sees objective + candidate only
   (MSI methodology gate).
3. Single-judge verdicts on contested items require a second independent check.
4. Adversarial + OOD suites (D7) run for every checkpoint before any canonical number
   is quoted (the Laya memorization lesson, 04 §1).
5. Experiment log per run: hypothesis, configuration, dataset+hash, model, tokenizer,
   context length, training method, seed, hardware, metrics, result, interpretation,
   decision (prompt §38).
6. Statistical treatment where claiming "beats": paired tests (McNemar precedent),
   bootstrap CIs, and N stated. No superiority claims without them.
7. Failures are benchmark results too: every negative result lands in
   `research/failures.md` with evidence and the change it motivated.

## 8. Sprint mapping

| Sprint | Benchmark work |
|---|---|
| 1 | freeze MSI-Bench v1 + probe suite schemas; run BL1–BL4 (BL1–BL4 results already partially exist in `LCC/benchmarks/research/`) |
| 2 | bake-off harness: BL5–BL6 under identical protocol |
| 3 | first specialist vs BL1–BL6 on B2/B3/B4 heads |
| 4 | block-aware ablation: hierarchy vs pair scorer |
| 5 | probe-suite utilization at 32K/64K |
| 6 | outcome-backed vs relevance-only training comparison (H3) |
| 7 | sufficiency calibration gates |
| 8 | MSI heads vs triage-gate baseline (the existing `(decision, conf, risk) -> route` rule) |
| 9 | P(success|plan) reliability |
| 10 | quantization regression gates (int8/int4 must not move metrics beyond tolerance) |
