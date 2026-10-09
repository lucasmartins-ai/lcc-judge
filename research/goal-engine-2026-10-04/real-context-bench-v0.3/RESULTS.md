# Status: independent review FAIL (2026-10-10) — not a held-out result

Read this first. The review found that the "fresh" 60 items share all 25 sessions (and most
tool calls) with the frozen 60, so v0.3 is not independent of v0/v0.2; the drop audit
deviated from the pre-registered plan (judge routing: one judge saw all 150 and drops-c had a
single judge; the "any judge flags" assembly and aggregation script were written after the
verdicts; trim packets showed the original clipped to head+tail 1,500 chars, i.e. mostly the
same text the trim keeps, so judges saw little of the removed middle). The counts below are
recorded as exploratory observations only. A valid held-out check needs session-disjoint data
(e.g. Codex sessions or sessions recorded after 2026-10-09), two judges per record with the
assembly fixed in advance, and trim packets that show the removed middle.

# Real-context bench v0.3: fresh 60 + blind drop audit, results 2026-10-09

INFERIDO (exploratory). One offline pass over 60 fresh real Claude Code contexts. All 60 labels
are LLM-made, token counts are heuristic (`approximate:heuristic`), and the audit was judged by
Claude subagents, not the owner. This file holds counts only. Per-item data, packets, verdicts
and the unblinding key stay in `~/.lcc/bench/real-context-v0/`. Machine-readable files:
`score.json` (probes and reduction, plus an `audit` block) and `audit-summary.json` (audit).
Freeze commit `a74d8b3` was pushed before either arm ran. Policy pin: LCC
`feat/transcript-rules-policy` @ `8997be6` (PR #45, not merged).

## Limits first

- **The audit passes by the smallest possible margin.** Seven records were judged needed or
  unsure. Seven is the most the pre-registered rule allows at n = 150: the upper Wilson bound is
  .0932 against a .10 limit, and an eighth flagged record would have failed the run. Treat the
  PASS as a boundary result, not as a comfortable margin.
- **Judging did not follow the planned routing.** The plan was one judge per file, each seeing
  only its own 50 records. In practice:
  - Judge "a" got `drops.jsonl`, so it saw all 150 records.
  - Judges "b" and "c" got `drops-a` and `drops-b`.
  - File `drops-c` (50 records) was judged by judge "a" alone.

  No judge saw the key. 100 records were judged twice, and the judges agreed on 99 of them; the
  one disagreement was an unsure versus a not_needed. The primary assembly below is the
  conservative one: a record counts against the policy if any judge flagged it. The other two
  assemblies give the same verdict (see Sensitivity).
- **Judge "a" barely explained its verdicts.** All 143 of its not_needed verdicts carry the same
  one-line reason. The verdict values agree with the two other judges, but nobody wrote a reason
  per record for those 143.
- **No owner review.** All judges were Claude subagents working only from the packet. Each packet
  showed the last 3 text turns and the tool output, clipped head+tail to 3000 characters, so a
  judge could miss a dependency that sat outside that window.
- **Probe retention is by construction.** Only 22 of the 77 applicable probe instances test tool
  blocks, and those use the policy's own predicates (stated in `PROTOCOL.md` before the run). The
  audit is the only check here that does not share the policy's code.
- **Sample shape.** The 150 audited records come from 58 items, at most 3 per item (the cap was
  6). They cover 69 drops and 81 trims, out of a population of 1,408 decisions (584 drops, 824
  trims). Every rule and tool cell holds 1 to 81 records, so the per-cell rates are descriptive
  only.
- **Shared sessions.** All 60 fresh items come from the 25 sessions that also hold frozen-60
  items. No item shares a session with the dev split.
- **Mechanical baseline.** The mechanical arm ran on the rules pin, not the v0 pin `dd5dd80`, so
  its numbers do not reproduce v0.

## Probes and reduction (n = 55 items with an applicable probe)

| Arm | Item retention | Wilson 95% | Probe retention | Token reduction pooled / median item | Latency median / p90 |
|---|---:|---|---:|---:|---:|
| full | 55/55 | .935–1.00 | 77/77 | 0 / 0 | n/a |
| mechanical | 54/55 | .904–.997 | 76/77 | .0001 / 0 | 881 ms / 4.4 s |
| **lcc_rules_transcript** | **55/55** | .935–1.00 | **77/77** | **.350 / .364** | **8.5 ms / 24 ms** |

- Bytes: .352 pooled and .363 median item.
- Both arms: 60/60 ok, 0 errors, 0 guard trips. Remote calls: 0.
- The full arm scored 55/55, so the run is not void.
- Against mechanical, the v0 stop criterion gives a win: retention is greater or equal, reduction
  is strictly higher, and there were 0 guard trips.
- Per-call decisions recorded by the rules arm: 5,789 (the report field `tool_calls_total` sums to 6,156):
  - dropped: 584 (447 stale reads far from recent work, 137 superseded by a later call)
  - trimmed: 824 large old outputs
  - kept: 4,381 (343 by a protect or pin rule, 4,038 by default)

## Blind drop audit (pre-registered acceptance)

| Measure | k / n | Rate | Wilson 95% |
|---|---:|---:|---|
| **Primary: false-drop rate (needed + unsure) / judged** | **7 / 150** | **.047** | **.023–.093** |
| Secondary: needed / (needed + not_needed), unsure excluded | 1 / 144 | .007 | .001–.038 |
| Unsure rate | 6 / 150 | .040 | n/a |

**Acceptance: PASS.** The rule passes if the upper Wilson bound is at or below .10. Here the bound
is .0932, which is exactly the pass limit for n = 150 (at most k = 7).

### Breakdown (conservative assembly; needed / unsure / judged)

| By decision and rule | Needed | Unsure | Judged | Primary Wilson 95% |
|---|---:|---:|---:|---|
| drop: stale read far from recent work | 0 | 2 | 44 | .013–.151 |
| drop: superseded by a later call | 0 | 1 | 25 | .007–.195 |
| **drop total** | 0 | 3 | 69 | .015–.120 |
| trim: large old output | 1 | 3 | 81 | .019–.120 |

| By tool | Needed | Unsure | Judged |
|---|---:|---:|---:|
| Bash | 0 | 2 | 67 |
| Read | 0 | 3 | 52 |
| MCP tools (all servers) | 1 | 1 | 26 |
| Write | 0 | 0 | 3 |
| Agent | 0 | 0 | 1 |
| WebSearch | 0 | 0 | 1 |

What the flagged records were, from the judges' one-line reasons (no content):

- **The one needed (a trim).** The removed middle of an MCP tool output (the trim keeps head + tail) held a message that
  explained a pending account status, and the user's request asked about that status.
- **The six unsure:**
  - three trims: usage statistics, CRM notes, and a verification message;
  - two stale-read drops: a skill's composition contract, and a config mapping;
  - one superseded drop: the file that was about to be edited.

  In each case the judges said the content might bear on the request but they could not tell
  from the packet.

### Sensitivity (same data, other assemblies)

| Assembly | needed + unsure / judged | Upper Wilson | Result |
|---|---:|---:|---|
| Conservative: any judge flags it (primary) | 7 / 150 | .0932 | PASS |
| Judge "a" alone (saw all 150) | 7 / 150 | .0932 | PASS |
| One judge per file (b for file a, c for file b, a for file c) | 6 / 150 | .0845 | PASS |

The key was joined to the private rules run, matching (item, tool_use_id). All 150 rows match the
run's decision and reason: 0 mismatches. Aggregation code:
`research/real_context_bench_v03_audit.py`.

## Reading

On 60 real contexts that nobody looked at during development, the fixed rules policy (`8997be6`)
cut about 35% of tokens in milliseconds, offline. Its probe retention is perfect, but that is
mostly by construction. Read blind, about 1 in 21 of the removals or trims it made was flagged as
possibly needed (7/150), and only one was judged clearly needed. That needed case was a trim of
an MCP output whose removed middle held the answer.

This clears the pre-registered bar, but only just, and the judges were LLMs who could see only
the clipped packets. The cheapest next checks that could change confidence:

1. The owner re-judges the 7 flagged records and a random 20 of the not_needed ones.
2. Look at the trim rule on MCP and other non-file outputs. The removed middle can hold status
   and result lines, and this is the only cell with a needed verdict.
