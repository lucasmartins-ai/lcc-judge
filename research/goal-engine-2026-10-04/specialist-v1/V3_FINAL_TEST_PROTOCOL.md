# Specialist v3 final test: pre-registered protocol

Written and pushed on 2026-10-16, before the post-cutoff held-out set is built. The count at the time of
writing showed 25 qualifying sessions (claude 21, codex 1, hermes 3). It reported counts only; no
held-out item, text or label had been opened. No training, tuning or model choice happens after the build.

## Trigger and population

- Build once with `python -m research.heldout_v3 build`, on the first day the count shows >= 30 qualifying
  sessions. The builder refuses a second build (existing receipt).
- Eligible: held-out items with agent-action evidence and at least one USED candidate block.
- Primary: eligible items not content-linked to any train or dev item (the builder's check).

## What is frozen (sha256)

| File | sha256 |
|---|---|
| `~/.lcc/bench/specialist-v3/model.json` | `219cd798d47f39d18249597892c92f0772d7946ed59610d5b86b8500fa1b51f7` |
| `research/specialist_v3.py` | `fff2c201225627dd30348c8259190790c3a17b43e8d3abea63c460c67881a21e` |
| `research/specialist_v2.py` (features) | `6638809ed9b58c832ea6c36e22b88665b7857f8b2eb816dbc4935ee0c3ac01f9` |
| `research/llm_judge_arm.py` | `e203ec94c405db7f53dcc6023b4e27d8e29a91715fa9d87c7f45a5926d5e19ee` |
| `research/heldout_v3.py` | `ac6efb45755aff83b86edb40e0b938672d5ee54f80f8c4b5f716a87a8f243e0e` |

The only code allowed to change before the run is an evaluation script that reads these unchanged
modules, plus a `--set heldout` option in `llm_judge_arm.py` that only selects items. Any such change is
committed before the build, and its hash is recorded in the results.

## Arms

- **All primary items:** specialist v3 (shipped), recency, BM25, LCC mechanical, and random (mean of 5
  seeds).
- **LLM subset:**
  - Membership: one primary item per session, chosen with `random.Random(20261016)` over the item ids,
    sorted; at most 40 items in all, split evenly across sessions in sorted order.
  - Generalist arms: Claude Opus 5.5 and Gemini 3.8 Flash (High), both through `llm_judge_arm.py`.
  - Quota: these arms run on the subscription only. Each arm stops at 2,500 CLI calls.
  - Usage-limit stop: the run waits for the reset and resumes from cache, with no other retries.
  - Ties to a cap: if an arm cannot finish every subset item, the comparison uses only the items both
    arms finished, and the results report that count.
- Jev is not run, because it is paid. Its saved dev numbers stay descriptive only.

## Metrics

- **What is measured:**
  - Recall of USED tokens.
  - All-kept: every USED block kept.
- **How it is computed:**
  - Cut levels: 10–60% of candidate tokens removed.
  - AUC: trapezoid over 0–60% (0% = 1.0), normalised to 0–1.
- **How it is reported:** per source and per request category.
- **Paired bootstrap:**
  - 2000 resamples of session groups.
  - Seed 20261016.
  - The 95% CI is on mean(v3 − arm) of per-item AUC.

## Acceptance

1. **Local baselines** (primary items): v3 beats recency, BM25 and mechanical. The CI lower bound must be
   above 0 for both metrics against each of them.
2. **Generalists** (LLM subset): one verdict for each of Opus and Gemini, per metric.
   - **Superior:** the CI lower bound is above 0.
   - **Not inferior:** the lower bound is above −0.02.
   - **Inferior:** otherwise.
   - The headline claim "superior to a generalist" requires *superior* on recall and at least *not
     inferior* on all-kept.
3. **Cost** (primary items, fresh process, 1 thread): median at most 250 ms per item, p90 at most 1000 ms,
   and peak RSS at most 300 MB.

## Stated before the run

- The edge suite is not a gate. Its counts are already known: v3 28/23/20, Opus 35/35/35, Gemini
  35/35/34. The results repeat them, without re-running.
- Labels are rule-based next-action evidence, which favours what the agent reused. The generalists judge
  generic relevance, so this measures fit to the owner's sessions, not general reading skill. Results are
  tagged INFERIDO.
- The sample is small. With about 30 sessions, the CIs will be wide, and *not inferior* is the likely
  outcome against Opus.
- Latency is measured on a shared machine.
