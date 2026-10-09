# Real-context bench v0.4: Codex held-out set + two-judge blind audit (frozen 2026-10-09)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` | `3b44504e362c2ee5fb05c80ef60a3839e3c838198cbdfab37f7729f2ceec8f2a` |
| `research/real_context_bench.py` (v0 harness, probes, scoring; unchanged) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` (rules payload, LCC pin check, verdict; unchanged) | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| `research/real_context_bench_v03.py` (rules runner, audit sampler, clip; unchanged) | `4bf10daf00f9cf2613b2ab7c16cd3203ca1122f6fe1810cbb4b4bee2d2a73940` |
| `research/codex_context.py` (Codex adapter, new) | `60c296094bb37d059195dc9c5354a27d3a1e673122971a518a713f2851b4ed8e` |
| `research/real_context_bench_v04.py` (sample, run/score, audit packets, new) | `d483b60c2b6ed463cf5a2783865a7c932202f6aa35d03ce8cddc751be77d4ead` |
| `research/real_context_bench_v04_audit.py` (validity, re-judge, aggregation, new) | `a54073344b6892aef1d116b13878e901045410070a6bb34ae20220ff69e9daa6` |
| private `sample.json` | `42439c56ce5504bd3a0dd737a6b0159964c715a75daf198c9695bb526035a09d` |
| private `labels-llm-v2.jsonl` | `c00be7ef36aed1e185f82eb90a89254387559dc22cc1158d9a62e3a4ea59a9ee` |
| private `dossiers/` digest | `7aee317df21a59ef720261e1f94920c1ad7a2d5dea5d1421006658d597bc1600` |

Committed and pushed before either arm runs. The runner refuses to start if any hash differs.
Private root: `~/.lcc/bench/codex-heldout-v0.4/`. The repo gets counts only.

## Why

v0.3 failed review (see `../real-context-bench-v0.3/RESULTS.md`):

- its "fresh" 60 shared all 25 sessions with the frozen 60;
- judge routing deviated from plan;
- the any-judge assembly and the aggregation code were written after the verdicts;
- trim packets showed mostly the text the trim kept.

v0.4 fixes each of these:

- data from a different agent, Codex, whose sessions no earlier bench set used (asserted);
- routing, validity, re-judging and aggregation fixed in code and tested before judging;
- trim packets that show the removed middle itself.

## Policy under test

LCC `feat/transcript-rules-policy` (PR #45, not merged) at `8997be6871c3b82d9c2cb8ed05e77a06846e8b04`,
worktree `/Users/Master/lcc-wt-rules`. The runner checks `lcc.__file__`, HEAD and a clean tracked
tree. Both arms run on that commit.

| arm | call |
|---|---|
| mechanical | v0 `MECH_KW` block compaction (threshold 0.4, blocks 40–6000 chars, trim head 300) |
| lcc_rules_transcript | `compact_transcript(payload=rules_payload(blocks), question=goal, provider='rules')`, defaults |

`full` is scored from the dossier text as a sanity control (must retain 100% or the run is void).
Offline, network guard, one pass per arm, no retries, 600 s per item.

## Codex adapter (`research/codex_context.py`)

- **Prompts.** Same rules as `research.import_agent_requests`:
  - human sessions only (`source` vscode/cli, no parent thread);
  - injected blocks skipped;
  - `(session, text)` deduped;
  - id = sha256(`codex\0` + redacted text).

  Mapped back to the first rollout record that carries each prompt. Ids and session hashes
  reproduce `imported/codex.jsonl` exactly (930/930).
- **Context.** Every response item before the prompt record. A `compacted` record restarts the
  context at its `replacement_history`. One block group per response item.
  - Dropped: developer messages, reasoning and encrypted compaction items.
  - Mapped:
    - user/assistant text becomes text blocks;
    - function, custom and tool-search calls become `tool_use` blocks, with parsed JSON input or `{input: raw}`;
    - their outputs become `tool_result` blocks;
    - web search and image generation calls become `tool_use` blocks with no result.
- **Tool names stay native.** Examples: `exec_command`, `apply_patch`, `update_plan`,
  `mcp__<server>__<tool>`. No renaming to Claude names.
- **`is_error`** is set only from a nonzero exit code that Codex recorded. Codex records it in
  three places:
  - the `Process exited with code N` header;
  - the `Exit code: N` header;
  - a JSON `exit_code` field.
- **Payload** is the v0.2 `rules_payload` over those blocks: `{role, text, toolUses, toolResults(is_error)}`.

Tests: `tests/test_codex_context.py` (synthetic rollouts).

## Held-out sample (seed 20261011)

- **Population.** 930 imported Codex prompts, all mapped to a rollout position. 730 have at least
  one assistant message before the prompt, over 255 sessions.
- **Prior benches.** Every `session_hash` and `path` value under
  `~/.lcc/bench/real-context-v0` was collected (199 hashes, 203 paths). Overlap with the
  candidates: 0 sessions excluded. Overlap with the sample: 0 session hashes, 0 paths, and 0 prior
  paths under `~/.codex`.
- **At most 2 per session.** For each session, its eligible ids are shuffled and the first 2 kept,
  giving 372 candidates.
- **Labels.** Precedence: owner verdict on a v2 label, then the taxonomy-v2 LLM pass, then new
  labels. The new labels cover the 302 candidates with no v2 label. They were made before sampling
  by the Claude session that wrote this protocol, from the redacted request text alone, with the
  v2 rules. They are marked `llm_v04_codex_v2_rules` (private `labels-llm-v2.jsonl`, pinned).
  Low-confidence candidates are excluded (10).
- **Allocation.** Equal round-robin over 14 strata until 60.
  - Sampled per stratum: 5 each for UNKNOWN, approve_or_pick, correct_approach_or_rule,
    environment_and_infra, external_accounts_and_comms, failure_report and git_ship; 4 each for
    the 6 other strata; 1 for general_question (only 1 eligible).
  - Sessions: 59, at most 2 per session.
  - Label sources: 45 new LLM, 14 v2 LLM pass, 1 owner-confirmed.
- **Dossiers.** 60 built, 0 id mismatches, 0 empty. Median visible context 302 KB (max 685 KB).
- **Noted.** 4 of the 60 items come from sessions whose working directory is an LCC repository.
  None of those contexts was read while the policy was built.

## Probes, metrics, verdict

Copied from v0/v0.2/v0.3 unchanged (`probes`, `metrics`). Verdict vs mechanical: rules wins iff
item retention >= mechanical AND pooled token reduction strictly > mechanical AND zero guard trips.
Exploratory, point estimates.

**Mirroring caveat, stated before the run.** On Claude transcripts the rules policy mirrors these
probes, so probe retention there was largely by construction. On Codex names:

- **Probes that never apply:** GIT_STATE needs a `Bash` call and LAST_ARTIFACT_EDIT needs an edit
  tool, so both are NOT_APPLICABLE on every Codex item. The policy's git, edit and whole-file
  supersession rules never fire either.
- **Probes that still mirror the policy:**
  - LAST_AGENT_TURN and LATEST_SUMMARY: text is never edited.
  - TASK_STATE: `update_plan` is in both lists.
  - LAST_TOOL_RESULT.
  - NAMED_REFS.
  - ERROR_RESULT. The probe also uses the error regex on any result, while the policy uses
    `is_error` only, so a regex-only error can show as a miss.

Probe retention is still mostly by construction. The audit is the check that does not share the
policy's predicates.

## Drop/trim audit (primary evidence on retention), fixed now

- **Sample.** 150 drop/trim decisions of the rules run, seed `20261011`, at most 3 per item. It
  uses the v0.3 `audit_select` code, unchanged. If fewer than 150 exist, all are taken and n is
  reported.
- **Ids and files.** Ids are D001–D150. Files: `f1` = D001–D050, `f2` = D051–D100,
  `f3` = D101–D150. The audit phase writes them once and refuses to overwrite.
- **Packet.**
  - Every packet shows the request, the last 3 user/assistant text turns (each ≤ 1500 chars,
    head+tail), the tool name and the tool input (≤ 1000).
  - **Removals:** the original output, head+tail ≤ 3000, plus its length.
  - **Shortenings:** the kept head and kept tail exactly, plus the **removed middle itself**
    (head+tail of the removed part ≤ 3000) and its length. The middle is checked to be exactly
    the original minus the kept head and tail, or the audit stops.
- **Blinding.**
  - Packets carry no rule, reason, source, arm, compactor, item id or category.
  - Every `[... lcc: ...]` note is replaced by `[...]` in every field.
  - `key.jsonl` stays private and is not shown to judges.
- **Judges.**
  - There are 3 judges, A, B and C: the owner, or fresh Claude Code subagents that get only the
    instructions and their packet file. No paid or remote API is used.
  - Routing: **A judges f1+f2, B judges f2+f3, C judges f3+f1.** Every record gets exactly 2
    independent verdicts. A file's third judge (f1 → B, f2 → C, f3 → A) has not seen it.
- **Verdicts.**
  - Each verdict is `needed` / `not_needed` / `unsure`, with a reason specific to the record.
  - The instructions are verbatim in `protocol.json`. Re-running the tool is not a reason for
    `not_needed`.
  - A verdict is **invalid** when any of these holds:
    - its value is not one of the three outcomes;
    - its normalized reason has fewer than 5 words;
    - the same normalized reason occurs on another record of the same judge (generic: every copy
      is invalid);
    - it is missing.
  - The record's third judge re-judges each invalid verdict (`rejudge`). A valid re-judgment fills
    the slot. A record that still lacks two valid verdicts is *incomplete*.
- **Primary metric.** A record is flagged if **either** final verdict is `needed` or `unsure`, or
  if it is incomplete. False-drop rate = flagged / 150, with a Wilson 95% interval.
  **Acceptance: PASS iff the upper bound ≤ 0.10.** At n = 150 that means at most 7 flagged
  (7 → .0932, 8 → .1017).
- **Secondary:**
  - needed-only (either judge says `needed`) / n, Wilson 95%;
  - inter-judge agreement (raw and Cohen's kappa);
  - unsure rate;
  - splits by decision, rule and tool after unblinding.
- **Aggregation.** `research/real_context_bench_v04_audit.py` (`rejudge`, `score`) implements
  exactly this rule. It was written and tested (`tests/test_real_context_bench_v04.py`) before
  any judging. `score` joins every key row to the private rules run and stops on any mismatch.

## Run

```
PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.real_context_bench_v04 run --arm mechanical
    ... run --arm lcc_rules_transcript ; ... score ; ... audit
# judging (judge-A/B/C.jsonl -> verdicts-A/B/C.jsonl), then:
python3 -m research.real_context_bench_v04_audit rejudge   # if any verdict is invalid
python3 -m research.real_context_bench_v04_audit score
```
