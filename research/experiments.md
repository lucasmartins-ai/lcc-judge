# Experiment Log

Current state: **Sprint 2 quality gate fails; CPU M8 per-block target fails; real replay
executed, proposed reliability fails; zero P2 training admission**.
Verifier challenge calibration completed2026-10-04: provisional per-kind targets pass
on108 reserved controls; its2 PDB false negatives remain in the historical result.
New separate PDB recipe reaches0FP/0FN/0UNKNOWN on112 curated controls. This is a
point observation (gateClaim DOWNGRADE); external references and R19 remain open.
Latest evidence: `research/goal-engine-2026-10-04/REPORT.md`. Useful replacement work
remains incomplete; the preceding goal checkpoint reports `usageLimited`, while
the current2026-10-08 query returns no active goal (`goal: null`). An already
launched local final evaluation completed and rejected all candidates. Subsequent
saved-logit diagnosis and a bounded wording pilot are complete; that pilot also
fails. The semantic task/goal-binding review led to a frozen eight-field contract
and one complete goal-only development probe. Neural and lexical router gates
fail; fresh confirmation, full field selection and LCC outcomes are not executed.
Subsequent separately supervised support/field heads on cached scores and direct
frozen-query embeddings also fail. The latter passes train but binds only9/240
supported validation questions correctly and accepts55 unsupported requests.
New point claims receive BLOCK with the required inference qualification; human
semantic review and useful replacement remain open. No adoption. Previous ACTIVE
statements are historical.
Previous continuation: `research/audit-2026-10-03/AUDIT_RESOLUTION.md`.
Historical EXP-03/04 use their original corpus, probe cohorts and execution recipe.

Format per program §38: every experiment records hypothesis, configuration, dataset,
model, tokenizer, context length, training method, seed, hardware, metrics, result,
interpretation and decision. No important result exists only in terminal output.

---

## EXP-2026-10-08-04 — Separate query support/field heads fail development transfer

**Hypothesis/configuration:** teach applicability separately from field identity
before another complete selector or LCC outcome. First use twelve existing frozen
query/definition logits, then a separately frozen direct-query representation.
No validation fit, old definition edits, model/backbone/pooling search, extra seeds
or encoder updates. Same train-only per-column normalization, binary support BCE
balanced equally across classes, field CE on supported queries only, .01 mean
weight penalties; zero initialized heads, CPU float64/two threads,200 full-batch
Adam steps/LR.05. Same484 two-axis train policies, requiring aggregate/EN/PT
precision>=.99, accepted and correct coverage>=.80, UNKNOWN>=.95. Final update only.

**Data:** unchanged exposed authored1,172/1,136 unique train/validation questions,
256/240 supported,916/896 UNKNOWN. Labels/records/entities never enter neural
inputs. Zero literal overlap; known primitives/templates/correlated wordings
remain. These are development diagnostics, not fresh family or human certification.

**First protocol/model:** a1aae8e09162455ec94e162bf36c09daf3cad0cd7e734eef062af38e6227bb91,
117 trained parameters on12 cached logits, no encoder loading/tokenization/new
inference. No feasible training policy. Actual null policy abstains all and fails
coverage. Fixed zero-floor validation diagnostic:139/369 accepted correct,
172/240 supported accepted,139/240 correct coverage,UNKNOWN699/896;197 unsupported
accepts. Reducing the original808 unsupported accepts also loses original197
correct bindings. This diagnostic is not adopted. Fit1.794550s, cached fit/eval
2.867838s after train input load, peak382,173,184bytes; predecessor encoding cost
excluded. Exit0 at2026-10-08T11:11:22.812835Z.

**Second protocol/model/tokenizer:** cbc41131673d23a9e8163fc6d878708a9707f0b8e11b7e8e1784210d94d83444,
same immutable upstream mMARCO MiniLM/revision8008f0154ca2387468013ed439df09d70c122412.
CPU fp32/eight threads/batch16, whole query window512/max40train/46validation,
masked mean over attended last hidden states including specials/excluding padding.
Input query only. Frozen encoder has0trainable parameters;384-dimensional features
feed3,465 head parameters. Representation/dimension/capacity change jointly.
2,308 query items/145 batches/57,727 HF tokens, all complete; no errors/cuts/retries.
Head fit.811892s, encoder-load/encoding/head-fit/evaluation25.592704s, peak whole
process1,831,731,200bytes.200 finite updates,234,400 support/51,200 field head-row
exposures per pilot. Head size does not establish lightweight whole-engine serving.
Exit0 at2026-10-08T11:20:30.397320Z. Both local executions use0API calls.

**Point results:** second train policy passes235/235 accepted correct,
235/256 supported/correct coverage,UNKNOWN916/916; nine train-grid policies pass.
Selected support floor2.9717180328740613, field margin floor.0007943026185683877.
Fixed validation fails9/70 accepted correct,15/240 supported accepted,
9/240 correct coverage,UNKNOWN841/896.55 unsupported accepts and6 wrong direct
fields. EN4/37 accepted correct,6/120 supported accepted,UNKNOWN417/448;
PT5/33,9/120,UNKNOWN424/448. Zero-floor diagnostic39/216 accepted correct,
78/240 supported accepted,UNKNOWN758/896, not adopted. Unconditioned field accuracy
114/240 (cached-head185/240, original197/240) shows field failure as well as support
abstention. No causal flaw or universal architecture limitation follows.

**Verification/limits:** source/input/weight/policy/metric/summary audits PASS,
no encoder or optimizer replay. One fresh-context reviewer independently rebuilds
all11,136/5,568 source annotations, normalized matrix predictions, all484 policies,
cohort/family confusion metrics and tokenization. No implementation/ID/pooling
error identified explaining collapse. Objective/policy/padding regressions
RED-to-GREEN; full suites255/256tests0skips22.745/32.248s, scoped Ruff E9/F passes.
One Minor auxiliary start/load metadata guard gap deferred; current records are
coherent and pinned in overall manifest. Human semantic certification and serving
remain unavailable. One external Jev claim-gate call, no complete remote token/
cache/cost reconciliation established; automated MEASURED BLOCK (.66 support /
2.94 strength), required **INFERIDO — nao medido (falta medicao repetida ou fonte independente)**.
No retry; all new point observations retain that qualification.

**Decision:** reject both candidates, retain original197/240 control unchanged.
No fresh confirmation, full eighteen-field selection/LCC utility, provider/default
change, P2 admission or release promotion. Next prepare complete goals with
matched supported/unsupported frames, semantic field contrasts and UNKNOWN
ambiguity; group translations/paraphrases under whole-family IDs before splits,
reserve confirmation, use actual LCC requests where available, review labels.
No more epochs/seeds/lowered precision or backbone changes to rescue these pilots.
Broad efficient/useful replacement remains incomplete.

Evidence: [cached-score receipts](goal-engine-2026-10-04/goal-support-pilot-v1/RESULTS.md),
[query-embedding receipts and independent review](goal-engine-2026-10-04/goal-embedding-pilot-v1/RESULTS.md),
immutable protocol/head/training/calibration/train-validation results/audit files,
raw embeddings, source archives and claim-gate receipt in their respective folders.
Offline reproduction: `python -m research.goal_support_pilot --phase audit` and
`python -m research.goal_embedding_pilot --phase audit`.

## EXP-2026-10-08-03 — Frozen eight-field goal-only routing fails

**Hypothesis/configuration:** one query-only interpretation of eight public
source fields may separate direct requests from unsupported goals before source
selection. Freeze units, scope, accepted questions and twelve bilingual candidate
definitions before scoring. Unique argmax of the same raw single-logit scores;
unsupported winners and exact ties return UNKNOWN. No thresholds, definition
search, training, extra seeds, backbone/window change or product adapter.

**Data/splits:** existing exposed wording-pilot train/validation only, with caller
entity suffix removed and targets/record annotations separate from inputs. All
64/32 original raw fixtures recounted. Deduplicate (language, natural question):
1,172/1,136 questions, 256/240 supported and 916/896 UNKNOWN, zero literal overlap.
Structural-UNKNOWN direct queries remain supported where the field is registered;
out-of-registry requests remain UNKNOWN. Authored correlated families are not
fresh confirmation or independent human ground truth; no final data is scored.

**Model/tokenizer/hardware:** unchanged upstream mMARCO MiniLM revision
8008f0154ca2387468013ed439df09d70c122412, SHA-pinned local files and tokenizer.
CPU fp32, eight threads, batch16, complete pair window512/max actual152, no cuts.
Inference uses frozen eval weights; no optimizer/seed adaptation. All sources,
inputs/annotations, definitions and full input lengths pinned in protocol
20ebddaaba6dadecee2a8d05600a72408058f3e127f4dbccb12085f8c57fd7d0.
Lexical control reuses the existing ASCII content-word overlap on identical strings.

**Point results:** validation neural accepted precision197/1048=.187977,
supported acceptance240/240=1.0, correct binding197/240=.820833 and UNKNOWN
recognition88/896=.098214. It accepts808 unsupported and43 wrong direct fields.
Lexical precision.233456, supported coverage.687500, correct coverage.529167,
UNKNOWN.577009. Both aggregate/EN/PT gates fail: precision≥.99, supported
coverage≥.80, UNKNOWN≥.95. Semantic-only neural UNKNOWN85/864=.098380; only3/32
out-of-registry requests abstain. Accepted coverage alone supplies no success.
These are routing counts, not AUC or full eighteen-field selection metrics.

**Execution/cost:** all27,696 declared local pairs and2,949,948 nonpadding tokens
reconcile counted/submitted/completed/valid. Train/validation scoring102.567/99.615s,
setup3.354s, whole-probe peak RSS1,832,255,488bytes. Exit0 at
2026-10-08T10:15:36.896834Z, zero inference errors/cuts/local API calls. These are
complete probe costs, not LCC serving or replacement economics. One separate
external Jev claim-gate call lacks token/cache/cost accounting in its receipt.

**Verification/qualification:** frozen core receipt audit and additive summary
checks pass with zero new forwards. One fresh-context reviewer independently
rebuilds inputs/argmax/lexical reductions/masks/metrics/accounting. Its one
summary-audit gap is regraded Important: false summary quality/next action could
bypass a failed development gate. One RED→GREEN guard preserves frozen sources;
252 tests/zero skips16.665s and scoped Ruff E9/F pass. Human semantics remain
pending. Automated MEASURED claim gate BLOCK (.82 support /2.04 strength), required
label **INFERIDO — nao medido (falta medicao repetida ou fonte independente)**;
receipt preserved, no retry. Receipt/math review is not scientific certification.

**Decision:** reject this fixed zero-shot routing recipe. Stages1/2 complete;
stages3/4 not executed by the frozen stop rule. No fresh question confirmation,
new LCC outcomes, provider/default changes, P2 admission or release promotion.
Separately supervised query support and field identity is the next bounded
hypothesis to specify; no such training is executed here. Do not rescue this
exposed development set by cutoff/definition search, epochs, seeds or new backbones.
Full engine+LCC usefulness remains incomplete.

Evidence: [contract, results, stopping rules and limitations](goal-engine-2026-10-04/goal-interpreter-probe-v1/RESULTS.md),
`{protocol,summary,audit,audit-summary-supplement,result-claim-gate}.json`, immutable
`train/validation-{inputs,annotations,scores,metrics}.json`, `INDEPENDENT_REVIEW.md`
and regression/full-suite logs in that folder. Offline reproduction:
`python -m research.audit_goal_interpreter_probe`.

## EXP-2026-10-08-02 — Semantic goal review and a bounded interpreter proposal

**Question/hypothesis:** does decomposing goal interpretation and source-field
selection offer a cheaper, inspectable next test after failed pair-model transfer?
This review does not test the new architecture or establish a causal failure mode.

**Data/method:** exposed wording-pilot train/validation inputs, all 96 original
author-created Retry/UDP/Git fixtures, and frozen validation scores/cutoffs.
A fixed sample covers eight fields × two query languages × six strata: 96 cases
selected by saved IDs, with positives preferring contradictions and negatives
preferring measured values. All four actual DROP rows are supplemental. Review
all 100 cases against tool definitions; no conflicting authored question targets.
No definite swapped field label was found in the 32 binary coverage cases.
Potential caption/unit/scope ambiguity is recorded, not asserted as the cause.

**Local receipts:** two separate count paths give 256/240 distinct direct
train/validation questions among 11,136/5,568 rows, after removing entity scope.
Semantic UNKNOWN covers derivation/diagnosis/broader usefulness; structural
UNKNOWN can have a valid direct-field goal and malformed record. Model input
has natural goal/caption/value, with field/unit only in diagnostic bindings.
The unchanged UTC typed API returns UNKNOWN for all 5,568 pilot validation
records in a schema-only probe, with zero DROP and preserved original text.
Its one literal request uses explicitly synthetic UTC, not capture timestamps.

**Verification/limits:** stdlib checks, no local tokenizer/model invocation, no new
training/epochs/seeds or execution of raw tools; local research-model forwards
zero. One supplementary external Jev claim-gate call has no token/cache accounting
in its receipt; it is not model-quality or independent semantic-label evidence. A temporary
output reproduces the protocol, summary and all cases apart from creation times,
checking 20 pinned input/source hashes. Extractor self-check and scoped Ruff E9/F
pass. No new full-suite run; 247 tests is the preceding phase's result. Same-agent
semantic review is not independent human labeling. The automated claim gate
returned BLOCK, support .65, for the combined counts/compatibility statement as
MEASURED, requesting repeated measurement or an independent source. Preserve
the receipts and use its required inference label; no selective gate retry.

**Decision/proposal:** freeze eight public source-field definitions and separate
question support from record validity; run one goal-only development probe with
the existing immutable multilingual reranker plus lexical controls, at most
30,000 local pair forwards and no adaptation. Proposed router targets: accepted
precision ≥.99, supported coverage ≥.80, semantic UNKNOWN recognition ≥.95.
Confirm on fresh whole query families before full selection or LCC outcomes;
original semantic/outcome/P2 gates remain. Source adapters may not use gold roles
or fabricate UTC. Efficiency and improved quality are hypotheses. No production
code, default, P2 admission, release or new model adoption.

Evidence: [review and ordered stopping rules](goal-engine-2026-10-04/semantic-goal-review-v1/REVIEW.md),
`{protocol,summary,cases,independent-count-check,compatibility-probe,verification,result-claim-gate}.json`
in the same directory. The original pilot and final confirmation remain rejected.

## EXP-2026-10-08-01 — Saved-final diagnosis and bounded wording pilot rejected

**Hypothesis:** whole goal-wording families on difficult known distinctions may
improve exposed development transfer. The preceding zero-forward diagnosis
reproduces the original final metrics; support AUC for 101/202/303 is
.822646/.849480/.766815. At original support cutoffs, final-fitted relevance
cutoffs preserving retention reject .370047/.404361/.346890 of negatives while
dropping 132/140/75 semantic UNKNOWNs. Preventing those drops lowers rejection
to .019518/.075534/.096737. Original scores/cutoffs are preserved. These are
exposed diagnostics, not adoption policies or a complete two-axis optimum.

