# v5 cycle 2: ranking vs `stashed` on tool outputs only (results)

Produced on 2026-10-19 by `python -m research.v5c2 stash | bench | score | edge` under `V5C2_PROTOCOL.md`
(committed in 3bb2db8 before any dev scoring). Aggregates only. Machine-readable: `v5c2-results.json`,
`v5c2-bench.json`, `v5c2-edge.json`. Labels: **MEDIDO** for the numbers on this set; every reading of them is
**INFERIDO** (`gateClaim` was not run). No model calls.

## Bottom line

- **No candidate replaces stashed's choice.** v3, v5c2 and v5c2_ct all fail non-inferiority on all-kept (CI lower
  bounds -0.071 / -0.085 / -0.094, margin -0.005) and none is superior on any metric. stashed stays as is.
- **Recall leans toward the rankers but stays inside the noise**: v3 +0.032 [-0.016, +0.079], v5c2 +0.029
  [-0.022, +0.077]. All-kept leans the other way: v3 -0.011, v5c2 -0.023.
- **To match stashed's tokens, rankers stash about 2.8x more results** (53.5 vs 19.0 per item) and more USED
  results (6.5 vs 4.6 per item): more `recall` calls for the agent. Our reading (INFERIDO): they pick many small
  outputs where stashed takes a few large old ones. Token parity is approximate. Rankers drop whole results until
  they reach the budget, so they remove about 3% more tokens: 8.65 M vs 8.39 M, median per-item ratio 1.035. Net
  of the 11-token stash notes they still save slightly more: 8.50 M vs 8.33 M. The overshoot works against the
  rankers' recall, not for it.
- **Cache cost is the same for every arm.** Each arm's first removal sits at about 2-3% of the context, so
  almost the whole prefix is invalidated either way (median 54-56 k tokens; break-even about 32 reuses). The
  cache-aware tie-break moved the median first mutation from 1,200 to 1,346 tokens and changed nothing material.
- **Budgets met**: v5c2 median 167.7 ms (v3 129.0 ms in the same run, load average 6), peak RSS 162.5 MB.
  Cycle 1 measured v5 under load average 65-178; that load probably explains most of the overrun (INFERIDO, not
  re-measured). The score-only fast path cut detector time by 42% on design items. The ratio v5c2 / v3 = 1.30 is
  MEDIDO, from one run.

## Population (dev, 325 items)

| stage | items |
|---|---:|
| transcript rebuilt + stashed ran, 0 `verify_stashed` violations, 0 fail-safes, 0 network-guard trips | 325 |
| stashed removes nothing | 38 |
| no USED tool output in the stash-safe pool | 23 |
| **eligible** (95 session groups: claude 75, codex 67, hermes 122) | **264** |

Per eligible item (medians): 75.5 results in the stash-safe pool, stashed removes 14 of them, i.e. 56% of
tool-output tokens and 35% of all context tokens.

## Matched budget (264 items; arm - stashed, paired group bootstrap, 2000 resamples, seed 20261019)

| arm | recall | all-kept | recall vs stashed [95% CI] | all-kept vs stashed [95% CI] | results removed / item | USED results stashed / item | items with >= 1 USED stashed |
|---|---:|---:|---|---|---:|---:|---:|
| **stashed** | 0.590 | 0.224 | - | - | 19.0 | 4.57 | 205 |
| v3 | 0.622 | 0.212 | +0.032 [-0.016, +0.079] | -0.011 [-0.071, +0.052] | 53.5 | 6.46 | 208 |
| v5c2 | 0.618 | 0.201 | +0.029 [-0.022, +0.077] | -0.023 [-0.085, +0.040] | 53.6 | 6.47 | 211 |
| v5c2_ct | 0.617 | 0.189 | +0.027 [-0.025, +0.076] | -0.034 [-0.094, +0.026] | 56.4 | 7.03 | 214 |
| recency | 0.578 | 0.205 | -0.012 [-0.046, +0.024] | -0.019 [-0.064, +0.028] | 31.9 | 5.42 | 210 |
| mechanical | 0.564 | 0.178 | -0.026 [-0.062, +0.009] | -0.046 [-0.090, -0.005] | 50.7 | 8.36 | 217 |
| bm25 | 0.507 | 0.144 | -0.082 [-0.135, -0.028] | -0.080 [-0.135, -0.021] | 56.5 | 9.32 | 226 |

With `used_loose` the order is the same (stashed 5.5 loose-used results stashed per item, v3 7.9, v5c2 8.0).

Per source (recall / all-kept):

| source | n | stashed | v3 | v5c2 |
|---|---:|---|---|---|
| claude | 75 | **0.616 / 0.307** | 0.593 / 0.213 | 0.593 / 0.213 |
| codex | 67 | 0.663 / 0.209 | **0.750 / 0.358** | 0.740 / 0.313 |
| hermes | 122 | 0.533 / 0.180 | 0.569 / 0.131 | 0.567 / 0.131 |

