# Real-context bench v0.6: results

Protocol: `protocol.json` (frozen and pushed in b731998, before the dossiers were built). LCC 1bc2005.
These are counts only. The per-item data stays in `~/.lcc/bench/heldout-v0.6/`.

## Limits (read first)

- **The pre-registered verification requirement FAILED.** `protocol.json` requires "0 violations in both
  arms and runtime_fail_safe 0", and otherwise "the arm is invalid for the safety claim". Violations are 0,
  but runtime_fail_safe = 1 in each rules arm (the same item). Under the frozen protocol, therefore, the
  recoverable arm **cannot carry the safety claim**, even though its audit passes.
- **The audit is small and narrow.** n = 77, not 150 (31 items with pointers × cap 3). All 77 records are
  whole-file `read_file` pointers. Command pointers (the riskier kind) were not tested, because Hermes's
  shell tool is not in lcc's SHELL_TOOLS. The result says nothing about command pointers.
- **The check is a transcript proxy.** The bench has no disk snapshot. A file pointer is trusted when no
  later call in the transcript writes that file. Edits made outside the transcript are not seen.
- **Agreement is uninformative.** Every verdict was `not_needed`. Raw agreement is 1.0 and Cohen's kappa is
  undefined (null), so this does not show that the judges can tell the classes apart.
- **Who judged.** Three isolated judges (A, B, C), each working in its own folder with only its two packet
  files and the verbatim judging text. The packet hashes in the judge folders match `audit-packets.json`
  (not modified). Judge isolation beyond that was not audited from here.
- Retention is scored on 49 items. TASK_STATE, GIT_STATE and LAST_ARTIFACT_EDIT were not applicable on Hermes.
- One mechanical item ran for 4640 s even though the per-item limit is 600 s (see Deviation).

## Run

60 dossiers were built, with 0 id mismatches, 0 empty contexts and 0 overlap with any earlier set. Each arm
ran once, offline, with 0 guard trips and all 60 items `ok`. Full control retained 1.0 (not void).

| arm | item retention (49 scored) | pooled token reduction | median per item |
|---|---|---|---|
| mechanical | .898 | .0573 | .0000 |
| lcc_rules_lossless | 1.000 | .0081 | .0000 |
| lcc_rules_recoverable | 1.000 | .0411 | .0123 |

**Verification:** lcc's verifier found 0 violations and the independent check found 0, in both rules arms.
runtime_fail_safe = 1 in each rules arm, on the same item (about 1.4M tokens, 2093 tool calls). lcc
rejected its own dedupe plan for that item and kept every tool call (output equal to input), so nothing
unsafe was emitted. INFERIDO: this is a planner bug on this Hermes transcript, probably caused by duplicate
tool-call ids. That cause is not confirmed. The policy was not changed on TEST.

**Deviation:** one mechanical item (7.2 MB) ran for 4640 s even though the per-item limit is 600 s. lcc's
broad `except Exception` handlers swallow the harness's SIGALRM `ItemTimeout`, so the limit is not
enforced inside lcc. The record is `ok` and is scored as recorded.

**Pointers (recoverable):** 166, all `file_whole` from `read_file`, in 31 items, with `transcript_proxy`.

## Audit (primary evidence)

77 records drawn with seed 20261013 (f1 26, f2 26, f3 25), routed A: f1+f2, B: f2+f3, C: f3+f1. All 154
assigned verdicts were valid. 0 re-judges were requested and 0 were substituted. The key join with the run
had 0 mismatches.

| | count |
|---|---|
| n | 77 |
| needed_unrecoverable | 0 |
| unsure | 0 |
| incomplete | 0 |
| not_needed | 77 |
| primary flagged | 0/77, Wilson 95% [0, .0475] |

**Audit acceptance: PASS** (upper bound .0475 ≤ .10). The secondary needed_unrecoverable-only result is
also 0/77, with an upper bound of .0475. The unsure verdict rate is 0.

Verdict files are pinned in `verdicts.sha256`. The aggregate is in `audit-summary.json`, written by
`-m research.real_context_bench_v06_test audit-score` (the frozen code).

## Verdict

- Audit: PASS.
- Protocol verification requirement: FAILED (runtime_fail_safe 1 ≠ 0), so the recoverable arm is invalid
  for the safety claim under the frozen protocol.
- INFERIDO: the audit supports file-pointer recovery on Hermes. It does not yet support making
  `recoverable` the default. That needs two things: the fail-safe trip reproduced and fixed on DEV, and a
  fresh confirmation run that includes command pointers.
