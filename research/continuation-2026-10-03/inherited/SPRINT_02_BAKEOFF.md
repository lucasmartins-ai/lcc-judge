# SPRINT_02 — Encoder Bake-off (first pass, 2026-10-02)

Status: **executed** (probe suite + 7/8 candidates on CPU). Full tables:
[bakeoff/results/RESULTS.md](bakeoff/results/RESULTS.md) · raw rows:
[bakeoff/results/results.json](bakeoff/results/results.json) · formal log:
[research/experiments.md](research/experiments.md) (EXP-2026-10-02-01).

Nome: **deferido** (decisão do fundador) — working title `specialist`.

## What was built

- `bakeoff/` — probe harness: 8 task cases × 8 depths (0 control → 8192 tokens) ×
  two difficulty families:
  - **P1 detect**: incident evidence vs unrelated filler ("notice the block").
  - **P2 judge**: incident vs healthy lookalike with identical vocabulary ("tell the
    values apart") — the necessity question, lexical-trap-free.
- Adapters: Laya judges (exact LCC `keep_question` phrasing), cross-encoder,
  bi-encoders, unbounded lexical baseline. Deterministic, seeded, offline-capable.

## Headline findings

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| 1 | **Nobody judges values out of the box** — P2 is chance for all 7 models | all J cells ≈ 0.4–0.7 at n=8, no trend | necessity/criticality heads must be *trained*; supports H1 |
| 2 | **ModernBERT-base is the best detection backbone**: .88 AUC @512, decays with depth (.58 @8K) | detect row | Track B primary: 8K-native encoder + trained heads |
| 3 | **The Laya fine-tune fails on novel evidence even at control depth** (detect .28) | laya-lcc-relevance-v1 row | 3rd confirmation of memorization; September numbers stay buried |
| 4 | **Silent truncation = effective-context loss**: Laya reads 8K inputs at flat 360 ms and judges nothing past ~1K | flat latency + flat AUC | declared window ≠ used window; probe suite is the only honest measure |
| 5 | **CPU cost is quadratic in block length on 8K encoders**: 187 ms @256 → 8.0 s @8K | ModernBERT latency row | cost argument for block-aware local attention + per-block scoring |
| 6 | Thin ≥16K small-encoder candidate space (gte needed remote code and failed; jina/nomic same issue) | load failure recorded | strengthens Track B *adaptation* (position extension) over shopping |

## Sprint 2 gate status (docs/08)

> Gate: chosen backbone reaches measurable effective context ≥ 16K at acceptable CPU
> cost — or documented evidence that no candidate does.

**Status 2026-10-03 (after EXP-03-01 + EXP-04 + Independent Audit): GATE FAILED, documented.**
No configuration clears the 0.90 AUC bar at 16K on the honest 62-case probe suite v1.2.
Best measured: **J .756 pooled @16K** (within-old-8 .859), with the judge ≥ .70 floor holding
through 16K. Detection remains at chance (.511 @16K). Effective context = 0 for both families.
Independent audit (2026-10-03) verified the numbers and uncovered 4 blockers (holdout data
leakage in corpus v0.3, dynamic RoPE cache non-determinism, harness truncation miscalculation,
and uncertified epoch history).

**Formal Redirect Decision (docs/08 §Sprint 2 Gate):**
The second branch of the gate clause is activated: documented evidence that no candidate reaches
effective context ≥ 16K at acceptable CPU cost (CPU latency at 32K is ~37 s/block, quadratic).
Between the two redirect options (Track C native pretraining vs abandoning >8K ambitions in favor
of block-level aggregation), **we formally select the second option**:
1. **Abandon single-sequence >8K ambitions for Sprint 2/3.** Do not invest in Track C native
   encoder pretraining yet, because the residual gap is domain-agnostic score calibration and
   detect transfer, NOT context length or RoPE capacity (the depth curve is flat from 0 to 16K).
2. **Adopt working envelope ≤8K tokens with block-level aggregation.** The operational architecture
   relies on local token encoder (ModernBERT + line-attn) over ≤8K blocks, aggregated by the
   hierarchical block reasoner in Sprint 4.
3. **Revised Sprint 2/3 Gate:**
   - Backbone: ModernBERT-base + line-attn pooling + unfreeze-last-2.
   - Quality bar: AUC(d) ≥ 0.90 on both detect (P1) and judge (P2) across the ≤8K envelope
     on clean uncontaminated OOD under calibrated scoring.
   - Latency budget: M8 compliant on reference CPU (<50 ms p50 warm per block, ≤43 s per dossier).

## EXP-02 update (2026-10-02, same day): first trained decision head

Corpus (`data/exp02/`, programmatic `corpus-exp02/0.1`: 8 domains, value-pair
semantics, train/OOD split on paraphrase families + subject names, hash-disjoint,
anti-shortcut verified) + ModernBERT frozen + 0.2M head, 3 epochs on MPS.
Full log: [research/experiments.md](research/experiments.md) (EXP-2026-10-02-02).

- OOD gate: AUC 0.650 → 0.696 → **0.729** (val tracks; no overfitting signature).
- Transfer to curated probes at control depth: **detect 0.81 / judge 0.69** — first
  positive evidence that P1/P2 are learnable (H1 trainability).
- **Measured gap: length generalization.** The head drifts to higher P(evidence) with
  longer inputs; ranking *inverts* below chance at depth (0.00 detect @512 with the
  8K window). Probe confound noted (noise blocks ~55 tokens longer) — harness v1.1
  will match lengths; the drift itself is a model property.
- The head is now the "trained-judge" baseline row in the bake-off
  (`specialist-exp02-512` / `specialist-exp02-8k`).

## EXP-02b outcome (2026-10-02, later same day): gate FAILED, mechanism measured

Length-decorrelated corpus v0.2 + probe v1.1 built; the retrain did NOT recover depth
judgment (OOD 0.49–0.52 across mean-pool / attn-pool / shallow-unfreeze). Six controlled
runs isolate the mechanism: a **dilution cliff** — below ~10% decisive-token share the
signal disappears from frozen representations (27% share learns 0.73; 10.7% → 0.62;
≤8% → chance), while a BoW logistic still gets 0.75 (data is learnable). This is the
first measured architectural argument for the block-aware, line-level aggregation
design (H2). Full chain: [research/experiments.md](research/experiments.md)
(EXP-2026-10-02-03). EXP-02c = line-level aggregation head; acceptance unchanged.

## EXP-02c outcome (2026-10-02, later): **ACCEPTANCE PASSED** — first H2 win

Line-level aggregation head on the same frozen ModernBERT + corpus v0.2 (0.39M
params): per-line scoring via tokenizer offset mapping (single forward pass),
attention aggregation over lines (`--pooling line-attn`). Full log:
[research/experiments.md](research/experiments.md) (EXP-2026-10-02-04).

- OOD gate: **0.891** (vs 0.511 mean-pool / 0.492 token-attn / 0.511 line-max) — the
  dilution cliff was a pooling failure.
- Hard max over lines does **not** train (train AUC 0.506 — MIL gradient starvation
  with ~40 lines); dense softmax attention over lines converges in one epoch. Line-level
  *and* differentiably dense, both required.
- Curated probes v1.1: **judge .95 @256 / .83 @512** (1K window) and .92/.78 (512
  window) — pre-registered acceptance (judge ≥ 0.70 held at 256–512) **met**. Baseline
  EXP-02 head: .56/.33 (512) and .47/.42 (8K) off-control.
- **Full 0–8192 curve (same day)**: exp02c-8k holds judge **.89 @4K untruncated**,
  and exp02c-12k at depth 8192 untruncated reads **D=.86 / J=.88** — the 8K drop was
  a tokenizer-window artifact, not positions. The line-attention head extrapolates
  zero-shot from ~1K training tokens to ~10K; judge ≥ .78 at every depth 256→8192 when
  untruncated. Real EXP-03 question is now 16K/32K only (extension path confirmed:
  `rope_type: dynamic|linear` + factor, config-level, no new weights; 32K eval is
  quadratic on CPU → MPS or reduced grid).
- Watch-items: detect at control is weaker (.58 vs .81); 512-window truncates 24/24
  blocks at depth 512 (window must match depth); n=8 cases → gate result, not a
  precision claim.

## EXP-03 outcome (2026-10-02, same day): position extension 8K→32K — near-miss at the bar, positive at the floor

Same trained line-attn checkpoint, one variable at the position layer (config-level
RoPE, no new weights), probes v1.1 untruncated to 32K, MPS. Full log:
[research/experiments.md](research/experiments.md) (EXP-2026-10-02-05).

| variant | J@8K | J@16K | J@32K | D@32K |
|---|---|---|---|---|
| pure extrapolation | .875 | .891 | .719 | .641 |
| **dynamic-NTK (factor 6)** | .906 | .891 | **.828** | **.750** |

- Dynamic rope holds judge **.828 at 32K untruncated** (fact .40 vs decoy .12) while
  extrapolation degrades with noise drifting up — first measured rope-adaptation win.
- **Strict Sprint-2 gate stays OPEN**: .90 bar not reached at 16K (J=.891 = 57/64
  pairs, one tie from the bar at n=8 granularity); judge ≥ .70 floor holds through
  32K. Deciders: probe expansion 8→60+ and the encoder adaptation run.
- Cost: p50 37 s/block @32K MPS (quadratic) — fine as per-block scoring off the hot
  path, not shippable as whole-state scoring.
- Pipeline reproducibility check exact (8K cell identical to baseline to 3 decimals).

## Probe suite v1.2 + EXP-04 (2026-10-03): the 16K near-miss was an artifact; gate now measured FAILED

Two pre-registered deciders executed in sequence. Full logs:
[research/experiments.md](research/experiments.md) (EXP-2026-10-03-01, EXP-2026-10-03-02).

**v1.2 probe expansion (8 → 62 cases, hand-authored, none shared with the training
generator).** The `.891 @16K` boundary read was inside n=8 noise AND inside a case set
that mapped ~1:1 onto the training archetypes — 7–8 of the original 8 are near-copies
of `corpus.py` domains. On the honest suite the same checkpoint reads **J .726 / D .571
@16K** (n=62, 3844 pairs), and the curve is **flat in depth** (.657 at control → .743 at
4K → .726 at 16K): the failure is not positional, it is domain generalization.

**EXP-04 (corpus v0.3 + adaptation), gate metric first.** `corpus-exp02/0.3` adds 10
training archetypes and holds 4 domains out *entirely* as the OOD split (the v0.2 gate
never held out a domain, which is why it read .891 while probe transfer read .66). Two
arms, 3 epochs, MPS:

| arm | domain-OOD (full) | val | J@512 (n=62) | J@16384 (n=62) | D@16384 |
|---|---|---|---|---|---|
| baseline v0.2 frozen | — | — | .684 | .726 | .571 |
| v0.3 frozen | .573 | .931 | .722 | — | — |
| **v0.3 unfreeze-last-2** | **.673** | .949 | **.779** | **.756** | .511 |

- Encoder adaptation is the real lever (+.10 on judge vs the frozen arm); corpus
  diversity alone gains little.
- **Sprint-2 gate NOT passed** — eff ctx at the .90 bar is still 0 at every depth.
  Judge ≥ .70 floor holds through 16K. Logged as a failed gate per R2.
- Residual cause is now measured, not guessed: **per-domain score offsets are
  arbitrary** (holdout-domain fact-vs-decoy separation is strong *within* a domain —
  pdf_render fact −2.74 vs decoy −4.76 — but the absolute scale differs by >6 logits
  across domains; paired .711 vs pooled .614). The detect family never transferred
  (.46–.59 at every depth, both arms).
- Accepted stack: `line-attn` + dynamic-NTK rope (f6, window 49152) + unfreeze-last-2,
  checkpoint [models/exp02d-unfreeze2](models/exp02d-unfreeze2). Position extension is
  retired as a lever (ruled out by measurement).
- Next: domain-agnostic score normalization (rank/z-score aggregation — the paired-vs-
  pooled gap is already in hand), a detect-family objective, and the outcome-backed
  replay pilot (P2 ground truth), which was already the parallel blocker.

## Next steps (EXP-02c done + EXP-03 measured + Sprint 3 prep)

1. ~~EXP-02c (structural fix)~~ **DONE — acceptance passed, full curve done** (see
   above). ~~Remaining exp02c work: the 60+ curated-case expansion~~ **DONE (v1.2)**.
2. ~~Adaptation control: 4-epoch `--unfreeze-last-n 2`~~ **DONE (EXP-04)** — it was the
   effective lever (+.10 judge on unseen archetypes), but the .90 gate is still not met;
   the bottleneck is domain-agnostic calibration, not capacity.
3. ~~Probe suite expand 8 → 60+~~ **DONE (v1.2, 62 cases)** — and it overturned the
   near-miss; `results.json` rows are version-tagged (v1.0/v1.1/v1.2).
4. ~~EXP-03 position extension~~ **DONE**; now retired as a lever (measurement ruled it
   out — the depth curve is flat).
5. **NEW, highest priority**: domain-agnostic score normalization (per-objective
   z-score / rank aggregation) to close the paired-vs-pooled gap (.71 vs .61 on holdout
   domains) — no retraining required, measurable on existing checkpoints.
6. **NEW**: a detect-family objective in the corpus; detect is at chance (.46–.59) on
   unseen archetypes at every depth, including control.
7. Replay pilot (20 tasks) remains the parallel blocker for outcome-backed labels —
   P2 ground truth eventually comes from it, replacing synthetic value pairs.
8. MPS spot-check of the latency budget (M8) — probe rows are CPU-only.
