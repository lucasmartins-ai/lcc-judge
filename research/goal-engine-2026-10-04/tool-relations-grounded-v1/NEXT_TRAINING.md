# Next decision: retained ranking prior with explicit scope and support

Historical design, written after data preparation and before candidate execution.
The subsequent [retained-ranking study](../tool-relation-support-v1/RESULTS.md)
completed all three seeds and fails. New work is in
[NEXT_DESIGN.md](../tool-relation-support-v1/NEXT_DESIGN.md); the sequence below
records the executed design, not a pending run. The engine + LCC goal remains
active; a direct-record classifier alone cannot complete it.

1. Freeze the complete executable adaptation recipe and source/model/data hashes.
   Use the already pinned multilingual ranking artifact, CPU/float32, complete
   pairs, retained output prior, and explicit three-class support. Validate the
   actual XLM-R encoder/classifier structure before choosing trainable layers.
   Declare seeds, finite epochs, trainable parameter count, optimizer, globally
   fixed class weights and thread/batch limits before any new score. No implicit
   native ModernBERT substitution or selection over the old exposed finals.
2. Use the 3,592 unique train inputs and preserve all 4,864 source-row receipts.
   Calibration is excluded. Only the two natural projected strings enter the
   model; class, field, source binding, truth and family metadata are labels or
   audit material. Structural UNKNOWN bypasses the model. Broad diagnosis,
   derivation and multifield usefulness remain semantic UNKNOWN, never negatives.
3. Before final scoring, save all selected weights and global validation-only
   support/relevance cutoffs. Relevance is the relevant-minus-irrelevant logit;
   support score is UNKNOWN minus logsumexp of the other two. They are not
   calibrated probabilities. Retain every validation semantic UNKNOWN and at
   least .95 of relevant/contradictory records in each language when selecting
   the most selective global relevance cutoff. No objective-specific final anchors.
4. Score the complete original validation/final populations. Require each seed
   and each EN/PT language pooled and within-goal AUC >= .90, positive and
   contradiction KEEP >= .95, negative DROP >= .70, semantic UNKNOWN recognition
   >= .95 and **zero UNKNOWN DROP**. Preserve every error, overflow and invalid
   update. Abort nonfinite training; no selective retries or added epochs.
   Confirm all raw score/weight/epoch/selection/math identities independently.
5. A pass supports this bounded authored direct-record contract only. Six final
   pairs are new combinations of known fields/tools; related tasks and broad
   LCC relevance remain unvalidated. Reserve fresh LCC tasks before advancing,
   including paraphrases, conflicting/healthy evidence, related derivable fields,
   ambiguous goals and complete real tool outputs. Do not count repeated rows
   or repeated dossiers as independently sampled production sessions.
6. Compare qualified candidates in LCC against full context, Laya and Jev at
   8K/32K/larger dossier sizes. Measure selected evidence coverage and actual
   task success; require success >= .90, loss versus full <= .02, removal >= .25,
   zero UNKNOWN loss. Count every submitted HF token, overflow, cold/warm latency,
   installed-process RSS and complete cache-aware executor/provider usage. Pair
   capacity is not useful dossier context. Keep representative scenario scope
   explicit; current priority is tool outputs/logs pending further user steering.
7. Only after useful quality, evaluate a smaller student/quantization and prepare
   immutable model hosting and a separate source repository. P2 admission still
   requires reliable externally referenced outcomes and independent review;
   existing rejected replay has zero admission. Publication/default changes and
   a scientific superiority claim remain separate decisions.

Extra epochs, bigger RoPE, final cutoff search and quantization of losing candidates
do not unlock the present quality decision. Keep previous failures and frozen
source snapshots intact. If this next design fails, record the outcome and revise
the problem/data evidence; do not redefine the full goal as a code-audit PASS.
