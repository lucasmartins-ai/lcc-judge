# Next decision: bounded fit and transfer on richer audited development data

The varied-state data phase is complete. No model has scored these inputs and
there is no new quality result. The full engine+LCC goal stays active. Do not
retune or resume any rejected old derivative, or use exposed old finals as final.

1. Implement a tested reader for frozen gzip rows/views. Reconstruct only the
   deterministic compatibility keys needed by shared training/scoring helpers:
   projected input identity and report identity, checked against saved strings.
   Preserve original files. Deduplicate50,084projected training inputs and audit
   all complete conditional quartets. Inputs are question/report strings only;
   annotations determine supervision, not runtime answers. Binary count after
   dedup is25,016negative/18,282positive, semantic UNKNOWN6,786.
2. Keep separate relevance and semantic support. Globally balance **both binary
   classes** using deduplicated counts: each class weight N/(2*n_class), zero
   relevance weight/gradient for semantic UNKNOWN. Balance supported/UNKNOWN
   independently with fixed global fractions. Keep both quartet axes and finite
   update/weight guards. A regression must prove class balance, UNKNOWN masking
   and source-input identity before freezing a new recipe. Old loss sources stay
   archived/unchanged; do not silently reinterpret previous training.
3. Freeze one development seed101, three fixed CPU/fp32 epochs, retained immutable
   mMARCO prior, classifier/last2blocks, classifierLR1e-4/tail2e-5, AdamWwd.01,
   batches16pairs/4quartets,8threads, no network/truncation. Predeclare class and
   quartet counts, all updates/token budgets and source/data/weight identities.
   One full unique-item pass then one unique-quartet pass per epoch, without
   checkpoint/epoch search. No candidate final scoring or public adoption.
4. Score validation once then train under the same validation-only frozen global
   cutoffs. Report pooled, within-goal and same-report goal-ordering, KEEP/negative
   DROP/contradiction/UNKNOWN, both query languages and both report languages.
   Success: train **and validation**, aggregate and every query/report language,
   pooled/within-goal≥.90, positive and contradiction retention≥.95, negative
   removal≥.70, semantic UNKNOWN recognition≥.95 and0UNKNOWN DROP. No quality
   inference from a data audit or high training AUC. Capture real costs and all
   failed/partial execution; no selective restart or extra losing epochs.
5. Only a promising development recipe enters fresh confirmation. Freeze new raw
   requests, complete inputs/wording and declared competing-field coverage before
   scoring any final. Current52edges/all18primitives are known; remaining cross-tool
   combinations may be reserved explicitly. Three fixed seeds must each satisfy
   the same quality policy. Unseen pair edges do not mean unseen tools/domains.
6. Qualified candidates enter new semantic LCC tasks with full/Laya/Jev controls,
   8K/32K/larger useful-dossier budgets, success≥.90, loss≤.02, removal≥.25,
   complete UNKNOWN and full cold/warm/RSS/cache/token costs. Adaptation quality
   on76token pairs alone is insufficient. Quantization/release/manuscript follow
   useful outcome measurements; P2 requires reliable independent review.
