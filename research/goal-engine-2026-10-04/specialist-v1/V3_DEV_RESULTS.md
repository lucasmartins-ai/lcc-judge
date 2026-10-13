# Specialist v3: dev results (next-action labels v2)

Produced by `python -m research.specialist_v3 select` then `eval` (2026-10-13). This file holds counts and metrics only, with no session text. Machine-readable copy: `v3-dev-results.json`. The frozen test split is spent and was not opened. Every number below comes from DEV, from the synthetic edge suite or from private stress items built from dev. All of them were used to choose v3, so none of them is held-out evidence.

## What changed vs v2

- **Model.** v3 averages the two frozen v2 models: the shipped LR and the GBDT alternative, both trained on train only. There is no retraining. The size penalty is unchanged (alpha 0.5 x log chars).
- **Rule floor (+3.0 logit).** It applies to the 1 block with the highest BM25 match to the goal (only when BM25 > 0) and to the 2 most recent blocks with an error marker. At most 3 blocks per item get the floor, so it protects goal-named and fresh-failure evidence without re-ranking the rest.
  - Why: in the v2 failures, v2 ranked the goal-matching or error-marked must-keep block near the bottom. Examples: `huge_log_middle_error` (0/36), `general_question_drop_all` (0/142), `long_session_over_32k` (0/590), `unrecoverable_read` (1/57). The LR gives `bm25_goal_rank` -0.009, `is_error` -0.016 and `lcc_protected` +0.03, but `keys_log` +0.49 and the recency terms around -0.3. The labels drop goal-shared evidence by construction, so the model cannot learn that goal match matters. It learns identifier density and recency instead.
  - Capping the recency features (msg/block distance clipped at log 7-20) was also tried. It lowered dev slightly and made the edge suite worse (17/15/10 for a refit LR), so it was dropped.
  - A graded goal prior on every block (+lambda x BM25 rank) reached 33/30/25 on the edge suite but cost 0.06 of dev all-kept AUC. The top-k floor keeps most of that gain at no dev cost.
- **Memory.** `specialist_v2.featurize` now runs LCC's mechanical pass first (its intermediates are freed before ours exist), and it keeps BM25 postings only for the query terms (goal + last 3 turns) instead of the full vocabulary. Features are bit-identical: 27 dev items, including the 2 largest, compared against the cached v2 feature matrices showed 0 differences. A synthetic unit test checks it too.
- **Selection rule (written before the grid ran).** The grid was members {lr, gbdt, ens} x k_goal {1,2,3} x k_err {0,1,2,3}, bonus 3 (36 configs). The pick maximises dev recall AUC + 0.25 x all-kept AUC, subject to:
  - dev recall AUC and all-kept AUC >= v2;
  - edge pass count strictly above every other arm at 30, 50 and 70%.
  - 11 of 36 configs passed both constraints. All 11 are `ens` or `gbdt` with a goal floor and k_err >= 1 or k_goal >= 2. Picked: `ens`, k_goal 1, k_err 2.
- **Unchanged.** The hardened `block_meta` (header trusted only at offset 0, message index cannot go backwards) and its forged-header test stay as they were. Before LCC integration, block metadata must still arrive structured from LCC's splitter (TEST_RESULTS.md post-run note).

## Dev, all 325 eligible items (MEDIDO on dev; dev chose the config)

| arm | AUC recall | AUC all-kept | AUC ev-cov |
|---|---|---|---|
| specialist_v3 | 0.887 | 0.445 | 0.948 |
| specialist_v2 | 0.884 | 0.434 | 0.947 |
| specialist_v2_gbdt | 0.889 | 0.440 | 0.951 |
| recency | 0.789 | 0.308 | 0.903 |
| bm25 | 0.787 | 0.264 | 0.876 |
| mechanical | 0.784 | 0.243 | 0.888 |
| random | 0.685 | 0.149 | 0.866 |

