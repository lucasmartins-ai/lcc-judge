# v5 cycle 2: can a ranker choose WHAT `stashed` removes, on tool outputs only? (pre-registered)

Written and committed on 2026-10-19 before any arm was scored on the dev items in this cycle's setup. Owner approval
in chat: "Sim, pode liberar o próximo ciclo do v5: avaliação só sobre saídas de ferramentas, ajuste pt-en e
otimização de tempo, com o stashed como base de comparação", plus a cache-cost requirement. Code:
`research/v5c2.py`. File hashes: `V5C2_PROTOCOL.json` (the run refuses nothing by itself; the hashes let a reader
check that the frozen files are the ones scored). Results will be tagged INFERIDO unless `gateClaim` passes.

## Why

The owner's live plugin runs provider `rules` with `rulesMode: stashed` (no model in the live path). In LCC's
tool-call mode, user and assistant text and call inputs never change; only tool results can be replaced. v5 cycle 1
failed dev because protecting short user rule turns cost AUC under next-action labels, and that protection is
irrelevant here: text is never removed. The question is narrower and closer to the product: **inside the same
safety envelope and at the same token budget, does ranking by v3 / v5 stash fewer of the tool outputs the agent goes
on to use than stashed's own rules, without costing more prompt cache?**

## Population

- **Dev split** of next-action v2 (`matched_budget_v2.eligible_dev`, 325 items, 107 session groups). The spent TEST
  split, the held-out v3 set and the sealed edge v2 are not used (refused / not opened).
- **Transcript rebuild** (private): each item's LCC blocks are mapped back to transcript content blocks through
  their `src` ranges (`v5c2.rebuild`); a block spanning several content blocks is cut at its inner render headers,
  which must number exactly `hi - lo`, else the item is excluded (`rebuild`, counted). Call ids are synthetic; each
  result pairs FIFO with the oldest open call of the same tool. Results with no open call are orphans (kept by every
  arm, outside the metric). Whitespace between blank-line-split pieces is normalised to one blank line.
- **Stashed run**: LCC pin `4719fde` (detached worktree `~/.lcc/bench/lcc-4719fde`, clean tree checked),
  `compact_transcript(provider='rules', rules_mode='stashed', question=goal)` with defaults (preserve_recent 6),
  no `workspace_root`, network guard on, stash to a private dir. `verify_stashed` violations or a runtime
  fail-safe exclude the item (`verify`, counted). The same payload is run with `rules_mode='lossy'` only to read
  each result's protection reason.
- **Metric blocks** = LCC candidate blocks (>= 40 chars) of kind `tool_result` that belong to a non-orphan result
  that LCC's lossless step did not dedupe. Dedupes apply identically to every arm and are left out.
- **Stash-safe pool** (what any arm may remove) = results that are not pinned, not deduped, not
  `short_result_kept_whole` (synthetic call ids are unique, so the duplicate-id rule never fires), and either stashed by `stashed` or not hard-protected by `lossy`
  (`lossy` keep reason `kept_default` or `trim_guard_*`; `latest_error_result`, `call_before_latest_error`,
  `latest_git_state`, `latest_task_state`, `latest_artifact_edit`, `latest_user_question`, `latest_tool_result`,
  `named_in_goal`, `named_in_recent_turns` stay kept by every arm).
- **Eligible item**: stash run ok, `stashed` removes > 0 tokens, and >= 1 USED metric block sits in the pool (only
  there can a choice differ). Other items are counted by reason, not scored.

## Arms

All arms remove whole results from the pool (LCC never cuts a stashed result).

| arm | how it chooses |
|---|---|
| `stashed` | LCC's own choice at its natural cut (decision `replace`). Its removed tokens = the item's budget B |
| `v3` | frozen specialist v3 (`~/.lcc/bench/specialist-v3/model.json`) |
| `v5c2` | frozen v5c2 model (below) |
| `v5c2_ct` | v5c2 with the cache-aware tie-break (below) |
| `recency`, `bm25`, `mechanical` | as in matched-budget v2 (block index; stdlib BM25 of the goal; LCC `_score_mechanically` + protection) |

Ranker arms score **every block of the item with its full text, as live** (`Judge.score(goal, texts)`); a result's
score is the **max** over its blocks. Matched budget: drop results lowest score first (ties: older first) until
removed tokens >= B. Tokens = LCC block tokens (gpt-4.1 heuristic), all blocks of a result.

