# Semantic tool measurement relevance — completed CPU comparison

P1 asks whether a report directly describes the measurement requested by a natural-language objective. The same report is queried under two neighboring objectives and flips label. An ordinary value can be relevant. Labels follow authored concept slots, not operational health, necessity, outcome-backed P2 or externally reviewed semantic truth. Models receive objective/report strings only.

1152/384/384 train/validation/final pairs;12 training families and six reserved final concept-pair families. No entity/content-hash overlap. Primitive vocabulary, author and report forms are shared. Full HF pairs ≤79 tokens; no cut or incomplete report span. Low/high numeric bands and INFO/WARN/ERROR are independent of the binary label.

## Preserved numerical failure

The original MPS protocol semantic-tool-v1 completed five finite candidates. Last-two seed 303 wrote three NaN epoch-loss records, then failed threshold selection, with no saved weights/validation/selection/final predictions. Its loop had no nonfinite guard. The independent incomplete-run audit verifies 15 finite epochs plus three in valid passes; it does not manufacture a missing final comparison. JSON NaN tokens in those historical records are preserved failures, not valid accepted metadata.

Fresh train-only instrumented seed 303 checks were finite for 144 first-epoch batches on CPU and MPS, plus a separate 40-batch MPS check. Per-stage synchronization changes execution; the original cause remains unresolved. The40-batch metadata has an off-by-one41 count;40 raw rows are authoritative. No diagnostic model was admitted or scored on final data.

## Separate CPU protocol

CPU-v2 froze source/data/criteria separately, preserved the same previously unscored final families, and ran all six candidates anew with finite-update guards. Three matched seeds, three finite epochs per arm, batch8; parent backbone/line scorer retained and heads reset at the matched seed boundary. Frozen/cache and last-two/native now both use CPU. This comparison changes device/cache trajectory and guard checks; it does not isolate or explain the prior MPS failure.

Validation selected last-two before final inference. Thresholds use validation only (greatest raw-logit threshold with ≥.95 recall). Per-seed final gate: pooled/paired AUC≥.90, recall≥.95, rejection≥.70; full population, zero errors/cuts.

| Arm | Mean pooled AUC | Mean paired AUC | Recall | Negative rejection | Family-bootstrap95% AUC | Seeds passing |
|---|---:|---:|---:|---:|---|---:|
| frozen | 0.5591 | 0.6892 | 0.9670 | 0.0399 | [0.5204,0.6050] | 0/3 |
| last-two | 0.5661 | 0.6910 | 0.9618 | 0.0417 | [0.5238,0.6146] | 0/3 |

Only 4.17% of known irrelevant reports are rejected by the selected arm at its validation thresholds. High recall is obtained by preserving most reports, not useful selection. All six candidates fail. Family intervals use2000 fixed NumPy draws/seed78112; only six authored groups, so descriptive, not population reliability.

| Control | Pooled AUC | Paired AUC | Eligible rows / total | Cuts / errors |
|---|---:|---:|---:|---:|
| bge | 0.6269 | 0.6667 | 384/384 | 0/0 |
| laya | 0.5101 | 0.5156 | 384/384 | 0/0 |
| lexical | 0.5895 | 0.6250 | 384/384 | 0/0 |
| parent | 0.5168 | 0.6146 | 384/384 | 0/0 |

All controls use identical input identities. Raw epoch training time sums to 344.05s; this excludes model loading/cache/evaluation and is not an efficiency or architecture comparison. Complete stage logs remain in the parent directory.

## Validation and decision

The stdlib independent audit reconstructs every rendered concept/query annotation from the archived dictionary, split/content identity, goal-dependent pairs, raw pooled/paired scores, validation threshold/selection, epoch receipts/optional weight hashes and every seed gate. It does not reexecute training or rederive NumPy bootstrap intervals. The first audit invocation happened before summary completion and failed on the missing file; after the summary finished, the complete audit passed without changing scores.

`python -m research.audit_semantic_study --out research/goal-engine-2026-10-04/semantic-tool-cpu-v2`

No neural/default/P2 promotion. These failures occur with short complete inputs; expanding RoPE cannot by itself fix this measured semantic relation. The next cheap decision is a ranking-pretrained compact cross-encoder on a frozen known-cohort diagnostic, before further adaptation/new final families. Current final families are exposed after this study; future models cannot treat them as untouched confirmation.

Production code now stops on nonfinite loss/gradients/update state and rejects corrupt/overflowing checkpoint tensors before mutating a model.120 engine tests and 52 relevant consumer tests pass. Installed numerical guards/native shadow/typed operation pass scoped offline macOS arm64/Python3.14 and Linux arm64/Python3.13 smoke. No MPS training stability or broad hardware certificate follows.