Paired bootstrap of the mean per-item AUC difference: 2000 resamples of 107 session groups, seed 20261013, 95% CI.

| v3 minus | recall | all-kept |
|---|---|---|
| specialist_v2 | +0.0036 [+0.0003, +0.0074] | +0.0103 [-0.0015, +0.0223] |
| recency | +0.0978 [+0.0802, +0.1157] | +0.1367 [+0.1039, +0.1731] |
| bm25 | +0.1005 [+0.0835, +0.1173] | +0.1805 [+0.1545, +0.2068] |
| mechanical | +0.1028 [+0.0857, +0.1193] | +0.2018 [+0.1669, +0.2387] |

- v3 is at least as good as v2 on dev on both AUCs. The all-kept gain over v2 is not significant: its CI crosses 0.
- All-kept items at 10/30/50/60% removed: v3 241/122/59/45; v2 238/119/58/45 (out of 325).
- Recall AUC by source: claude v3 0.904 vs v2 0.898 (n=97); codex 0.925 vs 0.918 (n=80); hermes 0.856 vs 0.856 (n=148).
- jev-overlap (43 items, lineage never trained on):
  - v3 recall 0.886 / all-kept 0.419;
  - v2 0.884 / 0.421;
  - Jev 0.818 / 0.337 (saved v0.1 scores);
  - bm25 0.809 / 0.291.

## Edge suite (35 synthetic cases, single-author gold; v3 selection looked at it)

| arm | 30% | 50% | 70% |
|---|---|---|---|
| **specialist_v3** | **28** | **23** | **20** |
| specialist_v2 | 24 | 20 | 13 |
| specialist_v2_gbdt | 19 | 15 | 8 |
| mechanical | 22 | 21 | 18 |
| bm25 | 21 | 20 | 18 |
| laya | 21 | 14 | 11 |
| specialist_inv | 22 | 13 | 10 |
| drop_largest | 17 | 17 | 17 |
| random (5 seeds) | 18.4 | 11.8 | 5.2 |
| recency | 7 | 7 | 4 |
| oracle | 35 | 35 | 35 |

The best other arm per cut is 24 / 21 / 18, so v3 is ahead by +4 / +2 / +2. The margins are thin (2 cases at 50 and 70%), and the gold is single-author.

Per category, passes at 30/50/70%:

| category | n | v3 | v2 | mechanical | bm25 |
|---|---|---|---|---|---|
| approve_or_pick | 2 | 2/2/2 | 1/1/1 | 2/2/2 | 2/2/2 |
| correct_approach_or_rule | 1 | 1/1/0 | 1/1/0 | 1/1/1 | 1/1/0 |
| environment_and_infra | 4 | 3/2/2 | 3/2/1 | 3/3/3 | 3/3/3 |
| external_accounts_and_comms | 3 | 3/1/1 | 2/1/0 | 1/1/1 | 1/1/1 |
| failure_report | 5 | 4/4/4 | 3/3/3 | 4/4/3 | 3/3/2 |
| general_question | 2 | 2/2/2 | 1/1/1 | 1/1/1 | 2/2/2 |
| git_ship | 2 | 1/0/0 | 1/0/0 | 1/0/0 | 1/0/0 |
| handoff_prompt | 1 | 1/0/0 | 1/0/0 | 0/0/0 | 0/0/0 |
| project_audit_or_direction | 2 | 0/0/0 | 1/1/0 | 0/0/0 | 0/0/0 |
| revise_recent_output | 2 | 2/2/1 | 2/2/2 | 2/2/1 | 1/1/1 |
| specified_task | 6 | 5/5/5 | 4/4/3 | 5/5/4 | 5/5/5 |
| supply_fact_or_step_done | 1 | 1/1/1 | 1/1/1 | 0/0/0 | 0/0/0 |
| task_status_or_control | 4 | 3/3/2 | 3/3/1 | 2/2/2 | 2/2/2 |

