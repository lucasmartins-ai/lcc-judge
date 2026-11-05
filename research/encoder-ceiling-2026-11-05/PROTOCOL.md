# Encoder quality check (step 1): protocol, written before data (2026-11-05)

## Question

Do frozen Granite block vectors plus a trained session layer rank context blocks better than the
shipped `specialist_v3` on new real sessions?

The test is the cheapest quality check of the encoder path, with cost ignored (offline, GPU allowed).
It tests one configuration:
- the full Granite 97M, frozen;
- a 512-token window;
- one session-layer recipe.

A pass says step 2 is worth building. A fail does not prove that no encoder could beat v3; a
fine-tuned encoder might. Stopping the encoder path on a fail is the owner's rule, a decision and
not a proof: a cheaper student distilled from a frozen teacher that lost is unlikely to win.

Each failed comparison is labelled one of two ways:
- **"inconclusive"** if its CI upper bound exceeds +0.02 on either metric;
- **"no gain shown"** otherwise.

**Why now.** Encoder spikes 1 and 2 were NO-GO on cost (`research/encoder-spike-2026-11-05/RESULTS.md`).
On 2026-11-05 the owner chose this order:
1. this test;
2. step 2, only if this test passes: a small distilled encoder with a 512-token window, encoding each
   block as it arrives, re-gated on cost;
3. otherwise a deterministic path: edge cases and LCC rules, no learned encoder.

## Data

**Train.** The `next-action-v2` train split, with the same exclusions as specialist v2's training
(`specialist_v2.item_rows`):
- no agent action;
- quarantined dev forks;
- jev-overlap lineage groups and their forks;
- no USED candidate.

That leaves **1,790 items**. Unlike v2, every candidate block is used: no negative subsampling.

**Dev.** The 325 eligible dev items. They are used only for early stopping and the selection grid
below. Dev already shaped v2 to v5, so dev numbers are not evidence.

**Test: held-out v4, a new build.**
- **Builder.** `research/heldout_v3.py` `build_phase` (code unchanged), cutoff
  `2026-10-18T00:00:00.000Z`, private root `~/.lcc/bench/heldout-v4`.
- **Why that cutoff.** Held-out v3 was built on 2026-10-17, so a session whose first record is on or
  after this cutoff is disjoint from it by construction.
- **Receipt.** Copied to this folder as `heldout-v4-receipt.json` (counts and sha256 only).
- **Count on 2026-11-05 23:18 UTC** (`heldout_v3 count`):
  - Claude Code: 118 sessions, 1,393 candidate items;
  - Hermes: 1 session, 19 items;
  - Codex: 0 sessions.
- **Independence from held-out v3.** The builder checks lineage against next-action-v1 only, so the
  study's build step adds two checks. It drops every new group that shares a session key with a
  held-out v3 item, and every new group content-linked to a held-out v3 item. Content links use
  `next_action_labels.content_links` with the builder's rule. Drops are counted in the receipt.
- **Groups.** Held-out items content-linked to each other (forks the lineage keys miss) have their
  groups merged (union-find) before groups are counted or resampled.
- **Population.** Primary = eligible items (agent action, at least one USED candidate) minus items
  content-linked to train/dev, as in the v3 final test.
- **Population file.** The build step writes the primary item ids with their final groups to a
  private file. Its sha256 and counts go into the receipt, and the test reads only this file.
- **Floor.** If the primary population has fewer than 60 session groups after the merge, the study
  stops here and reports counts only.
- **Labels.** The builder computes them. Before the freeze, labels are read only to decide
  eligibility for the population file. No score or metric on the held-out is computed until the
  freeze (below) is pushed.

**Labels (all sets).** Rule-based next-action evidence (USED). Results are tagged INFERIDO.

## Arms