**Data:** reuse actual 64/32 Retry/UDP/Git author fixtures, four pairs and eight
known relevance fields; all 18 fields remain in semantic UNKNOWN. Four whole
goal phrases per field/language/split and disjoint frames/UNKNOWN wording; report
captions remain known. Train/validation: 11,136/5,568 correlated rows and
10,434/5,304 unique projected inputs. Raw/projected maxima 131/71 and132/74 HF
tokens, zero overlap/cuts; independent raw/label/tokenizer audit passes. Scope,
class mix and workload change jointly, so this is not an isolated wording effect.

**Configuration:** one fixed seed101, three finite epochs, immutable mMARCO
multilingual MiniLM revision `8008f0154ca2387468013ed439df09d70c122412`; CPU fp32,
eight threads, macOS arm64/Python3.14.3. Last two blocks and classifier, batch16 /
four quartets, balanced classification plus conditional ranking, pair window512.
AdamW head LR1e-4 / tail LR2e-5. Actual 2,649 accepted updates / 42,318 training
pair presentations / 1,796,904 nonpadding tokens. Epoch times96.056/93.671/98.328s.

| Result | Train | Validation | Scalar validation, shadow |
| --- | ---: | ---: | ---: |
| Pooled AUC | .840858 | .625629 | .586981 |
| Within-goal AUC | .870361 | .694824 | .644043 |
| Positive retention | .937988 | .998047 | 1.000000 |
| Contradiction retention | .928571 | .997573 | 1.000000 |
| Negative DROP | .000000 | .001953 | .000000 |
| Binary UNKNOWN | .968994 | .998047 | 1.000000 |

Both trained policy gates fail. Semantic/structural UNKNOWN recognition is1.0,
UNKNOWN DROPs zero. Validation emits zero explicit KEEP, 2 positive and2 negative
DROP, and1,022 positive and1,022 negative UNKNOWN. Scalar uses identical inputs
and has no DROP authority. No new final or semantic LCC outcomes are evaluated.

**Accounting and integrity:** total local evaluation22,016 forwards /940,508
tokens including scalar. Exit0 complete at2026-10-07T23:10:02Z (local Oct8).
Summary peak RSS2,151,464,960 bytes precedes scalar; full-run/serving peak is
unmeasured. The producer's relative data path was wrong (`..` instead of `.`).
First full-audit failure is preserved. Execution used the fixed SHA-checked DATA
path. The additive auditor verifies all frozen data hashes with an explicit
erratum; original protocol/source/weights/scores remain unchanged. Future
producer corrected; red/green regression saved. Independent math/order/epoch/
calibration/private-weight/scalar/chronology audit passes with zero forwards.
247 tests / zero skips in17.904s and scoped Ruff pass. The separate Jev claim
gate PASS0.90 supports only completed finite epochs and the observed validation
failure, not quality or causality; receipt in `study-v1/result-claim-gate.json`.

**Decision:** reject the pilot; no more seeds, epochs or final from this recipe.
Review semantic scope and goal binding, then freeze a controlled development
experiment. Unchanged quality/outcome/P2 gates still apply. No adoption, default
change or release. The goal tool remains `usageLimited`; useful replacement is
incomplete. Immutable protocol identities: diagnosis `a000415a32264fc43686f29b89ae833c03effa880bb1928661684e96d9491f37`,
data `94a3b391162767f1f3df9bc422c4200a758a627b76f4f9098821305237151d80`,
study `f037d5d067aee03c03b4a6941dd4e816c1e4f23c19f99482de8d17390ae96461`.
Evidence: [diagnosis](goal-engine-2026-10-04/varied-relation-confirm-v1/failure-diagnosis-v1/RESULTS.md),
[pilot receipts](goal-engine-2026-10-04/wording-development-pilot-v1/RESULTS.md),
[redirect](goal-engine-2026-10-04/wording-development-pilot-v1/NEXT_DESIGN.md).

## EXP-2026-10-07-01 — Fresh confirmation complete; all three candidates rejected

The fixed fresh confirmation has64new authored Retry/UDP/Git fixtures/1,152
actual primitive fields. All18field meanings/three tools remain known;101new
cross-tool pair edges and52known-edge wording controls. Source-bound original
captures execute once; excluded calibration remains excluded. An additive Git
X/Y/index-wording correction was frozen in design-v2 before row derivation and
any model inference, with original capture declaration unchanged.
Supervision protocolc0a33bb29f8c1eaa95c68802ddfe2b7d654aac6e7f72fa22c9b69d9470d41640:
163,712correlated rows/120,220distinct projected inputs, raw/projected maxima
147/84tokens, zero cuts and zero development overlap. Independent full-token
audit PASS. Initial receipt audit failed only on JSON integer/string UDP-map key
comparison; additive auditor correction preserved original data/source/failure,
not a recapture or model-quality retry.

Original seed101 reused. Independent202/303 use the immutable mMARCOmMiniLM
revision8008f0154ca2387468013ed439df09d70c122412, CPUfp32/eightthreads,
batch16/4quartets, last2blocks+classifier, three fixed epochs and unchanged
balanced independent-support/conditional objective, classifierLR1e-4/tail2e-5.
Each completes18,819finite updates/301,068training pairs/11,667,693tokens and
90,240development evaluation forwards/3,592,064tokens.202/303training epoch
times2567.044/2268.376s; study peakRSS2,470,051,840/2,494,398,464bytes includes
training/loading. Both exit0; independent update/metric/cutoff/privateweight
audits PASS. Validation pooled.966275/.968888, within-goal.976450/.978966,
negativeDROP.826998/.832407, binaryUNKNOWN.176983/.134878, semantic/structural
UNKNOWNrecognition1.0 and UNKNOWN DROPs0. Retention includes KEEP and UNKNOWN.
All development query/report-language gates pass; this is development, not
fresh-final or useful LCC certification.

The unexecuted final scorer had wrong coupled support, absent projected hash,
missing subset UNKNOWNs and repeated scalar controls. Red regressions preserved;
corrected before any final forwards by reusing complete-input/failure-accounting
helpers.243tests/0skips15.288s, scoped Ruff E9/F PASS. Every candidate weight,
validation-only cutoff, audit, source and fresh data hash is locked before final.
Evaluation protocol19e779f288b384d7d4169149b21a05f604547d58621e6ccc58fe4949648e26fb
started2026-10-07T20:44:00Z in one detached fixed local process.101,202,303 then
one scalar control; all15slices per seed required, no averages rescuing failures.
Evaluation finished21:12:19Z, exit0, all four populations complete. Actual final
cost480,880unique pair forwards/24,255,452nonpadding tokens,1699.060s elapsed;
peakRSS3,795,386,368bytes includes dataset/receipts/reduction, not isolated serving.
No cuts/errors. Independent stdlib final audit PASS validates evidence and all
reductions with0additional forwards. Every candidate/slice policy FAIL: pooled
.858590/.870348/.850205, within-goal.886508/.895157/.879500, positive retention
.556436/.655497/.593073, semanticUNKNOWN recognition.699074/.703993/.518953,
UNKNOWN DROPs1568/1220/1716. Scalar shadow pooled.874211 exceeds all three overall;
all its records remain UNKNOWN and it has no DROP authority. Reject adoption.
Next diagnose saved logits, then freeze separate wording-diverse development and
untouched confirmation. No extra epochs/final fitting/default/P2/publication.
The Jev claim gate PASS applies only to completed epoch/receipt integrity.
Full replacement remains incomplete; the goal tool reports usageLimited.
Evidence: [current state](goal-engine-2026-10-04/varied-relation-confirm-v1/STATE.md),
`seed202/audit.json`, `seed303/audit.json`, `supervision-v1/audit-corrected-v1.json`,
`evaluation-v1/protocol.json`, `launch.json`, `started.json`, fixed run stdout/stderr.

## EXP-2026-10-05-05 — Balanced varied-state development passes; fresh confirmation required

Frozen protocolb8240c1a93f70508e6f7a40d8590e4c408aa82b51e36a8b417b894d121713588
binds v1 interruption audit bySHA. Preflight independently proves same immutable
model/data/seed101/3CPUfp32epochs/loss/LR/gates; new output/weight destination,
not false resume without checkpoint or selection on quality. Prior recorded cost
2426updates/38816pairs/1526283tokens retained as partial lower bound. New declared
18819updates/301068pairs/11667693tokens,50084items/12568quartets.

Fixed source-checked POSIXsupervisor launches once with own session/file stdio;
actual supervisor50655PPID1/PGID50655andchild50657 remained live after launcher exit;
execution completed2026-10-05T09:54:28Z with exit0.
Initial status compared executable paths and falsely saidSTOPPED after macOS
resolved Python; real process checks prevented a restart. Additive PID/birth/fixed
module observer passes regressions/actual checks; frozen study bytes unchanged.
First1798saved updates match v1 inputs/loss/counts exactly,0extraforwards; not a
quality result or independent observation.230tests/0skips22.804s,scopedRuffPASS.
Three completed finite epochs:18819updates/301068pairs/11667693tokens, rechecked
against accepted-update totals/budget; third finished2026-10-05T09:42:22Z. Runtime
frozen hashes and independent final weight bytes match the immutable base.
Direct training_meta and weights saved before evaluation; validation/train
evaluation completed90,240forwards/3,592,064tokens,0cuts/errors. Train/validation
pooled.983074/.968897,within-goal.988845/.977276; validationnegativeDROP.810472,
semanticUNKNOWNrecognition1.0 and0UNKNOWNDROP. Both exposed gates pass every
query/report language. Preservation includes UNKNOWN (validationbinary.389235).
Known fields/tools/pairs/wording and correlated author fixtures are development,
not fresh final/LCC outcomes. Recipe/data changes are not a causal ablation.
Epoch time3818.791s/evaluation716.882s; process peakRSS2,506,162,176bytes includes
training/loading. Recorded prior+v2training339884pairs/13193976tokens is a lower
bound. Independent metric/order/calibration/privateweight and lifecyclecost auditsPASS.
After actual completion, current status delegates to the existing observer;
archived executed sources remain unchanged and execution guards stay strict.
232tests/0skips19.919s,scopedRuffPASS. Proceed to reserved fresh3seedconfirmation;
no extra development epochs, default/P2/hosting/publication. Full goal ACTIVE.
Evidence: [results](goal-engine-2026-10-04/varied-relation-dev-v2/RESULTS.md),
`protocol.json`, `preflight-audit.json`, `launch.json`, `child-process.json`,
`first-verified-observation.json`, `partial-prefix-consistency.json`.

## EXP-2026-10-05-04 — Balanced varied-state conditional development (incomplete)

ProtocolSHA c789b0e1a023a426609876a8e060d79c698b2836609122debeaeff50e04a0d94
freezes before execution. Same retained immutable mMARCOprior/last2classifier,
117.6Mtotal/3.7Mtrainable, CPUfp32/eightthreads/seed101/threefixedepochs,
classifierLR1e-4/tail2e-5/AdamWwd.01,batch16/4quartets. New audited development
input50084uniqueitems/12568quartets; classcounts25016negative/18282positive/
6786UNKNOWN. Relevance BCE globally balances both deduplicated binary classes;
UNKNOWN has zero relevance gradient and separate balanced support. Both conditional
axes remain. Data/coverage/lossbalance change together, no causal attribution.
Independent pre-execution source/input/budget auditPASS:18819updates/301068pair
presentations/11667693nonpaddingtrain tokens declared.225tests/0skips25.125s and
scopedRuffPASS. Efficient exact global validation cutoff agrees with independent
candidate scan and requires query/report language retention constraints.

Original execution started2026-10-05T08:15:02Z, network denied/local artifacts.
It is genuinely stopped: session71556 disappeared, no matching actual process.
Exact exit signal/cause unavailable. Independent ordered partial receipt recount:
2426accepted updates/38816recordedpairs/1526283nonpaddingtokens, a recorded lower
bound. **Zero completed epochs, weights/checkpoint, validation or quality result.**
No numerical exception was recorded, and no quality failure is inferred. Preserve
all prior receipts. Separate source/protocol/destination infrastructure continuation
starts from the same immutable base; data/seed/recipe/gates remain unchanged.
Evidence: [active execution state](goal-engine-2026-10-04/varied-relation-dev-v1/STATE.md),
`protocol.json`, `preflight-audit.json`, `started.json`, `accepted-updates.jsonl`.

## EXP-2026-10-05-03 — Varied actual states, bilingual connected development data

**Question and scope.** Can the next development population repair the measured
state/wording/graph coverage gaps before more adaptation? No model-quality test
yet. All tools/18primitives/52pair edges/known vocabulary occur in train;96author
fixtures are not production sessions or90,432independent observations. Broader
derivation/diagnosis/general relevance remain UNKNOWN, not binary negatives.

**Frozen execution.** New confined fixed worker, Linuxarm64/Python3.13.16,
Git2.47.3/Tenacity9.1.4; seed442600calibration16excluded,442601train64,
442602validation32. Worker sourceSHA5ded8f3bdf45d3e420c889d15e8dd38b2e95a631b2209eab0ab931f6638717a3,
dependencySHA255600482631fdd1a04f299af2f0f1e748d783caafa896bdee322fce18f099bf.
Two parent-image build attempts fail before any capture; both retained. Successful
third build uses original immutablePythonbase and checked offline blobs. Build
network flag governs RUN, not all metadata resolution. No host execution/install.
Each original capture executes once. Expected retry exhaustion is observed;
infrastructure failure would be UNKNOWN. Bounded UDP reads do not prove loss;
Git changes include staged/worktree deletion/addition/clean/mixed states.

**Data result.** Rawcalibration288fields/train1152/validation576 match independent
callback/time/payload/Gitblob/status audits; fixture intersections0. Train/valcapture
1.934019/1.242572s, excludedcalib1.024674s. All18roles form one52edge component,
degrees3..8. Independent32way goalalias/caption/reportlanguage factorial, both
querylanguages; semantic UNKNOWN covers all18roles/three kinds. Received-counter
language was qualified in design-v3 before labels; earlier declarations preserved.
SupervisionSHA b921938d794b597e068a25aad7375d7968e49d18a8d463e12219163626371c05:
60,288/30,144rows,50,084/23,692unique projected inputs. Unique trainclasses
25,016negative/18,282positive/6,786UNKNOWN. Numeric multisets balanced pergoal;
11,828/5,920relevantcontradiction rows. Zero content/effective/entity split overlap,
duplicate label conflicts or cuts. Exact local mMARCOtokenizer revision8008f0154ca2387468013ed439df09d70c122412:
rawpair maxima138/137,projected76/76,512window. No model scores/adaptation/epochclaim.

**Decision and verification.** Data integrity/coverage PASS, model quality untested.
221tests/0skips16.880s and scopedRuffF/E9PASS. ZeroAPI/model/P2/default/hosting/
publication. Freeze a new bounded development reader/global binary-balanced loss
and source/data/weight recipe; measure fit ANDtransfer under unchanged gates.
Fresh confirmation and full semantic LCC useful8K/32K/cost still required.
Evidence: [results](goal-engine-2026-10-04/tool-relation-states-v2/RESULTS.md),
`cohort-audit.json`, `design-audit.json`, `supervision-v1/{protocol,coverage,audit}.json`
and [next recipe](goal-engine-2026-10-04/tool-relation-states-v2/NEXT_TRAINING.md).

## EXP-2026-10-05-02 — Independent support and conditional ranking fit train, fail transfer

