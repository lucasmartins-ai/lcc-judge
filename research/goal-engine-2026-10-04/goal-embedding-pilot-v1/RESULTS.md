# Direct frozen-query support/field pilot — 2026-10-08

## Decision

The automated claim gate returns BLOCK (support .66 / strength2.94), requiring
**INFERIDO — nao medido (falta medicao repetida ou fonte independente)**.
All new point counts/costs below retain that exploratory qualification. Independent
receipt/math review does not certify labels, causality or real-user quality.
One external Jev claim call is separate from local API_calls0; no retry.

Reject this fixed development candidate. The train-selected policy passes train
and fails exposed validation severely. Aggregate and EN/PT fail; no fresh family
confirmation, full eighteen-field selection or LCC utility benchmark follows.
Lower unsupported acceptance without retaining correct useful queries is not
success. This negative result does not disprove all support/field architectures.

## Frozen method

Protocol cbc41131673d23a9e8163fc6d878708a9707f0b8e11b7e8e1784210d94d83444.
Same immutable upstream mMARCO MiniLM revision8008f0154ca2387468013ed439df09d70c122412
and existing exposed1,172/1,136 questions. Encoder sees only the natural question;
no definitions, labels, records, units/fields or entity suffix in model inputs.
CPU fp32/eight threads/batch16, complete query window512, masked mean of last hidden
states over attended tokens including specials; padding excluded. Encoder eval
weights frozen, trainable encoder parameters0; no optimizer touches the encoder.

384-dimensional saved representations feed the same independently supervised
support/field heads and train-only normalizer as the failed cached-score pilot:
3,465 head parameters,200 finite full-batch Adam steps, float64/two threads,
LR.05, balanced support BCE and supported-only field CE plus .01 mean penalties.
Only the representation/dimension/head capacity changes jointly; this comparison
does not isolate a causal mechanism. Neither old definitions nor failed strings
are revised; no seeds/backbones/pooling/cutoff search on validation.

484 train-only grid policies; chosen support floor2.9717180328740613 and field
margin floor.0007943026185683877. Gates: accepted precision>=.99, accepted and
correct supported coverage>=.80, UNKNOWN>=.95 in aggregate and EN/PT. Floats are
learned logits/margins, not calibrated probabilities. No feasible policy fallback
can turn abstention-only coverage into a pass.

## Exploratory point counts

| Policy/cohort | Accepted precision | Supported accepted | Correct supported coverage | UNKNOWN recognition | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Train-selected / train | 235/235=1.0 | 235/256=.917969 | 235/256=.917969 | 916/916=1.0 | PASS |
| Train-selected / validation | 9/70=.128571 | 15/240=.062500 | 9/240=.037500 | 841/896=.938616 | FAIL |
| Fixed zero floors / validation | 39/216=.180556 | 78/240=.325000 | 39/240=.162500 | 758/896=.845982 | FAIL |

The actual validation policy accepts55 unsupported requests plus6 wrong direct
fields. EN:4correct/37accepted,6/120 supported accepted,UNKNOWN417/448=.930804.
PT:5correct/33accepted,9/120 supported accepted,UNKNOWN424/448=.946429.
Zero-floor output is diagnostic and not adopted. Both policies lose useful bindings.
Unconditioned field argmax also loses transfer:114/240 correct (56EN/58PT),
versus185/240 for the cached-score field head and197/240 for the original router's
direct-query decisions. No support threshold alone can restore missing field
accuracy. That is a fixed-output observation, not a cause attributed to the encoder.

All questions/labels are reused authored development data, with zero literal
train/validation overlap and correlated known primitives/templates. There is
no independent human semantic certification, fresh utterance dataset or LCC task
outcome here. Train passing does not establish held-family or real-user quality.
failure-examples.json is a post-result illustrative first-ID sample, not random.

## Execution, audit and limits

Exit0 at2026-10-08T11:20:30.397320Z.2,308 query items /145 encoder batch calls /
57,727 complete nonpadding HF tokens; no truncation, errors or selective retry.
Encoder forward budget<=30,000.3,465 trained head parameters/200 updates,
234,400 support training rows and51,200 field training rows. Head fit.811892s,
encoder load/encoding/head fit/evaluation25.592704s, peak complete process RSS
1,831,731,200bytes. Encoder memory dominates this process; no lightweight whole
engine, LCC serving or context-efficiency claim follows from a small head.
Local model execution uses0API calls; external claim gate is separate.

Pooling padding/error regression RED→GREEN; inherited objective/policy regressions
plus full suite256tests/zero skips32.248s and scoped Ruff E9/F PASS. Frozen-source
offline audit PASS verifies saved query/embedding identities, all head vectors,
train-only grid, masks/metrics, normalizer, update/cost accounting and summary/
stop action. No encoder or optimizer replay; this does not independently attest
that each embedding was measured or certify labels. The combined fresh-context
review independently reconstructs all source annotations and predictions,
policies/counts and tokenization; see INDEPENDENT_REVIEW.md. It finds no Critical/
Important code issue or label/ID/pooling fault explaining the collapse. One Minor
auxiliary start/load metadata guard gap is deferred; current files are coherent
and bound in the overall source manifest. Per-pilot audit omissions remain.

Reproduce offline with no encoder inference:
`python -m research.goal_embedding_pilot --phase audit`.
Raw embeddings/head/training/policies/metrics and executed source archives are
preserved; `--phase run` refuses another start. No default/P2/publication promotion.

## Next decision

Do not add epochs/seeds or lower precision to hide the loss of useful coverage.
Prepare a separate development population of complete goals before more training:
independent whole-family IDs, EN/PT translations/paraphrases grouped, supported
and unsupported requests sharing surface frames, field/unit contrast cases and
ambiguity kept UNKNOWN. Keep the original197 correct direct decisions as a fixed
control while isolating support improvement. Freeze train/calibration/validation
and future confirmation families before fit; exposed populations remain diagnostic.
Use genuine LCC requests when available and identify authored substitutes clearly.
Human label review is pending. This data/contract work is the next proposed step;
no additional training or fresh confirmation was executed in this phase.
