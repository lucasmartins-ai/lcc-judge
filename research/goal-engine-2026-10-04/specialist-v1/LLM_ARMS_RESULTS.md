# Generalist LLM arms vs specialist v3 — 2026-10-13

Exploratory (INFERIDO). Owner-approved substitute for a paid Jev run: Claude Opus 5.5 via `claude -p`
(claude.ai subscription login, ANTHROPIC_* env stripped, no settings/CLAUDE.md, no tools) and Gemini 3.8
Flash (High) via `agy` (plan mode, sandbox). Same keep question, clipping and 8-block / 12000-char batches as
the Jev block arm (`research/llm_judge_arm.py`). No dollar spend; subscription quota only. Counts only;
per-item scores stay in `~/.lcc/bench/llm-arms/`.

## Edge suite (35 synthetic cases, single-author gold), passed at 30 / 50 / 70% cut

| Arm | 30% | 50% | 70% | Calls |
|---|---:|---:|---:|---:|
| Claude Opus 5.5 | 35 | 35 | 35 | 373 (+3 smoke) |
| Gemini 3.8 Flash (High) | 35 | 35 | 34 | 375 |
| specialist v3 | 28 | 23 | 20 | — |
| best non-LLM local arm | 24 | 21 | 18 | — |

Scoring sanity check on the Opus scores: shuffled within item 13/10/3 and 16/12/8 (two seeds), inverted
0/0/0. No unscored blocks (0 of 2,909), 0 failed calls in either arm.

## Real sessions: first 10 jev-overlap items (dev split), next-action evidence labels

| Arm | recall AUC | all-kept AUC |
|---|---:|---:|
| specialist v3 | 0.950 | 0.592 |
| Claude Opus 5.5 | 0.910 | 0.467 |
| Jev (saved scores) | 0.838 | 0.408 |
| BM25 | 0.829 | 0.300 |
| recency | 0.736 | 0.267 |
| mechanical | 0.743 | 0.167 |
| random | 0.717 | 0.185 |

376 Opus calls, 0 failures, no limit hit. Gemini was not run on real sessions.

## Reading

- On synthetic edge cases (supersession, contradiction, coreference), the generalists beat v3 by a wide
  margin. Those cases need reading comprehension that v3's lexical/positional features don't carry.
- On real sessions, v3 ranks above Opus and Jev. The labels measure what the agent reused next, which is
  what v3 was trained to predict; Opus judges generic relevance.

## Limits

- n = 10, no CIs. These items are in the dev split, which was used to select v3's floor (optimistic for v3).
- The edge gold is single-author, and v3's floor was selected using the edge suite.
- Proof requires the post-2026-10-12 held-out set (`research/heldout_v3.py`), which has 0 qualifying
  sessions as of this writing.

## Next

Targeted distillation: Opus labels for supersession / contradiction / coreference situations in train
sessions only, used as extra training signal for the local specialist. Then the frozen comparison on the new
held-out set with v3/v4, Opus and Gemini.
