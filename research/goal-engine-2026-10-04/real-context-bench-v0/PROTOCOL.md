# Real-context bench v0: frozen protocol (2026-10-09)

Machine-readable spec: `protocol.json`.
**sha256(protocol.json) = `f5608429a3740bc74da04c6bd77071fe08cebd3ad887ae996a32ba1df5e490c3`**
This hash was recorded before any run, and is also in `protocol.json.sha256`. The runner must refuse to start if the hash differs.
If `protocol.json` disagrees with this file, `protocol.json` is the one that counts.

## Question

The bench uses the owner's real Claude Code contexts. It asks whether a learned LCC arm keeps what each request category needs, at least as well as LCC mechanical does, while removing strictly more.

## Privacy and offline rules

- Prompt texts, rendered contexts, sample ids and per-item outputs live only under `/Users/Master/.lcc/bench/real-context-v0/`. This folder holds definitions, counts and aggregate metrics only.
- During a run, `socket.connect` and `create_connection` raise; a guard trip voids the run. `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`; nothing is installed.
- LCC is pinned to the detached worktree `.../real-context-v0/lcc-main` at `dd5dd80`, run with `/Users/Master/LCC/.venv/bin/python` (never `-I`; assert `lcc.__file__` is under `lcc-main/src`).

## Sample (60 items, seed 20261009)

- **Pool:** 693 claude prompts from `~/.lcc/request-log/imported/claude.jsonl`, all mapped back to their transcript record.
- **Eligible:** 595 have at least one assistant record before the prompt. Low-confidence labels are excluded.
- **Labels, in order of precedence:**
  1. Owner judgments (v1 review, v2 held-out review).
  2. The 6-labeler taxonomy-v2 pass (91 usable claude items).
  3. New labels for the 504 previously unlabeled usable claude prompts. **Claude made these in one LLM pass, using the taxonomy-v2 rules, for this bench. They are not owner-confirmed.** Owner-confirmed items were never relabeled.
- **Allocation:** 4 items per stratum, capped by availability. The leftover is filled round-robin, in alphabetical stratum order. Within each stratum, ids are sorted and then shuffled with the seed.

| stratum | eligible | sampled |
|---|---|---|
| UNKNOWN | 39 | 5 |
| approve_or_pick | 105 | 5 |
| correct_approach_or_rule | 34 | 5 |
| environment_and_infra | 17 | 5 |
| external_accounts_and_comms | 7 | 5 |
| failure_report | 26 | 5 |
| general_question | 2 | 2 |
| git_ship | 70 | 4 |
| handoff_prompt | 54 | 4 |
| project_audit_or_direction | 4 | 4 |
| revise_recent_output | 40 | 4 |
| specified_task | 22 | 4 |
| supply_fact_or_step_done | 85 | 4 |
| task_status_or_control | 78 | 4 |

- **Label sources in the sample:** bench LLM labeler 47, 6-labeler pass 11, owner 2.
- **Context size**, counting visible bytes (text, tool calls and tool results; no thinking, no images): median 201 KB, p90 553 KB, max 955 KB.
- **Private files:** the sample ids are in `sample.json`. Its sha256, and the sha256 of the label files, are pinned in `protocol.json`.

## Context and arms

- **Context:** walk `parentUuid` back from the prompt, stopping at a `compact_boundary`. Keep user and assistant records, oldest first. Each content block is rendered as one paragraph with a header (rules in `protocol.json`), and the paragraphs are separated by blank lines.
- **Question:** the raw prompt text.

| arm | status | what runs |
|---|---|---|
| full | control | context unchanged; must score 100% retention, otherwise the run is void |
| mechanical | deterministic baseline | `compact_context(provider='mechanical', threshold=0.4, min_block_chars=40, max_block_chars=6000, trim_head_chars=300, model='gpt-4.1')` |
| specialist | learned, local, **shadow-score only** | `provider='specialist'` with `ContextEngine(models/exp02-specialist-head, cpu, max_len=512)` |
| jev_block | learned, remote, **disabled** | `provider='jev'`, with an explicit client only |
| jev_transcript | learned, remote, **disabled** | `compact_transcript(provider='jev')`; scores tool calls only |

**Specialist.** At `dd5dd80` the specialist provider cannot mutate: it ranks blocks but keeps them all. Its reduction is therefore 0 and it cannot win.
Diagnostic only (never a candidate, reduction tied by construction): keep protected blocks, then top-ranked blocks until kept tokens equal mechanical's for that item, and score the probes.

