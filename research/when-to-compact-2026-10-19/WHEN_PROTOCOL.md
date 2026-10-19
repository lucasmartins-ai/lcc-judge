# When should LCC stash, relative to prompt-cache state? (pre-registered)

Written and committed on 2026-10-19 before any gap, cost or policy outcome was computed. Owner approval in chat:
"pode seguir com o estudo de quando compactar". Code: `research/when_to_compact.py`, tests
`tests/test_when_to_compact.py` (synthetic traces). Hashes: `WHEN_PROTOCOL.json`. Before freezing, only these were
looked at: field names and event types in the transcripts, the compact_boundary metadata (43 rows, mostly manual,
preTokens up to ~970k), and population counts (765 main-session files, 40,514 own requests, 1,134 subagent traces).
No gap, cache or cost figure was computed before this commit.

## Why

v5 cycle 2 (`research/goal-engine-2026-10-04/specialist-v1/V5C2_RESULTS.md`) found that any stashed pass mutates the
prefix at about 2-3% of the context, so it invalidates almost the whole prompt cache whoever chooses the blocks. If
selection does not move the cache cost, timing might. Question: **is there a moment where stashing is close to free
for the cache, and does stashing then save money on real Claude Code sessions?**

## Data (private, read-only, metadata only)

- `~/.claude/projects/**/*.jsonl`. Read fields: `type`, `subtype`, `uuid`, `timestamp`, `isSidechain`, `requestId`,
  `message.model`, `message.usage` (input, cache read, cache creation with the 5m/1h split, output), and
  `compactMetadata.{trigger, preTokens, postTokens}` of `compact_boundary` rows. No message text is kept.
- One request = one `requestId` (Claude Code logs one row per content block; usage taken from the last row, time
  span from first to last row). `<synthetic>` rows are skipped.
- Main sessions = files outside `subagents/`, sidechain rows excluded. Subagent traces are used only for the TTL mix.
- Resume / fork copies: a request or boundary already seen in an earlier file keeps its place for gap and context
  reconstruction but is flagged `dup` and excluded from every count and cost. Files are ordered by first timestamp,
  ties by last timestamp (the original ends first).
- `~/.lcc/request-log/requests.jsonl` has no token or timing usage (its rows carry a goal text field, not read); it is
  not used.

## Cost model (INFERIDO; base-input-token equivalents)

uncached 1.0, cache read 0.10, 5-minute write 1.25, 1-hour write 2.0 (Anthropic prompt-caching multipliers; LCC's
`CACHE_ALIGNMENT.md` uses the same 0.10 / 1.25; the 2.0 for 1-hour writes was not re-fetched in this cycle, no network).
Output tokens do not change under any policy and are left out. Per request: `u + 0.1 r + 1.25 w5 + 2.0 w1h`.

- Context of a request `C = u + r + w5 + w1h`. TTL in force before a request: 1 hour if the newest earlier write was
  mostly 1h, else 5 minutes. Idle gap = start of this request minus end of the previous one.
- Segments: natural compaction boundaries split a session; `S` = first context of the segment (system, tools, and
  the compaction summary or first prompt); message context = `C - S`.

## Reduction model (from v5 cycle 2, stashed on 264 dev items)

- A pass removes `rho = 0.35` of the message context, minus what earlier passes in the segment already removed
  (cumulative removal `rho (C - S)` in trace terms; a second pass only takes new growth).
- First mutation offset `m = S + mu (C - S)`, `mu = 0.03`: system and tools stay cached, the message part is invalidated
  from 3% on.
- Recall: `q = 4.57 / 19.0 = 0.24` of removed tokens are USED next (results-weighted) and are recalled once, at the
  trigger request, written at that request's write price (pessimistic: full output, immediately). Net removal for later
  requests `(1 - q)` of the pass.
- Expected removed-then-needed results = removed tokens / 6,951 (V5C2: 8,386,129 tokens removed on 264 items, 4.57
  USED results stashed per item).

## How a policy changes the trace

- Trigger request k (pass right before it): context `C' = C - previous net removal - new removal`; cache read
  `min(r_k, m)`; uncached unchanged; the rest written at k's write mix (if k wrote nothing, the TTL in force); plus the
  recall write. If the cache was really cold, `r_k` is already small and the pass costs nothing extra; if it was warm,
  the invalidation is charged.
- Other requests: the cumulative net removal comes off cache reads first, then writes, then uncached input
  (conservative: reads are the cheapest to save).
- Natural compaction boundaries stay where they were (most are manual) and reset the removal.

## Policies

| name | trigger |
|---|---|
| P0 | none before Claude Code's own compaction (today) |
| **P1** | first request after an idle gap longer than the TTL in force (cache already expired) |
| **P1_min10k / P1_min50k** | P1, only when the pass would remove >= 10k / 50k tokens |
| **P1_5m** | idle gap > 5 minutes whatever the TTL (a hook that cannot see the TTL) |
| P2 | tail-only while warm: stash only outputs after the last cache breakpoint. Claude Code puts a breakpoint on the newest message each turn, so the tail is the newest outputs, which stashed's `preserve_recent` never removes: P2 = P0 by construction |
| warm_50k | contrast: stash whenever a pass would remove >= 50k, cache state ignored |

Candidates: P1, P1_min10k, P1_min50k, P1_5m. No multiplicity correction (four related candidates; disclosed).

## Questions and outputs

1. Descriptive (MEDIDO): 5m vs 1h share of cache writes (main, subagents); idle-gap distribution; share of requests
   after a gap > 5 min / > 1 h / > TTL and how many of them read < 50% of their context from cache (cold); tokens
   re-written after gaps and their share of total cost; per natural compaction: gap since the previous request, cold
   share (gap > TTL), pre/post tokens, the first post-compaction request's writes and reads, and an estimated cost
   (summarizer input at read price if warm else write price, plus the first request after; INFERIDO because the
   summarizer call is not in the transcript).
2. Simulation (INFERIDO): per policy, sessions touched, share of touched sessions cheaper than P0, mean saving per
   session with a session bootstrap 95% CI (2000 resamples, seed 20261019; untouched sessions count as 0), total
   saving share, mean context reduction, passes, expected removed-then-needed results.
   Sensitivity: rho 0.15; q 0.5; mu 0.10; rho 0.15 with q 0.5.
3. Feasibility (static reading of LCC 1.1.0 plugin code and docs, and of the Claude Code 2.1.296 bundle's hook
   declarations): which events could run P1. Anything not executed is marked UNVERIFIED.

## Acceptance (fixed now)

- **Cost gate**: among sessions where the policy fires, >= 70% are cheaper than P0, and the 95% CI lower bound of the
  mean per-session saving (all sessions) is > 0.
- **Harm gate**: expected removed-then-needed results per session not above P0. P0 runs no pass before the natural
  compaction, so **any policy that fires fails this gate by construction** under this proxy. Stated now so it is not
  read as a surprise.
- Verdict: `recommended` = both gates. `conditional_opt_in` = cost gate passes in the primary run and in every
  sensitivity run, harm gate fails: then the recommendation can only be an opt-in, off by default, with a field
  measurement of recall calls per pass, and a design note is written for that. Otherwise: not recommended.

## Limits declared up front

- One user's sessions, one machine; subscription traffic (prices are relative, not the bill).
- rho, q and mu come from another population (v5 cycle 2 dev items at arbitrary points), not from passes run at idle
  returns. Passes are simulated, not run.
- Claude Code may change breakpoint placement or TTL between releases; the trace is what it was.
- Removing context may change what the agent does next (shorter answers, fewer reads, a later or no compaction); the
  simulation keeps the observed request sequence fixed.
