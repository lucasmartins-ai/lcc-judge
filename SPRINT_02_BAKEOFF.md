# SPRINT_02 — Encoder Bake-off (first pass, 2026-10-02)

Status 2026-10-03: **gate failed; redirect recorded; remediation partially complete**.
Current 2026-10-04 work: [engine + LCC validation](research/goal-engine-2026-10-04/REPORT.md).
Corrected recipes measured on identical new inputs; referenced replay fails
60% concordance/40% UNKNOWN; new frozen-head arms fail heldout-domain criteria.
Native HF frontier and pipeline outcome/cost measurements are complete: 744
uncut pairs, J .8345/D .7360 near native8192; 96 LCC outcome attempts. The native
shadow policy removes no context. Fresh holdout normalization fails its CI criterion.
Direct P1 label alignment is now measured: six new three-epoch runs, selected
last-two final AUC .7145; every seed fails .90. The separate explicit observation
operation preserves declared records/UNKNOWN in synthetic JSON dossiers through
128K cl100k tokens. It is P1 literal retrieval, not a neural context gain or LCC
outcome gate. The goal remains active for a narrow workflow pilot and a useful
semantic relevance candidate.
Clean corpus v0.4 and both 3-epoch arms are saved. Full n=62 coverage at 4K;
nominal 8K cuts every input. M8 per-block target fails; real replay completed,
but proposed reliability fails (80% concordance, 20% UNKNOWN; zero P2 admission).
Current evidence: [continuation report](research/audit-2026-10-03/AUDIT_RESOLUTION.md).
Update2026-10-04: [verifier calibration](research/verifier-calibration-2026-10-03/REPORT.md)
completed on80/108 curated controls; candidate passes provisional per-kind targets
but rejects2 valid PDB budgets. No P2 admission or repeated-replay certification.
Next experiment completed2026-10-04: [separate PDB recipe](research/pdb-routing-2026-10-04/REPORT.md)
has0FP/0FN/0UNKNOWN on112 new curated eval controls, versus27 FN in coupled review
with the same numeric guard/cutoff. Point observation, gateClaim DOWNGRADE;
independent task references and repeated replay remain open, zero P2 admission.
The initial pass below evaluated 7/8 candidates on CPU; later specialist timings are MPS. Full tables:
[bakeoff/results/RESULTS.md](bakeoff/results/RESULTS.md) · raw rows:
[bakeoff/results/results.json](bakeoff/results/results.json) · formal log:
[research/experiments.md](research/experiments.md) (EXP-2026-10-02-01).

Nome: **deferido** (decisão do fundador) — working title `specialist`.

## What was built

- `bakeoff/` — probe harness: 8 task cases × 8 depths (0 control → 8192 tokens) ×
  two difficulty families:
  - **P1 detect**: incident evidence vs unrelated filler ("notice the block").
  - **P2 judge**: incident vs healthy lookalike with identical vocabulary ("tell the
    values apart"). This curated incident/healthy discrimination task is not
    counterfactual necessity and retains lexical shortcuts.
- Adapters: Laya judges (exact LCC `keep_question` phrasing), cross-encoder,
  bi-encoders, unbounded lexical baseline. Deterministic, seeded, offline-capable.

## Historical first-pass findings

The initial interpretations below used small or mixed-recipe cohorts. They do
not certify necessity, absence of lexical shortcuts, numerical reasoning capacity,
or present-day model superiority. Later matched controls and MODEL_CARD.md define
the current limits and the mismatch between incident labels and KEEP relevance.

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
Historical v0.3 measurement: **J .756 pooled @16K** (within-old-8 .859).
The claim that judge ≥ .70 holds through 16K was incorrect: control J is .6915.
Detection remains at chance (.511 @16K). Effective context = 0 for both families.
Independent audit (2026-10-03) verified the numbers and uncovered 4 blockers (holdout data
leakage in corpus v0.3, dynamic RoPE cache non-determinism, harness truncation miscalculation,
and uncertified epoch history).

**Formal Redirect Decision (docs/08 §Sprint 2 Gate):**
The redirect branch is activated on the measured failed candidates; this does not
prove that every architecture fails or fill missing depths. The accepted v0.3
checkpoint has no 8192/32768 measurements. The historical ~37 s/block at 32K
was measured on MPS with v0.2 and n=8; it does not establish CPU feasibility or the
clean checkpoint's 32K quality.
Between the two redirect options (Track C native pretraining vs abandoning >8K ambitions in favor
of block-level aggregation), **we formally select the second option**:
1. **Abandon single-sequence >8K ambitions for Sprint 2/3.** Do not invest in Track C native
   encoder pretraining yet: quality already fails at control depth. Domain transfer,
   within-domain ranking and score offsets remain problems. The earlier curve suggests
   length is not the sole cause; it does not isolate positional capacity, especially
   given the historical RoPE cache defect.
2. **Adopt working envelope ≤8K tokens with block-level aggregation.** The operational architecture
   relies on local token encoder (ModernBERT + line-attn) over ≤8K blocks, aggregated by the
   hierarchical block reasoner in Sprint 4.
3. **Additional experimental quality/cost gate (Sprint 3 Pareto gate remains required):**
   - Backbone: ModernBERT-base + line-attn pooling + unfreeze-last-2.
   - Quality bar: AUC(d) ≥ 0.90 on both detect (P1) and judge (P2) across the ≤8K envelope
     on clean uncontaminated OOD under calibrated scoring.
   - Latency budget: M8 compliant on reference CPU (<50 ms p50 warm per block, ≤43 s per dossier).

## Continuation evidence (2026-10-03)

- `data/exp02e`: 2340/810/960 examples, 18 train domains, zero signatures from
  all 4 holdout domains in train/val; content hashes and split disjointness verified.
- Clean `models/exp02e-unfreeze2`, n=62, native window 8192: J/D =
  .748/.760 at control, .815/.713 at 512, .824/.702 at 4096.
  Nominal 8192 gives .619/.549, but **186/186 prompts are truncated**.
  The depth grid uses cl100k; the actual HF input is larger than the model window.
- The working ≤8K envelope and hierarchical aggregation are **experimental**.
  Neither untruncated near-window quality nor a hierarchy advantage has been proved.
- Label-free normalization on clean scores reaches unfreeze J .826/.855 at 0/512.
  At 512 the gain CI includes zero. This exploratory candidate-set score is not
  validated probabilistic calibration and does not pass the .90 quality gate.
- Joint detect product vs independent clean frozen BCE: ΔD −.0382/−.0453 at 0/512,
  both 95% CIs negative. Do not adopt this pilot's product score.
- CPU, clean unfreeze: 66K context tokens/100 blocks without cuts, load+scoring
  20.38 s; representative warm p50 192.40 ms. Dossier target passes; **M8 fails**.
  Peak fp32 process RSS 915.4 MiB; int8 deployment budget M9 is not certified.
- Old `data/d6_pilot` artifacts are **SYNTHETIC smoke tests**. New `data/d6_real_pilot`
  has 120 real stateless Hermes calls: 5 NECESSARY, 11 UNNECESSARY, 4 UNKNOWN after
  audited verifier correction. Concordance80%/UNKNOWN20% fail the proposed targets;
  all labels remain outside P2 training. Six executable Python fixtures and fourteen
  typed-answer checks are bounded contracts, not production-service replays.
  See [real replay audit](research/replay-real-2026-10-03/REPORT.md).

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
  pairs; one additional strict pair win would clear the bar at n=8); judge ≥ .70 floor holds through
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
4K → .726 at 16K). Quality fails already at control, supporting a transfer problem;
the subsequently found RoPE cache defect prevents treating this as proof that
positions are preserved.

