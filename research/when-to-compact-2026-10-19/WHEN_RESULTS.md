# When should LCC stash, relative to prompt-cache state? (results)

Produced on 2026-10-19 by `python -m research.when_to_compact run` under `WHEN_PROTOCOL.md` (committed in 43c81a7
before any outcome was computed). Aggregates only; machine-readable: `when-results.json`. Labels: **MEDIDO** = counted
from the owner's Claude Code usage metadata; **INFERIDO** = simulated or read from code (`gateClaim` was not run).
No model calls, no network. Costs are in base-input-token equivalents (uncached 1.0, read 0.10, 5m write 1.25,
1h write 2.0); output tokens are left out because no policy changes them.

## Bottom line

- **The cheap moment exists and it is the idle return.** After a gap longer than an hour, 97% of returns find the
  cache cold and re-write a median of 278k tokens. Those re-writes are **15.9% of all main-session cost** (MEDIDO).
  A stash pass there pays no invalidation, because the prefix is re-written anyway.
- **P1 (stash on the first request after an idle gap longer than the TTL) is cheaper than today on 97.7% of the
  sessions where it fires**: mean saving 185k base tokens per session [114k, 262k], 9.3% of total cost, 8.7% less
  context on average (INFERIDO). It passes the cost gate in all four sensitivity runs. The worst one is rho 0.15
  with q 0.5: +2.5% of cost, CI lower bound +31k per session.
- **It fails the harm gate, as the protocol said it would.** Each pass is expected to stash about 4.2 results the
  agent uses next (1,650 over 396 passes). The verdict is therefore **conditional opt-in**: off by default, with
  a field count of `recall` calls per pass. It is not recommended as a default.
- **The TTL decides everything.** 95% of main-session cache writes are 1-hour. A hook that assumes 5 minutes (P1_5m)
  hits a warm cache on 71% of its triggers and **loses 10.7% of cost** [-325k, -110k per session]. A hook must know,
  or be configured with, the TTL in force.
- **Natural compaction is not where the money goes.** There are 39 compactions (37 manual). They cost about 0.7% of
  main-session cost (INFERIDO estimate), and 85% happen on a warm cache (median gap 84 s). Moving the stash to the
  natural compaction point saves little. Idle returns are 20x more expensive in total.
- **P2 (tail-only while warm) is empty by construction.** The newest outputs sit after the last breakpoint, and
  `stashed` never removes them (`preserve_recent`). Stashing while warm is a gamble: warm_50k earns +3.8% at rho 0.35
  but loses at rho 0.15 or q 0.5, and is cheaper on only 57% of touched sessions.

## Data (MEDIDO)

767 main sessions (40,524 own requests; resume / fork copies de-duplicated) and 1,134 subagent traces (36,585
requests). The data is live: the count includes sessions written up to the run.

| | main | subagents |
|---|---:|---:|
| share of cache-write tokens at 1-hour TTL | **95.4%** | 0.0% |
| writes as share of cost | 34.4% | 47.8% |
| cost, base-token eq. | 1.53 B | 1.16 B |

Subagents write only 5-minute caches and do not idle; the timing question is about the main session.

### Idle gaps (main sessions, 39,732 gaps between requests)

| p10 | p25 | p50 | p75 | p90 | > 5 min | > 1 h |
|---:|---:|---:|---:|---:|---:|---:|
| 3.3 s | 5.0 s | 8.9 s | 20.4 s | 69 s | 3.96% (246 sessions) | 1.00% (130 sessions) |

| return after a gap | n | cold (reads < 50% of context) | re-written tokens p50 / p90 | re-written, sum | share of total cost |
|---|---:|---:|---:|---:|---:|
| > 5 min | 1,574 | 28.8% | 1.4k / 336k | 137.1 M | 17.9% |
| **> TTL (= > 1 h here)** | **396** | **97.0%** | **278k / 595k** | **121.7 M** | **15.9%** |

Context at those returns: median 314k tokens (p90 636k).

### Natural compactions (39 unique boundaries)

| | value |
|---|---|
| trigger | 37 manual, 2 auto |
| gap since the previous request | p50 84 s, p75 498 s, p90 2.7 h |
| cold (gap > TTL; all 39 at 1-hour TTL) | **15.4%** (28.2% under a 5-minute rule) |
| tokens before / after | p50 561k / 15.7k (p25 59k: LCC plugin test sessions) |
| first request after: writes / reads | p50 35k / 52k |
| estimated cost (summarizer input + first request after) | 11.0 M = **0.72%** of main-session cost (INFERIDO; the summarizer call is not in the transcript) |

