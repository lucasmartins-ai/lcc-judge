# Experiment Log

Format per program §38: every experiment records hypothesis, configuration, dataset,
model, tokenizer, context length, training method, seed, hardware, metrics, result,
interpretation and decision. No important result exists only in terminal output.

---

## EXP-2026-10-03-02 — EXP-04: domain-diversity corpus (v0.3) + encoder adaptation — gate NOT reached, mechanism isolated

**Hypothesis / pre-registration.** EXP-03-01 showed the transfer collapse is depth-invariant
and domain-bound. Two candidate causes, one variable each: (a) the training corpus holds out
templates/subjects but never DOMAINS, so the head learns field-vocabulary priors instead of
"anomalous vs healthy value"; (b) the frozen encoder cannot represent unfamiliar archetypes.
Pre-registered read: probe suite v1.2 (62 cases, pooled AUC, bar .90) at depth 0 (control)
and 16384 (the gate depth), same dynamic-NTK position recipe in all arms (single variable
changes only at the training layer).

**Configuration.**
- `corpus-exp02/0.3` (`data/exp02d/`, 2340/810/960, hash-disjoint): +10 new training
  archetypes (api_contract, geoshard_routing, audit_log_gap, cost_runaway,
  fraud_false_positive, i18n_missing, image_pull_failure, monitoring_flap, pii_in_logs,
  grpc_deadline) — none of them is a probe v1.2 archetype *by construction* (different
  incident semantics; verified: no probe `case_id` shares its full domain token set with
  a corpus domain). 4 domains (`vector_drift`, `bot_traffic`, `pdf_render`,
  `sms_delivery`) held out ENTIRELY as the OOD split; `neg_unrelated` now draws its
  decisive line from a *different* domain's vocabulary (the v0.2 distractor was
  same-domain/different-subject, so it could not test "is this line about the
  objective"). Length stream unchanged (mean 335 words).
  *(Audit note 2026-10-03: `specialist/corpus.py:412` drew unrelated distractors from all
  domains including holdouts, producing 172 train and 32 val examples with holdout tokens;
  corrected in v0.4).*
