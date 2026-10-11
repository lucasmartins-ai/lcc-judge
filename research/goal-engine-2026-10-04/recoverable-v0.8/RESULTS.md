# Recoverable v0.8: the v0.7-review fix is a strict subset of the v0.7 pin

LCC `4c39161` (PR #45, `feat/transcript-rules-policy`) against LCC `653eeae` (the v0.7 pin, run from a detached
worktree outside `~/LCC`). Script: `research/recoverable_v08.py`. Counts: `summary.json`. Per-item rows stay in
`~/.lcc/bench/recoverable-v0.8/`. This is counts only. It is not a pre-registered TEST run, and there is no new
blind audit.

## Limits (read first)

- **The v0.7 audit covers v0.8 only through the subset property.** No judge has seen a v0.8 output. On every item
  of every set, the pointers at `4c39161` are a subset of the pointers at `653eeae`. On Hermes v0.7 TEST, the
  12 surviving pointers come from the population the v0.7 audit sampled (1/54 flagged). The fix only turns
  replaces into keeps, so the number of removals that should not have happened cannot go up. Their rate among the
  survivors is not measured, though, because the fix is not a random subsample. Of the 54 records audited in
  v0.7, 2 survive at `4c39161`, and both were `ok`. The one flagged record (`unsure`) is now kept. The other
  sets have no recoverable TEST audit at `653eeae`, so for them the subset only shows "no new removal" and gives
  no rate.
- **The audits only ever covered whole-file pointers.** Range pointers (41 survive) and command pointers (0 by
  default, 22 with `allow_command_pointers=True`) have no blind audit at any version. Command pointers are off
  by default for this reason.
- **The check is a transcript proxy.** These dossiers have no disk snapshot, so they ran with no
  `workspace_root`. A file pointer is trusted when no later call in the transcript writes, or may write, that
  file. **In production, the safeguard is the disk check:** `rules_mode=recoverable` plus `workspace_root`,
  which re-reads each pointed file at compaction time and keeps any that changed.
- Spent sets (Hermes v0.6 and v0.7 TEST) were only read. Nothing was written next to them.

## Method

There are three runs per item, each in its own process from a clean worktree whose HEAD is checked against the pin.
All ran offline, with 0 guard trips, 0 errors and 0 degraded outputs.

- `old`: `653eeae`, `rules_mode=recoverable`, using its defaults.
- `new`: `4c39161`, `rules_mode=recoverable`, using its defaults. Command pointers are off.
- `new_cmd`: `4c39161`, the same as `new` plus `allow_command_pointers=True`.
- `new_lossless`: `4c39161`, `rules_mode=lossless`. This is a baseline only.

Every output was re-checked by two checkers: lcc's own verifier at that pin, and the independent
`research/recoverable_check_v4.py` plus the dedupe check, which use no lcc code. **Subset:** for each item,
the set of replaced `tool_use_id`s at `new` (and at `new_cmd`) must be contained in the set at `old`. The input
token counts matched on every item at both pins.

## Result: subset 0 violations, verification 0/0/0 (PASS)

| set | items | replaced old | replaced new | removed by fix | subset viol. | reduction old | reduction new | lossless |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| claude_frozen_60 | 60 | 38 | 0 | 38 | 0 | .0146 | .0034 | .0034 |
| claude_fresh_60 | 60 | 32 | 2 | 30 | 0 | .0123 | .0024 | .0016 |
| claude_dev_326 | 326 | 404 | 9 | 395 | 0 | .0432 | .0067 | .0063 |
| codex_v04_test_60 | 60 | 309 | 7 | 302 | 0 | .0963 | .0160 | .0125 |
| codex_v05_dev_141 | 141 | 771 | 37 | 734 | 0 | .1184 | .0264 | .0185 |
| codex_v05_test_60 | 60 | 282 | 7 | 275 | 0 | .1040 | .0204 | .0153 |
| hermes_v06_test_60 (spent) | 60 | 82 | 0 | 82 | 0 | .0282 | .0108 | .0108 |
| hermes_v07_test_80 (spent) | 80 | 134 | 12 | 122 | 0 | .0343 | .0097 | .0033 |
| **all** | **847** | **2052** | **74** | **1978** | **0** | **.0576** | **.0123** | **.0093** |

"Reduction" is the pooled token reduction, 1 − Σout/Σin, counted with lcc's tokenizer.
The old run reproduces v0.7 exactly on its TEST set: 134 pointers, pooled reduction .0343.

**Verification at `new`:** the lcc verifier found 0 violations, `independent_check_v4` + dedupe found 0, and
runtime_fail_safe was 0 on all 847 items. `new_cmd` and `new_lossless` also show 0/0/0.

**Verification of `old` under the v4 checker:** the lcc verifier found 0, but `independent_check_v4` found 1895
violations in 378 items. These are the opaque later writes (H1) that the v0.7 review found and that v3 did not
check. This is the gap the fix closes.

**Why the fix removed pointers** (the `new` keep reason for each pointer that `old` replaced):

| reason | count |
|---|---:|
| file_written_later (H1: a later opaque call may have written the file) | 1862 |
| command_output_changed_later | 72 |
| command_pointers_disabled (H2) | 22 |
| dedupe (now a lossless reference to an identical result) | 22 |
| **total** | **1978** |

By the kind of pointer at `old`: 649 `file_whole`, 1324 `file_range` and 5 `command` were removed. At `new`,
33 `file_whole`, 41 `file_range` and 0 `command` survive, in 38 items (it was 400 items at `old`).

With `allow_command_pointers=True` (`new_cmd`): 96 pointers survive, including 22 command pointers (5 of these
were command pointers at `old` and 17 were range pointers there). The subset still has 0 violations, the
verification is 0/0/0, and the pooled reduction is .0126.

## Reading

- The fix is mechanically safe relative to v0.7. It never adds a pointer, and every surviving output passes both
  verifiers.
- The cost is most of the gain. Pooled reduction drops from .0576 to .0123, against .0093 for lossless alone.
  On these offline transcripts, recoverable mode now adds about 0.3 points over lossless.
- Recommended configuration: `rules_mode=recoverable` with `workspace_root` (so the disk check runs) and command
  pointers off (the default). Whether recoverable is worth enabling over lossless at this margin is a product
  decision.
