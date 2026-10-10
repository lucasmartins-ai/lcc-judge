# Real-context bench v0.5: Codex TEST 60 + two-judge blind audit, results 2026-10-10

> **Review notes (independent review, PASS_WITH_NOTES).** (1) The TEST judges did not receive
> the frozen v0.4 judging text word for word: the workflow prompt paraphrased it. The audit is
> therefore a deviation from the protocol, though in the direction of the same task. (2) Judge
> isolation was by instruction only: judges could list the private audit folder that also held
> key.jsonl and other judges' verdicts. (3) DEV vs TEST rates below are not comparable as
> written: DEV had one judge per record, TEST flags a record if either of two judges flags it;
> a one-judge rate on TEST is about 54/264 = .20. (4) Verdict files are not hash-pinned in the
> repo, and run records do not store the policy commit (the worktree reflog confirms d0cb548).

**Status: audit FAIL under the pre-registered rule, by a wider margin than v0.4.** 36 of 132
audited drop/trim decisions were flagged (needed or unsure by at least one judge). The upper
Wilson 95% bound is .3543 against a .10 limit (at n = 132, at most 6 flags would have passed).
The rules arm still wins the probe verdict against mechanical, but its token reduction fell from
.641 (v0.4, rules@8997be6) to .191, and the audit is the primary retention evidence.

INFERIDO (exploratory). One offline pass over 60 held-out Codex contexts from the v0.5 TEST half
(sessions disjoint from DEV and from every earlier bench). Labels are LLM-made, token counts are
heuristic, and the judges were not the owner. This file holds counts only. Per-item data,
packets, verdicts and the unblinding key stay in `~/.lcc/bench/codex-heldout-v0.5/`.
Machine-readable files: `score.json` (probes, reduction) and `audit-summary.json` (audit, written
by the frozen `research/real_context_bench_v04_audit.py score` through
`research.real_context_bench_v05_test audit-score`, which re-checks every freeze hash first).
Freeze commit `69c90d6` was pushed before TEST dossiers existed; the score and unjudged packets
were recorded in `c1d3dc2`. Policy pin: LCC `feat/transcript-rules-policy` @ `d0cb548`
(PR #45, not merged).

## Limits first

- **The acceptance rule fails.** 36/132 flagged = .2727 (Wilson .2040–.3543). Even the
  needed-only secondary (17/132 = .1288, Wilson .0820–.1966) is above .10 at the upper bound,
  unlike v0.4 (7/150, upper .0932).
- **DEV did not transfer to TEST.** The policy was tuned on the DEV half; the DEV round-2 audit
  flagged 9/100. TEST flags 36/132. The DEV changes did not fix the failure on fresh sessions,
  and the gap is itself evidence of tuning to DEV (or of judge variance; this design cannot tell
  them apart).
- **Realised n is 132, not 150.** Only 46 items had drop/trim candidates, and the per-item cap
  of 3 left a shortfall of 18. Per protocol, acceptance uses realised n.
- **Both judges flagged half of the flags.** 18 of the 36 were flagged by both assigned judges.
  An "only if both judges flag" reading (not pre-registered, sensitivity only) gives 18/132,
  upper bound .2053, which also fails. Both judges said needed on 6/132 (upper .0956).
- **Agreement is lower than v0.4.** 107/132 pairs agree (raw .8106, kappa .4546; v0.4 .9267 /
  .6454). Unsure verdicts: 31/264 (.1174).
- **Judges.** Three judges (A, B, C) per the frozen routing; all 264 verdicts passed the validity
  rule, so the frozen re-judge rule requested 0 re-judgments (0 substituted, 0 incomplete). The
  aggregation does not record who the judges were; per protocol they are the owner or fresh
  Claude Code subagents, and none was the owner review.
- **Probe retention is by construction.** GIT_STATE and LAST_ARTIFACT_EDIT were not applicable
  on any Codex item; the other probes mostly use the policy's own predicates.
- **Labels and provenance.** 37 TEST labels are v0.4 LLM labels (request text seen once), 15 are
  new v0.5 LLM labels, 8 come from the taxonomy-v2 LLM pass. No owner labels.
- **Weak baseline, heuristic tokens.** Mechanical removes .0009 of tokens; token counts use
  `approximate:heuristic`.

## Audit (primary retention evidence)

- **Sample.** n = 132 (49 drops, 83 trims) from 46 items, at most 3 per item. Population: 611
  decisions (365 trims, 207 superseded drops, 39 stale-read drops). 0 packets with LCC markers.
- **Routing.** As frozen: A judged f1+f2 (100), B f2+f3 (82), C f3+f1 (82). Every record got two
  valid verdicts. 0 key/run join mismatches.

| metric | k / n | rate | Wilson 95% |
|---|---:|---:|---|
| primary: flagged (needed, unsure or incomplete) | 36 / 132 | .2727 | .2040–.3543 |
| secondary: needed by at least one judge | 17 / 132 | .1288 | .0820–.1966 |
| incomplete | 0 / 132 | 0 | — |
| unsure verdicts (of 264) | 31 / 264 | .1174 | — |

**Acceptance: FAIL** (upper bound .3543 > .10).

Judge verdict totals: A 12 needed / 73 not_needed / 15 unsure; B 4 / 72 / 6; C 7 / 65 / 10.

**Splits after unblinding** (descriptive; small cells):

| split | n | flagged | needed |
|---|---:|---:|---:|
| drop: superseded_by_later_call | 36 | 7 | 4 |
| drop: stale_read_far_from_recent_work | 13 | 5 | 3 |
| trim: large_old_output_trimmed | 83 | 24 | 10 |
| tool exec_command | 100 | 22 | 12 |
| tool exec (code mode) | 9 | 7 | 2 |
| tool mcp (all servers) | 11 | 6 | 2 |
| tool codex_app__read_thread_terminal | 1 | 1 | 1 |
| tools tool_search, view_image, write_stdin | 11 | 0 | 0 |

The 36 flagged records come from 21 of the 46 items. Trims still carry most flags (24/83), but
drops now fail too (12/49 vs 2/23 in v0.4).

## Probes and reduction (from `score.json`, n = 54 items with an applicable probe)

| arm | item retention | Wilson 95% | probe retention | token reduction, pooled / median item | latency, median / p90 |
|---|---:|---|---:|---:|---:|
| full | 54/54 | — | 72/72 | 0 / 0 | — |
| mechanical | 52/54 | .875–.990 | 69/72 | .0009 / .0001 | 6,213 / 70,790 ms |
| lcc_rules_transcript | 52/54 | .875–.990 | 70/72 | .1914 / .1104 | 18 / 124 ms |

- **Runs.** 60/60 for each arm, 0 failures, 0 guard trips.
- **Verdict.** `verdict_v05.wins` = true (retention_ge with equal item retention,
  token_reduction_gt, zero_guard_trips).
- **Guards.** The rules run kept 451 large outputs through trim guards (234 edited-later, 126
  recent, 64 named, 19 interactive, 8 error), against 365 trims.

## What this means

The v0.5 changes made the policy far more conservative (.191 token reduction vs .641) and it still
fails the audit on fresh sessions, with more flags than v0.4 (27% vs 14%) and drops failing
alongside trims. The DEV result (9/100) did not hold on TEST. The rules policy at `d0cb548`
should not be claimed as safe for Codex transcripts. Any further change needs a new frozen
protocol and data not yet seen; v0.4 and v0.5 TEST are both spent.
