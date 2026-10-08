# Retained multilingual ranking: all three candidates fail

The fixed adaptation completed all three seeds and nine finite epochs. **No
candidate passes.** The full engine + LCC goal remains active; these models are
not adopted, substituted into the native provider, or sent to LCC outcomes.

## Frozen recipe

[Protocol](protocol.json), SHA
`f28b63f52d46f8ad6f3d974b383f9edd81cc84184383965f81b3bea29669fe4e`,
was saved before execution. The exact multilingual artifact is
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` at revision
`8008f0154ca2387468013ed439df09d70c122412`; base weight SHA
`5daeca2481a76b5976a2bdc32f0a78532b6716da4f8cd3ff59460ef8d2f359b4`.
The scalar ranking output was retained as an initial relevance margin. UNKNOWN
received a separate seeded row; the intermediate classifier dense was preserved.

Total parameters: **117,641,859**; trained parameters: **3,697,923**, classifier
and last two XLM-R blocks. The other **113,943,936** parameters were frozen, and
embeddings/first ten blocks ran in evaluation mode during training. CPU/float32,
eight threads, batch16, seeds101/202/303, three fixed epochs, AdamW2e-5/wd.01.
The 3,592 unique train inputs have classes1,724/1,724/144; global class weights
apply to per-item CE. Structural UNKNOWN bypasses the model. No metadata enters
the two natural model strings. Scores are derived in Python double from persisted
float32 logits, so the score axes can be exactly recounted.

The data are the [actual Retry/UDP/Git cohort](../tool-relations-grounded-v1/RESULTS.md).
The task is **direct recorded-field claim retrieval**, not generic LCC usefulness.
Broader derivation/diagnosis/usefulness is UNKNOWN and retains the source block.
Final has six new pair combinations and wording; all fields/tools occur in train.
Authored fixtures/captions and repeated rows are not production sessions or P2.

## Complete final population

All three private weights and validation-only global support/relevance cutoffs
were saved in [selection.json](selection.json) before any final score. Binary
ordering includes every binary record, even records subsequently kept as UNKNOWN.
There was one complete final pass per seed and original scalar control.

| Seed | Pooled AUC | Within-goal AUC | Positive KEEP | Negative DROP | Semantic UNKNOWN recognition | UNKNOWN DROP |
|---|---:|---:|---:|---:|---:|---:|
| 101 | .655814 | .666667 | .958333 | .086806 | .944444 | 0 |
| 202 | .628048 | .665365 | .954861 | .086806 | .944444 | 0 |
| 303 | .648015 | .666667 | .958333 | .091146 | .944444 | 0 |
| Mean | **.643959** | **.666233** | .957176 | **.088252** | .944444 | 0 |

Relevant contradiction KEEP is1.0 and structural UNKNOWN recognition is1.0 in
every seed. The required pooled/within-goal .90 and negative DROP .70 fail widely;
semantic UNKNOWN recognition also misses .95. Zero UNKNOWN DROP is a point
observation on this cohort, not certified safety or evidence of useful compression.

English/Portuguese pooled means are .644267/.644245. English negative rejection
is .176505; **Portuguese rejects zero negatives**. English semantic UNKNOWN
recognition is1.0; Portuguese is .888889. Eight Portuguese semantic UNKNOWN
records per seed are kept as KEEP instead of recognized as UNKNOWN.

The original frozen scalar scores pooled .661983 and within-goal .710938 on
identical final inputs. It runs blanket shadow UNKNOWN/KEEP, with no support or
DROP authority. Adaptation did not improve those aggregate point scores. This is
not an isolated test of retaining the prior: data, architecture/training selection
and initialization differ from previous studies.

All seeds score retry attempts/wait and scheduled/actual waiting near1.0 within
goal. The two UDP direction pairs and two Git pairs are **exactly .50**. In each
of those four families, every seed retains the same report preference after the
goal flips, giving one correct ordering out of two. A global cutoff or monotone
calibration cannot reverse that missing conditional ordering.

## What the additional diagnosis establishes

A separately frozen exposed diagnostic selects the fixed first seed101, not the
best final seed, and makes one pass over the original train population. It retains
the original validation cutoffs; no training or threshold refitting follows.
[Fit protocol](fit-diagnostic-v1/protocol.json), [independent analysis](fit-contrast-analysis.json).

Training pooled AUC is **.807571**, within-goal .800130 and negative rejection
.026910, with all semantic UNKNOWN retained. Global class-balanced CE on the
first saved output for each unique train input is .906237. Argmax classification
assigns none of the144 semantic UNKNOWN inputs to class UNKNOWN, despite support
margin calibration recognizing them. That margin is a score, not a class probability.
Training fit is also below the desired gate; there is no evidence that a cutoff
alone can fix the design.

The training relation graph has **18 roles, nine pairs, nine disconnected
components**, one competing role per role. All six final pairs connect different
training components. These are measured coverage/contrast gaps. They do not prove
that connectivity, optimizer settings, initialization or frozen layers caused
the failures. The next design needs explicit conditional relation coverage and
scope/support treatment before another candidate; see [NEXT_DESIGN.md](NEXT_DESIGN.md).

## Execution and audit

Nine finite epochs produced **2,025 accepted updates**, 32,328 training pair
presentations and 1,111,464 nonpadding training tokens. Summed epoch wall time was
326.778 s. All frozen parameter hashes match after each epoch. Every accepted
update has ordered input hashes, loss and padded/nonpadding accounting in its
seed's `accepted-updates.jsonl`. Metadata comes from direct driver receipts,
not reconstructed terminal history.

Validation/final candidate and control evaluation totals **16,992 pair forwards /
658,792 nonpadding tokens**, zero cuts/errors. The later fit diagnostic adds
**4,800 forwards / 164,436 tokens**, 23.501 s; it is separate from candidate
validation/final. Whole study-process peak RSS is **3,520,970,752 bytes**,
including training, loading and allocator state; this is not installed inference
memory or an efficiency comparison with Laya.

[Receipt/math audit](audit.json) passes without weights or inference. The first
weight parser assumed all upstream tensors were float32. The immutable artifact
also contains an int64 `position_ids` buffer. An additive regression and checker
validate that exact 0..513 buffer while hashing only declared learned parameters.
The frozen trainer/protocol/scores remain unchanged. [Full weight audit](audit-weights-v2.json)
passes, including all candidate SHA values and frozen tensor bytes against the
original artifact. Its source snapshots are in `audit-weight-sources-v2/`.

```sh
python -m research.audit_tool_relation_support
python -m research.audit_tool_relation_weights
python -m research.analyze_tool_relation_fit
```

The first command audits receipts with the standard library; the second also
requires the private original/candidate artifacts but never loads model tensors.
Use the additive weight command above for this upstream artifact. The frozen
auditor's initial `--verify-weights` path rejects its known integer buffer.
The third recounts the exposed fit/contrast evidence without model/API calls.

Current verification: **194 tests, zero skips, 17.940 s**, including local LCC
integration, in `../goal-full-tests-relation-support-final.log`; scoped Ruff
0.16.10 F/E9 passes. The trailing UNKNOWN JSON in that test log is a mocked
capture failure, not a real study failure. Prior support receipt audit still
passes from its archived sources. All raw evidence and three private derivatives
are preserved; [artifact inventory](../../../artifacts/tool-relation-support.json).
No API, P2 admission, default, hosting or public publication changed.
