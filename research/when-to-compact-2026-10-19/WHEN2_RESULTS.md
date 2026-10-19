# When to compact, part 2: keep-warm pings and fresh-session handoff (results)

Produced on 2026-10-19 by `python -m research.when2 run` under `WHEN2_PROTOCOL.md` (committed in 58c6c42 before any
part-2 outcome was computed). Aggregates only; machine-readable: `when2-results.json`. Post hoc checks (not
pre-registered, labelled): `research/when2_posthoc.py` -> `when2-posthoc.json`. Labels: **MEDIDO** = counted from
the owner's Claude Code usage metadata; **INFERIDO** = simulated (`gateClaim` was not run). No model calls, no
network. Costs in base-input-token equivalents (uncached 1.0, read 0.10, 5m write 1.25, 1h write 2.0, output 5.0).
769 main sessions (live data; part 1 saw 767). Mean P0 cost is about 2.0 M per session.

## Bottom line

- **Most long idles never come back to the same prefix.** Of 814 idle episodes past 55 minutes on a 1-hour cache,
  49% are session ends and 21% come back after more than 4h40. Only 11% come back in the hour a single ping buys
  (MEDIDO).
- **Keep-warm (P4) is slightly positive on average, but it fails the gate.** A ping costs 0.1 x prefix. A rescued
  return saves about 1.9 x prefix. The break-even return probability is 5.3% analytic, 4.8% empirical. The first
  ping's rescue rate is 11.2%; pings 2-4 rescue 6.4-7.1%, just above break-even. P4_K1 saves +37k per session
  [+12k, +68k], 1.9% of cost (INFERIDO). But it touches 760 sessions and only 6% of them get cheaper. Most sessions
  only pay wasted end-of-session pings, and the gain sits in a few sessions. Verdict: **not recommended** (cost gate).
  It also spends quota, and its terms of use and feasibility are open.
- **Keep-warm does not improve P1.** P1+P4_K1 vs P1: +13k per session [-3k, +33k], CI includes 0. With more pings
  it gets worse (K4: -2k).
- **Fresh-session handoff (P5) is the largest cost lever by far, on the cost side only.** On a cold return with a
  large context, P5 rebuilds the session as system + a ~15.7k handoff. It saves **+550k per session [+334k, +810k],
  27.6% of cost**, and beats P1 by +365k [+217k, +541k] (paired). **P1+P5** (handoff when it drops >= 50k tokens,
  else stash) is the top robust policy: **+570k [+349k, +837k], 28.6%**. It passes the cost gate in every
  sensitivity run. The pre-registered verdict is **`cost_only_candidate`**: handoff quality was not measured, so this
  is not a recommendation to use it.
- **The P5 number is an upper bound.** The trace is held fixed, so after a handoff the context stays ~138k smaller
  until the next natural compaction. A real agent would re-read some of it. A post hoc stress test treats the handoff
  as 100k instead of 15.7k, as if the agent rebuilt most of the context right away. P1+P5 still saves +304k
  [+166k, +470k], and +245k with Claude Code's own /compact pricing (INFERIDO, post hoc).
- **Adding pings to P1+P5 costs money**: -35k per session [-54k, -18k] (post hoc paired). A cold return that the
  handoff handles is cheaper than keeping a 300k prefix warm for an hour.

## Return-gap distribution (MEDIDO)

40,514 idle episodes (39,266 at a 1-hour TTL), including 751 uncensored session ends (400 at 1-hour, 351 at
5-minute TTL; the 5-minute ones are short or headless sessions).

| returns after | p10 | p25 | p50 | p75 | p90 |
|---|---:|---:|---:|---:|---:|
| > 5 min | 5.8 min | 8.0 min | 14.3 min | 61 min | 5.0 h |
| > 1 h | 1.3 h | 2.0 h | 4.2 h | 9.1 h | 16.7 h |

1-hour TTL episodes idle past 55 min (n = 814; D = 55 min, T = 60 min):

| user comes back | n | share | what a ping does |
|---|---:|---:|---|
| (55, 60] min | 18 | 2.2% | nothing, the cache was still warm |
| (60, 115] min | 91 | 11.2% | ping 1 rescues |
| (115, 170] min | 51 | 6.3% | ping 2 rescues |
| (170, 225] min | 44 | 5.4% | ping 3 rescues |
| (225, 280] min | 39 | 4.8% | ping 4 rescues |
| later than 280 min | 171 | 21.0% | every ping wasted |
| never (session end) | 400 | 49.1% | every ping wasted |

