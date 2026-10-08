# Experimental checkpoint card

This card describes the local clean research control `models/exp02e-unfreeze2`.
It is not a released checkpoint or a validated replacement for Laya/Jev.

## Intended operation

The neural provider exposes `rank_context` for experimental
objective/block ranking. The LCC integration is explicit and shadow-only: every
block is KEEP, failures/over-window pairs are UNKNOWN. Raw logits are neither
calibrated relevance probabilities nor counterfactual necessity estimates.

The package also has a separate dependency-free `rank_observations` operation
with caller-supplied entity/field/window slots. It is an exact supported-record
retrieval contract, not this checkpoint's learned capability. See
[the API contract](docs/10_OBSERVATION_OPERATION.md).

The direct-P1 study trained six derivative checkpoints (frozen/last-two × three
seeds), three completed epochs each, with complete training pairs ≤628 HF tokens.
Validation selected last-two before final inference: mean final AUC .7145, all
seeds fail .90, and mean wrong-entity-anomaly rejection is 1.85%. Those checkpoints
are not adopted or publicly hosted. Sources/splits/epoch receipts and raw scores
are in research/goal-engine-2026-10-04/direct-relevance-v1/. They do not replace
this control's historical metadata or establish neural long-context capability.

The subsequent semantic tool study has a preserved numerical failure: one MPS
seed produced nonfinite losses and no final result. A separate CPU comparison
completed six derivative candidates, three finite epochs each, with pairs ≤79
HF tokens. Validation selected last-two; final mean pooled AUC .5661 and paired
AUC .6910, with only 4.17% negative rejection at validation thresholds. All seeds
fail. These are authored P1 measurement relations, not independently reviewed
necessity labels; see research/goal-engine-2026-10-04/semantic-tool-cpu-v2/.
Current training/checkpoint guards reject nonfinite values; this does not explain
the prior numerical cause or establish MPS training reliability.

The compact ranking-pretrained MiniLM derivative is a separate architecture and
research study (22,713,601parameters). Six full adaptations complete three finite
epochs each on18 exposed development families, with eight new final pair families
reserved before training. Validation-selectedBCE final pooled AUC.8279,
same-goal ordering.8542,negative rejection.3776; every seed fails. A fixed generic
report control also fails. It is not substituted after observing another arm's
final and is not compatible with this native ModernBERT provider.
See [local derivative artifacts](artifacts/compact-relation.json) and the
[compact study](research/goal-engine-2026-10-04/compact-relation-v1/RESULTS.md).
Those authored P1 labels, repeated projected inputs and shared schemas are not
external, human-reviewed production or P2 evidence. No derivative is adopted.
The measurement questions and reports are English. Portuguese or multilingual
semantic relevance is not measured by these studies.

A later cohort includes English/Portuguese goals against English captions and
actual tool values on68authored fixtures. Three full adaptations with fresh
three-class heads completed three finite epochs each. Mean final pooled/within-goal
AUC.733249/.733796, negative rejection.102431 and UNKNOWN drops7/16/8 all fail.
EN/PT pooled means.845684/.626288 are measured on that authored cohort, not general
language competence. All three derivatives remain unadopted and privately stored;
see [the support results](research/goal-engine-2026-10-04/tool-role-support-v1/RESULTS.md)
and [artifact hashes](artifacts/tool-role-support.json). These changes combine
head initialization, adaptation and supervision; they do not isolate a cause.

A later frozen multilingual scalar control (117,641,089parameters) scores the same
exposed tool-role pairs:pool.785710/within-goal.846788,EN/PTpool.841622/.742775.
It fails the diagnostic.90criterion and has no support/DROP authority. Its model,
vocabulary and pretraining differ; no isolated language cause, LCC outcome or
useful-context capability follows. See [diagnostic receipts](research/goal-engine-2026-10-04/semantic-next/multilingual-frozen-v1/RESULTS.md).

