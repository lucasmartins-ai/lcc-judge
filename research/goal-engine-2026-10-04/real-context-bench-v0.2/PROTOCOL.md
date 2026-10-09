# Real-context bench v0.2: offline rules arm (amendment of v0.1, frozen 2026-10-09)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` (this amendment) | `689da07bba68e7dfd627fa496bd26241980b7326f9566db9668403441182b9f0` |
| `research/real_context_bench.py` (v0/v0.1 harness, probes, scoring; unchanged since the v0.1 freeze) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` (new arm run path, per-baseline verdict) | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| amended v0.1 `protocol.json` | `9b2edeed79c4eef710e17b0608ea002e6de5812f9fae899c43ff7042ab3c7d5d` |
| v0 `protocol.json` | `f5608429a3740bc74da04c6bd77071fe08cebd3ad887ae996a32ba1df5e490c3` |

Committed and pushed before the arm runs. The runner refuses to start if any hash differs.

## What changes from v0.1

One offline arm is added. Sample (same 60 frozen ids), context rendering, probes, metrics,
stop criterion and privacy env are copied unchanged. No arm from v0/v0.1 is re-run; their
records are reused. No remote call is made and the network guard is never lifted.

## Arm

| arm | call |
|---|---|
| lcc_rules_transcript | `compact_transcript(TranscriptCompactionRequest(payload, question=goal, provider='rules'))`, every other field at its committed default (threshold 0.5, preserve_recent 6, trim_head_chars 300, min_reduction 0.25, ...) |

- LCC pin: branch `feat/transcript-rules-policy` (PR #45, not merged), commit
  `413b6f4478c3741e88125e2313b4a9f38b806a60`, worktree `/Users/Master/lcc-wt-rules`. The runner
  checks `lcc.__file__`, HEAD and a clean tracked tree.
- Payload: the v0.1 `transcript_payload` plus `is_error=true` on results flagged as errors in the
  session (a real Claude Code transcript carries this flag; v0.1 jev_transcript did not forward it).
- Output: rendered with v0.1 `apply_transcript` (dropped calls lose both blocks, trimmed results
  take LCC's text, text blocks never change).
- One pass, sample order, no retries, 600 s per item; an error or timeout fails every applicable probe.
- Development used only 326 dev dossiers outside the frozen sample and its sessions; the 60 frozen
  ids were not opened.

## Verdict

v0 stop criterion, applied twice: vs **mechanical** and vs **jev_block** (both full 60-item runs).
Wins iff item retention >= baseline AND pooled token reduction strictly > baseline AND zero guard
trips in the candidate arm. (The frozen aggregate verdict sums trips over every arm, which
includes jev_transcript's 25 v0.1 trips; v0.2 counts the candidate's own.) Point estimates decide;
n is about 49 scored items, so the outcome is exploratory and no significance is claimed.
`full` must still score 100% or the run is void.
