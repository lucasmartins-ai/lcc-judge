# Lossless dedup v1: LCC `rules_mode="lossless"` on every existing dossier set

Counts only. Per-item records (ids, decisions, outputs) stay under `/Users/Master/.lcc/bench/lossless-dedup-v1/`.

- LCC: `/Users/Master/lcc-wt-rules`, branch `feat/transcript-rules-policy` (PR #45), commit
  `7b92ad2b80d6fd812ac706f3270a9ed838806514`, clean tree (checked by `v02.check_lcc_rules` before the run).
- Run: `research/lossless_dedup_measure.py`. It is offline, runs under the bench network guard (0 trips) and makes no judge or remote calls.
- Payload, rendering and token counting are the bench code, reused unchanged: `v02.rules_payload`, `rcb.apply_transcript` and `rcb.lcc_count` (gpt-4.1 counter). Reductions are computed the same way as in the earlier score files, on the same dossiers.
- Probes: the frozen probe config. It is byte-identical in the v0, v0.3, v0.4 and v0.5 protocols, and is loaded sha-checked from v0.5. Unlabelled Codex v0.5 DEV items are scored as `UNKNOWN`, following the v0.5 dev convention.
- Each item is checked for losslessness three ways, and every one of them must report zero violations:
  1. the run-time self-check inside `compact_transcript`, which falls back to keeping everything if it fails;
  2. `verify_lossless(original_payload, compacted_payload)`, run again here from the two payloads;
  3. an independent check in this module. It confirms that each replaced result's target is kept unchanged in the rendered output and has the same `is_error`, and that the note's own claim holds: `[identical output kept at <id>]` means the same lines (only the three Codex volatile header lines are ignored); `[output = lines a-b of <id>]` means the original is exactly raw lines a..b of `<id>`. A range-less or wrong-range note is a violation.
- Control: on items where nothing was replaced, the rendered output equals the input byte for byte (226/226).

## Lossless mode (this run)

| set | n | violations (rt / verify / indep.) | token reduction pooled | median item | max item | items reduced | calls | replaced (identical / line range) | dropped / trimmed | probe retention item | probe retention probe | latency ms median / p90 / max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude frozen 60 | 60 | 0 / 0 / 0 | .0034 | .0012 | .0449 | 40 | 5984 | 357 (327 / 30) | 0 / 0 | 49/49 | 69/69 | 8.6 / 43.3 / 154.9 |
| Claude fresh 60 | 60 | 0 / 0 / 0 | .0016 | .0002 | .0125 | 31 | 6156 | 199 (156 / 43) | 0 / 0 | 55/55 | 77/77 | 8.6 / 39.3 / 78.4 |
| Claude dev 326 | 326 | 0 / 0 / 0 | .0063 | .0020 | .2931 | 209 | 22783 | 1704 (1601 / 103) | 0 / 0 | 323/323 | 455/455 | 6.3 / 17.1 / 218.4 |
| Codex v0.4 test 60 | 60 | 0 / 0 / 0 | .0125 | .0018 | .2428 | 45 | 4345 | 441 (441 / 0) | 0 / 0 | 54/54 | 69/69 | 10.6 / 36.5 / 80.3 |
| Codex v0.5 dev 141 | 141 | 0 / 0 / 0 | .0185 | .0026 | .5302 | 114 | 10576 | 1210 (1210 / 0) | 0 / 0 | 137/137 | 189/189 | 14.4 / 93.5 / 403.9 |
| Codex v0.5 test 60 | 60 | 0 / 0 / 0 | .0153 | .0018 | .0842 | 41 | 4276 | 595 (595 / 0) | 0 / 0 | 54/54 | 72/72 | 11.1 / 84.4 / 210.7 |
| **all** | **707** | **0 / 0 / 0** | | | | 480 | 54120 | 4506 (4330 / 176) | 0 / 0 | 672/672 | 931/931 | |

On the same items, the full-context control retains 100% of items and probes in every set.

## Change from the first run (commit 83f7120)

The first run wrote `[output contained in <id>]` for a partial match. That note did not say which lines of `<id>` the original was, so the original could not be rebuilt (example: `prod.hosts` returned X, a later read of `dev.hosts` returned X+Y). Review found 482 such notes; 474 pointed at a call with a different input. The note is now `[output = lines a-b of <id>]` on raw lines, and both verifiers check that exact range. A partial match that held only after ignoring the Codex volatile header lines cannot be written as a raw line range, so it is no longer made. On Codex that was every partial match (0 line-range notes now; some of those results are instead replaced by a later identical rerun). Totals moved from 4573 replaced results (482 partial) to 4506 (176 line range), and Codex pooled reductions dropped by .0002 to .0005.

## Against earlier arms (pooled token reduction; item retention in parentheses)

| set | lossless (this run) | mechanical | jev_block | lossy rules (pinned commit of that bench) | lossy audit |
|---|---|---|---|---|---|
| Claude frozen 60 | .0034 (1.000) | .0001 (.9796) | .0345 (.9592) | .3864 (1.000), v0.2 | — |
| Claude fresh 60 | .0016 (1.000) | .0001 (.9818) | — | .3497 (1.000), v0.3 | — |
| Claude dev 326 | .0063 (1.000) | .0002 | — | .3892, last DEV iteration (private log) | — |
| Codex v0.4 test 60 | .0125 (1.000) | .0004 (.963) | — | .6414 (.9815), v0.4 | FAIL 21/150 flagged |
| Codex v0.5 dev 141 | .0185 (1.000) | .0021 (.9781) | — | .2614 (1.000), rules@d0cb548 | — |
| Codex v0.5 test 60 | .0153 (1.000) | .0009 (.963) | — | .1914 (.963), rules@d0cb548 | FAIL 36/132 flagged |

Sources: the score files listed in `summary.json` under each set's `prior.source`.

## Reading

- Lossless mode found no violations under any of the three checks, on 707 items and 4506 replaced results. Probe retention matches the full context: 672/672 items and 931/931 probes.
- Its pooled reduction is above mechanical on every set (Claude .0016 to .0063, Codex .0125 to .0185). It is below `jev_block` on the frozen 60 (.0034 vs .0345) and one to two orders of magnitude below the lossy rules.
- Medians are small (.0003 to .0026): most sessions repeat little exact output. The savings come from a few items with many identical reruns, up to .53 on a single Codex DEV item.
- What this measures: every removal is reversible from the compacted transcript alone, and that is checked mechanically, so no judge is needed. Each note names the kept result and, for a partial match, the exact line range, so the original rebuilds byte for byte (identical notes: up to the three Codex volatile header lines). It does not measure whether the much smaller savings are worth turning on. It also does not show that an agent never needs to know *when* an earlier output appeared: the note keeps the text reachable but the agent has to follow it, and a line-range note can point at a call with a different input (another file or command).
- The "independent" check reimplements the same normalisation rule (three Codex header lines), not a separately derived one. A wrong rule would therefore pass both checks.
