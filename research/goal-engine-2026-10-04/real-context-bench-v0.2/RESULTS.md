# Real-context bench v0.2 — offline rules arm — results 2026-10-09

INFERIDO (exploratory): one offline pass, 60 real Claude sessions, 47/60 labels LLM-made, probes
are mechanical proxies of taxonomy-v2 `context_needed`, token counts heuristic
(`approximate:heuristic`). Counts only; per-item data stays in `~/.lcc/bench/real-context-v0/`.
Score: `score.json`. Freeze commit `1239766` (pushed 2026-10-09 before the run, 19:00:48Z).

## Limits first

- **Retention is mostly guaranteed by construction.** 50 of the 69 applicable probe instances
  target text blocks (LAST_AGENT_TURN 46, LATEST_SUMMARY 4), and `compact_transcript` never edits
  text. Only 19 probe instances test tool blocks (TASK_STATE 5, ERROR_RESULT 4,
  LAST_ARTIFACT_EDIT 4, LAST_TOOL_RESULT 4, GIT_STATE 2, NAMED_REFS 0). The arm passed all 19.
- **The rules mirror the probes.** The policy's protect rules (latest error, git state, task state,
  artifact edit, tool result, names in the goal) were written against the same probe definitions on a
  dev split. The frozen 60 ids were never opened during development, but a 100% here means "the
  policy keeps what these probes look for", not "the policy keeps what the user needed".
- n = 49 scored items (11 have no applicable probe); category cells hold 1–5 items. No significance
  is claimed. Wilson lower bounds overlap for every arm except jev_transcript.
- The arm forwards `is_error` (as a real Claude Code transcript does); v0.1 jev_transcript did not.
  Dev showed 2/323 ERROR_RESULT misses without the flag.
- Pinned to an unmerged branch (`feat/transcript-rules-policy` @ `413b6f4`, LCC PR #45).

## Results (items with an applicable probe: n = 49)

| Arm | Item retention | Wilson 95% | Probe retention | Token reduction pooled / median item | Latency median / p90 |
|---|---:|---|---:|---:|---:|
| full | 49/49 | .93–1.00 | 69/69 | 0 / 0 | — |
| mechanical | 48/49 | .89–1.00 | 68/69 | .0001 / 0 | 697 ms / 6.6 s |
| specialist (shadow) | 49/49 | .93–1.00 | 69/69 | 0 / 0 | 24.6 s / 89.7 s |
| jev_block (v0.1) | 47/49 | .86–.99 | 67/69 | .035 / 0 | 14.0 s / 37.0 s |
| jev_transcript (v0.1, invalid) | 30/49 | .47–.74 | 42/69 | .252 / .385 | 2.5 s / 6.1 s |
| **lcc_rules_transcript** | **49/49** | .93–1.00 | **69/69** | **.386 / .379** | **7 ms / 18 ms** |

Bytes: .387 pooled / .378 median item. 60/60 items ok, 0 errors, 0 timeouts, 0 guard trips in
this arm, 0 remote calls, $0. `full` scored 49/49, so the run is not void.

Per category (rules / mechanical / jev_block): all cells equal at k = n except
supply_fact_or_step_done 4/4 / 3/4 / 4/4, general_question 1/1 / 1/1 / 0/1,
handoff_prompt 4/4 / 4/4 / 3/4.

Decisions over 5,984 tool calls: 814 dropped (495 stale read far from recent work, 319 superseded
by a later call), 655 large old outputs trimmed, the rest kept (231 by a protect rule, 108 pinned recent). Every item
ran the rules provider undegraded; 2 items cut under 5% (1 at 0).

## Stop criterion

| vs | retention ≥ | token reduction > | zero guard trips (arm) | wins |
|---|---|---|---|---|
| mechanical | 1.000 ≥ .980 | .386 > .0001 | yes | **yes** |
| jev_block | 1.000 ≥ .959 | .386 > .035 | yes | **yes** |

The frozen aggregate `verdict` (v0 rule) still reports `zero_guard_trips: false` because it sums
trips over every arm, including jev_transcript's 25 v0.1 trips; the pre-registered v0.2 verdict
(`verdict_v02`) counts the candidate arm's own trips.

## Reading

On the same 60 real sessions, the offline rules policy cuts ~39% of tokens (pooled and median) with
no probe loss, in milliseconds, with no API. That matches dev (326 items: 323/323, .389). It beats
jev_block (3.5% cut, $43.52) on both conditions. Given the limits above, the next measurement that
would change confidence is a probe set that is not derived from the same rules (e.g. owner review
of what each request actually used), not a larger rerun of these probes.
