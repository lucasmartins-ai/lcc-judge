# Explicit observations inside LCC — bounded outcome result

Four profiles, six already-exposed authored tasks, four supported record forms, two full cl100k dossier budgets and three executor repeats: 144 actual calls. Source/data/policy freeze precedes dispatch; execution order is fixed/randomized, no selective retry. Slot retrieval and exact JSON grading are P1, not necessity/P2 or production evidence.

| Budget | Profile | Correct / attempted | Mean byte removal | Minimum observation / UNKNOWN coverage | Median warm compile |
|---|---|---:|---:|---:|---:|
| 8192 | full | 17/18 | 0.00% | 100% / 100% | 0.000 ms |
| 8192 | jev | 18/18 | 28.89% | 100% / 100% | not repeated |
| 8192 | laya | 17/18 | 0.00% | 100% / 100% | 5974.242 ms |
| 8192 | observations | 18/18 | 92.50% | 100% / 100% | 1.399 ms |
| 32768 | full | 17/18 | 0.00% | 100% / 100% | 0.000 ms |
| 32768 | jev | 18/18 | 36.36% | 100% / 100% | not repeated |
| 32768 | laya | 16/18 | 0.00% | 100% / 100% | 22170.038 ms |
| 32768 | observations | 18/18 | 98.10% | 100% / 100% | 6.547 ms |

All 144 services completed, with no executor errors/timeouts. Local and Jev each return 36/36 verified answers; both pass the declared fixed point criterion at both budgets. Full input and Laya return 34/36 and 33/36. Laya and full have identical compiled bytes; their stochastic response difference is not a causal effect of compilation. No general model/default adoption follows.

The independent audit checks archived source/data identity, exact task annotations, compiled slices/gaps, every raw final response and grade, the point gates, all 591 successful semantic call fingerprints and cached token accounting. The six-task clustered intervals are descriptive; all-success bootstrap [1,1] has no unseen-task failure bound. The executor is a mutable alias without applied generation seeds.

## Usage, including cached input

| Budget | Profile | Executor input including cache | Uncached input | Cache read | Output |
|---|---|---:|---:|---:|---:|
| 8192 | full | 168663 | 9242 | 159421 | 6710 |
| 8192 | observations | 30603 | 5793 | 24810 | 5270 |
| 8192 | laya | 168663 | 15213 | 153450 | 10925 |
| 8192 | jev | 125301 | 17190 | 108111 | 6857 |
| 32768 | full | 625002 | 94456 | 530546 | 8326 |
| 32768 | observations | 31602 | 8047 | 23555 | 5002 |
| 32768 | laya | 625002 | 95931 | 529071 | 15117 |
| 32768 | jev | 403749 | 112881 | 290868 | 8633 |

Executor totals: 2,178,585 input tokens including 1,819,832 cache-read tokens; 66,840 output tokens. Jev compilation: 591 successful calls / 602,669 recorded input tokens. The frozen summary's `observed_input_tokens` field is **uncached input only**; it is not full prompt usage. `audit.json` above reconciles all token categories. Billing rates/invoice cost are unknown; do not equate cached tokens with newly billed input.

## Supplemental cold/warm memory checks

One fixed exposed task at each budget, fresh sequential process per local profile, three passes; zero APIs. Peak RSS includes imports/runtime/model/grid. These are whole-path cost observations, not population latency or architecture superiority. Jev server/child-process RSS is unmeasured.

| Budget | Profile | Setup seconds | First compile seconds | Median warm seconds | Process peak RSS bytes |
|---|---|---:|---:|---:|---:|
| 8192 | full | 0.0000 | 0.000000 | 0.000000 | 29392896 |
| 8192 | observations | 0.1427 | 0.001733 | 0.001469 | 41992192 |
| 8192 | laya | 28.8365 | 6.411935 | 5.936115 | 5971116032 |
| 32768 | full | 0.0000 | 0.000000 | 0.000000 | 29491200 |
| 32768 | observations | 0.2549 | 0.023838 | 0.008810 | 42631168 |
| 32768 | laya | 29.3086 | 23.843049 | 22.879254 | 5968756736 |

The initial supplemental driver had incorrect LCC constructor argument names and failed before Laya scoring. The original log/partial local measurements remain in local-process-cost/ and local-cost.log; corrected measurements use local-process-cost-v1/. Original outcome sources and results were unchanged.

## Integration and limits

Prepared LCC source: src/lcc/relevance/observations.py in the separate local consumer checkout. It accepts an explicit ObservationRequest, verifies the local receipt, keeps UNKNOWN/protected blocks, preserves every kept slice/gap and keeps all candidates on missing/in valid runtime. No CLI/default promotion. Eleven integration test cases, 52 tests in the relevant LCC suite, 109 engine tests before the subsequent semantic-study tests; scoped Ruff/mypy checks and executable example pass.

Offline command: `python -m research.audit_observation_lcc_pilot`. Raw output, protocol, grid, execution order, source snapshots and sanitized ledger remain beside this report. Live rerunning additionally requires the local LCC checkout, pinned weights, Hermes/provider and private Jev bridge dependency; offline receipt audit needs none of them. The frozen protocol hashes the Hermes launcher but not its whole library or the private TypeSafe client. These provenance limits prevent a fully immutable remote-service reexecution claim.

Next: semantic-tool P1 relation study with separately frozen families, then a candidate-specific LCC outcome pilot if its gate passes. The goal remains active; a literal parser is not a broad neural replacement.
