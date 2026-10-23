# Intake judge v1: pre-registered protocol

Written on 2026-10-23, before any training label was produced, any model was fit, or any post-cutoff prompt
was read. The only look at post-cutoff data so far is a count (below), made on a temporary import that was
deleted afterwards. Owner decisions taken on 2026-10-23: the owner hand-labels the held-out gold; Opus is the
training teacher through the subscription CLI.

## Question

Can a small local model put an incoming owner prompt into the 13 request categories of
`request-taxonomy-v1/taxonomy-v2.json` (plus UNKNOWN) accurately enough for LCC's intake to use, at a cost
that fits a check on every prompt? Today `lcc.intake.parse_intake` (lcc `f9cac12`, #105) has no category at
all: readiness comes from regex rules, and the brief holds only text copied from the input.

Why a category: taxonomy v2 defines, per category, the context the agent needs (the agent's last turn for
`approve_or_pick`, the pasted error for `failure_report`, git state for `git_ship`, ...). A category lets
intake name a missing piece ("failure report without the error text") and lets compaction know what to
protect, without rewriting the user's text.

Out of scope for v1: readiness / "needs clarification". It needs an outcome label (did the agent have to
ask, did the owner correct course) that this repo does not have yet. v1 does not change readiness.

## Data

- **Source:** the owner's own agent prompts, through `research/import_agent_requests.py`. Redacted text only,
  stored under `~/.lcc/`, never committed. This repo gets counts, ids and hashes.
- **Re-import first.** LCC's redaction rules changed after the 2026-10-08 import (the importer refuses to
  append to the old files). v1 imports everything again with the current rules into a new base,
  `~/.lcc/intake-v1/`, reusing `~/.lcc/request-log/.salt`. The old files are kept untouched. The ruleset
  sha256 is recorded in the build receipt.
- **Cutoff 2026-10-09T00:00Z** (the day taxonomy v2 was confirmed). A session belongs to the **held-out**
  pool if its first imported prompt is at or after the cutoff; every other session with timestamps belongs
  to **train/dev**. Records with no timestamp (mostly Cursor) go to train/dev only.
- **Count at writing (temporary import, then deleted):** 1,311 prompts at or after the cutoff in 157
  sessions (claude 1,219 / 130, hermes 83 / 23, codex 9 / 4); pt 1,055, en 248. Codex history before
  2026-10 is mostly gone from disk; the train pool will lean on Claude and Hermes.
- **Text-linked items:** a held-out prompt whose normalised text (lowercase, whitespace collapsed) equals a
  train/dev prompt is reported separately ("seen text") and left out of the primary metrics. Short replies
  like "sim" repeat across sessions, so this count is reported, not hidden.
- **Label input:** labels, teacher and model see the prompt text alone, as the 2026-10-09 taxonomy labels
  did. Some categories (`approve_or_pick`, `supply_fact_or_step_done`) depend on the agent's previous turn;
  that ceiling is the same for every arm and is stated in the results.

## Teacher (training labels)

- Claude Opus 5.5 through `claude -p --model opus --tools ""` (subscription; the `llm_judge_arm.py`
  safety rules: tools disabled, no permission bypass, `ANTHROPIC_*` env stripped).
- One short question per prompt, batched up to 20 prompts per call: the taxonomy-v2 definitions and
  decision rules, then "answer one category id per prompt". No free-text relevance judgement.
- Cap: 3,500 CLI calls in all. On a usage-limit stop the run waits for the reset and resumes from cache.
- **Teacher check (stop rule):** before training, the teacher labels the 83 owner-judged items from
  taxonomy v1/v2 review (`owner-review-score*.json` ids, matched to the new import by source and
  timestamp; unmatched ids are reported). If teacher agreement with the owner is below **0.75**, v1 stops
  and the taxonomy prompt is revised in an amendment before anything else is run.
- Teacher labels are never shown for held-out prompts during development.

## Model and selection (train/dev only)

