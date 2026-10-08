# Direct frozen-query representation — 2026-10-08

The preceding cached-score pilot fails even its training policy grid. Its fixed
zero-floor diagnostic reduces unsupported acceptance but loses useful correct
bindings. This separately frozen development experiment tests the approved small
support/field heads on the query encoder representation, instead of twelve scores.
No failed strings, labels, recipe or thresholds are changed in the predecessor.

Reuse the same exposed 1,172/1,136 queries and eight-field contract. Input is only
the natural question. Existing immutable mMARCO MiniLM encoder, CPU fp32, eight
threads, batch16, no truncation, max512 query tokens; mean last hidden states over
all attended tokens including special tokens, excluding padding. Freeze weights;
no gradients or encoder updates. Exactly2,308 new query forwards, <=30,000; pin
all whole-input token counts before scoring, model files/revision and code hashes.

Fit the same two independent linear heads and train-only normalizer using the
unchanged goal_support_pilot functions: zero initialization, float64, two threads,
200 full-batch Adam steps at LR.05, equal-class support BCE, supported-only field
CE and .01 mean weight penalty. Same21-quantile two-axis train-only grid and
aggregate/EN/PT >=.99 precision / >=.80 accepted and correct coverage / >=.95 UNKNOWN.
No validation fit, other seeds/checkpoints/pooling recipes or backbone selection.
No feasible train policy means abstention-only fails coverage; zero-floor results
are separate diagnostics. Stop before fresh confirmation/LCC if development fails.

All data remain authored, exposed and correlated. Literal split overlap zero
does not establish whole-family semantic novelty. A development pass requires
separately frozen fresh whole-question families, grouping translations/paraphrases,
then original complete selector gates and LCC utility/cost. No P2/default/adoption.
Independent human semantic certification is still pending.

Tasks: behavioral padding/invalid-input pooling regression RED→GREEN; full tests;
pre-inference freeze; single encoder/head execution; offline rederive head outputs,
policies and metrics from pinned saved embeddings (no repeated encoder inference);
one final fresh-context review covering both development pilots, document results.
