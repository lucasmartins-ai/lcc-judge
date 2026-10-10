# Real-context bench v0.5: Codex TEST half, rules@d0cb548 (frozen 2026-10-10)

Machine-readable spec: `protocol.json`. If the two disagree, `protocol.json` counts.

| frozen file | sha256 |
|---|---|
| `protocol.json` | `5720df9cc78c54dd2c81acd4449a804052706affc7e141bd887d853c24e7a230` |
| `research/real_context_bench.py` (v0, unchanged) | `1d462543b39382113b1f03854d80f6850897f7591787c41c57c936f15604ec5e` |
| `research/real_context_bench_v02.py` (unchanged) | `ccbfe9abbe109f3a11c014c9c7ff9040078fdcf273abad1b8392439ff75f7ce0` |
| `research/real_context_bench_v03.py` (unchanged) | `4bf10daf00f9cf2613b2ab7c16cd3203ca1122f6fe1810cbb4b4bee2d2a73940` |
| `research/codex_context.py` (unchanged) | `60c296094bb37d059195dc9c5354a27d3a1e673122971a518a713f2851b4ed8e` |
| `research/real_context_bench_v04.py` (unchanged) | `d483b60c2b6ed463cf5a2783865a7c932202f6aa35d03ce8cddc751be77d4ead` |
| `research/real_context_bench_v04_audit.py` (aggregation, unchanged) | `a54073344b6892aef1d116b13878e901045410070a6bb34ae20220ff69e9daa6` |
| `research/real_context_bench_v05.py` (split, unchanged since 3b8e695) | `22ecb3590600fd536429e3b59ff3f2b376e38cca71261f21a3b969e493bb456b` |
| `research/real_context_bench_v05_test.py` (TEST runner, new) | `d0891f9c2b42fecf0bfa1f2b738c671b983e16a3b6a77e282a18f73ccacb5e8f` |
| private `split.json` | `42eae2ed70b061565021403c9fcf72133400542f24c6b7db3706b413dffbba25` |
| private `test-sample.json` | `b3a8573447be3931138607d2060daed9c028a8e9a5cef3ef064d024ca0e216bc` |
| private `labels-llm-v2.jsonl` (v0.5) | `2e2929bcb25caf4ebce6c87f7661c092bb3252ae2cfacb0eb78906161ce34564` |

The private hashes equal those in `split-receipt.json`. Committed and pushed **before any TEST
dossier is built**. Every TEST phase refuses to run if any hash differs.
Private root: `~/.lcc/bench/codex-heldout-v0.5/`. The repo gets counts only.

## Why

v0.4 (rules@8997be6) was a valid session-disjoint test. It FAILED its pre-registered audit:
21/150 flagged, upper Wilson .2046 > .10. The policy was then changed on the v0.5 DEV half only
(98 sessions, 141 dossiers, two rounds), using DEV runs and the v0.4 aggregate failure pattern.
v0.4 items and verdicts were not used. v0.5 re-tests the changed policy on the untouched TEST half
with the v0.4 measurement unchanged.

## Policy under test

LCC `feat/transcript-rules-policy` (PR #45, not merged) at `d0cb5488a16ace11d387ba7ab240b9a931bfc490`
(HEAD = origin, clean tracked tree), worktree `/Users/Master/lcc-wt-rules`. Both arms run on that
commit; the runner checks `lcc.__file__`, HEAD and a clean tree. Arms, offline guard, one pass per
arm, no retries, 600 s per item: as v0.4.

## TEST sample (seed 20261012, from the v0.5 split at 3b8e695)

- 196 eligible sessions (59 v0.4/earlier-bench sessions excluded), split 98 DEV / 98 TEST.
  0 shared sessions, 0 shared paths.
- 140 TEST candidates (≤ 2 per session), 4 low-confidence excluded, equal allocation to 60 items
  from 50 sessions. Strata as in `split-receipt.json`.
- **Dossiers are built after this freeze**, once, by `real_context_bench_v05_test dossiers`
  (v0.4 `build_dossier`, unchanged). It asserts every item is from a TEST session, no item shares a
  session or path with DEV, no id is a DEV dossier, 0 id mismatches, 0 empty contexts. The digest
  goes to private `dossiers-receipt.json`, is checked by every later phase and reported in `score.json`.

**Disclosures.** The policy was tuned on DEV (DEV round-2 audit: 9/100 flagged). 37 of the 60 TEST
items carry v0.4 labels made from request text only, so those request texts were seen once; their
contexts never were. 15 TEST labels are new v0.5 labels from request text.

## Probes, metrics, verdict

Copied from v0.4 unchanged. Verdict vs mechanical: rules wins iff item retention >= mechanical AND
pooled token reduction strictly > mechanical AND zero guard trips. Probe retention is still mostly
by construction (see v0.4 caveat). Since 43cde02/d0cb548 the edited-later trim guard also fires on
Codex `apply_patch` bodies; GIT_STATE and LAST_ARTIFACT_EDIT remain NOT_APPLICABLE on Codex.

## Drop/trim audit (primary evidence), identical to v0.4

- 150 drop/trim decisions of the rules run, seed `20261012`, ≤ 3 per item, v0.3 `audit_select`
  unchanged. Ids D001–D150; `f1` = D001–D050, `f2` = D051–D100, `f3` = D101–D150; written once.
- Packets (v0.4 `packet`, unchanged): request, last 3 turns, tool, input; removals show the
  original output; shortenings show kept head, kept tail and the removed middle (checked exact).
- Blinding: no rule, reason, source, arm, item id or category; every `[... lcc: ...]` note → `[...]`.
  `key.jsonl` stays private.
- Judges A, B, C (owner or fresh Claude Code subagents with only the instructions and their file;
  no paid or remote API). Routing **A: f1+f2, B: f2+f3, C: f3+f1**. Instructions verbatim in
  `protocol.json` (same text as v0.4).
- Validity, re-judging by the third judge, incompleteness: as v0.4.
- **Primary.** Flagged iff either final verdict is `needed` or `unsure`, or incomplete.
  False-drop rate = flagged / 150, Wilson 95%. **PASS iff upper bound ≤ 0.10** (≤ 7 of 150).
- Secondary: needed-only, agreement (raw, kappa), unsure rate, splits by decision/rule/tool.
- Aggregation: `research/real_context_bench_v04_audit.py`, byte-identical to v0.4, called with
  root = the v0.5 private root (`rejudge`, `audit-score` phases of the v0.5 runner).

## Run

```
PYTHONPATH=/Users/Master/lcc-wt-rules/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.real_context_bench_v05_test dossiers
    ... run --arm mechanical ; ... run --arm lcc_rules_transcript ; ... score ; ... audit
# judging (judge-A/B/C.jsonl -> verdicts-A/B/C.jsonl), then:
    ... rejudge        # if any verdict is invalid
    ... audit-score
```
