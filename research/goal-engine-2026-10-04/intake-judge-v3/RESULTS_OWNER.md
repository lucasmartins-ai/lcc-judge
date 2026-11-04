# Intake judge v3: owner held-out results (one-shot, 2026-11-04)

Protocol: [PROTOCOL.md](PROTOCOL.md), amendments 1–5, and
[v2 amendment 2](../intake-judge-v2/AMENDMENT_2.md) for the owner gold. Full numbers:
[owner-test-results.json](owner-test-results.json). Draw receipt: [owner-draw.json](owner-draw.json). The
external results are in [RESULTS_EXTERNAL.md](RESULTS_EXTERNAL.md). The owner gold is now spent. Counts and
arithmetic are MEDIDO; readings are INFERIDO.

## Bottom line

- **Acceptance 1, owner non-inferiority: FAIL.** v3 − v1 = **−0.059 [−0.140, +0.016]**. The margin needed a
  lower bound above −0.03.
- **Acceptance 1b, the same check on `blind`: FAIL.** The owner's `blind` and `final` labels are identical on
  all 136 items, so the view gives the same numbers.
- **v3 does not replace v1 in LCC.** The ship rule needs acceptance 1, 1b, 2, 2b and 3. Acceptance 2, 2b and 3
  passed on the external gold.
- **Neither direction is shown.** The CI includes 0, so v3 is not shown to be worse for the owner either. This
  test only shows that it cannot be called non-inferior.

## Owner gold

- 136 prompts from 72 sessions started from 2026-10-24, at most 2 per session.
- Labelled in one pass by the owner. Every `blind` label equals its `final` label, so the votes changed
  nothing. No item was marked "unsure".
- Votes shown after each blind pick:
  - Claude Opus 5.5 and Codex `gpt-6.1-sol` (`xhigh`): all 136 items.
  - Gemini Argon "Alto": 100 items (see the amendment).

| arm | accuracy | macro-F1 |
|---|---:|---:|
| Claude Opus 5.5 (teacher, with previous turn) | 0.794 | 0.730 |
| **v1 (shipped in LCC)** | **0.522** | **0.448** |
| intake judge v3 | 0.463 | 0.418 |
| v2 pick | 0.463 | 0.404 |
| keyword rules | 0.184 | 0.218 |
| majority (`specified_task`, v3 freeze) | 0.103 | 0.013 |

v3 − arm, accuracy [95% CI, session bootstrap, seed 20261025]:

| arm | difference [95% CI] |
|---|---|
| v1 (shipped) | −0.059 [−0.140, +0.016] |
| v2 pick | 0.000 [−0.045, +0.044] |
| keyword | +0.279 [+0.187, +0.372] |
| Opus | −0.331 [−0.417, −0.246] |

## Sensitivity views (the same verdict in each)

| view | items | sessions | v3 − v1 [95% CI] |
|---|---:|---:|---|
| `final` = `blind` | 136 | 72 | −0.059 [−0.140, +0.016] |
| majority of Codex + Gemini + owner-blind | 123 | 69 | −0.073 [−0.160, +0.008] |
| all three models agree | 80 | 51 | −0.075 [−0.171, +0.013] |

## Where v3 loses (descriptive, reported after the decision)

| slice | items | v3 | v1 |
|---|---:|---:|---:|
| Portuguese prompts | 95 | 0.389 | 0.400 |
| English prompts | 41 | 0.634 | 0.805 |
| with the agent's previous turn | 118 | 0.458 | 0.525 |
| without it | 18 | 0.500 | 0.500 |

- Discordant items: v1 right and v3 wrong on 18; v3 right and v1 wrong on 10.
- Most frequent v3 errors:
  - `git_ship` read as `approve_or_pick` (6);
  - `general_question` read as `task_status_or_control` (6).

Reading (INFERIDO):
- Almost all of the gap is on the owner's English prompts. On Portuguese, the two are level.
- With the previous turn, v3 (like v2) often reads a short "yes" after "shall I commit?" as approving a choice.
  The owner labels it by the approved action (`git_ship`). Opus, given the same input, gets 10 of 14 `git_ship`
  items right, so this is a small-model error, not a teacher rule.
- `general_question` is hard for every arm: Opus gets 2 of 11. The owner's use of that category differs from
  the teacher's.

## What this leaves

- Under the pre-registered rule, v3 does not replace v1.
- v3's external result still stands: on other people's prompts, v3 scores 0.697 against v1's 0.303.

## Product decision after the result (owner, 2026-11-04)

The owner decided, after seeing this result, to make v3 LCC's default `category` model, with v1 kept and
selectable. This is not a pass of acceptance 1, and nothing here should be cited as one.

- **Reason given:** LCC's users are mostly other people. On their prompts v3 scores 0.697 and v1 scores 0.303,
  and v1 sits below the constant `specified_task` answer (0.434).
- **Cost to the owner:** on his own prompts the difference is −0.059 [−0.140, +0.016]. That is not shown to be
  a loss, and not shown to be safe.
- **The owner can pin v1** for his own use.
