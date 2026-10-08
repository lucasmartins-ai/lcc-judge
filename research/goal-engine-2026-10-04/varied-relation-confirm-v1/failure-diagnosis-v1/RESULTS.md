# Saved-final failure diagnosis — 2026-10-08 local / 2026-10-07 UTC

The failed confirmation contains both ranking and support-transfer errors.
Changing one global relevance cutoff cannot repair strict ordering. No candidate
or original cutoff was changed. This phase used saved logits only: zero model
forwards, tool captures or API calls. These exposed finals are diagnostic data.

Protocol SHA: `a000415a32264fc43686f29b89ae833c03effa880bb1928661684e96d9491f37`.
`protocol.json` binds original scores, metrics, inputs, audits and archived source;
`summary.json` records unchanged original evidence. The reducer independently
reproduces all four original aggregate results before computing the breakdowns.

| Seed | Original pooled | UNKNOWN-vs-binary support AUC | Negative DROP with retention-fitted cutoff | Semantic UNKNOWN DROPs | Negative DROP after also preventing UNKNOWN DROP |
| --- | ---: | ---: | ---: | ---: | ---: |
| 101 | .858590 | .822646 | .370047 | 132 | .019518 |
| 202 | .870348 | .849480 | .404361 | 140 | .075534 |
| 303 | .850205 | .766815 | .346890 | 75 | .096737 |

Support AUC uses strict `P(logit2(semantic UNKNOWN) > logit2(binary))`, with
equal scores contributing zero. Retention-fitted diagnostics use the original
support cutoff and the greatest relevance cutoff preserving at least .95
positive and contradiction retention in all 24 cohort/query-or-report-language
constraints. This still falls short of the required .70 negative DROP. Further
lowering the relevance cutoff prevents UNKNOWN DROP but cannot turn incorrectly
supported UNKNOWN records into recognized UNKNOWNs. The original recognition
rates remain .699074/.703993/.518953, below .95.

Another saved diagnostic forces all semantic UNKNOWNs to abstain before fitting
retention. Its negative DROP is .010046/.052760/.000281 and binary UNKNOWN
.992258/.954580/.999419. This requires 100% recognition, stricter than the .95
gate; it is not an exhaustive optimization of every possible two-axis policy or
a proof that every refit is impossible. None of these final-fitted cutoffs may
serve inference or qualify an adoption candidate.

Positive records frequently dropped across all seeds include sent UDP datagrams,
staged Git paths and actual retry waiting time. Query aliases and same-tool field
distinctions also show substantial error differences. Inspect `101.json`,
`202.json`, `303.json`, and `scalar.json` for complete role/pair/language/alias/
caption/UNKNOWN-kind counts and exclusive KEEP/DROP/UNKNOWN dispositions.
Fixtures and wording combinations are correlated. Pair novelty is confounded
with tool combination and difficulty; these breakdowns do not isolate a cause.

The next bounded [wording pilot](../../wording-development-pilot-v1/RESULTS.md)
has now also failed. It is separate exposed development and does not rescore
these finals, certify production relevance or admit P2 data.

Runnable checks: `python -m unittest tests.test_varied_relation_failure_diagnosis`
checks strict ties, all retention constraints and aligned populations. The
original immutable diagnosis refuses to overwrite this output directory; inspect
its archived sources when reconstructing the historical receipt.
