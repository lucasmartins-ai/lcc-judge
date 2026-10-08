# One scope-checked input view, exposed-cohort diagnostic

Same original validation384/final384 records and pinned MiniLM as the raw control.
The fixed view checks caller entity against two exact report grammars, removes
validated structure/severity/entity suffix, and preserves the natural question,
measurement description and numeric value. It never reads label/domain/slot
annotations. Unsupported or ambiguous inputs stay UNKNOWN with original evidence.
This is a changed-input recipe, not a same-input model/architecture comparison.

Sources, view hashes and criteria were frozen before this study's six passes.
2304 actual pair evaluations, all complete ≤30tokens, no cuts/errors, identical
repeated scores. No training/APIs/default change. Threshold chosen on validation.

| Exposed final metric | Raw control | Fixed view |
|---|---:|---:|
| Strict pooled AUC | .6719835069 | .6928710938 |
| Same report, two goals AUC | .7031250000 | .7656250000 |
| Same goal, candidate ordering AUC | 257/384=.6692708333 | 265/384=.6901041667 |
| Positive recall | .9687500000 | .9479166667 |
| Negative rejection | .0520833333 | .0989583333 |

The unchanged gate fails, including recall. This closes the representation-only
hypothesis on these exposed cohorts; it does not establish independent transfer or
prove which removed field caused the point differences. Whole-pass times are
.518/.466/.458s validation and .492/.495/.490s final; 49212 nonpadding tokens
counted/submitted/completed/valid. Saved load/setup≈3.537s, process highwater
RSS663617536bytes includes interpreter, framework and whole study. No separate
architecture performance comparison is claimed.

Independent stdlib audit reconstructs views from original records, verifies archived
sources/identities/threshold/raw metrics/accounting and the failed gate without
model/API calls: `python -m research.audit_reranker_projection`.

Next: a separately frozen compact adaptation study, with old18 exposed families
now development and eight new measurement-pair families reserved before training.
Neither diagnostic gives P2 necessity labels or authorizes context removal.
