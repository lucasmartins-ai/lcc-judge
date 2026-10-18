# Specialist v5: deterministic edge detectors + cascade (results)

Produced by `python -m research.specialist_v5 select` and `final` on 2026-10-18 under `V5_SELECTION_RULE.md`
(committed in 22b8d21 before any dev scoring; Amendment 1 in 33089dd before the sealed set was opened).
Counts and aggregates only, no session text. Machine-readable: `v5-dev-results.json`, `v5-sealed-results.json`,
`v5-teacher-agreement.json`, `v5-dev-diagnostic.json`, `v5-bench.json`, `edge-v2-receipt.json`.

## Bottom line

- **v5 is not adopted.** Every config fails the pre-declared dev non-inferiority step: recall -0.0033
  [-0.0070, -0.0009], all-kept -0.0051 [-0.0100, -0.0016] (lower bounds below -0.005). v3 stays shipped.
- **The detectors generalise to new edge cases.** On the sealed edge v2 (49 cases, opened once), v5 passes
  35/30/20 at 30/50/70% vs v3 26/19/10 and BM25 32/22/14. Opus passes 49/49/47, so most of the gap to a
  generalist remains.
- **Where the dev cost comes from (diagnostic, after the decision):** almost all of it is `user_directive`
  (protecting short user rule / correction / "fyi" turns). Without it, dev is -0.0004 recall / -0.0015
  all-kept, but most of the edge gain goes too. The next-action labels count a block as used when the agent
  reuses its content next; a rule the agent obeys is rarely "reused", so this metric penalises keeping rules by
  construction (INFERIDO).
- **Latency budget not met under load.** v5 runs about 1.7x v3 per item (v3 itself measured 327-485 ms median
  with load average 65-178, vs 178 ms in the quiet v3 final test). Estimated quiet median about 300 ms > 250 ms
  (INFERIDO). Peak RSS 126-147 MB and model 183 KB are within budget.

## Edge suite v2 (step A)

- 130 cases written by Claude Opus 5.5 (`research/edge_v2.py`, one CLI call each), 130 passed the mechanical
  checks (schema, gold ids, gold not trivially the largest or the most recent block, must share <= 30%, no
  secret-shaped strings). Same fixture schema as v1, plus `edge_type`, `lang`, `harness`.
- Seeded split per edge type: 81 dev-edge (`tests/fixtures/edge_cases_v2/`) and 49 sealed (private; sha256 per
  case + directory hash in `edge-v2-receipt.json`, committed in d24c195 before any detector work).

| edge type | dev | sealed |
|---|---:|---:|
| contradiction | 7 | 4 |
| structured_config | 7 | 4 |
| source_authority | 7 | 4 |
| qualifier_exception | 7 | 5 |
| pt_en_mixed | 7 | 4 |
| git_wide_view | 7 | 4 |
| prompt_injection | 7 | 4 |
| supersession | 7 | 4 |
| coreference | 7 | 4 |
| general | 18 | 12 |

- Owner review: `edge-v2-review.csv` (20 seeded dev-edge cases, plain pt-BR, columns ok / errado / comentario).
  **Review pending.** The gold is Opus-authored and not owner-confirmed.

## Detectors (step 1) and cascade (step 2)

`research/specialist_v5.py`. Score = frozen v3 score + bonus for blocks a detector protects. Text + LCC's
structured metadata only (message index, role, kind, tool). Blocks over 1,000 chars get no bonus.

- **Stage 1 (every block):** `user_directive` (rule / exception / correction / authority markers in user turns,
  3 most recent), `goal_xling` (goal match after a pt<->en glossary of 234 entries, identifier splitting and
  5-char stems; weak bonus), `translated_only` (matches the goal only through the other language),
  `git_state` (first + latest git status for a commit / push goal), `convention` (AGENTS.md / "## Commits",
  skipping legacy / outdated docs), `wide_doc`, `ordinal_ref` ("o segundo", "option 2": the enumerated block
  that best matches the goal), `said_ref` ("do jeito que voce falou"), `other_env` (prod goal: demote
  staging-only blocks).
- **Flag only (no score change):** `injection` (instruction-shaped text in a tool output: the block stays as
  evidence and never counts as a rule), `hedge`, `stale`. Hedge and stale demotion cost train-sample AUC with
  no dev-edge gain, so they were switched off.
- **Stage 2 (cascade):** only for blocks inside the lowest 70% of tokens after stage 1: `value_conflict` (same
  quantity, by unit class or config key, with different values in two goal-related lines about the same
  subject) and `qualifier_link` (the tool output that carries the condition a recent user exception names).
  Stage 2 adds +2 / +2 dev-edge passes at 50 / 70% over stage 1 only (b3).

