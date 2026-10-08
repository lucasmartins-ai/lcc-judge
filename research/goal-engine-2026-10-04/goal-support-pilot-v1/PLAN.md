# Cached-score query-support pilot — 2026-10-08

The user approved continuing after the frozen goal-only routing failure, with
out-of-scope acceptance the immediate problem. This bounded development pilot
tests separately supervised support and field identity before new encoder work.

Inputs are the same twelve immutable query/public-definition logits from
goal-interpreter-probe-v1. No question annotation, record, entity or target enters
the feature vector. Fit only on its original train population; exposed validation
is one fixed diagnostic evaluation, not fresh confirmation. Existing authored
semantic labels remain subject to independent human review. Literal query
overlap is zero; shared primitives/templates and correlated families remain.

Recipe: train-only per-column mean/population-standard-deviation (constant column
scale 1); two linear heads, binary support and eight-class field identity. Zero
initial weights/biases; CPU float64, two threads, 200 full-batch Adam updates,
LR .05, no weight decay; sum of equally balanced binary support BCE, field CE on
supported train queries only, and .01 mean squared weights for each head.
No encoder loading, tokens, extra scores, seeds, model/definition search or best
epoch selection. Final update only; abort on nonfinite loss/gradient/weights.

Select support floor and top-two field-logit margin floor using only train:
21 quantiles (0:.05:1) plus max+1 per axis; reject exact field ties. Among policies
passing all aggregate/EN/PT gates, maximize minimum correct supported coverage,
then overall correct coverage, then lower floors. Gates retain accepted precision
>=.99, supported acceptance >=.80 and UNKNOWN recognition >=.95; additionally
require correct supported coverage >=.80. No feasible train policy means no
deployable policy; report fixed zero-floor diagnostics separately, never as a pass.

Do not retune after validation. Passing development only permits preparation of
fresh question families, with translations/paraphrases grouped, original full
selection gates and later LCC8K/32K/larger success>=.90, loss<=.02, removal>=.25
and complete serving cost. Failure stops before fresh confirmation and LCC.
An eight-field pilot cannot certify eighteen fields, source adapters, opacity,
real user questions or replacement of Laya/Jev.

1. Add behavioral tests, then implement cached input guards, separate fitting,
   conservative policy calibration and frozen preparation/run/offline audit.
2. Watch tests RED→GREEN; run full suite/Ruff; freeze sources/input hashes and
   protocol before the single head fit. Exclusive receipts; no overwritten run.
3. Execute the bounded fit/evaluation; offline rederive every saved prediction,
   policy and reduction. Preserve loss/update/parameter/time/RSS accounting.
4. One fresh-context final review; one Important/Critical fix pass if required.
   Record decision, claim qualification, current docs/manifest and durable memory.
