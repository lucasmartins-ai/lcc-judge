# Real-context bench v0.6: Hermes TEST, rules lossless + recoverable @1bc2005 (frozen 2026-10-10)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` | `22fc47174b93fedeb34a5bead3b2da07747b591d921c8ed908474f45cba59f24` |
| `research/real_context_bench.py` | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| `research/real_context_bench_v03.py` | `4bf10daf00f9cf2613b2ab7c16cd3203ca1122f6fe1810cbb4b4bee2d2a73940` |
| `research/real_context_bench_v04.py` | `d483b60c2b6ed463cf5a2783865a7c932202f6aa35d03ce8cddc751be77d4ead` |
| `research/real_context_bench_v05.py` | `22ecb3590600fd536429e3b59ff3f2b376e38cca71261f21a3b969e493bb456b` |
| `research/hermes_context.py` | `68793d14f76da188844e1158a08e066a731fd054f92636f15cd4d0b13d764006` |
| `research/real_context_bench_v06_heldout.py` | `2c23cc9eaba4c2bc1bc15feb3f3cf4c576a30f1912d9b458eefb26bede65b9e8` |
| `research/lossless_dedup_measure.py` | `8d904ef78bffa83dfd76e42ef1c530e60277a51f138bb5b8fdf7547bdd5d6105` |
| `research/recoverable_dev_measure.py` | `917610aacaa233d16919c4e5cd8489d6f17f714567a352373d9988481beaa887` |
| `research/real_context_bench_v04_audit.py` | `a54073344b6892aef1d116b13878e901045410070a6bb34ae20220ff69e9daa6` |
| `research/real_context_bench_v06_audit.py` | `a5db2e9e3c0d94063b11ae472c740025572369d9b04e8e9303f7c49f7d76aacf` |
| `research/real_context_bench_v06_test.py` | `2bc320f6e7431283ea606dc6748f3a5dac3556879bd1426d2d4944ea82b4d24b` |
| `tests/test_real_context_bench_v06.py` | `e5fd1328a9e0a8ed5ac6e2096de3dcc36758407be865d248184b2364cf0f09e1` |
| `tests/test_recoverable_dev_measure.py` | `71526bc4d1ca6cd84763637ae93f47b6dfc7a5aa4e417db476134591dda95f42` |
| `tests/test_hermes_context.py` | `8b2cf758bfea88b04028c8316b11e4e3d84d3af5847390c5d0110061f7307eae` |
| private `test-sample.json` | `08070f751cdc730689a7b82abca2c907a0c079d36374eeba4e74e109b4d23ba0` |
| private `labels-llm-v2.jsonl` | `fc4f339eec5a8fff3bdae2bb068885df1c477887ece0e8637e925107ee935bac` |

Committed and pushed **before any TEST dossier is built**. Every TEST phase refuses to run if any hash
differs, if the LCC worktree is not at the pin, or if the judging text differs from the DEV text.
Private root: `~/.lcc/bench/heldout-v0.6/`. The repo gets counts only.

## Why

Owner decision 2026-10-10: removing an old tool output is acceptable when the agent can recover it by
re-reading the file or re-running a read-only command. Removing needed content that cannot be recovered
is not acceptable. The lossy rules policy failed v0.4 (21/150) and v0.5 (36/132). `rules_mode=recoverable`
implements the new contract. On DEV only (467 items) it had 0 violations from both verifiers. The DEV audit
packets exist but had no verdicts at freeze time, so no judge result informed this protocol.

## Policy under test

