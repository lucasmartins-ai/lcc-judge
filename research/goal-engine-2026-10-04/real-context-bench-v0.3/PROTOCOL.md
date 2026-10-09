# Real-context bench v0.3: fresh test set + blind drop audit (frozen 2026-10-09)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` | `a056cafd4f1f51964f1fe916be446d5f6ebb497bd8866d47e08aa6000c41a8c5` |
| `research/real_context_bench.py` (v0 harness, probes, scoring; unchanged) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` (rules payload, LCC pin check, verdict; unchanged) | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| `research/real_context_bench_v03.py` (fresh sample, run/score, audit packet) | `4bf10daf00f9cf2613b2ab7c16cd3203ca1122f6fe1810cbb4b4bee2d2a73940` |
| private `fresh-sample.json` | `6158007050060d251be67e367f08a60a8a561e7cb4b3c919d39d4ae27eb11e38` |

Committed and pushed before either arm runs. The runner refuses to start if any hash differs.

## Why

v0.2 scored the rules policy at `413b6f4` 49/49 on the frozen 60, but its protect rules copy the
probes' predicates, so that retention is largely by construction, and a review found three
policy bugs the probes could not see (fixed in `8997be6`). v0.3 re-measures the fixed policy on
items nobody has looked at, and adds a check that does not share the policy's predicates: blind
judging of a sample of what the policy removed.

## Fresh sample

- From the 693 Claude prompts in `pool.json`, excluding the 60 frozen v0 ids and the 326 dev ids:
  307 candidates, 197 eligible (>= 1 assistant record before the prompt, label confidence not
  low). 0 were unlabeled, so no new labels were made.
- Labels: owner_v1 > pool label (owner v2 / LLM v2 pass) > labels-claude-extra. The sample has
  56 `llm_bench_labeler_v2_rules` and 4 `llm_v2_pass` labels, none owner-confirmed.
- v0 allocation code unchanged, seed `20261010`: 60 items over 12 strata (5 or 6 each;
  external_accounts_and_comms has 2 eligible; general_question and project_audit_or_direction have none).
- Session overlap: all 60 come from 25 sessions that also hold frozen-60 items (every remaining
  eligible item does, since the dev split excluded those sessions). None shares a session with
  the dev split. Earlier context can overlap a frozen item's context in the same session.
- Dossiers built with the v0 builder: 60 built, 0 id mismatches, 0 empty.

## Arms (offline, network guard, one pass, no retries, 600 s per item)

| arm | call |
|---|---|
| mechanical | v0 `MECH_KW` block compaction (threshold 0.4, blocks 40–6000 chars, trim head 300) |
| lcc_rules_transcript | `compact_transcript(payload=rules_payload(blocks), question=goal, provider='rules')`, defaults |

- Both arms run on LCC branch `feat/transcript-rules-policy` (PR #45, not merged) at
  `8997be6871c3b82d9c2cb8ed05e77a06846e8b04`, worktree `/Users/Master/lcc-wt-rules`; the runner
  checks `lcc.__file__`, HEAD and a clean tracked tree. Mechanical at this commit differs from the
  v0 pin `dd5dd80` only in the shared reversal-cue regex and the supersession reason text.
- Payload as v0.2: v0.1 `transcript_payload` plus `is_error` on flagged results.
- `full` is scored from the dossier text as a sanity control (must retain 100% or the run is void).

## Probes, metrics, verdict

Copied from v0/v0.2 unchanged (`probes`, `metrics` in `protocol.json`). Verdict vs mechanical:
rules wins iff item retention >= mechanical AND pooled token reduction strictly > mechanical AND
zero guard trips in the rules arm. Exploratory, point estimates, no significance claimed.

**Known caveat, stated before the run:** the rules policy mirrors these probes (same error, git,
path/URL, task-tool and edit-tool predicates; goal-named protection re-implements NAMED_REFS;
text blocks are never edited). Probe retention for this arm is mostly by construction and does
not show that the policy keeps what the user needed. At `8997be6` the error rule skips `Read`
results and the ERROR_RESULT probe does not, so that disagreement can show up as a miss.

## Drop audit (primary evidence on retention)

- Population: every tool call the rules arm dropped or trimmed across the 60 fresh items.
- Sample: 150 decisions, seed `20261010`, at most 6 per item (per-item shuffle, capped, then
  round-robin over shuffled items), then shuffled and split into three files of 50
  (`drops-a/b/c.jsonl`, private under `~/.lcc/bench/real-context-v0/audit/`).
- Each record: `audit_id`, the request, the last 3 user/assistant text turns before it (each
  clipped head+tail to 1500 chars), tool name, tool input (clipped 1000), the full original tool
  output clipped head+tail to 3000 chars, its length, and for trims the shortened output.
- Blinding: no rule name, reason, arm, item id or category in the packets. The unblinding key
  (`key.jsonl`) stays private and is not shown to judges until all three files are judged.
- Judges: one per file, the owner or a fresh Claude Code subagent that receives only the
  instructions below and one file. No paid or remote API is called.
- Instructions (verbatim in `protocol.json`): judge from what is shown whether the agent, to
  handle the request correctly, would plausibly need information that is in the original output
  and absent from what remained. Answer `needed`, `not_needed` or `unsure`, with one sentence.
  "The agent could re-run the tool" is not a reason for `not_needed`.
- **Primary metric:** false-drop rate = (needed + unsure) / judged, Wilson 95% CI. Unsure counts
  against the policy.
- **Pre-registered acceptance:** PASS iff the upper Wilson 95% bound <= 0.10. At n = 150 that
  means at most 7 needed-or-unsure (7 -> .093, 8 -> .102).
- Secondary: needed / (needed + not_needed) with unsure excluded; unsure rate; split by drop vs
  trim and by tool after unblinding.

## Run

```
PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.real_context_bench_v03 run --arm mechanical
    ... run --arm lcc_rules_transcript ; ... score ; ... audit
```
