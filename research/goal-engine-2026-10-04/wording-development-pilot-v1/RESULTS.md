# Held goal-wording development pilot — rejected

One fixed seed and three finite epochs completed locally; the development
quality gate fails. The independent audit passes evidence integrity, with an
explicit preserved metadata-path erratum. This phase supplies no fresh final,
LCC outcome, adoption, P2 admission or provider promotion.

The pilot reuses the original actual train/validation captures: 64/32 authored
Retry/UDP/Git fixtures. It contains four within-tool distinctions and eight known
relevance fields: retry attempts/failures, actual/scheduled waiting time, sent UDP
datagrams/payload bytes, staged/worktree Git paths. Semantic UNKNOWN cases retain
all 18 known fields. Each relevance field/language has four whole goal phrases
per split; train and validation phrases, question frames and UNKNOWN frames are
disjoint. Report captions remain known. Neither this nor the authored captions
are independent production/human ground truth.

The previous final diagnosis informed this pilot's focus. Its old finals remain
excluded from training and validation; the pilot is exposed development, not a
new independent confirmation. Scope, class composition, wording and training
workload change jointly, so comparisons with the previous larger development
study cannot isolate a wording effect. The four pairs also omit other poorly
ordered pairs found in that diagnosis.

| Data | Rows | Binary positive/negative | Semantic/structural UNKNOWN | Unique projected inputs | Maximum raw/projected HF tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 11,136 | 2,048 / 2,048 | 6,912 / 128 | 10,434 | 131 / 71 |
| Validation | 5,568 | 1,024 / 1,024 | 3,456 / 64 | 5,304 | 132 / 74 |

Zero projected-input overlap, conflicting labels or cuts. Independent full
tokenizer recount and raw-capture audits pass. Unique training class counts are
1,824 negative / 1,824 positive / 6,786 semantic UNKNOWN; correlated rows are not
independent task counts. Data protocol SHA:
`94a3b391162767f1f3df9bc422c4200a758a627b76f4f9098821305237151d80`.

Training reuses the existing finite CPU fp32 recipe: mMARCO multilingual MiniLM
revision `8008f0154ca2387468013ed439df09d70c122412`, eight threads, last two blocks
and classifier, batch 16 / four quartets, AdamW head LR1e-4 / tail LR2e-5, balanced
classification followed by conditional ranking. Fixed seed101, three epochs,
117,641,859 total / 3,697,923 trainable parameters. No seed search or extra epochs.
Study protocol SHA:
`f037d5d067aee03c03b4a6941dd4e816c1e4f23c19f99482de8d17390ae96461`.

| Population | Pooled AUC | Within-goal AUC | Positive retention | Contradiction retention | Negative DROP | Binary UNKNOWN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Trained, train | .840858 | .870361 | .937988 | .928571 | .000000 | .968994 |
| Trained, validation | .625629 | .694824 | .998047 | .997573 | .001953 | .998047 |
| Immutable scalar, validation | .586981 | .644043 | 1.000000 | 1.000000 | .000000 | 1.000000 |

The scalar is a shadow ordering control on identical inputs, with no DROP
authority. Both trained populations fail their aggregate and language policy
criteria. Semantic/structural UNKNOWN recognition is 1.0 and UNKNOWN DROPs are zero;
preserving a positive includes UNKNOWN, not necessarily KEEP. The trained
validation policy emits **0 positive KEEP, 2 positive DROP, 1,022 positive UNKNOWN;
0 negative KEEP, 2 negative DROP, 1,022 negative UNKNOWN**. This is inadequate
context removal despite high retention. Support discrimination AUC is .999108
on train and .886953 on validation; ranking also fails before thresholding.
The scoped result does not prove that the original architecture or every possible
calibration cannot work. It rejects this bounded recipe.

Actual accepted training: 2,649 finite updates / 42,318 pair presentations /
1,796,904 nonpadding tokens. Epoch times: 96.056/93.671/98.328s. Trained evaluation:
16,512 forwards / 704,464 tokens; scalar validation: 5,504 / 236,044. Total
evaluation: 22,016 forwards / 940,508 tokens, no cuts/errors. Execution started
2026-10-07T23:03:55Z and exited0 at23:10:02Z, complete including the scalar.
The summary's process peak RSS 2,151,464,960 bytes covers the training/trained-eval
phase before the scalar; a full-run or isolated deployment peak was not recorded.
No tool captures or model API calls occurred in this data/training phase. The
later external claim-check call is separate from these local model budgets.

`study-v1/training_meta.json` is written from accepted updates and three direct
finite epoch receipts, not reconstructed from terminal logs. It binds private
weights SHA `48ef51fc1028d194bd69b089fa654a2b211a5549eb39bc7b97a5bf60b474409a`;
independent frozen-parameter bytes match the immutable base. Weights remain
private and incompatible with the native ModernBERT provider.

## Preserved metadata erratum and reproducibility

The executed producer wrote `data_directory=".."` where the shared auditor's
base is `study-v1`'s parent; the correct value is `"."`. Execution used the fixed
DATA path and SHA-checked data files, so the trained input/update receipts bind
the intended data. The first independent full audit fails with FileNotFoundError;
`audit-before-path-correction-errors.log` preserves that failure. The historical
protocol and executed source archives remain unchanged. The corrected producer
uses `"."` for future preparations. The additive auditor explicitly supplies the
actual directory and verifies **every original frozen data-file hash**, with an
erratum in `study-v1/audit.json`. The audit does not certify that the original
relative-path metadata was correct. Current-source guards prevent replaying the
old training with changed sources; no restart or re-training occurred.

```sh
python -m research.audit_wording_pilot_study --data-only
python -m research.audit_wording_pilot_study
PYTHONPATH=. python research/goal-engine-2026-10-04/wording-development-pilot-v1/study-v1/offline-diagnosis.py
python -m unittest tests.test_wording_pilot_study tests.test_wording_development_pilot tests.test_varied_relation_failure_diagnosis
```

The full independent audit rederives data/labels/tokens, deduplication, update
order/counts, finite epochs, calibration, scores, metrics, source archives and
private frozen weights, plus scalar accounting and terminal chronology, with
zero audit inference. Scoped Ruff E9/F passes. The workspace suite passes 247
tests / zero skips in 17.904s, including local LCC integration. The isolated path
regression fails before correction and passes afterward; both logs are saved.

The separate Jev claim gate passes (.90 support) only for the completed finite
epochs and observed failed validation; see `study-v1/result-claim-gate.json`.
It does not certify quality, a causal improvement or broader LCC replacement.

Execution, audit, metrics and offline diagnosis are complete. See
[the next decision](NEXT_DESIGN.md); another confirmation is not justified by
this failed pilot. The broader engine+LCC objective remains unfinished.
