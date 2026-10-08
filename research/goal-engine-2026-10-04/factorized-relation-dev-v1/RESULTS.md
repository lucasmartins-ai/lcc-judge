# Conditional training fits exposed train; transfer and removal still fail

The bounded single-seed development study completed all three finite epochs.
Training ordering is above .90, but validation ordering and negative rejection
fail. **This derivative is rejected for progression to fresh LCC outcomes.**
It is not a fresh-final experiment, an adoption candidate or useful-context proof.
The full engine + LCC goal remains active.

## What changed and what was measured

Protocol SHA `f5036631a3fff8e2bad9e0659be83f00e0962755012fc19b8feddc06b85d65a5`
was frozen before adaptation. The exact multilingual XLM-R artifact and retained
scalar-margin initialization are unchanged from the preceding study. Total/trainable
parameters117,641,859/3,697,923, last two blocks and classifier. Embeddings/first
ten blocks stay frozen and in eval. CPU/fp32/eight threads, seed101, three epochs,
AdamW classifierLR1e-4/tailLR2e-5/wd.01. Objective and classifier LR change jointly;
there is no causal ablation of either change or fair performance comparison here.

The same exposed original train and validation data are used. There are3,592
unique train pairs and1,002 deduplicated complete AA/AB/BA/BB quartets. Only natural
question/report strings enter the model. Each epoch contains a unique-item pass
and a unique-quartet pass with reproducible separate shuffles. Independent losses:

- Relevance BCE on binary records only, globally normalized by their fraction.
  Semantic UNKNOWN receives zero relevance gradient.
- Independent binary UNKNOWN-logit BCE, globally balanced supported/unsupported.
  The three head outputs no longer compete through a three-class CE denominator.
- Quartet softplus differences require relevant diagonal wins along both the
  report and goal axes. Conditional batches have no direct UNKNOWN-head gradient.

The shared writer saves the legacy coupled support axis in auxiliary
`*-logits.json`; `*-scores.json` derives independent logit2 support from those
same float32 logits without additional forwards. Relevance is logit1-logit0.
All raw files are immutable; model margins are not probabilities.

One complete exposed validation pass fixes the global cutoffs, then one complete
train pass uses those same cutoffs. No original final or fresh confirmation is
model scored. Point criteria remain pooled/within-goal≥.90, positive/contradiction
KEEP≥.95, negative DROP≥.70, semantic UNKNOWN≥.95 and zero UNKNOWN DROP, aggregate
and each EN/PT. Even exposed development does not satisfy all those criteria.

## Independently recounted results

| Population | Pooled AUC | Within-goal | Same-report goal | Negative DROP | Binary UNKNOWN | Semantic UNKNOWN recognized | UNKNOWN DROP |
|---|---:|---:|---:|---:|---:|---:|---:|
| Exposed train | .976310 | .972222 | .975694 | .011285 | .534071 | 1.0 | 0 |
| Exposed validation | .556345 | .613426 | .596065 | .012731 | .781829 | 1.0 | 0 |

Train has4,864rows/4,608binary, validation1,824rows/1,728binary. Positive KEEP
train/validation.986545/.975694; relevant contradiction KEEP.987633/.981132.
Structural UNKNOWN recognition1.0 on64/24rows. All semantic UNKNOWN192/72 are
recognized in this point evaluation; this does not certify unseen-goal safety.

Validation EN/PT pooled.553203/.550754, within-goal.659722/.567130 and negative
DROP0/.025463. Train EN/PT pooled.977517/.975478, both within-goal.972222. Both
train and validation fail overall policy gates. The .976train score is fit,
not semantic transfer. Most validation binary records are UNKNOWN, preserving
them and preventing useful removal. No cutoff is tuned to salvage this result.

The original disconnected pair graph, authored fixtures/English captions and
validation-specific wording remain unchanged. The train/validation gap demonstrates
failure on those validation strings; it does not isolate wording, graph, support
loss, learning rate, capacity or optimizer as its cause. Next work must broaden
audited development language/competing-field coverage before another confirmation.

## Complete execution and reproducibility

Three finite epochs, **1,428 accepted updates** (675classification/753conditional),
22,800 pair presentations/785,304 nonpadding training tokens. Summed epoch time
225.970s; frozen parameter hashes match after every epoch. Direct update/epoch
receipts, not terminal reconstruction, attest the completed epochs.

Evaluation: **6,600 valid pair forwards/232,194 nonpadding tokens**, zero cuts/errors:
1,800validation/67,758tokens in9.160s, 4,800train/164,436tokens in24.386s.
Whole study-process peak RSS1,999,126,528bytes includes training/loading/runtime;
it is not installed inference memory or LCC pipeline latency. No confidence
interval is assigned to correlated repeated authored rows or this one seed.

[Independent audit](audit.json) PASS verifies source/data/input identities,
both score axes, strict pooled/contrast metrics, global calibration optimality,
step ordering/token accounting, epochs, chronology and original/derivative hashes
and frozen tensor bytes. It does not replay gradients or approve quality.

```sh
python -m research.audit_factorized_relation_dev
python -m research.audit_factorized_relation_dev --verify-weights
```

The default audit is standard-library-only, offline, without models or APIs.
The second additionally requires private original/derivative artifacts, reading
their bytes without loading tensors. [Artifact inventory](../../../artifacts/factorized-relation-dev.json)
records seed/three direct epochs/weight SHA; it has no public download or deployment
operation. No native ModernBERT provider/default/P2/API/hosting/publication changes.

199 current tests, zero skips,19.210s including local LCC integration; scoped
Ruff0.16.10 F/E9 PASS. Log:`../goal-full-tests-factorized-relation.log`; trailing
UNKNOWN JSON is a mocked transport-failure case. Tests cover independent support
gradients, both conditional axes, complete train-only quartets and rejection of
changed scores/inputs/accounting. The RED import failure and GREEN are preserved.

See [NEXT_COVERAGE.md](NEXT_COVERAGE.md) for the next decision. No additional
epoch, final anchor, bigger RoPE, quantization or LCC outcome run on these weights.