The next data phase captures 68 fresh authored Retry/UDP/Git fixtures and 1,224
actual fields, with source-bound direct-record labels and explicit UNKNOWN for
derivation/diagnosis/broader relevance. All primitive fields/tools occur in train;
final reserves pair combinations and wording, not unseen sources. Real artifact
checks preserve the original ranking margin when expanding to three outputs;
they are initialization checks, not candidate quality. The later classifier/last-two
adaptation (3,697,923 trainable of117,641,859 total parameters) completed nine finite
epochs. Every seed fails: pooled/within-goal means .643959/.666233, negative rejection
.088252, Portuguese rejection0. UNKNOWN DROP0 is a point result, not a safety
certification. No useful-context claim or native-provider substitution follows.
See [data and limits](research/goal-engine-2026-10-04/tool-relations-grounded-v1/RESULTS.md),
[training receipts](research/goal-engine-2026-10-04/tool-relation-support-v1/RESULTS.md)
and [private derivative inventory](artifacts/tool-relation-support.json).

The next independent-support/conditional-ranking experiment is development-only:
one seed/three finite epochs on exposed original train/validation, no final scoring.
Trainpool.976310/within-goal.972222 but validation.556345/.613426,negativeDROP
.012731. All semanticUNKNOWNrecognized, yet78.18%ofvalidationbinary records are
UNKNOWN. It fails the policy gate and is not adopted. Objective and headLR change
jointly, not an isolated causal result. See [development receipts](research/goal-engine-2026-10-04/factorized-relation-dev-v1/RESULTS.md)
and [private artifact identity](artifacts/factorized-relation-dev.json).

The latest varied-state development corpus measures96new authored fixtures/
1,728fields, with separate16fixture calibration excluded. It connects52competing
field pairs and crosses goal/report wording and EN/PT language. Saved labels and
complete inputs pass independent source/token audits, with no split overlap and
no truncation (maximum76projected pair tokens). All primitives/tools/pair edges
are known training scope. A subsequent one-seed/three-epoch development adaptation
passes exposed train/validation: pooled.983074/.968897, validation within-goal
.977276 and negative DROP.810472. Preservation includes UNKNOWN; validation
binary UNKNOWN.389235 remains a limitation. Independent input/math/calibration/
private frozen-weight audits pass. This separate117.6M multilingual architecture
is not a native ModernBERT replacement. That development checkpoint preceded the
fresh confirmation below; useful semantic LCC outcomes remain unverified.
See [complete results](research/goal-engine-2026-10-04/varied-relation-dev-v2/RESULTS.md)
and [private artifact](artifacts/varied-relation-dev.json). No adoption.
Independent seeds202/303 subsequently completed the same three-epoch development
recipe; validation pooled.966275/.968888 and negative DROP.826998/.832407.
Their independent score/calibration/private-weight audits pass. A separate fresh
confirmation completed with all three weights/cutoffs locked beforehand. Every
candidate fails: pooled.858590/.870348/.850205, retention.556436/.655497/.593073,
semanticUNKNOWN recognition.699074/.703993/.518953 and UNKNOWN DROPs1568/1220/1716.
The immutable scalar pooled.874211 exceeds all three on this fresh population,
but has no DROP authority. Independent evidence audit PASS; adoption is rejected.
Useful semantic LCC outcomes remain unproven. See [final results](research/goal-engine-2026-10-04/varied-relation-confirm-v1/RESULTS.md) and
[current state and scope](research/goal-engine-2026-10-04/varied-relation-confirm-v1/STATE.md).
See [actual data and limitations](research/goal-engine-2026-10-04/tool-relation-states-v2/RESULTS.md).
This does not establish a76token useful dossier window or general LCC relevance.

The later goal-wording pilot reuses the original 64/32 development fixtures for
eight relevance fields/four within-tool distinctions; all18fields remain in
semantic UNKNOWN cases. One fixed seed/three finite epochs fails: train/validation
pooled AUC .840858/.625629, validation within-goal .694824, negative DROP .001953 and
binary UNKNOWN .998047. Its policy emits no explicit KEEP on validation. Independent
data/update/calibration/score/private-weight audits pass with an explicit original
relative-path metadata erratum; the frozen protocol remains unchanged. This
bounded development result has no fresh final and is not an isolated wording
ablation. See [results](research/goal-engine-2026-10-04/wording-development-pilot-v1/RESULTS.md)
and [private artifact](artifacts/wording-development-pilot.json). No adoption.

