# bakeoff — encoder bake-off harness (Sprint 2)

Measures **effective context** (not declared windows), judgment quality and CPU cost
for candidate encoders/judges. See `../docs/05-benchmark-strategy.md` §4 and
`../SPRINT_02_BAKEOFF.md`.

## Run

```bash
/Users/Master/LCC/.venv/bin/python -m bakeoff.runner --device cpu            # all models
/Users/Master/LCC/.venv/bin/python -m bakeoff.runner --models ModernBERT-base --depths 0,256,1024
/Users/Master/LCC/.venv/bin/python -m bakeoff.runner --fresh                 # discard saved results
```

Results accumulate across invocations in `results/results.json` (re-run models
replace their rows); `results/RESULTS.md` is regenerated from all saved rows.

## Structure

- `probes.py` — deterministic probe generation. Two families: `noise_unrelated`
  (P1 detection) and `noise_decoy` (P2 value judgment); depth 0 = control.
  Depth is tiktoken cl100k tokens.
- `adapters.py` — `LexicalAdapter`, `LayaJudgeAdapter` (exact LCC `keep_question`),
  `HFSequenceAdapter` (cross-encoder), `BiEncoderAdapter` (mean-pooled cosine).
- `runner.py` — grid runner, AUC/latency/RSS metrics, report renderer.

## Metric

`AUC(d) = P(score(fact@d) > score(noise@d))` over case pairs; effective context =
largest depth with AUC ≥ 0.90, reported separately for P1 and P2. Latency is per
(objective, block) call on a fixed machine (Apple M1 Max CPU, 10 cores).

## Caveats

- n = 8 cases ⇒ AUC granularity 1/64; read curves, not single cells.
- Laya rows probe the raw model beyond LCC's production budget (LCC refuses states
  over 831 tokens and keeps blocks whole instead).
- RSS deltas are `ru_maxrss`-based (max-only) and understate later models in a batch.
