# LCC-judge

The local block judge for [LCC](https://github.com/lucasmartins-ai/lcc) (Local Context Compiler), and the
benchmarks behind it.

When LCC has to shrink an agent's context, it scores every block and drops the lowest first. LCC-judge
builds and tests that scorer. The current judge, **specialist v3**, is a small feature model (logistic
regression + gradient-boosted trees, 183 KB of JSON, numpy only) that runs on CPU in about 0.2 s per item
with no network and no external model. It replaced Laya (deprecated) and the paid remote Jev judge as LCC's
default for transcripts; Jev stays available in LCC as an opt-in.

Large models (Claude Opus 5.5, Gemini 3.8 Flash) appear here only as offline benchmark references and as a
teacher for one experiment. Nothing in the shipped judge calls them.

## Status

- **v3 is shipped in LCC**: ranker in [lcc#50](https://github.com/lucasmartins-ai/lcc/pull/50), auto
  default for transcripts in [lcc#51](https://github.com/lucasmartins-ai/lcc/pull/51) (both merged
  2026-10-18). LCC vendors the model as `src/lcc/relevance/specialist_v3.json`.
- **v4 was not adopted** under its pre-declared selection rule.
- **v5 is in progress**: deterministic detectors for the edge-case failures, a sealed second edge suite.

| version | what it is | outcome | results |
|---|---|---|---|
| v1 | ModernBERT pair head, shadow-only in LCC | never passed its quality gates outside training; not adopted | [MODEL_CARD.md](MODEL_CARD.md), [STATUS.md](STATUS.md) |
| v2 | 50 cheap features, LR (+ GBDT alternative), next-action labels | frozen test: beat recency/BM25/mechanical; failed the edge suite and peak RSS (307.7 MB > 300) | [TEST_RESULTS.md](research/goal-engine-2026-10-04/specialist-v1/TEST_RESULTS.md) |
| v3 | v2 LR + GBDT averaged, plus a floor for the top goal-match block and the 2 newest errors; leaner memory | **shipped**; passed the pre-registered held-out test vs local baselines and cost | [V3_DEV_RESULTS.md](research/goal-engine-2026-10-04/specialist-v1/V3_DEV_RESULTS.md), [V3_FINAL_TEST_RESULTS.md](research/goal-engine-2026-10-04/specialist-v1/V3_FINAL_TEST_RESULTS.md) |
| v4 | Opus 5.5 as a holistic "relevance" teacher + supersession / contradiction / coreference features | not adopted: edge rose to 29/27/23, dev all-kept AUC fell significantly. Lesson: teaching holistic relevance hurts a fast system-1 judge | [V4_DEV_RESULTS.md](research/goal-engine-2026-10-04/specialist-v1/V4_DEV_RESULTS.md) |
| v5 | deterministic detectors built from edge cases, sealed edge suite v2, Opus only as a small yes/no teacher | in progress | not published yet |

## Results

Labels are rule-based next-action evidence: a block counts as USED when the agent reused something from it
afterwards. That is v3's training target, so these numbers measure fit to real agent sessions, not general
reading skill. They are tagged **INFERIDO** for that reason; the counts and arithmetic are **MEDIDO**. The
sessions are the owner's own (Claude Code, Codex, Hermes) and stay private; only aggregates are published.

Metric: drop the lowest-scored blocks until 10–60% of candidate tokens are gone; **recall** = share of USED
tokens kept, **all-kept** = item keeps every USED block. AUC over the 0–60% curve, 1.0 = perfect.

**Held-out final test** (pre-registered; sessions started after the cutoff and never seen in development;
193 items in 36 session groups; paired bootstrap over groups):

| arm | recall AUC | all-kept AUC | v3 − arm, recall [95% CI] | v3 − arm, all-kept [95% CI] |
|---|---:|---:|---|---|
| **specialist v3** | **0.899** | **0.434** | | |
| mechanical (LCC lexical) | 0.829 | 0.238 | +0.070 [+0.044, +0.102] | +0.197 [+0.134, +0.283] |
| recency | 0.818 | 0.306 | +0.081 [+0.067, +0.097] | +0.129 [+0.069, +0.201] |
| BM25 | 0.803 | 0.270 | +0.097 [+0.066, +0.136] | +0.164 [+0.099, +0.248] |
| random | 0.689 | 0.138 | | |

LLM subset (36 items, one per session group; Opus and Gemini scored offline through subscription CLIs):

| arm | recall AUC | all-kept AUC | v3 − arm, recall | v3 − arm, all-kept | reading |
|---|---:|---:|---|---|---|
| specialist v3 | 0.876 | 0.417 | | | |
| Claude Opus 5.5 | 0.884 | 0.347 | −0.009 [−0.055, +0.031] | +0.069 [−0.028, +0.167] | tie: no significant gap either way |
| Gemini 3.8 Flash | 0.838 | 0.299 | +0.038 [−0.007, +0.083] | +0.118 [+0.026, +0.220] | not inferior on recall, better on all-kept |

**Edge suite** (35 synthetic cases built from real failure patterns; single-author gold; v3's config was
selected with it, so it is not held-out evidence). Cases passed at 30 / 50 / 70% cut:

| arm | 30% | 50% | 70% |
|---|---:|---:|---:|
| Claude Opus 5.5 | 35 | 35 | 35 |
| Gemini 3.8 Flash | 35 | 35 | 34 |
| **specialist v3** | **28** | **23** | **20** |
| mechanical | 22 | 21 | 18 |
| Laya | 21 | 14 | 11 |
| BM25 | 21 | 20 | 18 |
| recency | 7 | 7 | 4 |

This is v3's weak spot: supersession, contradiction, coreference and rule cases need reading
comprehension that its features do not carry. v5 targets exactly these.

**Cost** (fresh process, 1 thread, held-out items, shared machine so latency is an upper bound): median
178 ms, p90 567 ms, peak RSS 97.5 MB, 183 KB model. Synthetic stress items: see the latest benchmark run.

Full tables, sources and disclosures: [V3_FINAL_TEST_RESULTS.md](research/goal-engine-2026-10-04/specialist-v1/V3_FINAL_TEST_RESULTS.md).
Latest benchmark run: [research/bench-results/latest.md](research/bench-results/latest.md).

## Run the benchmark

`research/bench.py` recomputes every number above from cached data and saved scores. It makes no LLM or
remote call; Opus, Gemini, Jev and Laya scores are read from earlier runs' caches.

```sh
export PYTHONPATH="$HOME/path/to/lcc/src:$PWD"   # LCC source, for the mechanical baseline
python -m research.bench edge      # edge suite, all arms
python -m research.bench dev       # 325 dev items + jev-overlap subset
python -m research.bench heldout   # frozen final test: re-report, recompute, compare field by field
python -m research.bench cost      # latency / RSS on synthetic stress items
python -m research.bench all       # everything -> research/bench-results/latest.{md,json}
```

`edge` and `cost` need only this repo, LCC and the v3 model. `dev` and `heldout` read the private session
data under `~/.lcc/bench/` and do not run without it. The command refuses the spent test split and writes
aggregates only. The latest run reproduced the dev results and the held-out final test exactly.

## Repo map

| path | what |
|---|---|
| `research/specialist_v3.py` | v3 judge: `Judge.load(path).score(goal, texts) -> [float]` |
| `research/specialist_v2.py` | features (BM25, recency, error markers, LCC protection, size) and v2 models |
| `research/matched_budget_v2.py` | drop-by-budget metrics, baselines, jev-overlap subset |
| `research/edge_suite.py`, `research/edge_cases_build.py` | edge suite and its fixtures (`tests/fixtures/edge_cases/`) |
| `research/next_action_labels.py` | next-action labels from agent transcripts |
| `research/heldout_v3.py`, `research/v3_final_test.py` | held-out build and the one-shot final test |
| `research/llm_judge_arm.py` | offline LLM reference arms (not part of the product) |
| `research/bench.py` | the benchmark entry point |
| `research/goal-engine-2026-10-04/specialist-v1/` | protocols, results and receipts for v2–v4 |
| `lcc_engine/`, `specialist/` | the earlier ModernBERT engine (v1) and its training code |
| [STATUS.md](STATUS.md) | project status and evidence index |

## Evaluation rules

- **Pre-registration.** Each final test has a protocol committed and pushed before its data is built
  ([V3_FINAL_TEST_PROTOCOL.md](research/goal-engine-2026-10-04/specialist-v1/V3_FINAL_TEST_PROTOCOL.md)).
  Selection rules are written before candidates are scored ([V4_SELECTION_RULE.md](research/goal-engine-2026-10-04/specialist-v1/V4_SELECTION_RULE.md)).
- **Frozen hashes.** The test runner refuses to start if the model, the code or the held-out manifest differ
  from the sha256 values in the protocol and build receipt.
- **Session-disjoint held-out.** The final test uses sessions that started after a cutoff, with zero items
  content-linked to train/dev. Each test set is evaluated once; the old test split is spent and refused.
- **Negative results stay.** Failed candidates and their reasons are kept in [research/failures.md](research/failures.md)
  and [research/experiments.md](research/experiments.md).

## Privacy

Session text, goals and per-item scores live only under `~/.lcc/` on the owner's machine. This repository
holds code, synthetic fixtures, counts, aggregates and hashes. No result in this README can be recomputed
without that private data except the edge suite and the cost run.

## License

Code and project-authored fixtures: MIT ([LICENSE](LICENSE)). Third-party material:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Resumo (pt-BR)

- O LCC-judge é o juiz local de blocos do LCC: decide o que cortar do contexto, sem rede e sem modelo externo.
- O especialista v3 está em produção no LCC (PRs #50/#51) e substituiu o Laya e o Jev pago como padrão.
- No teste final pré-registrado, o v3 venceu recency, BM25 e o mecânico, empatou com o Opus e superou o Gemini em all-kept.
- O ponto fraco são os casos de borda (28/23/20 contra 35/35/35 do Opus); o v5 ataca isso.
- `python -m research.bench all` refaz todos os números, sem chamar LLM.
