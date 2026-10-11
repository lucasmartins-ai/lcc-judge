# Real-context bench v0.7: Hermes TEST, rules lossless + recoverable @653eeae (frozen 2026-10-11)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` | `69ae86fdd7993ae30caa52920a2b3adc6fb573d9c4dadb25fea32497cc6e4b38` |
| `research/real_context_bench.py` | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| `research/real_context_bench_v03.py` | `4bf10daf00f9cf2613b2ab7c16cd3203ca1122f6fe1810cbb4b4bee2d2a73940` |
| `research/real_context_bench_v04.py` | `d483b60c2b6ed463cf5a2783865a7c932202f6aa35d03ce8cddc751be77d4ead` |
| `research/real_context_bench_v05.py` | `22ecb3590600fd536429e3b59ff3f2b376e38cca71261f21a3b969e493bb456b` |
| `research/hermes_context.py` | `68793d14f76da188844e1158a08e066a731fd054f92636f15cd4d0b13d764006` |
| `research/real_context_bench_v06_heldout.py` | `2c23cc9eaba4c2bc1bc15feb3f3cf4c576a30f1912d9b458eefb26bede65b9e8` |
| `research/real_context_bench_v07_heldout.py` | `12c2c13ed4c1069fcb57d3222c002f76bcecbf9c0cab2320bd4bbc6b975c4a59` |
| `research/lossless_dedup_measure.py` | `8d904ef78bffa83dfd76e42ef1c530e60277a51f138bb5b8fdf7547bdd5d6105` |
| `research/recoverable_dev_measure.py` | `917610aacaa233d16919c4e5cd8489d6f17f714567a352373d9988481beaa887` |
| `research/recoverable_dev_v2.py` | `0950d2eaf06f82bad059271d05164f5d9261c2eac5e28131acb06b127a8e854d` |
| `research/real_context_bench_v04_audit.py` | `a54073344b6892aef1d116b13878e901045410070a6bb34ae20220ff69e9daa6` |
| `research/real_context_bench_v06_audit.py` | `a5db2e9e3c0d94063b11ae472c740025572369d9b04e8e9303f7c49f7d76aacf` |
| `research/real_context_bench_v06_test.py` | `2bc320f6e7431283ea606dc6748f3a5dac3556879bd1426d2d4944ea82b4d24b` |
| `research/real_context_bench_v07_audit.py` | `8804c3c445c53f96d28639dba995730a930d679ce2abe2040a2901ce6ac16c87` |
| `research/real_context_bench_v07_test.py` | `f4d23031acae8c0f71a7bb27777cc647a85905c1d084bd8f0b58a00e5cee87cf` |
| `tests/test_real_context_bench_v06.py` | `e5fd1328a9e0a8ed5ac6e2096de3dcc36758407be865d248184b2364cf0f09e1` |
| `tests/test_real_context_bench_v07.py` | `3883c23017d0272daa328719b91b822a35f01394ccf827007a031b7910eedff7` |
| `tests/test_recoverable_dev_measure.py` | `71526bc4d1ca6cd84763637ae93f47b6dfc7a5aa4e417db476134591dda95f42` |
| `tests/test_hermes_context.py` | `8b2cf758bfea88b04028c8316b11e4e3d84d3af5847390c5d0110061f7307eae` |
| private `test-sample.json` | `6a3da43861b354519a9cd8ccdf14c49d0781f671523323b7e0c53ea1ec1710ad` |
| private `labels-llm-v2.jsonl` | `03dc77d3edc0078ed0c3571e83f2a1895c59b00e1d442aed906297c3ca293eb4` |

Committed and pushed **before any TEST dossier is built**. Every TEST phase refuses to run if any hash
differs, if the LCC worktree is not at the pin, or if the judging text (in `protocol.json` and in the private
`audit/instructions.txt`) differs from `research.real_context_bench_v07_test.JUDGE_TEXT`.
Private root: `~/.lcc/bench/heldout-v0.7/`. The repo gets counts only.

## Why

