# Real-context bench v0.4: Codex held-out 60 + two-judge blind audit, results 2026-10-10

**Status: audit FAIL under the pre-registered rule.** 21 of 150 audited drop/trim decisions
were flagged (needed or unsure by at least one judge). The upper Wilson 95% bound is .2046
against a .10 limit. The rules arm still beats mechanical on the probe verdict, but that verdict
mostly mirrors the policy, and the audit is the primary retention evidence.

INFERIDO (exploratory). One offline pass over 60 Codex contexts from sessions no earlier bench
used. Labels are mostly LLM-made, token counts are heuristic, and the judges were Claude
subagents, not the owner. This file holds counts only. Per-item data, packets, verdicts and the
unblinding key stay in `~/.lcc/bench/codex-heldout-v0.4/`. Machine-readable files: `score.json`
(probes, reduction) and `audit-summary.json` (audit, written by the frozen
`research/real_context_bench_v04_audit.py score`). Freeze commit `6aad680` was pushed before
either arm ran, and the score was recorded in `ad1711d`. Policy pin: LCC
`feat/transcript-rules-policy` @ `8997be6` (PR #45, not merged).

## Limits first

- **The acceptance rule fails, and not at the margin.** At most 7 flagged records would have
  passed. 21 were flagged, giving a rate of .14 (Wilson .0934–.2046).
- **Most flags are "unsure", not "needed".** Of the 21 flagged records, 7 have at least one
  needed verdict and 14 have only unsure verdicts. The needed-only rate is 7/150 = .0467
  (Wilson .0228–.0932). That is a pre-registered secondary metric, not the acceptance rule. It
  does not turn the result into a PASS.
- **Two judges flagged most of them.** 13 of the 21 were flagged by both judges, and 8 by one.
  An "only if both judges flag" reading (not pre-registered, sensitivity only) gives 13/150,
  upper bound .1426, which also fails.
- **The trims carry the failure.** The trim rule (`large_old_output_trimmed`) accounts for 19 of
  the 21 flags: 19/127 trims, Wilson .0979–.2219. Drops: 2/23 (Wilson .0242–.2680). The drop
  sample is small (n = 23) because the population is 80% trims (1,481 trims vs 363 drops).
- **Judges' main reason for unsure:** trimmed output of a file the agent was about to edit, which
  the agent could read again. The protocol says re-running a tool is not a reason for
  not_needed, so these count against the policy as written.
- **No owner review.** All three judges were fresh Claude Code subagents working only from their
  packet files. Each verdict had its own reason. All 300 verdicts passed the validity rule, so
  nothing was re-judged (0 requested, 0 substituted).
- **Probe retention is by construction.** GIT_STATE and LAST_ARTIFACT_EDIT were not applicable
  on any Codex item. The other probes mostly use the policy's own predicates (stated in
  `PROTOCOL.md` before the run).
- **Labels and provenance.** 45 of the 60 labels were made by the LLM session that froze the
  protocol, 14 come from the taxonomy-v2 LLM pass and 1 is owner-confirmed. `is_error` comes only
  from recorded exit codes. 4 items come from sessions in LCC repositories.
- **Weak baseline.** Mechanical compaction removes almost nothing from Codex contexts (0.04% of
  tokens), so "rules beats mechanical" is a low bar here.
- **Heuristic tokens.** Token counts use `approximate:heuristic`, not a real tokenizer.

## Audit (primary retention evidence)

- **Sample.** n = 150 (23 drops, 127 trims) from 57 items, at most 3 per item. Population: 1,844
  decisions.
- **Routing.** As frozen: A judged f1+f2, B judged f2+f3, C judged f3+f1. Every record got two
  independent verdicts. Validity: 100/100 valid for each judge. 0 key/run join mismatches.

| metric | k / n | rate | Wilson 95% |
|---|---:|---:|---|
| primary: flagged (needed, unsure or incomplete) | 21 / 150 | .1400 | .0934–.2046 |
| secondary: needed by at least one judge | 7 / 150 | .0467 | .0228–.0932 |
| incomplete | 0 / 150 | 0 | — |
| unsure verdicts (of 300) | 25 / 300 | .0833 | — |

**Acceptance: FAIL** (upper bound .2046 > .10).

**Agreement:** 139 of 150 pairs agree (raw .9267), with Cohen's kappa .6454.

**Splits after unblinding** (descriptive; small cells):

| split | n | flagged | needed |
|---|---:|---:|---:|
| drop: superseded_by_later_call | 18 | 1 | 0 |
| drop: stale_read_far_from_recent_work | 5 | 1 | 1 |
| trim: large_old_output_trimmed | 127 | 19 | 6 |
| tool exec_command | 119 | 16 | 5 |
| tool mcp (all servers) | 10 | 3 | 1 |
| tool write_stdin | 11 | 1 | 0 |
| tool multi_agent_v1__wait_agent | 1 | 1 | 1 |
| tools exec, tool_search, apply_patch | 9 | 0 | 0 |

The 21 flagged records come from 15 of the 57 items.

## Probes and reduction (from `score.json`, n = 54 items with an applicable probe)

| arm | item retention | Wilson 95% | probe retention | token reduction, pooled / median item | latency, median / p90 |
|---|---:|---|---:|---:|---:|
| full | 54/54 | — | 69/69 | 0 / 0 | — |
| mechanical | 52/54 | .875–.990 | 67/69 | .0004 / .0002 | 1,894 / 11,102 ms |
| lcc_rules_transcript | 53/54 | .902–.997 | 68/69 | .6414 / .6388 | 6 / 13 ms |

- **Runs.** 60/60 ok for both arms, with 0 guard trips, 0 degraded and 0 errors.
- **Verdict.** `verdict_v04.wins` = true: retention_ge, token_reduction_gt and zero_guard_trips
  all hold.
- **Byte reduction** (rules, pooled): .6494.

## What this means

On session-disjoint Codex data, the rules policy cuts about 64% of tokens. The blind audit,
however, flags 14% of its drop/trim decisions as possibly needed. Most of these are trims of
large old command outputs. The pre-registered bar is ≤ 10% at the upper bound, so the policy
does not clear it. The secondary needed-only rate (upper bound .0932) suggests the hard failures
are rarer than the flags. That reading is not the pre-registered rule, though, and it rests on
LLM judges. A next step would change the trim rule, for example keeping more of outputs that the
agent goes on to edit. That would need a new frozen protocol and fresh data, not a re-score of
this set.
