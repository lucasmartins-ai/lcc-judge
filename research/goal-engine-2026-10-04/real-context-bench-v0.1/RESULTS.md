# Real-context bench v0.1 — Jev arms — results 2026-10-09

Exploratory (INFERIDO): one pass, 60 real Claude sessions, 47/60 labels LLM-made, probes
are mechanical proxies of taxonomy-v2 `context_needed`, token counts heuristic.
Counts only; per-item data stays in `~/.lcc/bench/real-context-v0/`. Score: `score.json`.

## Limits first

- **jev_transcript is not a valid measure of Jev.** 102 of its 379 requests failed and LCC
  fell back to keeping context: 77 were rejected by the API (`max_tokens_exceeded`: LCC's
  transcript mode builds requests larger than Jev accepts; failed requests had a median
  80,766 state chars), and 25 were blocked by this harness's own network guard (cause not
  established: the guard lift is already serialized by the meter lock, jev_block also
  batches on threads with 0 trips, and each trip happens once per affected item 15-20 ms
  after a successful call; reproduce before changing the guard). It is also partial: 42 ok, 9 TranscriptFitError, 1 stopped at the cap,
  8 not run. No item was re-run (protocol: no selective retries).
- jev_block is clean: 3,226/3,226 requests ok, 60/60 items, 0 failed calls.
- `zero_guard_trips` is false for every arm because the frozen scorer sums trips over all
  arms (all 25 come from jev_transcript; jev_block items record 0). This does not change
  any verdict: jev_block already fails the retention condition.

## Spend (US$85 hard cap, owner-approved before any call)

| Arm | Calls | Spend | Projection (cap basis / uninflated) |
|---|---:|---:|---:|
| jev_block | 3,226 | $43.52 (API-reported usage) | $42.29 / $31.03 |
| jev_transcript | 379 (102 failed) | $41.42 (277 API-reported; failed calls charged at projection) | $39.71 / $27.64 |
| Total | | **$84.93** | |

## Results (items with an applicable probe: n = 49)

| Arm | Item retention | Wilson 95% | Token reduction pooled / median item | Latency median |
|---|---:|---|---:|---:|
| full | 49/49 | .93–1.00 | 0 / 0 | — |
| mechanical | 48/49 | .89–1.00 | .0001 / 0 | 0.7 s |
| specialist (shadow) | 49/49 | .93–1.00 | 0 / 0 | 24.6 s |
| **jev_block** | **47/49** | .86–.99 | **.035 / 0** | 14.0 s |
| jev_transcript (invalid, see limits) | 30/49 | .47–.74 | .252 / .388 | — |

jev_block misses: general_question 0/1, handoff_prompt 3/4. jev_transcript on its 44
completed items with probes: 30/44 retention at .259 pooled reduction (mechanical 43/44).

## Reading

On real sessions, LCC block mode with Jev removes **3.5% of tokens** (median item 0%),
not the ~50% measured on curated corpora (docs/JEV.md), and loses 2/49 needed items.
The judge is not what limits reduction here: LCC's protection and block policy keep
almost everything regardless of provider. Transcript mode is where reduction exists
(~26–39%), but its requests overflow Jev and it drops needed context often (30/44).

Stop criterion: no arm wins (none keeps >= mechanical retention with strictly higher
reduction). For the local-model plan this changes the target: matching "Jev in LCC block
mode" is cheap (it barely cuts); the real work is a block/tool-call policy that cuts
safely, then a model for the decisions that policy leaves open.

## Follow-ups

1. LCC: transcript mode must fit requests to Jev's real token limit (77 rejections).
2. Harness: reproduce the 25 guard trips and fix their real cause before any further remote run.
3. Jev block decisions (3,226 requests) exported privately as candidate distillation
   labels: `~/.lcc/bench/real-context-v0/jev-decisions.jsonl` (to be generated).

## Independent review (2026-10-09): PASS_WITH_NOTES

Chronology (freeze 13:47:12Z, first remote call 13:58:33Z), spend ($84.93 from ledgers;
jev_block 100% API-reported), no key in either tree, no selective retries, and all
aggregates recompute. Notes: spend is modeled at the input rate for output tokens too
(807K output tokens in jev_block) and charges the 102 failed calls at projection — check
the TypeSafe invoice; PROTOCOL.md hash is unchanged since the freeze but not enforced by
the runner; the guard-trip cause above was corrected after review.
