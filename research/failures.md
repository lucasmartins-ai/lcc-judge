# Failure Log — LCC-judge Research

Per `docs/08-roadmap.md:88` and `docs/05-benchmark-strategy.md:114`:
"Failures are benchmark results too: every negative result lands in `research/failures.md` with evidence and the change it motivated. Every gate failure triggers diagnosis, not escalation of architecture."

---

## FAIL-2026-10-03-01 — Sprint 2 Gate Failure: Effective Context ≥ 16K on Probe Suite v1.2

- **Date:** 2026-10-03
- **Sprint / Milestone:** Sprint 2 (Encoder Bake-off) — Gate requirement (`docs/08:33`)
- **Gate Statement:** "Chosen backbone reaches measurable effective context ≥ 16K at acceptable CPU cost — or documented evidence that no candidate does (which is itself a publishable finding and redirects to Track C or to abandoning >8K ambitions)."
- **Verdict:** **GATE FAILED (documented evidence branch satisfied, redirect activated).**

### 1. Measured Numbers & Verification

Independent audit (`research/audit-2026-10-03/AUDIT.md`, `verify.py`) recomputed metrics directly from raw rows without relying on the runner's AUC function:

| Depth (tokens) | Cases (n) | J pooled | D pooled | Status |
|---|---:|---:|---:|---|
| 0 (control) | 62 | 2658/3844 = .691 | 2252/3844 = .586 | Fails .90 bar |
| 512 | 62 | 2996/3844 = .779 | 2042/3844 = .531 | Fails .90 bar |
| 4096 | 4 (partial) | 12/16 = .750 | 10/16 = .625 | Incomplete / Fails .90 bar |
| 8192 | 0 | — | — | Missing |
| 16384 | 62 | 2907/3844 = **.756** | 1965/3844 = **.511** | Fails .90 bar |
| 32768 | 0 | — | — | Missing on accepted checkpoint |

- Effective context at the .90 bar: **0 for both detection (D) and judgment (J)**.
- Neither the control depth nor 16K reached the 0.90 AUC threshold.
- Historical 32K latency was ~37 s/block on MPS (v0.2, n=8), not CPU. It cannot certify
  CPU M8 or the accepted/clean checkpoint at 32K.

### 2. Independent Audit Findings (2026-10-03)

An exhaustive independent audit identified four blocking defects and five material qualifications:

1. **Holdout Leakage in Training Corpus (v0.3):**
   In `specialist/corpus.py:412`, negative unrelated distractors (`neg_unrelated`) drew from all domains in `DOMAINS` rather than restricting to `TRAIN_DOMAINS`. As a result, 172 train examples and 32 validation examples contained text signatures from the 4 holdout domains (`vector_drift`, `bot_traffic`, `pdf_render`, `sms_delivery`). "Held out ENTIRELY" was false.
2. **Dynamic RoPE Cache Non-Determinism:**
   Hugging Face's `dynamic_rope_update` decorator cached the maximum sequence length seen and did not reset for subsequent shorter sequences above `original_max_position_embeddings` (8192). On the accepted checkpoint, `booking_timeout/fact@8192` shifted from 0.486 to 0.642 (delta = 0.1557) when evaluated after a 20,000-position call. This violated input determinism (`docs/02:21`, requirement M7).
3. **Truncation Flag Masking in Harness:**
   `bakeoff/adapters.py` calculated truncation by comparing OpenAI tiktoken `cl100k_base` counts against Hugging Face tokenizer windows. In `specialist-exp02c-512@256`, 24/24 inputs were actually truncated by ModernBERT (563–607 HF tokens > 512), but recorded as `truncated=false`.
4. **Incomplete Coverage and Missing Redirect Decision:**
   4K was partial (n=4), 8K was absent, and `SPRINT_02_BAKEOFF.md` declared the redirect satisfied without formally choosing between Track C native pretraining and abandoning >8K ambitions.
5. **Unstratified Validation & Uncertified Epoch History:**
   `eval-limit 20` evaluated only the first 160 examples of OOD (all `vector_drift`), failing to cover all 4 holdout domains during epoch progress.

### 3. Root Cause Analysis