- **Contamination audit (self-check, run after the numbers above):** 9 of the 10 new
  domains are token-disjoint from every probe archetype, but `monitoring_flap` shares its
  skill with the probe case `raft_leader_flap` (both "count state transitions during an
  incident"). Sensitivity measured: dropping `raft_leader_flap` moves J@16384 .756 → .750,
  J@512 .779 → .772, J@0 .691 → .685 (J moves ≤ .006), and D@16384 .511 → .495 (a drop
  of .016, > .006). The conclusion (gate failed, calibration-bound) is unchanged; the honest
  count of truly unseen probe archetypes is 53 of 62, not 54.
- Two arms, ModernBERT + `line-attn`, MPS, batch 8, max_len 1024, 3 epochs:
  **frozen** (0.39M trainable) and **unfreeze-last-n 2** (10.42M, lr-encoder 2e-5).
- Measured on probes v1.2 at depths 0 / 512 / 16384, window 49152, rope dynamic factor 6,
  all cells untruncated, 0 errors. Gate metric = pooled AUC; paired (within-case) AUC
  reported as diagnostic only.

**Result (OOD gate first per R2 — full split, 960 items, 4 unseen domains).**

| arm | OOD full | val full | OOD partial / val per epoch (ep1→3) |
|---|---|---|---|
| frozen line-attn | .573 | .931 | .304/.659 → .345/.829 → .364/.883 |
| unfreeze-2 (10.4M) | **.673** | .949 | .287/.936 → .383/.964 → .389/.975 |

Probe suite v1.2, pooled AUC (n=62; new54 / old8 in parentheses):

| depth | baseline exp02c-v0.2 | frozen v0.3 | unfreeze-2 v0.3 |
|---|---|---|---|
| 0 (control) | .554 / .657 | .563 / .657 | .586 / **.691** (.594/.685) |
| 512 | .561 / .684 | .549 / .722 | .531 / **.779** (.465/.761) |
| 16384 | .571 / .726 | — | .511 / **.756** (.465/.749; .766/.859) |

Case-set labels: "all62" = the v1.2 suite as built; "new54" = the 54 cases authored in
v1.2 (old8 = the original 8, which are near-copies of v0.2 training archetypes); of the
new54, 53 have no token overlap with any v0.3 training archetype (`raft_leader_flap`
shares `monitoring_flap` — see the contamination audit below; ≤ .006 J effect).

**Interpretation.**
1. **Both interventions help the judge, neither reaches the bar.** Unfreeze-2 lifts pooled
   J@16384 .726 → **.756** and J@512 .684 → **.779**; new54 J@16K .700 → .749, new54
   J@512 .661 → .761. Real gains in unseen archetypes (+.05 to +.06 on new54, not +.10
   isolated from unfreeze alone), but eff ctx at the .90 bar remains 0 — **the Sprint-2
   gate is NOT passed.**
2. **Encoder adaptation is the effective lever, not corpus diversity alone**: frozen v0.3
   gains almost nothing over the v0.2 baseline while unfreezing the last 2 layers buys
   +.057 on all62 (.048 on new54) on the probe judge.
3. **In-domain vs domain-OOD gap WIDENS with training** — val .936→.975 while full-split
   domain-OOD stays .673 (unfreeze) / .573 (frozen).
4. **Per-domain offsets are arbitrary** (measured on the 4 holdout domains, unfreeze
   arm): pdf_render fact −2.74 vs decoy −4.76 while sms_delivery fact +0.14 vs decoy −1.82.
   Within-domain paired AUC .711 vs pooled .614.
5. **Detect family remains at chance**: new54 D runs .46–.59 across complete depths
   (0, 512, 16K); all62 is .586 (0), .531 (512), .625 (4K partial, n=4), .511 (16K).

**Decision.**
- **Sprint-2 gate: NOT passed.** Recorded in `research/failures.md` (FAIL-2026-10-03-01).
- **Formal redirect:** Per `docs/08:33`, project formally redirects to an experimental
  envelope of ≤8K tokens per block with hierarchical block aggregation (Sprint 4);
  single-sequence >8K ambitions paused for Sprint 2/3.
- Accepted architecture: `line-attn` pooling + dynamic-NTK rope (factor 6, window 49152)
  + `--unfreeze-last-n 2`. Checkpoint `models/exp02d-unfreeze2`.
- Next levers, in priority order:
  1. Fix harness (deterministic RoPE, exact truncation flags, run provenance) — DONE.
  2. Rebuild uncontaminated corpus v0.4 and retrain short baseline arms.
  3. Domain-agnostic score calibration pilot at 0/512.
  4. Complete 4K and 8K coverage; evaluate ≤8K envelope against M8 CPU budget.

---

## EXP-2026-10-03-01 — probe suite v1.2 (8 → 62 cases): the 16K "near-miss" was a case-set artifact

**Hypothesis / pre-registration (before measuring).** The Sprint-2 boundary read
(J@16K = .891 = 57/64 pairs, one pair-tie from the .90 bar) sits inside n=8 noise.
Expanding the curated suite with independently authored cases (anti-contamination
path, kept separate from the training generator) will (a) resolve the boundary and
(b) test whether the original 8 cases were representative. Gate metric unchanged:
pooled AUC(d) = P(score(fact@d) > score(noise@d)) over ALL case pairs (n²), bar .90.

**Configuration.** `bakeoff/probes.py` PROBE_VERSION 1.2: 54 new `ProbeCase` entries
authored by hand (not generated), same construction rules as v1.1 (fact/decoy share
keys and differ only in values; length-matched — max fact/decoy token delta ≤ 4 on
all 62; log level drawn uniformly; one length-matched unrelated distractor). Depth
grid unchanged. `bakeoff/runner.py --cases` now builds only the selected cases (the
full 62-case deep grid cost real time per batched invocation). Baseline checkpoint
unchanged: `models/exp02c-line-attn` via the `specialist-exp03-dynamic-49k` adapter
(dynamic-NTK rope factor 6, window 49152), MPS, all cells untruncated, 0 errors.
Depths 0/512/4096/8192/16384 run with n=62; 32768 still n=8 (not re-run).

**Result (pooled AUC, gate metric; old8/new54 split in parentheses).**

| depth | n | D | J | D old8/new54 | J old8/new54 |
|---|---|---|---|---|---|
| 0 (control) | 62 | .554 | .657 | — | — |
| 512 | 62 | .561 | .684 | — | — |
| 4096 | 62 | .562 | .743 | — | — |
| 8192 | 62 | .563 | .741 | .781 / .529 | .906 / .718 |
| 16384 | 62 | **.571** | **.726** | .781 / .537 | .891 / .700 |

- **Reproducibility exact**: old8 cells at 8192/16384 reproduce the EXP-03 numbers
  to three decimals (.781/.906 and .781/.891) — same pipeline, only the case
  composition changed.
- **The original 8 probe cases are quasi-in-domain**: 7–8 map 1:1 onto the
  `corpus.py` training archetypes (disk_quota↔disk_quota, retry_storm↔retry_storm,
  auth_regression/config_drift↔config_change, queue_backlog↔pool_saturation,
  cache_stampede↔cache_perf, session_leak↔sweep_jobs, booking_timeout↔http_status).
  The EXP-02c "transfer" numbers were inflated by domain overlap.
- **Failure is depth-INVARIANT, not positional**: on all62, J runs .657 (control)
  → .743 (4K) → .726 (16K) [on new54: .639 → .722 → .700] — no decay with depth; detect
  is flat .55–.57 at every depth *including control*. Dynamic rope keeps the curve flat
  to 16K exactly as designed; context length is not what is failing.
- Pooled vs within-case (paired) AUC at 16384 on new54: .700 vs .815 — cross-case
  score calibration accounts for ~.11 of the gap; the discriminating skill itself
  holds on 44/54 new cases (fact > decoy within case), 10/54 inverted.

**Interpretation.**
1. **Sprint-2 gate fails decisively on the honest suite**: eff ctx at the .90 bar =
   0 for both families on v1.2 (J@16K .726 vs .90). The "one-pair near-miss" was a
   sampling artifact of a small, domain-overlapping case set — n=62 (3844 pairs)
   makes the boundary question moot rather than resolving it in our favor.
2. **The binding constraint is domain generalization of the trained skill**, not
   positions and not (yet) adaptation: the head reaches only J≈.66–.74 on unseen
   archetypes even at control depth with the decisive line alone in front of it.
3. **Detect family is at chance on unseen archetypes** (.55–.57 pooled, at every
   depth) — the EXP-02c watch-item ("detect at control is weaker") is now quantified:
   line-attn learned to detect *known* incident shapes, not evidence-vs-noise
   generically.
4. Metric discipline: the gate stays on the pre-registered pooled AUC (cross-objective
   comparability); paired AUC is reported as a diagnostic only.

**Decision.**
- Probe suite v1.2 is now the gate instrument (62 cases, 1/3844 pair granularity);
  the old8 stay reported for continuity but the gate read is quoted on all 62 with
  the clean54 split shown.
- Gate stays OPEN; diagnosis revised: the next spend is **training-side domain
  diversity** (corpus v0.3: +10 new training archetypes, 4 held out *entirely* as a
  domain-OOD gate so the per-epoch gate predicts probe performance) ± **encoder
  unfreeze** (the planned adaptation run) — logged as EXP-2026-10-03-02.
- Rope/position extension is no longer the suspected bottleneck and is not re-run.

---

## EXP-2026-10-02-05 — EXP-03: position extension 8K→32K, measured with the line-attention head

**Hypothesis / pre-registration (before measuring).** The EXP-02c head + extended
positions can hold the decision signal at 16K–32K depth. Acceptance (Sprint 2 gate,
docs/08): **measurable effective context ≥ 16K** (AUC ≥ 0.90 per family) — with the
judge ≥ 0.70 floor from EXP-02c kept as the secondary read.

**Configuration.** Same trained checkpoint (`models/exp02c-line-attn`) — single
variable at the position layer, head frozen (it already extrapolates to ~10K).
Position extension is config-level in transformers 5.x (RoPE per layer type:
`sliding_attention` θ=10K / `full_attention` θ=160K; no new weights). Two variants,
window 49152 (verified untruncated at depth 32768 — smoke test: 49K tokens / 1,404
lines, ~60 s/fwd MPS):
- `exp03-extrap-49k`: rope untouched (pure extrapolation past the 8192 training max);
- `exp03-dynamic-49k`: `rope_type=dynamic` (NTK-aware, factor 6) — inert below 8192,
  stretches wavelengths beyond (verified formula semantics in modeling_rope_utils).
Infra: `bakeoff/runner.py` merge now cell-granular (model, depth, case) + `--cases`
filter so deep grids build in <600 s batches. Eval on **MPS** (CPU quadratic cost at
32K ≈ 144 s/block); depths 8192/16384/32768, probe v1.1, n=8.

**Result (all AUCs; untruncated everywhere; gate read at the .90 bar).**

| model | depth | D | J | fact | decoy | unrel | p50 MPS |
|---|---|---|---|---|---|---|---|
| exp02c-12k (baseline, CPU) | 8192 | .859 | .875 | .45 | .13 | .14 | 9.0 s |
| exp03-extrap-49k | 8192 | .859 | .875 | .45 | .13 | .14 | 2.0 s |
| exp03-extrap-49k | 16384 | .781 | .891 | .64 | .18 | .30 | 7.4 s |
| exp03-extrap-49k | 32768 | .641 | .719 | .61 | .30 | .50 | 38.4 s |
| exp03-dynamic-49k | 8192 | .781 | .906 | .43 | .12 | .18 | 2.0 s |
| exp03-dynamic-49k | 16384 | .781 | .891 | .44 | .09 | .17 | 9.0 s |
| exp03-dynamic-49k | 32768 | **.750** | **.828** | .40 | .12 | .17 | 37.1 s |

**Interpretation.**
1. **Position extension works as designed and is measurable**: dynamic-NTK holds
   judge **.828 at 32K untruncated** (fact .40 vs decoy .12 — clean value separation)
   while pure extrapolation degrades to .719 with noise scores drifting up (.50 — the
   familiar length-drift reappearing in encoder space). First measured win for rope
   adaptation: +.11 judge at 32K, one variable changed.
2. **Strict gate NOT passed**: eff_ctx at the pre-registered .90 bar is 16384 minus
   one pair-tie (J@16K = .891 = 57/64 for both variants; J@32K dynamic = .828).
   The secondary judge ≥ .70 floor, however, holds at EVERY depth through 32K with
   dynamic (extrap only barely at .719). n=8 → 1/64 granularity: the .891 vs .90
   boundary is inside noise; the 60+ case expansion decides it.
3. The EXP-02c 8K regression check is exact (extrap@8192 = baseline 12K cell:
   D .859/J .875, means identical to 3 decimals) — pipeline reproducibility confirmed.
4. Cost is the real 32K problem: p50 37 s/block MPS (~144 s CPU), quadratic in depth.
   Block-aware per-block scoring keeps this off the hot path in LCC, but a 32K
   *state* scored whole is not shippable at this latency.
5. Remaining lever to clear .90 @16K: **adaptation** (unfreeze encoder on long
   blocks — the EXP-02b under-trained control at 4+ epochs, now with long-context
   curriculum). The aggregation head and the position config are no longer the
   suspected bottlenecks.

**Decision.**
- EXP-03 outcome = **near-miss at the strict bar, positive at the floor**: recorded
  per R2 without quoting as a pass. Sprint-2 gate stays OPEN pending (a) the 60+
  case probe expansion and (b) the adaptation run.
- Dynamic-NTK (factor 6) becomes the default position recipe for the specialist
  stack; pure extrapolation is retired as the 32K option.
- Next: adaptation run with long-block curriculum; probe expansion 8→60+ (independent
  authoring path) to resolve the .891 boundary; then Sprint-3 block-aware
  architecture design starts from an evidenced baseline.

---

## EXP-2026-10-02-04 — EXP-02c: line-level aggregation head (the structural fix) — **ACCEPTANCE PASSED**

**Hypothesis.** (H2, seeded by EXP-02b): aggregating the decision signal at LINE
granularity instead of pooling the whole block into one vector beats the measured
dilution cliff. Pre-registered acceptance (unchanged from EXP-02b): **judge ≥ 0.70
held at depth 256–512 on curated probes v1.1.**

**Configuration.** `specialist/model.py` gained two pooling modes (line ids derived
from the fast tokenizer's offset mapping — count of newlines before token start — so both
remain ONE encoder forward pass):
- `line-max`: per-token scorer → max within line → max over lines (multiple-instance
  learning; gradient flows only through the current argmax line).
- `line-attn`: line representation = mean of token hiddens per line → learned
  attention over lines → existing head (dense gradient through the softmax).
`specialist/train.py`: `--pooling line-max|line-attn`; optimizer fix (all non-encoder
trainable params — including the line scorer — join the head param group; before this
the new scorer would never have been updated). Training: corpus v0.2 (`data/exp02b/`),
3 epochs × ~175 s each on MPS (per-epoch checkpoint + `--resume`), batch 8,
lr-head 1e-3, max_len 1024, seed 0, ModernBERT frozen, **0.39M trainable params**.
Hardware: Apple M1 Max 64GB. Checkpoints: `models/exp02c-line-max/`,
`models/exp02c-line-attn/`.

**Result (full OOD gate, gate-first per R2).**

| run | OOD AUC (full) | val AUC | train AUC | note |
|---|---|---|---|---|
| line-max, 3 ep | 0.511 | 0.481 | **0.506** | does not even fit TRAIN — MIL pathology |
| line-attn ep 1 | 0.834 | 0.855 | — | immediate jump, ~5× the mean-pool signal |
| line-attn ep 2 | 0.879 | 0.888 | — | |
| line-attn ep 3 | **0.891** | 0.897 | — | vs mean-pool 0.511 / token-attn 0.492 |

**Probe transfer (curated v1.1, `bakeoff` runner, CPU).**

| model | window | D@0 | D@64 | D@256 | D@512 | J@0 | J@64 | J@256 | J@512 |
|---|---|---|---|---|---|---|---|---|---|
| specialist-exp02c-512 | 512 | .58 | .73 | .70 | .69 | .72 | .89 | **.92** | **.78** |
| specialist-exp02c-1k | 1024 | .58 | .73 | .72 | **.95** | .72 | .89 | **.95** | **.83** |
| specialist-exp02-512 (v1.0 rows, baseline) | 512 | .81 | .28 | .44 | .45 | .69 | .47 | .56 | .33 |
| specialist-exp02-8k (v1.0 rows, baseline) | 8192 | .81 | .28 | .23 | .00 | .69 | .47 | .47 | .42 |

**ACCEPTANCE: judge ≥ 0.70 at depth 256 AND 512 → PASS** (.95/.83 with the 1K window;
.92/.78 with the 512 window). First time any neural candidate holds P2 judgment at
depth on the curated probes; the previous head collapsed to .42–.56 off-control.

**Interpretation.**
1. **The dilution cliff was a pooling failure.** Same encoder (frozen ModernBERT),
   same corpus, same optimizer — changing only the aggregation granularity takes OOD
   0.511 → 0.891. Line-level attention over ~40 segments surfaces the value-match
   signal that whole-block mean/token-attention pools erase below ~10% decisive share.
2. **Dense gradient is what makes it learn.** Hard max over lines (`line-max`) starves:
   with ~40 lines the decisive line rarely wins the initial argmax, so its gradient
   almost never fires (train AUC 0.506 after 3 epochs — classic MIL search pathology).
   Softmax attention over lines touches every line each step and converges in one
   epoch (0.834). For H2 the aggregation must be line-level AND differentiably dense.
3. **The EXP-02 length bias does not reappear**: v0.2 is length-decorrelated and the
   line-attention weights normalize away line-count effects; judge stays ≥ .78 through
   depth 512 (with the window that doesn't truncate — 24/24 blocks truncate at the
   512 window at depth 512, and the score drop .95→.78 tracks exactly that).
4. New watch-item: **detect at control is weaker** (.58 vs EXP-02's .81 on v1.0 probes)
   — the head learns necessity judgment before detection polish; also the baseline rows
   above are probe v1.0, so cross-version comparisons stay indicative (curves, not
   cells).
5. n = 8 cases (1/64 AUC granularity): the PASS is a gate result, not a precision
   claim — the 60+ case expansion (queued) is what turns this into a publishable
   number.

**Follow-up (same day): full 0–8192 curve + window extrapolation.** Depth-granular
merge added to `bakeoff/runner.py` (stale rows dropped per (model, depth), so long
curves build in batches); `specialist-exp02c-8k` adapter added (same head, no
truncation up to 8K). All cells probe v1.1, CPU, n=8:

| adapter | window | D@512 | D@1K | D@2K | D@4K | D@8K | J@512 | J@1K | J@2K | J@4K | J@8K |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exp02c-512 | 512 | .69 | .44 | .75 | .63 | .53 | .78 | .30 | .45 | .69 | .55 |
| exp02c-1k | 1024 | .95 | .48 | .72 | .44 | .67 | .83 | .42 | .59 | .75 | .69 |
| exp02c-8k | 8192 | .95 | .73 | **1.00** | .69 | .38† | .83 | .91 | .94 | **.89** | .61† |

† = 24/24 blocks truncated (depth-8192 blocks + objective exceed even the 8K window).
eff_ctx (bar .90) for exp02c-8k: **detect 2048 / judge 2048** (J@4K = .891, one
pair-tie from the bar at 1/64 granularity — curves, not cells).

**EXP-03 baseline cell (same day): the 8K drop was truncation, not positions.**
`specialist-exp02c-12k` (same head, 12K window) at depth 8192, **untruncated**:
**D=0.859 / J=0.875** (fact .45 vs decoy .13 — clean separation; p50 8.96 s/block CPU).
The un-extended backbone (training max 8192) already reads ~10K-token inputs
zero-shot; the .38/.61 @8K cells were a tokenizer-window artifact.

1. **The aggregation head extrapolates zero-shot in length**: trained at ≤1024 tokens
   (~40 lines), it holds judge .89 at 4096 and .88 at ~10K tokens (~700 lines) with
   no length training. The head is not the long-context bottleneck.
2. **Position extrapolation past the training max is also surprisingly free** (≤10K
   tested) — but 16K/32K remain untested and are the real EXP-03 question. Position
   extension config path confirmed (transformers 5.x `rope_parameters` per layer type:
   `sliding_attention` θ=10K window 128 / `full_attention` θ=160K; extension =
   `rope_type: dynamic|linear` + factor + `max_position_embeddings`, no new weights).
3. Truncation remains the dominant failure mode wherever it occurs (both capped-window
   adapters past their window, and the 8K window itself at depth 8192). Eval cost at
   32K is quadratic on CPU (~144 s/block) → EXP-03 measurement must run on MPS or a
   reduced grid.
4. H2 strengthened: block-aware line aggregation holds **judge ≥ .78 at every depth
   256→8192 untruncated** (pre-registered acceptance was .70 @256–512) on the same
   backbone where raw cosine detection decayed to .58 and the mean-pooled trained head
   was .00 detect @512.

**Decision.**
- **EXP-02c acceptance PASSED** — logged as the first empirical win for the block-aware
  line-level aggregation design (H2); seed of the Sprint-4 architecture. Not quoted as
  a Sprint-2 gate pass (that gate is ≥16K effective context — still open, EXP-03).
- Next: EXP-03 (position extension 8K→32K) now measured with the line-attention head
  as instrument; full 0–8192 curve for exp02c; rerun the full bake-off on probe v1.1
  for a clean single-version table (current results.json mixes v1.0/v1.1 rows, tagged).
- Still open: 4-epoch `--unfreeze-last-n 2` adaptation control; replay pilot (20 tasks)
  for outcome-backed P2 labels.

---

## EXP-2026-10-02-03 — EXP-02b: length-decorrelated corpus + the dilution-cliff diagnostic chain

**Hypothesis.** (a) Length-decorrelating the corpus (the EXP-02 measured length bias)
recovers robust depth judgment (acceptance: judge ≥ 0.70 at depth 256–512 on curated
probes); (b) if not, isolate the mechanism by single-variable controls.

**Configuration.** Corpus v0.2 (`corpus-exp02/0.2`, `data/exp02b/`): block length drawn
from an independent stream (120–700 words, built to target for every kind — verified:
label=1 mean 325 words vs label=0 mean 336; per-kind 325/339/333). Probes upgraded to
v1.1 (matched middle lengths; log level uniform across kinds — removes the v1 ERROR↔fact
cue). Six controlled training runs on MPS (ModernBERT frozen + 0.2M head unless noted):
see result table. Also implemented attention pooling (`--pooling attn`) and fixed the
transformers-5.x layer path for `--unfreeze-last-n`.

**Dataset.** train 2,400 / val 640 / ood 960 (same domain/template/subject splits as
v0.1, hash-disjoint). Class: SYNTHETIC. Auxiliary sets: `data/exp02b_short` (≤250
words), `data/exp01_padded` (v0.1 + ~100-word tails), `data/exp02b_taildec` (decisive
line moved to block end).

**Result (all AUCs = full OOD gate).**

| run | data | change vs baseline | OOD AUC |
|---|---|---|---|
| baseline (EXP-02) | v0.1 (40-word blocks) | — | **0.729** |
| repro-check | v0.1 | current code | 0.696 (trajectory matches) |
| v0.2 mean-pool | v0.2 (mean 330 words) | length-decorrelated corpus | 0.511 |
| v0.2 short ≤250w | v0.2-short (mean 185 words) | same, short blocks only | 0.504 |
| v0.1 padded | v0.1 + 100-word tails (140 words) | tail length only | 0.621 |
| v0.2 taildec | v0.2, decisive line last | position only | 0.507 |
| v0.2 attn-pool | v0.2 | learned token-gated pooling | 0.492 |
| v0.2 unfreeze-2L (1 ep) | v0.2 | 10.2M params adapted | 0.525 |
| BoW logistic (probe) | v0.2-short | lexical linear model | **0.750** |

**Interpretation (the dilution cliff).**
1. The corpus is learnable (BoW 0.75) and the training code is clean (repro matches
   EXP-02). The v0.2 failure is not data correctness, not code, not position.
2. Everything orders by **decisive-token share** (≈15 evidence tokens / block tokens):
   27–37% → learns (0.73); 10.7% → 0.62; ≤8% → chance (0.49–0.52). Below ~10% share,
   neither mean pooling nor learned attention pooling over *frozen* representations can
   surface the value-match signal; 1 epoch of shallow encoder adaptation does not
   restore it either.
3. This is a measured architectural argument for the program's core bet (H2): decision
   signal must be aggregated at **line/block granularity** (score local segments, then
   max/attention over segment scores — exactly the block-aware design of docs/03 §2),
   not by pooling a whole 300-token block into one vector.
4. The EXP-02 length *bias* (mean-score drift with input length) and the *cliff*
   (signal loss below a share threshold) are two distinct failure modes; the v1.1
   probes and v0.2 corpus now isolate both.
5. Caveat: the unfreeze test is 1 epoch only — under-trained for 10M params; a 3–5
   epoch run is needed before closing the "adaptation works" question.

**Decision.**
- EXP-02c (next, the structural fix): **line-level aggregation head** — per-line
  scoring (local encoding) + max/attention aggregation over lines; acceptance stays
  judge ≥ 0.70 at depth 256–512 on curated v1.1 probes. If it works, it is the first
  empirical win for the block-aware architecture and the seed of the Sprint-4 design.
- Parallel: 4-epoch `--unfreeze-last-n 2` run as the adaptation control.
- The acceptance criterion for EXP-02b (judge ≥ 0.70 held at depth) is NOT met —
  recorded as a failed gate with the mechanism measured, per docs/07 R2 discipline.

---

## EXP-2026-10-02-02 — EXP-02: first trained necessity decision head (ModernBERT)

**Hypothesis.** A minimal decision head trained on a programmatic, anti-memorization
necessity corpus (a) learns the P1/P2 skills beyond chance on held-out generators, and
(b) transfers to independently authored probes; frozen-encoder + head is sufficient
when the *data* is designed against memorization (the September failure was data, not
the frozen-encoder recipe per se).

**Configuration.** `specialist/` package (corpus.py, model.py, train.py). Backbone:
ModernBERT-base frozen (0.2M trained params: Linear 768→256→GELU→Dropout→1), mean
pooling; BCE-with-logits; AdamW lr_head 1e-3, wd 0.01; batch 16; max_len 512; 3 epochs;
seed 0; temperature fitted on val only (grid NLL) → T = 0.35.

**Dataset.** `data/exp02/` — programmatic corpus `corpus-exp02/0.1`: 8 domains
(http_status, disk_quota, config_change, pool_saturation, cache_perf, retry_storm,
sweep_jobs, deploy_rollout), each with anomaly/healthy *value pairs*, 2 train + 2 OOD
paraphrase template families, and subject-name pools split train/OOD (70 vs 50 names,
zero overlap). Labels: pos = decisive line with anomaly values for the objective's
subject; negatives = healthy-value lookalike (P2) or other-subject line, sometimes
anomalous (distractor anomaly). Anti-shortcut controls: log level independent of
label (verified: label rate ≈1/3 across all four levels), objective mentions subject
via name or alias. Splits disjoint by content hash. Sizes: train 3,200 / val 800 /
ood 1,200. Class: SYNTHETIC (generator + seed recorded).

**Models.** EXP-02 head as trained (window 512) and same head scoring at the encoder's
native 8K window (window-length transfer test). **Training method.** Frozen encoder +
head, 3 epochs. **Seed.** 0. **Hardware.** Apple M1 Max, MPS, 62 s/epoch.

**Metrics.** Corpus: AUC (Mann-Whitney), OOD gate reported before in-domain every
epoch. Probes: the bake-off P1/P2 suite (8 curated cases × 8 depths), same protocol as
EXP-01 for comparability.

**Result.**
- Corpus OOD gate: AUC 0.650 → 0.696 → **0.729** (val 0.627 → 0.683 → 0.723). OOD ≥ val
  at every epoch — no overfitting signature.
- Curated probes (transfer, zero overlap of cases/objectives with training):
  - Control depth 0: **detect 0.81, judge 0.69** — best calibrated judge at control
    (raw ModernBERT cosine 0.45; minilm-ce 0.58; laya-typed 0.70 but uncalibrated).
  - Window-512 variant: signal washes out with added filler (detect 0.28–0.64 across
    depths, ≈chance).
  - Window-8K variant: all three kind-means drift upward together with input length
    (fact .55→.77) and AUC *inverts* below chance at depth (detect 0.00 @512, 0.11
    @1024) — noise_unrelated probe blocks run ~55 tokens longer than fact blocks and
    the length bias ranks them higher.

**Interpretation.**
1. *Learnability confirmed*: P1/P2 skills are learnable by a 0.2M head on a frozen
   encoder when data is programmatic and anti-shortcut — transfers to independently
   written cases at control depth (0.81/0.69). This is the first positive evidence
   for H1's trainability claim.
2. *Length generalization is the measured gap*: the head carries an input-length score
   drift (longer block ⇒ higher P(evidence)) that inverts rankings beyond training
   lengths. Enlarging the window without length-matched training makes it *worse*,
   not better. EXP-02b must decorrelate length from label (matched-length negatives,
   long tails) and the probe suite needs v1.1 (matched middle lengths — the ~55-token
   confound is a harness flaw, amplified but not created by the model's bias).
3. Consistent with EXP-01 #3: the September recipe fails on data design, succeeds on
   data design — the recipe (frozen encoder + small head) is not the villain.
4. n = 8 curated cases; control-depth cells are indicative; the drift curves are the
   evidence.

**Decision.**
- EXP-02b (next): retrain with length-decorrelated corpus + length-matched probes
  (v1.1); acceptance = judge ≥ 0.7 held at depth 256–512 on curated probes.
- Keep the 512 envelope as the current LCC-relevant regime (LCC clips scoring inputs
  to ~4K chars); long-context remains EXP-03's problem (position extension), now with
  a trained head as the measuring instrument.
- The trained head becomes the standard "trained-judge" baseline row in the bake-off.

---

## EXP-2026-10-02-01 — Encoder bake-off: effective-context probe suite (Sprint 2)

**Hypothesis.** (a) Off-the-shelf encoders/judges expose a usable *detection* signal
for evidence buried at depth in realistic filler, with measurable effective-context
curves well below declared windows; (b) no off-the-shelf model performs value-level
*necessity judgment* (incident vs healthy lookalike); (c) the Laya decision-judge
lineage cannot see beyond its ~1K state window regardless of input length.

**Configuration.** Harness `bakeoff/` (probes.py, adapters.py, runner.py). Two probe
families × 8 depth placements × 8 task cases × 3 block kinds:
- P1 `detect`: incident line vs unrelated filler (critical-recall analogue).
- P2 `judge`: incident line vs healthy lookalike, same vocabulary, values differ
  (necessity/value semantics — lexical-trap-free by design).
- Control depth 0 = decisive line alone. Depth = tiktoken cl100k tokens (fact placed
  at ~depth−48, 256-token tail). Seeds fixed per (case, depth, kind); deterministic.
- Scoring: Laya judges via `laya.load(...).predict` with LCC's exact `keep_question`
  phrasing (compactor.py), batch 1, raw (bypassing LCC's 831-token production budget
  refusal to probe raw model behavior); cross-encoder sigmoid(logit); bi-encoders
  mean-pooled cosine rescaled to [0,1]; lexical baseline = content-word overlap.

**Dataset.** 8 curated probe cases (`bakeoff/probes.py` CASES): log/terminal dossiers
with one decisive incident line and plausible healthy decoys. Class: CURATED (builder:
this experiment; selection rule: low objective↔fact lexical overlap, values carry the
answer).

**Models.** lexical-overlap (BL0); convaiinnovations/laya-multilingual;
convaiinnovations/laya-typed-decisions; ~/Models/laya-lcc-relevance-v1 (the 2026-09-23
fine-tune); cross-encoder/ms-marco-MiniLM-L-6-v2 (22.7M); BAAI/bge-small-en-v1.5
(33.4M); answerdotai/ModernBERT-base (149M, 8K window);
Alibaba-NLP/gte-multilingual-base (306M) — **load failed** (`trust_remote_code`
required; not enabled), recorded as failure.

**Tokenizer / context length.** Each model's own tokenizer with truncation to its
declared window (512 / 1024 / 8192); depth measured in tiktoken cl100k.

**Training method.** None (zero-shot probing). **Seed.** Per-block seeds as above.

**Hardware.** Apple M1 Max, 64 GB RAM, 10 cores; CPU inference (`--device cpu`),
single process per batch; Python 3.14.3, torch 2.14.0, transformers 5.17.0, laya
0.3.7 (LCC venv). RSS = ru_maxrss delta per batch process (max-only, cannot decrease).

**Metrics.** AUC(d) = P(score(fact@d) > score(noise@d)) over 8×8 case pairs;
effective context = largest depth with AUC ≥ 0.90; p50 latency per (objective, block)
call; load time; RSS delta. Full rows: `bakeoff/results/results.json`; tables:
`bakeoff/results/RESULTS.md`.

**Result (headline rows, AUC @ depths 0/256/512/1K/2K/4K/8K).**
- ModernBERT-base — detect: .75/.81/**.88**/.77/.64/.64/.58 · judge: .45–.73, ≈chance
  · p50 187 ms @256 tok, 3.1 s @4K, 8.0 s @8K.
- laya-multilingual — keeps everything (fact/noise means .85–.95 both), detect ≈.5 at
  every depth · p50 ~360 ms flat from 512 to 8K tokens (silent truncation at its
  1024 max_len: content beyond is invisible).
- laya-typed-decisions — only model clearing the bar anywhere: detect .92 at depth 0
  (control), .67 at 64, ≈.5–.78 beyond · judge ≈chance.
- laya-lcc-relevance-v1 (the fine-tune) — detect **.28 at depth 0 control** (worse
  than chance on entirely new evidence lines), ≈.44–.70 beyond · judge ≈chance.
- minilm-msmarco-ce — detect .89 at control decaying to .50 at 512 (window edge) ·
  judge ≈chance · fastest learned scorer (9–35 ms).
- bge-small-en-v1.5 — ≈.5–.7 both families; cosine dilution severe even at depth 0.
- lexical-overlap — detect .72–.78 flat (depth-insensitive, unbounded) · judge .49–.57
  (by construction cannot separate values).
- gte-multilingual-base — load failure (see Models).

**Interpretation.**
1. *Detection at depth is real but nobody is good at it out of the box.* ModernBERT's
   cosine curve is the best available and still only reaches .88 at 512 tokens and
   decays with depth — usable as a warm-start signal, not a judge.
2. *Value-level necessity judgment (P2) is unclaimed territory* — every model sits at
   chance. Supports H1 (relevance ≠ necessity is a distinct learning problem) and
   confirms the heads must be trained, not borrowed.
3. *Third independent confirmation of the memorization finding*: the fine-tune scores
   worse than chance on novel evidence at the control depth — its September in-domain
   numbers did not survive contact with new data (consistent with LAYA.md §8 finding 2).
4. *Silent truncation is the real effective-context mechanism*: Laya accepts 8K-token
   inputs at flat latency and judges nothing past ~1K — declared window ≠ used window
   (R5 confirmed as an observed phenomenon, not a fear).
5. *CPU cost grows steeply with block length* on the 8K encoder (quadratic regime:
   8 s @8K vs 187 ms @256) — strong cost argument for the block-aware local-attention
   architecture bet and for per-block scoring over whole-dossier states.
6. n = 8 cases ⇒ AUC granularity 1/64; single-cell values (e.g. J@4K = .80) are
   indicative only. Curves, not cells, carry the evidence.

**Decision.**
- **Track B confirmed as primary path**: ModernBERT-base-class backbone (native 8K,
  best detection curve, faster than Laya at equal depth) + trained typed decision
  heads. Track C (native architecture) stays gated: the ≥16K candidate space for small
  encoders is thin, which *strengthens* the case for position-extension adaptation —
  to be tested next (Sprint 2 continuation).
- Next experiment (EXP-02): train a minimal decision head on ModernBERT over the
  P1/P2 probe families (expanded corpus) as the first Track-B training target, with
  an OOD split from day one.
- Next experiment (EXP-03): position-extension (RoPE/ALiBi-style adaptation or
  continued pretraining) to push ModernBERT-class encoders from 8K toward 32K, with
  this same probe suite as the acceptance curve.
- Open fix: gte-multilingual-base retry with `trust_remote_code=True` (vendor custom
  code; requires an explicit go-ahead) or substitute snowflake-arctic-embed-m-v2.0.
- Probe suite becomes part of MSI-Bench v1 (long-context probes, docs/05 §4).

---