**v5c2 (frozen before scoring; model sha256 in the json):** v5 cycle-1 b3_s12 (bonus 3, weak 0.25, cascade on,
max_chars 1000, off = stale, hedge) with two changes made on dev-edge / old suite / train sample only:
1. `translated_only` protects the top **2** translated matches (was top 1). Unit test
   `test_translated_top2_v5c2`. Effect on design data: old suite 32/30/27 -> 33/31/28 (the pt_en case), dev-edge v2
   unchanged (64/48/25), train-sample guard unchanged (recall -0.0013, all-kept +0.0017 vs v3).
2. Speed: `Judge.score` skips detectors that cannot change a score under `off` (injection, hedge; stale unless a
   prod goal lets it shadow `other_env`), and `facts` computes line stems only for lines holding a fact. Scores
   identical (0 differences on 416 items: 300 train, 81 dev-edge, 35 old suite); detector time 60.8 -> 35.4 s on
   those items. `Judge.flags` still returns every flag.

**Cache-aware tie-break (`v5c2_ct`, declared now):** results whose v5c2 scores fall in the same 0.5-logit bucket
(`floor(score / 0.5)`) drop the **later** result first, so the first mutation tends to sit later in the prefix.

## Metrics (per eligible item, then mean over items)

- **recall** = USED metric-block tokens kept / USED metric-block tokens (next-action v2 strict USED).
- **all_kept** = no USED metric block removed.
- **recall-at-stash**: number of USED results removed (each one is a later `recall` the agent would need) and the
  share of items with >= 1; also with `used_loose`.
- **Cache cost** (LCC compactor formula, factors read 0.10, write 1.25): `first_mutation_offset` = tokens of the
  whole context before the first removed block; `invalidated` = context tokens - offset; `dropped` = removed tokens
  - note tokens x removed results (note = LCC `stash_note`, counted with LCC's counter);
  `break_even_reuses` = invalidated x (1.25 - 0.10) / (dropped x 0.10). Reported per arm (median, sum). An arm that
  wins recall but invalidates more cache is reported as such.
- Removed tokens and removed result counts per arm (the budget is matched to within one result).

## Acceptance (per candidate: `v5c2`, `v5c2_ct`, `v3`)

A candidate replaces stashed's choice only if **all** hold:
1. **Non-inferior**: paired group bootstrap (2000 resamples over session groups, seed 20261019) of
   (arm - stashed) per item, 95% CI lower bound > -0.005 for **both** recall and all_kept;
2. **Superior on at least one**: CI lower bound > 0 for recall or all_kept;
3. **Cache**: median invalidated tokens <= 1.10 x stashed's median;
4. **Budget**: median latency <= 250 ms and peak RSS <= 300 MB on the dev items (fresh process, 1 thread, same
   method as v3 / v5; v3 re-measured in the same run; load average recorded).

If more than one candidate passes, the pick is the one with the highest recall, then the lower median invalidated
tokens. Three candidates are tested without a multiplicity correction; this is disclosed, not corrected.
Baselines (`recency`, `bm25`, `mechanical`) are reported for scale only.

## Descriptive only

- **Dev-edge v2 (tool-output gold)**: the 81 dev-edge cases restricted to those with >= 1 `tool_result` gold block
  (`must` or `one:`); only tool results are candidates; fixed cuts 30 / 50 / 70% of tool-output tokens; pass = every
  tool-result `must` kept and every `one:` group made only of tool results keeps one. Arms v3, v5c2, recency, bm25,
  mechanical. Dev-edge took part in v5's design, so these counts are not evidence. `stashed` is not run on the
  synthetic fixtures (no real call inputs or ids; its age rules need long sessions).
- Per-source split (claude / codex / hermes).

## Model calls

None planned. The cycle is local and deterministic. (Cap if ever needed: 500 Opus subscription CLI calls.)

## Disclosures and limits

- USED is next-action evidence (what the agent reused next without re-fetching), not a recall log. It is a proxy for
  "would have needed a recall".
- The dev split was read in v5 cycle 1 (selection and a post-decision per-detector ablation), so it is not clean for
  detector design; no detector was tuned on it in this cycle.
- The transcript rebuild approximates the original payload (synthetic ids, normalised blank lines); stashed's rules
  read sizes, ages, tools, inputs and text patterns, which the rebuild keeps.
- Latency is measured on a shared machine; the load average is reported next to it.