On Claude Code sessions (the owner's live plugin) stashed's own choice is the better one on both metrics; the
rankers' recall lead comes from Codex and Hermes. Per-source n is small; this split was not pre-declared as a test.

## Cache cost (LCC factors: read 0.10, write 1.25)

| arm | first mutation offset, median tokens | share of context | invalidated tokens, median | invalidated, sum | break-even reuses, median |
|---|---:|---:|---:|---:|---:|
| stashed | 1,428 | 0.03 | 56,134 | 18.65 M | 32.6 |
| v3 | 1,200 | 0.02 | 54,687 | 18.65 M | 32.1 |
| v5c2 | 1,200 | 0.02 | 54,687 | 18.64 M | 32.0 |
| v5c2_ct | 1,346 | 0.03 | 53,870 | 18.48 M | 31.9 |
| recency | 411 | 0.01 | 56,371 | 18.94 M | 33.3 |
| mechanical | 624 | 0.02 | 55,924 | 18.70 M | 33.4 |
| bm25 | 773 | 0.02 | 54,622 | 18.62 M | 33.0 |

Every arm passes the cache gate (median invalidated <= 1.10 x stashed). Reading (INFERIDO): any pass that removes a
third of the context from old outputs mutates the prefix near its start, so a stash pass is a cache epoch whoever
picks the blocks. The cost question is *when* to run it (after a cache expiry, or behind a protected prefix), not
*what* to stash.

## Budgets (same run, fresh process, 1 thread, 325 dev items)

| model | ms median | ms p90 | peak RSS MB | model KB | load avg 1 m |
|---|---:|---:|---:|---:|---:|
| v5c2 | 167.7 | 432.0 | 162.5 | 183 | 6.2 |
| v3 | 129.0 | 325.1 | 165.8 | 183 | 5.6 |

v5c2 / v3 = 1.30 (cycle 1: 1.7-2.1 under heavy load).

## Dev-edge v2, tool-output gold only (77 of 81 cases; descriptive, design data)

Passes at 30 / 50 / 70% of tool-output tokens: mechanical 67/52/35, **v5c2 59/45/28**, bm25 56/36/29, v3 53/34/21,
recency 43/16/1. v5c2 gains over v3 on git_wide_view (2/1/1 -> 7/6/5), pt_en_mixed (4/1/0 -> 4/3/1),
qualifier_exception and general; loses one case on structured_config at 70%. Mechanical leads here, probably (not checked) because
the synthetic gold often names goal terms that LCC's lexical score and protection pick up; on real dev items
mechanical is below stashed.

## Reading (INFERIDO)

- stashed's rules (stale reads far from recent work, large old outputs, superseded reads) are already a good
  "what to stash" policy for Claude Code sessions. A next-action ranker forced to remove the same tokens spreads the
  cut over many small outputs and stashes more of what the agent uses next.
- The rankers' recall edge is token-weighted: they keep more USED tokens but break more items. That fits a ranker
  that protects big used outputs and drops many small ones.
- Nothing here argues for putting v3 / v5 in the live stashed path. If ranking comes back, the natural slot is
  inside stashed's eligible set (re-order or veto among what stashed already picks), not a free choice over the
  pool. That needs its own protocol.

## Limits

- USED is next-action evidence, not a recall log; it is a proxy for "would have needed a recall".
- Transcripts were rebuilt from LCC blocks (synthetic call ids, normalised blank lines); stashed ran on the
  rebuild, not on the original JSONL.
- The dev split was read in cycle 1 (selection and an ablation); no detector was tuned on it in this cycle.
- Three candidates without a multiplicity correction (disclosed in the protocol); it does not matter, none passed.
- One machine, one run; latency from a quiet-ish shared machine (load average 6).

## Independent review (read-only, Sonnet subagent, 2026-10-19)

**Verdict: PASS WITH NOTES.** The reviewer found no bug that could change the verdict. The 14 unit tests pass, the
doc's tables match the json, the protocol hashes match the committed files, and the new public files hold
aggregates only. Its reading confirms that `score_only` gives identical scores.

Notes, and what was done with each:
1. The matched budget is looser than "within one result". A block that spans two results counts in both result
   budgets, and rankers overshoot by about 3%. Now disclosed above. The overshoot penalises the rankers.
2. "Same token saving" ignored the cost of the stash notes, and "many small outputs" was stated as fact. Fixed
   above: net-of-notes figures added, and the reading is tagged INFERIDO.
3. The cause of the cycle-1 latency overrun was asserted, not measured. Now tagged INFERIDO.
4. `test_score_only_keeps_scores` only exercises a prod goal. The non-prod skip, the main speed-up, has no direct
   unit test; only the 416-item identity check covers it. Left for the next cycle: test files are hashed in the
   frozen protocol.
5. The pool does not exclude results made only of LCC-protected blocks (< 40 chars). This affects every arm the
   same way and is negligible.
6. The per-source split has no CI. It was not pre-declared, and the doc already says so.
