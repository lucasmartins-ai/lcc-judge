# Stashed v1: rules_mode=stashed (LCC 4719fde) on the 847 real-session dossiers

Pin `4719fde` (branch `claude/silly-chatelet-0500f9`), detached worktree `~/.lcc/bench/lcc-4719fde`. Script:
`research/stashed_v1.py`. Counts: `summary.json`. Per-item rows and the stash stay in `~/.lcc/bench/stashed-v1/`.
Single offline pass, no `workspace_root`, 0 guard trips, 0 errors, 0 degraded. Measured 2026-10-17.

## Limits (read first)

- **Mechanical only.** This proves that removed bytes are stored and come back byte-identical. It does NOT
  measure whether an agent calls `recall` when it needs a removed output, or whether task success holds.
  That needs an agent-in-the-loop eval (not run).
- No blind audit. The lossy arm's two failed blind audits still apply to *what* is removed; stashed removes a
  similar set but keeps it recallable.
- Hermes v0.6/v0.7 TEST sets are spent; read only.
- Stash size on this corpus: 7 114 unique blobs, 65 MB.

## Harness sanity

`lossless` (.0093) and `recoverable` (.0123) reproduce recoverable-v0.8 exactly on the same 847 items.
The independent stash checker (no lcc code) flags a tampered pointer (`sha_mismatch`) in a one-line test.

## Result

| set | items | lossless | recoverable | lossy | **stashed** | results stashed |
|---|---:|---:|---:|---:|---:|---:|
| claude_frozen_60 | 60 | .0034 | .0034 | .2417 | **.2480** | 645 |
| claude_fresh_60 | 60 | .0016 | .0024 | .2040 | **.2249** | 646 |
| claude_dev_326 | 326 | .0063 | .0067 | .2814 | **.2464** | 3 551 |
| codex_v04_test_60 | 60 | .0125 | .0160 | .2850 | **.3580** | 774 |
| codex_v05_dev_141 | 141 | .0185 | .0264 | .2614 | **.3219** | 1 583 |
| codex_v05_test_60 | 60 | .0153 | .0204 | .1914 | **.2515** | 558 |
| hermes_v06_test_60 (spent) | 60 | .0108 | .0108 | .3278 | **.3593** | 1 617 |
| hermes_v07_test_80 (spent) | 80 | .0033 | .0097 | .3439 | **.3795** | 1 456 |
| **all** | **847** | **.0093** | **.0123** | **.2790** | **.3013** | **10 830** |

Pooled token reduction, 1 − Σout/Σin, lcc tokenizer. Input 45 551 754 tokens.

Verification on `stashed`: lcc `verify_stashed` 0 violations, independent stash check 0, runtime fail-safe 0.