Rescue rate per ping, among episodes where that ping fired: ping 1 11.2% (91/814), ping 2 7.1% (51/715),
ping 3 6.6% (44/663), ping 4 6.4% (39/613).

### Break-even (INFERIDO)

- Analytic, one ping on a 1-hour cache: `0.1 / (2.0 - 0.1)` = **5.3%**.
- Empirical: mean ping cost 27.5k (0.1 x prefix) / mean benefit of a warm return after > 1 h 578k (p50 520k,
  n = 396) = **4.8%**.
- The first ping clears break-even about 2x. Pings 2-4 clear it by 1.2-1.3x, so they are close to a wash.

## Policy simulation (INFERIDO; 769 sessions, paired session bootstrap 2000, seed 20261019)

Saving = P0 cost - policy cost per session, in base-token equivalents; untouched sessions count as 0. "touched" =
any ping, stash pass or handoff. "vs P1" = paired per-session difference.

| policy | touched | touched cheaper | mean saving / session [95% CI] | total | vs P1 [95% CI] | pings / rescues | passes / handoffs | cost gate | verdict |
|---|---:|---:|---|---:|---|---:|---:|:-:|---|
| P1 (part 1) | 130 | 97.7% | +185k [+116k, +268k] | 9.3% | - | 0 / 0 | 396 / 0 | pass | conditional_opt_in |
| P4_K1 | 760 | 6.1% | +37k [+12k, +68k] | 1.9% | -148k [-211k, -93k] | 1,174 / 92 | 0 / 0 | fail | not recommended |
| P4_K2 | 760 | 7.9% | +48k [+13k, +93k] | 2.4% | -137k | 2,247 / 145 | 0 / 0 | fail | not recommended |
| P4_K4 | 760 | 10.0% | +67k [+9k, +138k] | 3.3% | -119k | 4,234 / 230 | 0 / 0 | fail | not recommended |
| P5 | 97 | 90.7% | **+550k [+334k, +810k]** | 27.6% | **+365k [+217k, +541k]** | 0 / 0 | 0 / 216 | pass | cost_only_candidate |
| P1+P4_K1 | 760 | 14.9% | +198k [+118k, +292k] | 9.9% | +13k [-3k, +33k] | 1,174 / 92 | 305 / 0 | fail | not recommended |
| P1+P4_K2 | 760 | 13.6% | +194k [+108k, +294k] | 9.7% | +9k [-14k, +38k] | 2,247 / 145 | 254 / 0 | fail | not recommended |
| P1+P4_K4 | 760 | 12.8% | +183k [+90k, +294k] | 9.2% | -2k [-36k, +42k] | 4,234 / 230 | 171 / 0 | fail | not recommended |
| **P1+P5** | 130 | 93.1% | **+570k [+349k, +837k]** | **28.6%** | **+385k [+230k, +570k]** | 0 / 0 | 184 / 212 | pass | **cost_only_candidate** |
| P1+P4_K1+P5 (expl.) | 760 | 14.1% | +536k [+313k, +796k] | 26.8% | +350k | 1,174 / 92 | 125 / 180 | fail | not recommended |
| P1+P4_K2+P5 (expl.) | 760 | 13.4% | +501k [+289k, +750k] | 25.1% | +316k | 2,247 / 145 | 96 / 158 | fail | not recommended |
| P1+P4_K4+P5 (expl.) | 760 | 13.3% | +431k [+242k, +654k] | 21.6% | +246k | 4,234 / 230 | 51 / 120 | fail | not recommended |

- Saving per idle episode with >= 1 ping (P4 alone): K1 +24k [+9k, +40k], K2 +32k [+9k, +54k], K4 +44k
  [+7k, +81k]. Ping overhead is 1.6% / 2.9% / 5.3% of total cost.
- P5 drops 29.8 M tokens over 216 handoffs (about 138k each) and cuts the mean context by 30%. P1+P5 runs 184 stash
  passes (expected removed-then-needed results: 172, vs 1,650 for P1 alone). Its 212 handoffs drop 29.2 M tokens,
  and their loss of knowledge is not measured.

### Sensitivity (mean saving per session [95% CI]; cost gate)