**Question and development recipe.** Can separating UNKNOWN from binary relevance
and requiring both conditional axes repair the observed train-ordering failure?
SHA `f5036631a3fff8e2bad9e0659be83f00e0962755012fc19b8feddc06b85d65a5`, frozen
before adaptation at2026-10-04T23:53:45Z (October5local). Same pinned multilingual
XLM-R, retained scalar prior,117,641,859total/3,697,923trainable parameters, classifier
and last2blocks. CPU/fp32/eightthreads, seed101/threefixedepochs/AdamWwd.01,
classifierLR1e-4/tail2e-5. Loss and head LR change together; no causal ablation.
One unique-item factorized BCE pass and one unique quartet softplus pass per epoch.
Relevance targets exclude semantic UNKNOWN; its independent support logit no longer
competes through three-class CE. Quartets demand diagonal wins in both directions.

**Exposed data and complete execution.** Original train/validation only, already
exposed and authored. 3,592unique items/1,002unique quartets; no original final
model scoring or fresh confirmation. Threefiniteepochs/1,428accepted updates,
22,800pair presentations/785,304nonpaddingtrain tokens,225.970s summed epochs.
Validation then train each scored once:6,600validforwards/232,194tokens,0cuts/errors.
Independent logit2support is rederived from the same persisted logits with0extra
forwards; auxiliary legacy logsumexp scores remain preserved separately.

**Result.** Trainpool.9763096939/within-goal.9722222222/same-reportgoal.9756944444,
but validationpool.5563445752/within-goal.6134259259/same-reportgoal.5960648148.
Train/valnegativeDROP.011285/.012731 and binaryUNKNOWN.534071/.781829. All semantic
UNKNOWN are recognized,0UNKNOWN DROP; most binary valrecords are preserved as
UNKNOWN. Global cutoffs fitted only on that exposed validation are used unchanged
on train. EN/PTvalpool.553203/.550754,within.659722/.567130,rejection0/.025463.
Both exposed policy gates fail. High train AUC does not demonstrate transfer or
useful removal. No additional cutoff/epoch search. The gap does not isolate wording,
coverage, learning rate, support objective or capacity as a cause.

**Audit/cost/decision.** Independent stdlib source/input/raw-axis/math/calibration/
update/epoch/chronology and base/private derivative/frozen-byte auditPASS,0forwards.
Whole study-processRSS1,999,126,528bytes includes training/loading/runtime, not
deployed memory or LCC latency.199tests pass0skips19.210s,including localLCC;scoped
Ruff0.16.10F/E9PASS. Model is development-only and rejected, not a final candidate.
Next: broaden audited wording/language/support and connect competing-field coverage,
vary actual tool fixture states, then freeze fresh confirmation before selection.
No extra epochs/final anchors/quantization/RoPE/outcomes on this derivative.
ZeroAPI/P2/default/hosting/publication; full engine+LCCgoal active.
Evidence: [completed development receipts](goal-engine-2026-10-04/factorized-relation-dev-v1/RESULTS.md),
`audit.json`, `protocol.json`, `training_meta.json`,
[next coverage](goal-engine-2026-10-04/factorized-relation-dev-v1/NEXT_COVERAGE.md)
and `artifacts/factorized-relation-dev.json`.

## EXP-2026-10-05-01 — Retained multilingual ranking fails direct-record confirmation

**Question and frozen recipe.** Does preserving the scalar ranking prior while
training explicit support and two encoder blocks repair conditional field ordering?
Protocol SHA `f28b63f52d46f8ad6f3d974b383f9edd81cc84184383965f81b3bea29669fe4e`,
frozen 2026-10-04T23:13:37Z (October 5 local). Immutable multilingual XLM-R
`mmarco-mMiniLMv2-L12-H384-v1@8008f0154ca2387468013ed439df09d70c122412`;
117,641,859 total / 3,697,923 trainable parameters. Classifier dense/output and
last two blocks trained; embeddings/first ten blocks stay frozen and in eval.
Retained relevant-minus-irrelevant scalar margin, separately seeded UNKNOWN row.
CPU/fp32/eight threads on macOS26.6.2 arm64, Python3.14; seeds101/202/303,
three fixed epochs, batch16, AdamW2e-5/wd.01, global class-weighted CE. Original
multilingual scalar control uses the identical complete pairs in shadow only.

**Data and execution.** The preceding actual Retry/UDP/Git corpus supplies
4,864/1,824/2,496 rows, 3,592 unique training pairs with classes1,724/1,724/144.
All three broad/derived/diagnostic semantic UNKNOWN categories are counted after
a pre-training regression fix; structural UNKNOWN bypasses the model. Nine
finite epochs, 2,025 accepted updates, 32,328 pair presentations and 1,111,464
nonpadding training tokens. Summed epoch time326.778s; validation/final candidates
plus scalar control16,992 valid pair forwards/658,792 tokens, zero cuts/errors.
All weights and validation-only global cutoffs freeze before any final scoring.
Full study-process peak RSS3,520,970,752bytes includes training/loading/runtime,
not installed deployment memory or a comparison with Laya/LCC.

**Result.** Every seed fails. Final mean pooled.6439588256/within-goal.6662326389,
positive KEEP.9571759259, contradiction KEEP1, negative DROP.0882523148 and
semantic UNKNOWN recognition.9444444444. No UNKNOWN is dropped, but each seed
keeps eight Portuguese semantic UNKNOWNs as KEEP. EN/PT mean pooled.644267/.644245;
negative DROP.176505/0. Original scalar control.661983pooled/.710938within-goal,
blanket UNKNOWN without learned support authority. These are correlated authored
direct-record tasks, not general LCC relevance, independent production or P2.

**Independent audit and exposed diagnosis.** Raw mathematics, input/source hashes,
calibration, selection chronology and accepted updates PASS. The frozen optional
weight auditor rejects the upstream I64 position buffer; an additive checker
verifies exactly that known arange buffer, all three private weight hashes and
unchanged frozen learned parameters. Original sources/protocol/scores stay intact.
The fixed first seed101 is subsequently checked once on exposed train data:
4,800 valid forwards/164,436tokens in23.501s, pooled.807571/within-goal.800130,
below.90 even on train. Independently recounted fit/contrasts PASS. Train roles
form nine disconnected two-role components; all six final pairs cross components.
UDP and both Git final families retain the same report preference after the goal
flips in every seed (96/96 matrices per family), producing within-goal.50. A global
threshold cannot repair that ordering. Optimizer/capacity/coverage causes are not
isolated; the graph gap alone is not causal proof. 194 tests pass, zero skips,
17.940s including local LCC integration; scoped Ruff0.16.10 F/E9 passes.

**Decision.** Reject all three derivatives; keep finals exposed and immutable.
Change the conditional relevance/support objective and connected hard-negative
coverage, inspect development fit before reserving/spending fresh confirmation.
No extra epochs/final anchors/quantization/RoPE or LCC outcomes on these weights.
Qualified candidates still require fresh LCC8K/32K quality and total-cost checks.
Zero API/P2/default/hosting/publication; full engine+LCC goal remains active.
Evidence: [results and recount commands](goal-engine-2026-10-04/tool-relation-support-v1/RESULTS.md),
`audit.json`, `audit-weights-v2.json`, `fit-contrast-analysis.json`,
[changed next design](goal-engine-2026-10-04/tool-relation-support-v1/NEXT_DESIGN.md)
and `artifacts/tool-relation-support.json`.

## EXP-2026-10-04-16 — Actual Retry/UDP/Git supervision and retained ranking preparation

**Question and configuration.** Can a fresh, explicit direct-record task repair
missing tool/wording coverage without discarding the pretrained ranking signal?
This phase prepares that test; no new candidate quality is measured. A separate
trusted Linux arm64 worker installs 31 exact hashed Debian packages and Tenacity
9.1.4 offline from the immutable Python base. Actual Git 2.47.3/Python 3.13.16.
Read-only, network-none, UID 65534, bounded CPU/memory/PIDs/tmpfs/streams/time.
Source/image/dependency identities, failures and earlier source snapshots retained.

**Actual data.** Main seeds 442511/442512/442513, 32/12/24 new authored fixtures:
68 fixtures, 1,224 independently recounted fields. Four calibration fixtures with
seed 442500 contribute 72 separate fields and are excluded. Scheduled sleep,
actual sleep and elapsed duration differ; datagrams include zero-byte payloads.
UDP is payload/datagram observation, not wire/IP capture. Git index/worktree edit
counts remain fixed at 2/3; rename/merge/submodule coverage is absent. Capture wall
train/val/final: 1.356/0.976/1.188 s. No real capture failure or selective retry.

**Supervision and limits.** Frozen label/input protocol
`1fca8ea4cd2fbbde0d4f06abc0ef0c52eb905a92c1010448dfff5ea0dcae8681`
precedes derivation and candidate scores, after raw collection. 4,864/1,824/2,496
rows, 3,592/996/864 unique projected pairs. Train class counts after deduplication:
1,724 irrelevant, 1,724 relevant, 144 semantic UNKNOWN; 64 structural UNKNOWN
bypass. EN/PT goals, English authored captions; all four train alias/caption
combinations occur, numeric multisets balanced under each goal. Actual tokenizer
recount passes, raw maxima 113/109/114 and projected maxima 50/46/51, zero cuts.
Final reserves six pair combinations and wording; all 18 primitives and all three
sources occur in train. Raw/effective/entity/fixture cross-split overlap zero.
Repeated rows and three source clusters are not independent production tasks.
Direct-record equality is not generic LCC usefulness: derivation, diagnosis and
broader goals stay UNKNOWN. False requested claims stay relevant contradictions.

**Initialization check.** Scalar output expands to relevant-minus-irrelevant
margin while preserving encoder and XLM-R classifier dense parameters. Tiny real
BERT/XLM-R regressions and the exact pinned multilingual artifact pass. CPU RNG
is restored and a local generator avoids changing accelerator RNGs. Two exposed
implementation checks are preserved, three pairs per before/after pass each:
12 pair forwards total, 72 nonpadding tokens per pass. No reserved cohort is
scored, no thresholds fitted, no candidate trained or weights saved. Each smoke
has matching preserved-parameter hashes and maximum margin error below 1e-6;
these are implementation invariants, not semantic correctness or safety evidence.
Current suite: 185 tests, zero skips, 17.863 s including the local LCC integration;
scoped Ruff 0.16.10 F/E9 passes. Prior core/support/multilingual audits remain PASS.
Historical logs with four skipped consumer tests are retained; the current log
includes the consumer checkout and is goal-full-tests-tool-relations-final-current.log.

**Decision.** Freeze the bounded adaptation recipe next, retain prior and explicit
support, then evaluate complete validation/final populations under the unchanged
quality criteria. Only qualified direct-record candidates enter fresh LCC outcome
and complete local-cost/context checks. Keep broader goals protected; direct-field
success alone cannot complete the engine+LCC goal. No extra losing epochs, final
anchors, larger RoPE or quantization. Zero API/P2/default/hosting/publication.
Evidence: [actual results and recount commands](goal-engine-2026-10-04/tool-relations-grounded-v1/RESULTS.md),
`supervision-v1/{protocol,coverage,audit-tokenizer,training-preparation}.json`,
`ranking-prior-smoke*/{protocol,receipt}.json`, source/build/raw archives.

## EXP-2026-10-04-15 — Frozen multilingual prior improves exposed ranking, still fails

**Protocol.**SHAcd41918e5f2692d46e616e65943f8c3428e51cc6cff64fb3b00b358e98036e99.
Frozenmmarco-mMiniLMv2-L12-H384-v1revision8008f0154ca2387468013ed439df09d70c122412,
117,641,089parameters,XLM-Rscalar12layers384hidden,512complete-pairtokens;CPU/fp32/
8threads/batch16. ArtifactTLS/Git-blob/LFSidentity verified. No adaptation/threshold
fitting; oneval/finalpass each. ReuseEnglishscalar scores onidenticalinputhashes.

**Result.**Finalpooled.7857100875,within-goal.8467881944;EN/PTpool.841622/.742775,
within-goal.875000/.818576. Englishscalarpool.651176,within.747830,PTpool.574650.
All pooled/within-goal≥.90aggregate+each-languagecriterion fails.Used-vs-available
within.690104,sparse.791667,inodecapacity.786458;somecells pass but global does not.
BlanketshadowUNKNOWN/KEEP, no learned support/DROP authority or LCC compression.

**Cost/audit/scope.**4248validpairforwards/143588nonpaddingtokens,max48HFtokens,
0cuts/errors. Observedsetup5.693s,val12.287s,final17.450s,whole diagnostic-process
RSS1,760,886,784bytes (loading/runtime included, not installed inferenceRSS).
Independent archivedsource/input/rawmath/fullaccounting auditPASS.165tests pass
20.032s,scopedRuffF/E9PASS. Already exposed authored68fixtures/Englishcaptions,
3correlated final tool sources/sharedconcepts. Architecture/tokenizer/size/training
corpora all change, so language pretraining is not isolated as a cause. NoP2/
production/usefullongcontext proof follows. Final stays exposed.

**Decision.**Actual retry/network/Git captures and independent wording combinations,
then reserve freshconfirmation before next adaptation with retained rankingprior
and explicit support. No extraepochs/finalanchors/quantization/biggerRoPE on losing
candidates. ZeroAPI/P2/adoption/default/hosting/publishing. Fullengine+LCCgoal active.
Dependency preflight:old image has noGit/GCC/make. Git1:2.47.3-0+deb13u1and30deps
were downloaded separately and matched to APT-index SHA256;Tenacity9.1.4wheelTLS/SHA
verified.31debblobs/23,006,960bytes plus28,926bytewheel are ignored private artifacts;
not installed on host. No new retry/network/Git capture yet. DynamicAPTdiscovery
is not itself a future immutable worker recipe; offline pinned install remains.
See semantic-next/tool-dependency-preparation/README.md and manifests.
Artifacts:semantic-next/multilingual-frozen-v1/{protocol,rawscores,summary,audit}.json,
RESULTS.md;semantic-next/upstream/artifacts.json. Replay execution API unchanged.

## EXP-2026-10-04-14 — Grounded three-class support training fails every seed

**Protocol.** Frozen support SHA53f9a7b42cb6d2dbf3e003031872d43c53f272a379d833904ab22a28ed10be4b.
MiniLM-L6 revision233902d25c440f23af6f7d6e94d2946bac0bee0a, CPU/fp32,8threads,
all encoder weights adapted, fresh seededLinear384→3 (old scalar head discarded).
22,714,371adapted parameters; seeds101/202/303,3fixedepochs,batch16,AdamW2e-5/wd.01.
3676unique train views, global class weights N/(3*n_class), per-item CE/global mean.
Structural UNKNOWN bypasses scorer; full natural projected strings only.

**Result.**9finiteepochs,2070updates,33084trainingpairpresentations/984042tokens;
583.163s summed epoch time. Every seed fails. Final mean pooled.7332494916,
within-goal.7337962963,KEEP/contradiction.9953703704,DROP rejection.1024305556,
semantic UNKNOWN recognition.8495370370. UNKNOWN DROP7/16/8(allPortuguese).
EN/PT pooled means.845684/.626288. Frozen scalar on same views.651176pooled,
.747830within-goal, blanket shadow UNKNOWN/KEEP without learned support detection.
All weights/globalval cutoffs frozen before complete final evaluation.16992valid
pair forwards/589712tokens,0cuts/errors. Whole studyRSS1,503,281,152bytes includes
training state; not deploy RSS. No independence intervals over correlated rows.

