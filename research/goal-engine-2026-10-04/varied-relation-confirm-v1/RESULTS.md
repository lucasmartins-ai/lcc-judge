# Fresh confirmation — complete, all three candidates rejected

The fixed evaluation completed2026-10-07T21:12:19Z with exit0, no inference
error and all four populations complete. The independent stdlib audit passes:
saved inputs, fp32 logits, locked validation-only cutoffs, all15slice reductions,
source/weight hashes, chronology and total cost agree. Audit PASS validates the
receipts; candidate quality FAIL remains authoritative.
The separate Jev claim gate also passes only the narrow observed assertion that
this fixed confirmation rejected all three candidates; it does not certify utility.

Protocol: `19e779f288b384d7d4169149b21a05f604547d58621e6ccc58fe4949648e26fb`.
Evidence: `evaluation-v1/summary.json`, `process-exit.json`, `audit.json`, and
each `101/202/303/scalar/{unique-scores,metrics}.json`. No threshold changed,
candidate retrained, selective retry or new model inference was used by the audit.

## Fresh-final point measurements

| Candidate | Pooled AUC | Within-goal AUC | Positive retention | Contradiction retention | Negative DROP | Semantic UNKNOWN recognition | UNKNOWN DROPs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Seed101 | .858590 | .886508 | .556436 | .559945 | .883821 | .699074 | 1,568 |
| Seed202 | .870348 | .895157 | .655497 | .662274 | .847605 | .703993 | 1,220 |
| Seed303 | .850205 | .879500 | .593073 | .600384 | .840125 | .518953 | 1,716 |
| Immutable scalar shadow | .874211 | .899835 | 1.0 | 1.0 | 0 | 1.0 | 0 |
| Required candidate gate | ≥.90 | ≥.90 | ≥.95 | ≥.95 | ≥.70 | ≥.95 | 0 |

All three candidates fail every one of their15required complete-policy slices.
The scalar control performs ranking only and retains everything as UNKNOWN;
its perfect retention does not demonstrate compression or learned abstention.
Structural UNKNOWN recognition is1.0 for every candidate/control. Candidate
binary UNKNOWN rates are.203565/.166501/.136546. Positive retention counts both
KEEP and UNKNOWN; even with that protection,34.45%–44.36%of relevant rows DROP.

| Candidate | Positive KEEP | Positive UNKNOWN | Positive DROP | Semantic UNKNOWN incorrectly KEEP | Semantic UNKNOWN incorrectly DROP |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seed101 | 17,845 | 25,744 | 34,747 | 512 | 1,568 |
| Seed202 | 31,686 | 19,663 | 26,987 | 826 | 1,220 |
| Seed303 | 31,673 | 14,786 | 31,877 | 1,609 | 1,716 |

Denominators:78,336positive/78,336negative/6,912semanticUNKNOWN/128structuralUNKNOWN.
These163,712rows are correlated variants of64authored fixtures/1,152actual fields,
not163,712independent user tasks or production/human ground truth. All18primitive
meanings/three tools are known. The primary101newcross-tool edges differ in
difficulty/tool distribution from the52known-pair wording controls; their contrast
is not a causal estimate of pair novelty or paraphrase robustness.

## Required cohort/language slices

All numbers remain available perseed in `metrics.json`. Pooled/within-goal AUCs:

| Cohort | Seed101 | Seed202 | Seed303 | Immutable scalar |
| --- | ---: | ---: | ---: | ---: |
| Primary new cross-tool pairs | .896578 / .927647 | .909056 / .936881 | .885257 / .916315 | .932793 / .955774 |
| Known-pair wording controls | .784091 / .806603 | .793098 / .814115 | .780162 / .807993 | .755169 / .791185 |

Each cohort includes aggregate, EN/PT query and EN/PT report gates, sharing UNKNOWN
rows for safety evaluation without repeating their forwards. Some primary ordering
submetrics pass, but retention and UNKNOWN policy fail; no cohort grants DROP
authority. None of the adapted candidates exceeds the scalar's pooled ordering on
the overall fresh population or primary cross-tool population. On known-pair wording
controls the adaptations improve scalar ordering, but all remain far below.90.

Development validation had pooled≈.966–.969 and retention≥.95. Fresh confirmation
does not sustain those results. A wording/state generalization problem and cutoff
transfer problem are hypotheses to separate using saved scores. A global monotone
score calibration or threshold change alone cannot repair the failed ordering AUCs.
These combined data/objective/recipe changes are not an isolated causal ablation.

## Complete evaluation cost

Each model scored120,220distinct complete projected inputs/6,063,863nonpadding
tokens once; duplicated correlated rows reuse persisted logits. Four populations
total480,880forwards/24,255,452tokens, no cuts/errors. Actual model-scoring times:
seed101423.285s, seed202409.163s, seed303406.158s, scalar415.416s. Total process
elapsed1699.060s (28.32min); peakRSS3,795,386,368bytes includes all dataset/receipt
loading and reduction, not an isolated deployment footprint. CPUfp32/eightthreads,
batch16,512token pair window. Earlier development/training/interrupted costs remain
separate and preserved. Evaluation API calls0; audit additional model forwards0.

## Decision and next work

Reject these three candidates for context-dropping adoption. Preserve all frozen
data/weights/receipts. No final fitting, more epochs on this recipe, seed picking,
native32K expansion, quantization or expensive LCC outcome comparison is justified
by this failed confirmation. The scalar remains a shadow ordering reference.

1. Recount errors from saved logits only: primitive/pair/wording/query/report
   language/UNKNOWN kind, retention-vs-rejection tradeoffs and comparisons with
   scalar. Separate ordering, support and cutoff transfer without rerunning models.
   Success: exact failure counts reconcile with this report and identify the major
   error cohorts; any hypothetical cutoff analysis is explicitly diagnostic only.
2. Use those cohorts to freeze a separate development population with more varied
   EN/PT direct-field wording and unsupported goals, splitting whole wording
   families between training and validation. Test a bounded change that preserves
   scalar ordering while improving support/retention. These finals are now exposed
   and cannot be reused as a fresh adoption test.
3. Freeze a new untouched confirmation after all candidate weights/cutoffs are
   locked. Success: every predeclared seed/slice satisfies the unchanged table
   thresholds and zero UNKNOWN DROPs. Only then measure fresh useful semantic
   LCC8K/32K/larger outcomes, complete cost and external-provider comparisons.

The full engine+LCC usefulness goal is incomplete; the goal tool reports
`usageLimited`. No default/P2/publication or broad Laya/Jev replacement approval.
