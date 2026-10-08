# Fixed upstream MiniLM on exposed semantic pairs

The diagnostic completed all 2304 pair evaluations: validation384/final384,
three repeats each, fixed CPU/fp32/batch16/8threads, whole pairs ≤93tokens,
zero cuts/errors and identical repeated scores. No APIs or training. The model
is the pinned MS-MARCO MiniLM-L6 snapshot listed in protocol.json.

| Metric | Validation | Exposed final |
|---|---:|---:|
| Strict pooled AUC | .8154296875 | .6719835069 |
| Same report, two goals AUC | .8958333333 | .7031250000 |
| Same goal, candidate ordering AUC | 347/384 = .9036458333 | 257/384 = .6692708333 |
| Positive recall at validation threshold | .9531250000 | .9687500000 |
| Negative rejection | .2708333333 | .0520833333 |

The declared quality gate fails. Whole-final-family 2000-draw descriptive
bootstrap95% for pooled AUC is [.5898905436,.7639973958]. Six authored families
are not an independent semantic population. Raw scores and original input hashes
are in validation-0/1/2.json and final-0/1/2.json. Same-goal ordering is a separate
axis from paired_auc, which this protocol defines across two goals for one report.
An offset normalizer cannot reverse wrong candidate ordering under a fixed goal.

The original process failed only while JSON-serializing loader diagnostics after
all scores/threshold were saved. `run.json` is absent and is not manufactured.
`audit.json` is an offline completion from those raw receipts. Unsaved setup time,
RSS and runtime identity stay unknown. Failure traceback remains in ../reranker-run.log.
The current adapter normalizes runtime sets in loading metadata; a regression test
failed before the fix and passes after it. Archived executed-source retains the
exact adapter that scored these rows; no inference was repeated to fill the report.

Observed complete pair-pass times are 1.043/1.011/1.232s validation and
1.008/1.055/1.050s final. These include tokenization and are not a matched
architecture latency claim. Actual token accounting is 161340 counted/submitted/
completed/valid nonpadding tokens. Annotation checks additionally use the earlier
CPU study's archived corpus source, a retrospective dependency explicitly recorded
in audit.json. No independent temporal attestation, default adoption or P2 labels.

Audit, standard library only, zero model/API calls:
`python -m research.audit_reranker_diagnostic`.
