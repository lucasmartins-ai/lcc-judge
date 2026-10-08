# Retained multilingual ranking and explicit direct-record support

Previous goal turn: **progress**. Actual Retry/UDP/Git captures, fresh supervised
views, initialization invariants and 185 checks completed. No candidate quality
or full engine+LCC completion followed. No live training process carried over.

1. [x] Regress semantic UNKNOWN categories and actual XLM-R trainability before
   implementation. Audit data again before freeze; preserve historical sources.
2. [x] Freeze CPU/float32, three seeds101/202/303, three fixed epochs, batch16,
   eight threads, AdamW2e-5/wd.01; retain the scalar ranking output as a margin.
   Train only classifier and last two XLM-R encoder blocks. Record exact total,
   trainable and frozen parameter identities before execution. No new arm search.
3. [x] Execute original scalar validation control, all three finite adaptations
   and validation-only global cutoffs. Save per-update/epoch/raw failure receipts,
   full private candidate weights and selection before any final scores.
4. [x] One complete final pass per seed and scalar control; no threshold search
   or retries on final. Independently reduce raw scores, support categories,
   strict ties, per-language/family/source gates, chronology and token accounting.
5. [x] Verify private weights and frozen parameter invariants, appropriate tests,
   current source identity and honest public documentation. Preserve failures.
6. [x] If each seed/language passes, reserve and execute fresh LCC outcome/cost/
   context confirmation; otherwise record the failed candidate and revise the
   actual evidence gap. A direct-record pass alone cannot complete the full goal.

Completed result: all seeds fail, mean pooled .643959/within-goal .666233 and
negative rejection .088252; Portuguese rejection0. No UNKNOWN DROP in this cohort.
Independent raw/weight/finite-update audits pass;194tests17.940s,zero skips.
The exposed first-seed train-fit check also misses .90 and the pair graph has
nine disconnected components. See RESULTS.md and NEXT_DESIGN.md. No live process
remains; the full goal stays active with a changed objective/coverage decision next.

All three seeds and each EN/PT language must meet pooled and within-goal AUC .90,
positive/contradiction KEEP .95, negative DROP .70, semantic UNKNOWN recognition
.95, structural recognition1 and zero UNKNOWN DROP. Binary ordering includes all
binary records. Unknown broad diagnosis/derivation/usefulness keeps the block.
All fields/tools are present in train; final has new pair combinations/wording,
not unseen-source or production ground truth. No API, P2, default or publication.