**Gains vs v2** are in approve_or_pick, failure_report, general_question, specified_task, task_status_or_control and external_accounts_and_comms. These are the goal-named or error cases the floor targets.

**Regressions vs v2:**
- project_audit_or_direction drops from 1/1/0 to 0/0/0 (`contradiction_unresolved`);
- revise_recent_output drops at 70% (`old_read_later_edited`).

**v3 still fails at 50%:** contradiction_unresolved, coreference_cause, git_state_commit_own_work, handoff_prompt, negation_rule, prior_compaction_summary, project_audit_wide_view, prompt_injection_in_tool_output, pt_en_mixed, qualifier_exception, source_authority, structured_config_block.
- None of these is a goal-match or fresh-error case.
- They need supersession, coreference, rule and wide-view reasoning that neither v2's features nor the floor capture.

## Cost (fresh process, 1 thread, same BENCH method as the test protocol)

| run | items / blocks | ms median | p90 | max | peak RSS MB |
|---|---|---|---|---|---|
| v3, all 325 dev items | median 363 blocks | 157.7 | 467.3 | 1598 | **161.6** |
| v2 models, same lean features, same run | median 363 blocks | 152.5 | 416.1 | 1893 | 163.9 |
| v2 before the memory change, all 325 dev items | median 363 blocks | 119.2 | 310.1 | 1430 | 187.9 |
| v3, stress: 2 largest dev items joined (2813 blocks, 6.3 M chars) | 1 | 4323 | - | - | 156.9 |
| v2 before the memory change, same stress item | 1 | 4831 | - | - | 204.3 |
| v3, stress: 4 largest dev items joined (5367 blocks, 12.1 M chars) | 1 | 9999 | - | - | 260.1 |

- **MEDIDO:**
  - On all dev items, peak RSS fell from 187.9 MB to 161.6 MB, under the 250 MB target. On the 6.3 M-char stress item it fell from 204 MB to 157 MB.
  - Median latency is 158 ms, under 300 ms. v3 adds about 5 ms over the v2 models alone (the GBDT walk).
  - The model file is 183 KB, because it embeds both member models.
- **INFERIDO:**
  - Test-set RSS. The test items cannot be re-measured: the split is spent. v2 peaked at 307.7 MB on test (max 2177 blocks).
  - The memory change cut the stress peak by 23%. Applied to the test peak, that gives about 235 MB for v3.
  - Memory still grows with item size. A 12 M-char item (2.5x the largest test item by blocks) reaches 260 MB.
  - The remaining peak is mostly LCC's own mechanical pass: about 44 MB on the 6.3 M-char item. Live LCC computes that pass anyway, so the specialist could reuse it instead of recomputing it.
- Latency was measured under machine load averages of 29-35 (10 cores); load was 335 at times during this session. Treat latency as an upper bound. The v2-before row came from an earlier run under different load (9.7).

## Limits

- **INFERIDO: labels.** The labels are rule-based next-action evidence that lean recent and drop goal-shared evidence. The floor deliberately goes against that bias, so dev metrics cannot reward it. Dev only shows that the floor costs nothing there.
- **Edge suite is not held-out.** It chose the config (the constraint in the selection rule), its gold is single-author, and it has 35 cases. The v3 edge win is a regression and diagnosis result, not held-out evidence. A grid of 36 configs on 35 cases can overfit. The 11 passing configs form a plateau (k_goal 1-3, k_err 1-3), not a single point, which is some reassurance but not proof.
- **No new held-out set yet.** v3 has no honest held-out estimate. The next check is `research.heldout_v3`: sessions started after 2026-10-12, session-disjoint from every v1/v2 lineage group. On 2026-10-13 00:00 UTC there were 0 qualifying sessions in claude, codex and hermes.
- **No Jev on test.** Jev was not re-run, and no remote or LLM calls were made.
- **LLM arm not run.** `research.llm_judge_arm` (Opus / Gemini Flash through the subscription CLIs) is ready but has not been executed.
