# Lossless dedup v1: LCC `rules_mode="lossless"` on every existing dossier set

Counts only. Per-item records (ids, decisions, outputs) stay under `/Users/Master/.lcc/bench/lossless-dedup-v1/`.

- LCC: `/Users/Master/lcc-wt-rules`, branch `feat/transcript-rules-policy` (PR #45), commit
  `83f71207d965e0ea257007adf9d44578a252f5f7`, clean tree (checked by `v02.check_lcc_rules` before the run).
- Run: `research/lossless_dedup_measure.py`. It is offline, runs under the bench network guard (0 trips) and makes no judge or remote calls.
- Payload, rendering and token counting are the bench code, reused unchanged: `v02.rules_payload`, `rcb.apply_transcript` and `rcb.lcc_count` (gpt-4.1 counter). Reductions are computed the same way as in the earlier score files, on the same dossiers.
- Probes: the frozen probe config. It is byte-identical in the v0, v0.3, v0.4 and v0.5 protocols, and is loaded sha-checked from v0.5. Unlabelled Codex v0.5 DEV items are scored as `UNKNOWN`, following the v0.5 dev convention.
- Each item is checked for losslessness three ways, and every one of them must report zero violations:
  1. the run-time self-check inside `compact_transcript`, which falls back to keeping everything if it fails;
  2. `verify_lossless(original_payload, compacted_payload)`, run again here from the two payloads;
  3. an independent check in this module. It confirms that each replaced result's target is kept unchanged in the rendered output, has the same `is_error`, and contains the replaced result's whole lines contiguously and in order. Only the three Codex volatile header lines are ignored.
- Control: on items where nothing was replaced, the rendered output equals the input byte for byte (707/707).

## Lossless mode (this run)

| set | n | violations (rt / verify / indep.) | token reduction pooled | median item | max item | items reduced | calls | replaced (identical / contained) | dropped / trimmed | probe retention item | probe retention probe | latency ms median / p90 / max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude frozen 60 | 60 | 0 / 0 / 0 | .0034 | .0012 | .0449 | 41 | 5984 | 359 (327 / 32) | 0 / 0 | 49/49 | 69/69 | 6.2 / 35.2 / 92.8 |
| Claude fresh 60 | 60 | 0 / 0 / 0 | .0016 | .0003 | .0125 | 31 | 6156 | 201 (156 / 45) | 0 / 0 | 55/55 | 77/77 | 9.6 / 38.7 / 74.3 |
| Claude dev 326 | 326 | 0 / 0 / 0 | .0063 | .0020 | .2931 | 209 | 22783 | 1704 (1601 / 103) | 0 / 0 | 323/323 | 455/455 | 6.0 / 17.6 / 394.0 |
| Codex v0.4 test 60 | 60 | 0 / 0 / 0 | .0130 | .0021 | .2428 | 45 | 4345 | 453 (396 / 57) | 0 / 0 | 54/54 | 69/69 | 10.3 / 30.5 / 56.4 |
| Codex v0.5 dev 141 | 141 | 0 / 0 / 0 | .0187 | .0026 | .5404 | 115 | 10576 | 1249 (1068 / 181) | 0 / 0 | 137/137 | 189/189 | 8.8 / 19.8 / 32.0 |
| Codex v0.5 test 60 | 60 | 0 / 0 / 0 | .0155 | .0018 | .0842 | 41 | 4276 | 607 (543 / 64) | 0 / 0 | 54/54 | 72/72 | 6.8 / 19.8 / 33.2 |
| **all** | **707** | **0 / 0 / 0** | | | | 482 | 54120 | 4573 | 0 / 0 | 672/672 | 931/931 | |

On the same items, the full-context control retains 100% of items and probes in every set.

## Against earlier arms (pooled token reduction; item retention in parentheses)

| set | lossless (this run) | mechanical | jev_block | lossy rules (pinned commit of that bench) | lossy audit |
|---|---|---|---|---|---|
| Claude frozen 60 | .0034 (1.000) | .0001 (.9796) | .0345 (.9592) | .3864 (1.000), v0.2 | — |
| Claude fresh 60 | .0016 (1.000) | .0001 (.9818) | — | .3497 (1.000), v0.3 | — |
| Claude dev 326 | .0063 (1.000) | .0002 | — | .3892, last DEV iteration (private log) | — |
| Codex v0.4 test 60 | .0130 (1.000) | .0004 (.963) | — | .6414 (.9815), v0.4 | FAIL 21/150 flagged |
| Codex v0.5 dev 141 | .0187 (1.000) | .0021 (.9781) | — | .2614 (1.000), rules@d0cb548 | — |
| Codex v0.5 test 60 | .0155 (1.000) | .0009 (.963) | — | .1914 (.963), rules@d0cb548 | FAIL 36/132 flagged |

Sources: the score files listed in `summary.json` under each set's `prior.source`.

## Reading

- Lossless mode found no violations under any of the three checks, on 707 items and 4573 replaced results. Probe retention matches the full context: 672/672 items and 931/931 probes.
- Its pooled reduction is above mechanical on every set (Claude .0016 to .0063, Codex .0130 to .0187). It is below `jev_block` on the frozen 60 (.0034 vs .0345) and one to two orders of magnitude below the lossy rules.
- Medians are small (.0003 to .0026): most sessions repeat little exact output. The savings come from a few items with many identical reruns, up to .54 on a single Codex DEV item.
- What this measures: removals are provably lossless with respect to the transcript text, so no judge is needed. It does not measure whether the much smaller savings are worth turning on. It also does not show that an agent never needs to know *when* an earlier output appeared: an "[output contained in X]" pointer keeps the text but moves where it appears.
- The "independent" check reimplements the same normalisation rule (three Codex header lines), not a separately derived one. A wrong rule would therefore pass both checks.
