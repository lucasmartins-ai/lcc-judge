# Status (2026-10-25)

Read this first. Every number below comes from a committed receipt; the path is given
next to each table. Paths are relative to `research/goal-engine-2026-10-04/` unless they
start with `research/` or `docs/`. Counts only: no session text is stored in this repo.

Benchmark: `python -m research.bench all` recomputes the v3 edge / dev / held-out / cost numbers offline (no LLM call); latest run in [research/bench-results/latest.md](research/bench-results/latest.md).

## Current state (2026-10-25)

LCC-judge now builds two kinds of local model for LCC: a **block judge**, which decides what to keep when
context is compacted, and an **intake judge**, which classifies the request the user types. Both run on
CPU, stdlib only, with no network. LLMs (Opus, Gemini, Codex) appear only as offline teachers, references
and voters.

| line | state | evidence |
|---|---|---|
| Block judge specialist v3 | **shipped**, LCC auto default for transcripts (lcc#50, lcc#51) | `specialist-v1/V3_FINAL_TEST_RESULTS.md` |
| Block judge v4 (Opus relevance teacher) | not adopted | `specialist-v1/V4_DEV_RESULTS.md` |
| Block judge v5 (edge detectors) | not adopted on dev; sealed edge v2 35/30/20 vs v3 26/19/10 | `specialist-v1/V5_DEV_RESULTS.md` |
| v5 cycle 2 (rankers as stash policy) | no ranker replaces `stashed`'s choice (all-kept non-inferiority fails) | `specialist-v1/V5C2_RESULTS.md` |
| `stashed` + `recall` | H1 and H2 pass: 36.6% fewer tokens, non-inferior to full context on artifact recall (+0.006 [−0.023, +0.034]); 90% of stash probes recalled | `stashed-recall-v1/RESULTS.md` |
| Probe eval v1 | verbatim modes beat Claude Code's native summary on artifact trail; not a matched-budget result | `probe-eval-v1/RESULTS.md` |
| When to compact | idle-return cache re-writes are 15.9% of main-session cost; stash-on-idle-return is a conditional opt-in; keep-warm pings fail the cost gate; fresh-session handoff +27.6% cost, quality **unmeasured** | `research/when-to-compact-2026-10-19/WHEN_RESULTS.md`, `WHEN2_RESULTS.md` |
| **Intake judge v1** | **shipped** in LCC as an advisory `category` field (lcc#124, merged 2026-10-23, `9b0fac3`) | `intake-judge-v1/RESULTS.md` |
| **Intake judge v2** (adds the agent's previous turn) | frozen, owner held-out pending | `intake-judge-v2/FREEZE.json` |
| **Intake judge v3** (adds public data) | **external test passed**; owner held-out pending | `intake-judge-v3/RESULTS_EXTERNAL.md` |

### Intake judge (request category)

The intake judge puts each prompt in one of the 13 categories of `request-taxonomy-v1/taxonomy-v2.json`, or
UNKNOWN. With the category, LCC can name the context the agent needs (the pasted error for a failure
report, git state for a ship request) without rewriting the user's text. Model: hashed n-grams and
multinomial logistic regression, distilled from Opus labels. Every version below was pre-registered.

**v1**
- Trained on the owner's prompts only.
- Owner-labelled held-out, 116 items both owner passes agree on: 0.509, vs keyword rules 0.224 and Opus
  0.862. Beats rules: PASS. Close to Opus: FAIL.
- Cost: 0.26 ms median per prompt, 1.2 MB model. Shipped advisory, shown only at probability >= 0.45.

**v2**
- Adds the tail of the agent's previous turn. Pick: B C=10.
- Dev macro-F1 0.490, vs 0.466 for prompt-only. Static embeddings (shrunk potion-multilingual-128M) lost:
  dev macro-F1 0.34, RSS about 780 MB.
- Amendment 1 changed the export format after the dev run (same weights).
- Waits for the owner held-out.

**v3**
- Trained on owner prompts, a public Claude Code set (MIT, about one developer) and WildChat coding chats
  (ODC-BY, split by person).
- External held-out, 99 items:
  - Gold: the owner's labels, picked blind and then checked against Claude, Codex and Gemini votes. The
    reveal changed 1 label.
  - v3 0.697 vs v1 0.303: **+0.394 [+0.283, +0.500]**. PASS on the `final` and `blind` labels.
  - Opus 0.859; keyword 0.424; always answering `specified_task` 0.434.
- **v1 is worse than that constant answer on other people's prompts.** A judge trained on one person does
  not transfer.
- Most of v3's gain is on WildChat. On the one other Claude Code user (22 items) it is +0.18 [0.00, +0.36],
  so "works for other agent users" is suggested, not shown.
- Amendment 3 removed one dev guard after the dev run. v3 ships only if the owner held-out also passes:
  non-inferior to the shipped model, CI lower bound above −0.03.

**Owner held-out (v2 and v3)**
- Sessions started from 2026-10-24.
- The gold is drawn once at least 100 qualifying sessions exist. Fallback: 60 sessions by 2026-11-30.
- A daily local scheduled task (`intake-heldout-count`) runs `python -m research.intake_v2 count` and
  reports when the trigger is met.

## Update 2026-10-18: specialist v3 final test (post-cutoff held-out set)

Pre-registered in `specialist-v1/V3_FINAL_TEST_PROTOCOL.md`; results in `specialist-v1/V3_FINAL_TEST_RESULTS.md`
(INFERIDO: rule-based next-action labels). 208 held-out items, 193 primary in 36 session groups.

- vs recency / BM25 / mechanical: **PASS** on both metrics (CI lower bounds > 0; recall AUC 0.899 vs 0.818 /
  0.803 / 0.829).
- vs generalists (36-item subset): Opus recall −0.009 [−0.055, +0.031], all-kept +0.069 [−0.028, +0.167]
  (labelled *inferior* by the rule, but this is inconclusive: no significant gap either way). Gemini 3.8 Flash
  recall +0.038 [−0.007, +0.083] *not inferior*, all-kept +0.118 [+0.026, +0.220] *superior*. The headline
  "superior to a generalist" is **not** met.
- Cost **PASS**: median 178 ms, p90 567 ms, peak RSS 97.5 MB.
- The edge suite (synthetic) still favours the generalists (35/35/35 vs v3 28/23/20).

---

*Everything from here down is the 2026-10-11 snapshot, kept as history. Where it disagrees with "Current
state" above (for example "the learned judge is not adopted"), the section above is current.*

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
- Intake judge: [v1](research/goal-engine-2026-10-04/intake-judge-v1/RESULTS.md),
  [v2 protocol](research/goal-engine-2026-10-04/intake-judge-v2/PROTOCOL.md),
  [v3 protocol](research/goal-engine-2026-10-04/intake-judge-v3/PROTOCOL.md),
  [v3 external results](research/goal-engine-2026-10-04/intake-judge-v3/RESULTS_EXTERNAL.md); code in
  `research/intake_v1.py`, `intake_v2.py`, `intake_v3.py`, `intake_judge*.py`. Teacher and voter runs used
  subscription CLIs and the owner's browser session only: no API spend.
- Model: [MODEL_CARD.md](MODEL_CARD.md); design docs: `docs/00-vision.md` … `docs/10_OBSERVATION_OPERATION.md`

## Open gaps and next steps (2026-10-11; current list in docs/08-roadmap.md)

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