**Audit and limitations.**Independent score/math/hash/input/calibration/epoch/selection
and private weights audits PASS;162tests without skips25.261s,scopedRuffF/E9 PASS.
Data are68authored toolfixtures, shared concepts/schema/Englishcaptions; finalDU/DF/
GZIP supervision/strings withheld,3correlated sources. Rawtrainreceipts include all
31fields. No sampled production orP2. Trainalias/caption0:0/1:1andval2:2are always
coupled; coverage gap observed, cause not established. Cohort final now exposed.

**Decision.**Do not run LCC outcomes/promote these candidates. Inspect pinned
multilingual prior as diagnostic, uncouple wording, add actual retry/network/Git
relations and reserve fresh confirmation before another design. No extra epochs,
final anchors or quantization of rejected candidates. Current loader position-table
guard corrected for RoBERTa families; study executed sources remain immutable.
ZeroAPI/P2/default/publication. Fullengine+LCCgoal remains active.
Artifacts:tool-role-support-v1/RESULTS.md,protocol.json,selection.json,rawscores,
audit-weights.json,wording-coverage.json,artifacts/tool-role-support.json.

## EXP-2026-10-04-13 — Grounded tool-role receipts and explicit UNKNOWN preparation

**Protocol/data.** Frozen before main captures:932c23cd40b323e88186a9755e887a44ede076d168d6f08264b0446a022ce96b.
68authored fixtures, bounded immutable Linux arm64 worker, no host mounts/network/
credentials/caller programs. GNU9.7/gzip1.13/Python3.13.16,C.UTF-8;2108fields from
1088CLI/API observations. Seeds442421/442422/442423;32/12/24fixtures give
4864/1824/2496rows (binary4608/1728/2304; UNKNOWN256/96/192). EN/PT goals balanced,
English authored captions. Nine development families/five sources; six final
families/three held-out sourcesDU/DF/GZIP, four families sharingDF. Underlying
concepts/schema/author overlap; no independent-session or six-unseen-concept claim.

**Result/validation.** All receipts and labels audited. Numeric multisets identical
between P1 labels per goal;4304false numeric claims,2152relevant contradictions.
Raw/effective input,fixture-content/entity cross-split overlap0. Unique projected
3676/1292/1674 disclose repeated inputs; maxraw112/109/120,view51/48/58,512window,
zero cuts. Optional pinned-tokenizer recount passes.151engine/consumer tests
pass, plus three objective-helper regression tests. No model weights loaded,
scores/training epochs/updates,API,P2/default or public release in this phase.

**Failure/provenance.** Original calibration supplied zero admitted fixtures after
invalidDFoptions; saved source/build/trace preserved. Corrected worker and actual
integration regression pass; exposed calibration seed442420 excluded. Missing
tokenizer cache stopped counting; five pinned files restored with verifiedTLS/SHA,
then counts completed without source/data changes.

**Decision.** Data PASS is not model approval. Current projection still treats
semantic unsupported goals as projectable; structural UNKNOWN alone is guarded.
Three-class preparation deduplicates train to1772irrelevant/1772relevant/132UNKNOWN,
with tested globally balanced CE and separate relevance/support score axes. Its
proposed driver/protocol/thresholds must be frozen before training/final scoring.
Packet/retry/tracked-file failures remain outside this captured scope. Goal active;
next bounded support/relevance candidate, then fresh LCC outcomes if quality clears.
Artifacts:tool-role-grounded-v1/RESULTS.md,protocol.json,audit-tokenizer.json,
training-preparation.json,NEXT_TRAINING.md;research/tool_role_training.py.
Complete follow-up suite:154tests,15.134s,zero skips in
goal-full-tests-grounded-training-prep.log.

## EXP-2026-10-04-12 — Compact relation adaptation and fixed report control

**Protocol.**2304/576/512 authored P1 pairs. Old18 exposed pair families now
development; eight new final pairs reserved before training. Original/projected
input hashes and entities disjoint across splits; unique projected2208/576/496,
not independent rows. Shared author/schema/primitive vocabulary, three phrases
per side. Six full22.7M MiniLM candidates,BCE/joint×seeds101/202/303,3fixed epochs,
AdamW2e-5,16-row whole-group batches,CPU/fp32/8threads. Inputs≤31/30/28tokens.
All18epochs/2592updates finite; direct epoch/meta/weight receipts, no retries.

**Result.**Validation selectedBCE before final. Final pooledmean.8279470,
same-report goal contrast.9179688, same-goal candidate ordering.8541667,
recall.96875,rejection.3776042. Frozenpool.7336121; jointpool.8331197.
Every seed of both arms fails. Selected descriptive eight-family bootstrap95%
[.7455461,.9157088]. Weak ordering in retry/network prevents a calibration-only
explanation. Do not substitute joint because its final mean is slightly higher.

**Additional fixed diagnostic.**Rawgoal/report minus fixed generic-report logit
(one reference perreport,coefficient1), originalBCE weights and base receipts
preserved.1632new forwards/33414tokens, no training/API, now-exposed final.
Pooled.8226267, within-goal.8450521,rejection.3190104; all seeds stillfail.
The same-report goal axis cancels unchanged; no anchor tuning or adoption.

**Cost/validation.**41472trainingpairs/879480nonpadding tokens;483.642saved
epochseconds.7616validation/final pairs including frozen control;whole-study
peakRSS1.322GB is not deployment memory. Independent stdlib audits verify
source/data/annotations/views/epochs/selection/raw metrics/gates/bootstrap and
optional six weights.135engine+consumer integration tests pass without skips.
Artifacts:compact-relation-v1/,report-prior-diagnostic-v1/,artifacts/compact-relation.json.
Zero API/P2/default/public release. Goal remains active: next supervision must
use externally referenced tool-role contracts and fresh language/contradictions,
not more epochs/RoPE or anchors on exposed synthetic templates.

## EXP-2026-10-04-11 — Ranking-pretrained MiniLM and a fixed input view

**Protocol.**Pinned MS-MARCO MiniLM-L6 (233902d25c440f23af6f7d6e94d2946bac0bee0a),
22.7M parameters,CPU/fp32/batch16/8threads. Existing exposed384validation/384final
semantic pairs, three repeated passes per split. Rawquestion/report first; another
separately frozen study checks explicitentity/two grammars and preserves question/
measurement/value while removing validated structure. Altered-input recipe, not
a same-input architecture comparison. Complete input,max93raw/30viewtokens.

**Result.**Rawfinal pooled.6719835, same-report goal contrast.703125,within-goal
257/384=.6692708,rejection.0520833. Viewpooled.6928711,goalcontrast.765625,
within-goal265/384=.6901042,rejection.0989583; recall.9479167 alsofails.
Both fail with zero errors/cuts;2304actual forwards each, repeated scores identical.

**Failure/provenance.**Rawprocess saved all scores/threshold then failed JSON
serialization of loader set metadata. Missingrun.json is not manufactured;offline
audit completes math, lost setup/RSS stayunknown. Adapter metadata normalization
fixed withRED/GREEN regression; archived scoredsource preserved,no inference rerun.
Independent audits check raw math/threshold/views/accounting, zero model/APIcalls.
No adoption/P2/default. Reduced inputs alone did not resolve semantic relation.
Artifacts:reranker-known-control/,measurement-projection-v1/.

## EXP-2026-10-04-10 — Semantic tool relation and a preserved numerical failure

**Protocol/data.**1152/384/384 authored P1 pairs,12 train/val concept families/six
withheld final pairs. Same report changes label with the queried measurement;
normal/unusual values, severity and format balanced. Labels are declared semantic
slot equality, not anomaly/necessity/P2/human production labels. Entities/content
hashes disjoint; max full pair79 HF tokens, zero cuts/incomplete spans. Three seeds,
three epochs, batch8; frozen vs last-two, matched fresh heads/parent line scorer.

**MPS-v1 failure.** Five finite candidates completed validation; last-two303 has
three NaN-loss passes and failed threshold computation before saved weights,
validation/selection/final predictions.15 finite epochs plus three invalid passes;
no final result invented. Fresh instrumented first144 training batches CPU/MPS
were finite; synchronization changed, so the original cause remains unresolved.
The40-batch diagnostic metadata says41 due to a loop index;40 raw rows authoritative.

**CPU-v2.** Separate source/data freeze, same previously unscored final cohorts,
all six candidates retrained inCPU with finite guards.18 finite epochs completed.
Validation selected last-two. Final pooled mean.5660626, six-family descriptive95%
[.5238336,.6145743], paired.6909722, recall.9618056, rejection.0416667; every seed
fails. Frozen pooled.5591182 [.5203955,.6049986]. Controls on384/384 complete pairs:
BGE.6268989, lexical.5895182, parent.5167914, Laya.5101183. No same-population cuts.
No runtime/architecture superiority claim or independent temporal attestation.

**Decision/validation.** No adoption. A short-input semantic failure is present;
expanding RoPE alone cannot address it. Test a ranking-pretrained compact encoder
before another adaptation cycle; this final cohort is now exposed. Independent
stdlib raw/annotation/epoch/selection/weight-hash audits pass; intervals are not
rederived by that mode. Production loss/update/checkpoint nonfinite guards fixed;
120 engine tests and52 relevant consumer tests pass. Scoped installed offline
numerical/native/typed smoke passes macOS arm64/Python3.14 andLinux arm64/Python3.13;
MPS training reliability is not established. Docker image initially absent, then
rebuilt from the pinned base; original failing check logs retained.

**Artifacts.** research/goal-engine-2026-10-04/semantic-tool-v1/ (incomplete),
semantic-tool-cpu-v2/ (completed negative), numerical-safety-before/;
`python -m research.audit_semantic_study --out research/goal-engine-2026-10-04/semantic-tool-cpu-v2`.
Goal remains active; zero P2 training admission/default/public release.

## EXP-2026-10-04-09 — Explicit local observations in the LCC outcome path

**Protocol.** Six exposed synthetic P1 tasks, four supported text forms, full
cl100k8K/32K dossiers, full/local-observations/pinned-Laya/Jev, three actual executor
repeats per cell,144 calls. Sources/data/policy frozen before dispatch, randomized
order seed442404, no selective retry. Immutable snapshots of local sources;
remote executor alias mutable/no applied generation seeds. Exact JSON code oracle,
not Jev judging itself. CPU current LCC blocks, KEEP.40 for Laya/Jev, no trim.

**Result.** Local36/36 and Jev36/36 correct; full34/36, Laya33/36. Local mean byte
removal92.50%/98.10%, Jev28.89%/36.36%; every declared observation/UNKNOWN retained.
Laya/full compile identical bytes, so their stochastic outcome difference cannot
be attributed to the selector. Local/Jev pass the fixed point criterion at both
budgets; six authored task groups do not establish population reliability.

**Cost.**591 successful Jev calls/602669 input tokens. Executor2178585 input including
1819832 cache-read,66840 output. The frozen summary's input field is uncached only;
audit.json supplies all categories. Invoice cost unknown. Supplemental six local
fresh-process checks include setup, first/warm calls and RSS; local exact route
≈42MB versus pinned Laya≈5.97GB for one exposed task per budget. Operational paths
and work differ; no isolated architecture or generic superiority claim. Initial
supplemental constructor failure is preserved; corrected v1 completed without APIs.

**Validation/decision.** Independent raw/source/annotation/slice/gap/ledger/token
reductions pass.109 engine tests,52 relevant consumer tests, scoped lint/typecheck
and executable integration example pass. Separate opt-in typed LCC operation; no
CLI/default/neural promotion, P2 admission or public release. The next neural target
is natural-language objective→tool-measurement relation, separately frozen.
Artifacts: research/goal-engine-2026-10-04/observation-lcc-pilot/;
command: `python -m research.audit_observation_lcc_pilot`. Goal remains active.

## EXP-2026-10-04-08 — Explicit observation retrieval at long dossier sizes

**Question.** Can explicit entity/field/inclusive-UTC slots avoid spending a neural
sequence window on exact supported-record retrieval? This is P1, not necessity P2
or arbitrary incident diagnosis. No public release/default promotion.

**Protocol.** Six frozen final-field synthetic JSON fixtures, full dossiers at
8192/32768/131072 cl100k budgets, three sequential parser passes. MATCH keeps,
NO_MATCH drops, unknown/ambiguous/opaque keeps whole. Sources/data freeze precedes
dispatch; no APIs. Independent audit reconstructs all texts/hashes/token counts.

**Result.** Every requested observation and every UNKNOWN preserved. Minimum
removed-byte fractions .94664/.98712/.99681; median rank 1.05/4.39/17.90 ms in this
process. Candidate ≤447 tokens; process highwater RSS 82,460,672 bytes includes
Python/tokenizer. No matched neural timing or LCC executor outcome was measured.

**Decision.** Expose a separate experimental dependency-free rank_observations API
with caller-supplied slots. Neural shadow provider/defaults unchanged. Next is a
frozen narrow LCC workflow pilot; the useful replacement goal remains active.
Artifacts: research/goal-engine-2026-10-04/observation-frontier/;
contract: docs/10_OBSERVATION_OPERATION.md; source tests: 105 passing.

## EXP-2026-10-04-07 — Direct P1 relevance remains below the quality gate

**Problem.** Earlier incident-vs-healthy labels do not answer LCC KEEP relevance.
New P1 labels come from explicit entity/field/window observations; positives include
healthy/anomalous readings, negatives wrong entity/field/window, ambiguity UNKNOWN.

**Protocol.** 2016/672/504 train/validation/final items; 1440/480/360 binary labels.
12 train domains/six final fields, no entity/content-hash overlap. Shared authored
schemas prevent a claim of independent external semantic confirmation. Full HF
pairs ≤628 and observation spans intact. Frozen vs last-two: three matched seeds,
three completed epochs each, batch eight, new matched head initialization, head
LR .0003 / encoder .00002; frozen CPU/cache versus last-two MPS. No relative
latency/isolated architecture claim. Validation selects the arm before final.

**Results.** Selected last-two final AUC mean .7145169, descriptive domain bootstrap
95% [.7069723,.7281914]; frozen .6379780 [.6267147,.6701847]. All seeds fail .90.
Selected healthy/anomalous recall .99074/.98611 at validation thresholds, but
wrong-entity anomaly rejection only .01852. Controls typed=1.0, lexical=.43146,
parent=.51100, Laya=.50424; BGE=.50193 only on 290/360 eligible binary rows
(99/504 total inputs cut). Raw inputs match; BGE is a subset diagnostic.

**Decision.** No adoption. A typed grammar winning is evidence about this narrow
combined-system design, not neural novelty. Route explicit records cheaply and
reserve future neural supervision for relations the parser cannot resolve.
No incident/P2 gate was redefined as passing. Sources/splits/selections/epoch
receipts/raw logits/independent audit: research/goal-engine-2026-10-04/direct-relevance-v1/.
The first preparation is preserved as superseded before training. Missing optional
Laya stopped an attempt before inference; installing pinned .3.4 completed it
without rescoring successful controls. No APIs in this study.

## EXP-2026-10-04-06 — Engine + LCC: native coverage and pipeline outcome diagnostic