## Policy simulation (INFERIDO; 767 sessions, session bootstrap 2000 resamples, seed 20261019)

Saving = P0 cost - policy cost, per session, in base-token equivalents. Untouched sessions count as 0 in the mean.

| policy | sessions touched | touched sessions cheaper | mean saving / session [95% CI] | total saving | context mean | passes | expected removed-then-needed results (per pass) | cost gate | harm gate |
|---|---:|---:|---|---:|---:|---:|---:|:-:|:-:|
| P0 (today) | 0 | - | 0 | 0 | - | 0 | 0 | - | yes |
| **P1** | 130 | **97.7%** | **+185.5k [+114.2k, +261.7k]** | **9.3%** | -8.7% | 396 | 1,650 (4.2) | **pass** | fail |
| P1_min10k | 111 | 99.1% | +174.0k [+107.2k, +245.9k] | 8.7% | -8.6% | 266 | 1,626 (6.1) | pass | fail |
| P1_min50k | 63 | 100% | +137.1k [+83.1k, +195.7k] | 6.9% | -7.2% | 111 | 1,307 (11.8) | pass | fail |
| P1_5m | 246 | 43.9% | -213.2k [-324.8k, -110.0k] | -10.7% | -13.2% | 1,572 | 2,537 (1.6) | fail | fail |
| P2 | 0 | - | 0 | 0 | - | 0 | 0 | - | yes |
| warm_50k (contrast) | 154 | 57.1% | +76.3k [+43.2k, +112.5k] | 3.8% | -12.1% | 290 | 2,116 (7.3) | fail | fail |

### Sensitivity (mean saving per session [95% CI], total saving; share of touched sessions cheaper)

| run | P1 | P1_min10k | P1_min50k | P1_5m | warm_50k |
|---|---|---|---|---|---|
| primary (rho 0.35, q 0.24, mu 0.03) | +185k [114k, 262k], 9.3%; 98% | +174k, 8.7%; 99% | +137k, 6.9%; 100% | -213k, -10.7%; 44% | +76k, 3.8%; 57% |
| rho 0.15 | +78k [47k, 111k], 3.9%; 98% | +64k, 3.2%; 97% | +30k, 1.5%; 100% | -460k, -23.0%; 29% | -13k, -0.6%; 30% |
| q 0.5 | +121k [74k, 171k], 6.1%; 98% | +112k, 5.6%; 97% | +86k, 4.3%; 100% | -361k, -18.1%; 35% | -12k, -0.6%; 25% |
| mu 0.10 | +186k [114k, 262k], 9.3%; 98% | +174k, 8.7%; 99% | +137k, 6.9%; 100% | -166k, -8.3%; 47% | +88k, 4.4%; 61% |
| rho 0.15 + q 0.5 | +51k [31k, 72k], 2.5%; 98% | +41k, 2.1%; 97% | +19k, 1.0%; 100% | -523k, -26.2%; 26% | -28k, -1.4%; 5% |

P1, P1_min10k and P1_min50k pass the cost gate in every run, so the pre-registered verdict for all three is
`conditional_opt_in`. P1_5m and warm_50k never pass.

## Reading (INFERIDO)

- The saving has two parts. At the trigger, the pass shrinks a re-write that was going to happen anyway, at 2.0x
  under the 1-hour TTL. After it, every later request in the segment reads fewer tokens at 0.1x. Sessions here run
  at 300k+ tokens with many requests per hour, so the read part adds up.
- The 2.3% of touched sessions where P1 loses are returns where the cache was still warm despite a gap > 1 h (3% of
  those returns read more than half of their context). A pass there invalidates a warm 1-hour prefix.
- Among the three passing variants, **P1_min10k** is the practical choice. It keeps 94% of P1's saving with a third
  fewer passes (266 vs 396), so it skips tiny passes that would only cost a stash note and a possible recall. P1_min50k
  is the conservative option: it has the fewest passes, but more needed results per pass (11.8), because a pass at
  50k+ removable tokens sweeps a large stretch.
- The harm proxy only counts results. It says nothing about whether a recall at an idle return is costly for the
  task. After a long break the user often starts a new sub-task, which would make stale outputs less likely to be
  needed. That is a hypothesis, not tested: the USED rate came from next-action points anywhere in a session.

