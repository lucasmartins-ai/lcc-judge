# Specialist v5: selection rule (pre-declared)

Written and committed on 2026-10-18, before any v5 candidate was scored on the 325 dev items and before the sealed
edge v2 was opened. Code: `research/specialist_v5.py` (`select` implements steps 1-3, `final` step 4).

## What was used to build v5 (and therefore is not evidence)

- **Dev-edge v2** (81 visible cases, `tests/fixtures/edge_cases_v2/`) and the **old 35-case suite**: detectors were
  designed and tuned by reading their failures.
- **A seeded sample of 300 TRAIN items** (`train_guard`): a regression guard for real sessions (v5 - v3 per-item
  AUC). v3 was fit on these items, so the guard is in-sample for v3.
- **Opus system-1 answers** (`research/teacher_v5.py`) on candidates from the train sample and from dev-edge:
  used to measure and tune detector patterns (precision / recall), never as a relevance target.
- Not used: the 325 dev items, the spent test split, the held-out v3 set, the sealed edge v2.

## Candidates (4 configs, fixed grid)

Score = v3 score (frozen) + bonus for blocks a strong detector protects + 0.25 x bonus for weak ones
(goal_xling). Blocks over 1,000 chars get no bonus. `stale` and `hedge` are flagged only (no score change).

- bonus in {2, 3} (v3 logit units; v3's own floor is 3)
- stages in {stage 1 only, stage 1 + cascade stage 2 (value_conflict, qualifier_link on at-risk blocks)}

v3 itself is the control.

## Rule

1. **Dev (325 eligible dev items, next-action v2 strict USED, full-text scoring as live).** Paired group
   bootstrap of the per-item AUC difference v5 - v3 (2000 resamples over session groups, seed 20261018, 95% CI).
   Eligible only if the CI lower bound is > -0.005 for **both** recall AUC and all-kept AUC.
2. **Old edge suite (35 cases).** Passes >= v3 at each of the 30, 50 and 70% cuts.
3. **Dev-edge v2 (81 cases).** Pass total over the three cuts strictly above v3's.
4. **Pick** the eligible config with the most dev-edge v2 passes (sum of cuts); ties -> most old-edge passes ->
   max dev recall AUC + 0.25 x all-kept AUC.
5. **Budgets (hard, measured on the pick with v3's bench method):** median latency < 250 ms on dev, peak RSS
   < 300 MB, model file (v3 members + rule parameters) < 1 MB; CPU only; no new dependencies.
6. **Sealed edge v2 (49 cases)**, opened once after steps 1-5 are written to `v5-dev-results.json`, with
   `research.specialist_v5 final`: v3, the v5 pick, BM25, recency and Claude Opus 5.5 (same keep question and
   batching as the earlier LLM arms, run only here, counted inside the 1,500-call cap). Reported per cut and per
   edge type. **This is the honest number.** It is reported whether it favours v5 or not; no tuning after it.

## Adoption

v5 is a candidate for the LCC provider port only if steps 1-5 pass. The sealed result decides how the gain is
described: if v5's sealed pass count at 50% is not above v3's, the dev-edge gain is reported as not generalising.

## Disclosures

- Dev-edge v2 and the old suite took part in design; their counts are not held-out evidence.
- The sealed cases were written by the same generator and prompt as dev-edge (same author, Opus), so the sealed
  number measures generalisation to new cases of the same kind, not to real sessions.
- One raw case (plan 0) was read during the generator smoke test and was forced into dev before the split.
