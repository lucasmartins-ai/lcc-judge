# Real-context bench v0: results (2026-10-09)

Status: **exploratory (INFERIDO)**. Point estimates on 49 scored items; no significance claimed.
Protocol: `protocol.json`, sha256 `f5608429a3740bc74da04c6bd77071fe08cebd3ad887ae996a32ba1df5e490c3`, re-checked after `score` and unchanged since freeze.
Machine-readable counts: `score.json` (no ids, no per-item rows). Raw contexts, ids and per-item outputs stay under `~/.lcc/bench/real-context-v0/`.

## Limits (read first)

1. **The comparison is degenerate.** At `dd5dd80`, mechanical removes almost nothing (0.010% of tokens), and the specialist removes nothing because it is shadow-only. The verdict below compares two arms that are both close to "keep everything". It says nothing about whether a learned arm could cut more and still keep what is needed.
2. **The diagnostic arm did not run at mechanical's budget.** `specialist_rank_at_mechanical_budget` keeps the protected blocks plus the blocks in `report.specialist_ranking` order. On these contexts the ranking leaves out a median 53% of block characters (max 93%) that are not protected either. On 56 of 60 items the budget could not be reached, so the diagnostic cut 55% of tokens where mechanical cut 0.01%. Its retention (39/49) measures a much harsher cut than mechanical's and **must not be read as "specialist ranking at equal budget"**. A fix would need a protocol amendment, such as appending unranked blocks after the ranked ones. That was not done, because the protocol is frozen.
3. 47 of 60 labels come from a single LLM pass that the owner has not confirmed.
4. 11 of 60 items have no applicable probe and count for reduction only: specified_task 4/4, project_audit_or_direction 4/4, plus 1 each of failure_report, general_question and git_ship. NAMED_REFS was applicable 0 of 13 times. 12 of those goals name no path, file or URL, and the one ref found does not occur in its context. So **specified_task and project_audit_or_direction have no retention evidence at all**.
5. TASK_STATE was applicable 5 times and not applicable 30 times. GIT_STATE was applicable 2 times. Category cells have n = 1 to 5.
6. Probes check that a block survives verbatim, not that an answer is correct. Token counts are heuristic (`approximate:heuristic`).

## Run

| | full | mechanical | specialist |
|---|---|---|---|
| items run / ok | 60 / 60 | 60 / 60 | 60 / 60 |
| errors, timeouts > 600 s | 0 | 0 | 0 |
| network guard trips | 0 | 0 | 0 |
| provider_used | — | mechanical | specialist_shadow |

Sample phase re-derived the frozen 60-id allocation: 0 id mismatches, 0 empty contexts. Visible bytes: sum 14,918,591, median 200,186, max 952,654.
Sanity: full retained 49/49 items and 69/69 probes, so the run is **not void**.

## Per-arm results

| arm | item retention (k/n) | Wilson 95% | probe retention | token reduction pooled / median item | byte reduction pooled / median item | latency median / p90 (ms) |
|---|---|---|---|---|---|---|
| full | 49/49 = 1.000 | .927–1.000 | 69/69 | 0 / 0 | 0 / 0 | 0 / 0 |
| mechanical | 48/49 = .980 | .893–.996 | 68/69 | .0001 / 0 | .0001 / 0 | 697 / 6,582 |
| specialist | 49/49 = 1.000 | .927–1.000 | 69/69 | 0 / 0 | 0 / 0 | 24,554 / 89,705 |
| *diagnostic (see limit 2)* | *39/49 = .796* | *.664–.885* | *58/69* | *.554 / .527* | *.560 / .530* | — |

- **Mechanical in detail:** 3,051,935 tokens in and 3,051,621 out, so 314 tokens (0.010%) and 1,919 bytes removed. Over 60 items it dropped 65 blocks and trimmed none; 30 items lost at least one block, and only 1 item lost more than 1% (max 7.1%). At `dd5dd80`, mechanical drops only blocks with zero lexical overlap with the goal that nothing protects or pulls back in. The 0.4 threshold is not used by this provider. Its one failure was a LAST_AGENT_TURN probe on a supply_fact_or_step_done item. Max latency was 23,608 ms.
- **Specialist:** model load 3,756 ms, timed once. Per-item latency was about 35 times mechanical's at the median, with a max of 164,256 ms (under the 600 s timeout).

