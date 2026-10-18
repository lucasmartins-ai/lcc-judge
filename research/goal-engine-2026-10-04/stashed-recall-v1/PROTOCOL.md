# Stashed recall v1: does an agent recall what `stashed` removed, and does the task survive? (draft 2026-10-17)

**Status: DRAFT, not frozen.** It becomes binding when committed with the owner's route approval line (Run order,
step 2). Counts only in the repo; every answer, recall log and verdict stays under the private root
`~/.lcc/bench/stashed-recall-v1/`. Results are tagged INFERIDO until `gateClaim` returns PASS on them.

## Why

`stashed-v1` showed that `rules_mode=stashed` (LCC `4719fde`) removes 30.1% of tokens on 847 real-session
dossiers while every removed result stays byte-recoverable through `recall` (0 violations, two checkers). That is a
storage property. It says nothing about the two things that decide whether the mode is usable:

1. **Recall behaviour.** When a needed fact sits only in a stashed result, does the agent call `recall` for it?
   How often does it recall what it did not need?
2. **Task outcome.** Do answers on the same probes stay as good as with the full context?

## Reuse of probe-eval-v1 (frozen, not modified)

This eval reuses, read-only, from `probe-eval-v1` (frozen 2026-10-16, Amendments 1-3):

- **Population D:** 172 items, 75 session-lineage groups (`probe-receipt.json`, `ids_sha256`
  `5c1421ee885f7c39423ef06612b00026aa16c8ead5f13c85f7a62f4356bb860e`). Stratum J is not used.
- **Probes:** the private D probe files (`probes_sha256`
  `9cbf1ee7d960a490b89b6d58726bd6b2a2b38b0aa9b547a5fc4a58503226bc7f`): artifact 172, recall 162,
  continuation 172, decision 156. They were generated from `C` and `W` only, before any arm existed, and before
  `stashed` existed. No new probe is generated.
- **Context `C`:** rebuilt by the frozen builder (`D/items/`).
- **Code:** `research/probe_eval_v1.py` (sha256 `fa520220…49363d`) is imported, never edited: the CLI wrapper,
  gold rules, artifact recall, exact match, masking, judge call and paired cluster bootstrap.
- **Texts:** A, K and R unchanged. Q is extended (Q-T below) only for arms that have the tool.

The builder refuses to run if any reused hash differs.

## Arms

All arms use the same answerer (Claude Sonnet 5.5, medium effort, subscription `claude -p`), the same item order and
`P`, and the probes in one numbered call, as in probe-eval-v1.

| arm | context `C'` | tool | answerer text |
|---|---|---|---|
| `full_t` | `C` unchanged | `recall` present, stash empty for this item | Q-T |
| `stashed_t` | `C` after `rules_mode=stashed` at pin `4719fde`, no `workspace_root` | `recall` over this item's stash | Q-T |
| `stashed_0` | same `C'` as `stashed_t` | none | Q (frozen) |

- `full_t` vs `stashed_t` is the outcome contrast with the prompt and tool presence held equal.
- `stashed_t` vs `stashed_0` isolates what the recall tool buys.
- probe-eval-v1's `full` (no tool, Q) is shown as a reference row only, never in a test: its prompt differs.

**Compaction.** `stashed` runs offline at the pin in a detached worktree (`~/.lcc/bench/lcc-4719fde`), clean tree,
`LCC_STASH_DIR=<private>/stash/<item>` (one stash per item, so an item can only recall its own blobs). The output
is re-checked with lcc's `verify_stashed` and `research.stashed_v1.independent_stash_check`. A violation voids the
item for the two stashed arms and is reported.

**Tool shim.** The answerer sees exactly one tool, `recall(id, lines?)`, served by
`research/recall_mcp_shim.py` (stdio MCP, written in the harness step). It calls
`lcc.relevance.transcript_stash.recall` at the pin and:
- logs every call (item, arm, stash id, line range, bytes and tokens returned, ok / error) to
  `<private>/recall-log/<arm>/<item>.jsonl`;
- caps at **8 calls per answer** (the 9th returns an error text) and **20 000 tokens per call** (longer blobs
  return the first 20 000 tokens plus a note to pass `lines`);