| run | P4_K1 | P4_K4 | P5 | P1+P4_K1 | P1+P5 |
|---|---|---|---|---|---|
| primary | +37k [12k, 68k]; fail | +67k [9k, 138k]; fail | +550k [334k, 810k]; pass | +198k; fail | +570k [349k, 837k]; pass |
| ping_turn (ping = real turn, +5k) | +30k [5k, 60k]; fail | +39k [-16k, 108k]; fail | = | +191k; fail | = |
| lead50 (ping at 50 min) | +28k [7k, 54k]; fail | +49k [-4k, 117k]; fail | = | +193k; fail | = |
| H30k | = | = | +493k [295k, 730k]; pass | = | +515k [307k, 762k]; pass |
| gen_native (/compact pricing) | = | = | +485k [286k, 725k]; pass | = | +506k [297k, 754k]; pass |
| gen_local (no model cost) | = | = | +637k [399k, 921k]; pass | = | +655k [410k, 948k]; pass |
| gen_prebuilt (summary while warm) | = | = | +576k [349k, 850k]; pass | = | +598k [361k, 881k]; pass |
| rho 0.15, q 0.5 | = | = | = | +81k; fail | +565k [345k, 829k]; pass |

`=` means the run does not touch that policy's inputs. P1 stays +185k [116k, 268k] in every run but rho/q
(+51k [31k, 74k]). With rho 0.15 / q 0.5, P1+P4_K1 does beat P1 (+8k to +59k), because P1 is weak there.

### Post hoc (not pre-registered; `when2-posthoc.json`)

| check | mean saving / session [95% CI] |
|---|---|
| P1+P5, handoff 50k | +444k [+258k, +665k] (native pricing +381k) |
| P1+P5, handoff 100k (regrowth proxy) | +304k [+166k, +470k] (native pricing +245k) |
| P5, handoff 100k | +265k [+140k, +415k] (native pricing +202k) |
| P1+P4_K1+P5 minus P1+P5 (paired) | -35k [-54k, -18k] |
| P1+P5 minus P5 (paired) | +20k [+11k, +31k] |

## Reading and recommendation (INFERIDO)

Pre-registered rule: pick the best robust policy in each class, and prefer the class with no content loss.
- **No content loss (P4)**: nothing is robust. Keep-warm has a positive expected value only because the first ping
  rescues 11% of long idles, against a 5% break-even. Its margin is thin, it pays on every session end, and it buys
  nothing once a handoff or stash handles cold returns. **Do not build it.** If someone wants it anyway: K = 1 only,
  for prefixes the user is likely to resume, and only after the open points below are checked.
- **Stash (P1 class)**: P1 stays the pick (`conditional_opt_in`, part 1). Pings do not improve it.
- **Handoff (P5 class)**: P1+P5 is the best robust policy on cost. Even the post hoc 100k regrowth proxy saves
  about 1.6x what P1 does. It is a `cost_only_candidate`. The study cannot say whether the agent works as well
  after a handoff.

**Best answer to the idle-return problem, given what was measured:** on a return after more than the TTL with a
large context (>= 50k droppable), **offer** a fresh session seeded with a compact handoff. Do it as a prompt the
user accepts, not silently, because quality is unmeasured. Fall back to the P1 stash for smaller contexts. Do not
keep the cache warm with pings. Before any default: measure handoff quality on real idle returns (task success,
re-reads in the first 10 requests, user corrections) and run the regrowth check on real data. Claude Code's bundle
already carries an "inactive for ... and is ... tokens long" resume prompt (part 1, not executed). Check whether it
already does this before building anything.

## Keep-warm caveats (stated, not verified)

- Pings use subscription quota and rate limits. They are automated requests nobody asked for. Whether the
  provider's terms or norms allow keep-alive traffic was **not checked**, and this study states no policy fact
  about it.
- A ping must reproduce the exact cached prefix (same model, system, tools, messages) to hit the cache. A Claude Code
  turn appends a message (covered by `ping_turn`). How a hook would send a prefix-identical request was not tested.
- The cost model assumes a cache read refreshes the TTL. That is how the part-1 traces behave, and it was not
  re-checked against current docs (no network).

## Limits

- Everything in part 1's Limits applies: one user, relative prices, live data, a fixed request sequence, and the
  cold/TTL heuristics.
- P5 is priced with no recall or regrowth cost. That favors P5. The post hoc 100k run is a proxy, not a measurement.
- The output factor 5.0 and the ping overhead (15 tokens) are INFERIDO. At these sizes they barely matter
  (`ping_turn` is 300x larger).
- The cost gate's "70% of touched sessions" rule penalizes policies that spread a small cost over many sessions,
  such as end-of-session pings. It was fixed in advance and applied as written. P4's mean saving has a CI above 0;
  the gate fails on the distribution.
- 13 policies and 7 sensitivity runs, with no multiplicity correction (disclosed in the protocol).