## System-1 teacher (step 3)

`research/teacher_v5.py`: 4 tiny questions (pair conflict, pair newer-version, goal reference -> block, block
flags {directive, qualifier, guess, injection}) on candidates chosen by loose heuristics from 300 TRAIN items
and from dev-edge. 1,845 questions in 155 calls (about 12 per call). Answers tuned patterns only; they were never
a relevance target. Detector vs Opus (recall is relative to the loose candidate pools):

| detector | dev-edge P / R (n) | train P / R (n) |
|---|---|---|
| user_directive | 0.95 / 0.73 (141) | 0.70 / 0.79 (500) |
| qualifier marker | 0.61 / 0.73 (141) | 0.61 / 0.54 (500) |
| hedge | 0.93 / 0.93 (89) | 0.79 / 0.97 (200) |
| injection | 1.00 / 1.00 (157) | 0.00 / 0.00 (302; Opus said yes on 15, mostly the owner's own prompt templates and test strings; detector flagged 1) |
| value_conflict | 0.85 / 0.37 (102) | 0.00 (9 flagged, 2 real of 152) |
| ordinal / said ref | 0.31 / 0.38 (91) | - (2 positives) |

Tuning from these answers: English "important", "ignore", "nao vai" dropped from the directive pattern; the
injection pattern ignores matches next to regex / guard / pattern text; fact lines from JSON, HTML, timings,
test progress and git logs no longer count; conflicts need the same subject (>= 2 shared stems) and 2-4
holders. Real conflicts are rare in real sessions (2 of 152 candidate pairs), so `value_conflict` precision on
train stays poor.

## Selection on dev (step D, 325 items, full-text scoring)

Paired group bootstrap, 2000 resamples of 107 groups, seed 20261018. v3: recall AUC 0.8872, all-kept 0.4446.

| config | recall | all-kept | recall vs v3 | all-kept vs v3 | old edge 30/50/70 | dev-edge 30/50/70 | eligible |
|---|---|---|---|---|---|---|---|
| v3 | 0.8872 | 0.4446 | - | - | 28/23/20 | 41/23/11 | control |
| b2, stage 1 | 0.8840 | 0.4395 | -0.0032 [-0.0069, -0.0009] | -0.0051 [-0.0100, -0.0016] | 31/28/25 | 63/44/21 | no (dev) |
| b2, stage 1+2 | 0.8840 | 0.4395 | -0.0032 [-0.0069, -0.0009] | -0.0051 [-0.0100, -0.0016] | 31/28/25 | 63/46/22 | no (dev) |
| b3, stage 1 | 0.8840 | 0.4395 | -0.0033 [-0.0070, -0.0009] | -0.0051 [-0.0100, -0.0016] | 32/30/27 | 64/46/23 | no (dev) |
| b3, stage 1+2 | 0.8839 | 0.4395 | -0.0033 [-0.0070, -0.0009] | -0.0051 [-0.0100, -0.0016] | 32/30/27 | 64/48/25 | no (dev) |

Dev-edge v2 per type, passes at 30/50/70% (v3 -> v5 b3 stage 1+2):

| type | n | v3 | v5 |
|---|---:|---|---|
| contradiction | 7 | 3/3/1 | 4/3/1 |
| coreference | 7 | 3/3/0 | 7/4/1 |
| general | 18 | 14/9/5 | 16/14/9 |
| git_wide_view | 7 | 2/1/1 | 7/6/6 |
| prompt_injection | 7 | 2/1/0 | 5/3/0 |
| pt_en_mixed | 7 | 5/1/1 | 4/3/2 |
| qualifier_exception | 7 | 2/1/1 | 6/5/3 |
| source_authority | 7 | 3/0/0 | 5/1/0 |
| structured_config | 7 | 3/2/1 | 4/4/1 |
| supersession | 7 | 4/2/1 | 6/5/2 |

Old suite (35), per category at 30/50/70%, v3 -> b3: git_ship 1/0/0 -> 1/1/1, project_audit_or_direction
0/0/0 -> 2/2/2, environment_and_infra 3/2/2 -> 4/4/3, external_accounts_and_comms 3/1/1 -> 3/2/2,
task_status_or_control 3/3/2 -> 4/4/3, revise_recent_output 2/2/1 -> 2/2/2; no category lost a pass. Still failing at 50%: coreference_cause, handoff_prompt,
prompt_injection_in_tool_output, pt_en_mixed, qualifier_exception. Old pt_en_mixed fails at every cut:
`translated_only` protects `cart.ts` but takes only the top block, and `shipping.ts` also matches only through
English ("shippingFee"). Taking the top 2 would likely fix it. Not changed, because the sealed set was already
spent.

## Sealed edge v2 (opened once; Amendment 1 config b3, stage 1+2)

| arm | 30% | 50% | 70% |
|---|---:|---:|---:|
| Claude Opus 5.5 | 49 | 49 | 47 |
| **v5 (b3, stage 1+2)** | **35** | **30** | **20** |
| BM25 | 32 | 22 | 14 |
| v3 | 26 | 19 | 10 |
| recency | 19 | 4 | 0 |
| oracle | 49 | 49 | 49 |

Per type, passes at 30/50/70% (v3 / v5 / Opus):

| type | n | v3 | v5 | Opus |
|---|---:|---|---|---|
| contradiction | 4 | 1/1/0 | 1/1/0 | 4/4/3 |
| coreference | 4 | 1/0/0 | 2/1/1 | 4/4/4 |
| general | 12 | 10/8/5 | 10/9/6 | 12/12/12 |
| git_wide_view | 4 | 1/0/0 | 1/1/1 | 4/4/4 |
| prompt_injection | 4 | 3/2/1 | 3/3/1 | 4/4/4 |
| pt_en_mixed | 4 | 3/3/2 | 3/3/2 | 4/4/4 |
| qualifier_exception | 5 | 2/1/0 | 4/4/2 | 5/5/5 |
| source_authority | 4 | 1/1/0 | 3/2/1 | 4/4/4 |
| structured_config | 4 | 3/2/2 | 4/3/3 | 4/4/3 |
| supersession | 4 | 1/1/0 | 4/3/3 | 4/4/4 |

Reading (INFERIDO): the gain holds on unseen cases of the same kind: +11 passes at 50% (19 -> 30), and v5 now
beats BM25 at every cut, where v3 did not. Contradiction and pt/en did not improve on sealed. The sealed cases
come from the same generator and prompt as dev-edge, so this measures generalisation to new synthetic cases,
not to real sessions. n = 4-5 per type.

## Budgets

| run (325 dev items, fresh process, 1 thread) | v5 ms median | v3 ms median | v5 p90 | v5 peak RSS MB | model KB | load avg |
|---|---:|---:|---:|---:|---:|---:|
| run 1 | 680.9 | 327.2 | 2338 | 146.6 | 183 | 176-178 |
| run 2 (after a behaviour-identical speed-up of `fold`, injection pre-filter, digit check) | 812.5 | 485.2 | 2306 | 126.5 | 183 | 65-77 |

Behaviour-identical: detector flags compared on 416 items (dev-edge, old suite, train sample), 0 differences.
The machine was heavily loaded, so absolute latency is not comparable with the v3 final test (178 ms). The
ratio is the usable number: v5 / v3 = 2.1 then 1.7. At 1.7x the quiet v3 figure, v5 would be about 300 ms,
over the 250 ms budget.

## Opus calls

528 CLI calls out of the 1,500 cap, all through `research/opus_cli.py` (ledger, cap, cache, ANTHROPIC_*
stripped, no tools):
- 130 generation;
- 1 pt-BR review text;
- 155 teacher (50 dev-edge, 105 train);
- 242 sealed final.

There were no usage-limit stops, retries or failures inside the runs. (The session itself paused for a
subscription reset between the train-sample work and the teacher run; no call was in flight.)

## What the LCC provider port would need (if a later version passes)

- Inputs are already what LCC PR #50 passes: block text plus message index, role, kind and tool. The detectors
  read role and kind only from those fields, never from block text.
- Return per-block flags (`Judge.flags`) next to the scores, so LCC can annotate `injection` blocks as
  untrusted evidence without dropping them.
- Better split (diagnostic): protect short user directive turns at the LCC level, as LCC already protects some
  blocks, and keep the judge's score for the rest. The dev metric cannot see that protection, because it
  excludes protected blocks from candidates. It needs an outcome measure (MSI-style) instead.
- Latency: the detectors need about 0.7x v3's time again. Before a port, cut it by computing stems once (shared
  with s2.featurize) and skipping stage 2 when stage 1 already keeps every candidate.

## Limits

- Edge gold is Opus-authored (dev and sealed) and not owner-confirmed. The old suite is single-author.
- Dev-edge, the old suite, the 300-item train sample and the teacher answers were all used for design.
- `v5-dev-diagnostic.json` (per-detector ablation on dev) was computed after the decision. It is for the next
  cycle's design, and it means dev is no longer clean for detector selection.
- The latency numbers come from a shared, heavily loaded machine.