| arm | role | what it is |
|---|---|---|
| `enc_feat` | primary | session layer over [Granite block vector, v3's 50 features] plus a goal token |
| `feat` | control | the same session layer and training, with the block and goal vectors removed |
| `v3` | reference | `specialist_v3` frozen (`model.json` sha256 `219cd798...`), `Judge.score(goal, texts)` |
| `recency` | sanity | `matched_budget_v2.cheap_scores`; reported, no gate |

**Vectors.**
- Encoder: `ibm-granite/granite-embedding-97m-multilingual-r2`, revision `835ad14`, PyTorch fp32 on
  MPS, CLS pooling. Weights frozen.
- Text: each block's text exactly as v3 receives it (store text with its render header).
- Window: 512 tokens. A longer block keeps its first 382 and last 128 tokens, between `CLS` and `SEP`.
- Goal: the item's goal is encoded the same way.
- Cache: vectors are stored privately per sha256 of the text.

**Session layer**, identical for both trained arms.
- Block input: Linear(vector 384 + 50 features → 128). Features are z-scored with train statistics.
- Goal token: Linear(goal vector 384 → 128) plus a learned type embedding. In `feat` the goal token is
  only the type embedding.
- Body: 2 pre-norm transformer encoder layers (d 128, 4 heads, FF 256, dropout 0.1). Full attention
  over every block of the item (protected blocks included) and the goal token.
- Items over 12,288 blocks run in consecutive chunks of 12,288, each chunk with the goal token. No
  train or dev item is that large.
- Head: Linear(128 → 1) per block.
- Score: logit − α · `log_chars` + 3.0 · `floor_mask`. This is v3's own score formula.
  `specialist_v3.floor_mask` uses v3's frozen `k_goal` = 1 and `k_err` = 2: it lifts the top block by
  goal BM25 and the two most recent error blocks.
- Why the floor: v3 has these safeguards for blocks the goal names and for recent errors. The USED
  labels drop evidence the goal already names, so without the floor a new arm could gain on the
  metric only by giving those blocks up.

**Training.**
- Loss: BCE on the candidate blocks, with each item weighing the same.
- Target: 1 if USED, 0.5 if goal-shared but not USED, 0 otherwise. This is the average of v3's two
  member targets: its GBDT learns USED, its LR learns USED-or-goal-shared
  (`specialist_v2.FROZEN_RECIPE`).
- Optimiser: AdamW, weight decay 0.01, one item per step, gradients accumulated over 8 items.
- At most 20 epochs. Early stopping on dev recall AUC with patience 3.

**Selection, on dev only, separately per arm.**
- Grid: lr in {3e-4, 1e-3}, α in {0, 0.5, 1.0}. Seeds 1, 2 and 3 for each lr.
- The arm's logit is the mean of the three seeds' logits. The score formula above is then applied.
- Pick the config with the highest dev recall AUC; ties go to dev all-kept AUC.
- Nothing else is tuned.

**Deviation allowed in advance.** If MPS produces NaN or fails, the same run repeats on CPU with the
same seeds, and the switch is reported.

## Freeze, then test (each run once)

1. **Freeze.** `FREEZE.md` plus `freeze.json` record:
   - the chosen configs;
   - sha256 of every model file, the study code, the vector cache index, the held-out manifest and the
     population file;
   - dev numbers for both arms.

   The freeze is pushed before the test phase.
2. **Test.** Refuses to run if any frozen hash differs. Scores all four arms on the primary population
   once. Writes `RESULTS.md` and `results.json` with aggregates only; per-item scores stay private.

## Metrics and gate

- **Metrics.** Recall AUC and all-kept AUC over drop budgets 0-60% (`matched_budget_v2.item_metrics` /
  `aggregate`), as in every block-judge result since v2.
- **Comparison.** Paired bootstrap of mean(A − B) over session groups: 2,000 resamples, 95% percentile
  CI, seed 20261105, `specialist_v2_test.cluster_boot`.
- **Pass(A over B).** The CI lower bound is > 0 on at least one metric and > −0.02 on the other.
  −0.02 is the non-inferiority margin of the v3 final test.

| hypothesis | comparison |
|---|---|
| H1 | `enc_feat` over `v3`, plus guard G |
| H2 | `enc_feat` over `feat` (do the vectors add anything?) |
| H3 | `feat` over `v3`, plus guard G (does the session layer alone add anything?) |

**Guard G (goal-shared evidence).** Neither the floor nor the target guarantees that a trained arm
keeps blocks the goal names, and the USED metric cannot see them. So H1 and H3 count as passed only if
the trained arm is also non-inferior to v3 on **goal-shared recall AUC**:
- the same recall AUC, with the goal-shared candidates as positives;
- computed on primary items that have at least one goal-shared candidate;
- passes when the paired CI lower bound is > −0.02.

There is no multiplicity correction. The three results are read together through the table below,
which is fixed now.

| result | next step |
|---|---|
| H1 and H2 pass | step 2: distil a small encoder (512 window, encode on arrival), cost gate 500 MB / 2 s |
| H3 passes, and H1 or H2 fails | the feature-only session layer is the candidate; no encoder; its own cost gate |
| H1 passes, H2 and H3 fail | the gain cannot be attributed; the owner decides |
| H1 and H3 fail | the encoder path closes; the owner's deterministic fallback |

**Reported without a gate:**
- recency;
- results by source;
- recall and all-kept at 30% and 60%;
- the all-eligible population, content-linked items included;
- the dev numbers;
- passes on the 35-case edge suite at 30, 50 and 70% for both trained arms, against v3's 28 / 23 / 20.
  This is a non-regression check on hand-made cases; v3's selection looked at them.

## Limits, stated now

- **INFERIDO labels.** USED is what the agent reused next, found by rules. The labels lean recent and
  drop evidence the goal already names. v3 was trained on the same labels.
- **One user, one tool.** The test is almost all of the owner's Claude Code sessions, so provider
  neutrality is not tested.
- **Not measured:** cost (that is step 2), quality against LLM judges, and the effect of the 512-token
  window against a longer one.
