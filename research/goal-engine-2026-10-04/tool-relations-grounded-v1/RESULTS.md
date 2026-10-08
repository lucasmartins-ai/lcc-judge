# Actual retry, UDP and Git observations; new direct-record supervision

Historical completed data/initialization phase. The subsequent
[retained-ranking adaptation](../tool-relation-support-v1/RESULTS.md) trained three
seeds and fails. No raw measurement or frozen data protocol changed; statements
below about no candidate training describe this original phase. Its final is now
exposed, and new work is recorded in ../tool-relation-support-v1/NEXT_DESIGN.md.

The engine + LCC goal remains active. This phase closes a missing **measurement
and supervision** step. It has not trained a new candidate or demonstrated useful
context, efficient LCC outcomes, or a replacement for Laya/Jev. The previous neural
quality failures remain failures. No default, P2 admission or public release changed.

## Actual observations

The new trusted worker records 18 fields per authored fixture:

- Retry: attempts, failed calls, sleep callback count, scheduled sleep, measured
  sleep callback time and whole elapsed duration. The initial call counts as an
  attempt; scheduled waiting is not measured sleeping or total elapsed time.
- UDP: sent/received datagrams and sent/received payload bytes. Every fixture
  contains an empty datagram, which still counts as a datagram. These are actual
  loopback socket events, not IP packet or wire-byte capture.
- Git: index, untracked, ignored and clean tracked path counts; index and worktree
  edit counts; present tracked and nonignored untracked file bytes. NUL-separated
  output preserves spaces and newlines in paths. A deleted tracked path remains
  in the index and contributes no current file bytes. Rename, merge, submodule
  and production repository behavior are outside this fixture contract.

| Collection | Seed | Fixtures | Independently recounted fields | Capture wall time |
|---|---:|---:|---:|---:|
| Exposed calibration | 442500 | 4 | 72 | 0.872 s |
| Train | 442511 | 32 | 576 | 1.356 s |
| Validation | 442512 | 12 | 216 | 0.976 s |
| Reserved final | 442513 | 24 | 432 | 1.188 s |

The main cohort has **68 fixtures and 1,224 fields**, separately from calibration.
All six pairwise fixture-content intersections between the four collections are
empty. This is authored-content separation, not semantic or production independence.
All captures completed with exit zero. Raw records and events remain immutable;
no experimental capture was retried or overwritten.

Actual versions are Git 2.47.3, Tenacity 9.1.4 and Python 3.13.16 on Linux arm64.
Each main split has 2–8 datagrams per fixture. Git index/worktree edit counts are
fixed at 2/3 by the fixture template: this phase does not cover varied edit counts.
UDP sends and deliveries coincide on the successful local transport, so equality
of values does not establish semantic interchangeability of the two directions.

[Cohort audit](cohort-audit.json) independently recounts raw API/CLI evidence;
[cohort identity](cohort.json) is
`91c44e2e9150b6cf73571c556aeed422ce0ebdcb32335dbb08acaa22850265aa`.
The individual raw files and their protocols are in `calibration/`, `train/`,
`validation/` and `final/`. Audit PASS concerns saved receipts, not physical
attestation, independently sampled tasks or human-reviewed necessity labels.

## Confined, pinned execution

[The current build receipt](build-recipe-v2/build.json) records image
`sha256:3f6cf84bea54d6d34a9076b9a7142bf5dbafa676cc598bd952c744445ab81ef4`,
source identity `b7d1db093b638050280917604068e42909d095a5baafa640ad962f0f2557b375`
and dependency identity `255600482631fdd1a04f299af2f0f1e748d783caafa896bdee322fce18f099bf`.
The recipe installs 31 exact hashed Debian package files and the exact Tenacity
wheel, offline from the original immutable Python base. Private dependency blobs
and copied build-context blobs are ignored by Git; manifests and source recipes
are retained. The earlier build remains preserved and supplied no main capture.

The worker runs without external networking, host mounts, privileges or caller
code, under a read-only root, UID 65534, one CPU, 256 MB memory, 64 PIDs, bounded
tmpfs, streams and timeout. Loopback UDP stays inside the isolated container.
Unavailable or failed execution is UNKNOWN; completed earlier source receipts
are preserved when a later source fails, and the whole failed capture is excluded.
This behavior was checked with regression tests, not a broad security certificate.

Transport factoring changed the original core worker's source identity, so its
image was rebuilt separately: [core-worker-build/build.json](core-worker-build/build.json).
Its 31-field measurement program remains unchanged. Earlier capture protocols,
source snapshots and image identities are preserved, and their audits still pass.

## Supervision and input coverage

[The new frozen supervision protocol](supervision-v1/protocol.json), SHA
`1fca8ea4cd2fbbde0d4f06abc0ef0c52eb905a92c1010448dfff5ea0dcae8681`,
was saved before deriving labels or scoring a candidate. Raw collection preceded
the language/label freeze; this is not a claim that labels preceded observation.

