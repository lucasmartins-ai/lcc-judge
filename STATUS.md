# Status (2026-10-11)

Read this first. Every number below comes from a committed receipt; the path is given
next to each table. Paths are relative to `research/goal-engine-2026-10-04/` unless they
start with `research/` or `docs/`. Counts only: no session text is stored in this repo.

## Goal

Find out whether a small local model can decide what LCC keeps in an agent's context
more cheaply than the remote Laya/Jev path, without losing what the agent needs.
"Engine + LCC" is the unit evaluated, on real sessions and task outcomes.

## Short answer

- **The learned judge is not ready and is not adopted.** No learned candidate passed outside
  its training data. The checkpoint in this repo runs in LCC only as a shadow ranker
  (every block KEEP).
- **What shipped is a deterministic policy in LCC, not a model.** On real sessions, LCC's
  block mode with Jev cuts 3.5% of tokens; the lossy rules cut 19–64% but failed two blind
  audits; the lossless and recoverable modes pass mechanical checks but cut about 1%.
- **Laya was never run on the real-context bench.** There is no real-session number for Laya.

## What was proven

| claim | evidence |
|---|---|
| 3,782 redacted real prompts from 7 agents (stored only under `~/.lcc`) | `genuine-requests-v1/README.md` |
| 13-category request taxonomy; owner confirmed 26/27 held-out high-confidence items (.963) | `request-taxonomy-v1/README.md` |
| Lossless mode: 0 violations under 3 checks on 707 items; retention 672/672 items, 931/931 probes | `lossless-dedup-v1/RESULTS.md` |
| Recoverable (file pointers): v0.7 TEST audit PASS 1/54 (upper .0977); v0.8 fix is a strict subset of v0.7 on 847 items, verification 0/0/0 | `real-context-bench-v0.7/RESULTS.md`, `recoverable-v0.8/RESULTS.md` |

## What failed

| line of work | result | evidence |
|---|---|---|
| Learned candidates (many studies) | direct-P1 mean final AUC .7145 vs .90 gate; varied-relation fresh confirmation pooled AUC .8502–.8703, all three seeds fail; none adopted | `direct-relevance-v1/summary.json`, `varied-relation-confirm-v1/RESULTS.md`, `MODEL_CARD.md` |
| Authored corpus (retry/UDP/git fixtures) | owner review agreement .417 vs .95 gate | `human-review-v2-pt/RESULTS.md` |
| Lossy rules, Codex held-out | v0.4: 21/150 flagged (upper .2046); v0.5: 36/132 flagged (upper .3543); limit .10 | `real-context-bench-v0.4/RESULTS.md`, `real-context-bench-v0.5/RESULTS.md` |
| Lossy rules, Claude "fresh 60" | audit PASS at the margin (7/150), but the review FAILED it: shares all 25 sessions with the frozen 60 | `real-context-bench-v0.3/RESULTS.md` |

## What shipped (LCC, merged)

