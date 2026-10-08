# Grounded tool-role supervision: data-phase receipt report

This report records the data phase before model execution. The later completed
[three-class study](../tool-role-support-v1/RESULTS.md) fails every seed; data-audit
PASS is not a learned-quality result. Counts and immutable capture receipts below
remain unchanged.

The data protocol was frozen before the main captures:
`932c23cd40b323e88186a9755e887a44ede076d168d6f08264b0446a022ce96b`.
Sources are saved under `sources/`, with capture start/end receipts in
`collection-events.jsonl`. These local hashes/timestamps are an auditable record,
not independent certification of preregistration.

| Split | Fixtures | Binary P1 rows | UNKNOWN rows | Unique projected pairs | Max raw/view tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 32 | 4608 | 256 | 3676 | 112 / 51 |
| validation | 12 | 1728 | 96 | 1292 | 109 / 48 |
| final | 24 | 2304 | 192 | 1674 | 120 / 58 |

Each split has equal English/Portuguese goal counts. Report captions remain
English. There are zero overlaps of original/projected inputs, fixture contents
or entities across splits. The validation corpus contains1808 unique raw pairs
out of1824rows; identical measured/swapped values sometimes produce duplicates.
Projected rows total4800/1800/2448, including semantic UNKNOWN. The unique counts
above include these semantic UNKNOWN pairs; they are not independent tasks.

All68authored fixtures executed in the same immutable Linux arm64 image
`sha256:86e9c5f09cf5c25f6cf891dda724c867d9cb05d4d6c955093fb625ba25fea1ef`,
source identity `58c65fd6f4f38111ebb82c6fce6f55b4370090ca28ddc8bc9c3ed5a01a5cc338`.
GNU coreutils9.7, gzip1.13 and Python3.13.16/C.UTF-8 are recorded by the worker.
It has no host mounts/credentials/network, a read-only root, UID65534,256MiB RAM,
one CPU,64processes,64MiB temporary space,≤60s and≤4MiB per output stream.
Only bounded seeds/counts are accepted; trusted templates, not caller programs,
run wc/stat/du/df/gzip and Python APIs. Inode/free-space/clock values are snapshots;
they need invariant checks rather than bitwise repeatability on another machine.

The1088raw observations provide2108fields. The independent auditor reparses all
31fields/fixture from saved CLI/API receipts and recomputes content counters,
logical/allocation relationships, child environment counts and timing deltas.
The worker additionally checked CLI fields against actual os.stat/statvfs and
authored content while files existed. Offline auditing does not recreate those
deleted files or independently resample their state. `audit-tokenizer.json` also
recounts every pair with the hash-checked local pinned tokenizer. Zero cuts,
model forwards, model training, API calls, P2 labels or default changes.

P1 relevance is equality of the requested and reported measurement roles,
regardless of whether the reported number is true. Each goal has the same numeric
multiset among positives and negatives: measured/value-swap variants defeat a
value-magnitude shortcut. There are4304numerically false claims,2152relevant;
1152/424/576relevant contradictions in train/validation/final. Half the variants
are controlled counterfactual claims, not actual tool stdout. Equal swapped
values remain true and are counted as such. Fixtures, questions, captions and
label contracts are authored; this is not sampled production/user-session truth.

There are192/72/144semantic UNKNOWN and64/24/48structural UNKNOWN rows. The current
view rejects the latter but still projects the former: it cannot decide whether
a natural goal is answerable. A future classifier/support policy must be tested
before it can authorize DROP. UNKNOWN is not converted to a negative P1 label.

Training/validation binary roles cover nine families from wc/stat/clock/command/
environment. Final binary roles cover six families from **three** held-out sources
(DU/DF/GZIP), four families sharing DF receipts. Logical/allocation and other
underlying concepts overlap development; this is source/wording/input transfer,
not six independent unseen concepts. Packet versus byte, retry wait versus count,
and tracked versus untracked relations are absent. Their earlier failures remain.
No generic calibration, Portuguese competence or useful-context claim follows.

The worker captures all31fields in every fixture, including DU/DF/GZIP fields in
train/validation **raw receipts**. Those fields and commands never enter their
binary model strings or labels. The source holdout is therefore defined over
model supervision/inputs, not absence from the archived raw measurement files.
UNKNOWN rows intentionally share a WC source across splits. A training pipeline
must use the declared pairs, not feed receipt metadata/raw commands to the model.

Preserved setup failures: initial calibration rejected incompatible `df --inodes`
and `--output` options. It supplied zero admitted fixtures. The correction was
tested and the original `build-recipe/`, `calibration-probe/` and failure log remain.
`build-recipe-v1/` and `calibration-probe-v1/` record the corrected worker; exposed
calibration seed442420 is excluded from all main splits. Token counting first
found a missing local tokenizer cache; only five pinned files were restored with
verified TLS and SHA256 (`tokenizer-restore.json`). No protocol/data were changed.

Post-capture lint found one unused runtime import. Only current source was cleaned;
captured sources/image/receipts remain intact. `build-recipe-v2/` records the new
source identity6ed98b5b21c961a692578517e34755be64a2f1808f66f8fb7079e8a923a837c2,
imagee4f3e87adc6591755bc0a5646e6555fd43e299923cc80c033c3392bf84b21878.
The worker program itself is unchanged. Archived-data auditing still passes;
the current live source intentionally cannot overwrite/reuse the old freeze for
capture. Ruff0.16.10 scoped F/E9 passes, and the current full suite passes154tests
without skips (`../goal-full-tests-grounded-current.log`,15.214s).

Reproduce receipts without Docker, models or APIs:

```sh
python -m research.audit_tool_role_data
```

Optional `--verify-tokenizer --snapshot PATH` recounts tokens from the five pinned
local files with transformers; it loads no model weights. Reexecuting tools is a
separate capture, not receipt auditing: explicitly build the pinned base/worker,
freeze a new output directory and preserve its new receipts. Do not replace this
capture's stateful values or overwrite any failed attempt.

151engine/consumer integration tests passed without skips in
`../goal-full-tests-grounded-tools.log`. Subsequent objective-helper tests are
separately recorded; the complete suite with those helpers passes154tests without
skips (`../goal-full-tests-grounded-training-prep.log`,15.134s). Neither this data
PASS nor tests approve a model. The full
engine+LCC goal remains active; next is bounded P1+UNKNOWN adaptation, then
LCC outcomes/efficiency if a candidate clears all quality criteria.
