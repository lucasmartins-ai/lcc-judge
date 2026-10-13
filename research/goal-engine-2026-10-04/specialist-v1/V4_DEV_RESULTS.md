# Specialist v4: dev results (Opus-distilled teacher + supersession / contradiction / coreference features)

Produced by `python -m research.specialist_v4 {extras|subset|train|select|eval}` on 2026-10-13. This file has
counts and aggregates only, with no session text. Machine-readable copy: `v4-dev-results.json`.
- The selection rule (`V4_SELECTION_RULE.md`) was committed in 44a1d5c, before any candidate was scored.
- The spent test split was not opened.
- The post-2026-10-12 held-out set was not read.

## Bottom line

**v4 is not adopted.** Under the pre-declared rule, only v3 itself (base v3, beta 0) is eligible, so v3 stays the
shipped specialist. Two signals pulled in opposite directions:

- **The Opus teacher fixes edge cases but costs dev all-kept AUC.** Every teacher config passes more edge cases
  than v3 (up to 29/27/26 vs 28/23/20). Each one also lowers dev all-kept AUC, and the drop is significant for
  every beta >= 0.25: -0.008 to -0.091. Dev recall AUC does not move (all CIs cross 0).
- **The new features alone (no Opus) improve dev but not the edge suite.** v3n with beta 0 raises dev all-kept
  AUC by +0.0087 [+0.0028, +0.0148] and recall by +0.0022 [-0.0005, +0.0058]. On the edge suite it scores
  27/24/20, one case below v3 at 30%, so the rule rejects it.

Reading (INFERIDO): Opus judges generic relevance ("prefer keeping when unsure"). Those labels move the model
toward goal-matching and recent assistant text, and away from what the agent actually re-used next, which is
what the next-action labels measure. The patterns we targeted are not what the teacher learned. Its largest
coefficients are goal length, BM25 vs goal, recency and block size; the 14 new features get small weights.

## Recipe

- **New features (EXTRA, 14 columns, regex and key bookkeeping, CPU only):**
  - rule_marker, user_rule
  - reversal_marker, reversal_near
  - summary_marker
  - value_facts, value_conflict, value_changed_later, latest_value_holder (same subject with different values
    across blocks)
  - ref_start, ref_antecedent (a later text turn opens with a pronoun or says "isso" / "that error")
  - early_user_turn
  - reread_path, path_edited_later
- **Hardening and tests.**
  - Role, kind and tool still come only from `s2.block_meta` (header trusted only at offset 0, monotonic
    message index). A forged-header test covers `user_rule`.
  - The first 50 columns are bit-identical to v2's `featurize`, checked by a test.
- **Teacher labels.**
  - Claude Opus 5.5 via `llm_judge_arm --set train`: subscription CLI, ANTHROPIC_* stripped, no tools, same keep
    question and batching as the Jev arm.
  - Frozen targeted subset of 306 TRAIN items (hermes 208, claude 52, codex 46), chosen by the cheap pattern
    heuristics. `train_guard` refuses dev, quarantined dev forks, jev-overlap items and test.
  - Up to 32 candidate blocks per item: pattern blocks, their neighbours and the last 3 text turns.
  - 9,789 blocks labelled, 0 unscored. Opus mean keep-probability 0.474; 48% of blocks at >= 0.5.
