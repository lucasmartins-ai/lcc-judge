# 09 — Open Questions (v0)

Status: Sprint 0. Open means open: none of these are answered by preference, only by
evidence. Each question carries the experiment that would answer it where known.

## A. Core research questions (from the program, with experiment hooks)

| # | Question | How we answer it | Where it lands |
|---|---|---|---|
| Q1 | How much context do LCC decisions *actually* need? | distribution of critical-evidence positions in real dossiers + probe suite | S1–S2 |
| Q2 | Do current judges fail from model size or insufficient context? | Laya (small/short) vs Jev (larger/32K) error profiles vs position of evidence | S2 bake-off |
| Q3 | Does a small specialized encoder beat a larger generic one? | BL5 vs S3 specialist at matched eval | S3 gate |
| Q4 | What does block-aware reasoning specifically buy? | hierarchy vs pair scorer, same data | S4 gate |
| Q5 | What does >8K context buy? | utilization curves at 2K…64K | S5 gate |
| Q6 | Can a 30–100M model use 64K effectively? | multi-hop triads at depth; tier comparison | S5 |
| Q7 | Do outcome-backed labels beat relevance labels? | H3 controlled comparison (same backbone, two label sources) | S6 gate |
| Q8 | Does teacher distillation help or cap generalization? | train with/without teacher warm start; compare OOD | S3/S6 |
| Q9 | Can sufficiency be predicted reliably? | S1 calibration + false-sufficient ceiling | S7 |
| Q10 | Can model/reasoning needs be predicted before execution? | I1/I2 vs multi-config replay truth | S8 |
| Q11 | Can total inference be reduced while holding task success? | MSI-Bench: cost @ matched success vs deterministic planner | S8–S9 |

## B. Taxonomy questions (from 01 §8)

- B1: Is CONDITIONALLY_NECESSARY predictable from (block, set), or does it need
  task-state/plan features?
- B2: Are necessity and criticality separate heads or one distribution's tail?
  (shared-vs-separate-head ablation)
- B3: Should sufficiency output typed missing-evidence categories (closed enum) rather
  than free text? (probably yes — keeps the model non-generative)

## C. Architecture questions

- C1: Local-window + global block attention — or is a longformer-style sparse pattern
  enough? (latency/quality ablation, S2–S4)
- C2: How much block metadata earns its place? (per-feature ablation; prompt §11)
- C3: Does the custom tokenizer beat existing tokenizers enough to matter?
  (tokens/byte, tokens/code-line, effective-context gain; S1 study, E1 gate)
- C4: Is a pairwise relation module worth it beyond LCC's deterministic graph? (E3)
- C5: Incremental/block-cached scoring for `--append-to` workloads — can decisions stay
  stable under cache? (E7)

## D. Data questions

- D1: What is the real replay cost per reliable label? (S1 pilot → R19 reliability)
- D2: Can group ablations stand in for single-unit ablations at scale without label
  noise? (pilot)
- D3: How do we get ground-truthed *contradiction* and *supersession* pairs at scale?
- D4: What consent/anonymization pipeline is needed for REAL traces? (legal/ethical
  review before any real session enters training data)

## E. Decision questions for the founder (only the user can decide)

1. **Name** (DEFERRED to post-training, founder decision 2026-10-02): shortlist stays
   open in 06 until training reveals the model's real dimension; freeze + registry
   sweep happen at repo creation / model release time. Working title: `specialist`.
2. **Repository**: confirm creation of `lucasmartins-ai/[name]` at Sprint 2 (separate
   from LCC because it owns weights/training/datasets), and the LCC provider-adapter
   boundary.
3. **Compute budget ceiling** for S2–S3 (local MPS-only vs cloud GPU allowance).
4. **Real-trace policy**: which agent-session sources may enter training data
   (Hermes sessions, agenttrace-studio artifacts), and under what anonymization.
5. **Sprint cadence / gate authority**: who signs off gate failures (founder vs
   evidence-only rule).

## F. Meta question (the one that matters)

> If the specialist model cannot beat BL1 (deterministic LCC) + BL4 (Jev on demand) on
> the paired quality-cost frontier, is the model program stopped — or redirected to
> MSI-only heads (routing/verification) where local latency is the differentiator?

This decision rule should be agreed **before** Sprint 3 results exist, so the outcome
cannot be rationalized after the fact.