**EXP-04 (corpus v0.3 + adaptation), gate metric first.** `corpus-exp02/0.3` adds 10
training archetypes and attempted to hold 4 domains out as OOD. Audit found
172 train/32 val distractor examples with holdout signatures; v0.4 fixes this (the v0.2 gate
never held out a domain, which is why it read .891 while probe transfer read .66). Two
arms, 3 epochs, MPS:

| arm | domain-OOD (full) | val | J@512 (n=62) | J@16384 (n=62) | D@16384 |
|---|---|---|---|---|---|
| baseline v0.2 frozen | — | — | .684 | .726 | .571 |
| v0.3 frozen | .573 | .931 | .722 | — | — |
| **v0.3 unfreeze-last-2** | **.673** | .949 | **.779** | **.756** | .511 |

- Isolated encoder adaptation gain at512 is +.057 on all62 (frozen v0.3 .722 →
  unfreeze v0.3 .779). The +.095 comparison to v0.2 also changes the corpus.
- **Sprint-2 gate NOT passed** — eff ctx at the .90 bar is still 0 at every depth.
  The earlier judge ≥ .70 floor claim was incorrect: control J=.6915. The 4K
  original cell is partial (n=4), and 8192/32768 are missing. Logged as a failed gate per R2.
- Score offsets and within-domain ranking both contribute. The terminal-only paired
  .711/pooled .614 diagnostic has no saved recipe and is withdrawn; independent OOD
  evaluation gives historical judge pooled .7104/macro within-domain .7400, vector .4272.
  Clean v0.4 vector judge falls to .2119. Calibration is not the sole bottleneck.
- Historical accepted stack: `line-attn` + dynamic-NTK(f6, window49152) + unfreeze2,
  `models/exp02d-unfreeze2`. It used contaminated v0.3 and is archived for reproduction.
  Clean experimental comparator is `models/exp02e-unfreeze2`; neither passes the gate.
  Position extension is deferred because quality already fails at control; it was not
  conclusively ruled out by a cache-dependent depth curve.

## Current next steps

1. Separate PDB arithmetic/text recipe has completed its new frozen curated eval
   (0 errors/112); the earlier2FN remain historical. Obtain independent task
   references, then integrate a new protocol and measure repetition under identical inputs
   and recorded backend/seed constraints. The real20-task pilot still fails proposed
   reliability; no P2 admission. Do not selectively retry UNKNOWN or retune current eval.
2. Confirm the fixed normalization recipe on untouched objectives and realistic
   candidate sets. Unfreeze@512 gain CI includes zero; .90 quality is not reached.
3. Improve within-domain transfer (clean vector judge .212) and define detect targets
   with matched-seed controls. Reject the joint-product pilot that reduced D.
4. If needed for the envelope decision, measure near-window placement within the
   full8192 HF input budget, including objective/tail; require n62 and zero cuts.
   Compare simple chunk aggregation before investing in a hierarchy.
5. Once quality is useful, optimize CPU against both M8 limits on66K and measure
   int8 M9. Current dossier passes but per-block p50 is192.40ms; M8 fails.

Execution and measurable criteria: [continuation report](research/audit-2026-10-03/AUDIT_RESOLUTION.md).
Do not spend on32K/64K or Track C while control/OOD quality remains below the bar.