The binary task explicitly asks for the **direct measurement record**. Positive
reports claim the requested field; negatives claim the other field in a pair.
Measured and value-swap claims balance numeric multisets for both labels under
each goal. Incorrect requested claims remain relevant contradictions. They are
authored claims bound to real source values, not all true tool statements.

Related counters may be useful for deriving an answer or diagnosing a failure.
Those broader questions are **UNKNOWN**, with the original block retained. Direct
field equality is not the label for generic LCC usefulness and does not authorize
discarding related evidence in a broader task. Structural records without a
complete binding also stay UNKNOWN before model inference.

| Split | All rows | Binary | Semantic UNKNOWN | Structural UNKNOWN | Unique projected pairs | Maximum raw / projected HF tokens |
|---|---:|---:|---:|---:|---:|---:|
| Train | 4,864 | 4,608 | 192 | 64 | 3,592 | 113 / 50 |
| Validation | 1,824 | 1,728 | 72 | 24 | 996 | 109 / 46 |
| Final | 2,496 | 2,304 | 144 | 48 | 864 | 114 / 51 |

English/Portuguese goals are balanced, with English authored captions. Training
has all four intent/caption combinations 0:0, 0:1, 1:0 and 1:1, 1,152 binary rows
each, eight raw fixtures per combination. Each fixture receives one combination;
there are no four independent replications of that fixture. Format, level and
question template vary separately. Validation/final use indices 2/3.

Final reserves six new **pair combinations**, fresh wording and fixture/entity/
effective inputs. All 18 primitive fields and all three sources occur in training.
There is no unseen-source/domain claim. Saved strings, labels, raw bindings,
numeric balance and every token count were independently audited with zero model
forwards: [audit-tokenizer.json](supervision-v1/audit-tokenizer.json).
Raw, projected, fixture and entity cross-split intersections are zero. Repeated
rows and only three source clusters prevent population reliability intervals.

Training deduplication yields 1,724 IRRELEVANT, 1,724 RELEVANT and 144 semantic
UNKNOWN items: [training-preparation.json](supervision-v1/training-preparation.json).
The 64 structural UNKNOWN training rows bypass the model. Deduplication remains
inside train; original validation/final populations are kept for future scoring.

## Ranking initialization checked, no candidate trained

The new initializer retains a scalar ranking head as
`logit(RELEVANT) - logit(IRRELEVANT)`. Only the final linear output expands; the
encoder and XLM-R classifier's intermediate dense layer retain their parameters.
UNKNOWN receives an uncalibrated seeded row. This provides no safety guarantee.

Tests cover tiny real BERT/XLM-R models, deterministic initialization, unchanged
caller CPU RNG, avoidance of accelerator RNG reseeding and rejection before
mutation. The current exposed implementation smoke also
loads the exact previously pinned multilingual artifact locally: three examples
before/after, six pair forwards and 72 nonpadding tokens per pass. Preserved
parameter hashes match; maximum absolute margin error is **4.76837158203125e-7**
against tolerance 1e-6. Parameters expand from 117,641,089 to 117,641,859.
[Receipt](ranking-prior-smoke-v2/receipt.json), [protocol](ranking-prior-smoke-v2/protocol.json).
No labels, candidate quality, support recognition or reserved cohort were tested.
No candidate weights were saved. The original downloaded artifact is unchanged.
The first smoke remains in `ranking-prior-smoke/`, before the regression fixed
global accelerator seeding. Both preserve the ranking margin; their UNKNOWN row
identities differ. Together they executed 12 exposed implementation pair forwards,
not any validation/final candidate forwards.

## Recount without repeating experiments

```sh
python -m research.audit_tool_relations --out research/goal-engine-2026-10-04/tool-relations-grounded-v1/train
python -m research.audit_tool_relations --out research/goal-engine-2026-10-04/tool-relations-grounded-v1/validation
python -m research.audit_tool_relations --out research/goal-engine-2026-10-04/tool-relations-grounded-v1/final
python -m research.audit_tool_relation_supervision
python -m research.audit_tool_relation_supervision --recount-tokenizer
```

Default supervision audit uses the standard library and archived receipts. Optional
token recount requires the separately pinned local tokenizer and Transformers;
neither command loads model weights or executes tools, training or APIs. Upcoming
work and success criteria are in [NEXT_TRAINING.md](NEXT_TRAINING.md).

Current verification: **185 tests, zero skips, 17.863 s**, including four local LCC
integration checks, in `../goal-full-tests-tool-relations-final-current.log`.
Scoped Ruff 0.16.10 F/E9 passes. The earlier test run with four consumer skips
is preserved; the current run includes the LCC checkout on PYTHONPATH. The mocked
failed-capture regression prints an UNKNOWN receipt after the unittest summary;
it is a simulated transport failure, not a failed or admitted main capture.
The independent prior core-data, support-study and multilingual audits still pass,
without tools/model/API reexecution or changes to their historical sources.
