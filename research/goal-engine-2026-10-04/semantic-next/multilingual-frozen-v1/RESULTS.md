# Frozen multilingual ranking: improved diagnostic, gate still fails

Protocol `cd41918e5f2692d46e616e65943f8c3428e51cc6cff64fb3b00b358e98036e99`. All inputs are previously exposed authored tool-role pairs. This is a fixed ranking diagnostic without adaptation, threshold fitting, support detection or DROP authority.

| Control | Final pooled AUC | Within-goal AUC | EN pooled | PT pooled |
| --- | ---: | ---: | ---: | ---: |
| Multilingual scalar | 0.785710 | 0.846788 | 0.841622 | 0.742775 |
| Original English scalar | 0.651176 | 0.747830 | 0.832794 | 0.574650 |

The frozen diagnostic criterion requires pooled and within-goal AUC≥.90 in aggregate and each English/Portuguese language. It fails. Both models keep every row in shadow; therefore zero DROP and zero UNKNOWN DROP are policy invariants, not learned calibration or useful compression. The original English model scores are reused unchanged, with matching effective input hashes and cohort IDs; no repeated English-model forwards.

| Final family | Pooled AUC | Within-goal AUC |
| --- | ---: | ---: |
| bytes_vs_inodes | 0.835015 | 0.888021 |
| compression_sizes | 0.863064 | 0.966146 |
| inode_capacity | 0.787543 | 0.786458 |
| sparse_usage | 0.800401 | 0.791667 |
| used_vs_available | 0.683539 | 0.690104 |
| volume_capacity | 0.794922 | 0.958333 |

The same-goal failure is strongest for used-vs-available (.690104) and remains below .90 for sparse usage (.791667), inode capacity (.786458) and bytes-vs-inodes (.888021). Some other within-goal cells pass while pooled AUC stays below .90. Improvement on a point metric does not qualify a candidate or fix absent retry/network/Git relations.

## Identity, coverage and observed cost

Pinned model `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@8008f0154ca2387468013ed439df09d70c122412`, raw one-logit XLM-R reranker, **117,641,089 parameters**, CPU/fp32,8threads,batch16, complete-pair limit512. Original upstream scalar/dense weights retained; no model adaptation. Artifacts are TLS/immutable revision/Git-blob or LFS identity verified in `../upstream/artifacts.json`. No custom upstream code is executed.

All **4248 projected rows** (1800validation,2448final) score without cuts/errors, including semantic UNKNOWN. Structural24/48 UNKNOWN rows bypass the model. Maximum complete pair **48 HF tokens**; **143588 counted/submitted/forward-completed/valid-score tokens** reconcile. English-caption/PT-query tokenization differs from the English model despite identical strings.

Observed setup **5.693s**, one validation pass **12.287s** and final pass **17.450s**. Whole diagnostic-process peak RSS **1,760,886,784bytes** includes artifact loading/hash buffers and ML runtime; it is not installed inference RSS or a cold/warm LCC comparison. No inference-efficiency superiority is established.

The upstream [pinned model card](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/blob/8008f0154ca2387468013ed439df09d70c122412/README.md) declares Apache-2.0 and machine-translated mMARCO with Portuguese. Architecture, tokenizer/vocabulary, size and training data differ from the English model; this comparison does not isolate language pretraining as a cause. The3class adapted MiniLM study also changes its output head/objective, so its different final scores are not a pure language comparison.

The fixtures, goal/report captions and equality labels are authored, with six final families but only three correlated held-out binary sources. All original finals are exposed. Scope is P1 question/report relevance, not independently reviewed production or P2 necessity. No useful long-dossier context is validated by short pairs.

## Verification and next work

The independent stdlib auditor verifies immutable source/data/score hashes, effective pair identities, strict pooled/within-goal and per-language/family reductions, full token/row accounting and control reuse. It performs no model or API calls. Audit PASS means receipt consistency, while ranking remains FAIL. The suite now passes165tests without skips (`../../goal-full-tests-multilingual-diagnostic.log`,20.032s). New input/UNKNOWN/language-gate behavior has RED/GREEN evidence in the parent folder; scoped Ruff F/E9 passes.

```sh
python -m research.audit_multilingual_diagnostic
```

Next: complete actual bounded retry/network/Git measurements and uncoupled phrasing, reserve a fresh confirmation cohort, then freeze a candidate preserving the ranking prior with explicit support recognition. More training on the exposed evaluation set, final threshold fitting, quantization and larger RoPE are not warranted now. Goal stays active; zero API calls, P2 admission, adoption, default change or publication.
