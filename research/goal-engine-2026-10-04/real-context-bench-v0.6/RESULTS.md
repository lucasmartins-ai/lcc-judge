# Real-context bench v0.6: run results (audit not judged yet)

Protocol: `protocol.json` (frozen and pushed in b731998, before the dossiers were built). LCC 1bc2005.
These are counts only. The per-item data stays in `~/.lcc/bench/heldout-v0.6/`.

**Run:** 60 dossiers were built, with 0 id mismatches, 0 empty contexts and 0 overlap with any earlier
set. Each arm ran once, offline, with 0 guard trips and all 60 items `ok`.

| arm | item retention (49 scored) | pooled token reduction | median per item |
|---|---|---|---|
| mechanical | .898 | .0573 | .0000 |
| lcc_rules_lossless | 1.000 | .0081 | .0000 |
| lcc_rules_recoverable | 1.000 | .0411 | .0123 |

**Verification:** lcc's verifier found 0 violations and the independent check found 0, in both rules
arms. **runtime_fail_safe = 1 in each rules arm.** It is the same item in both arms, about 1.4M tokens
with 2093 tool calls. lcc's own runtime check rejected the lossless dedupe plan it had built for that
item. It then kept every tool call (degraded, output equal to input), so nothing unsafe was emitted.
The protocol requires runtime_fail_safe 0, so this is reported as a **failed verification
requirement**: a planner bug on this Hermes transcript, caught by the fail-safe. Duplicate tool-call
ids in the transcript are the likely cause, but this has not been confirmed. The policy was not
changed on TEST.

**Deviation:** one mechanical item (7.2 MB) ran for 4640 s even though the per-item limit is 600 s.
lcc's broad `except Exception` handlers swallow the harness's SIGALRM `ItemTimeout`, so the limit is
not enforced inside lcc (this harness has always worked this way). The record is `ok` and is scored
as recorded.

**Pointers (recoverable):** 166, all `file_whole` from `read_file`, in 31 items, with
`transcript_proxy`. No command pointers: Hermes's shell tool is not in lcc's SHELL_TOOLS.

**Audit:** 77 of 150 records were drawn, because 31 items × cap 3 limits the sample (f1 26, f2 26,
f3 25). Under the protocol's rule at n = 77, the result is PASS iff ≤ 2 records are flagged. Verdicts
are pending.
