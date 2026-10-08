# Fresh confirmation execution — 2026-10-07

Development replications and fresh-final evaluation are complete and independently
audited. **All three candidates fail the quality gate.** See [results](RESULTS.md).
The goal tool reports `usageLimited`. This is not a completed or user-paused goal;
the evaluation process has ended and full engine+LCC usefulness remains incomplete.

## Completed evidence

- Original seed101 reused, with three epochs, weights and validation-only cutoffs.
- Seed202 exited0 at16:03:04Z; seed303 exited0 at16:45:49Z. Their `audit.json`
  receipts independently rederive updates, scores, calibration and private weights.
- Each completed seed:18,819finite updates/301,068training pair presentations/
  11,667,693nonpadding training tokens. Each development evaluation:90,240forwards/
  3,592,064nonpadding tokens. These totals exclude other historical studies and
  the interrupted v1 lower-bound cost, which remains preserved separately.
- Fresh data:64authored tool fixtures/1,152measured primitive fields,
  163,712correlated rows/120,220distinct projected inputs. Independent raw/label/
  tokenizer/disjointness audit PASS; zero cuts.101unseen cross-tool pair edges,
  52known-edge wording controls; all18primitive meanings/three tools remain known.
- The additive Git wording correction in `design-v2` preceded row derivation and
  model scoring. Capture-bound original sources/receipts remain unchanged.

| Seed | Development validation pooled | Within-goal | Positive retention | Contradiction retention | Negative DROP | Binary UNKNOWN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 101 | .968897 | .977276 | .960862 | .957770 | .810472 | .389235 |
| 202 | .966275 | .976450 | .958534 | .958446 | .826998 | .176983 |
| 303 | .968888 | .978966 | .958233 | .955068 | .832407 | .134878 |

These are exposed development point measurements, not independent final or LCC
outcomes. Retention includes both KEEP and UNKNOWN. All three semantic/structural
UNKNOWN recognitions are1.0, UNKNOWN DROPs0; development gates pass each query/
report language. The independent audits certify evidence integrity. The Jev
claim gate PASS is limited to completed-epoch/receipt integrity, not model quality.

## Completed run and guards

Evaluation protocol SHA:
`19e779f288b384d7d4169149b21a05f604547d58621e6ccc58fe4949648e26fb`.
Launched once at20:43:59Z, PID67881 with recorded birth and fixed module; started
at20:44:00Z and seed101 at20:44:03Z. Inspect `evaluation-v1/launch.json`,
`started.json`, `run.log`, `run-errors.log` and `process-exit.json`.
Finished21:12:19Z, exit0; all four scoring populations complete. Independent
`evaluation-v1/audit.json` PASS rederives evidence with zero additional inference.
Do not infer completion from a surviving PID or restart from missing output.

The unexecuted scorer had the wrong coupled support axis, an absent view hash,
missing UNKNOWN rows in subset gates and repeated scalar controls. Before any
final forward it was replaced with existing complete-input/failure-accounting
helpers. The red regression receipt remains. Current tests pass243/0skips;
Ruff E9/F passes. Scoring sources are archived and SHA-bound before execution.

All three weights/cutoffs/development audits were locked before any final inference.
Support is the trained independent logit2; relevance is logit1−logit0. Identical
inputs reuse one saved forward; fifteen required slices per seed share UNKNOWN
annotations but never count those forwards twice. Metrics include exclusive
KEEP/DROP/UNKNOWN counts. Scalar runs once in shadow, with no DROP authority.
Actual final cost:480,880unique pair forwards/24,255,452nonpadding tokens for
three candidates plus scalar. Total elapsed1699.060s; process peakRSS3,795,386,368bytes
includes dataset/receipt handling and reduction, not deployment footprint.
Raw receipts preserve failed/partial inference accounting; no selective retries.

## Next action after failed confirmation

1. Execution and independent audit are complete. Every seed/slice policy fails;
   pooled.858590/.870348/.850205, retention.556436/.655497/.593073, semanticUNKNOWN
   recognition.699074/.703993/.518953 and UNKNOWN DROPs1568/1220/1716.
2. Saved-logit diagnosis is now complete with zero additional forwards. Fitting
   relevance for retention still fails negative rejection/support recognition;
   these hypothetical final-fitted cutoffs are not serving policies.
   See [diagnosis](failure-diagnosis-v1/RESULTS.md).
3. The separate bounded wording pilot also completed and failed: validation
   pooled.625629/negativeDROP.001953/binaryUNKNOWN.998047. No new final was scored.
   See [results and redirect](../wording-development-pilot-v1/RESULTS.md). Diagnose
   the semantic task and goal-binding contract before a controlled new protocol.
   An untouched passing confirmation remains required before semantic LCC outcomes.

No default promotion, P2 admission, external publication, native32K-attention claim
or broad Laya/Jev replacement certification. Semantic dossier usefulness,
independent replay reliability and final public preparation still remain.