- Split train/dev by session group: 80/20, `random.Random(20261023)` over sorted session hashes.
- Model: hashed word 1–2-gram + char 2–5-gram features, multinomial logistic regression. Trained with
  scikit-learn offline; exported as JSON weights; inference in pure Python (no numpy needed), so LCC can
  vendor it like `specialist_v3.json`.
- **Fixed grid (6 configs):** features in {char only, char + word} x C in {0.3, 1, 3}.
- **Pick:** highest dev macro-F1 against teacher labels; ties go to the smaller model file.
- **Freeze receipt** (`FREEZE.json`, committed and pushed before the held-out sample is drawn): sha256 of the
  model, the inference code, the keyword baseline, the teacher prompt and the evaluation script; dev numbers
  of every config.

## Keyword baseline

A hand-written rule classifier (`research/intake_keywords.py`): cue lists per category (error words and
stack-trace shapes for `failure_report`, `commit`/`push`/`PR` for `git_ship`, short yes/no/option replies for
`approve_or_pick`, ...), first match wins, else `specified_task`. Written from the taxonomy definitions and
train/dev prompts only, hashed in the freeze receipt. It stands for "what a regex intake can do", the
current approach in LCC.

## Held-out gold (owner)

- Drawn after the freeze receipt is pushed: 150 primary held-out prompts, at most 2 per session,
  `random.Random(20261023)` over sorted ids within each session, then over sessions.
- A local review page (same mechanism as `research.request_taxonomy_review`) shows the prompt text and the
  14 category definitions. The owner picks one category or "unsure". No model, teacher or baseline output is
  shown. Labels stay in `~/.lcc/intake-v1/gold/`.
- "Unsure" items are counted and excluded. If fewer than 120 items remain, a second draw of the same rule
  tops the set up to 150, once.

## Arms on the gold set (one run)

- **intake judge v1** (the frozen pick).
- **Keyword baseline.**
- **Majority class** (the most frequent teacher label in train).
- **Claude Opus 5.5 zero-shot**, the teacher prompt itself: the reference for how much distilling costs.
  Counted inside the 3,500-call cap.

## Metrics and acceptance

- Accuracy and macro-F1 over the categories present in the gold set. Per-category precision/recall and the
  confusion matrix are reported, by language and by source.
- Paired bootstrap over session groups: 2000 resamples, seed 20261023, 95% CI on the per-item difference
  (accuracy) and on the resampled macro-F1 difference.

1. **Beats rules:** v1 minus keyword baseline, and v1 minus majority, have CI lower bounds above 0 for both
   accuracy and macro-F1.
2. **Close to the teacher:** v1 minus Opus on accuracy has a CI lower bound above **−0.10**. Reason for the
   margin, chosen now: v1 runs on every prompt locally in milliseconds; Opus needs a network call per prompt.
   A gap of up to 10 points is the price the owner accepts for that, and no more.
3. **Cost** (fresh process, 1 thread, on the gold prompts): median at most 5 ms per prompt, p90 at most 20 ms,
   model file at most 2 MB, peak RSS at most 100 MB.

**Ship rule.** If 1 and 3 pass, v1 goes to LCC as an additive field (`category` and `category_confidence`
in the intake result, plus the taxonomy's "context needed" note for that category). Readiness is not
changed. If 2 also passes, the results may say "close to Opus"; otherwise they say "beats rules, below Opus"
with the measured gap. If 1 fails, nothing ships and the result is kept in `research/failures.md`.

## Stated before the run

- Training labels come from Opus, and Opus is also an arm: v1 can at best approach it. Arm 2 measures the
  distillation loss, not independent skill.
- Single owner, single labelling pass, one machine. Results are tagged INFERIDO; counts are MEDIDO.
- Held-out sessions lean on Claude Code (130 of 157); Hermes and Codex numbers will have wide CIs.
- The owner's gold labels are from prompt text alone, so categories that need the agent's previous turn
  will show lower agreement for every arm.
- Each held-out set is used once. After the run, it is spent.