- **Models (train only, v2's fit_lr defaults, no dev tuning).**
  - `lrg4`: LR on the 64 features with v2's USED-or-goal-shared target (513,352 rows).
  - `teacher`: LR on the 64 features with Opus soft labels. Fit correlation with the Opus labels: 0.53.
- **Grid (pre-declared).**
  - base: v3 (v2 LR + v2 GBDT) or v3n (lrg4 + v2 GBDT);
  - beta: {0, 0.25, 0.5, 1, 2} x teacher logit;
  - v3's size penalty and floor are kept unchanged.

## Opus calls

1,459 CLI calls out of the 1,500 cap. This total includes:

- 2 smoke calls;
- 19 failed calls that were retried;
- 3 usage-limit stops.

The first chunk (3 shards x 479 max) stopped on usage limits (HTTP 429) after 908 calls. After the reset, the
remaining 549 calls finished all 306 items with no limit hit.

## Selection (pre-declared rule; dev = 325 eligible items, row-based scores as in v3 select)

Diffs are paired group bootstrap vs v3: 2000 resamples of 107 session groups, seed 20261013, 95% CI.

| config | edge 30/50/70 | recall vs v3 | all-kept vs v3 | eligible |
|---|---|---|---|---|
| v3, beta 0 (= v3) | 28/23/20 | 0 | 0 | yes (control) |
| v3, beta 0.25 | 30/26/20 | +0.0010 [-0.0010, +0.0030] | -0.0095 [-0.0161, -0.0021] | no |
| v3, beta 0.5 | 28/26/22 | +0.0014 [-0.0015, +0.0041] | -0.0187 [-0.0285, -0.0098] | no |
| v3, beta 1 | 28/27/23 | -0.0002 [-0.0052, +0.0046] | -0.0428 [-0.0578, -0.0274] | no |
| v3, beta 2 | 29/27/26 | -0.0061 [-0.0139, +0.0021] | -0.0908 [-0.1122, -0.0690] | no |
| v3n, beta 0 (no Opus) | 27/24/20 | +0.0022 [-0.0005, +0.0058] | +0.0087 [+0.0028, +0.0148] | no (edge 30%) |
| v3n, beta 0.25 | 30/26/20 | +0.0005 [-0.0014, +0.0026] | -0.0082 [-0.0151, -0.0012] | no |
| v3n, beta 0.5 | 29/26/21 | +0.0021 [-0.0007, +0.0050] | -0.0131 [-0.0230, -0.0031] | no |
| v3n, beta 1 | 29/27/23 | +0.0003 [-0.0044, +0.0046] | -0.0405 [-0.0547, -0.0253] | no |
| v3n, beta 2 | 29/27/25 | -0.0055 [-0.0133, +0.0021] | -0.0867 [-0.1069, -0.0650] | no |

The edge counts were part of the rule, and the features were designed after reading the failing fixtures, so
no edge number here is held-out evidence.

## Diagnostic candidate: v3n, beta 1 (full-text scoring, as live)

**Not adopted.** It was chosen after selection, as the config with the most edge passes among those with dev
recall >= v3. It shows what the teacher buys and what it costs.

Dev, 325 items (MEDIDO):

| arm | recall AUC | all-kept AUC |
|---|---|---|
| v4 candidate (v3n, beta 1) | 0.8875 | 0.4041 |
| v3 | 0.8872 | 0.4446 |
| v3n, beta 0 (no Opus) | 0.8894 | 0.4533 |
| recency | 0.7894 | 0.3080 |
| bm25 | 0.7867 | 0.2641 |
| mechanical | 0.7844 | 0.2428 |

- **Candidate vs v3:** recall +0.0003 [-0.0044, +0.0046]; all-kept -0.0405 [-0.0547, -0.0253].
- **Candidate vs baselines:** recall about +0.10 over recency, BM25 and mechanical; every CI excludes 0.
- **Recall by source, candidate vs v3:**
  - claude 0.893 vs 0.904 (n=97);
  - codex 0.937 vs 0.925 (n=80);
  - hermes 0.857 vs 0.856 (n=148).
- **jev-overlap (43 items), recall / all-kept:**
  - candidate 0.885 / 0.397;
  - v3 0.886 / 0.419;
  - Jev 0.818 / 0.337;
  - bm25 0.809 / 0.291.

## Edge suite (35 synthetic cases, single-author gold)

| arm | 30% | 50% | 70% |
|---|---|---|---|
| Claude Opus 5.5 (LLM arm) | 35 | 35 | 35 |
| v4 candidate (v3n, beta 1) | 29 | 27 | 23 |
| v3 | 28 | 23 | 20 |
| v3n, beta 0 (no Opus) | 27 | 24 | 20 |
| mechanical | 22 | 21 | 18 |
| bm25 | 21 | 20 | 18 |

Passes per category at 30/50/70%:

| category | n | candidate | v3 | no-Opus | v3 beta 2 | Opus |
|---|---|---|---|---|---|---|
| approve_or_pick | 2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| correct_approach_or_rule | 1 | 1/1/0 | 1/1/0 | 1/1/0 | 1/1/1 | 1/1/1 |
| environment_and_infra | 4 | 2/2/2 | 3/2/2 | 3/2/2 | 3/2/2 | 4/4/4 |
| external_accounts_and_comms | 3 | 3/2/2 | 3/1/1 | 3/2/1 | 2/2/2 | 3/3/3 |
| failure_report | 5 | 5/5/4 | 4/4/4 | 4/4/4 | 5/5/5 | 5/5/5 |
| general_question | 2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 |
| git_ship | 2 | 1/0/0 | 1/0/0 | 1/0/0 | 1/0/0 | 2/2/2 |
| handoff_prompt | 1 | 1/1/0 | 1/0/0 | 0/0/0 | 1/1/1 | 1/1/1 |
| project_audit_or_direction | 2 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 2/2/2 |
| revise_recent_output | 2 | 2/2/2 | 2/2/1 | 2/2/1 | 2/2/2 | 2/2/2 |
| specified_task | 6 | 5/5/5 | 5/5/5 | 5/5/5 | 5/5/5 | 6/6/6 |
| supply_fact_or_step_done | 1 | 1/1/1 | 1/1/1 | 1/1/1 | 1/1/1 | 1/1/1 |
| task_status_or_control | 4 | 4/4/3 | 3/3/2 | 3/3/2 | 4/4/3 | 4/4/4 |

**Which cases the teacher fixes and which it does not:**

- **Newly passed at 50%:** coreference_cause, handoff_prompt, negation_rule, prior_compaction_summary.
- **Still failing at 50%:**
  - contradiction_unresolved;
  - git_state_commit_own_work, project_audit_wide_view (wide-view / git);
  - prompt_injection_in_tool_output;
  - pt_en_mixed, qualifier_exception, source_authority;
  - structured_config_block.
- **Contradiction:** `value_conflict` fires on both must blocks of contradiction_unresolved, but neither model
  gives it enough weight to pass that case.
- **One loss:** environment_and_infra drops one case at 30%.
- **How broad the gains are:** they spread over 5 categories (external_accounts_and_comms, failure_report,
  handoff_prompt, revise_recent_output, task_status_or_control). They are not a single-case fit. But with n = 1-6 per category, no category result is meaningful on its own.

## Cost (fresh process, 1 thread, same BENCH method as v3)

| run | ms median | p90 | max | peak RSS MB | model KB |
|---|---|---|---|---|---|
| v4 candidate, 325 dev items (median 363 blocks) | 184.4 | 451.0 | 1987 | 165.3 | 189 |
| v3, same session | 171.8 | 501.7 | 1994 | 173.3 | 183 |
| v4 candidate, stress 2,813 blocks / 6.3 M chars | 6116 | - | - | 156.9 | - |
| v4 candidate, stress 5,367 blocks / 12.1 M chars | 12698 | - | - | 264.0 | - |

**MEDIDO:**
- The candidate meets every budget on dev: peak RSS 165 MB (< 250), median 184 ms (< 300), model 189 KB (< 1 MB).
- The EXTRA features cost about 0.2 ms per block (15 sampled train items, 22,955 blocks, under load) after
  the value-extraction regex was anchored on the operator. The first version backtracked and was about 5x
  slower.

**INFERIDO:**
- Latency comparisons are noisy. Load average was 26-28 here (and up to 258 earlier in the session).
- The 12 M-char stress item exceeds 250 MB for v3 as well (260 MB).

## Limits

- **INFERIDO: labels and teacher.** The next-action labels lean recent and drop goal-shared evidence. Opus
  labels generic relevance, with clipped blocks and 8-block batches, so it does not see the whole session. The
  two disagree, and the rule weights dev.
- **What was not tried:** a teacher prompt aimed at supersession (for example, "is this block superseded later?")
  and a GBDT teacher. Both are open options.
- **Edge suite is not held-out.** It took part in selection, the features were designed from its failing
  fixtures, it has 35 cases and the gold is single-author.
- **Held-out set.** `research.heldout_v3 count` at 2026-10-13 16:38 UTC found 5 qualifying sessions, 10
  candidate items: claude 3 sessions / 5 items, hermes 2 / 5, codex 0. That is too few to build the frozen
  comparison yet.
- **No paid API calls.** Gemini was not run.