**Question.** Does complete input coverage translate into useful, efficient LCC context?
**Configuration.** Clean v0.4 unfreeze-two checkpoint, corrected line attention,
native RoPE/8192 HF pair window. Pinned ModernBERT/tokenizer revision, 62 known v1.2
cases, common triplet filler prefixes, seed442381, pair budgets512/2048/4096/8192,
744 actual MPS pair calls, no cuts. Separate current LCC CPU/eight-thread pipeline:
four known referenced contracts1/2/4/18, 8K/32K HF dossier budgets, seed442382,
full/specialist-shadow/pinned-Laya/Jev profiles, three actual executor repeats per
cell (96 attempts). KEEP .40, trim off, one block per call, safety protections on.
Hermes alias/seed limitations and TSX transport costs are recorded before dispatch.
**Result.** At native8192, J .834547/D .735952,186/186 complete inputs;
no native budget passes .90. Pipeline 8K verified success1.00 in all profiles;
specialist/Laya remove0 chars, Jev mean reduction.7966. Pipeline32K full.25,
specialist/Laya.1667, Jev.75; Jev reduction.7940. Only Jev meets the small fixed
conditional adoption criterion at8K; no motor replacement is validated.
**Interpretation.** Full and specialist inputs are identical; their stochastic
success differences cannot be attributed to the motor. Known curated tasks and
single compilation observations do not establish independent production quality
or intrinsic latency superiority. Jev includes per-call TSX startup; concurrent
MPS work affects CPU costs. Whole-pair capacity is not useful dossier context.
**Validation/cost.** Offline raw/hash/label audits;531 successful canonical Jev
calls,767942 input tokens; observed executor500030 input/24732 output tokens
(the raw audit is authoritative if reading later). Actual invoice costs unknown;
training admission0. See `lcc-pareto/audit.json` for complete cost/error fields.
**Decision.** Keep shadow. Do not quantize losing heads, expand RoPE or pretrain a
native encoder now. Align KEEP relevance labels and train an explicitly narrowed
operation before another policy/efficiency candidate. Legacy incident gate fails.
**Evidence.** `research/goal-engine-2026-10-04/{REPORT.md,hf-frontier/,lcc-pareto/}`;
`python -m research.engine_validation_audit`.

---

## EXP-2026-10-04-05 — Fresh matched holdout normalization fails its fixed criterion

**Configuration.** Unchanged v0.4 generator, seed442383,64 exact-objective triplets
(192 candidates),16 groups per known holdout domain. Zero old content-hash overlap.
Parent plus all three validation-selected BCE seeds share full frozen-encoder
features, MPS encoder/CPU heads, max2048 HF pair tokens. Label-free within-triplet
logit z-score; original gain≥.03/positiveCI/Dloss≤.01 criterion frozen before
inference. 2000 whole-domain bootstrap draws, seed78105, only four domains.
**Result.** Parent J .6350→.7048, D .6470→.6406, gainCI[-.0391,.1592];
selected BCE J .6143→.6708, D .6417→.6378, CI[-.0745,.1582]. Paired J.7344/.6250.
Both criteria and .90 quality gates fail. A monotone adjustment cannot reverse
incorrect within-objective order. No calibrated probability claim follows.
**Decision.** Keep the normalizer exploratory; offsets explain part of the signal,
not a demonstrated sole bottleneck. No adoption or P2 admission.
**Evidence.** `research/goal-engine-2026-10-04/holdout-normalization/`;
`python -m research.audit_normalization` reproduces metrics and intervals offline.

---

## EXP-2026-10-04-04 — Frozen-encoder BCE/pairwise/joint objectives do not transfer

**Configuration.** Same clean adapted encoder frozen;2340 existing train items,
2160 fresh validation items/18 domains (seed442378),480 fresh final items/four
holdout domains (seed442379), no content-hash overlap. Three seeds101/202/303,
three actual completed epochs each, LR.0003, batch32, full-pair cache≤2048 HF,
encoder MPS/eight threads/headsCPU. BCE, BCE+within-domain pairwise loss, masked
joint relevance/incident losses plus product score. Validation-only mean(J,D)
selects BCE before final inference. No P2/outcome supervision.
**Result.** Parent final J .6524/D .6325. BCE means.6344/.6339,
pairwise.6396/.6367, joint.6009/.6193. Every D<.70 and every D-gain grouped CI
includes zero. Validation J≈1 is not heldout-domain performance.
**Decision.** Reject new heads. More epochs on the same families are deferred.
Old mixture of unpaired objectives cannot test candidate-set normalization;
EXP-05 supplies fresh matched candidates instead. No external transfer claim.
**Evidence.** `research/goal-engine-2026-10-04/{head-objectives/,study-analysis.json}`;
`python -m research.analyze_engine_studies` checks saved scores, epochs and selection.

---

## EXP-2026-10-04-03 — Referenced replay and corrected baseline recipes

**Configuration.** 20 primary-reference contracts; deadlock/DNS contracts3/19
quarantined for unsupported causal explanations.120 stateless executor attempts,
three repetitions baseline/ablation, seeds metadata only, frozen structural plus
consistency recipe, numeric PDB guard, Jev1.13 cutoff.50 inherited. Independent
human/production grounding absent. Separately five CPU/eight-thread controls,
62 known cases, identical inputs seed130/depth0/512, official BGE/GTE recipes,
pinned Laya; corrected line pooling and pinned backbone. GTE's author-derived
nonpersistent position/RoPE buffers restored after Transformers meta loading.
**Result.** Replay117 final executor successes/three timeouts;5NEC/7UNNEC/8UNKNOWN,
concordance.60/UNKNOWN.40 fail .95/.10. 62 canonical Jev calls/69949 input tokens;
original bridge misroutes requested tag to old replay tag. Preserved original
summary `execution_errors=15` means12 quarantines+3 actual errors. Training0.
Corrected control specialist J/D .7911/.7771 at0, .8293/.7219 at512; no .90 gate.
BGE/Laya truncate all186 depth512 inputs. Full control table/uncertainty is in REPORT.
**Decision.** Reject P2 admission; preserve raw failures and misrouted ledger
exports. Correct future bridge routing; archive old sources. Current software
controls do not certify production security or semantic reliability.
**Evidence.** `data/d6_referenced_pilot_v03/`, `research/goal-engine-2026-10-04/matched-controls/`;
`python -m research.referenced_replay_audit`.

---

## EXP-2026-10-04-02 — PDB arithmetic before text: zero errors on new curated eval

**Question.** Can exact PDB arithmetic followed by text-only consistency review
accept valid budgets while rejecting incorrect arithmetic and contradictory prose?
**Configuration.** `pdb-routing/0.1`,56 development/112 eval controls; disjoint
replica scales4/6/8/10 vs9/11/13/15/17/19/23/29. Shared archetype/templates,
single-author text labels. Numerical reference uses upstream Go
`k8s.io/apimachinery@v0.36.0` conversion and separately enumerated legal removals.
Supported controller/all healthy/voluntary eviction scope. New `pdb_verifier.py`
and separate TypeSafe bridge, Jev1.13.0, macOS arm64,4 subprocess workers.
No backbone, tokenizer, training, Hermes generation or sampling seed applies.
Cutoff .50 inherited; zeroFP/FN/UNKNOWN target and all sources frozen before any
development/eval calls. Same numeric guard in both arms; comparison changes state
representation and semantic question together. No selective retries or eval tuning.
**Result.** Eval separatedTP48/TN64/FP0/FN0/UNKNOWN0; coupled21/64/0/27/0.
Development separated24/32/0/0/0; coupled19/32/0/5/0. The local frozen target is
attained. Numerical grid4240 conversions/290752 policy checks, zero mismatches.
Integer int32 and leading-zero-percent regressions corrected in the new module.
**Interpretation.** Point observation on curated controls; correlated scale variants
do not establish population reliability. Text labels have no external annotator.
No cluster/full manifest/selector testing. Comparison does not isolate a causal
effect of either question or representation alone. Historical2PDB FN remain saved.
**Validation/cost.**32 tests pass; stdlib audit reexecutes upstream reference,
checks168 receipts, frozen hashes/cutoff and240 successful calls against the ledger.
133932 Jev input tokens; published-tariff estimate$0.005625144; invoice unavailable.
Historical verification scripts still pass. gateClaim initially BLOCK(.77), then
DOWNGRADE(.88, evidence2.27) after adding raw per-case values; report as point
observation. Gate calls excluded from240. Training admission0.
**Decision.** Keep the separate recipe as experimental candidate. Validate20 task
references independently, freeze a new replay recipe, then confirm120 identical-input
repetitions against proposed≥95% concordance/≤10%UNKNOWN before any P2 admission.
Do not retune or repeat selected errors from this eval.
**Evidence.** `research/pdb-routing-2026-10-04/{REPORT.md,protocol.json,pre-dispatch-freeze.json,summary.json,verification.json,numeric-verification.json,receipts/,upstream/,oracle/}`;
`python3 research/pdb-routing-2026-10-04/verify.py`; `tests/test_pdb_routing.py`.

---

## EXP-2026-10-04-01 — Verifier challenge calibration: aggregate targets pass, PDB semantic false negatives

**Question.** Can executable/typed-response verifiers reject incorrect outputs on
fresh curated controls before scaling outcome-backed replay?
**Configuration.** 80 calibration/108 eval controls,6 coding/14 typed archetypes,
single-author labels from explicit contracts. New response/program ASTs, zero code
AST overlap across splits or with the previous pilot; conceptual archetypes shared.
Version `verifier-calibration/0.1`, sources/protocol/cases hashed before eval.
Expanded executable candidate `replay/outcome_verifier.py`; optional semantic
consistency Jev1.13.0 via canonical client/ledger,140 calls56+84, macOS arm64,
four stateless subprocess workers. No Hermes generation or model training.
Cutoff grid .50/.70/.80/.90/.95/.99; chosen .50 in calibration only, frozen before
any eval receipt. Targets per kind: FP≤.05, FN≤.10, UNKNOWN≤.05; codeFP=0.
**Result.** Eval code candidateTP12/FP0/FN0/UNKNOWN0, vs legacy11/2/1/0 on24 cases.
Typed candidate40/0/2/0, vs legacy41/37/1/0 on84 (42 positives/42 negatives).
Provisional per-kind criteria pass. Both new FN are safe PDB budgets under7 replicas,
quorum4: maxUnavailable40% and2 rejected semantically at .40/.36 while numeric
contract passes. PDB FN2/3 positive controls prevents family-level certification.
**Interpretation.** Corrected boolean/percentage types, hardcoded-input acceptance,
SET NX lost contention, actual SQL/rollback checks, and RuntimeError-as-test-failure.
Semantic checking catches contradictions that a correct mechanism key alone admits.
This is curated challenge validation, not an independent production label census.
Zero observed FP on12/42 negatives cannot certify population FPR≤5%; all training
admission remains false. Replay concordance95% is separate from semantic cutoff .50.
**Cost.**140995 Jev input tokens, published-tariff estimate$0.00592179, actual invoice
unavailable.25 regressions pass; independent script verifies receipts, source hashes,
split/AST isolation, frozen cutoff and canonical ledger. Original120 pilot receipts
and historical gate/corpus verification remain valid.
**Decision.** Keep candidate experimental. Route quantitative budgets to code in
the next frozen recipe; constrain semantics to textual claims and confirm on new
controls without retuning this eval. Obtain independently validated task references
and a fresh120-episode repeatability eval before P2 admission or scale-up.
**Evidence.** `research/verifier-calibration-2026-10-03/{REPORT.md,summary.json,verification.json,protocol.json,frozen-threshold.json,pre-eval-freeze.json,receipts/}`;
`python3 research/verifier-calibration-2026-10-03/verify.py`; `tests/test_verifier_calibration.py`.

---

## EXP-2026-10-03-08 — Actual replay: 120 calls, bounded outcomes, proposed reliability fails

**Question.** Does real repeated execution support reliable necessity labels for D6/P2?
**Configuration.** Frozen `real-replay/0.1` protocol; 20 curated tasks, baseline and
candidate-block removal, 3 independent calls each. Hermes v0.21.5+5430.g5d07710,
commandcode/stealth/space-bunny-alpha, safe-mode, no tools/memory/plugins; macOS arm64,
three concurrent subprocesses, fresh process/session per call. Seeds42/59/76 are
input metadata, not applied generation seeds; backend alias is not immutable.
No model training. Six generated-Python executable contracts, fourteen typed-answer
checks. Jev1.13.0 is a supplementary semantic diagnostic, never the label oracle.
**Result.** 120 calls and unique sessions,119 valid JSON artifacts; baseline60/60 and
ablation39/60 verified runs. Audit gives5 NECESSARY/11 UNNECESSARY/4 UNKNOWN;
80% task concordance (Wilson CI95% [.584,.919]),20% UNKNOWN. Proposed≥.95/≤.10
targets fail; the .95 threshold is not empirically validated. Zero training admission.
**Verifier audit.** Original PDB check incorrectly rejected maxUnavailable1; corrected
three ablation verdicts from saved outputs, one task NECESSARY→UNNECESSARY.
Original episode receipts and executed source remain intact. Six correct-code
controls pass and six broken-code controls fail; independent verification checks
raw receipts/hashes/counts. Futurev0.2 removes unapplied seed from prompt and fixes
JSON-key hash canonicalization; it has not been run. No selective retries.
**Cost.** Hermes118008input/91522output tokens; actual billed cost unavailable.
Jev119calls/74931input tokens, tariff estimate$0.003147102 (official$.042/M input,
free output), not a measured invoice. Smokes and gate calls are outside these totals.
**Decision.** Preserve negative result; calibrate verifiers on untouched fixtures and
freeze admission criteria before confirmatory eval. Do not scale or train on these
labels yet. Nine Jev/fixture diagnostic disagreements further preclude treating
semantic scores as ground truth. This is actual execution on curated contracts,
not restored production incidents.
**Evidence.** `research/replay-real-2026-10-03/REPORT.md`, `verification.json`,
`evaluation-audit.json`, `executed-source/`; `data/d6_real_pilot/episodes/`,
`summary.json`, `records.jsonl`, `protocol.json`; `python3 research/replay-real-2026-10-03/verify_run.py`.

---

## EXP-2026-10-03-07 — CPU reference remeasurement: dossier passes, per-block M8 fails

**Question.** Does the clean selected unfreeze arm meet both M8 targets on the 66K-token reference?
**Configuration.** `models/exp02e-unfreeze2`, corpus v0.4, native window 8192, temperature .6,
fp32 CPU, offline, macOS arm64, Python 3.14.3, torch 2.14.0, transformers 5.17.0, 8 threads.
Synthetic 100 blocks × 660 context HF tokens (67,100 paired input tokens), no cuts;
first forwards timed with load contribution; warm p50 from 15 samples after 5 warmups.
**Result.** Load+scoring 20.3826 s, representative warm p50 192.3979 ms; peak process RSS
915.375 MiB. Dossier ≤43 s passes; p50 <50 ms fails; **M8 overall false**.
M9 int8 footprint not tested. This is pair scoring, not an integrated hierarchical pipeline.
**Decision.** No CPU production certification. Fix quality first; then evaluate a smaller tier,
quantization/batching/cache with explicit quality regression and both M8 targets.
**Evidence.** `research/continuation-2026-10-03/bench-cpu-unfreeze2.json`; executable
`python -m research.bench_cpu --model-dir models/exp02e-unfreeze2 --out <json>`.

---

## EXP-2026-10-03-06 — D6 pilot correction: oracle simulation, real replay pending