## Per-category item retention (k/n; n = items with at least one applicable probe)

| category | sampled | full | mechanical | specialist | diagnostic* |
|---|---|---|---|---|---|
| UNKNOWN | 5 | 5/5 | 5/5 | 5/5 | 5/5 |
| approve_or_pick | 5 | 5/5 | 5/5 | 5/5 | 4/5 |
| correct_approach_or_rule | 5 | 5/5 | 5/5 | 5/5 | 3/5 |
| environment_and_infra | 5 | 5/5 | 5/5 | 5/5 | 4/5 |
| external_accounts_and_comms | 5 | 5/5 | 5/5 | 5/5 | 3/5 |
| failure_report | 5 | 4/4 | 4/4 | 4/4 | 4/4 |
| general_question | 2 | 1/1 | 1/1 | 1/1 | 1/1 |
| git_ship | 4 | 3/3 | 3/3 | 3/3 | 3/3 |
| handoff_prompt | 4 | 4/4 | 4/4 | 4/4 | 4/4 |
| project_audit_or_direction | 4 | 0/0 | 0/0 | 0/0 | 0/0 |
| revise_recent_output | 4 | 4/4 | 4/4 | 4/4 | 1/4 |
| specified_task | 4 | 0/0 | 0/0 | 0/0 | 0/0 |
| supply_fact_or_step_done | 4 | 4/4 | 3/4 | 4/4 | 3/4 |
| task_status_or_control | 4 | 4/4 | 4/4 | 4/4 | 4/4 |

\* Diagnostic is not at budget (limit 2). Descriptive only, given n of 1 to 5 per cell. Wilson intervals are in `score.json`.

## Probe applicability

| probe | applicable | not applicable |
|---|---|---|
| LAST_AGENT_TURN | 46 | 0 |
| TASK_STATE | 5 | 30 |
| NAMED_REFS | 0 | 13 |
| ERROR_RESULT | 4 | 1 |
| GIT_STATE | 2 | 2 |
| LATEST_SUMMARY | 4 | 0 |
| LAST_ARTIFACT_EDIT | 4 | 0 |
| LAST_TOOL_RESULT | 4 | 0 |

## Stop-criterion verdict

The only learned candidate is the specialist. Its retention of 1.000 is at least mechanical's .980, which passes. Its pooled token reduction of 0 is **not** strictly above mechanical's .0001, which fails. Guard trips were 0, which passes.
**The specialist does not win.** This was expected by construction: it cannot mutate at `dd5dd80`. Given limit 1, the result also does not support saying that mechanical "works" on real contexts. Mechanical keeps the needed blocks because it keeps nearly all of them.

## Remote arms (designed, disabled, not run)

No network calls were made. These estimates come from `protocol.json`, which uses the docs/JEV.md rate of about $0.0042 per 1K tokens and counts tokens as bytes/4:

| arm | est. tokens | est. cost per pass |
|---|---|---|
| jev_block | 3.74M total; 50.2K median item ($0.21) | **≈ $15.70** |
| jev_transcript | about 5.3x state resend | **≈ $83** |

35 of 60 items exceed 44K tokens, the largest size Jev was measured at, so these figures are extrapolated.

## What would make v1 informative

- Use a learned arm that can actually drop blocks, and a baseline whose reduction is not about 0. For example, a lexical-threshold baseline, or the mechanical arm with protection and relational pull-in reported separately.
- Fix the diagnostic budget fill (rank unranked blocks last) as an explicit protocol amendment, with a new hash.
- Add probes for specified_task and project_audit_or_direction that do not depend on the goal naming paths.

## Review notes (2026-10-09, independent review PASS_WITH_NOTES)

- The freeze hashed protocol.json only. The harness was last edited after the smoke
  run and before the full runs; its post-run sha256 is `aaf5ff982885494ebd8c5399b4f7d8ecc924a42e8c2f48045f892490a82f20e2`. Logic matched the
  protocol on review, but chronology alone does not prove probe code was fixed first.
  v1 must hash the harness in the freeze.
- Probes are proxies for taxonomy-v2 `context_needed`, not literal derivations
  (e.g. git_ship does not probe "changes made this session").
- The network guard covers socket connect only; 0 trips plus HF offline flags is
  strong but not complete evidence of no traffic.
- The lcc-main worktree is merge commit 71bd8a3 whose tree equals dd5dd80.