LCC `feat/transcript-rules-policy` (PR #45, not merged) at `1bc20056cfccd4915394862e431f409efee44144`. This is
HEAD, equal to origin, with a clean tree, rebased on origin/main. Worktree: `/Users/Master/lcc-wt-rules`.

Arms, each run once, offline with the network guard on, no retries, 600 s per item:
- `mechanical`: the v0 baseline.
- `lcc_rules_lossless`: `provider='rules', rules_mode='lossless'`.
- `lcc_rules_recoverable`: `rules_mode='recoverable'` with no workspace root, so the check is `transcript_proxy`.

Verification: every rules-arm item is checked by lcc's `verify_lossless` / `verify_recoverable` AND by the
independent bench checks, which use no lcc code. The required result is 0 violations.

## TEST sample

60 Hermes items from 53 sessions, seed 20261013, drawn in 5f37db8 (`heldout-receipt.json`). They have 0
session/path/id overlap with any earlier bench file. Dossiers are built after this freeze, once, with
`research/hermes_context.build_dossier`, and the overlap is asserted again.

## Probes, metrics

Copied from v0–v0.5 unchanged. They are a sanity check here, because neither rules mode edits text or tool
inputs. Hermes tool names make some probes NOT_APPLICABLE. The descriptive verdict vs mechanical uses
`v02.verdict`. Mechanical is lossy, so the rules arms can lose on reduction by design.

## Recoverability audit (primary evidence)

- Population: every `replace` (recovery pointer) decision of the recoverable run. Lossless dedupes are
  excluded because they are verified lossless.
- Sample: `v03.audit_select`, seed 20261013, n = 150, at most 3 per item. If fewer than 150 exist, all are
  taken and the realised n is used.
- Ids R001…; files f1/f2/f3 = thirds in pick order (50/50/50 at n = 150).
- Packet: identical to the DEV packet (request, last 3 turns, tool, tool_input, recovery_pointer,
  removed_output clipped to 3000, removed_output_chars).
- Blinding: packets carry no rule, reason, arm, item, category or pointer-kind field. `key.jsonl` stays
  private.
- Routing: **A: f1+f2, B: f2+f3, C: f3+f1**.
- **Isolation**: each judge works in `~/.lcc/bench/heldout-v0.6/judge-<X>/`. That folder holds only the
  judge's two packet files, and the judge writes `verdicts-<X>.jsonl` there. Re-judging happens in
  `rejudge-<X>/`, which holds only `rejudge-<X>.jsonl`.
- Judges: the owner or fresh Claude Code subagents. No repo, key or network tools, and no paid or remote API.
- Validity and re-judging: as in v0.4.
- **Primary**: a record fails if EITHER final verdict is `needed` (= needed_unrecoverable) or `unsure`, or
  if it is incomplete. Fail rate = flagged / n, Wilson 95%. **PASS iff the upper bound ≤ 0.10** (≤ 7 of 150).
- Secondary: needed_unrecoverable-only rate, agreement (raw, kappa), unsure rate, splits by pointer kind
  and tool, and token reduction.
- Aggregation: `research/real_context_bench_v06_audit.py`. It is a copy of the v0.4 aggregation, adapted
  only to the labels, the folders and the replace-key join. Tests check that it is equal to v0.4 on the
  same inputs.

### Judging text (verbatim, byte-identical to DEV; sha256 `9c0be3f5243cbafda4913a69639281fcd840854e8425577b37b3dc65b004e944`)

> You see a user request sent to a coding agent, the last few conversation turns before it, and one earlier tool call (tool, tool_input). A context-compaction step removed that call's output from the agent's context and left only recovery_pointer in its place: this is exactly what the agent now sees where the output was. removed_output shows the output that was removed (head and tail if long; removed_output_chars is its full length). The agent can follow the pointer at any time: re-read the named file (or line range) or re-run the named command, and it will get whatever that returns NOW, not necessarily what it returned then. Judge only from what is shown: to handle this request correctly, would the agent plausibly need information in removed_output that it could NOT get back by following the pointer? Answer needed when the removed content was needed and following the pointer would plausibly not return it (for example the file or repository state was changed afterwards and the old content itself matters, or the pointer does not identify how to get it back). Answer not_needed when the removed content is not needed for this request, or when following the pointer would give the agent what it needs. Answer unsure when the shown context is not enough to tell. Give one sentence of reason specific to this record (what the removed output holds and why it is or is not needed and recoverable). A generic reason reused across records is invalid. Do not guess what policy made the choice. Output one JSON line per record: {"audit_id": ..., "verdict": "needed"|"not_needed"|"unsure", "reason": ...}.

## Run

```
PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.real_context_bench_v06_test dossiers
    ... run --arm mechanical ; ... run --arm lcc_rules_lossless ; ... run --arm lcc_rules_recoverable
    ... score ; ... audit
# judging in judge-A/B/C (verdicts-<X>.jsonl), then:
    ... rejudge        # if any verdict is invalid
    ... audit-score
```
