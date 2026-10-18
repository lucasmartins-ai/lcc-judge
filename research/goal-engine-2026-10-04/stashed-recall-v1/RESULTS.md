# Stashed recall v1: results (2026-10-18)

Pre-registered in `PROTOCOL.md` (amendments 1-4). Harness frozen at 42dc86e, re-frozen at 7b55f79 (Amendment 4).
Receipts committed in e647be1 before any D answer. Aggregates only; machine-readable copy: `results.json`.
**Label: INFERIDO.** One run, one owner's sessions, one answerer model; `gateClaim` was not run on these numbers.
1 118 subscription calls in all (cap 1 150), including pilot, duplicates from the Amendment 4 incident and 429
stops. LCC pin `4719fde` (`rules_mode=stashed`, branch `claude/silly-chatelet-0500f9`, not merged).

## Bottom line

- **H1 passes.** With 36.6% fewer context tokens, `stashed` + recall is non-inferior to full context on artifact
  recall: `stashed_t − full_t` = **+0.006 [−0.023, +0.034]** (margin −0.05).
- **H2 passes.** The tool is what makes it work: on stash probes, `stashed_t − stashed_0` = **+0.89 [+0.82, +0.95]**.
  Without the tool the model gets 1 in 144 of them right; with it, 90%.
- **Agents recall when needed and mostly only then:** 90% of stash probes triggered a recall of the right blob;
  76% of recall calls fetched a blob holding gold. Recalled text was 16% of the stashed tokens, so the effective
  context (kept + recalled) is a median **75% of full**.

## Gates (D: 172 items, 75 lineage groups, 0 dropped)

| gate | rule | result |
|---|---|---|
| V1 | `full_t` artifact recall ≥ 0.50 | 0.61: pass |
| V2 | ≤ 10% dropped | 0%: pass |
| V3 | ≥ 40 stash-dependent probes | 144 stash probes (Amendment 2): pass. Original probes: 19, descriptive only |
| V4 | tool path works | pass (pilot) |
| judge agreement | Opus × Gemini quadratic-weighted kappa, artifact_trail | 0.911 on 204 records (17 items) |

## Per arm (95% CI: cluster bootstrap for means, Wilson for rates)

| metric | full_t | stashed_t | stashed_0 |
|---|---|---|---|
| context tokens, pooled | 9 398 654 | **5 961 815** (−36.6%) | 5 961 815 |
| artifact path recall (mean) | 0.613 | 0.619 | 0.573 |
| recall exact match | 0.988 [0.956, 0.997] | 0.981 [0.947, 0.994] | 0.883 [0.824, 0.924] |
| stash-probe exact match (n = 144) | 0.924 [0.868, 0.957] | 0.896 [0.835, 0.936] | **0.007** [0.001, 0.038] |
| items with ≥ 1 invented path | 0.59 | 0.59 | 0.57 |
| judge accuracy | 3.67 | 3.64 | 3.51 |
| judge artifact trail | 3.72 | 3.71 | 3.57 |
| judge continuity | 3.80 | 3.81 | 3.63 |
| judge instruction following | 4.26 | 4.20 | 4.15 |

`full_t` and `stashed_t` share the same prompt and tool; `full_t` made 0 recall calls (nothing stashed).

## Contrasts

| contrast | n (groups) | mean [95% CI] |
|---|---|---|
| **H1** artifact recall, stashed_t − full_t | 172 (75) | **+0.006 [−0.023, +0.034]**: pass |
| **H2** stash-probe exact, stashed_t − stashed_0 | 144 (64) | **+0.889 [+0.820, +0.949]**: pass |
| S2 recall exact, stashed_t − full_t | 162 (72) | −0.006 [−0.022, 0.000] |
| S3 stash-dependent original probes, stashed_t − full_t | 15 (13) | 0.000 [0.000, 0.000] |
| S3b same probes, stashed_t − stashed_0 | 15 (13) | +0.93 [+0.77, +1.00] |

## Recall behaviour (`stashed_t`)

| metric | all 172 | single-run 55 (Amendment 4) |
|---|---|---|
| R1 stash probes followed by a recall of a gold blob | 0.903 [0.843, 0.941] (n = 144) | 0.917 [0.805, 0.967] |
| R1 original stash-dependent probes (descriptive) | 0.895 [0.686, 0.971] (n = 19) | — |
| R2 recall calls that fetched a gold-holding blob | 0.761 [0.698, 0.814] | 0.853 [0.750, 0.918] |
| R3 recall calls per item (mean) / items with none | 1.19 / 40 | — |
| R3 cap hits / R6 errors | 0 / 0 | — |
| R4 recalled tokens / stashed tokens | 0.159 | — |
| R5 effective context (kept + recalled) / full, median | 0.752 | — |

## Reading (INFERIDO)

- `stashed` is the first LCC mode that cuts a large share of real-session context (36.6% on D, 30.1% on the 847
  dossiers of `stashed-v1`) without measurable loss on these probes. The earlier verbatim modes cut < 1%.
- The removed content is rarely what the agent used next: only 19 of 662 original probes depended on it. When it
  is needed, the model asks for it: 90% of the time on probes built to need it.
- The saving is smaller than 36.6% once recalls are paid: median 25% per item. Recall turns also re-send the
  context, which a provider prompt cache absorbs only if the prefix is stable; that cost is not modelled here.
- Not budget-matched to a summary: the native summary of probe-eval-v1 used about 10% of `C`. LCC leaves user and
  assistant text and call inputs untouched, which are 27% of `C` on D, so no current mode can reach 10%.

## Limits

- Stash probes ask about removed content on purpose (Amendment 2). They measure "can it get it back when asked",
  not "did it need it". The natural-need stratum is small (19 probes).
- Amendment 4: two drivers overlapped; 21 `stashed_t` items were re-run, and R1/R2 are also shown on the 55
  single-run items. The 96 re-used items could rarely pair an answer with the other execution's log.
- One answerer (Sonnet 5.5) through the subscription CLI; the tool loop is Claude Code's, not each agent's own.
- D is not virgin (see probe-eval-v1); the `stashed` rules reuse `lossy`/`recoverable`, tuned on sets that may
  share sessions with D.
