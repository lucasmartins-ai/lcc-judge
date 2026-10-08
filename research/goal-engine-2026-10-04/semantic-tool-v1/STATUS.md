# Preserved incomplete MPS study

Five finite validation candidates; last-two seed 303 has three NaN loss passes and
failed before saved weights/validation/selection/final inference. See audit.json,
../semantic-train.log and numerical-diagnostic/DIAGNOSTIC_NOTES.md.15 finite epochs
plus three in valid passes are not18 accepted training epochs. The original cause
is unresolved; instrumented first-epoch checks change synchronization.

CPU comparison is a distinct separately frozen protocol in ../semantic-tool-cpu-v2/,
not a retry replacing this result. No final result or selected arm is invented here.
Audit: python -m research.audit_semantic_study --allow-incomplete.
