# Balanced varied-state development — promising, confirmation required

The original detached execution completed at2026-10-05T09:54:28Z with exit0.
Both exposed train and validation pass the declared point criteria, aggregate and
each EN/PT query/report language. The [independent audit](audit.json) recomputes
inputs, update order, totals, calibration and metrics and verifies private weights
against the immutable base. PASS attests those receipts, not production usefulness.

## Recipe and populations

Frozen [protocol](protocol.json) SHA
`b8240c1a93f70508e6f7a40d8590e4c408aa82b51e36a8b417b894d121713588`.
Retained `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` scalar prior at revision
`8008f0154ca2387468013ed439df09d70c122412`;117,641,859total/3,697,923trainable
parameters, classifier and last2blocks. Seed101, three fixed CPU/fp32 epochs,
eight threads, AdamWclassifierLR1e-4/tail2e-5/weightdecay.01. Full unique-item
classification then full unique-quartet conditional pass each epoch; batches16/
4quartets. Binary relevance classes and support classes are globally balanced;
semantic UNKNOWN has no relevance gradient. Both conditional axes remain.

[Audited source data](../tool-relation-states-v2/RESULTS.md) supplies64train and
32validation author-created fixtures, with18known primitive fields/three tools/
52known pair edges. Train60,288rows/50,084unique projected inputs/12,568quartets;
validation30,144rows/23,692unique inputs. These correlated rows are not90,432
independent sessions. Query/report aliases, captions and languages are known;
only the raw fixture populations are disjoint. Maximum projected pair76tokens
inside a512token window; this does not measure useful long dossier context.

## Measured quality

Global cutoffs are fitted on validation only and frozen before train scoring:
independent support logit≥-8.779959678649902 means UNKNOWN; otherwise relevance
logit1-logit0<-1.1708091497421265 means DROP. Minimum semantic-UNKNOWN support
cutoff and retention constraints are declared in [thresholds.json](thresholds.json).

| Metric | Train | Validation |
|---|---:|---:|
| Strict pooled AUC | .983074 | .968897 |
| Within-goal AUC | .988845 | .977276 |
| Same-report goal-ordering AUC | .988882 | .977614 |
| Positive preservation | .963041 | .960862 |
| Relevant contradiction preservation | .963307 | .957770 |
| Negative DROP | .917443 | .810472 |
| Binary UNKNOWN | .249718 | .389235 |
| Semantic UNKNOWN recognition | 1.0 | 1.0 |
| Structural UNKNOWN recognition | 1.0 | 1.0 |
| UNKNOWN DROP count | 0 | 0 |

Preservation is KEEP **or UNKNOWN**, matching the declared policy; it is not
exclusive KEEP classification. Validation39%binary UNKNOWN remains a practical
limitation even though negative removal passes. Semantic recognition1.0 is partly
a consequence of the fitted cutoff and needs fresh confirmation. Every query/
report language passes; the tightest validation contradiction retention is EN
query.950000. Complete denominators and language slices are in
[train-metrics.json](train-metrics.json) and
[validation-metrics.json](validation-metrics.json). No fixture confidence interval
or causal attribution follows from these point results.

## Execution and recorded cost

[Direct training_meta](training_meta.json) records three completed finite epochs,
not reconstructed terminal output. Accepted updates18,819; pair presentations
301,068; nonpadding train tokens11,667,693; summed epoch time3,818.791s.
Evaluation90,240valid forwards/3,592,064tokens,192structural bypass rows,
716.882s; no cuts/errors. Entire study process peakRSS2,506,162,176bytes includes
training/loading and is not deployment memory. Recorded execution wall4,551.728s
also includes setup and metric calculation, not an inference latency benchmark.

The original [v1](../varied-relation-dev-v1/STATE.md) remains incomplete, with no
checkpoint/epoch/quality result and unknown exit cause. Its recorded lower-bound
cost2,426updates/38,816pairs/1,526,283tokens is preserved and SHA-bound. Combined
recorded training cost21,245updates/339,884pairs/13,193,976tokens. Possible prior
unpersisted work cannot be recovered. See [lifecycle and cost audit](lifecycle-cost-audit.json).

Private derivative SHA
`430a9e548a2e9f1f256f70ef2f5a6307768f936d555e4bfbe0b8f625e2017464`;
all frozen learned parameter bytes match the immutable base. Model architecture
differs from the native ModernBERT provider. No public weight URL or adoption.

After actual completion, the current status command delegates to the existing
PID/birth/module observer. Read-only observation verifies archived executed
sources; execution still requires current source equality. Original21frozen
sources and original observer archive remain unchanged. Regressions cover both
paths; no restart followed the historical falseSTOPPED observation.

232tests pass with0skips in19.919s, including localLCC; scopedRuffF/E9PASS.
Log: [complete integration check](../goal-full-tests-varied-development-complete-lcc.log).
The initial invocation without LCC on PYTHONPATH skipped4tests; its log is retained.
The corrected run includes them. Trailing UNKNOWN is a mocked failed capture.

## Decision and reproduction

Proceed to [fresh confirmation](NEXT_CONFIRMATION.md) under the frozen recipe.
No old exposed final is reused. No extra development epochs or threshold search.
P1 primitive relevance is not reviewed P2 necessity. Zero API calls/P2 admission/
default change/hosting/publication. Full engine+LCC goal remains ACTIVE.

```sh
python -m research.audit_varied_relation_dev \
  --out research/goal-engine-2026-10-04/varied-relation-dev-v2 --verify-weights
python -m research.detached_varied_study status
```

The optional weight check needs the private derivative and immutable upstream
snapshot. Without private weights, omit that flag to audit public receipts.
Original executed snapshots are the historical source contract; the post-study
status correction is not retroactively presented as executed training code.