A separate [goal-only development probe](research/goal-engine-2026-10-04/goal-interpreter-probe-v1/RESULTS.md)
freezes eight field contracts and applies an unchanged upstream mMARCO MiniLM
reranker to query/definition pairs with lexical controls. Both fail the combined
router gate; no candidate training, fresh confirmation or LCC
outcome is performed. Point evidence is exploratory and its automated MEASURED
claim gate returns BLOCK. This probe adds no useful-context or replacement claim.

Separate support/field supervision is subsequently tested on cached twelve-score
features and384-dimensional frozen-query means. Both development recipes fail;
the latter fits train but yields only9 correct/70 accepted validation bindings,
including55 unsupported accepts. Full unconditioned field accuracy is114/240.
Small heads (117/3,465 parameters) do not change the encoder's memory footprint or
establish whole-engine efficiency. These are exposed authored exploratory results,
claim-gate BLOCK, no fresh confirmation/adoption. See [receipts and limitations](research/goal-engine-2026-10-04/goal-embedding-pilot-v1/RESULTS.md).

The underlying v0.4 supervision distinguishes authored anomalous incident lines
from healthy decoys and unrelated lines. It does not establish that every healthy
block is irrelevant to an LCC objective. Healthy readings can be useful negative
evidence. Applying a threshold to discard them needs a different label/outcome
contract and validation; this checkpoint must not silently authorize that policy.

## Architecture and provenance

- Backbone: `answerdotai/ModernBERT-base`, line attention, last two encoder layers
  adapted, scalar objective/block head.
- Current model/tokenizer load pin: `8949b909ec900327062f0ebf497f51aef5e6f0c8`.
  The historical checkpoint did not record this revision. The current loader pin
  is not evidence of the original training load identity.
- Clean corpus: `corpus-exp02/0.4`, 18 training domains, four domain holdouts;
  saved train/val/OOD counts 2340/810/960. Signature/content-hash separation is
  verified; semantic independence of all generator/probe families is not.
- Saved training configuration: seed 0, three reported completed epochs,
  `max_len=1024`, temperature .6. Epoch history was reconstructed from terminal
  evidence, not an immutable run attestation. Current audits preserve and check
  that archived history; they do not reexecute original training.
- The native backbone has an 8192 HF-token pair window. Training length and
  inference window are separate quantities. A larger window does not imply
  training exposure at that length or useful decision quality.
- Checkpoint/config hashes and artifact inventory: [ARTIFACTS.md](ARTIFACTS.md),
  [artifacts/models.json](artifacts/models.json), and the frozen experiment protocols.

## Evaluation

[The engine + LCC report](research/goal-engine-2026-10-04/REPORT.md) preserves raw
scores and scope. On complete near-8192 HF inputs in the known 62-case suite,
J=.8345/D=.7360; neither clears .90. On 480 fresh synthetic holdout items,
J=.6524/D=.6325. Three-seed BCE/pairwise/joint head candidates fail the fixed
holdout criterion. Fresh matched-objective normalization has a gain interval
including zero and is not admitted.

In the bounded four-task LCC 8K/32K diagnostic, the native shadow path removes zero
context. It is therefore not an efficient compression replacement. Those tasks
are known curated contracts, not independently sampled production sessions.
Referenced replay reliability fails; all replay records remain ineligible for P2.

## Reproduction and access

Native inference after explicit local artifact setup has been checked on macOS
arm64/Python 3.14 and Linux arm64/Python 3.13 CPU, offline. Other platforms and
training reproductions are unverified. Historical and new receipt audits are
separate from rerunning model training. See [README.md](README.md) for commands.

No public weight URL exists. Backbone/code and imported references retain their
licenses and attribution; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
A checkpoint release still needs immutable hosting, complete training/data
provenance, explicit weight-license obligations, and checksums. Repository source
availability must not be advertised as publicly hosted model availability.
