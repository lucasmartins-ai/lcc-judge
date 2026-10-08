# Contributing

We evaluate the complete engine + LCC system. The most useful change improves task
outcomes, useful context or measured total cost while preserving evidence.
An isolated model leaderboard is not enough to establish that improvement.

Start with a small issue or experiment proposal explaining the decision it resolves.
Include the current failure, expected behavior and measurable success criterion.
Useful starting areas are independently referenced outcome fixtures, shortcut
controls, correct model baselines and cross-platform reproduction.

For code changes, reproduce the failure with a regression, apply the smallest fix,
and run the affected tests. The full suite uses the research extra and Docker worker;
receipt audits use the standard library. Changes to generated-program execution
must preserve confinement and return UNKNOWN when its runtime is unavailable.

For experiments, freeze sources, input/case identities, model/tokenizer revisions,
metric, seeds, selection rules and costs before dispatch. Keep raw scores and errors.
Evaluate a new final set after development choices; repeated tuning on the existing
probes is exploratory. Report ties, missing observations, cuts and device/backend.
Never mix probe versions, populations or checkpoints into one comparison cell.

Do not overwrite historical protocols, receipts, tensors or negative results. Archive
executed sources and sanitize call evidence into the run directory. Post-execution
corrections require their own audit and must preserve original verdicts. A ledger
export or file timestamp is not an external attestation of preregistration.

Keep task outcome ground truth separate from relevance annotation. Synthetic labels
and curated answer assertions do not automatically qualify as P2 replay data. Exact
constraints belong in executable checks; semantic judgments require a separate,
validated outcome contract. Runtime failure cannot prove that a removed block was
necessary.

Before proposing adoption, include a matched LCC outcome comparison, cold/warm
p50/p95 latency, peak/resident memory, token/input coverage and failure behavior.
Quantization or context expansion is a new condition and needs regression evidence.
The current provider is shadow-only until those quality/policy gates are passed.