Quality fails even at control depth, so extending positions alone cannot solve the gate.
The earlier flat curve is consistent with a transfer problem, but does not establish
that positional representations were preserved: the RoPE cache was order-dependent.
Independent OOD re-evaluation found within-domain failures too (historical vector
judge AUC .427), so score offsets are only part of the diagnosis. The .711/.614
terminal diagnostic lacks a reproducible population/recipe and is withdrawn as
standalone evidence. Historical D results establish poor transfer; they do not prove
which training objective will fix it. CPU feasibility is measured separately below.

### 4. Formal Redirect Decision

In compliance with `docs/08-roadmap.md:33`:
1. **Option Selection:** Formally select the **abandonment of single-pass >8K sequence ambitions** for Sprint 2/3, rejecting premature investment in Track C native long-context pretraining.
2. **Working Architecture:** Adopt the **experimental working envelope of ≤8K tokens per block** with hierarchical block-level aggregation (the block-aware model planned for Sprint 4).
3. **Revised Sprint 2/3 Gate:**
   - Quality bar: AUC(d) ≥ 0.90 for both detect (P1) and judge (P2) across the ≤8K range on clean, uncontaminated OOD under calibrated scoring.
   - Latency budget: Compliance with M8 on reference CPU (<50 ms p50 warm per block, ≤43 s per dossier).

### 5. Changes Motivated & Corrective Actions Executed

1. **Deterministic Dynamic RoPE:** Implemented `make_rotary_deterministic` in `specialist/model.py`. Re-evaluating with dirty RoPE cache yielded delta = 0.000000 (verified by `check_score_order.py`).
2. **Exact Tokenizer Truncation:** Refactored `bakeoff/adapters.py` to count tokens using the model's actual tokenizer against effective limits. Zero false untruncated flags.
3. **Provenance & Transparency:** Added `device`, `run_id`, and `actual_tokens` per row in `bakeoff/runner.py`. Merge logic preserves multi-device history, and reports explicitly show `(n=...)` on partial depth cells.
4. **Data Leakage Elimination (Corpus v0.4):** Fixed `specialist/corpus.py` to draw `neg_unrelated` distractors strictly from `TRAIN_DOMAINS` for train/val splits and `HOLDOUT_DOMAINS` for OOD splits.
5. **Stratified Epoch Validation:** Fixed `specialist/train.py` so epoch-level validation covers all 4 holdout domains uniformly.
6. **Documentation Integrity:** Roadmap (`docs/08`) and Sprint 2 bake-off (`SPRINT_02_BAKEOFF.md`) updated with formal redirect; experiment log (`research/experiments.md`) corrected for chronological ordering and narrative errata.

---

## FAIL-2026-10-03-02 — Clean remediation pilots do not certify readiness

Historical remediation state; real replay was subsequently executed in
EXP-2026-10-03-08 / FAIL-2026-10-03-03 below.

- Clean v0.4 unfreeze, n=62: best raw J .824 at 4K; .90 gate still fails.
- Nominal 8K cuts 186/186 inputs; it does not test an untruncated native-window boundary
  or show that a hierarchy beats pair scoring.
- Joint detect product against independent frozen BCE reduces D by .0382 at 0
  (95% CI [−.0731, −.0049]) and .0453 at 512 ([−.0762, −.0166]). Original comparison
  mislabeled a head ablation of the joint model as an independent baseline.
- Clean unfreeze CPU: 66K context tokens, 100 blocks, no cuts; load+scoring 20.38 s,
  warm representative block p50 192.40 ms. Whole dossier passes; M8 overall fails.
  Old 16.11 s workload silently cut inputs and was smaller than the reference;
  a 64-token p50 cannot certify typical blocks. M9 int8 footprint was not measured.
- Original `data/d6_pilot` copied oracle keywords and labeled simulation as REPLAYED.
  Corrected to SYNTHETIC, zero P2 admission. .95 remains a proposal, not an empirically
  validated reliability threshold; real executor and outcome verifier are pending.
- The inherited normalization numbers lacked a saved recipe and used old scores.
  The clean saved continuation pilot is exploratory; at 512 the unfreeze gain CI
  crosses zero. None of its cells reaches the .90 joint quality bar.

Evidence: `research/continuation-2026-10-03/verification.json`,
`normalization-results.json`, `bench-cpu-unfreeze2.json`,
`research/detect-supervision-results.scores.json`, `data/d6_pilot/summary.json`.
Inherited artifacts are preserved under `research/continuation-2026-10-03/inherited/`.
Next: confirm normalization on untouched objectives/candidate mixtures; measure
untruncated near-window inputs only if needed for the envelope decision; supply real
resettable replay executors/verifiers; optimize CPU after quality is useful.