## Feasibility in Claude Code (static reading; UNVERIFIED unless stated)

- **What LCC 1.1.0 runs today** (read from `plugins/claude-code`): one function hook on `session.compact`, which
  replaces the messages with `compact_transcript` output or calls `next(event)`. Two classic hooks, `PreCompact` and
  `SessionStart(compact)`, pin facts. The plugin never asks for a compaction. So P1 cannot run with the shipped plugin.
- **What the 2.1.296 function-hook surface declares** (strings in the Claude Code bundle, not executed):
  - `$.session.compact({ instructions })` is on the hook API, so a hook can request a compaction.
  - Events: `prompt.submit` (fires before the request; can rewrite or `drop` the prompt), `turn.start`,
    `turn.complete`, `session.append`, `session.compact`.
  - Calls: `clock.now`, `store.get` / `store.set`, `session.usage`, `session.messages`.
  - `session.compact` may return `{ skip: reason }` before calling `next()` (veto without a summary).
  - UNVERIFIED: whether `$.session.compact()` called inside `prompt.submit` / `turn.start` completes before that
    turn's request; what `session.usage` returns (the TTL split?); what `trigger` the resulting `session.compact`
    carries.
- **Classic hooks alone cannot do P1.** `UserPromptSubmit` can measure the gap from `transcript_path` timestamps, but
  it cannot rewrite the conversation. It could only print a hint.
- **Built-in nudge.** The bundle carries an "inactive for ... and is ... tokens long" resume prompt, so Claude Code
  already handles long idle resumes in some flow. Its behavior was not checked.

## Design note for an LCC PR (only if the owner opts in; not a default)

- **Trigger**: a `turn.start` function hook (or `prompt.submit` if `turn.start` turns out to be too late) reads
  `last_request_end` from `$.store`. That key is written on `turn.complete` with `$.clock.now()`. The hook fires when
  `now - last_request_end > idleTtlSeconds` and the estimated removable tokens are at least `idleMinRemovableTokens`.
  It then calls `$.session.compact({ instructions: "lcc:idle" })`. The existing `session.compact` handler sees the
  marker and runs `provider: rules`, `rulesMode: stashed`.
- **Config knobs** (plugin `userConfig`): `idleStash` (`false`), `idleTtlSeconds` (`3600`, the 1-hour TTL seen in
  95% of main-session writes; 300 only for 5-minute setups), `idleMinRemovableTokens` (`10000`), and an
  `idleMaxPassesPerSession` cap (`8`).
- **Fail-safe**: on an idle-triggered compaction, every failure path returns `{ skip: reason }` and never calls
  `next(event)`. The built-in summary on a cold 300k-token cache would be the most expensive thing that could
  happen. Other rules:
  - Stand down when `$.session.usage` (if it exposes it) shows a cache read on the previous request after the gap,
    i.e. the cache is warm.
  - Never trigger on subagents (5-minute TTL, no idle).
  - Never trigger twice without new growth.
  - Toast every outcome: `lcc: idle stash (removed N tokens, cache was cold)` or `lcc: idle stash skipped (reason)`.
- **Measure in the field** before any default change: recall calls per idle pass, and the next request's
  `cache_read` vs `cache_creation`, to confirm the cache really was cold.
- **First prove the plumbing**: one throwaway session with an idle trigger forced via a 60-second
  `idleTtlSeconds`. Check that `$.session.compact` from `turn.start` runs before the request and that the
  `session.compact` event carries the marker.

## Limits

- One user, one machine, subscription traffic. The prices are relative multipliers, not the bill. The session count
  moves while sessions are being written.
- rho, q and mu come from v5 cycle 2's dev items at arbitrary points in sessions, not from passes run at idle
  returns. No pass was run on these traces.
- The request sequence is held fixed. With less context the agent might act differently (fewer re-reads, later or
  no compaction). Recall timing is pessimistic: all recalls are charged at the trigger at write price.
- The "cold" test (reads < 50% of context) and the TTL inference (newest write mostly 1h) are heuristics from usage
  fields.
- The compaction cost is an estimate. The summarizer request is not in the transcript.
- The function-hook feasibility comes from strings in one Claude Code build. Nothing was executed.
- Four related candidates, no multiplicity correction (disclosed in the protocol). The CIs are far from zero.
