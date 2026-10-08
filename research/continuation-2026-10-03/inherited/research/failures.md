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
- Latency at 32K on CPU is quadratic (~37 s/block; 186 scores ≈ 1.9 hours).

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

The failure to reach the 0.90 AUC bar at 16K is **not positional**:
- The performance curve is depth-invariant: J is .691 at control, .779 at 512, and .756 at 16K; D is flat ~0.51–0.58 across all depths.
- Dynamic-NTK RoPE successfully preserved position representations up to 16K.
- The binding constraints are:
  1. **Domain Generalization & Score Calibration:** Arbitrary score offsets across domains (e.g. pdf_render vs sms_delivery differed by >6 logits). Within-domain discrimination is solid (within-domain paired AUC ≈ .71–.74), but pooling destroyed cross-domain ranking (.61–.71 pooled).
  2. **Zero Trained Detect Transfer:** Detection on unseen archetypes remained at chance (~0.51–0.58) because the head had no objective-aligned detection supervision.
  3. **Quadratic CPU Cost:** Evaluating full dossiers at 16K–32K on CPU without block partitioning violates latency budget M8 (<50 ms p50 warm per block).

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
