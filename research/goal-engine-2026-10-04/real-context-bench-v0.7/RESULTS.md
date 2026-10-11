# Real-context bench v0.7: results

Protocol: `protocol.json` (frozen and pushed in f082362, before the dossiers were built). LCC 653eeae.
These are counts only. The per-item data and verdict text stay in `~/.lcc/bench/heldout-v0.7/`.

## Limits (read first)

- **Only whole-file pointers were tested.** All 134 recoverable pointers on this TEST set are `file_whole`
  (133 `read_file`, 1 `terminal`); there are 0 `file_range` and 0 `command` pointers. The kind stratification
  had nothing to balance, and all 54 audited records are `read_file`. The result says nothing about range or
  command pointers. This is the same gap as v0.6.
- **The audit is small.** n = 54, not 150 (22 items with pointers, cap 3 per item). At n = 54 the threshold
  allows at most 1 flagged record: 1/54 gives upper .0977, 2/54 would give .1254 and FAIL. The PASS has
  almost no margin.
- **The check is a transcript proxy.** No disk snapshot exists. A file pointer is trusted when no later call
  in the transcript writes that file. Moves or edits made outside the transcript are not seen. The one flagged
  record is exactly this case (see Audit).
- **The temp-path rule was tuned on DEV verdicts** (disclosed in the protocol). It kept 54 TEST reads
  (`keep:temp_path`). It is a fixed list of system temp dirs; project-local scratch dirs are not covered.
- **Agreement is weakly informative.** Kappa is 1.0, but it rests on one non-`ok` record out of 54.
- **Who judged.** Three isolated judges (A, B, C), each in its own folder with only its two packet files and the
  verbatim judging text. The packet hashes in all three folders match `audit/f1-f3.jsonl` (not modified).
  Judge isolation beyond that was not audited from here.
- Retention is scored on 67 items. TASK_STATE, GIT_STATE and LAST_ARTIFACT_EDIT were not applicable on Hermes.
- Mechanical shows 0.0 reduction on this set. That is the unchanged baseline code; the cause was not
  investigated.

## Run

80 dossiers were built, with 0 id mismatches, 0 empty contexts and 0 overlap with any earlier set. Each arm
ran once, offline, with 0 guard trips and all 80 items `ok`. Full control retained 1.0 (not void).

| arm | item retention (67 scored) | pooled token reduction | median per item |
|---|---|---|---|
| mechanical | .970 | .0000 | .0000 |
| lcc_rules_lossless | 1.000 | .0033 | .0000 |
| lcc_rules_recoverable | 1.000 | .0343 | .0002 |

**Verification (requirement 1):** in both rules arms, lcc's verifier found 0 violations, the independent check
(`independent_check_v3`) found 0, and runtime_fail_safe = 0. **PASS.**

**Pointers (recoverable):** 134 in 22 items, all `file_whole`, with `transcript_proxy` on all 80 items.

## Audit (requirement 2, primary evidence)

54 records drawn with seed 20261014 (f1 18, f2 18, f3 18), routed A: f1+f2, B: f2+f3, C: f3+f1. All 108
assigned verdicts were valid. 0 re-judges were requested and 0 were substituted. The key join with the run had
0 mismatches.

| | count |
|---|---|
| n | 54 |
| needed_unrecoverable | 0 |
| unsure | 1 |
| incomplete | 0 |
| ok | 53 |
| primary flagged | 1/54, Wilson 95% [.0033, .0977] |

**Audit acceptance: PASS** (upper bound .0977 ≤ .10). Secondary needed_unrecoverable-only: 0/54, upper .0664.
Unsure verdict rate .0185 (2 of 108 verdicts). Per pointer kind: file_whole only, same numbers.

The flagged record got `unsure` from both of its judges. INFERIDO from the private reasons: the read file sits
in a folder that an external process may move it out of, so a re-read could fail. The transcript proxy cannot
see that.

Verdict files are pinned in `verdicts.sha256`. The aggregate is in `audit-summary.json`, written by
`-m research.real_context_bench_v07_test audit-score` (the frozen code).

## Verdict

- Requirement 1 (verification): PASS (0 / 0 / 0 in both rules arms).
- Requirement 2 (audit primary): PASS (1/54, upper .0977).
- v0.7: **PASS** under the frozen protocol.
- INFERIDO: this supports `recoverable` for whole-file read pointers on Hermes transcripts, with no margin to
  spare. It does not support range or command pointers, which were absent. Recommendation: keep `lossless` as
  the default; offer `recoverable` as opt-in. Before any default change, run a set that contains command and
  range pointers, and consider keeping reads from folders that external processes move files out of (the
  flagged case).
