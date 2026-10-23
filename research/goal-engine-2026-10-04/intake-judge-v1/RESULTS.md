# Intake judge v1: results (one-shot held-out test, 2026-10-23)

Protocol: [PROTOCOL.md](PROTOCOL.md), amendments [1](AMENDMENT_1.md) and [2](AMENDMENT_2.md). Frozen model and
code: [FREEZE.json](FREEZE.json). Full numbers: [test-results.json](test-results.json). The held-out gold is now
spent. Counts and arithmetic are MEDIDO; readings are INFERIDO (one owner, one machine, prompt text only).

## Bottom line

- **Beats rules: PASS.** On the primary gold (116 items both owner passes agree on, 79 sessions), v1 is right on
  **0.509** vs the keyword baseline **0.224**: +0.284 [+0.190, +0.389]. Macro-F1 0.457 vs 0.228, +0.229
  [+0.107, +0.361]. Majority class: 0.078. Same verdict on each full pass.
- **Close to Opus: FAIL.** Opus (the teacher, zero-shot) is right on **0.862**. v1 − Opus = −0.353
  [−0.459, −0.250], far past the −0.10 margin. Distilling 2,482 teacher labels into a hashed n-gram LR keeps
  about a third of the gap between rules and Opus.
- **Cost: PASS by a wide margin.** Median 0.26 ms, p90 0.85 ms per prompt, load 9 ms, peak RSS 39.7 MB,
  model 1.22 MB, stdlib only.
- **Ship rule** (checks 1 and 3 pass): v1 qualifies for LCC as an additive `category` field, labelled
  "beats rules, below Opus". Readiness stays untouched.
- **The owner's two passes agree on 116 of 150 (0.773).** Opus scores 0.86 on the agreed items and about
  0.75–0.77 on each full pass, so on ambiguous prompts no arm can be graded cleanly.

## Primary view (116 items)

| arm | accuracy | macro-F1 |
|---|---:|---:|
| Claude Opus 5.5 (teacher, zero-shot) | 0.862 | 0.821 |
| **intake judge v1** | **0.509** | **0.457** |
| keyword rules | 0.224 | 0.228 |
| majority (`task_status_or_control`) | 0.078 | 0.010 |

Sensitivity views (same arms, same checks; verdicts identical):

| view | items | v1 | keyword | Opus | v1 − Opus [95% CI] |
|---|---:|---:|---:|---:|---|
| pass1 | 150 | 0.440 | 0.187 | 0.753 | −0.313 [−0.407, −0.212] |
| pass2 | 148 | 0.466 | 0.230 | 0.770 | −0.304 [−0.403, −0.207] |

## Where v1 loses (primary view, recall per category)

| category | n | v1 | Opus |
|---|---:|---:|---:|
| approve_or_pick | 22 | 0.55 | 0.77 |
| specified_task | 17 | 0.71 | 0.94 |
| git_ship | 16 | 0.56 | 0.94 |
| correct_approach_or_rule | 15 | 0.27 | 0.93 |
| environment_and_infra | 9 | 0.33 | 0.78 |
| task_status_or_control | 9 | 0.33 | 0.89 |
| supply_fact_or_step_done | 8 | 0.25 | 0.75 |
| revise_recent_output | 7 | 0.71 | 0.86 |

Most frequent v1 errors: git_ship → approve_or_pick (4), supply_fact → failure_report (3),
environment_and_infra → correct_approach (3), correct_approach → revise_recent_output (3). Reading (INFERIDO):
the categories that depend on intent ("this is wrong, do it differently", "commit that") rather than on
surface words are where character n-grams fail. Portuguese is harder than English (0.47 vs 0.64 for v1;
Opus 0.86 vs 0.88).

## Post hoc, not a verdict: confidence as a gate

Computed after the test on the same 116 items, so it is selected on the held-out and is a hint, not
evidence. Keeping only predictions with probability ≥ 0.4 covers 42 items (36%) at 0.81 accuracy;
≥ 0.6 covers 20 items at 0.90. A shipped field should carry the probability and LCC should show the
category only above a threshold set on dev, not on this set.

## What this means for the next version

1. Ship v1 only as an additive, confidence-gated field: it is far better than regex and costs nothing.
2. The gap to Opus is a model-capacity problem, not a label problem: the teacher agrees with the owner at
   0.84 (train-period items) and 0.86 here. Candidates for v2, each needing its own pre-registration:
   more teacher labels (the 1,158 held-out prompts are now spent and usable for training; Opus cost was
   151 calls for 3,007 items), a larger C (v1's pick sat at the grid edge), and the agent's previous turn
   as input for the reply-type categories.
3. Readiness / "needs clarification" stays out of scope until an outcome label exists.
