# 02 — Model Requirements (v0)

Original design: Sprint 0. These are engineering requirements, not marketing numbers. Targets
marked **[T]** are budgets to be validated against baselines in Sprint 1–2; success
thresholds are deliberately NOT pre-declared (they get set from measured baselines).

Current scope (2026-10-04): `rank_context` is implemented in shadow mode with raw
pair logits, offline artifact loading and refusal above the configured HF window.
Calibrated necessity/criticality/redundancy and set reasoning below remain targets.
The Sprint 2 redirect permits an experimental <=8K block path; it does not pass
the original pooled-AUC gate or certify 32K useful coverage.

Deployment reality that drives everything: LCC runs on a developer laptop (CPU or
Apple MPS), must work **offline**, must not block the compile pass, and must fail
closed. The model is advisory — a wrong estimate must never silently delete evidence.

## 1. MUST (hard requirements)

| # | Requirement | Rationale / evidence |
|---|---|---|
| M1 | **Useful coverage of >=32K in engine + LCC, 64K preferred [target]** — native pair windows and dossier coverage are measured separately. The experimental <=8K block path must establish coverage/outcomes before adoption; configuration size alone proves neither | Laya's window motivated specialization; historical 40/77 and Jev comparisons require their original input/provider contracts, not a new capacity claim |
| M2 | **Block-aware input**: consume Context IR blocks with metadata (id, source, type, tool, file, turn/order, protected, dependencies, provenance class) | LCC already knows this structure; the model must not rediscover it |
| M3 | **Typed, non-generative outputs** per block: `necessity`, `criticality`, `redundancy`, `uncertainty` (0–1, calibrated) + global scores; no free text ever reaches the context | LCC contract: "no text the model returns ever reaches your context" |
| M4 | **ABSTAIN as first-class output**; uncertainty ⇒ policy preserves | fail-closed doctrine (00 §6) |
| M5 | **Model ≠ policy**: no decision thresholds in the weights; all thresholds live in the external, versioned policy | prompt principle §15; LCC `policy.py` precedent |
| M6 | **Offline, local CPU inference** with no network, no API key (`LCC_DISABLE_NETWORK=1` compatible) | core LCC promise |
| M7 | **Deterministic given same input**: fixed weights ⇒ fixed scores; no sampling in the decision path | LCC determinism ADRs (0006, 0007) |
| M8 | **Latency budget [T]**: whole-dossier scoring ≤ the current Laya pass (~43 s cold on a 66K-token session) — target substantially under it on CPU; per-block p50 target < 50 ms warm | measured Laya baseline: cold 43.2 s / warm 0.5 s (cache); the model must beat *useful* work per second |
| M9 | **RAM budget [T]**: int8 footprint ≤ 1 GB resident for the Base tier so it can ride along inside `lcc compact` | laptop deployment |
| M10 | **Provider contract**: emits a provider-independent native result (03 §5); LCC adapts it; core schema never names the model | MSI adapter discipline |
| M11 | **Auditability**: every score carries model version, config version, and input block ids; reproducible from the receipt | MSI Inference Receipt |
| M12 | **Calibration**: uncertainty must be meaningful (report ECE / reliability curves on frozen calibration split); a 0.9 must mean 90% | abstention quality depends on it; `noul_temperature` fitting precedent |

## 2. SHOULD (strong preferences)

| # | Requirement | Rationale |
|---|---|---|
| S1 | Parameter tiers **Tiny ~30M / Base ~75M / Large ~150M**, sharing tokenizer + heads so policies can swap tiers | Pareto study (05 §6); "smaller can win" is a hypothesis |
| S2 | Quantization: **int8 required target, int4 experimental** with calibration-set regression gate | CPU deployment |
| S3 | Streaming/segmented scoring with a global block-set reasoner so sets larger than the token window can still get set-level heads | real sessions are 60K+ tokens |
| S4 | Head modularity: `necessity`, `criticality`, `redundancy` first; later heads (sufficiency, ambiguity, complexity, risk, routing, verification, outcome) attach without backbone retrain | curriculum (03 §6) |
| S5 | Metadata features enter as typed embeddings (block type, source, tool, position, age, protected, dependency degree); each feature must earn its place in ablation | prompt §11 — no feature tourism |
| S6 | ONNX export path by Sprint 10, not before | avoid premature optimization |
| S7 | Tokenizer compatibility with LCC's local token accounting (or a measured conversion factor, as done for Jev: `api = 249 + 0.98 * local`) | token budget honesty |
| S8 | Training reproducible: fixed seeds, pinned dataset hashes, recorded hardware, experiment-log schema (05 §7) | MSI reproduction requirement |

## 3. EXPERIMENTAL (prove or cut)

| # | Item | Gate to keep it |
|---|---|---|
| E1 | Custom tokenizer (code/paths/JSON/logs/diffs/traces corpus) | ≥ meaningful gain on tokens/byte, tokens/code-line, effective context increase vs best existing tokenizer (prompt §25); else drop |
| E2 | Native long-context architecture (Track C, own weights from scratch) | must beat adapted encoders (Track B) at matched parameter count on the frozen benchmark |
| E3 | Pairwise relation heads (`depends_on[i,j]`, `duplicates[i,j]`, …) | beats LCC deterministic graph + B5 baseline |
| E4 | Global reasoner hierarchy (block → set attention) | beats simple pair scorer; if not, simplify (prompt §42) |
| E5 | Position-extension methods (RoPE scaling, etc.) beyond 32K | effective-context probes show real utilization at 48K/64K |
| E6 | Outcome head `P(success | plan)` | only with multi-config replay data (Sprint 9) |
| E7 | KV-cache/block-cache for incremental passes (`--append-to` workloads) | measurable warm-pass speedup without decision drift |

## 4. Explicit non-requirements (v0)

- No generative decoding, no chat interface, no embeddings service.
- No GPU required at inference. (Training: single modern GPU class **[T]** — e.g. one
  24–48 GB card or cloud equivalent; exact budget fixed in Sprint 2 after bake-off.)
- No fine-tuning inside LCC; LCC only consumes providers.
- No claim of optimality — minimality stays empirical and scoped (MSI theory).

## 5. Measurable acceptance style

Every requirement that can be measured gets, before Sprint 3 starts: a metric, a frozen
dataset split, a baseline number (from mechanical/Laya/Jev/encoder tracks), and a
reproduction command. No success threshold is invented before those baselines exist.
