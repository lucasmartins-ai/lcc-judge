# Grounded relevance and support: all three candidates fail

Protocol: `53f9a7b42cb6d2dbf3e003031872d43c53f272a379d833904ab22a28ed10be4b`. The driver, policies, sources and data/model hashes were frozen before training; all three weights and validation cutoffs were frozen before the one final pass. These are local auditable receipts, not independent preregistration certification.

| Seed | Final pooled AUC | Within-goal AUC | UNKNOWN dropped | Gate |
| --- | ---: | ---: | ---: | --- |
| 101 | 0.731689 | 0.740451 | 7 | FAIL |
| 202 | 0.714132 | 0.699219 | 16 | FAIL |
| 303 | 0.753927 | 0.761719 | 8 | FAIL |

Mean pooled AUC **0.733249**, within-goal **0.733796**, positive/contradiction KEEP recall **0.995370**, negative DROP rejection **0.102431** and semantic UNKNOWN recognition **0.849537**. All UNKNOWN drops are Portuguese semantic-UNKNOWN rows. Structural UNKNOWN stays whole.

| Goal language | Mean pooled AUC | Within-goal AUC | Negative DROP | Semantic UNKNOWN recognition |
| --- | ---: | ---: | ---: | ---: |
| en | 0.845684 | 0.836806 | 0.189236 | 1.000000 |
| pt | 0.626288 | 0.630787 | 0.015625 | 0.699074 |

Frozen original scalar MiniLM on identical views: pooled AUC **.651176**, within-goal **.747830**. Its policy is blanket shadow UNKNOWN/KEEP, with no support detector or DROP authority; its zero UNKNOWN drops do not demonstrate learned support recognition. The adapted pooled metric rises while within-goal ordering is lower than the frozen control. This comparison cannot isolate the cause: the output head and training objective both changed.

The frozen criteria require every seed, aggregate and each language: pooled and within-goal ≥.90, positive/contradiction KEEP ≥.95, negative DROP ≥.70, semantic UNKNOWN recognition ≥.95, structural UNKNOWN recognition 1.00 and zero UNKNOWN DROP. Original cohorts are retained in every calculation; no selectively eligible subset, per-goal tuning or final anchors. All three validation candidates already fail the utility criteria; the predeclared diagnostic final pass confirms the negative result. No LCC outcome run or adoption follows.

## Execution and provenance

Original English MS-MARCO MiniLM-L6, 22,713,601 parameters, pinned revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`. The scalar head was replaced with a fresh seeded three-class linear head while retaining the encoder initialization; adapted parameter count **22,714,371**. Full CPU/fp32 adaptation, seeds 101/202/303, three fixed epochs each, batch16, AdamW2e-5/weight decay.01. Do not describe this initialization as retaining the pretrained ranking head.

Train views deduplicate to 3676 items (1772 irrelevant,1772 relevant,132 semantic UNKNOWN). Per-item CE uses fixed class weights N/(3*n_class), with a global mean;64 structural UNKNOWN rows bypass the model. The three-class raw axes are logit1−logit0 and logit2−logsumexp(logit0,logit1). Validation freezes one support and one relevance cutoff per seed, common across goals and languages.

Nine directly recorded finite epochs, **2070 accepted updates**, **33084 training pair presentations** and **984042 nonpadding training tokens**. Saved epoch wall time totals **583.163s**; this excludes setup/scoring and is not deployment latency. Evaluation: **16992 valid pair forwards**, **589712 nonpadding tokens**, zero cuts/errors; structural UNKNOWN bypasses the model. Whole study-process peak RSS **1,503,281,152 bytes** includes training/runtime state and is not an installed inference-memory measurement. Private weight hashes are in [the artifact inventory](../../../artifacts/tool-role-support.json); no model is hosted or compatible with the native ModernBERT provider.

## Coverage and remaining limits

These are actual CLI/API values on68authored fixtures, authored questions/English captions, controlled counterfactual numbers and labels defined by measurement-role equality. Final binary supervision/strings withhold DU/DF/GZIP, three correlated tool sources with shared primitive concepts; all31tool fields still exist in raw train/validation receipts. Labels, roles and receipt metadata are never model inputs. No production, human-reviewed task population or P2 necessity ground truth is established.

[wording-coverage.json](wording-coverage.json) shows an additional coverage gap: training uses only alias0/caption0 and alias1/caption1, validation alias2/caption2. Question/report phrasings are coupled. Crossed variants were absent. This and the English-pretrained backbone are hypotheses for a future controlled test, not demonstrated causes of the measured language gap. Loss reduction on training does not establish transfer. Retry, network and tracked/untracked Git relations remain absent from this cohort. The final is now exposed and cannot serve as fresh confirmation for the next design.

After completion, the current scalar loader corrected RoBERTa-family position capacity: a514-row table with padding index1 supports512 complete nonpadding tokens. Regression evidence is in `../semantic-next/position-window-red-archived.log` and `position-window-green-v1.log`. Old executed sources/protocol remain immutable; the current driver intentionally rejects reusing their old freeze with changed live sources. Receipt audits use saved source hashes and do not rescore models.

## Verification and next decision

The independent stdlib auditor checks saved data/view/source hashes, raw three-logit arithmetic, strict AUCs, all groups, calibration optimality, epochs, selection timing, gates and optional private weight hashes. Both audits PASS while every candidate fails its quality gate. The current suite passes162tests without skips (`../goal-full-tests-support-window.log`,25.261s); scoped Ruff0.16.10 F/E9 passes. Audit PASS means receipt consistency, not model approval.

```sh
python -m research.audit_tool_role_support
python -m research.audit_tool_role_support --verify-weights
```

Next: inspect a pinned multilingual ranking prior on these already-exposed pairs as a diagnostic; uncouple wording and complete documented retry/network/Git captures; reserve fresh confirmation before any new training/selection. No extra epochs, final threshold tuning, quantization or larger RoPE on these failed candidates. The full engine+LCC goal remains active, with useful selection and fresh downstream outcomes still required. Zero API calls, P2 admission, default change or publication.
