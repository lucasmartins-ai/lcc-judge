# 08 — Roadmap (v0)

Status: Sprint 0. Each sprint has a **gate**: a measured condition that must hold before
the next sprint's investment. Gates exist to make overengineering expensive (prompt §42).

## Sprint 0 — Discovery (this document set)

Produce: architecture analysis, task + decision taxonomy, training-target taxonomy,
repository relationships, model requirements v0, baseline inventory, risk register,
naming candidates, dataset/benchmark strategy. **No training.**
Gate: founder review of the Sprint-0 conclusions (name shortlist, build-vs-adapt,
next-sprint tasks).

## Sprint 1 — Specification + baselines

- Freeze native output schema (`lookaspecialist-result/0.1`), dataset record schema
  (`looka-dataset-record/0.1`), LCC adapter contract (provider interface).
- Context IR integration confirmed against LCC `ir.py` + MSI `context-ir/0.1`.
- Freeze MSI-Bench v1 + long-context probe suite (schemas + splits by content hash).
- Run and archive baselines BL1–BL4 (mechanical, Laya, laya-lcc-relevance-v1, Jev) under
  the new protocol; BL5 (generic encoder + heads) harness built.
- Remove-and-replay harness prototype (label reliability check on 20 tasks, R19).
Gate: benchmark protocol produces reproducible rows for ≥ 4 baselines with paired
quality+cost; replay labels agree on ≥ threshold of repeated ablations (threshold set
from the pilot's own distribution).

## Sprint 2 — Encoder bake-off

- Track A vs Track B candidates (ModernBERT-class, Laya lineage, long-context encoders):
  quality, **effective context curve** (2K…32K probes), latency, RAM, CPU feasibility.
- Position-extension experiments on the best candidate (up to 32K).
- Decide native-architecture need (Track C) from measured gaps only.
Gate: chosen backbone reaches measurable effective context ≥ 16K at acceptable CPU
cost — or documented evidence that no candidate does (which is itself a publishable
finding and redirects to Track C or to abandoning >8K ambitions).
Status (2026-10-03): GATE FAILED (effective context = 0 for both detect and judge at
AUC ≥ 0.90; independent audit confirmed numbers and isolated data leakage + harness bugs).
Formal Redirect Decision: Formally selected the redirect option of abandoning single-pass
>8K sequence ambitions for Sprint 2/3. In place of premature investment in Track C native
long-context pretraining, the project adopts an experimental working envelope of ≤8K tokens
per block with hierarchical block-level aggregation (aligning with Sprint 4).
Additional experimental Sprint 2/3 quality/cost gate: ModernBERT backbone + line-attn pooling reaches AUC(d) ≥ 0.90 on
both detect and judge across the ≤8K envelope on uncontaminated OOD under calibrated scoring,
satisfying the CPU latency budget M8 (<50 ms p50 warm per block, ≤43 s per dossier).
This adds to the Sprint 3 Pareto gate below; it does not replace it. The hierarchy
is a proposed redirect, not a measured win. Current clean measurements still fail
quality at control/4K, cut every nominal-8K prompt, and miss the CPU per-block target.
The inherited 20-task replay was synthetic. A separate pilot now has 120 actual
Hermes calls with bounded fixture checks, giving 80% concordance and20% UNKNOWN;
it fails the proposed .95/.10 targets. Verifier calibration and an empirically
justified admission threshold remain unvalidated, so Sprint 1 replay reliability
and the D6 outcome-backed prerequisite remain unmet. See
`research/replay-real-2026-10-03/REPORT.md` and
`research/audit-2026-10-03/AUDIT_RESOLUTION.md`.
Update2026-10-04: verifier challenge calibration on80/108 curated controls selected
semantic cutoff .50 before eval; provisional per-kind error targets pass, with2 PDB
false negatives. External task-reference validation and repeated replay R19 remain
unmet. This does not certify P2 admission or replace the .95 repeat-concordance
proposal. See `research/verifier-calibration-2026-10-03/REPORT.md`.
Further update2026-10-04: exact PDB arithmetic before text consistency achieved
0FP/0FN/0UNKNOWN on112 new curated eval controls; coupled review had27FN with the
same guard/cutoff. This is a point observation (gateClaim DOWNGRADE), with a
shared archetype and single-author text labels. No independent task-reference
validation or repeated R19 certification yet; P2 admission remains0. See
`research/pdb-routing-2026-10-04/REPORT.md`.

Status 2026-10-08 (goal-engine track, `research/goal-engine-2026-10-04/`).
All figures below are exploratory point observations on exposed or single-author
populations (INFERIDO, not MEASURED; gateClaim DOWNGRADE where the receipts say so).
Every learned candidate is rejected: P1 (`REPORT.md`), semantic CPU-v2
(`semantic-tool-cpu-v2/`), compact relation (`compact-relation-v1/`), tool-role
support (`tool-role-support-v1/`), relation support (`tool-relation-support-v1/`),
factorized relation (`factorized-relation-dev-v1/`), varied-relation fresh
confirmation (`varied-relation-confirm-v1/RESULTS.md`: all three seeds below the
immutable scalar shadow, .874211 pooled / .899835 within-goal AUC), the
goal-interpreter probe (`goal-interpreter-probe-v1/RESULTS.md`: correct binding
197/240) and the two support/field pilots (`goal-support-pilot-v1/`,
`goal-embedding-pilot-v1/`; supplementary metadata audits in each
`audit-metadata-v2.json`). The only useful observed path is the deterministic
`rank_observations` route (`observation-lcc-pilot/RESULTS.md`: 36/36 on six
exposed authored tasks, 92.50%/98.10% mean byte removal at 8K/32K); it does not
interpret free text, and the typed API still lacks per-observation UTC time,
field and unit in current records (`TYPED_API_METADATA_GAP.md`). P2 admission
remains 0. Next cycle: `goal-family-corpus-v1/PLAN.md`; its section 5 stop
criterion closes the learned route to shadow-only (with `rank_observations` as
the product path) on any fresh-confirmation gate failure, two consecutive
validation failures, two failed human reviews, or too few genuine requests by
2026-12-31.

## Sprint 3 — First specialist (necessity/criticality/redundancy)

- Train heads B2/B3/B4 on outcome-backed D6 + curated D2 (Stage 3 curriculum).
- Calibration fitting; ABSTAIN mechanics; policy integration behind feature flag.
Gate: on frozen eval, specialist beats BL1–BL5 on critical recall @ matched reduction
**or** on reduction @ matched critical recall — one of the two Pareto directions must
hold, OOD suite must pass before any number is quoted (R2).

## Sprint 4 — Block-aware model

- Local token encoder + global block reasoner vs the Sprint-3 pair-scoring baseline.
- Metadata feature ablations (each feature earns its place).
Gate: hierarchy beats simple pair scorer with significance; else simplify (R12).

## Sprint 5 — Long-context native

- 32K then 64K effective context; probe-suite utilization curves.
Gate: 32K utilization beats 8K on multi-hop triads; 64K only if 32K pays (R5).

## Sprint 6 — Outcome-backed training at scale

- Replay/ablation/outcome-delta pipeline scaled (D6 growth); necessity label taxonomy
  complete (NECESSARY…UNKNOWN); H3 test: outcome-backed vs relevance-only training.
Gate: H3 evidence is conclusive in one direction; dataset yield per replay-dollar is
documented (R1/R14).

## Sprint 7 — Sufficiency

- Set-level head (S1): sufficiency + typed missing-evidence; restoration integration
  with LCC bounded restore.
Gate: sufficiency calibration usable (ECE gate); false "sufficient" rate under ceiling
set from baseline distribution.

## Sprint 8 — MSI heads

- Complexity/risk/routing/reasoning/verification heads (T2/T3, I1–I6), incremental.
Gate per head: trustworthy dataset exists + beats the deterministic planner
(`choose_route`) and the triage gate on false-de-escalation (R17).

## Sprint 9 — Outcome prediction

- `P(success | candidate plan)` research (I7/O2) on multi-config replay receipts.
Gate: calibration evidence on held-out plans; otherwise report as exploratory only.

## Sprint 10 — Optimization

- ONNX, INT8/INT4, batching, block-cache, CPU tuning; export pipeline; model releases.
Gate: quantization regression within tolerance; latency budget M8 met on reference CPU.

## Standing rules across sprints

- Experiment log + `research/failures.md` updated every sprint (prompt §38–39).
- Every gate failure triggers diagnosis, not escalation of architecture.
- Repo creation (`lucasmartins-ai/[name]`) happens at Sprint 2 decision, not before.
- LCC integration always via provider/adapter; LCC's deterministic safety layers never
  get bypassed by the learned path.

## Dependency view

```text
S0 discovery ──► S1 spec+baselines ──► S2 bake-off ──► S3 first specialist
                                                     │
                        S3 ──► S4 block-aware ──► S5 long-context
                        S3 ──► S6 outcome-backed (needs replay scale from S1)
                        S6 ──► S7 sufficiency ──► S8 MSI heads ──► S9 outcome
                        S4/S5/S7 stable ──► S10 optimization
```