**Remote cost if the Jev arms were enabled.** Not run. The estimate uses the docs/JEV.md rate of about $0.0042 per 1K context tokens per pass.
- Sample is about 3.74M tokens (bytes/4): about $0.21 per median item, **about $15.70 per block-mode pass**. 35 of 60 items exceed 44K tokens, the largest size Jev was measured at (extrapolation).
- Transcript mode resends state per batch (about 5.3x, REAL_SESSIONS.md): **about $83 per pass**. Never pass `auto`/`jev` without an injected client: `JevClient.from_env` finds a key on its own.

**Not in v0:** laya. Note that transcript-mode laya on `dd5dd80` leaks to remote Jev unless `client=LayaClient()` is passed, because of a fall-through in `_resolve_client`.

## Must-keep probes (mechanical)

A probe is the content of one context block; it passes if that content, whitespace collapsed, is a substring of the arm's output. It is **NOT APPLICABLE** when its target is absent from the context or shorter than 12 characters; NOT APPLICABLE never counts as pass or fail.

**Probe definitions.**
- `LAST_AGENT_TURN`: the latest assistant text block, or the latest AskUserQuestion or ExitPlanMode call.
- `TASK_STATE`: the latest TodoWrite, TaskCreate, TaskUpdate, ExitPlanMode or update_plan call.
- `LAST_TOOL_RESULT`: the latest tool result.
- `ERROR_RESULT`: the latest tool result that has `is_error` set or matches the error regex. NOT APPLICABLE when the goal itself contains the error, because the goal is never compacted.
- `GIT_STATE`: the latest result of a Bash `git status`, `git diff` or `git log`.
- `NAMED_REFS`: for each path, filename or URL named in the goal that also occurs in the context, the latest block that contains it. All of them must pass.
- `LATEST_SUMMARY`: the latest assistant text block of 500 characters or more.
- `LAST_ARTIFACT_EDIT`: the latest Write, Edit, MultiEdit or NotebookEdit call.

**Probes per category**, derived from the taxonomy-v2 `context_needed`:

| category | probes |
|---|---|
| approve_or_pick | LAST_AGENT_TURN, TASK_STATE |
| supply_fact_or_step_done | LAST_AGENT_TURN |
| correct_approach_or_rule | LAST_AGENT_TURN |
| external_accounts_and_comms | LAST_AGENT_TURN |
| task_status_or_control | TASK_STATE, LAST_AGENT_TURN, LAST_TOOL_RESULT |
| revise_recent_output | LAST_AGENT_TURN, LAST_ARTIFACT_EDIT |
| failure_report | ERROR_RESULT |
| git_ship | GIT_STATE |
| handoff_prompt | LATEST_SUMMARY, TASK_STATE |
| specified_task | NAMED_REFS |
| project_audit_or_direction | NAMED_REFS (weak: the "broad project view" it needs is not mechanical) |
| environment_and_infra | NAMED_REFS, LAST_AGENT_TURN |
| UNKNOWN | LAST_AGENT_TURN, TASK_STATE |
| general_question | none (its context is droppable), so it counts for reduction only |

**Extra rule for short goals.** A goal under 15 words also gets `LAST_AGENT_TURN` and `TASK_STATE`, following the taxonomy rule never to drop these for short replies.

## Metrics

- **Primary: item retention** (all applicable probes pass; items with none count for reduction only). **Secondary:** probe-level retention.
- **Reduction**, pooled `1 - sum(out)/sum(in)` plus per-item median, in bytes and in tokens via LCC's `count_tokens(text, 'gpt-4.1')` (offline this is heuristic-v1, approximate; method recorded).
- **Latency:** median and p90 wall time in ms, per item and per arm. Model load is timed once, separately.
- **Confidence intervals:** Wilson 95% on item retention, per arm and per arm × category. The category cells have 2 to 5 items, so they are descriptive only.
- **Errors:** an arm error, or a timeout over 600 s, counts as a fail on every applicable probe and is listed.

## Stop criterion

A learned arm **wins** only if, on the same items, its aggregate item retention is **at least** mechanical's, its pooled token reduction is **strictly higher**, and the network guard never tripped. The decision uses point estimates. With about 58 scored items no significance is claimed, so the outcome is exploratory (INFERIDO).

## Known limits

47 of 60 labels are single-pass LLM labels; general_question has 2 items and project_audit_or_direction 4 eligible. Probes check verbatim survival, not answer correctness; a short probe can match by coincidence; token counts are heuristic.
