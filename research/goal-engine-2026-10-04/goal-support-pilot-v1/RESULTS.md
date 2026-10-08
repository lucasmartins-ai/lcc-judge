# Cached-score supervised support/field pilot — 2026-10-08

## Decision

Reject this fixed development recipe. None of its484 train-only policy grid
points passes the aggregate/EN/PT precision, correct coverage and UNKNOWN gates.
The resulting null policy abstains on every query; zero coverage is a failure,
not improved usefulness. Fixed zero-floor diagnostics below are not adopted.
No fresh confirmation, source selector, LCC benchmark, default or P2 promotion.

## Method and scope

Protocol a1aae8e09162455ec94e162bf36c09daf3cad0cd7e734eef062af38e6227bb91
was frozen before the sole fit. Twelve immutable predecessor query/definition
logits,1,172/1,136 exposed unique train/validation queries,256/240 supported,
916/896 UNKNOWN. No record/annotation/entity features; no encoder loading,
tokenization or additional encoder inference. Definitions and parent scores
remain unchanged. Literal query overlap zero; authored families/primitives remain
correlated and exposed. Independent human semantics are pending.

Train-only mean/population SD, constant-column scale1; two linear heads totaling
117 parameters. Zero initialization, CPU float64/two threads,200 full-batch Adam
steps/LR.05, equal-class binary support BCE, supported-only field CE and .01
mean weight penalties. Final step only. Both policy floors are fitted on train
only; all gates apply to aggregate/EN/PT. Correct supported coverage>=.80 is an
additional conservative requirement beyond predecessor accepted coverage.

| Fixed zero-floor diagnostic | Train | Validation |
| --- | ---: | ---: |
| Accepted precision | 188/433=.434180 | 139/369=.376694 |
| Supported accepted | 200/256=.781250 | 172/240=.716667 |
| Correct supported coverage | 188/256=.734375 | 139/240=.579167 |
| UNKNOWN recognition | 683/916=.745633 | 699/896=.780134 |
| Unsupported accepted | 233 | 197 |

The predecessor neural router accepts808 unsupported and binds197 direct queries
correctly. This zero-floor diagnostic reduces unsupported acceptance to197 but
also reduces correct useful bindings to139. Different policies are explicitly
named; this is not an adopted before/after improvement or a causal diagnosis.
The actual null policy has precision undefined, coverage0 and UNKNOWN1.0 and fails.

## Accounting and verification

Exit0 at2026-10-08T11:11:22.812835Z.200 finite head updates;234,400 support training
row evaluations and51,200 field training row evaluations. These are small linear
head operations on cached features, not encoder forwards/tokens. Fit1.794550s,
fit/calibration/evaluation2.867838s after loading train inputs, whole-head process
peak RSS382,173,184bytes. The predecessor encoder cost is excluded and remains
in its original receipt; these costs are not whole serving or LCC economics.
Local API calls0; any later external claim review is accounted separately.

Three behavioral tests RED→GREEN; full suite255tests/zero skips22.745s; Ruff E9/F
PASS. Offline audit reproduces source/input identity, normalizer, every head
prediction, train-only policy grid, reductions, summary/stop flags and recorded
update/cost arithmetic. It does not replay optimizer updates or establish label
truth. Original sources/outputs remain frozen. One combined fresh-context review
covering this and the [direct-query embedding pilot](../goal-embedding-pilot-v1/RESULTS.md)
is recorded with the latter. Claim qualification is likewise recorded there.

Reproduce without encoder inference: `python -m research.goal_support_pilot --phase audit`.
`--phase run` refuses a second start. No thresholds, definitions or weights were
changed after inspecting validation. The next separately frozen representation
experiment reuses the same heads/gates, not this pilot's selected thresholds.