- never reads outside the item's stash dir.

CLI flags: `--tools ''`, `--strict-mcp-config --mcp-config <shim.json>`, `--allowedTools mcp__stash__recall`,
`--permission-prompts none`, no settings or CLAUDE.md, ANTHROPIC_* stripped. Any attempt at another tool is
denied by the CLI and counted.

### Q-T — answerer instructions with the tool (draft; sha256 recorded at freeze)

```
You are continuing a coding-agent session. The context above is everything you have from the session so far; parts of it may have been compressed. Some old tool results were replaced by a marker of the form [removed: N tokens · lcc recall <id>]. You have one tool, recall, which returns the exact removed text for an id. Use it when an answer depends on removed text; do not recall text you do not need. Answer each numbered question from the context and anything you recalled. Be specific: give exact paths, names, values and commands as they appear. If you still cannot tell, write "unknown" instead of guessing.
```

## Gold location (computed before any answer, from `C`, `C'` and the gold only)

For each probe gold feature (artifact paths, the recall target, the decision quote, the continuation target),
mark it:
- **in_view**: it occurs verbatim in `C'` outside stashed markers;
- **stash_only**: it occurs in `C` but in `C'` only inside one or more stashed results (list their stash ids);
- **neither**: not found in `C'` and not in a stashed blob (should not happen for gold that came from `C`; counted).

A probe is **stash-dependent** if at least one of its gold features is `stash_only` and none of its gold features is
`in_view`. Counts per type are committed in `location-receipt.json` before any arm runs.

## Metrics

**Recall behaviour (`stashed_t`, from the shim log):**
- **R1 needed-recall rate** (primary behaviour metric): over stash-dependent probes, the fraction for which the
  answer's call log holds at least one recall of a stash id that contains that probe's gold.
- R2 recall precision: of all recall calls, the fraction whose blob contains any gold feature of the item.
- R3 recalls per item (mean, median, share of items with 0) and the share hitting the 8-call cap.
- R4 recalled tokens as a share of the item's stashed tokens.
- R5 effective context: tokens of `C'` plus recalled tokens, as a median ratio to `C`. This is the real cost.
- R6 errors: unknown ids, cap hits, denied tool attempts.
- In `full_t`: any recall call is a false call (nothing is stashed); counted.

**Task outcome (all arms):** as in probe-eval-v1: per-item artifact recall (mechanical), recall exact match,
hallucinated paths per item, and the blind Opus judge on six 0-5 dimensions. The judge mask is extended to the
stashed marker and to the word "recall". Each item's arm answers are shuffled with `random.Random(20261017)`.

## Hypotheses and pass criteria (declared before any answer)

**Validity gates.** If any fails, the run is *invalid* and no H verdict is given.
- V1: `full_t` mean artifact recall ≥ 0.50.
- V2: ≤ 10% of D items dropped for failures, refusals or verification voids (dropped from every arm).
- V3: at least 40 stash-dependent probes across types; below that, H2 and R1 are descriptive only.
- V4: the tool works: on the pilot, a scripted recall of a known id returns its bytes through the CLI path.

**H1 (primary, outcome, non-inferiority).** `stashed_t` is not worse than `full_t` on artifact recall.
- Paired cluster bootstrap over lineage groups, 2000 resamples, seed 20261017.
- **PASS iff the lower bound of the two-sided 95% CI of `stashed_t − full_t` is > −0.05.**
- Reported with R5 (effective tokens) next to it.

**H2 (primary, behaviour).** On stash-dependent probes, the tool helps: mechanical score (artifact recall for
artifact probes, exact match for recall probes) of `stashed_t − stashed_0` has a 95% CI lower bound > 0.

**Secondaries (CIs, no pass claim).**
- S1: R1-R6.
- S2: H1 on recall exact match and on the judge's six-dimension mean.
- S3: H1 restricted to stash-dependent probes (the hard case; expected to be the weakest).
- S4: hallucinated paths by arm.
- S5: breakdown by source (claude / codex / hermes) and probe type.
- S6: H1 on the rules-clean sensitivity subset defined in probe-eval-v1.

