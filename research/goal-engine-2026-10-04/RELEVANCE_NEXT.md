# Next authorized cycle: align the operation before training

The goal stays active until a useful local selection candidate is measured. The
completed diagnostics reject the current candidates; they do not deliver a
replacement and do not turn a failed incident gate into a passing relevance gate.

## Narrow operation

For a stated operational objective, rank blocks containing an observation useful
to answering it. Positive evidence can be healthy, anomalous or contradictory;
an anomaly in another entity/subsystem is not positive merely because it is an
anomaly. Relevance is different from whether a selected set is sufficient or a
particular block is counterfactually necessary. The latter remain outside P1.

Start with explicit observations in supported log/config/metric schemas. Unknown
schemas, unresolved identity/window ambiguity, unsupported inference and opaque
cross-block causal dependencies remain UNKNOWN/KEEP. Do not train a broad answer
generator or restore arbitrary typed questions just to reproduce Laya's scope.

## Data contract before execution

1. Define the requested observation by entity, field and time/window. Record an
   explicit alias/source mapping when needed; avoid guessed entity equivalence.
2. Label directly supported healthy and anomalous observations as relevant. Use
   hard negatives with the wrong entity or requested field, including anomalous
   wrong-subsystem lines. Unsupported ambiguity gets an explicit unknown class.
3. Match formatting, length, log level, position and subject vocabulary across
   labels. Include lexical baselines and shortcut controls. Hide label metadata
   and decisive IDs from all model inputs.
4. Keep new P1 synthetic data distinguishable from outcome-backed P2. The current
   replay's rejected labels cannot be promoted or laundered as production truth.
5. Freeze source, train/validation/final identities and seeds before training.
   The four holdouts inspected in this cycle are exposed: reuse can diagnose,
   not confirm independently. Check both domain signatures and content hashes.
6. Count full HF pair lengths and complete observation spans during training.
   Require zero unreported truncation/evidence loss. Training exposure and native
   window must be stated separately.

## Bounded experiment

Use the accepted architecture as a control: frozen encoder versus last-two
adaptation, three matched seeds, explicit finite epochs/cost, validation-only
selection. Train a direct relevance target, not a joint incident product. Compare
lexical, official BGE, pinned Laya and the new candidate on identical inputs and
the same label/operation contract. Preserve the old incident scores unchanged.

Declare the new relevance quality gate separately before dispatch: uncut pooled
relevance AUC ≥.90, healthy-relevant recall and wrong-subsystem anomaly rejection
reported by family, complete raw errors and grouped uncertainty. No speculative
offset transform or favorable final-domain selection becomes a default.

If the candidate fails, inspect ordering versus offsets and compare with the
lexical control before another training run. A simple control winning is evidence
about the combined-system design; novelty is not required of an isolated motor.

Only a candidate with useful evidence ranking proceeds to LCC selection. Freeze
the policy before outcome evaluation: provisional bounded targets remain verified
success≥.90, loss versus full≤.02 and removed input≥.25. Report confidence intervals,
unknowns/timeouts, bytes/coverage, cold and repeated warm cost, RAM and API usage.
Batching/quantization then needs matched quality and failure regressions. A source
release remains an experimental artifact until model/policy gates pass.