**Question.** Did the inherited 20-task pilot supply outcome-backed P2 labels?
**Configuration.** Curated `replay/tasks.py`; inherited simulator reads `is_decisive` and
copies `required_keywords`; built-in verifier only matches those words. Three paired
repeats, seeds 42/59/76. Fixture names "hermes"/"ast" were not actual installed executors.
**Result.** Synthetic smoke: 16 NECESSARY, 2 UNNECESSARY, 2 UNKNOWN; 90% concordance,
10% UNKNOWN. No executor API calls, API cost zero, **zero P2 training admission**.
.95 is only a proposed reliability threshold; the pilot does not validate it.
**Decision.** Preserve old records in `research/continuation-2026-10-03/inherited/`;
canonical origin corrected to SYNTHETIC. `replay.harness` now requires explicit mode,
with a JSON subprocess contract, hidden answer keys, pinned scripts, full outputs,
measured cost receipts and UNKNOWN on execution/verifier errors. Real executor,
validated outcome verifier and resettable task environments are still required.
NECESSARY does not automatically imply CRITICAL; UNNECESSARY does not imply REDUNDANT.
**Evidence.** `data/d6_pilot/summary.json`, `records.jsonl`, `replay/README.md`,
`python -m replay.harness --simulate`. This is harness validation, not P2 ground truth.

---

## EXP-2026-10-03-05 — Joint Detect/Judge product: reject against independent clean BCE

**Hypothesis.** Objective-aligned detect supervision should give D≥.70 at 0/512,
positive paired bootstrap ΔD CI, and J loss≤.02. These are inherited pilot criteria.
**Configuration.** Existing frozen ModernBERT/line-attn two-head weights
`models/exp05-joint-detect`, trained on v0.4; original seed/epoch receipts were not
saved, so causal matched-seed attribution is unavailable. Reused weights without
retraining. Independent control `models/exp02e-line-attn` (BCE, 3 epochs, seed0),
MPS, max_len1024, suite1.2 n=62 at 0/512, untruncated. Score σ(judge)×σ(detect).
Case-paired bootstrap 1000 repeats, seed42. Metric strict pooled P(fact>noise).
**Result.** At 0, control J/D .6582/.6727, joint .6907/.6345,
ΔD −.0382, CI [−.0731, −.0049]. At512, control .7120/.6582,
joint .7222/.6129, ΔD −.0453, CI [−.0762, −.0166]. D criterion fails at both depths.
The inherited "judge_only baseline" was the judge head of this same joint model;
it is retained in the new output as an internal head ablation, not the BCE control.
**Decision.** Do not adopt this product score; keep negative result. Further objective work
needs actual target-aligned labels and recorded seeds, not repeated runs of this pilot.
**Evidence.** `research/detect-supervision-results.json` and `.scores.json` archive all
124 case/depth triplets, logits, input hashes, actual lengths and checkpoint hashes.
`python -m specialist.train_detect --evaluate-only --device mps` reproduces it.

---

## EXP-2026-10-03-04 — Clean per-objective logit normalization: exploratory gain, gate fails

**Hypothesis.** Removing objective offsets can improve pooled J without damaging D.
**Configuration.** Saved clean frozen/unfreeze scores, v1.2 n=62, depths0/512.
Fixed continuation recipe: logit(p), subtract the mean and divide by population sd
across all three candidates for each objective; no label-dependent fitting.
Case-paired bootstrap 2000 repeats seed42. Criteria fixed for this continuation:
ΔJ≥.03, CI lower bound>0, D loss≤.01. This is exploratory, not the inherited
unsaved terminal recipe and not an untouched confirmatory experiment.
**Result.** Frozen J .6582→.7510 at0, .7120→.8161 at512; criteria pass both.
Unfreeze J .7479→.8265 at0 (Δ+.0786, CI [.0200,.1288]),
.8145→.8554 at512 (Δ+.0408, CI [−.0146,.0926]); criteria fail at512.
Unfreeze D .7599→.8010 / .7125→.7482. No cell passes both .90 quality bars.
**Decision.** Worth a confirmatory pilot on untouched objectives with realistic varying
candidate sets. Scores depend on candidate composition and are not calibrated
probabilities (M12); do not ship or tune thresholds on these eval cases.
**Evidence.** `research/normalization_pilot.py`; protocol, all scores, metrics and CI
in `research/continuation-2026-10-03/normalization-{protocol,results}.json`.

---

## EXP-2026-10-03-03 — Clean corpus v0.4 + completed controls; coverage has an 8K caveat

**Hypothesis.** Removing holdout distractor leakage and repairing the harness permits
an interpretable comparison of frozen vs unfreeze-last2.
**Configuration.** `corpus-exp02/0.4`, seed0, `data/exp02e` 2340/810/960; 18 training
and 4 holdout domains. `models/exp02e-line-attn` / `exp02e-unfreeze2`, 3 stored epochs,
MPS, batch8, max_len1024, lr_head1e-3/lr_encoder2e-5, line-attn, seed0, T=.7/.6.
Epoch subsets now stratify 240 examples/4 holdout domains (60 each); IDs reconstructed
from current loader saved as a check, not original per-epoch receipts.
**Result.** Independent full saved-weight evaluation (960 OOD/810 val) reproduces
frozen .593582/.890774 and unfreeze .624242/.942871. Zero holdout text signatures in
train/val, correct content hashes, zero split hash intersections.
Suite1.2 n62 at0/512/4096/8192: frozen J/D .658/.673, .712/.658, .748/.660, .632/.545;
unfreeze .748/.760, .815/.713, .824/.702, .619/.549. Zero scoring errors;
**all 186 prompts at nominal8192 exceed the native HF window and are truncated**.
**Decision.** Quality still fails .90; 4K coverage is complete. The near-window
untruncated boundary, original checkpoint's missing8K/32K and hierarchy benefit are
not proved. Keep >8K deferred under the recorded redirect. Do not certify the new
quality/cost gate or overwrite historical reconstructed epoch metadata as verified.
**Harness corrections.** Inherited dynamic-RoPE/order fix and exact trained-tokenizer
flags retained. Continuation additionally fixes tie credit to match strict gate and
uses unrounded AUC for the gate. Raw scores are preserved; 20 historical summary
cells with ties change (archived diff). Probe/device provenance remains incomplete
for old rows and cannot be backfilled by assumption.
**Evidence.** `research/continuation-2026-10-03/verification.json`,
`saved-evaluation.json`, `stratified-sampling-check.json`, `score-order-check.json`;
raw `bakeoff/results/results.json`, full tables `RESULTS.md`.

---

## EXP-2026-10-03-02 — EXP-04: domain-diversity corpus (v0.3) + encoder adaptation — gate NOT reached, mechanism isolated

**Hypothesis / pre-registration.** EXP-03-01 showed the transfer collapse is depth-invariant
and domain-bound. Two candidate causes, one variable each: (a) the training corpus holds out
templates/subjects but never DOMAINS, so the head learns field-vocabulary priors instead of
"anomalous vs healthy value"; (b) the frozen encoder cannot represent unfamiliar archetypes.
Pre-registered read: probe suite v1.2 (62 cases, pooled AUC, bar .90) at depth 0 (control)
and 16384 (the gate depth), same dynamic-NTK position recipe in all arms (single variable
changes only at the training layer).

**Configuration.**
- `corpus-exp02/0.3` (`data/exp02d/`, 2340/810/960, hash-disjoint): +10 new training
  archetypes (api_contract, geoshard_routing, audit_log_gap, cost_runaway,
  fraud_false_positive, i18n_missing, image_pull_failure, monitoring_flap, pii_in_logs,
  grpc_deadline) — none of them is a probe v1.2 archetype *by construction* (different
  incident semantics; verified: no probe `case_id` shares its full domain token set with
  a corpus domain). 4 domains (`vector_drift`, `bot_traffic`, `pdf_render`,
  `sms_delivery`) held out ENTIRELY as the OOD split; `neg_unrelated` now draws its
  decisive line from a *different* domain's vocabulary (the v0.2 distractor was
  same-domain/different-subject, so it could not test "is this line about the
  objective"). Length stream unchanged (mean 335 words).
  *(Audit note 2026-10-03: `specialist/corpus.py:412` drew unrelated distractors from all
  domains including holdouts, producing 172 train and 32 val examples with holdout tokens;
  corrected in v0.4).*
