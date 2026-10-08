# Frozen goal-only interpreter probe — 2026-10-08

## Decision and claim qualification

All new numerical claims below are scoped exploratory execution observations.
The automated claim gate returned **BLOCK** (support .82; evidence strength 2.04),
requiring: **INFERIDO — nao medido (falta medicao repetida ou fonte independente)**.
The receipt is result-claim-gate.json. No gate retry or independent human semantic
certification occurred. Independent code/math review verifies these receipts;
it does not certify general performance or replace independent human labels.

Reject this zero-shot routing recipe. The contract is frozen and the probe is
complete; aggregate and both EN/PT language gates fail. No fresh confirmation,
field-selector implementation or new LCC utility benchmark follows from it.
This result does not reject the general goal-interpretation + source-binding
architecture; it rejects these fixed weights/definitions/routing on exposed data.

## Contract and inputs

Eight field source/unit definitions and four unsupported-kind definitions are
in registry.json / CONTRACT.md. Only query and public definition reach the
model. Annotation targets live in separate files. Malformed records do not make
a supported question unsupported; direct questions outside the eight fields do.
No record field, value, truth flag or entity suffix enters the model.

The 64/32 original raw fixtures are independently recounted. Existing exposed
wording-pilot data yield 1,172/1,136 unique train/validation queries, 256/240
supported direct questions and 916/896 UNKNOWN requests. Literal overlap zero.
These are authored, correlated wording families, not independent human tasks.
The existing queries are not a new complete-utterance or semantic-novelty dataset.

Fixed unique-argmax over twelve bilingual definitions, exact ties abstain.
No training, cutoff fitting, score-scale calibration or definition search.
The lexical control reuses bakeoff _content_words (ASCII words longer than three
characters), including its language/diacritic limitation; same input strings.

## Validation point results

| Model / cohort | Accepted precision | Supported coverage | Correct supported coverage | UNKNOWN recognition | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| neural / all | 0.187977 | 1.000000 | 0.820833 | 0.098214 | FAIL |
| neural / en | 0.182331 | 1.000000 | 0.808333 | 0.080357 | FAIL |
| neural / pt | 0.193798 | 1.000000 | 0.833333 | 0.116071 | FAIL |
| lexical / all | 0.233456 | 0.687500 | 0.529167 | 0.577009 | FAIL |
| lexical / en | 0.228571 | 0.716667 | 0.533333 | 0.566964 | FAIL |
| lexical / pt | 0.238636 | 0.658333 | 0.525000 | 0.587054 | FAIL |

Targets: precision ≥.99, supported coverage ≥.80, UNKNOWN recognition ≥.95
in aggregate and EN/PT separately. Coverage counts an accepted supported query
even when the field is wrong; precision and correct coverage expose that error.
CONTRACT.md names semantic UNKNOWN; the executable frozen protocol additionally
includes out-of-registry UNKNOWN in the combined gate. Both versions are reported
below and fail, so that scope wording difference does not alter the stop decision.
The neural policy accepts all 240 direct requests but binds only 197 correctly.
It also accepts 808 of 896 unsupported requests, yielding precision 197/1048.
The neural semantic-only UNKNOWN recognition is 85/864=.098380; out-of-registry
recognition 3/32=.093750. No success follows from coverage 1.0.

Failure examples are saved in failure-examples.json; selection is explicit and
illustrative. Frequent distinctions include scheduled versus observed waits,
attempts versus failures, bytes versus datagrams and Git index versus worktree.
The policy also assigns concrete fields to diagnosis/derived/broader requests.
That is consistent with topical relevance failing to establish request support;
it does not identify a causal flaw in the backbone or prove every other recipe
must fail. Unsupported prototypes and long bilingual definitions are confounds.

## Execution and verification

Immutable protocol: `20ebddaaba6dadecee2a8d05600a72408058f3e127f4dbccb12085f8c57fd7d0`.
Frozen upstream mMARCO MiniLM revision 8008f0154ca2387468013ed439df09d70c122412,
model SHA 5daeca2481a76b5976a2bdc32f0a78532b6716da4f8cd3ff59460ef8d2f359b4.
CPU fp32/eight threads/batch 16, complete pair window 512, maximum actual input 152.
Actual local pairs 27,696 (14,064 train + 13,632 validation), below 30,000; total
nonpadding tokens 2,949,948 reconcile counted/submitted/completed/valid counts.
The lexical control performs another 27,696 word-overlap comparisons; these are
not neural forwards and consume no model tokens. The frozen cap counts neural pairs.
Train/validation scoring 102.567/99.615s; setup 3.354s. Peak complete-probe RSS
1,832,255,488 bytes includes imports/model/controls, not LCC serving.
Exit 0 complete 2026-10-08T10:15:36.896834Z. No errors, cuts or optimizer updates.
The local probe uses zero API calls. One subsequent external Jev claim-gate call
is separate; its token/cache/cost ledger is unavailable in the receipt.

Four behavioral tests fail before implementation and pass afterward. After the
review fix, the full suite passes 252 tests / zero skips in 16.665s
(tests-post-review.log); scoped Ruff E9/F passes (ruff-post-review.log).
Offline receipt auditor verifies data/source hashes, input identities, every
score/token length, masks/metrics/controls/accounting and chronology with zero
additional forwards. Its audit is implementation-based; fresh independent math
and code review is recorded in INDEPENDENT_REVIEW.md. That review found missing
checks on the duplicated summary metrics/protocol/stop action. The additive
auditor and one RED→GREEN regression fix those checks while retaining every
frozen source and score; see audit-summary-supplement.json and the corruption
reproduction in summary-gap-reproduction.log. Independent human label review remains
pending. No P2/default/public-release promotion.

## What remains and next decision

Stage 1: contract complete as an authored, raw-checked definition; independent
human semantics still pending. Stage 2: closed negative probe. Stages 3/4 are
not executed because the frozen development gate fails. Fresh whole-query
families remain unused and must be reserved for a future passing recipe. The
historical eighteen-field and full LCC gates remain unchanged.

Next candidate decision: separately supervised query support and field identity,
instead of treating passage relevance as an applicability probability. A small
query-only head on the existing frozen encoder is a bounded hypothesis worth
specifying before further inference/training; no such training is executed here.
Do not fit this validation, add UNKNOWN keyword regexes, rewrite failed strings,
add old-pilot epochs/seeds, change backbones or claim useful 32K context.

Reproduce offline: `python -m research.audit_goal_interpreter_probe`.
This runs both the frozen core audit and the supplemental summary checks, with
zero new forwards. The historical `research.goal_interpreter_probe --phase audit`
alone lacks the supplemental checks. Live frozen sources must match their
archives; `--phase run` refuses a second start or score overwrite. Dependencies
and local upstream model artifacts are still required for historical preparation
or scoring, but this offline receipt audit does not invoke the model.