**Power (INFERIDO).** n = 172 in 75 groups; with a per-item SD of differences of 0.4 and design effect about 2,
the half-width of the 95% CI is about 0.085. A margin of −0.05 can therefore fail for lack of power even with no
true loss; the CI is reported either way.

## Leakage controls

| leak | control |
|---|---|
| Probes tuned to stashed | Probes were frozen on 2026-10-16, before `stashed` existed, from `C` and `W` only. |
| Prompt hinting the answer | Q-T names the marker and the tool only; it says nothing about which ids matter. |
| Cross-item recall | One stash dir per item; the shim refuses ids outside it. |
| Judge sees the arm | Markers, "recall" and tool traces are masked; answers shuffled; judge never sees `C'` or logs. |
| Recall log used as an outcome | R1 is behaviour only; outcome metrics read the answer text alone. |
| Tuning on D | Pilot on ≤ 10 TRAIN items (probe-eval-v1 pilot pool, same exclusions); code fixes only. |
| Stashed rules tuned on these sessions | `stashed` reuses the `lossy` and `recoverable` rules, which were adjusted on recoverable-dev sets that may share sessions with D; S6 reports the clean subset. |

## Budget (owner approval required before the pilot)

Subscription route, $0 cash, hard cap **900 CLI calls** for this eval, separate from probe-eval-v1's 3 000.
- Pilot: 10 items × 3 arms + 10 judge ≈ 40.
- D answers: 172 × 3 = 516 (one CLI call each; tool turns run inside that call).
- D judge: 172 (one Opus call per item, all arms). Gemini agreement: about 17 (10% sample).
- Total ≈ 745, under the cap. Tool turns add tokens, not calls; R5 reports them.

Usage-limit stop: wait for the reset and resume from cache. Transport errors get 1 retry.

## Run order

1. This file committed as draft.
2. Owner approves the route and cap (dated line here).
   **Approved 2026-10-17 by the owner: subscription CLI, $0 cash, hard cap 900 calls; harness and pilot to run
   after probe-eval-v1 finishes** ("Aprovo a rota assinatura, $0, limite de 900 chamadas"). Probe-eval-v1 must have finished its own run first, so the
   two never compete for the subscription quota.
3. Harness: `research/stashed_recall_v1.py`, `research/recall_mcp_shim.py`, tests. Pilot on ≤ 10 TRAIN items.
4. Freeze amendment: sha256 of the harness, the shim, Q-T and the green test log.
5. Compact D with `stashed` at the pin, verify, compute gold locations, commit `location-receipt.json`.
6. Run arms, then judge and the Gemini sample.
7. Score: `RESULTS.md` and `results.json` (counts and aggregates only), `gateClaim` on the headline numbers.

```
PYTHONPATH=/Users/Master/.lcc/bench/lcc-4719fde/src:/Users/Master/Downloads/LCC-judge \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/Master/LCC/.venv/bin/python \
    -m research.stashed_recall_v1 {pilot|compact|locate|run --arm <arm>|judge|agree|score}
```

## Amendments

### Amendment 1 (2026-10-18): pilot findings, code fixes, and a count-only preview of D

**Pilot (10 TRAIN items, 42 subscription calls, 0 dropped).** Code check only; no number below is a result.
- V4 (tool path) passes: through `claude -p` + the shim, Sonnet called `recall` once and returned the exact bytes.
- `stashed` cut pilot context from 529 881 to 400 960 tokens (−24%), 0 verification violations.
- `stashed_t` made **0 recall calls** on all 10 items; the pilot also had **0 stash-dependent probes**.
- One usage-limit stop (429) mid-run; resumed from cache after the reset, as the protocol says.
- Pilot gold predates probe-eval-v1 Amendment 1 (URLs in artifact gold), so its artifact scores are not comparable.

**Code fixes (no text, gold rule or criterion changed).**
1. zsh did not word-split a command variable in the run script; no call was spent.
2. Answers now record envelope facts: turns, permission denials, input/output tokens (`_turns`, `_denials`,
   `_in_tokens`, `_out_tokens`). They prove the tool was reachable when no recall happens, and give R5 its real
   token cost. They are never used as an outcome.

