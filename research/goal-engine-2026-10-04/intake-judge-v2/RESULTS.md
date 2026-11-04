# Intake judge v2: owner held-out results (one-shot, 2026-11-04)

Protocol: [PROTOCOL.md](PROTOCOL.md) with amendments [1](AMENDMENT_1.md) and [2](AMENDMENT_2.md). Full
numbers: [test-results.json](test-results.json). The gold is shared with v3; see
[RESULTS_OWNER.md](../intake-judge-v3/RESULTS_OWNER.md) for the gold itself and the v3 arm. The gold is now
spent. Counts and arithmetic are MEDIDO; readings are INFERIDO.

## Bottom line

- **v2 does not replace v1.**
- **Acceptance 1, replaces v1: FAIL.** v2 − v1 = **−0.059 [−0.133, +0.015]**; it needed a lower bound above 0.
  The fallback is the pick, so 1b fails too.
- **Acceptance 2, beats rules: PASS.**
  - Accuracy: +0.279 [+0.181, +0.372].
  - Macro-F1: +0.186 [+0.106, +0.278].
- **Acceptance 3, cost: PASS.** Median 1.60 ms, p90 2.01 ms, peak RSS 64.9 MB.
- **Close-to-Opus label: not met.** −0.331 [−0.410, −0.248].
- **The same verdict on `blind`:** the owner's `blind` and `final` labels are identical on all 136 items.

| arm | accuracy | macro-F1 |
|---|---:|---:|
| Claude Opus 5.5 (teacher, with previous turn) | 0.794 | 0.730 |
| **v1 (shipped in LCC)** | **0.522** | **0.448** |
| v2 pick (B, C=10) | 0.463 | 0.404 |
| majority (v2 freeze) | 0.213 | 0.025 |
| keyword rules | 0.184 | 0.218 |

## By slice (reported, not gating)

| slice | items | v2 | v1 | Opus |
|---|---:|---:|---:|---:|
| with the agent's previous turn | 118 | 0.483 | 0.525 | 0.805 |
| without it | 18 | 0.333 | 0.500 | 0.722 |
| Portuguese | 95 | 0.390 | 0.400 | 0.779 |
| English | 41 | 0.634 | 0.805 | 0.829 |

Category recall:
- **v2 loses** on `git_ship` (0.43 vs v1 0.79) and on `project_audit_or_direction` (0.50 vs 0.83).
- **v2 gains** a little on `approve_or_pick` (0.79 vs 0.76) and on `specified_task` (0.43 vs 0.36).
- **Every small model is low** on `revise_recent_output` (0.25) and on `task_status_or_control` (0.27), where
  Opus reaches 0.80–1.00.

## Reading (INFERIDO)

- **The previous turn did not pay off on the owner's future prompts.** Its dev gain (macro-F1 0.490 vs 0.466)
  did not carry over.
- **Short replies are read as approvals.** The owner labels a "yes" to "shall I commit?" by what was approved
  (`git_ship`). v2 often calls it `approve_or_pick`. Opus gets 0.71 on `git_ship` with the same input, so this
  is the small model's error, not the teacher's.
- **v1 still trails Opus by 0.27 on this gold.** That gap is where the room is.