- **Contamination audit (self-check, run after the numbers above):** 9 of the 10 new
  domains are token-disjoint from every probe archetype, but `monitoring_flap` shares its
  skill with the probe case `raft_leader_flap` (both "count state transitions during an
  incident"). Sensitivity measured: dropping `raft_leader_flap` moves J@16384 .756 → .750,
  J@512 .779 → .772, J@0 .691 → .685 (J moves ≤ .006), and D@16384 .511 → .495 (a drop
  of .016, > .006). The gate-failure conclusion is unchanged; the claim of a sole calibration bottleneck is withdrawn; the initial
  self-check claimed 53 unseen new cases. **Withdrawn after independent audit:**
  identifier-token overlap is not a semantic novelty test; rollout, pool saturation
  and cache concepts overlap too. No validated 53/54 novelty count exists.
- Two arms, ModernBERT + `line-attn`, MPS, batch 8, max_len 1024, 3 epochs:
  **frozen** (0.39M trainable) and **unfreeze-last-n 2** (10.42M, lr-encoder 2e-5).
- Measured on probes v1.2 at depths 0 / 512 / 16384, window 49152, rope dynamic factor 6,
  all cells untruncated, 0 errors. Gate metric = pooled AUC; paired (within-case) AUC
  reported as diagnostic only.

**Result (OOD gate first per R2 — full split, 960 items, 4 unseen domains).**

| arm | OOD full | val full | OOD partial / val per epoch (ep1→3) |
|---|---|---|---|
| frozen line-attn | .573 | .931 | .304/.659 → .345/.829 → .364/.883 |
| unfreeze-2 (10.4M) | **.673** | .949 | .287/.936 → .383/.964 → .389/.975 |

Probe suite v1.2, pooled AUC (n=62; new54 / old8 in parentheses):

| depth | baseline exp02c-v0.2 | frozen v0.3 | unfreeze-2 v0.3 |
|---|---|---|---|
| 0 (control) | .554 / .657 | .563 / .657 | .586 / **.691** (.594/.685) |
| 512 | .561 / .684 | .549 / .722 | .531 / **.779** (.465/.761) |
| 16384 | .571 / .726 | — | .511 / **.756** (.465/.749; .766/.859) |

Case-set labels: "all62" = the v1.2 suite as built; "new54" = the 54 cases authored in
v1.2 (old8 = the original 8, which are near-copies of v0.2 training archetypes); of the
new54 were authored separately; semantic independence from training has not been
certified. `raft_leader_flap`/`monitoring_flap` is one known overlap, not an exhaustive
audit. Case IDs alone cannot establish 53 genuinely novel cases.

**Interpretation.**
1. **Both interventions help the judge, neither reaches the bar.** Unfreeze-2 lifts pooled
   J@16384 .726 → **.756** and J@512 .684 → **.779**; new54 J@16K .700 → .749, new54
   J@512 .661 → .761. Real gains in unseen archetypes (+.05 to +.06 on new54, not +.10
   isolated from unfreeze alone), but eff ctx at the .90 bar remains 0 — **the Sprint-2
   gate is NOT passed.**
2. **Encoder adaptation is the effective lever, not corpus diversity alone**: frozen v0.3
   gains almost nothing over the v0.2 baseline while unfreezing the last 2 layers buys
   +.057 on all62 (.048 on new54) on the probe judge.
3. **In-domain vs domain-OOD gap WIDENS with training** — val .936→.975 while full-split
   domain-OOD stays .673 (unfreeze) / .573 (frozen).
4. **Per-domain offsets are arbitrary** (measured on the 4 holdout domains, unfreeze
   arm): pdf_render fact −2.74 vs decoy −4.76 while sms_delivery fact +0.14 vs decoy −1.82.
   The originally quoted within-domain paired .711 vs pooled .614 diagnostic has no
   saved population/recipe and is withdrawn as standalone evidence. Independent
   saved-checkpoint evaluation (`research/audit-2026-10-03/saved-evaluation.json`)
   gives unfreeze OOD judge pooled .7104, macro within-domain .7400, and vector .4272;
   offsets and within-domain ranking both matter.
5. **Detect family remains at chance**: new54 D runs .46–.59 across complete depths
   (0, 512, 16K); all62 is .586 (0), .531 (512), .625 (4K partial, n=4), .511 (16K).

**Decision.**
- **Sprint-2 gate: NOT passed.** Recorded in `research/failures.md` (FAIL-2026-10-03-01).
- **Formal redirect:** Per `docs/08:33`, project formally redirects to an experimental
  envelope of ≤8K tokens per block with hierarchical block aggregation (Sprint 4);
  single-sequence >8K ambitions paused for Sprint 2/3.
- Historical accepted architecture: `line-attn` + dynamic-NTK (factor 6, window 49152)
  + `--unfreeze-last-n 2`, `models/exp02d-unfreeze2`. Corpus v0.3 is contaminated;
  this checkpoint is retained for historical reproduction. Clean experimental
  comparator: `models/exp02e-unfreeze2`, native 8192 window. Neither is gate-approved.
- Next levers, in priority order:
  1. Fix harness (deterministic RoPE, exact truncation flags, run provenance) — DONE.
  2. Rebuild uncontaminated corpus v0.4 and retrain short baseline arms.
  3. Domain-agnostic score calibration pilot at 0/512.
  4. Complete 4K and 8K coverage; evaluate ≤8K envelope against M8 CPU budget.

---

## EXP-2026-10-03-01 — probe suite v1.2 (8 → 62 cases): the 16K "near-miss" was a case-set artifact

**Hypothesis / pre-registration (before measuring).** The Sprint-2 boundary read
(J@16K = .891 = 57/64 pairs, one additional strict pair win from clearing the .90 bar) sits inside n=8 noise.
Expanding the curated suite with independently authored cases (anti-contamination
path, kept separate from the training generator) will (a) resolve the boundary and
(b) test whether the original 8 cases were representative. Gate metric unchanged:
pooled AUC(d) = P(score(fact@d) > score(noise@d)) over ALL case pairs (n²), bar .90.

**Configuration.** `bakeoff/probes.py` PROBE_VERSION 1.2: 54 new `ProbeCase` entries
authored by hand (not generated), same construction rules as v1.1 (fact/decoy share
keys and differ only in values; length-matched — max fact/decoy token delta ≤ 4 on
all 62; log level drawn uniformly; one length-matched unrelated distractor). Depth
grid unchanged. `bakeoff/runner.py --cases` now builds only the selected cases (the
full 62-case deep grid cost real time per batched invocation). Baseline checkpoint
unchanged: `models/exp02c-line-attn` via the `specialist-exp03-dynamic-49k` adapter
(dynamic-NTK rope factor 6, window 49152), MPS, all cells untruncated, 0 errors.
Depths 0/512/4096/8192/16384 run with n=62; 32768 still n=8 (not re-run).

**Result (pooled AUC, gate metric; old8/new54 split in parentheses).**

| depth | n | D | J | D old8/new54 | J old8/new54 |
|---|---|---|---|---|---|
| 0 (control) | 62 | .554 | .657 | — | — |
| 512 | 62 | .561 | .684 | — | — |
| 4096 | 62 | .562 | .743 | — | — |
| 8192 | 62 | .563 | .741 | .781 / .529 | .906 / .718 |
| 16384 | 62 | **.571** | **.726** | .781 / .537 | .891 / .700 |

- **Reproducibility exact**: old8 cells at 8192/16384 reproduce the EXP-03 numbers
  to three decimals (.781/.906 and .781/.891) — same pipeline, only the case
  composition changed.
- **The original 8 probe cases are quasi-in-domain**: 7–8 map 1:1 onto the
  `corpus.py` training archetypes (disk_quota↔disk_quota, retry_storm↔retry_storm,
  auth_regression/config_drift↔config_change, queue_backlog↔pool_saturation,
  cache_stampede↔cache_perf, session_leak↔sweep_jobs, booking_timeout↔http_status).
  The EXP-02c "transfer" numbers were inflated by domain overlap.
- **Historical interpretation (qualified by the audit): failure already at control depth**: on all62, J runs .657 (control)
  → .743 (4K) → .726 (16K) [on new54: .639 → .722 → .700] — no decay with depth; detect
  is flat .55–.57 at every depth *including control*. The curve is compatible with a transfer problem, but the RoPE cache defect
  prevents claiming positional preservation from these rows alone.
- Pooled vs within-case (paired) AUC at 16384 on new54: .700 vs .815 — cross-case
  score calibration accounts for ~.11 of the gap; the discriminating skill itself
  holds on 44/54 new cases (fact > decoy within case), 10/54 inverted.

**Interpretation.**
1. **Sprint-2 gate fails decisively on the honest suite**: eff ctx at the .90 bar =
   0 for both families on v1.2 (J@16K .726 vs .90). The "one-pair near-miss" was a
   sampling artifact of a small, domain-overlapping case set — n=62 (3844 pairs)
   makes the boundary question moot rather than resolving it in our favor.
2. **The control result establishes a domain-transfer gap**; it does not alone
   rule out positional effects or encoder adaptation: the head reaches only J≈.66–.74 on unseen
   archetypes even at control depth with the decisive line alone in front of it.
3. **Detect family is at chance on unseen archetypes** (.55–.57 pooled, at every
   depth) — the EXP-02c watch-item ("detect at control is weaker") is now quantified:
   line-attn learned to detect *known* incident shapes, not evidence-vs-noise
   generically.
4. Metric discipline: the gate stays on the pre-registered pooled AUC (cross-objective
   comparability); paired AUC is reported as a diagnostic only.

**Decision.**
- Probe suite v1.2 is now the gate instrument (62 cases, 1/3844 pair granularity);
  the old8 stay reported for continuity but the gate read is quoted on all 62 with
  the clean54 split shown.
- Gate stays OPEN; diagnosis revised: the next spend is **training-side domain
  diversity** (corpus v0.3: +10 new training archetypes, 4 held out *entirely* as a
  domain-OOD gate so the per-epoch gate predicts probe performance) ± **encoder
  unfreeze** (the planned adaptation run) — logged as EXP-2026-10-03-02.
- Rope/position extension is no longer the suspected bottleneck and is not re-run.

---

## EXP-2026-10-02-05 — EXP-03: position extension 8K→32K, measured with the line-attention head

**Hypothesis / pre-registration (before measuring).** The EXP-02c head + extended
positions can hold the decision signal at 16K–32K depth. Acceptance (Sprint 2 gate,
docs/08): **measurable effective context ≥ 16K** (AUC ≥ 0.90 per family) — with the
judge ≥ 0.70 floor from EXP-02c kept as the secondary read.

**Configuration.** Same trained checkpoint (`models/exp02c-line-attn`) — single
variable at the position layer, head frozen (it already extrapolates to ~10K).
Position extension is config-level in transformers 5.x (RoPE per layer type:
`sliding_attention` θ=10K / `full_attention` θ=160K; no new weights). Two variants,
window 49152 (verified untruncated at depth 32768 — smoke test: 49K tokens / 1,404
lines, ~60 s/fwd MPS):
- `exp03-extrap-49k`: rope untouched (pure extrapolation past the 8192 training max);
- `exp03-dynamic-49k`: `rope_type=dynamic` (NTK-aware, factor 6) — inert below 8192,
  stretches wavelengths beyond (verified formula semantics in modeling_rope_utils).
Infra: `bakeoff/runner.py` merge now cell-granular (model, depth, case) + `--cases`
filter so deep grids build in <600 s batches. Eval on **MPS** (CPU quadratic cost at
32K ≈ 144 s/block); depths 8192/16384/32768, probe v1.1, n=8.

**Result (all AUCs; untruncated everywhere; gate read at the .90 bar).**

| model | depth | D | J | fact | decoy | unrel | p50 MPS |
|---|---|---|---|---|---|---|---|
| exp02c-12k (baseline, CPU) | 8192 | .859 | .875 | .45 | .13 | .14 | 9.0 s |
| exp03-extrap-49k | 8192 | .859 | .875 | .45 | .13 | .14 | 2.0 s |
| exp03-extrap-49k | 16384 | .781 | .891 | .64 | .18 | .30 | 7.4 s |
| exp03-extrap-49k | 32768 | .641 | .719 | .61 | .30 | .50 | 38.4 s |
| exp03-dynamic-49k | 8192 | .781 | .906 | .43 | .12 | .18 | 2.0 s |
| exp03-dynamic-49k | 16384 | .781 | .891 | .44 | .09 | .17 | 9.0 s |
| exp03-dynamic-49k | 32768 | **.750** | **.828** | .40 | .12 | .17 | 37.1 s |

**Interpretation.**
1. **Position extension works as designed and is measurable**: dynamic-NTK holds
   judge **.828 at 32K untruncated** (fact .40 vs decoy .12 — clean value separation)
   while pure extrapolation degrades to .719 with noise scores drifting up (.50 — the
   familiar length-drift reappearing in encoder space). First measured win for rope
   adaptation: +.11 judge at 32K, one variable changed.
2. **Strict gate NOT passed**: eff_ctx at the pre-registered .90 bar is 16384 minus
   one pair-tie (J@16K = .891 = 57/64 for both variants; J@32K dynamic = .828).
   The secondary judge ≥ .70 floor, however, holds at EVERY depth through 32K with
   dynamic (extrap only barely at .719). n=8 → 1/64 granularity: the .891 vs .90
   boundary is inside noise; the 60+ case expansion decides it.
3. The EXP-02c 8K regression check is exact (extrap@8192 = baseline 12K cell:
   D .859/J .875, means identical to 3 decimals) — pipeline reproducibility confirmed.
4. Cost is the real 32K problem: p50 37 s/block MPS (~144 s CPU), quadratic in depth.
   Block-aware per-block scoring keeps this off the hot path in LCC, but a 32K
   *state* scored whole is not shippable at this latency.
5. Remaining lever to clear .90 @16K: **adaptation** (unfreeze encoder on long
   blocks — the EXP-02b under-trained control at 4+ epochs, now with long-context
   curriculum). The aggregation head and the position config are no longer the
   suspected bottlenecks.

**Decision.**
- EXP-03 outcome = **near-miss at the strict bar, positive at the floor**: recorded
  per R2 without quoting as a pass. Sprint-2 gate stays OPEN pending (a) the 60+
  case probe expansion and (b) the adaptation run.
- Dynamic-NTK (factor 6) becomes the default position recipe for the specialist
  stack; pure extrapolation is retired as the 32K option.
- Next: adaptation run with long-block curriculum; probe expansion 8→60+ (independent
  authoring path) to resolve the .891 boundary; then Sprint-3 block-aware
  architecture design starts from an evidenced baseline.

---

## EXP-2026-10-02-04 — EXP-02c: line-level aggregation head (the structural fix) — **ACCEPTANCE PASSED**

**Hypothesis.** (H2, seeded by EXP-02b): aggregating the decision signal at LINE
granularity instead of pooling the whole block into one vector beats the measured
dilution cliff. Pre-registered acceptance (unchanged from EXP-02b): **judge ≥ 0.70
held at depth 256–512 on curated probes v1.1.**

**Configuration.** `specialist/model.py` gained two pooling modes (line ids derived
from the fast tokenizer's offset mapping — count of newlines before token start — so both
remain ONE encoder forward pass):
- `line-max`: per-token scorer → max within line → max over lines (multiple-instance
  learning; gradient flows only through the current argmax line).
- `line-attn`: line representation = mean of token hiddens per line → learned
  attention over lines → existing head (dense gradient through the softmax).
`specialist/train.py`: `--pooling line-max|line-attn`; optimizer fix (all non-encoder
trainable params — including the line scorer — join the head param group; before this
the new scorer would never have been updated). Training: corpus v0.2 (`data/exp02b/`),
3 epochs × ~175 s each on MPS (per-epoch checkpoint + `--resume`), batch 8,
lr-head 1e-3, max_len 1024, seed 0, ModernBERT frozen, **0.39M trainable params**.
Hardware: Apple M1 Max 64GB. Checkpoints: `models/exp02c-line-max/`,
`models/exp02c-line-attn/`.

**Result (full OOD gate, gate-first per R2).**

| run | OOD AUC (full) | val AUC | train AUC | note |
|---|---|---|---|---|
| line-max, 3 ep | 0.511 | 0.481 | **0.506** | does not even fit TRAIN — MIL pathology |
| line-attn ep 1 | 0.834 | 0.855 | — | immediate jump, ~5× the mean-pool signal |
| line-attn ep 2 | 0.879 | 0.888 | — | |
| line-attn ep 3 | **0.891** | 0.897 | — | vs mean-pool 0.511 / token-attn 0.492 |

**Probe transfer (curated v1.1, `bakeoff` runner, CPU).**

| model | window | D@0 | D@64 | D@256 | D@512 | J@0 | J@64 | J@256 | J@512 |
|---|---|---|---|---|---|---|---|---|---|
| specialist-exp02c-512 | 512 | .58 | .73 | .70 | .69 | .72 | .89 | **.92** | **.78** |
| specialist-exp02c-1k | 1024 | .58 | .73 | .72 | **.95** | .72 | .89 | **.95** | **.83** |
| specialist-exp02-512 (v1.0 rows, baseline) | 512 | .81 | .28 | .44 | .45 | .69 | .47 | .56 | .33 |
| specialist-exp02-8k (v1.0 rows, baseline) | 8192 | .81 | .28 | .23 | .00 | .69 | .47 | .47 | .42 |

**ACCEPTANCE: judge ≥ 0.70 at depth 256 AND 512 → PASS** (.95/.83 with the 1K window;
.92/.78 with the 512 window). First time any neural candidate holds P2 judgment at
depth on the curated probes; the previous head collapsed to .42–.56 off-control.

**Interpretation.**
1. **The dilution cliff was a pooling failure.** Same encoder (frozen ModernBERT),
   same corpus, same optimizer — changing only the aggregation granularity takes OOD
   0.511 → 0.891. Line-level attention over ~40 segments surfaces the value-match
   signal that whole-block mean/token-attention pools erase below ~10% decisive share.
2. **Dense gradient is what makes it learn.** Hard max over lines (`line-max`) starves:
   with ~40 lines the decisive line rarely wins the initial argmax, so its gradient
   almost never fires (train AUC 0.506 after 3 epochs — classic MIL search pathology).
   Softmax attention over lines touches every line each step and converges in one
   epoch (0.834). For H2 the aggregation must be line-level AND differentiably dense.
3. **The EXP-02 length bias does not reappear**: v0.2 is length-decorrelated and the
   line-attention weights normalize away line-count effects; judge stays ≥ .78 through
   depth 512 (with the window that doesn't truncate — 24/24 blocks truncate at the
   512 window at depth 512, and the score drop .95→.78 tracks exactly that).
4. New watch-item: **detect at control is weaker** (.58 vs EXP-02's .81 on v1.0 probes)
   — the head learns necessity judgment before detection polish; also the baseline rows
   above are probe v1.0, so cross-version comparisons stay indicative (curves, not
   cells).
5. n = 8 cases (1/64 AUC granularity): the PASS is a gate result, not a precision
   claim — the 60+ case expansion (queued) is what turns this into a publishable
   number.

**Follow-up (same day): full 0–8192 curve + window extrapolation.** Depth-granular
merge added to `bakeoff/runner.py` (stale rows dropped per (model, depth), so long
curves build in batches); `specialist-exp02c-8k` adapter added (same head, no
truncation up to 8K). All cells probe v1.1, CPU, n=8:

| adapter | window | D@512 | D@1K | D@2K | D@4K | D@8K | J@512 | J@1K | J@2K | J@4K | J@8K |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exp02c-512 | 512 | .69 | .44 | .75 | .63 | .53 | .78 | .30 | .45 | .69 | .55 |
| exp02c-1k | 1024 | .95 | .48 | .72 | .44 | .67 | .83 | .42 | .59 | .75 | .69 |
| exp02c-8k | 8192 | .95 | .73 | **1.00** | .69 | .38† | .83 | .91 | .94 | **.89** | .61† |

† = 24/24 blocks truncated (depth-8192 blocks + objective exceed even the 8K window).
eff_ctx (bar .90) for exp02c-8k: **detect 2048 / judge 2048** (J@4K = .891, one
pair-tie from the bar at 1/64 granularity — curves, not cells).

**EXP-03 baseline cell (same day): the 8K drop was truncation, not positions.**
`specialist-exp02c-12k` (same head, 12K window) at depth 8192, **untruncated**:
**D=0.859 / J=0.875** (fact .45 vs decoy .13 — clean separation; p50 8.96 s/block CPU).
The un-extended backbone (training max 8192) already reads ~10K-token inputs
zero-shot; the .38/.61 @8K cells were a tokenizer-window artifact.

1. **The aggregation head extrapolates zero-shot in length**: trained at ≤1024 tokens
   (~40 lines), it holds judge .89 at 4096 and .88 at ~10K tokens (~700 lines) with
   no length training. The head is not the long-context bottleneck.
2. **Position extrapolation past the training max is also surprisingly free** (≤10K
   tested) — but 16K/32K remain untested and are the real EXP-03 question. Position
   extension config path confirmed (transformers 5.x `rope_parameters` per layer type:
   `sliding_attention` θ=10K window 128 / `full_attention` θ=160K; extension =
   `rope_type: dynamic|linear` + factor + `max_position_embeddings`, no new weights).
3. Truncation remains the dominant failure mode wherever it occurs (both capped-window
   adapters past their window, and the 8K window itself at depth 8192). Eval cost at
   32K is quadratic on CPU (~144 s/block) → EXP-03 measurement must run on MPS or a
   reduced grid.
4. H2 strengthened: block-aware line aggregation holds **judge ≥ .78 at every depth
   256→8192 untruncated** (pre-registered acceptance was .70 @256–512) on the same
   backbone where raw cosine detection decayed to .58 and the mean-pooled trained head
   was .00 detect @512.

**Decision.**
- **EXP-02c acceptance PASSED** — logged as the first empirical win for the block-aware
  line-level aggregation design (H2); seed of the Sprint-4 architecture. Not quoted as
  a Sprint-2 gate pass (that gate is ≥16K effective context — still open, EXP-03).
- Next: EXP-03 (position extension 8K→32K) now measured with the line-attention head
  as instrument; full 0–8192 curve for exp02c; rerun the full bake-off on probe v1.1
  for a clean single-version table (current results.json mixes v1.0/v1.1 rows, tagged).
- Still open: 4-epoch `--unfreeze-last-n 2` adaptation control; replay pilot (20 tasks)
  for outcome-backed P2 labels.

---

## EXP-2026-10-02-03 — EXP-02b: length-decorrelated corpus + the dilution-cliff diagnostic chain

**Hypothesis.** (a) Length-decorrelating the corpus (the EXP-02 measured length bias)
recovers robust depth judgment (acceptance: judge ≥ 0.70 at depth 256–512 on curated
probes); (b) if not, isolate the mechanism by single-variable controls.

**Configuration.** Corpus v0.2 (`corpus-exp02/0.2`, `data/exp02b/`): block length drawn
from an independent stream (120–700 words, built to target for every kind — verified:
label=1 mean 325 words vs label=0 mean 336; per-kind 325/339/333). Probes upgraded to
v1.1 (matched middle lengths; log level uniform across kinds — removes the v1 ERROR↔fact
cue). Six controlled training runs on MPS (ModernBERT frozen + 0.2M head unless noted):
see result table. Also implemented attention pooling (`--pooling attn`) and fixed the
transformers-5.x layer path for `--unfreeze-last-n`.

**Dataset.** train 2,400 / val 640 / ood 960 (same domain/template/subject splits as
v0.1, hash-disjoint). Class: SYNTHETIC. Auxiliary sets: `data/exp02b_short` (≤250
words), `data/exp01_padded` (v0.1 + ~100-word tails), `data/exp02b_taildec` (decisive
line moved to block end).

**Result (all AUCs = full OOD gate).**

| run | data | change vs baseline | OOD AUC |
|---|---|---|---|
| baseline (EXP-02) | v0.1 (40-word blocks) | — | **0.729** |
| repro-check | v0.1 | current code | 0.696 (trajectory matches) |
| v0.2 mean-pool | v0.2 (mean 330 words) | length-decorrelated corpus | 0.511 |
| v0.2 short ≤250w | v0.2-short (mean 185 words) | same, short blocks only | 0.504 |
| v0.1 padded | v0.1 + 100-word tails (140 words) | tail length only | 0.621 |
| v0.2 taildec | v0.2, decisive line last | position only | 0.507 |
| v0.2 attn-pool | v0.2 | learned token-gated pooling | 0.492 |
| v0.2 unfreeze-2L (1 ep) | v0.2 | 10.2M params adapted | 0.525 |
| BoW logistic (probe) | v0.2-short | lexical linear model | **0.750** |

**Interpretation (the dilution cliff).**
1. The corpus is learnable (BoW 0.75) and the training code is clean (repro matches
   EXP-02). The v0.2 failure is not data correctness, not code, not position.
2. Everything orders by **decisive-token share** (≈15 evidence tokens / block tokens):
   27–37% → learns (0.73); 10.7% → 0.62; ≤8% → chance (0.49–0.52). Below ~10% share,
   neither mean pooling nor learned attention pooling over *frozen* representations can
   surface the value-match signal; 1 epoch of shallow encoder adaptation does not
   restore it either.
3. This is a measured architectural argument for the program's core bet (H2): decision
   signal must be aggregated at **line/block granularity** (score local segments, then
   max/attention over segment scores — exactly the block-aware design of docs/03 §2),
   not by pooling a whole 300-token block into one vector.
4. The EXP-02 length *bias* (mean-score drift with input length) and the *cliff*
   (signal loss below a share threshold) are two distinct failure modes; the v1.1
   probes and v0.2 corpus now isolate both.
5. Caveat: the unfreeze test is 1 epoch only — under-trained for 10M params; a 3–5
   epoch run is needed before closing the "adaptation works" question.

**Decision.**
- EXP-02c (next, the structural fix): **line-level aggregation head** — per-line
  scoring (local encoding) + max/attention aggregation over lines; acceptance stays
  judge ≥ 0.70 at depth 256–512 on curated v1.1 probes. If it works, it is the first
  empirical win for the block-aware architecture and the seed of the Sprint-4 design.
- Parallel: 4-epoch `--unfreeze-last-n 2` run as the adaptation control.
- The acceptance criterion for EXP-02b (judge ≥ 0.70 held at depth) is NOT met —
  recorded as a failed gate with the mechanism measured, per docs/07 R2 discipline.

---

## EXP-2026-10-02-02 — EXP-02: first trained necessity decision head (ModernBERT)

**Hypothesis.** A minimal decision head trained on a programmatic, anti-memorization
necessity corpus (a) learns the P1/P2 skills beyond chance on held-out generators, and
(b) transfers to independently authored probes; frozen-encoder + head is sufficient
when the *data* is designed against memorization (the September failure was data, not
the frozen-encoder recipe per se).

**Configuration.** `specialist/` package (corpus.py, model.py, train.py). Backbone:
ModernBERT-base frozen (0.2M trained params: Linear 768→256→GELU→Dropout→1), mean
pooling; BCE-with-logits; AdamW lr_head 1e-3, wd 0.01; batch 16; max_len 512; 3 epochs;
seed 0; temperature fitted on val only (grid NLL) → T = 0.35.

**Dataset.** `data/exp02/` — programmatic corpus `corpus-exp02/0.1`: 8 domains
(http_status, disk_quota, config_change, pool_saturation, cache_perf, retry_storm,
sweep_jobs, deploy_rollout), each with anomaly/healthy *value pairs*, 2 train + 2 OOD
paraphrase template families, and subject-name pools split train/OOD (70 vs 50 names,
zero overlap). Labels: pos = decisive line with anomaly values for the objective's
subject; negatives = healthy-value lookalike (P2) or other-subject line, sometimes
anomalous (distractor anomaly). Anti-shortcut controls: log level independent of
label (verified: label rate ≈1/3 across all four levels), objective mentions subject
via name or alias. Splits disjoint by content hash. Sizes: train 3,200 / val 800 /
ood 1,200. Class: SYNTHETIC (generator + seed recorded).

**Models.** EXP-02 head as trained (window 512) and same head scoring at the encoder's
native 8K window (window-length transfer test). **Training method.** Frozen encoder +
head, 3 epochs. **Seed.** 0. **Hardware.** Apple M1 Max, MPS, 62 s/epoch.

**Metrics.** Corpus: AUC (Mann-Whitney), OOD gate reported before in-domain every
epoch. Probes: the bake-off P1/P2 suite (8 curated cases × 8 depths), same protocol as
EXP-01 for comparability.

**Result.**
- Corpus OOD gate: AUC 0.650 → 0.696 → **0.729** (val 0.627 → 0.683 → 0.723). OOD ≥ val
  at every epoch — no overfitting signature.
- Curated probes (transfer, zero overlap of cases/objectives with training):
  - Control depth 0: **detect 0.81, judge 0.69** — best calibrated judge at control
    (raw ModernBERT cosine 0.45; minilm-ce 0.58; laya-typed 0.70 but uncalibrated).
  - Window-512 variant: signal washes out with added filler (detect 0.28–0.64 across
    depths, ≈chance).
  - Window-8K variant: all three kind-means drift upward together with input length
    (fact .55→.77) and AUC *inverts* below chance at depth (detect 0.00 @512, 0.11
    @1024) — noise_unrelated probe blocks run ~55 tokens longer than fact blocks and
    the length bias ranks them higher.

**Interpretation.**
1. *Learnability confirmed*: P1/P2 skills are learnable by a 0.2M head on a frozen
   encoder when data is programmatic and anti-shortcut — transfers to independently
   written cases at control depth (0.81/0.69). This is the first positive evidence
   for H1's trainability claim.
2. *Length generalization is the measured gap*: the head carries an input-length score
   drift (longer block ⇒ higher P(evidence)) that inverts rankings beyond training
   lengths. Enlarging the window without length-matched training makes it *worse*,
   not better. EXP-02b must decorrelate length from label (matched-length negatives,
   long tails) and the probe suite needs v1.1 (matched middle lengths — the ~55-token
   confound is a harness flaw, amplified but not created by the model's bias).
3. Consistent with EXP-01 #3: the September recipe fails on data design, succeeds on
   data design — the recipe (frozen encoder + small head) is not the villain.
4. n = 8 curated cases; control-depth cells are indicative; the drift curves are the
   evidence.

**Decision.**
- EXP-02b (next): retrain with length-decorrelated corpus + length-matched probes
  (v1.1); acceptance = judge ≥ 0.7 held at depth 256–512 on curated probes.
- Keep the 512 envelope as the current LCC-relevant regime (LCC clips scoring inputs
  to ~4K chars); long-context remains EXP-03's problem (position extension), now with
  a trained head as the measuring instrument.
- The trained head becomes the standard "trained-judge" baseline row in the bake-off.

---

## EXP-2026-10-02-01 — Encoder bake-off: effective-context probe suite (Sprint 2)

**Hypothesis.** (a) Off-the-shelf encoders/judges expose a usable *detection* signal
for evidence buried at depth in realistic filler, with measurable effective-context
curves well below declared windows; (b) no off-the-shelf model performs value-level
*necessity judgment* (incident vs healthy lookalike); (c) the Laya decision-judge
lineage cannot see beyond its ~1K state window regardless of input length.

**Configuration.** Harness `bakeoff/` (probes.py, adapters.py, runner.py). Two probe
families × 8 depth placements × 8 task cases × 3 block kinds:
- P1 `detect`: incident line vs unrelated filler (critical-recall analogue).
- P2 `judge`: incident line vs healthy lookalike, same vocabulary, values differ
  (historical incident/healthy diagnostic; lexical shortcuts remain possible,
  and this does not establish necessity or numerical reasoning).
- Control depth 0 = decisive line alone. Depth = tiktoken cl100k tokens (fact placed
  at ~depth−48, 256-token tail). Seeds fixed per (case, depth, kind); deterministic.
- Scoring: Laya judges via `laya.load(...).predict` with LCC's exact `keep_question`
  phrasing (compactor.py), batch 1, raw (bypassing LCC's 831-token production budget
  refusal to probe raw model behavior); cross-encoder sigmoid(logit); bi-encoders
  mean-pooled cosine rescaled to [0,1]; lexical baseline = content-word overlap.

**Dataset.** 8 curated probe cases (`bakeoff/probes.py` CASES): log/terminal dossiers
with one decisive incident line and plausible healthy decoys. Class: CURATED (builder:
this experiment; selection rule: low objective↔fact lexical overlap, values carry the
answer).

**Models.** lexical-overlap (BL0); convaiinnovations/laya-multilingual;
convaiinnovations/laya-typed-decisions; ~/Models/laya-lcc-relevance-v1 (the 2026-09-23
fine-tune); cross-encoder/ms-marco-MiniLM-L-6-v2 (22.7M); BAAI/bge-small-en-v1.5
(33.4M); answerdotai/ModernBERT-base (149M, 8K window);
Alibaba-NLP/gte-multilingual-base (306M) — **load failed** (`trust_remote_code`
required; not enabled), recorded as failure.

**Tokenizer / context length.** Each model's own tokenizer with truncation to its
declared window (512 / 1024 / 8192); depth measured in tiktoken cl100k.

**Training method.** None (zero-shot probing). **Seed.** Per-block seeds as above.

**Hardware.** Apple M1 Max, 64 GB RAM, 10 cores; CPU inference (`--device cpu`),
single process per batch; Python 3.14.3, torch 2.14.0, transformers 5.17.0, laya
0.3.7 (LCC venv). RSS = ru_maxrss delta per batch process (max-only, cannot decrease).

**Metrics.** AUC(d) = P(score(fact@d) > score(noise@d)) over 8×8 case pairs;
effective context = largest depth with AUC ≥ 0.90; p50 latency per (objective, block)
call; load time; RSS delta. Full rows: `bakeoff/results/results.json`; tables:
`bakeoff/results/RESULTS.md`.

**Result (headline rows, AUC @ depths 0/256/512/1K/2K/4K/8K).**
- ModernBERT-base — detect: .75/.81/**.88**/.77/.64/.64/.58 · judge: .45–.73, ≈chance
  · p50 187 ms @256 tok, 3.1 s @4K, 8.0 s @8K.
- laya-multilingual — keeps everything (fact/noise means .85–.95 both), detect ≈.5 at
  every depth · p50 ~360 ms flat from 512 to 8K tokens (silent truncation at its
  1024 max_len: content beyond is invisible).
- laya-typed-decisions — only model clearing the bar anywhere: detect .92 at depth 0
  (control), .67 at 64, ≈.5–.78 beyond · judge ≈chance.
- laya-lcc-relevance-v1 (the fine-tune) — detect **.28 at depth 0 control** (worse
  than chance on entirely new evidence lines), ≈.44–.70 beyond · judge ≈chance.
- minilm-msmarco-ce — detect .89 at control decaying to .50 at 512 (window edge) ·
  judge ≈chance · fastest learned scorer (9–35 ms).
- bge-small-en-v1.5 — ≈.5–.7 both families; cosine dilution severe even at depth 0.
- lexical-overlap — detect .72–.78 flat (depth-insensitive, unbounded) · judge .49–.57
  (by construction cannot separate values).
- gte-multilingual-base — load failure (see Models).

**Interpretation.**
1. *Detection at depth is real but nobody is good at it out of the box.* ModernBERT's
   cosine curve is the best available and still only reaches .88 at 512 tokens and
   decays with depth — usable as a warm-start signal, not a judge.
2. *Value-level necessity judgment (P2) is unclaimed territory* — every model sits at
   chance. Supports H1 (relevance ≠ necessity is a distinct learning problem) and
   confirms the heads must be trained, not borrowed.
3. *Third independent confirmation of the memorization finding*: the fine-tune scores
   worse than chance on novel evidence at the control depth — its September in-domain
   numbers did not survive contact with new data (consistent with LAYA.md §8 finding 2).
4. *Silent truncation is the real effective-context mechanism*: Laya accepts 8K-token
   inputs at flat latency and judges nothing past ~1K — declared window ≠ used window
   (R5 confirmed as an observed phenomenon, not a fear).
5. *CPU cost grows steeply with block length* on the 8K encoder (quadratic regime:
   8 s @8K vs 187 ms @256) — strong cost argument for the block-aware local-attention
   architecture bet and for per-block scoring over whole-dossier states.
6. n = 8 cases ⇒ AUC granularity 1/64; single-cell values (e.g. J@4K = .80) are
   indicative only. Curves, not cells, carry the evidence.

**Decision.**
- **Track B confirmed as primary path**: ModernBERT-base-class backbone (native 8K,
  best detection curve, faster than Laya at equal depth) + trained typed decision
  heads. Track C (native architecture) stays gated: the ≥16K candidate space for small
  encoders is thin, which *strengthens* the case for position-extension adaptation —
  to be tested next (Sprint 2 continuation).
- Next experiment (EXP-02): train a minimal decision head on ModernBERT over the
  P1/P2 probe families (expanded corpus) as the first Track-B training target, with
  an OOD split from day one.
- Next experiment (EXP-03): position-extension (RoPE/ALiBi-style adaptation or
  continued pretraining) to push ModernBERT-class encoders from 8K toward 32K, with
  this same probe suite as the acceptance curve.
- Open fix: gte-multilingual-base retry with `trust_remote_code=True` (vendor custom
  code; requires an explicit go-ahead) or substitute snowflake-arctic-embed-m-v2.0.
- Probe suite becomes part of MSI-Bench v1 (long-context probes, docs/05 §4).

---
