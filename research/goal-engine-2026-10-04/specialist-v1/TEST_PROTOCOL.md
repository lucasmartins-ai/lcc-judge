# Specialist v2: pre-registered test protocol

Written and pushed before any frozen test item is opened. The machine-readable copy with every hash is
`test_protocol.json` (written by `python -m research.specialist_v2_test protocol`). The runner
(`python -m research.specialist_v2_test run`) refuses to start if any hash differs from the files on disk,
re-checks every frozen test item against the test manifest, and refuses a second run once
`test_results.json` exists. No training, tuning or model choice happens after the run.

## What is frozen

- Model: `~/.lcc/bench/specialist-v2/model.json` (logistic regression, 50 features, target "USED or
  goal-shared", size penalty alpha 0.5), sha256 `0788f115fae5216358feddcfd119826cc0af196ca7b157cd8d00c4ecfe80696c`. Retrained on 2026-10-12 after the block-metadata
  hardening (commit 065f60f) with the recipe already chosen on dev (`FROZEN_RECIPE` in
  `research/specialist_v2.py`); no new selection.
- Code: sha256 of `research/specialist_v2.py`, `specialist_v2_test.py`, `matched_budget_v2.py`,
  `matched_budget.py`, `next_action_labels.py`, `edge_suite.py`, `edge_cases_build.py`,
  `real_context_bench.py`, and LCC's `relevance/compactor.py` + `blocks.py` (the mechanical pass).
- Labels: the v2 extractor (`next_action_labels.relabel_item`) applied to the 675 frozen test items for the
  first time inside the run, with the generic-feature list computed from v2 train groups (hash pinned). Test
  items manifest sha256 `a9450f04...` (labels-receipt.json, unchanged since the freeze).
- Edge suite: the 35 fixtures (`tests/fixtures/edge_cases`, directory hash) and the saved specialist v1 / Laya
  edge scores.

## Population

- Eligible: test items with agent-action evidence and at least one USED candidate block.
- Primary: eligible items not content-linked (`next_action_labels.content_links`, copied prefixes) to any
  train or dev item. `all_eligible` is reported as a secondary view.

## Arms

specialist v2 (shipped LR), recency, BM25, LCC mechanical, random (mean of 5 seeds), and the old specialist
(v1, exp02 ModernBERT head) on a seeded subset of 12 primary items per source (~30 s per item on CPU).

Jev is not run on test: it needs paid remote calls. The Jev comparison stays on jev-overlap dev (43 items)
and needs an owner-approved paid run on test. Saved v0.1 Jev scores of frozen-60 dossiers that happen to
fall in test are reported descriptively only, with no gate.

## Metrics

Recall of USED tokens and all-kept (every USED block kept) at 10-60% of candidate tokens removed; AUC by
trapezoid over 0-60% (0% = 1.0), normalised to 0-1. Reported overall, per source and per request category.

## Acceptance (all three must hold; otherwise FAIL)

1. On primary, specialist v2 mean recall AUC and mean all-kept AUC are above each of recency, BM25 and
   mechanical, and the paired bootstrap 95% CI of mean(v2 - baseline) per-item AUC has lower bound > 0 for
   both metrics against each of them (2000 resamples of session groups, seed 20261012).
2. Edge suite: specialist v2 passes >= every other arm (recency, BM25, mechanical, random, drop_largest,
   drop_smallest, specialist v1, Laya) at 30, 50 and 70% removed.
3. Cost on the primary test items, fresh process, 1 thread: median <= 250 ms per item, p90 <= 1000 ms,
   peak RSS <= 300 MB.

## Known weaknesses stated before the run

- Criterion 2 is expected to FAIL. The edge fixtures and the frozen model are both fixed, so the test-run edge
  counts equal the dev counts in DEV_RESULTS.md: the re-fit LR passes 24/20/13 at 30/50/70% against
  mechanical 22/21/18 (the pre-hardening LR passed 24/21/18). The model is not re-selected to fix this: that
  would be tuning on the edge suite. The edge suite also informed the LR-over-GBDT choice, so it is not
  held-out evidence either way. Ties would pass (>=).
- Labels are rule-based and lean recent; results are tagged INFERIDO in TEST_RESULTS.md.
- Latency is measured on a shared, loaded machine.
