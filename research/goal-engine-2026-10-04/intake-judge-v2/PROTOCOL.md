# Intake judge v2: pre-registered protocol

Written on 2026-10-23, before any v2 label, model or score exists, and before any prompt from the new
held-out period has been written (the period starts tomorrow). Owner decisions taken on 2026-10-23: v2
sees the agent's previous turn; a shrunk multilingual static-embedding model is a candidate.

## Why v2

v1 (lcc#124) beats keyword rules (0.509 vs 0.224) but trails Opus (0.862). It fails most on short replies
whose meaning sits in the agent's previous turn: "commit that" read as approval, "this is wrong" read as a
revision, facts read as failures (`intake-judge-v1/RESULTS.md`). v2 tests two fixes: give the model that
turn, and give it word meaning (static embeddings) instead of character shapes only.

## Data

- **Import:** `research/import_agent_requests.py run --with-prev` into `~/.lcc/intake-v2/` (same salt).
  Each record gains `prev_agent`: the last 600 characters of the agent's text before the prompt, redacted
  with the same rules. The previous turn joins the dedupe key, so "sim" after two different proposals is
  two requests. Only Claude Code and Hermes stores expose that turn; other sources have none.
- **Counts at writing:** 4,593 prompts, 3,466 with a previous turn (claude 1,974 of 2,185; hermes 1,492 of
  1,864); 0 prompts on or after 2026-10-24.
- **Held-out:** sessions whose first prompt is on or after **2026-10-24T00:00Z**. Built once, on the first
  day the count shows at least 100 such sessions with at least one prompt that has a previous turn. If
  that is not reached by 2026-11-30, it is built then if at least 60 sessions qualify; otherwise an
  amendment decides.
- **Train/dev:** every session that started before the cutoff. Dev is 20% of session groups,
  `random.Random(20261024)` over sorted session hashes. The sessions of the v1 owner-gold items are forced
  into dev (below).
- **Owner-dev:** the 116 v1 held-out items both owner passes agreed on, matched to v2 records by source,
  timestamp and prompt text. They were labelled from prompt text alone; they are a dev check, not a test.

## Teacher

- Claude Opus 5.5, same CLI and safety rules as v1. Each request is shown as the agent's previous turn (if
  any) followed by the prompt; the system prompt adds one sentence saying the previous turn is context and
  the category is about the user's request.
- Cap: 3,500 CLI calls in all, final-test arm included.
- **Stop rule:** teacher accuracy on owner-dev at least 0.75, else stop and amend before training.

## Candidates (fixed grid, 9 configs)

All are multinomial logistic regression, class-balanced, trained with `research/intake_v1.py:fit`
(full-batch Adam, 400 steps).

| family | features | C |
|---|---|---|
| A: text | v1 features of the prompt | 3, 10, 30 |
| B: text + previous turn | v1 features of the prompt; the same featuriser on the previous turn in its own hash namespace; each block L2-normalised on its own | 3, 10, 30 |
| E: embeddings | mean static embedding of the prompt (64 dims) and of the previous turn (64 dims, zeros when absent), plus a has-previous-turn flag | 1, 10 |
| H: hybrid | B's features plus E's dense features | 10 |

**Shrinking the embedding model, fixed now:**
- Source: `minishlab/potion-multilingual-128M` at commit `73908c3438cf03b6a01bcb9611d62b23d0726f08`
  (MIT; a static distillation of BAAI/bge-m3, 256 dims). Downloaded files are hashed in the freeze
  receipt.
- Vocabulary kept: every token id that occurs in any train or dev text (prompt or previous turn) under the
  model's own tokenizer. Tokens outside it are ignored at inference.
- PCA to 64 dims, fitted on the kept rows, stored as float16.
- The tokenizer (`tokenizer.json`, 18.6 MB) is used unchanged and needs the `tokenizers` library.

## Budgets (measured on dev, fresh process, 1 thread)

- **A/B:** median at most 5 ms and p90 at most 20 ms per prompt, model at most 2 MB, peak RSS at most
  100 MB. Stdlib only.
- **E/H:** median at most 5 ms and p90 at most 20 ms, all files together at most 30 MB, peak RSS at most
  150 MB. Needs numpy and `tokenizers`, as an optional LCC extra.

## Selection (dev only)

1. **Eligible:** within its family budget, and owner-dev accuracy at least 0.509 (v1's held-out score on
   those same items).
2. **Pick:** the highest dev macro-F1 against teacher labels among eligible configs. Ties go to the smaller
   total file size.
3. **Fallback pick:** the best eligible A/B config, by the same rule. LCC needs it where `tokenizers` is
   not installed. If the pick is itself A/B, the fallback is the pick.
4. **Display threshold** for each pick: the lowest probability cut with at least 0.80 dev accuracy, as in
   lcc#124.
5. **Freeze receipt** (`FREEZE.json`, pushed before the held-out sample is drawn): hashes of models, code,
   embedding files and teacher prompt; the dev table for all 9 configs.

## Held-out gold (owner)

- **Sample:** 150 primary held-out prompts, at most 2 per session, seeded `random.Random(20261024)`. A prompt
  whose prompt and previous turn exactly match a train/dev record is reported and excluded.
- **Page:** shows the agent's previous turn (if any) above the prompt, and nothing from any model.
- **Two passes,** at least 24 hours apart.
  - **Primary gold:** items both passes label alike.
  - **Sensitivity views:** each pass alone.
  - "Unsure" in either pass excludes the item from the primary gold.

## Arms (one run)

- v2 pick.
- v2 fallback (if different).
- v1 as shipped in lcc#124 (prompt only).
- Keyword rules.
- Majority class.
- Opus 5.5 with the previous turn (the teacher prompt).

## Acceptance (primary gold; paired session-group bootstrap, 2000 resamples, seed 20261024, 95% CI)

1. **Replaces v1:** v2 pick minus v1 has an accuracy CI lower bound above 0. The same check is run for the
   fallback, which may replace v1 on installs without `tokenizers` only if it passes on its own.
2. **Beats rules:** v2 pick minus keyword has CI lower bounds above 0 for accuracy and macro-F1.
3. **Cost:** the pick's family budget, re-measured on the gold prompts.
4. **Close to Opus:** a label only, not a gate. v2 minus Opus accuracy, CI lower bound above −0.10.

**Ship rule:**
- If 1–3 pass, the pick replaces v1 in LCC. LCC's intake gains an optional `previous_turn` input; without
  it, the models run with no previous turn, as they did for sources that lack one.
- An E/H pick ships as an optional extra over the fallback.
- Otherwise v1 stays, and the result is recorded in `research/failures.md`.

## Stated before the run

- The teacher sees the previous turn; owner-dev labels did not. Owner-dev is a guard, not a measure of the
  new task.
- The held-out leans on Claude Code. The previous turn exists only for Claude Code and Hermes.
- The embedding vocabulary is pruned to train/dev tokens, so new words in the held-out are ignored. This
  favours n-grams on new vocabulary; it is the price of a small file.
- Results are INFERIDO: one owner, one machine. Counts are MEDIDO.
