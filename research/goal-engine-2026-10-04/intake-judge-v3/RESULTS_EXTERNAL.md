# Intake judge v3: external held-out results (one-shot, 2026-10-25)

Protocol: [PROTOCOL.md](PROTOCOL.md) with amendments [1](AMENDMENT_1.md)–[4](AMENDMENT_4.md). Frozen pick:
[FREEZE.json](FREEZE.json), data (iii) C=3, family B. Full numbers:
[external-test-results.json](external-test-results.json). The external gold is now spent. The owner held-out
(acceptance 1) has not run yet, so **v3 is not yet cleared to ship**. Counts and arithmetic are MEDIDO;
readings are INFERIDO.

## Bottom line

- **Acceptance 2, external superiority: PASS.**
  - Gold: the owner's `final` labels on 99 items from 88 people or sessions (1 "unsure" excluded).
  - v3 is right on **0.697**; v1, the model shipped in LCC, on **0.303**. v3 − v1 = **+0.394 [+0.283, +0.500]**.
- **Acceptance 2b, same check on the owner's `blind` labels: PASS.** +0.394 [+0.283, +0.500].
  - The vote reveal changed one label in 99, and the owner moved to a category none of the three models had
    voted.
  - There is no sign that the teacher-family vote anchored the gold.
- **Acceptance 3, cost: PASS.** Median 0.69 ms, p90 1.99 ms, load 28 ms, peak RSS 64.9 MB, model 1.84 MB.
- **v1 does worse than always answering "specified_task" on other people's prompts:** 0.303 vs 0.434. v1
  and v2 were trained on one person's prompts.

## External gold, `final` (99 items)

| arm | accuracy | macro-F1 |
|---|---:|---:|
| Claude Opus 5.5 (teacher, with previous turn) | 0.859 | 0.788 |
| **intake judge v3** | **0.697** | **0.489** |
| majority (`specified_task`) | 0.434 | 0.076 |
| keyword rules | 0.424 | 0.137 |
| v2 pick | 0.354 | 0.204 |
| v1 (shipped in LCC) | 0.303 | 0.146 |

v3 − arm, accuracy [95% CI, session/person bootstrap]:

| arm | difference [95% CI] |
|---|---|
| v1 | +0.394 [+0.283, +0.500] |
| v2 pick | +0.343 [+0.226, +0.454] |
| keyword | +0.273 [+0.149, +0.394] |
| majority | +0.263 [+0.139, +0.382] |
| Opus | −0.162 [−0.248, −0.072] |

## Sensitivity views (the same verdict in each)

| view | items | v3 | v1 | Opus | v3 − v1 [95% CI] |
|---|---:|---:|---:|---:|---|
| `blind` (owner, before seeing votes) | 99 | 0.707 | 0.313 | 0.869 | +0.394 [+0.283, +0.500] |
| majority of Codex + Gemini + owner-blind | 98 | 0.745 | 0.296 | 0.969 | +0.449 [+0.347, +0.553] |
| all three models agree | 88 | 0.761 | 0.295 | 1.000 | +0.466 [+0.360, +0.571] |

Voter agreement:
- Claude–Codex 0.939, Claude–Gemini 0.919, Codex–Gemini 0.909.
- All three agreed on 89 of the 100 drawn items.

## By stratum (reported, not gating)

| stratum | items | v3 | v1 | Opus | v3 − v1 [95% CI] |
|---|---:|---:|---:|---:|---|
| another Claude Code user (public set, 11 sessions) | 22 | 0.545 | 0.364 | 0.727 | +0.182 [0.000, +0.364] |
| other people asking for code (WildChat, 77 people) | 77 | 0.740 | 0.286 | 0.896 | +0.455 [+0.325, +0.584] |

Reading (INFERIDO):
- Most of the gain is on WildChat. WildChat train data comes from the same platform as WildChat held-out,
  though from different people.
- On the one other agent user, v3 leans better than v1, but the CI touches 0. That stratum is 11 sessions of
  what looks like a single developer (amendment 1).
- "Works for other agent users" is therefore suggested, not shown.

## Where v3 misses (`final`, descriptive)

| category | n | v3 recall |
|---|---:|---:|
| specified_task | 43 | 0.74 |
| general_question | 12 | 0.83 |
| UNKNOWN | 11 | 0.73 |
| revise_recent_output | 11 | 0.73 |
| failure_report | 10 | 1.00 |
| task_status_or_control | 8 | 0.12 |
| project_audit_or_direction | 2 | 0.00 |
| correct_approach_or_rule | 2 | 0.00 |

Most frequent errors:
- specified_task → general_question (6): imperative requests read as questions.
- task_status_or_control → UNKNOWN (3) or approve_or_pick (2): short steering replies. These were also v1's
  weak spot.

## What is left

- **Acceptance 1, owner non-inferiority (CI lower bound above −0.03 against the shipped model).** It runs once
  on the owner-future gold, shared with the v2 test, when the 2026-10-24 held-out reaches 100 qualifying
  sessions.
- v3 replaces v1 in LCC only if that passes too.