---

## FAIL-2026-10-03-03 — Actual replay fails proposed reliability, verifier calibration pending

120 real Hermes calls,20 tasks ×2 conditions ×3 repeats;120 distinct sessions.
Post-execution audit:5 NECESSARY,11 UNNECESSARY,4 UNKNOWN;80% concordance and20%
UNKNOWN fail the proposed≥95%/≤10% targets. Baseline60/60 and ablation39/60 pass;
one artifact is invalid JSON. No selective retries; all records training-ineligible.
Six coding cases have executable outcome checks;14 typed-answer contracts are
bounded proxies. Generation seeds cannot be set and the backend alias is mutable;
v0.1 also sent differing seed metadata between repeats. Therefore this does not
certify production D6 or a causal label generator with all variability controlled.

Audit found a verifier false negative: conservative maxUnavailable1 is valid for
the stated quorum/maintenance objective. Correcting three saved verdicts changed
one task NECESSARY→UNNECESSARY without changing the failed reliability verdict.
Original receipts/source are retained. Jev diagnostic disagrees with fixtures on
9 answers at the descriptive .5 threshold; it is not the label oracle.

Motivated changes: fix PDB check; remove unused seed from future prompt; normalize
protocol JSON before hashing; fix Jev call count119. Next: calibrate verifiers and
freeze admission threshold on separate data, then untouched repeated eval under
an explicitly documented backend/seed contract. Do not admit or scale these labels.
Evidence: `research/replay-real-2026-10-03/{REPORT.md,verification.json,evaluation-audit.json}`;
`data/d6_real_pilot/{summary.json,records.jsonl,protocol.json,episodes/}`.

---

## FAIL-2026-10-04-01 — Semantic checker rejects valid quantitative PDB decisions

Verifier challenge calibration selected .50 from80 controls, frozen before108 eval
controls. Aggregate provisional per-kind targets pass: code0FP/0FN on12/12;
typed0FP/2FN on42/42. Yet both FN are PDB:2 of3 correct reserved budgets rejected.
With7 healthy replicas and quorum4, maxUnavailable40% rounds up to3 and leaves4;
maxUnavailable2 leaves5. Both allow one voluntary eviction. Numeric code accepts;
Jev gives .40/.36 and the frozen semantic cutoff rejects.

Motivated change for the next protocol: compute percentages/quorum/type constraints
in code and restrict semantic review to textual allegations. Do not tune current
cutoff or rewrite expected labels after eval. The candidate is not integrated into
the previous pilot, and all challenge/pilot records remain training-ineligible.
Single-author, correlated controls and12/42 negatives do not certify production
verifier error or R19 repeatability. Ground truth of external tasks still required.
Evidence: `research/verifier-calibration-2026-10-03/{REPORT.md,verification.json,summary.json,frozen-threshold.json}`,
cases `c_9a5a6c1b74da0a2b` and `c_581587d2de2b72ca` in eval receipts.

---

## FAIL-2026-10-04-02 — Coupled whole-answer review rejects valid PDB controls

Follow-up `pdb-routing/0.1` froze its .50 cutoff and zero-error target before
56 development/112 eval controls. Both arms use the same exact numeric guard;
the coupled arm keeps whole-answer state/question, while the separated arm receives
verified facts and full prose. Coupled eval has0FP/27FN/UNKNOWN0 on48 positives
and64 negatives; separated has0FP/0FN/UNKNOWN0. Development coupled has5FN.
Four valid-budget families account for27FN: conservative integer8, max-percent7,
leading-zero-percent4, equivalent integer8. No selected retry or eval tuning.

This is a local observation with a representation/question change together,
not proof of a single causal model defect. Official pinned Go conversion and
independent policy enumeration match the candidate on4240/290752 numeric checks.
The newly attained curated target does not certify R19 or population error;
gateClaim gave DOWNGRADE after raw per-case evidence. Text labels share one author
and templates. All training admission remains0 and the old replay is unchanged.
Motivated decision: retain arithmetic in code, use the separated experimental
candidate for the next frozen replay only after validating task references.
Evidence: `research/pdb-routing-2026-10-04/{REPORT.md,verification.json,summary.json,protocol.json,receipts/,gate-raw-evidence.json}`.