v0.6 audited 77 pointers and flagged 0, but all 77 were whole-file reads. The runtime fail-safe also fired on 1
item (7 duplicate tool_use_ids), and the independent review returned FAIL. LCC `f1c5ff7` fixed those findings.
At `f1c5ff7` the DEV re-measure (527 items, `recoverable-dev-v2`) had 0 lcc violations, 0 independent violations
and 0 fail-safes. A 90-record DEV audit, stratified by pointer kind, got two judges and the v0.7 labels: 89 ok,
1 unsure, 0 needed_unrecoverable. The unsure record, and one near-unsure note, were about files under `/tmp`,
which can be cleared. `653eeae` keeps reads in system temp dirs (reason `temp_path`), and `verify_recoverable`
rejects pointers to them. The DEV re-measure at `653eeae` (`recoverable-dev-v3`) had 0/0/0 violations and
1257 pointers. Disclosure: those DEV verdicts informed this one change. No TEST data was opened before this freeze.

## Policy under test

LCC `feat/transcript-rules-policy` (PR #45, not merged) at `653eeae0678f7ae5290535e66473f557fe69b98d`. This is
HEAD, equal to origin, with a clean tree. Worktree: `/Users/Master/lcc-wt-rules`.

Arms, each run once, offline with the network guard on, no retries, 600 s per item: `mechanical`,
`lcc_rules_lossless`, `lcc_rules_recoverable` (`transcript_proxy`, no workspace root).

## Requirements (both must hold for v0.7 PASS)

1. **Verification**: in both rules arms, 0 violations from lcc `verify_lossless` / `verify_recoverable`, 0 from the
   independent checks (`independent_check_v3`, no lcc code), and **0 runtime fail-safes**.
2. **Audit primary**: upper Wilson 95% of the flagged rate ≤ 0.10, for the audit overall.

## TEST sample

80 Hermes items from 63 sessions, seed 20261014, drawn in e3d4506 (`heldout-receipt.json`). They have 0
session/path/id/sid overlap with any earlier bench file, the v0.6 TEST included. Dossiers are built once, after
this freeze, and the overlap is asserted again.

## Recoverability audit

- Population: every `replace` decision of the recoverable run.
- Sample: n = 150, at most 3 per item over all kinds, seed 20261014, **stratified by pointer kind**
  (file_whole, file_range, command). The quota is 50 per kind. If a kind has fewer, the other kinds fill the
  rest, so the sample is as balanced as the population allows. The achieved n per kind is reported.
- Files f1/f2/f3: each kind's picks are dealt round-robin, so files are 50/50/50 with a near-equal share of
  each kind. Ids R001… run through f1, then f2, then f3.
- Packet: identical to v0.6 / DEV. Blinding: as in v0.6. `key.jsonl` stays private.
- Routing **A: f1+f2, B: f2+f3, C: f3+f1**. Each judge works only in `~/.lcc/bench/heldout-v0.7/judge-<X>/`,
  which holds only its two packet files, and writes `verdicts-<X>.jsonl` there.
- Validity and re-judging: as in v0.4 (a reason needs ≥ 5 words, unique per judge; the third judge re-judges).
- **Primary**: a record fails if EITHER final verdict is `needed_unrecoverable` or `unsure`, or if it is
  incomplete. PASS iff the upper Wilson 95% bound is ≤ 0.10 overall (≤ 7 of 150). The same rates are also
  reported per pointer kind, descriptively.
- Aggregation: `research/real_context_bench_v07_audit.py`, the v0.6 code with the labels changed only.
  Tests check that it equals v0.6 on relabelled inputs.

### Judging text (verbatim; sha256 `2b3707da9fe5f51808f9fd546db6a084ead89d0b5e0ed6e64eed9aa738b0df6a`)

> Blind auditor for a context compactor. Each record: a user request to a coding agent, the last turns, an earlier tool call whose output was REMOVED and replaced by the recovery pointer shown. Question: to correctly do what the user asked now, does the agent need the removed content AND would it be unable to get it back by following the pointer (re-read / re-run, in the stated directory), given what happened later in the session as far as you can tell? Answer needed_unrecoverable / ok / unsure, with a specific 5-15 word reason per record, unique, no quotes from the data.

## Run

```
PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.real_context_bench_v07_test dossiers
    ... run --arm mechanical ; ... run --arm lcc_rules_lossless ; ... run --arm lcc_rules_recoverable
    ... score ; ... audit
# judging in judge-A/B/C (verdicts-<X>.jsonl), then:
    ... rejudge        # if any verdict is invalid
    ... audit-score
```
