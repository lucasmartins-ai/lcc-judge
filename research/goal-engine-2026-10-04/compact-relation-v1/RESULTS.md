# Compact MiniLM adaptation — completed, failed adoption criterion

2304 train /576validation /512final P1 measurement pairs. Old18 exposed pair
families now all development; eight newly authored final pairs reserved before
adaptation. Entity/original-input/projected-input hashes do not overlap splits.
Unique model inputs are2208/576/496: some different-entity records collapse after
the validated scope projection. Rows are not independent semantic observations;
schemas/author/primitive vocabulary remain shared, with only three paraphrases
per question/measurement side. No external/human/P2 label claim.

Six full22,713,601-parameter MiniLM adaptations: BCE/joint×seeds101/202/303,
three fixed epochs, whole16-row batches, AdamW LR.00002,CPU/fp32/8threads.
Joint is0.5BCE+0.5same-goal ranking; all arms use the identical pretrained head
and batches. No final epoch selection, additional epochs or selective retries.
All18epochs and2592updates finite;41472 actual training pairs,879480nonpadding
tokens. Total saved epoch wall time483.642s. Train/val/final pairs≤31/30/28tokens,
no truncation. Candidate metadata is written after completed finite epochs and
validation, not reconstructed from terminal. Weights stay outside Git.

Validation mean AUC selectedBCE before any final inference.

| Final arm | Pooled AUC | Same report, two goals | Same goal, candidates | Recall | Negative rejection |
|---|---:|---:|---:|---:|---:|
| Frozen upstream | .7336121 | .7773438 | .7910156 | .9843750 | .0898438 |
| Selected BCE,3seed mean | .8279470 | .9179688 | .8541667 | .9687500 | .3776042 |
| Joint,3seed mean | .8331197 | .9257813 | .8665365 | .9726563 | .3684896 |

Every seed in both arms fails the original frozen criteria: pooled/same-report
goal contrast/same-goal candidate ordering≥.90, recall≥.95, rejection≥.70,
complete population. Joint is not substituted after seeing its slightly higher
final mean. Selected pooled family-bootstrap95%[.7455461,.9157088] uses2000whole
eight-family draws and is descriptive, not population reliability.

| Selected BCE final family | Pooled | Same-goal ordering | Negative rejection |
|---|---:|---:|---:|
| certificate | 1.0000 | 1.0000 | 0.9375 |
| file_text | 0.9854 | 1.0000 | 0.1979 |
| network_receive | 0.6781 | 0.6771 | 0.1667 |
| repository_files | 0.7507 | 0.8125 | 0.2500 |
| retry_wait | 0.7367 | 0.5417 | 0.5208 |
| scheduler_duration | 0.8392 | 0.8750 | 0.1250 |
| search_lines | 0.9736 | 0.9323 | 0.2708 |
| storage_entries | 0.8818 | 0.9948 | 0.5521 |

Several families have perfect/near-perfect ordering but poor global-threshold
rejection. Others fail ordering itself (especially retry_wait/network_receive).
This prevents calling offset calibration the sole bottleneck. The goal axis
paired_auc in this study differs from the within-objective paired metric in
earlier incident triplets; those numbers must not be compared as the same metric.

Peak whole-study process RSS1,321,680,896bytes includes framework, optimizer,
training and repeated model loads, not deployment RSS or a matched latency claim.
7616 actual validation/final pair evaluations including the frozen control.
Zero API calls, no model adoption/default change, no P2 admission.

Independent stdlib audit verifies archived source/data/projection/annotations,
epoch receipts, optional six weight hashes, raw metrics/thresholds/selection,
all seed gates and the descriptive bootstrap. Sources/hashes are not independent
temporal attestation or a reexecution of training.

`python -m research.audit_compact_relation_study`

`python -m research.audit_compact_relation_study --verify-weights`

A later fixed generic-report control is a separate exposed-cohort diagnostic in
../report-prior-diagnostic-v1/. It does not create new confirmation evidence.