**Deviation, disclosed: D compacted and located before the freeze (Run order step 5 ahead of step 4).** Because
the pilot showed zero stash-dependent probes, the `stashed` compaction and the gold-location counts were run on D
(offline, no model call, no answer) into a separate private dir (`D-preview/`), to know whether V3 can pass.
Counts seen, nothing else:
- `stashed` on D: 9 398 654 → 5 961 815 tokens (**−36.6%**), 2 144 results stashed, 0 violations, 172/172 ok.
- Stash-dependent probes: **19 in 15 items** (artifact 2, recall 14, continuation 1, decision 2). Gold features:
  1 086 in view, 72 stash-only, 57 neither.
- So **V3 (≥ 40 stash-dependent probes) will fail as written**: H2 and R1 would be descriptive only. H1 (outcome
  non-inferiority) is unaffected.

The D-preview outputs are not reused by the D run; step 5 recompacts into the D dir after the freeze.

### Amendment 2 (2026-10-18): stash probes

**Approved 2026-10-18 by the owner: stash probes, cap raised to 1 100 calls** ("Aprovo a Emenda 2: stash probes e
limite de 1.100 chamadas. Pode congelar o harness e rodar o D."). Implementation details fixed before the freeze:
- feature extraction is `nal.features` unchanged (its own minimum lengths apply); kind `line` is not used;
- the generator gets `recall_target`, `recall_excerpts` (probe-eval-v1 `recall_excerpts` over `C`) and
  `next_request`; `earlier_context_excerpt` and `what_the_agent_did_next` are empty strings, and any decision it
  returns is ignored;
- a target that fails the leak check gets one regeneration with the next-ranked candidate, then is dropped;
- the stash probe is asked as the **last** numbered question in the same answer call, in all three arms alike;
- stash probes are scored mechanically only and are not sent to the judge;
- H2 and R1 are computed on the stash-probe stratum; the 19 stash-dependent original probes stay descriptive.

Original proposal text:

To measure recall behaviour with power, add one probe per D item whose gold lives only in that item's stash:
- **Target:** one feature of kind hex > num > ident > quoted (probe-eval-v1 `KIND_RANK`, `nal.features`) that
  occurs in a stashed blob of the item and nowhere in `C'` outside markers nor in `P`; ties broken by
  `random.Random(20261018)` over sorted values. Items with no such feature get no stash probe (counted).
- **Question:** written by Claude Opus 5.5 with the frozen G text's RECALL part, from the ±600 chars around the
  target in `C` only (the generator never sees `C'`, arms or answers). Same leak check as recall probes.
- **Scored** by exact match, like recall probes; these probes are analysed as their own stratum (H2 and R1 move to
  it), never pooled into H1.
- **Cost:** about 172 more Opus calls → raise the cap from 900 to **1 100** (42 used so far).
- Limit, stated now: stash probes ask about content the agent did not necessarily use next, so they measure
  "can it get removed content back when asked", not "did it need it".

### Amendment 3 (2026-10-18): harness freeze

From this commit on, no code, prompt or criterion changes; a change found necessary voids the run, and that run's
results are still published. Every non-pilot phase checks probe-eval-v1's frozen files and every `path` / sha256
pair below (`stashed_recall_v1.own_frozen`). Q-T is frozen at sha256
`9331ffd9330871359bf60cdb75252f1def6bac9547f3dcbc64a38b368465de38`. No D answer, D stash probe or D judge output
existed when this was committed (only the count-only D preview of Amendment 1).

| frozen file | sha256 |
|---|---|
| `research/stashed_recall_v1.py` | `2e4cfca7f897358efb301a8ed7b397db5299fc02fd4299be52694d52e52817db` |
| `research/recall_mcp_shim.py` | `bcc5e01dca3316fd0d619c5f5f599adc4d17c904fa0530c2515f3d6b67cf8ffb` |
| `tests/test_stashed_recall_v1.py` | `9af94a3d510b469cad19d28b8c587070bd6f706577d32403f7d3424687f1ec83` |
| `research/goal-engine-2026-10-04/stashed-recall-v1/harness-tests.log` (19 passed) | `558fc69d463ccc3db39c0b59fdc43b63f769fb03855ce338fcf20fcef4a47467` |

Pilot spend at freeze: 51 subscription calls (the stash-probe pilot and one re-answer included).