| PR | merged | what |
|---|---|---|
| [lucasmartins-ai/lcc#40](https://github.com/lucasmartins-ai/lcc/pull/40) | 2026-10-09 | opt-in request log (redacted prompts, local only) |
| [lucasmartins-ai/lcc#44](https://github.com/lucasmartins-ai/lcc/pull/44) | 2026-10-10 | transcript mode fits every Jev request under the API's real token limit (cause of 77 rejections in v0.1) |
| [lucasmartins-ai/lcc#45](https://github.com/lucasmartins-ai/lcc/pull/45) | 2026-10-11 (`74f10e1`) | offline `rules` provider: `lossless` (default), `recoverable` (file pointers; disk check with `workspace_root`), lossy rules kept but not recommended |

Recommended config: `rules_mode=recoverable` + `workspace_root` + command pointers off;
`lossless` stays the default (`PLAN.md`, section "Desfecho 2026-10-11").

## Benchmark on real sessions

Pooled token reduction is `1 − Σout/Σin` (heuristic tokens up to v0.5, lcc tokenizer in
lossless/v0.8). Retention is item retention on mechanical probes; probes are proxies and,
for the rules arms, largely satisfied by construction, so the blind audits are the
primary safety evidence where they exist.

| arm | sets | token reduction (pooled) | retention / audit | remote spend | source |
|---|---|---|---|---|---|
| mechanical | Claude frozen 60 | .0001 | 48/49 | $0 | `real-context-bench-v0/RESULTS.md` |
| specialist (this repo, shadow) | Claude frozen 60 | 0 | 49/49 (keeps everything) | $0 | `real-context-bench-v0/RESULTS.md` |
| Jev block | Claude frozen 60 | .035 | 47/49 | $43.52 | `real-context-bench-v0.1/RESULTS.md` |
| Jev transcript (**invalid run**: 102/379 requests failed, before #44) | Claude frozen 60 | .252 | 30/49 | $41.42 | `real-context-bench-v0.1/RESULTS.md` |
| lossy rules | Claude frozen 60 (v0.2) | .386 | 49/49, probes copy the policy; 3 bugs found after | $0 | `real-context-bench-v0.2/RESULTS.md` |
| lossy rules | Codex held-out 60 (v0.4) | .641 | audit FAIL 21/150 | $0 | `real-context-bench-v0.4/RESULTS.md` |
| lossy rules | Codex TEST 60 (v0.5) | .191 | audit FAIL 36/132 | $0 | `real-context-bench-v0.5/RESULTS.md` |
| lossless | 707 items, 6 sets | .0016–.0185 per set | 672/672; 0 violations | $0 | `lossless-dedup-v1/RESULTS.md` |
| recoverable (transcript proxy) | Hermes TEST 80 (v0.7) | .0343 | audit PASS 1/54 | $0 | `real-context-bench-v0.7/RESULTS.md` |
| recoverable proxy v0.8 (current rules) | 847 items, 8 sets | .0123 (lossless on same items .0093) | subset of v0.7, 0/0/0 | $0 | `recoverable-v0.8/RESULTS.md` |
| recoverable with disk check (`7c75761`) | — | **not measurable offline** (no disk snapshots) | — | — | `recoverable-v0.8/RESULTS.md` |
| Laya | — | **not run on real sessions** | — | — | `real-context-bench-v0/PROTOCOL.md` ("Not in v0: laya") |

The only Laya numbers are on curated or synthetic dossiers: in the 8K/32K Pareto runs Laya
and the engine removed zero context while Jev removed about 79% of characters; in the
36-task synthetic observation pilot Laya scored 33/36 (Jev 36/36, full 34/36) (`PLAN.md`).

## Spend

Remote API spend on the real-context bench: **$84.93**, all in v0.1 (Jev arms, $85 cap
approved by the owner). Every other real-session arm ran offline at $0
(`real-context-bench-v0.1/RESULTS.md`). Training and earlier pilot costs are in `REPORT.md`.

## Evidence index

- Plan and decisions: `PLAN.md` (Portuguese), `REPORT.md`, `research/failures.md`, `research/experiments.md`
- Requests: `genuine-requests-v1/README.md`, `request-taxonomy-v1/README.md`, `human-review-v2-pt/RESULTS.md`
- Real-context bench: [v0](research/goal-engine-2026-10-04/real-context-bench-v0/RESULTS.md),
  [v0.1](research/goal-engine-2026-10-04/real-context-bench-v0.1/RESULTS.md),
  [v0.2](research/goal-engine-2026-10-04/real-context-bench-v0.2/RESULTS.md),
  [v0.3](research/goal-engine-2026-10-04/real-context-bench-v0.3/RESULTS.md),
  [v0.4](research/goal-engine-2026-10-04/real-context-bench-v0.4/RESULTS.md),
  [v0.5](research/goal-engine-2026-10-04/real-context-bench-v0.5/RESULTS.md),
  [v0.6](research/goal-engine-2026-10-04/real-context-bench-v0.6/RESULTS.md),
  [v0.7](research/goal-engine-2026-10-04/real-context-bench-v0.7/RESULTS.md),
  [recoverable v0.8](research/goal-engine-2026-10-04/recoverable-v0.8/RESULTS.md),
  [lossless dedup v1](research/goal-engine-2026-10-04/lossless-dedup-v1/RESULTS.md)
- Model: [MODEL_CARD.md](MODEL_CARD.md); design docs: `docs/00-vision.md` … `docs/10_OBSERVATION_OPERATION.md`

## Open gaps and next steps

1. **Outcome-based evaluation.** Every retention number is a probe or an LLM-judge audit.
   None measures whether the agent finished the task. This is the main gap.
2. **Measure recoverable live.** The disk-check mode can only be measured in real use,
   through the opt-in request log (#40).
3. **Laya on the same bench.** Run Laya on the frozen real-session sets. The Jev
   fall-through noted in the v0 protocol applies only to the `dd5dd80` pin; it is fixed on
   main by lucasmartins-ai/lcc#43 (`351a44f`, merged 2026-10-09).
4. **Jev transcript after #44.** v0.1 transcript numbers are invalid; not re-measured.
5. **Learned judge only after outcome labels.** No more training on authored corpora;
   train only once real requests carry outcome labels.
6. Range and command pointers have never had a blind audit (`recoverable-v0.8/RESULTS.md`).
