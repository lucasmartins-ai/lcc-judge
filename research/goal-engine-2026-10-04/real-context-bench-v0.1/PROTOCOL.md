# Real-context bench v0.1: remote Jev arms (amendment, frozen 2026-10-09)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` (this amendment) | `f7d8bf14db66acd5ea40a7b7c4345a0fa67a41d129f30c7005e99394ec9a99b4` |
| `research/real_context_bench.py` (harness, probes, scoring) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| amended v0 `protocol.json` | `f5608429a3740bc74da04c6bd77071fe08cebd3ad887ae996a32ba1df5e490c3` |

These hashes were recorded before any remote call. The runner refuses to start if any of them differs.

## What changes from v0

Only one thing changes: the two remote arms are enabled. The 60 sample ids, the context rendering, the probes, the metrics, the stop criterion, the pins and the privacy environment are all copied from v0 unchanged. The offline arms (full, mechanical, specialist) are not re-run; their v0 records are reused.

The owner approved this in chat on 2026-10-09: run both Jev arms on the same 60 items, send raw session context to the TypeSafe System One API, and stay under a **hard cap of US$35** in total.

## Arms

| arm | call (LCC `dd5dd80`) |
|---|---|
| jev_block | `compact_context(provider='jev', threshold=0.4, min_block_chars=40, max_block_chars=6000, trim_head_chars=300, model='gpt-4.1', batch_size=8, max_state_chars=12000, max_workers=1, jev_model='jev-latest', enable_semantic_verify=False)` |
| jev_transcript | `compact_transcript(provider='jev', threshold=0.5, preserve_recent=6, trim_head_chars=300, max_state_tokens=25000, max_request_tokens=30000, batch_calls=8, max_workers=1, model='gpt-4.1', jev_model='jev-latest')` |

- **jev_block** splits the context with the same parameters as v0 mechanical, so both arms see the same blocks. The remaining parameters are LCC defaults.
- **jev_transcript** uses LCC defaults throughout. The input has one message per context record. The output is the v0 rendering of the dossier blocks, with these changes: a dropped call loses both its tool_use and its tool_result block, and a trimmed result is replaced by LCC's trimmed text. Text blocks are never changed.

## Cost, calls and failures

- **Pricing:** $4.25 per 1M input tokens, plus 437 tokens per call (docs/JEV.md). When the API reports a cost or a token usage, that figure replaces the projection.
- **Cap check before every HTTP request.** The projected cost of the request is `(LCC pre-flight token count + 437) × rate`. The token count is offline, so it is the heuristic ×1.45, which is conservative. The request is not sent if either of these is true:
  - this arm's spend plus the projection would pass **$17.50**;
  - both arms' spend plus the projection would pass **$35**.

  In that case the run stops cleanly. The current item is marked `aborted_cap`, later items are not run, and the run is reported as **partial**. Spend is charged before the request leaves. A failed request keeps its projected charge.
- **Concurrency is 1 on the wire.** A lock in the meter serializes requests. This matters because `compact_transcript` ignores `max_workers`.
- **No retries.** The client is built with `JevClient.from_env(attempts=1)`; LCC's default is 3 attempts. A failed item stays failed and is never re-run. The runner refuses to write into an arm directory that already holds records.
- **Timeouts:** 1800 s per item, 45 s per request.
- **Run order:** `Random(20261009).shuffle(sorted ids)`, the same order for both arms. A capped run therefore covers a random subset across strata, and the completed sets of the two arms are prefixes of one list. jev_block runs first.
- **Network:** the v0 socket guard stays on and is lifted only inside the metered request. Any other connection voids the run.
- **Key:** it is never printed, logged or written. Every record is scrubbed for it before it is written. If no key resolves, the runner refuses to run.

## Offline projection (`project-cost`, before any remote call)

LCC's real batching and pre-flight were replayed with a fake transport. On `dd5dd80` the batches do not depend on the answers, so the call counts are exact. The counts-only result is in `project-cost.json`.

| arm | calls | cap-basis USD | uninflated USD | notes |
|---|---|---|---|---|
| jev_block | 3,226 (median 45.5 per item, max 157) | 42.29 | 31.03 | 0 pre-flight refusals |
| jev_transcript | 445 (median 6, max 21) | 39.71 | 27.64 | 9 items raise `TranscriptFitError` (no call; they count as arm errors) |

**Neither arm completes a full pass under its $17.50 share.** The run is expected to be partial, with roughly half of the items per arm at the uninflated rate. The v0 estimate of $15.70 for block mode undercounted, because the per-block question text and the clipped block heads cost more than bytes/4 of the context.

## Scoring

- **Intent to treat:** all 60 items. An item that was not run, or was aborted at the cap, fails every applicable probe.
- **Completed only:** when an arm is partial, it is compared with mechanical on the items it completed. The stop criterion ("on the same items") is decided on this comparison, and the intent-to-treat result is reported next to it.
- **Cost:** per arm, from `_cost.json`.

The repo receives counts only. Raw contexts, Jev outputs, `_cost.json` and the LCC ledger stay under `/Users/Master/.lcc/bench/real-context-v0/runs/<arm>/`.

## Commands (pinned interpreter, never `-I`)

```bash
P="PYTHONPATH=/Users/Master/.lcc/bench/real-context-v0/lcc-main/src:/Users/Master/Downloads/LCC-judge HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1"
env $P /Users/Master/LCC/.venv/bin/python -m research.real_context_bench project-cost
env $P /Users/Master/LCC/.venv/bin/python -m research.real_context_bench run --arm jev_block --allow-remote
env $P /Users/Master/LCC/.venv/bin/python -m research.real_context_bench run --arm jev_transcript --allow-remote
env $P /Users/Master/LCC/.venv/bin/python -m research.real_context_bench score --protocol v0.1
```
