# When to compact, part 2: keep-warm pings and fresh-session handoff (pre-registered)

Written and committed on 2026-10-19 before any part-2 outcome was computed. Owner request (via the session that
spawned this run): "the best solution to this (likely common) problem" of idle returns on a cold cache. Code:
`research/when2.py`, tests `tests/test_when2.py` (synthetic traces). Hashes: `WHEN2_PROTOCOL.json`. Part 1
(`WHEN_PROTOCOL.md`, `research/when_to_compact.py`, commit 43c81a7) is frozen and untouched; part 2 imports its
parser, annotator, cost model and reduction model. Known before freezing: only part 1's published aggregates
(`WHEN_RESULTS.md`), including the median post-compaction size (15,696 tokens) used for H. No return-gap
distribution beyond part 1's quantiles, no ping or handoff figure was computed before this commit.

## Data

Same traces and rules as part 1: `~/.claude/projects/**/*.jsonl`, numeric usage and timestamps only, main sessions,
resume / fork copies de-duplicated (counted once), live data (counts move while sessions are written).

## Cost model

Part 1 factors: uncached 1.0, cache read 0.10, 5m write 1.25, 1h write 2.0. New: output 5.0 (INFERIDO, from
memory of current Claude price sheets; used only for the ping's one token and the handoff summary).

## Idle episodes and the return-gap distribution (MEDIDO)

- An idle episode is a gap before a non-dup, non-segment-start main request (part 1's gap), plus a **session end**:
  the last request of a trace that is not a dup and is never followed by a request in any trace (a resumed
  session continues elsewhere), gap = infinity. A session end within `CENSOR` = 4 x 55 min + 1 h of the newest
  request in the data is censored (not charged, not counted).
- TTL in force: part 1's rule (newest write mostly 1h -> 1 hour, else 5 minutes); for a session end, the last
  request's own write mix.
- Report: counts, quantiles of returns after > 5 min and > 1 h; for 1-hour episodes idle past 55 min, the share
  that returns in (55, 60] min (warm anyway), in each ping's rescue window, later, or never; per ping j, the share
  of episodes where it fired that it rescued.

## Policies

`D = 55/60 x TTL`. A ping j fires at `j x D` after the previous request while the user is away, up to K. It reads
the current (policy) prefix: cost `0.1 x prefix + PING_EXTRA` (10 uncached tokens + 1 output token = 15). Reads
refresh the TTL, so after n pings the prefix stays warm until `n x D + TTL`.

| name | rule |
|---|---|
| P0 | today |
| P1 | part 1's P1 (stash rho 0.35 on the first request after gap > TTL), re-implemented; must equal part 1 on tests |
| P4_K1 / K2 / K4 | keep-warm, up to K pings per idle episode, also after the last request of a session |
| P5 | fresh-session handoff: on a cold return (gap > TTL and not kept warm, not a segment start) when the handoff drops >= 50k tokens, the context becomes `B0 + H` (B0 = first request's context of the trace: system, tools, first prompt; H = 15,696) |
| P1+P4_Kk | pings; a return outside the kept-warm window triggers P1 |
| P1+P5 | cold return: P5 if it drops >= 50k, else P1 |
| P1+P4_Kk+P5 | exploratory: all three levers |

- **Rescued return** (kept warm while the trace was cold): the request is re-priced as if warm: reads
  `max(r, min(previous context, C - u))`, the rest written at its own write mix. If the trace was already warm
  (3% of > 1 h returns), this changes nothing and the pings are pure cost.
- **P5 at the trigger**: handoff generation (primary `cold`) = an LLM call over the full current context without
  caching, `C x 1.0 + H x 5.0`; the request then reads `min(r, B0)` and writes the rest of `B0 + H` at its write
  price. Later requests in the segment lose `C - (B0 + H)` (reads first, then writes, then uncached; part 1's
  order). Natural compaction boundaries reset, as in part 1. No recall cost is charged: **handoff quality is not
  measured, only cost.**
- Paired comparisons: every policy is run on the same sessions; per-session differences vs P0 and vs P1.

## Questions and outputs

1. Return-gap distribution and break-even (MEDIDO counts; break-even INFERIDO): analytic break-even return
   probability for one ping on a 1-hour cache `0.1 / (2.0 - 0.1) = 5.3%`; empirical `mean ping cost / mean
   benefit of a warm return` over returns after > 1 h; per-ping rescue share compared to it.
2. Simulation (INFERIDO): per policy, sessions touched (any ping, pass or handoff), share of touched sessions
   cheaper than P0, mean saving per session with a 95% CI (paired session bootstrap, 2000 resamples, seed
   20261019, untouched sessions = 0), total saving share, overhead share, pings / rescues / passes / handoffs,
   saving per idle episode with >= 1 ping (ratio, same bootstrap), mean difference vs P1 with CI, expected
   removed-then-needed results (P1 part), tokens dropped by handoffs.
3. Sensitivity: `ping_turn` (ping is a real Claude Code turn, extra 5,000), `lead50` (ping at 50 min),
   `H30k`, `gen_native` (handoff input at write price, as Claude Code's own /compact on a cold cache),
   `gen_local` (deterministic local handoff, no model cost), `gen_prebuilt` (handoff built while warm at
   `(K+1) x D`, `0.1 x prefix + 5.0 x H`, paid on every episode that idles that long, used only on a cold return),
   `rho0.15_q0.5`.

## Acceptance (fixed now)

- Cost gate (part 1): among touched sessions >= 70% cheaper than P0, and CI lower bound of the mean per-session
  saving > 0. "Robust" = cost gate in primary and every sensitivity run.
- P4_K*: removes nothing, no harm proxy. Robust -> `recommended_cost_side` (the cost side only; quota, terms
  and feasibility are open, see below). Else not recommended.
- Policies with P1 and no P5: inherit P1's harm-gate failure. Robust -> `conditional_opt_in`.
- Policies with P5: quality unmeasured. Robust -> `cost_only_candidate` (needs a quality study before any use).
- "Beats P1": paired CI lower bound of (policy - P1) > 0 in the primary run.
- Recommendation rule: within each class (no content loss / stash / handoff), the robust policy with the highest
  primary mean saving; across classes, prefer no content loss unless another class beats it with a paired CI
  that excludes 0 (reported, not computed by the script). No multiplicity correction (13 policies, disclosed).

## Caveats stated now

- Pings spend quota / rate limit on subscription plans and are automated traffic. Whether provider terms or
  etiquette allow keep-alive requests was not checked here; this study states no policy fact. Claude Code has no
  keep-warm feature that this study knows of (not checked).
- A ping that reproduces the exact prefix needs the same model, system, tools and messages; a Claude Code turn
  appends a message (covered by `ping_turn`). Feasibility is not tested.
- P5 changes what the agent knows; its quality cost (redo work, wrong assumptions) is unknown and could exceed the
  saving. The request sequence is held fixed for every policy, as in part 1.
- Same population limits as part 1 (one user, one machine, relative prices, live data).
