# Next bounded decision: relevance plus explicit support

Historical design, written before execution. The subsequent frozen protocol and
completed three-seed study are recorded in [the support results](../tool-role-support-v1/RESULTS.md).
All candidates fail, including UNKNOWN preservation in Portuguese. The cohort is
now exposed; the steps below describe that executed design, not a pending run.

Question: can a compact model distinguish irrelevant/relevant/unsupported on
complete natural question/report views, including Portuguese goals and false
requested measurements? This tests a changed supervision/decision contract;
an improvement would not isolate actual-tool provenance as its cause.

1. Use the fixed MiniLM encoder/tokenizer artifact, CPU/fp32, three seeds
   101/202/303, three fixed epochs, batch16, AdamW2e-5/weight decay.01. Replace
   only the scalar output with a freshly seeded three-class head; full encoder
   adaptation is the proposed candidate. Record this initialization explicitly.
   Verify the original model weight SHA before loading; the tokenizer restore
   did not restore model weights. No native ModernBERT checkpoint substitution.
2. Deduplicate by effective `(question, report)` hash **inside train only**;
   conflicting labels fail preparation. Current3676unique training views have
   classes1772irrelevant/1772relevant/132semantic UNKNOWN. The64structural UNKNOWN
   bypass the model and stay UNKNOWN/KEEP. Keep every source row as a receipt,
   do not claim3676independent tasks. Validation/final remain original cohorts.
3. Use the tested global class weights N/(3*n_class), per-item cross entropy and
   a fixed global normalization, not a batch-dependent weighted denominator.
   Labels/role ids/receipt bindings never enter the two model strings. Existing
   finite-update/checkpoint guards apply; abort nonfinite runs, preserve failures.
4. Declare score axes in advance: relevance=logit(relevant)-logit(irrelevant);
   unsupported=logit(UNKNOWN)-logsumexp(other two). They are scores, not calibrated
   probabilities. Structural failure/overflow always retains the original block.
5. Before final, freeze one global support cutoff per seed from all validation
   semantic UNKNOWN (lowest unsupported score, retaining100% validation UNKNOWN).
   Then choose the most selective global relevance cutoff preserving≥.95 of
   positives and relevant contradictions in **each** goal language. A supported
   row below the relevance cutoff is DROP; an unsupported row is UNKNOWN/KEEP.
   No per-objective normalization, final anchor search or extra epoch selection.
6. Require **each seed and each language** pooled and same-goal ordering≥.90,
   positive/contradiction recall≥.95, negative rejection≥.70; zero UNKNOWN DROP
   and≥.95semantic UNKNOWN recognition. Compute rank metrics over all binary
   pairs, not a selectively eligible subset. Declare per-source/family breakdowns;
   only three final source clusters exist, so avoid population reliability CIs.
7. Score the original frozen scalar reranker as a ranking control on the same
   views, without treating its lack of support detection as a safe DROP policy.
   Save every raw output, coverage, threshold, update/epoch, loss and weight hash;
   independent audits must pass before any candidate moves to the LCC pilot.
8. If useful, test fresh LCC outcomes at8K/32K and a larger dossier budget,
   full/Laya/Jev controls, all unsupported data preserved, success≥.90,
   loss≤.02, byte removal≥.25, complete cold/warm/RSS/cache-aware usage.
   This grants only the measured contract, not generic diagnosis or P2.

Existing compact final, retry/network/tracked-file failures remain exposed or
outside the current captured scope. Do not report this experiment as fixing them.
Additional documented captures for those relations remain a separate coverage
task, not grounds to tune this prospective final after observing its scores.
Do not quantize, expand RoPE or change consumer defaults to hide a quality failure.
